"""Stage e: python -m query.ask (spec 02 "Output"; fails loudly while
ESCALATION_THRESHOLD is unset). No model calls: the real command is run
with the threshold unset in the child process only, and everything after
the threshold check is blocked there.
"""

import json
import os
import subprocess
import sys

import pytest

from query import ask, config
from query.config import ConfigError, Settings
from query.flow import QueryFlow
from query.generator import FakeGenerator
from query.handoff import JsonlHandoffStore, missing_fields
from query.response import ESCALATION_MESSAGE

ANSWER = {"decision": "answer", "answer": "Lengthen P-06.", "used_article_ids": ["KB-001"]}

pytestmark = pytest.mark.usefixtures("no_network")


@pytest.fixture
def fake_build(fake_retriever, make_chunk, tmp_path):
    """build() for main(): a flow over fakes with a test threshold."""

    def _make(reply=ANSWER, store=None):
        chunks = [make_chunk("KB-001", n=1, score=0.8, text="E-01 — Lengthen P-06.")]
        flow = QueryFlow(
            fake_retriever(chunks=chunks),
            FakeGenerator(reply),
            threshold=0.5,
            handoff_store=store or JsonlHandoffStore(tmp_path / "h.jsonl"),
            kb_version="v1",
        )
        return lambda: flow

    return _make


# --- The real command, threshold unset --------------------------------------------------

# Runs `python -m query.ask` in a child process whose threshold is None.
# query/config.py is not touched: the threshold is unset in the child's
# memory only. Everything the command must not reach while the threshold
# is unset (settings, API key, index, network) fails there, so the real
# model can never be called, even if the threshold check is broken.
UNSET_THRESHOLD_LAUNCHER = """
import runpy, socket, sys

import ingestion
from query import anthropic_api, config

def must_not_run(*args, **kwargs):
    raise AssertionError("loaded before the threshold check")

config.ESCALATION_THRESHOLD = None
config.load_settings = must_not_run
ingestion.open_retrieval = must_not_run
anthropic_api.AnthropicGenerator.from_environment = must_not_run
socket.socket.connect = must_not_run
socket.create_connection = must_not_run

sys.argv = ["python -m query.ask", *sys.argv[1:]]
runpy.run_module("query.ask", run_name="__main__", alter_sys=True)
"""


def test_real_command_fails_loudly_while_threshold_unset(tmp_path):
    handoffs = tmp_path / "handoffs.jsonl"
    result = subprocess.run(
        [sys.executable, "-c", UNSET_THRESHOLD_LAUNCHER, "E1 when the motor ramps up"],
        cwd=config.REPO_ROOT,
        # The shell's Anthropic variables are left out and HOME points at an
        # empty folder (no secrets file): the result must not depend on them.
        env={
            **{k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "VOLTRIX_"))},
            "HOME": str(tmp_path),
            "HANDOFF_PATH": str(handoffs),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == ask.EXIT_STARTUP_FAILED
    assert result.stdout == ""
    assert result.stderr.startswith("error: ESCALATION_THRESHOLD is NOT YET SET")
    assert "Traceback" not in result.stderr
    assert not handoffs.exists()


def test_threshold_checked_before_anything_is_loaded(monkeypatch):
    def must_not_run(*args, **kwargs):
        raise AssertionError("loaded before the threshold check")

    monkeypatch.setattr(config, "ESCALATION_THRESHOLD", None)
    monkeypatch.setattr(ask, "load_settings", must_not_run)
    monkeypatch.setattr(ask, "open_retrieval", must_not_run)
    monkeypatch.setattr(ask.AnthropicGenerator, "from_environment", must_not_run)
    with pytest.raises(ConfigError, match="NOT YET SET"):
        ask.build_flow()


# --- build_flow wiring (no network, no index) ------------------------------------------


