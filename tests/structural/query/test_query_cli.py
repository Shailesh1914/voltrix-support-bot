"""Stage e: python -m query.ask (spec 02 "Output"; fails loudly while
ESCALATION_THRESHOLD is unset). No model calls: the real command is run
only while the threshold is unset, when it stops before loading anything.
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


@pytest.mark.skipif(config.ESCALATION_THRESHOLD is not None, reason="would run the real bot")
def test_real_command_fails_loudly_while_threshold_unset(tmp_path):
    handoffs = tmp_path / "handoffs.jsonl"
    result = subprocess.run(
        [sys.executable, "-m", "query.ask", "E1 when the motor ramps up"],
        cwd=config.REPO_ROOT,
        env={**os.environ, "HANDOFF_PATH": str(handoffs)},
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
    monkeypatch.setattr(ask.BedrockGenerator, "from_settings", must_not_run)
    with pytest.raises(ConfigError, match="NOT YET SET"):
        ask.build_flow()


# --- build_flow wiring (no network, no index) ------------------------------------------


def test_build_flow_wires_config_settings_index_and_bedrock(monkeypatch, tmp_path, fake_retriever):
    settings = Settings("my-profile", "ap-south-1", "v2", tmp_path / "h.jsonl")
    opened, generators = [], []
    fake_generator = FakeGenerator(ANSWER)

    def fake_from_settings(s):
        generators.append(s)
        return fake_generator

    def fake_open(version):
        opened.append(version)
        return fake_retriever(kb_version=version)

    monkeypatch.setattr(config, "ESCALATION_THRESHOLD", 0.42)  # test value only
    monkeypatch.setattr(ask, "load_settings", lambda: settings)
    monkeypatch.setattr(ask, "open_retrieval", fake_open)
    monkeypatch.setattr(ask.BedrockGenerator, "from_settings", fake_from_settings)

    flow = ask.build_flow()

    assert opened == ["v2"] and generators == [settings]
    assert flow._threshold == 0.42
    assert flow._generator is fake_generator
    assert flow._handoff_store.path == settings.handoff_path
    assert flow._kb_version == "v2"


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
        ConfigError("AWS_PROFILE is not set (add it to .env)"),
        ask.RetrievalError("indexes/v3: index folder does not exist"),
        ask.ProfileNotFound(profile="nope"),
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
