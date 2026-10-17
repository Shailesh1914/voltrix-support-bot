"""Part B (spec 05): the real flow with a FAKE Anthropic client.

No network and no key: the client is scripted; AnthropicGenerator,
QueryFlow and every check in query/ are the real ones.
"""

import ast
import hashlib
import json
import re
import subprocess
from types import SimpleNamespace

import anthropic
import pytest

import ingestion
import query.anthropic_api
import query.config
import query.handoff
from evals import eval_part_b as pb
from evals import run_eval
from evals.eval_recorders import EvalError
from evals.eval_sweep import load_run
from query.anthropic_api import AnthropicGenerator
from query.config import ConfigError, require_threshold
from query.generator import GeneratorOutput
from query.handoff import missing_fields
from query.prompt import TOOL_NAME

# --- Fakes -------------------------------------------------------------------------


def message(decision="answer", answer="Check the motor wiring.", used=("KB-001",), tokens=(1200, 150),
            stop_reason="tool_use"):
    block = SimpleNamespace(
        type="tool_use", name=TOOL_NAME,
        input={"decision": decision, "answer": answer if decision == "answer" else "",
               "used_article_ids": list(used) if decision == "answer" else []},
    )
    return SimpleNamespace(stop_reason=stop_reason, content=[block],
                           usage=SimpleNamespace(input_tokens=tokens[0], output_tokens=tokens[1]))


def question_of(request) -> str:
    return re.search(r"<question>\n(.*)\n</question>", request["messages"][0]["content"], re.S).group(1)


class FakeClient:
    """messages.create() answers from script(question) -> message or exception."""

    def __init__(self, script):
        self.requests = []
        self.messages = self
        self._script = script

    def create(self, **request):
        self.requests.append(request)
        result = self._script(question_of(request))
        if isinstance(result, BaseException):
            raise result
        return result


def by_question(**replies):
    """Script: the first reply whose key word is in the question, else a plain answer."""

    def script(question):
        for word, reply in replies.items():
            if word in question:
                return reply() if callable(reply) else reply
        return message()

    return script


def service_error():
    return anthropic.AnthropicError("overloaded")


# T-001 answer, T-002 answer (two articles), T-003 escalate with the unknown
# code E-21 (no model call), T-004 escalate (the model says out_of_scope).
@pytest.fixture
def tickets(make_ticket):
    return [
        make_ticket("T-001", ids=("KB-001",), question="drive shows e1 when ramping"),
        make_ticket("T-002", ids=("KB-019", "KB-022"), category="installation", question="motor runs backwards"),
        make_ticket("T-003", expected="escalate", question="display shows E-21, what is it"),
        make_ticket("T-004", expected="escalate", category="scope", question="what is the price of a spare fan"),
    ]


DEFAULT_SCRIPT = dict(
    backwards=lambda: message(used=("KB-019", "KB-022"), answer="Swap two motor phases."),
    price=lambda: message(decision="out_of_scope"),
)


def run_with(tickets, fake_retriever, script=None, max_calls=pb.MAX_MODEL_CALLS):
    client = FakeClient(script or by_question(**DEFAULT_SCRIPT))
    generator = pb.UsageRecordingGenerator(AnthropicGenerator(client), max_calls=max_calls)
    outcome = run_eval.part_b(tickets, fake_retriever(), generator)
    return outcome, client, generator


def rows_of(outcome):
    return {r["ticket_id"]: r for r in outcome.rows}


# --- Recording -----------------------------------------------------------------------


