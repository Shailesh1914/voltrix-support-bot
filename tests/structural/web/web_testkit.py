"""Helpers and fixtures for the web structural tests (Session Q, spec 08).

No paid calls: Claude is the real AnthropicGenerator over a faked HTTP
transport (every Claude call is a recorded request). No network, no real
secrets file, no real data/ACTIVE_KB_VERSION. Expected values (status
codes, texts, limits, field names) are read from spec 08.
"""

import json
import logging
import re
import socket
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from ingestion import Chunk, KBInfo
from query import anthropic_api
from query.anthropic_api import AnthropicGenerator, make_client
from query.config import MODEL_ID
from query.flow import QueryFlow
from web import secret_source
from web.app import create_app

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC_08 = REPO_ROOT / "specs" / "08-deployment-spec.md"
REAL_KB_VERSION_FILE = REPO_ROOT / "data" / "ACTIVE_KB_VERSION"

FIXED_TIME = datetime(2026, 11, 11, 9, 30, tzinfo=timezone.utc)

# Fake secrets only. Each is distinctive, so a leak is easy to find.
KEY = "sk-ant-test-WEB-SENTINEL-KEY-0123456789"
CODE = "test-ACCESS-code-SENTINEL-77"
QUESTION = "E1 when the motor ramps up SENTINELQUESTION"
ANSWER_TEXT = "Lengthen P-06 SENTINELANSWER."
CHUNK_TEXT = "E-01 Overcurrent during acceleration — Fix\n\nLengthen P-06 SENTINELANSWER."

FAKE_ARTICLES = [
    ("KB-001", "E-01 Overcurrent during acceleration"),
    ("KB-002", "E-02 Overcurrent during deceleration"),
    ("KB-020", "Setting acceleration and deceleration ramp times"),
]

CLEARED_PREFIXES = ("ANTHROPIC_", "VOLTRIX_", "OTEL_", "FASTAPI_OTEL")
CLEARED_NAMES = ("HANDOFF_DIR", "HANDOFF_PATH", "IMAGE_TAG", "ACTIVE_KB_VERSION")


# --- Isolation ---------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """No test depends on the shell that runs it."""
    import os

    for name in list(os.environ):
        if name.startswith(CLEARED_PREFIXES) or name in CLEARED_NAMES:
            monkeypatch.delenv(name)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access in a structural test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture(autouse=True)
def no_real_secrets_file(monkeypatch):
    """Reading the real ~/.config/voltrix/secrets.env from a test fails."""
    real = anthropic_api.SECRETS_PATH.expanduser().resolve()

    def guard(module):
        original = module.dotenv_values

        def guarded(path=None, *args, **kwargs):
            if path is not None and Path(path).expanduser().resolve() == real:
                raise AssertionError("a web test read the real secrets file")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(module, "dotenv_values", guarded)

    guard(anthropic_api)
    guard(secret_source)


@pytest.fixture(autouse=True)
def no_real_kb_version_file(monkeypatch):
    real_read_text = Path.read_text

    def guarded(self, *args, **kwargs):
        if Path(self).resolve() == REAL_KB_VERSION_FILE.resolve():
            raise AssertionError("a web test read the real data/ACTIVE_KB_VERSION")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)


@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch):
    """The SDK's retries happen for real, without waiting."""
    monkeypatch.setattr(anthropic._base_client.time, "sleep", lambda seconds: None)


# --- Spec 08 values --------------------------------------------------------------------


@dataclass(frozen=True)
class Spec08:
    text: str
    bad_request_texts: dict[str, str]  # case -> error text
    max_question_chars: int
    page_max_question_chars: int  # the page's question box (section 4.3)
    blank_and_too_long_error: str  # the worked example after the 400 table
    success_fields: tuple[str, ...]
    health_fields: tuple[str, ...]
    access_denied: str
    internal_error: str
    demo_note: str
    min_code_length: int
    key_parameter: str
    code_parameter: str


