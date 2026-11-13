"""POST /ask (spec 08 section 4.2). Expected values come from spec 08."""

import hmac
import json
import uuid
from dataclasses import asdict

import httpx2
import pytest

from query.response import ESCALATION_MESSAGE
from web import app as web_app
from web_testkit import (
    ANSWER_REPLY,
    ANSWER_TEXT,
    CODE,
    OUT_OF_SCOPE_REPLY,
    QUESTION,
    error_reply,
    make_chunk,
)

# Spec 02 "Output", which spec 08 section 4.2 names as the success fields.
SPEC_02_OUTPUT_FIELDS = ("status", "answer", "citations", "escalation_reason", "handoff_id")


def assert_nothing_ran(bot):
    assert bot.claude.calls == 0, "Claude was called"
    assert bot.retriever.retrieval_calls() == 0, "retrieval ran"
    assert bot.flow.results == [], "the flow ran"
    assert bot.store.records == [], "a handoff was written"


# --- 401: before anything else ---------------------------------------------------------

WRONG_CODES = [
    "",
    "wrong-code-wrong-code",
    CODE[:-1],
    CODE + "x",
    CODE.upper(),
    " " + CODE,
    CODE + " ",
]


def test_missing_code_401(make_bot, spec_08):
    bot = make_bot()
    response = bot.ask(code=None)
    assert response.status_code == 401
    assert response.json() == {"error": spec_08.access_denied}
    assert_nothing_ran(bot)


@pytest.mark.parametrize("code", WRONG_CODES, ids=["empty", "other", "short", "long", "case", "lead space", "trail space"])
def test_wrong_code_401(make_bot, spec_08, code):
    bot = make_bot()
    response = bot.ask(code=code)
    assert response.status_code == 401
    assert response.json() == {"error": spec_08.access_denied}
    assert_nothing_ran(bot)


@pytest.mark.parametrize("raw", [b"{not json", b"[]", b'{"question": 5}', b""], ids=["bad json", "list", "number", "empty"])
def test_bad_code_with_bad_body_gives_401(make_bot, spec_08, raw):
    bot = make_bot()
    response = bot.ask(raw=raw, code="wrong-code-wrong-code")
    assert response.status_code == 401
    assert response.json() == {"error": spec_08.access_denied}
    assert_nothing_ran(bot)


def test_code_checked_before_body_is_read(make_bot, monkeypatch):
    bot = make_bot()

    def must_not_parse(body):
        raise AssertionError("body read before the access code check")

    monkeypatch.setattr(web_app, "parse_question", must_not_parse)
    assert bot.ask(code="wrong-code-wrong-code").status_code == 401


def test_code_compared_in_constant_time(make_bot, monkeypatch):
    calls = []
    real = hmac.compare_digest

    def spy(a, b):
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(web_app.hmac, "compare_digest", spy)
    bot = make_bot()
    assert bot.ask(code="wrong-code-wrong-code").status_code == 401
    assert bot.ask().status_code == 200
    assert len(calls) == 2


# --- 400: exact texts of spec 08 ---------------------------------------------------------

# Case name in the spec 08 table -> a body that is that case.
BAD_BODIES = {
    "Body is not valid JSON, or not a JSON object": [
        b"{not json",
        b"",
        b"\xff\xfe",
        b"[]",
        b'["question"]',
        b'"a question"',
        b"null",
        b"42",
    ],
    "`question` missing": [b"{}", b'{"Question": "x"}', b'{"text": "x"}'],
    "`question` is not a string": [b'{"question": 5}', b'{"question": null}', b'{"question": ["x"]}', b'{"question": {}}', b'{"question": true}'],
    "`question` empty after trimming spaces": [b'{"question": ""}', b'{"question": "   "}', b'{"question": " \\t\\n "}'],
}


def test_spec_lists_these_400_cases(spec_08):
    assert set(spec_08.bad_request_texts) == {*BAD_BODIES, "`question` longer than 1000 characters (counted as sent, before trimming)"}


@pytest.mark.parametrize(
    "case, raw",
    [(case, raw) for case, bodies in BAD_BODIES.items() for raw in bodies],
    ids=lambda v: v if isinstance(v, str) else repr(v)[:30],
)
def test_400_cases_with_exact_text(make_bot, spec_08, case, raw):
    bot = make_bot()
    response = bot.ask(raw=raw)
    assert response.status_code == 400
    assert response.json() == {"error": spec_08.bad_request_texts[case]}
    assert_nothing_ran(bot)


