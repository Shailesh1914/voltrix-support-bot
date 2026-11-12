"""Logging (spec 08 section 4.4) and no secret anywhere (section 4.6)."""

import logging
import re

import pytest

from web import __main__ as web_main
from web_testkit import (
    ANSWER_TEXT,
    CODE,
    KEY,
    OUT_OF_SCOPE_REPLY,
    QUESTION,
    error_reply,
    request_lines,
    response_text,
    secrets_in,
)

LINE = re.compile(r"request_id=(\S+) decision=(\S+) latency_ms=([0-9]+) status=([0-9]{3})")


def one_line(caplog):
    (record,) = request_lines(caplog)
    match = LINE.fullmatch(record.getMessage())
    assert match, record.getMessage()
    return match.groups()


@pytest.mark.parametrize(
    "case, expected_status, expected_decision",
    [
        ("answer", 200, "answered"),
        ("escalate", 200, "escalated"),
        ("service_error", 200, "escalated"),
        ("401", 401, "-"),
        ("400", 400, "-"),
        ("500", 500, "-"),
    ],
)
def test_one_request_line_per_ask(make_bot, all_logs, case, expected_status, expected_decision):
    class BrokenFlow:
        def ask(self, question):
            raise RuntimeError(question)

    replies = {"escalate": [OUT_OF_SCOPE_REPLY], "service_error": [error_reply(529, "overloaded_error")]}
    bot = make_bot(*replies.get(case, []), flow=BrokenFlow() if case == "500" else None)
    kwargs = {"401": {"code": None}, "400": {"raw": b"{"}}.get(case, {})
    response = bot.ask(**kwargs)
    assert response.status_code == expected_status
    request_id, decision, latency_ms, status = one_line(all_logs)
    assert request_id == response.headers["X-Request-Id"]
    assert decision == expected_decision
    assert int(status) == expected_status
    assert int(latency_ms) >= 0


def test_health_and_page_write_no_request_line(make_bot, all_logs):
    bot = make_bot()
    bot.client.get("/health")
    bot.client.get("/")
    assert request_lines(all_logs) == []


def test_only_the_allowed_anthropic_warning_is_added(make_bot, all_logs):
    bot = make_bot(error_reply(529, "overloaded_error"))
    bot.ask()
    others = [r for r in all_logs.records if r.name != "voltrix.web" and r.levelno >= logging.WARNING]
    assert [r.name for r in others] == ["query.anthropic_api"]
    assert others[0].getMessage() == "Anthropic API call failed: OverloadedError (HTTP 529)"


CASES = ["answer", "escalate", "service_error", "401", "400", "500"]


def run_case(make_bot, case):
    class BrokenFlow:
        def ask(self, question):
            raise RuntimeError(f"{question} {KEY} {CODE}")

    replies = {"escalate": [OUT_OF_SCOPE_REPLY], "service_error": [error_reply(529, "overloaded_error")]}
    bot = make_bot(*replies.get(case, []), flow=BrokenFlow() if case == "500" else None)
    code = {"401": "wrong-code-but-close-" + CODE[-6:]}.get(case, CODE)
    raw = {"400": b'{"question": "' + QUESTION.encode() + b'", '}.get(case)
    return bot.ask(code=code, raw=raw)


@pytest.mark.parametrize("case", CASES)
def test_no_question_answer_or_secret_in_any_response_or_log(make_bot, production_logs, case):
    response = run_case(make_bot, case)
    written = "\n".join(
        production_logs.format(r) + " " + str(r.args) + " " + (r.exc_text or "") for r in production_logs.records
    )
    assert secrets_in(written) == []
    assert "SENTINELQUESTION" not in written and "SENTINELANSWER" not in written
    assert secrets_in(response_text(response)) == []
    if case != "answer":
        assert ANSWER_TEXT not in response.text


@pytest.mark.parametrize("case", CASES)
def test_written_lines_per_ask(make_bot, production_logs, case):
    """Under the real logging set-up, an /ask writes exactly one line, plus
    the allowed Anthropic warning on a service error."""
    run_case(make_bot, case)
    names = [r.name for r in production_logs.records]
    if case == "service_error":
        assert names == ["query.anthropic_api", "voltrix.web"]
    else:
        assert names == ["voltrix.web"]


def test_sdk_debug_lines_would_hold_the_question(make_bot, all_logs):
    """Why the levels matter: at DEBUG the SDK logs the whole request.
    python -m web never enables DEBUG (test above)."""
    run_case(make_bot, "service_error")
    sdk_text = "\n".join(r.getMessage() for r in all_logs.records if r.name.startswith("anthropic"))
    assert "SENTINELQUESTION" in sdk_text


def test_no_secret_in_any_endpoint_response(make_bot):
    bot = make_bot()
    for response in (bot.client.get("/"), bot.client.get("/health"), bot.ask(), bot.ask(code=None)):
        assert secrets_in(response_text(response)) == []


# --- python -m web: logging set-up -----------------------------------------------------------


def test_uvicorn_access_log_off_and_port_8080(production_logs):
    runs = []
    sentinel_app = object()
    assert web_main.main(build=lambda: sentinel_app, run=lambda app, **kw: runs.append((app, kw))) == 0
    ((app, kwargs),) = runs
    assert app is sentinel_app
    assert kwargs["access_log"] is False
    assert kwargs["port"] == 8080 and kwargs["host"] == "0.0.0.0"
    assert kwargs["log_config"] is None


def test_log_levels_keep_library_info_lines_out(production_logs):
    assert logging.getLogger().level == logging.WARNING
    assert logging.getLogger("voltrix.web").getEffectiveLevel() == logging.INFO
    for library in ("httpx", "httpx2", "anthropic", "anthropic._base_client", "uvicorn", "uvicorn.access", "fastapi"):
        assert not logging.getLogger(library).isEnabledFor(logging.INFO), library
    assert logging.getLogger("query.anthropic_api").isEnabledFor(logging.WARNING)