def parse_spec_08(text: str) -> Spec08:
    flat = " ".join(text.split())

    def one(pattern: str, source: str = flat) -> str:
        found = re.findall(pattern, source)
        assert len(found) == 1, f"spec 08: expected one match of {pattern!r}, found {found}"
        return found[0]

    section = text[text.index("2. Body problems"):text.index("- Then the question goes through")]
    rows = re.findall(r"^\| (.+?) \| `([^`]+)` \|$", section, flags=re.M)
    lines = text.splitlines()
    health_line = next(line for line in lines if line.startswith("- Returns HTTP 200 with JSON: `status`"))
    return Spec08(
        text=text,
        bad_request_texts={case: error for case, error in rows if case != "Case"},
        max_question_chars=int(one(r"`question` longer than ([0-9]+) characters")),
        page_max_question_chars=int(one(r"The question box accepts at most ([0-9]+) characters")),
        blank_and_too_long_error=one(r"a question of only spaces that is longer than [0-9]+ characters gives `([^`]+)`"),
        success_fields=tuple(re.findall(r"`(\w+)`", one(r"result unchanged: ((?:`\w+`(?:, )?)+)"))),
        health_fields=tuple(re.findall(r"`(\w+)` \(", health_line)),
        access_denied=one(r'HTTP 401, JSON `\{"error": "([^"]+)"\}`'),
        internal_error=one(r'HTTP 500, JSON `\{"error": "([^"]+)"\}`'),
        demo_note=one(r'The page shows a note: "([^"]+)"'),
        min_code_length=int(one(r"The access code must be at least ([0-9]+) characters")),
        key_parameter=one(r"Parameter Store SecureString `(/voltrix/anthropic-key)`"),
        code_parameter=one(r"Parameter Store SecureString `(/voltrix/access-code)`"),
    )


@pytest.fixture(scope="session")
def spec_08() -> Spec08:
    return parse_spec_08(SPEC_08.read_text(encoding="utf-8"))


# --- Fakes ------------------------------------------------------------------------------


def make_chunk(article_id="KB-001", n=1, score=0.8, text=CHUNK_TEXT) -> Chunk:
    title = dict(FAKE_ARTICLES).get(article_id, f"Article {article_id}")
    return Chunk(
        chunk_id=f"{article_id}#c{n}",
        article_id=article_id,
        title=title,
        text=text,
        kb_version="v1",
        similarity_score=score,
    )


class CountingRetriever:
    """Contract-shaped retriever (spec 03); counts every call."""

    def __init__(self, chunks=None, kb_version="v1"):
        self.chunks = [make_chunk()] if chunks is None else list(chunks)
        self.kb_version = kb_version
        self.searches: list[tuple[str, int]] = []
        self.kb_info_calls = 0
        self.reads: list[str] = []

    def search(self, query: str, k: int):
        self.searches.append((query, k))
        return sorted(self.chunks, key=lambda c: (-c.similarity_score, c.chunk_id))[:k]

    def kb_info(self):
        self.kb_info_calls += 1
        return KBInfo(kb_version=self.kb_version, articles=sorted(FAKE_ARTICLES))

    def article_chunks(self, article_id: str):
        self.reads.append(article_id)
        found = [c for c in self.chunks if c.article_id == article_id]
        if not found:
            raise ValueError(f"unknown article_id {article_id!r}")
        return [replace(c, similarity_score=0.0) for c in found]

    def retrieval_calls(self) -> int:
        """Calls made while answering (kb_info is called once when the flow is built)."""
        return len(self.searches) + len(self.reads)


def tool_message(tool_input: dict) -> dict:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": MODEL_ID,
        "content": [{"type": "tool_use", "id": "toolu_1", "name": "submit_response", "input": tool_input}],
        "stop_reason": "tool_use",
        "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 10},
    }


ANSWER_REPLY = tool_message({"decision": "answer", "answer": ANSWER_TEXT, "used_article_ids": ["KB-001"]})
OUT_OF_SCOPE_REPLY = tool_message({"decision": "out_of_scope", "answer": "", "used_article_ids": []})