def too_long_case(spec_08):
    (case,) = [c for c in spec_08.bad_request_texts if "longer than" in c]
    return case


def test_question_over_the_limit_is_400(make_bot, spec_08):
    bot = make_bot()
    response = bot.ask({"question": "a" * (spec_08.max_question_chars + 1)})
    assert response.status_code == 400
    assert response.json() == {"error": spec_08.bad_request_texts[too_long_case(spec_08)]}
    assert_nothing_ran(bot)


def test_question_at_the_limit_is_accepted(make_bot, spec_08):
    bot = make_bot()
    question = QUESTION + " " + "a" * (spec_08.max_question_chars - len(QUESTION) - 1)
    assert len(question) == spec_08.max_question_chars
    assert bot.ask({"question": question}).status_code == 200


def test_limit_counted_as_sent_before_trimming(make_bot, spec_08):
    # Short text plus spaces: over the limit as sent, under it after trimming.
    bot = make_bot()
    question = QUESTION + " " * (spec_08.max_question_chars + 1 - len(QUESTION))
    assert len(question) == spec_08.max_question_chars + 1
    response = bot.ask({"question": question})
    assert response.status_code == 400
    assert response.json() == {"error": spec_08.bad_request_texts[too_long_case(spec_08)]}


def test_checks_run_in_table_order_blank_beats_too_long(make_bot, spec_08):
    # Spec 08 v1.2: only spaces and over the limit -> the "empty" error, the
    # earlier row of the table, not the "longer than" error.
    bot = make_bot()
    question = " " * (spec_08.max_question_chars + 1)
    response = bot.ask({"question": question})
    assert response.status_code == 400
    assert response.json() == {"error": spec_08.blank_and_too_long_error}
    assert spec_08.blank_and_too_long_error == spec_08.bad_request_texts["`question` empty after trimming spaces"]
    assert_nothing_ran(bot)


def test_limit_counts_characters_not_bytes(make_bot, spec_08):
    # 1000 characters of 2-3 bytes each in UTF-8 are still 1000 characters.
    bot = make_bot()
    question = "E1 " + "Ω" * (spec_08.max_question_chars - 3)
    assert len(question) == spec_08.max_question_chars
    assert bot.ask({"question": question}).status_code == 200


def test_extra_fields_are_ignored(make_bot):
    bot = make_bot()
    response = bot.ask({"question": QUESTION, "threshold": 0.0, "debug": True})
    assert response.status_code == 200
    assert response.json() == asdict(bot.flow.results[0])


# --- 200: the flow's result, unchanged ------------------------------------------------------


def test_answer_returns_the_flow_result_unchanged(make_bot, spec_08):
    bot = make_bot(ANSWER_REPLY)
    response = bot.ask()
    assert response.status_code == 200
    (result,) = bot.flow.results
    assert response.json() == asdict(result)
    assert tuple(response.json()) == spec_08.success_fields == SPEC_02_OUTPUT_FIELDS
    assert response.json()["status"] == "answered"
    assert response.json()["answer"] == ANSWER_TEXT
    assert response.json()["citations"] == [{"article_id": "KB-001", "title": "E-01 Overcurrent during acceleration"}]
    assert bot.claude.calls == 1


def test_question_reaches_the_flow_unchanged(make_bot):
    # The flow masks and normalises; the web layer passes exactly what was sent.
    bot = make_bot()
    asked = []
    real_ask = bot.flow.ask
    bot.flow.ask = lambda q: asked.append(q) or real_ask(q)
    question = "  E1 when the motor ramps up\n(second line)  "
    assert bot.ask({"question": question}).status_code == 200
    assert asked == [question]


def test_escalation_returns_the_flow_result_unchanged(make_bot, spec_08):
    bot = make_bot(OUT_OF_SCOPE_REPLY)
    response = bot.ask({"question": "how much does a VX-200 cost?"})
    assert response.status_code == 200
    (result,) = bot.flow.results
    body = response.json()
    assert body == asdict(result)
    assert tuple(body) == spec_08.success_fields
    assert body["status"] == "escalated" and body["escalation_reason"] == "out_of_scope"
    assert body["answer"] == ESCALATION_MESSAGE.format(handoff_id=body["handoff_id"])
    (record,) = bot.store.records
    assert record.handoff_id == body["handoff_id"]