def test_part_b_records_everything_spec_05_lists(tickets, fake_retriever):
    outcome, client, generator = run_with(tickets, fake_retriever)
    rows = rows_of(outcome)
    assert outcome.stopped is None and generator.calls == len(client.requests) == 3

    t1 = rows["T-001"]
    assert t1["top_score"] == 0.80
    assert t1["status"] == "answered" and t1["escalation_reason"] == "" and t1["handoff_id"] == ""
    assert t1["citations"] == [{"article_id": "KB-001", "title": "E-01 Overcurrent during acceleration"}]
    assert t1["failed_check"] == "" and t1["rejected_answer"] == ""
    assert t1["answer"] == "Check the motor wiring."
    assert (t1["input_tokens"], t1["output_tokens"]) == (1200, 150)
    assert t1["model_called"] is True and t1["malformed_output"] is False
    assert t1["model_output"] == {"decision": "answer", "answer": "Check the motor wiring.", "used_article_ids": ["KB-001"]}
    assert "E-01" in t1["question_sent"]  # the flow's normalised question
    assert [c["article_id"] for c in t1["retrieved_chunks"]] == ["KB-001", "KB-020"]
    assert t1["ac_pass"] is True

    assert rows["T-002"]["ac_pass"] is False  # stopped by the citation check (next test)
    t3 = rows["T-003"]
    assert t3["model_called"] is False and t3["model_output"] is None
    assert (t3["input_tokens"], t3["output_tokens"]) == (None, None)
    assert t3["status"] == "escalated" and t3["escalation_reason"] == "insufficient_context"
    assert t3["top_score"] == 0.80 and t3["handoff_id"]
    t4 = rows["T-004"]
    assert t4["escalation_reason"] == "out_of_scope" and t4["ac_pass"] is True
    assert t4["answer"].startswith("I can't answer this reliably.") and t4["handoff_id"] in t4["answer"]


def test_part_b_citation_check_is_recorded(tickets, fake_retriever):
    # T-002 cites KB-022, which was never retrieved: the flow's citation
    # check stops it, and the draft is kept for the human.
    outcome, _, _ = run_with(tickets, fake_retriever)
    t2 = rows_of(outcome)["T-002"]
    assert t2["status"] == "escalated" and t2["failed_check"] == "citation"
    assert t2["rejected_answer"] == "Swap two motor phases."
    assert t2["citations"] == []


def test_part_b_grounding_failure_is_recorded(tickets, fake_retriever):
    script = by_question(ramping=lambda: message(answer="Wait 99 minutes, then restart."), **DEFAULT_SCRIPT)
    outcome, _, _ = run_with(tickets, fake_retriever, script)
    t1 = rows_of(outcome)["T-001"]
    assert t1["status"] == "escalated" and t1["failed_check"] == "grounding"
    assert t1["rejected_answer"] == "Wait 99 minutes, then restart."
    assert t1["input_tokens"] == 1200  # the call returned, so its usage is known
    assert t1["ac_pass"] is False


def test_part_b_malformed_output_has_no_tokens_and_is_counted(tickets, fake_retriever):
    script = by_question(ramping=lambda: message(stop_reason="max_tokens"), **DEFAULT_SCRIPT)
    outcome, _, _ = run_with(tickets, fake_retriever, script)
    t1 = rows_of(outcome)["T-001"]
    assert t1["malformed_output"] is True and t1["model_output"] is None
    assert (t1["input_tokens"], t1["output_tokens"]) == (None, None)
    assert t1["escalation_reason"] == "insufficient_context"
    data = pb.run_data(tickets, outcome, 1)
    assert data["malformed_outputs"] == 1 and data["tokens"]["calls_without_usage"] == 1
    assert data["valid"] is True  # malformed output is an escalation, not a service error
    assert "slightly underestimated" in data["cost_note"] and "still billed" in data["cost_note"]


def test_handoff_check_follows_spec_02(tickets, fake_retriever):
    outcome, _, _ = run_with(tickets, fake_retriever)
    record = outcome.handoffs[0]
    assert pb.handoff_missing_fields(record) == missing_fields(record) == []
    broken = {k: v for k, v in record.items() if k != "failed_check"}
    broken["retrieved_chunks"] = [{k: v for k, v in record["retrieved_chunks"][0].items() if k != "text"}]
    assert pb.handoff_missing_fields(broken) == ["failed_check", "retrieved_chunks[0].text"]
    assert set(pb.HANDOFF_FIELDS) == set(query.handoff.HANDOFF_FIELDS)


def test_incomplete_handoff_makes_the_run_invalid(tickets, fake_retriever):
    outcome, _, _ = run_with(tickets, fake_retriever)
    del outcome.handoffs[0]["kb_version"]
    data = pb.run_data(tickets, outcome, 1)
    assert data["valid"] is False and data["incomplete_handoff_records"] == [outcome.handoffs[0]["handoff_id"]]