def test_build_flow_wires_config_settings_index_and_anthropic(monkeypatch, tmp_path, fake_retriever):
    settings = Settings("v2", tmp_path / "h.jsonl")  # no AWS settings needed
    opened, generators = [], []
    fake_generator = FakeGenerator(ANSWER)

    def fake_from_environment():
        generators.append("anthropic")
        return fake_generator

    def fake_open(version):
        opened.append(version)
        return fake_retriever(kb_version=version)

    monkeypatch.setattr(config, "ESCALATION_THRESHOLD", 0.42)  # test value only
    monkeypatch.setattr(ask, "load_settings", lambda: settings)
    monkeypatch.setattr(ask, "open_retrieval", fake_open)
    monkeypatch.setattr(ask.AnthropicGenerator, "from_environment", fake_from_environment)

    flow = ask.build_flow()

    assert opened == ["v2"] and generators == ["anthropic"]
    assert flow._threshold == 0.42
    assert flow._generator is fake_generator
    assert flow._handoff_store.path == settings.handoff_path
    assert flow._kb_version == "v2"


def test_api_key_checked_before_index_is_opened(monkeypatch, tmp_path):
    def no_key():
        raise ConfigError("VOLTRIX_ANTHROPIC_API_KEY is not set")

    def must_not_run(*args, **kwargs):
        raise AssertionError("index opened before the key check")

    monkeypatch.setattr(config, "ESCALATION_THRESHOLD", 0.42)  # test value only
    monkeypatch.setattr(ask, "load_settings", lambda: Settings("v1", tmp_path / "h.jsonl"))
    monkeypatch.setattr(ask, "open_retrieval", must_not_run)
    monkeypatch.setattr(ask.AnthropicGenerator, "from_environment", no_key)
    with pytest.raises(ConfigError, match="VOLTRIX_ANTHROPIC_API_KEY"):
        ask.build_flow()


def test_cli_never_imports_bedrock():
    source = open(ask.__file__, encoding="utf-8").read()
    assert "bedrock" not in source.lower() and "botocore" not in source


# --- main() with fakes -------------------------------------------------------------------


def test_answered_response_printed_as_json(fake_build, capsys):
    assert ask.main(["E1", "on", "start"], build=fake_build()) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {
        "status": "answered",
        "answer": "Lengthen P-06.",
        "citations": [{"article_id": "KB-001", "title": "E-01 Overcurrent during acceleration"}],
        "escalation_reason": "",
        "handoff_id": "",
    }


def test_escalated_response_printed_and_handoff_stored(fake_build, tmp_path, capsys):
    store = JsonlHandoffStore(tmp_path / "handoffs" / "h.jsonl")
    reply = {"decision": "out_of_scope", "answer": "", "used_article_ids": []}
    assert ask.main(["how much does a VX-200 cost?"], build=fake_build(reply, store)) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "escalated" and out["escalation_reason"] == "out_of_scope"
    assert out["answer"] == ESCALATION_MESSAGE.format(handoff_id=out["handoff_id"])
    (stored,) = [json.loads(line) for line in store.path.read_text(encoding="utf-8").splitlines()]
    assert stored["handoff_id"] == out["handoff_id"]
    assert missing_fields(stored) == []


@pytest.mark.parametrize(
    "error",
    [
        ConfigError("VOLTRIX_ANTHROPIC_API_KEY is not set"),
        ConfigError("ANTHROPIC_BASE_URL must not be set in the bot's environment"),
        ask.RetrievalError("indexes/v3: index folder does not exist"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_startup_errors_exit_2_with_message(capsys, error):
    def build():
        raise error

    assert ask.main(["q"], build=build) == ask.EXIT_STARTUP_FAILED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"error: {error}\n"


def test_empty_question_rejected_before_build(capsys):
    def build():
        raise AssertionError("built for an empty question")

    with pytest.raises(SystemExit) as exit_info:
        ask.main(["   "], build=build)
    assert exit_info.value.code == 2
    assert "the question is empty" in capsys.readouterr().err


def test_no_question_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as exit_info:
        ask.main([])
    assert exit_info.value.code == 2