def test_low_similarity_escalates_without_claude(make_bot):
    bot = make_bot(chunks=[make_chunk(score=0.1)])
    body = bot.ask().json()
    assert body["status"] == "escalated" and body["escalation_reason"] == "low_similarity"
    assert bot.claude.calls == 0


# --- Service error: a 200 escalation (spec 02 decision 6) -----------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        error_reply(529, "overloaded_error"),
        error_reply(500, "api_error"),
        error_reply(429, "rate_limit_error"),
        httpx2.ConnectError("connection refused"),
    ],
    ids=["529", "500", "429", "connect"],
)
def test_service_error_is_a_200_escalation(make_bot, spec_08, reply):
    bot = make_bot(reply)
    response = bot.ask()
    assert response.status_code == 200
    body = response.json()
    assert tuple(body) == spec_08.success_fields
    assert body["status"] == "escalated"
    assert body["escalation_reason"] == "service_error"
    assert body["handoff_id"] and body["answer"] == ESCALATION_MESSAGE.format(handoff_id=body["handoff_id"])
    assert body == asdict(bot.flow.results[0])
    # The SDK's retries ran (3 attempts in total, spec 02); the web layer added none.
    assert bot.claude.calls == 3


def test_client_error_is_a_200_escalation_without_retry(make_bot):
    bot = make_bot(error_reply(401, "authentication_error"))
    body = bot.ask().json()
    assert body["escalation_reason"] == "service_error"
    assert bot.claude.calls == 1


# --- 500: anything unexpected ----------------------------------------------------------------


class BrokenStore:
    def append(self, record):
        raise OSError("disk full at /secret/path SENTINELQUESTION")


class BrokenFlow:
    def ask(self, question):
        raise RuntimeError(f"unexpected: {question}")


@pytest.mark.parametrize("broken", ["store", "flow"])
def test_unexpected_error_is_500_without_details(make_bot, spec_08, broken):
    if broken == "store":
        bot = make_bot(OUT_OF_SCOPE_REPLY, store=BrokenStore())
    else:
        bot = make_bot(flow=BrokenFlow())
    response = bot.ask()
    assert response.status_code == 500
    assert response.json() == {"error": spec_08.internal_error}
    assert "Traceback" not in response.text and "SENTINELQUESTION" not in response.text


# --- X-Request-Id --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"code": None}, {"raw": b"{"}, {"flow_broken": True}],
    ids=["200", "401", "400", "500"],
)
def test_every_ask_response_has_a_request_id(make_bot, kwargs):
    bot = make_bot(flow=BrokenFlow()) if kwargs.pop("flow_broken", False) else make_bot()
    response = bot.ask(**kwargs)
    request_id = response.headers["X-Request-Id"]
    assert uuid.UUID(request_id).version == 4


def test_request_ids_differ(make_bot):
    bot = make_bot()
    ids = {bot.ask().headers["X-Request-Id"] for _ in range(3)}
    assert len(ids) == 3


# --- Only the spec 08 endpoints exist ----------------------------------------------------------


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_no_framework_pages(make_bot, path):
    assert make_bot().client.get(path).status_code == 404


class RecordingProvider:
    """Stands in for a globally configured OpenTelemetry provider (as a
    Lambda OTel layer would set). Any use by FastAPI is recorded."""

    def __init__(self, kind, used):
        self.kind, self.used = kind, used

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.used.append(f"{self.kind}.{name}")
            raise AssertionError("telemetry used")

        return record


def test_fastapi_telemetry_is_off(make_bot, monkeypatch):
    # Spec 08 v1.2 section 4.3: FastAPI's telemetry is switched off. With
    # providers that look configured, FastAPI would trace, meter and log
    # every request unless the app turns that off.
    import fastapi.telemetry._asgi as native

    used: list[str] = []
    monkeypatch.setattr(native, "_unconfigured", lambda provider: False)
    monkeypatch.setattr(native.trace, "get_tracer_provider", lambda: RecordingProvider("trace", used))
    monkeypatch.setattr(native.metrics, "get_meter_provider", lambda: RecordingProvider("metrics", used))
    monkeypatch.setattr(native._logs, "get_logger_provider", lambda: RecordingProvider("logs", used))
    bot = make_bot()
    statuses = [bot.client.get("/health").status_code, bot.ask().status_code]
    assert used == []
    assert statuses == [200, 200]


def test_get_ask_is_not_allowed(make_bot):
    bot = make_bot()
    assert bot.client.get("/ask", headers={"X-Access-Code": CODE}).status_code == 405
    assert_nothing_ran(bot)