def test_part_b_handoffs_stay_in_memory_and_are_complete(tickets, fake_retriever):
    outcome, _, _ = run_with(tickets, fake_retriever)
    escalated = [r["handoff_id"] for r in outcome.rows if r["status"] == "escalated"]
    assert [h["handoff_id"] for h in outcome.handoffs] == escalated
    assert all(pb.handoff_missing_fields(h) == [] for h in outcome.handoffs)
    t2 = next(h for h in outcome.handoffs if h["failed_check"])
    assert t2["rejected_answer"] == "Swap two motor phases."


def test_part_b_threshold_minus_one_reaches_the_model(make_ticket, fake_retriever):
    client = FakeClient(by_question())
    generator = pb.UsageRecordingGenerator(AnthropicGenerator(client))
    outcome = run_eval.part_b([make_ticket("T-001")], fake_retriever(lambda q: [("KB-001", -0.5)]), generator)
    assert outcome.rows[0]["model_called"] is True and outcome.rows[0]["status"] == "answered"


# --- service_error, call limit, aborts --------------------------------------------------


def test_part_b_stops_at_the_first_service_error(tickets, fake_retriever):
    outcome, client, _ = run_with(tickets, fake_retriever, by_question(**{**DEFAULT_SCRIPT, "backwards": service_error}))
    assert outcome.stopped == {"reason": "service_error", "ticket_id": "T-002"}
    assert [r["ticket_id"] for r in outcome.rows] == ["T-001", "T-002"]
    assert len(client.requests) == 2  # T-004 was never sent
    data = pb.run_data(tickets, outcome, 1)
    assert data["valid"] is False and data["summary"] is None
    assert data["tickets_run"] == 2


def test_call_limit_allows_exactly_the_limit(make_chunk):
    class Inner:
        def generate_with_usage(self, question, chunks):
            return GeneratorOutput("insufficient_context", "", ()), SimpleNamespace(input_tokens=1, output_tokens=1)

    generator = pb.UsageRecordingGenerator(Inner())
    assert generator.max_calls == pb.MAX_MODEL_CALLS == 100
    for _ in range(100):
        generator.generate("q", [make_chunk("KB-001#c1", 0.8)])
    with pytest.raises(pb.CallLimitExceeded, match="limit is 100"):
        generator.generate("q", [])
    assert generator.calls == 100


def test_call_limit_stops_a_run_and_keeps_what_was_paid(tickets, fake_retriever):
    outcome, client, _ = run_with(tickets, fake_retriever, max_calls=1)
    assert len(client.requests) == 1
    assert outcome.stopped["reason"].startswith("aborted: CallLimitExceeded")
    assert outcome.stopped["ticket_id"] == "T-002"
    assert pb.run_data(tickets, outcome, 1)["valid"] is False


def test_failure_before_any_paid_call_is_raised(tickets, fake_retriever):
    with pytest.raises(EvalError, match="no chunks"):
        run_with(tickets, lambda: fake_retriever(lambda q: []))


def test_interrupt_after_a_paid_call_keeps_the_run(tickets, fake_retriever):
    outcome, _, _ = run_with(tickets, fake_retriever, by_question(**{**DEFAULT_SCRIPT, "backwards": KeyboardInterrupt()}))
    assert outcome.stopped["reason"].startswith("aborted: KeyboardInterrupt")
    assert [r["ticket_id"] for r in outcome.rows] == ["T-001"]


# --- Plan and cost --------------------------------------------------------------------


def test_cost_formula():
    assert pb.cost_usd(1_000_000, 0) == pytest.approx(1.00)
    assert pb.cost_usd(0, 1_000_000) == pytest.approx(5.00)


def test_request_settings_come_from_the_generator():
    settings = pb.request_settings(AnthropicGenerator(client=None))
    assert settings["model_id"] == "claude-haiku-4-5-20251001"
    assert settings["temperature"] == 0
    assert settings["max_output_tokens"] == query.config.MAX_OUTPUT_TOKENS
    assert settings["system_prompt_sha256"] == hashlib.sha256(query.anthropic_api.SYSTEM_PROMPT.encode()).hexdigest()