def error_reply(status: int, error_type: str) -> tuple[int, dict]:
    return status, {"type": "error", "error": {"type": error_type, "message": "fake error text"}}


class FakeClaude:
    """The fake Claude client: a MockTransport handler under the real SDK.
    Replies in order (the last one repeats); every call is recorded."""

    def __init__(self, *replies):
        self.replies = list(replies) or [ANSWER_REPLY]
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, BaseException):
            raise reply
        if isinstance(reply, tuple):
            status, body = reply
            return httpx2.Response(status, json=body, request=request)
        return httpx2.Response(200, json=reply, request=request)

    @property
    def calls(self) -> int:
        return len(self.requests)

    def generator(self, key: str = KEY) -> AnthropicGenerator:
        http_client = httpx2.Client(transport=httpx2.MockTransport(self))
        return AnthropicGenerator(make_client(key, http_client))


class MemoryHandoffStore:
    def __init__(self):
        self.records = []

    def append(self, record):
        self.records.append(record)


class RecordingFlow:
    """Wraps a real QueryFlow and keeps every result it returned."""

    def __init__(self, flow):
        self.flow = flow
        self.results = []

    def ask(self, question):
        result = self.flow.ask(question)
        self.results.append(result)
        return result


@dataclass
class WebBot:
    client: TestClient
    claude: FakeClaude
    retriever: CountingRetriever
    store: MemoryHandoffStore
    flow: RecordingFlow

    def ask(self, body=None, code=CODE, raw: bytes | None = None, headers=None):
        all_headers = {} if code is None else {"X-Access-Code": code}
        all_headers.update(headers or {})
        if raw is not None:
            return self.client.post("/ask", content=raw, headers={"Content-Type": "application/json", **all_headers})
        return self.client.post("/ask", json={"question": QUESTION} if body is None else body, headers=all_headers)


@pytest.fixture
def make_bot():
    """A web app over a real QueryFlow, a counting retriever and the fake
    Claude client. The threshold is a test value, passed explicitly."""

    def _make(*replies, chunks=None, threshold=0.5, kb_version="v1", image_tag="local", flow=None, store=None):
        claude = FakeClaude(*replies)
        retriever = CountingRetriever(chunks, kb_version=kb_version)
        store = store or MemoryHandoffStore()
        real_flow = QueryFlow(
            retriever,
            claude.generator(),
            threshold=threshold,
            handoff_store=store,
            kb_version=kb_version,
            clock=lambda: FIXED_TIME,
        )
        recording = RecordingFlow(real_flow)
        app = create_app(flow or recording, access_code=CODE, kb_version=kb_version, image_tag=image_tag)
        return WebBot(TestClient(app, raise_server_exceptions=False), claude, retriever, store, recording)

    return _make


@pytest.fixture
def all_logs(caplog):
    """Every log record from every logger, at every level."""
    caplog.set_level(logging.DEBUG)
    return caplog


@pytest.fixture
def production_logs():
    """The records `python -m web` would write: its logging set-up
    (web.__main__.configure_logging), captured. Restored afterwards."""
    from web import __main__ as web_main

    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    web_logger = logging.getLogger("voltrix.web")
    saved_web_level = web_logger.level

    class Collect(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records: list[logging.LogRecord] = []

        def emit(self, record):
            self.format(record)
            self.records.append(record)

    web_main.configure_logging()
    collect = Collect()
    collect.setFormatter(logging.Formatter(web_main.LOG_FORMAT))
    root.addHandler(collect)
    try:
        yield collect
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
        web_logger.setLevel(saved_web_level)


def request_lines(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "voltrix.web"]


def secrets_in(text: str) -> list[str]:
    """Which fake secrets (or a long part of one) appear in text."""
    found = []
    for secret in (KEY, CODE):
        parts = {secret[i:i + 12] for i in range(len(secret) - 11)}
        if secret in text or any(p in text for p in parts):
            found.append(secret)
    return found


def response_text(response) -> str:
    return json.dumps(dict(response.headers)) + response.text