def test_plan_counts_calls_and_estimates_cost(tickets, fake_retriever):
    plan = run_eval.part_b_plan(tickets, fake_retriever())
    assert plan["tickets"] == 4 and plan["planned_model_calls"] == 3  # T-003 stops before the model
    assert plan["within_limit"] is True
    assert plan["estimated_input_tokens"] > 3 * pb.ESTIMATE_TOOL_OVERHEAD_TOKENS
    assert plan["worst_case_output_tokens"] == 3 * query.config.MAX_OUTPUT_TOKENS
    assert plan["estimated_cost_usd"] == pytest.approx(
        pb.cost_usd(plan["estimated_input_tokens"], plan["estimated_output_tokens"]))
    assert plan["worst_case_cost_usd"] > plan["estimated_cost_usd"]


# --- The command ----------------------------------------------------------------------


@pytest.fixture
def command(tmp_path, monkeypatch, tickets, fake_retriever):
    """run_eval.main() for part-b with a fake index, a fake client, a clean
    git tree and a temporary handoffs/ folder. Returns a helper."""
    ticket_file = tmp_path / "tickets.jsonl"
    ticket_file.write_text("".join(
        json.dumps({"ticket_id": t.ticket_id, "question": t.question, "expected": t.expected,
                    "expected_article_ids": list(t.expected_article_ids), "category": t.category}) + "\n"
        for t in tickets), encoding="utf-8")
    reports = tmp_path / "reports"
    state = SimpleNamespace(script=by_question(**DEFAULT_SCRIPT), generators=0, changes=[], clients=[],
                            reports=reports, handoffs=tmp_path / "handoffs")

    def make_real_generator():
        state.generators += 1
        client = FakeClient(lambda q: state.script(q))
        state.clients.append(client)
        return AnthropicGenerator(client)

    def refuse(*args, **kwargs):
        raise AssertionError("the bot's file handoff store must never be used by the evaluation")

    monkeypatch.setattr(ingestion, "open_retrieval", lambda kb_version: fake_retriever(kb_version=kb_version))
    monkeypatch.setattr(run_eval, "make_real_generator", make_real_generator)
    monkeypatch.setattr(run_eval, "HANDOFFS_DIR", state.handoffs)
    monkeypatch.setattr(pb, "uncommitted_code_changes", lambda: list(state.changes))
    monkeypatch.setattr(query.handoff, "JsonlHandoffStore", refuse)

    def run(*extra, run_number=1):
        argv = ["part-b", "--run", str(run_number), "--date", "2026-10-18",
                "--reports-dir", str(reports), "--tickets", str(ticket_file), *extra]
        return run_eval.main(argv)

    state.run = run
    state.files = lambda: sorted(p.name for p in reports.iterdir()) if reports.exists() else []
    return state


def test_dry_run_loads_no_key_and_writes_nothing(command, monkeypatch, capsys):
    def no_key(*args, **kwargs):
        raise AssertionError("the dry run must not load the key")

    monkeypatch.setattr(query.anthropic_api, "load_api_key", no_key)
    monkeypatch.setattr(AnthropicGenerator, "from_environment", no_key)
    assert command.run() == 0
    out = capsys.readouterr().out
    assert "planned model calls:  3 (limit 100 per run)" in out
    assert "cost (est.):" in out and "--run 1 --confirm" in out
    assert command.generators == 0 and command.files() == []


def test_dry_run_refuses_more_than_the_limit(command, monkeypatch, capsys):
    monkeypatch.setattr(pb, "MAX_MODEL_CALLS", 2)
    assert command.run() == 1
    assert "exceed the limit of 2" in capsys.readouterr().err
    assert command.generators == 0 and command.files() == []


def test_confirmed_run_writes_run_files_only_to_reports(command, capsys):
    assert command.run("--confirm") == 0
    assert command.files() == [
        "2026-10-18-part-b-run1-handoffs.jsonl",
        "2026-10-18-part-b-run1.json",
        "2026-10-18-part-b-run1.md",
    ]
    assert not command.handoffs.exists()
    data = json.loads((command.reports / "2026-10-18-part-b-run1.json").read_text(encoding="utf-8"))
    assert (data["kind"], data["run"], data["threshold"], data["valid"]) == ("part-b", 1, -1.0, True)
    assert data["model_id"] == "claude-haiku-4-5-20251001" and data["temperature"] == 0
    assert data["model_calls"] == 3 and data["tokens"] == {"input": 3600, "output": 450, "calls_without_usage": 0}
    assert data["cost_usd"] == pytest.approx(pb.cost_usd(3600, 450))
    assert data["plan"]["planned_model_calls"] == 3
    assert set(data["summary"]) == {"calibration", "holdout", "full"}
    assert data["handoffs_file"] == "2026-10-18-part-b-run1-handoffs.jsonl"
    lines = (command.reports / data["handoffs_file"]).read_text(encoding="utf-8").splitlines()
    assert len(lines) == data["handoff_records"] == 3  # T-002, T-003, T-004
    assert all(missing_fields(json.loads(line)) == [] for line in lines)
    md = (command.reports / "2026-10-18-part-b-run1.md").read_text(encoding="utf-8")
    assert "**VALID**" in md and "## Answers (for the Step 10 review)" in md
    assert "Malformed model outputs: 0." in md and "slightly underestimated" in md
    assert "Check the motor wiring." in md and "Rejected draft (failed_check citation" in md
    # The sweep reads it.
    assert set(load_run(command.reports / "2026-10-18-part-b-run1.json")) == {"T-001", "T-002", "T-003", "T-004"}


def test_a_valid_run_is_never_replaced(command, capsys):
    assert command.run("--confirm") == 0
    before = {p.name: p.read_bytes() for p in command.reports.iterdir()}
    assert command.run("--confirm") == 1
    assert "already exists" in capsys.readouterr().err
    assert command.generators == 1
    assert {p.name: p.read_bytes() for p in command.reports.iterdir()} == before
    assert command.run() == 1  # the dry run says so too


def test_service_error_writes_an_invalid_run_that_never_blocks_a_rerun(command, capsys):
    command.script = by_question(**{**DEFAULT_SCRIPT, "backwards": service_error})
    assert command.run("--confirm") == run_eval.EXIT_INVALID_RUN == 4
    assert command.run("--confirm") == 4
    assert "INVALID run 1 (service_error)" in capsys.readouterr().err
    data = json.loads((command.reports / "2026-10-18-part-b-run1-invalid-2.json").read_text(encoding="utf-8"))
    assert data["valid"] is False and data["stopped"] == {"reason": "service_error", "ticket_id": "T-002"}
    assert "**INVALID" in (command.reports / "2026-10-18-part-b-run1-invalid-1.md").read_text(encoding="utf-8")
    with pytest.raises(EvalError, match="invalid"):
        load_run(command.reports / "2026-10-18-part-b-run1-invalid-1.json")

    command.script = by_question(**DEFAULT_SCRIPT)
    assert command.run("--confirm") == 0
    assert "2026-10-18-part-b-run1.json" in command.files()
    assert len([f for f in command.files() if "invalid" in f]) == 6


def test_aborted_run_is_kept_as_invalid(command, capsys):
    command.script = by_question(**{**DEFAULT_SCRIPT, "backwards": KeyboardInterrupt()})
    assert command.run("--confirm") == 1
    data = json.loads((command.reports / "2026-10-18-part-b-run1-invalid-1.json").read_text(encoding="utf-8"))
    assert data["stopped"]["reason"].startswith("aborted: KeyboardInterrupt") and data["model_calls"] == 2


def test_uncommitted_code_blocks_a_paid_run(command, capsys):
    command.changes = ["query/flow.py"]
    assert command.run("--confirm") == 1
    assert "query/flow.py" in capsys.readouterr().err
    assert command.generators == 0 and command.files() == []


def test_generator_startup_failure_writes_nothing(command, monkeypatch, capsys):
    def no_key():
        raise ConfigError("VOLTRIX_ANTHROPIC_API_KEY is not set")

    monkeypatch.setattr(run_eval, "make_real_generator", no_key)
    assert command.run("--confirm") == 1
    assert "cannot start" in capsys.readouterr().err and command.files() == []


def test_handoffs_folder_change_makes_the_run_invalid(command, monkeypatch):
    real = run_eval.part_b

    def touching(*args):
        command.handoffs.mkdir()
        (command.handoffs / "handoffs.jsonl").write_text("{}\n")
        return real(*args)

    monkeypatch.setattr(run_eval, "part_b", touching)
    assert command.run("--confirm") == 1
    data = json.loads((command.reports / "2026-10-18-part-b-run1-invalid-1.json").read_text(encoding="utf-8"))
    assert data["stopped"]["reason"] == "handoffs/ changed during the run"


def test_run_number_must_be_1_2_or_3(command):
    with pytest.raises(SystemExit):
        command.run(run_number=4)


def test_three_runs_feed_the_aggregate_and_the_sweep(command, capsys):
    for n in (1, 2, 3):
        assert command.run("--confirm", run_number=n) == 0
    runs = [str(command.reports / f"2026-10-18-part-b-run{n}.json") for n in (1, 2, 3)]
    common = ["--date", "2026-10-18", "--reports-dir", str(command.reports)]
    ticket_file = str(command.reports.parent / "tickets.jsonl")
    assert run_eval.main(["aggregate", "--runs", *runs, *common, "--tickets", ticket_file]) == 0
    data = json.loads((command.reports / "2026-10-18-part-b-aggregate.json").read_text(encoding="utf-8"))
    assert data["sets"]["full"]["tickets_passed_in_all_runs"] == 3  # all but T-002 (citation check)
    assert data["sets"]["full"]["failed_in_some_run"] == ["T-002"]
    assert data["sets"]["full"]["unstable"] == []
    assert data["usage_total"]["model_calls"] == 9
    assert run_eval.main(["sweep", "--runs", *runs, *common, "--tickets", ticket_file]) == 0


# --- The threshold is the evaluation's own --------------------------------------------


def test_evaluation_never_sets_the_bots_threshold(command, repo_root):
    config_file = repo_root / "query" / "config.py"
    before = config_file.read_bytes()
    assert command.run("--confirm") == 0
    assert config_file.read_bytes() == before
    assert query.config.ESCALATION_THRESHOLD is None
    with pytest.raises(ConfigError, match="NOT YET SET"):
        require_threshold()


def test_evals_code_never_touches_the_threshold_setting_or_the_bots_handoff_store(repo_root):
    for path in sorted((repo_root / "evals").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert not re.search(r"\bESCALATION_THRESHOLD\b", source), path.name
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom):
                names = {a.name for a in node.names}
                assert not names & {"JsonlHandoffStore", "load_settings", "DEFAULT_HANDOFF_PATH"}, path.name


# --- uncommitted_code_changes on a real git repository --------------------------------


def test_uncommitted_code_changes(tmp_path):
    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=tmp_path,
                       check=True, capture_output=True)

    for name in ("query/flow.py", "ingestion/build.py", "specs/02.md", "evals/run_eval.py",
                 "evals/reports/r.md", "notes/n.md"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("x\n")
    git("init", "-q")
    git("add", ".")
    git("commit", "-q", "-m", "init")
    assert pb.uncommitted_code_changes(tmp_path) == []

    (tmp_path / "notes/n.md").write_text("changed\n")
    (tmp_path / "evals/reports/r.md").write_text("changed\n")
    (tmp_path / "evals/reports/new.json").write_text("{}\n")
    assert pb.uncommitted_code_changes(tmp_path) == []

    (tmp_path / "query/flow.py").write_text("changed\n")
    (tmp_path / "specs/02.md").write_text("changed\n")
    (tmp_path / "evals/new_module.py").write_text("x\n")
    (tmp_path / "ingestion/build.py").unlink()
    assert sorted(pb.uncommitted_code_changes(tmp_path)) == [
        "evals/new_module.py", "ingestion/build.py", "query/flow.py", "specs/02.md"]
    assert set(pb.code_trees(tmp_path)) == {"query", "ingestion"}


def test_uncommitted_code_changes_fails_loudly_without_git(tmp_path):
    with pytest.raises(EvalError, match="git"):
        pb.uncommitted_code_changes(tmp_path)  # not a repository
