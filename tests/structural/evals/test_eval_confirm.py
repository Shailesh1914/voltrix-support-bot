"""Part C confirmation run (spec 05): the real flow at the threshold in
query/config.py, compared with the sweep's simulation of the 3 Part B runs.

Fakes only: a scripted Anthropic client and a fake index. AnthropicGenerator,
QueryFlow and every check in query/ are the real ones. The 3 Part B runs are
made by the real part-b command on the same fakes.
"""

import json
import re
from types import SimpleNamespace

import anthropic
import pytest

import ingestion
import query.config
import query.handoff
from evals import eval_confirm as ec
from evals import eval_part_b as pb
from evals import eval_sweep
from evals import run_eval
from evals.eval_aggregate import load_part_b
from evals.eval_recorders import EvalError
from evals.eval_scoring import Outcome
from evals.eval_sweep import RunResult, load_run
from query.anthropic_api import AnthropicGenerator
from query.prompt import TOOL_NAME

THRESHOLD = 0.60
TREES = {"query": "q-tree", "ingestion": "i-tree", "evals/*.py": "e-id"}

# --- Fakes -------------------------------------------------------------------------


def message(decision="answer", answer="Check the motor wiring.", used=("KB-001",), tokens=(1200, 150)):
    block = SimpleNamespace(
        type="tool_use", name=TOOL_NAME,
        input={"decision": decision, "answer": answer if decision == "answer" else "",
               "used_article_ids": list(used) if decision == "answer" else []},
    )
    return SimpleNamespace(stop_reason="tool_use", content=[block],
                           usage=SimpleNamespace(input_tokens=tokens[0], output_tokens=tokens[1]))


def question_of(request) -> str:
    return re.search(r"<question>\n(.*)\n</question>", request["messages"][0]["content"], re.S).group(1)


class FakeClient:
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
    def script(question):
        for word, reply in replies.items():
            if word in question:
                return reply() if callable(reply) else reply
        return message()

    return script


SCRIPT = dict(
    backwards=lambda: message(used=("KB-019", "KB-022"), answer="Swap two motor phases."),
    price=lambda: message(decision="out_of_scope"),
)


def scores(query):
    """T-002 ("backwards") scores 0.55: answered at -1.0, low_similarity at 0.60.
    Everything else scores 0.80."""
    if "backwards" in query:
        return [("KB-019", 0.55), ("KB-022", 0.50)]
    return [("KB-001", 0.80), ("KB-020", 0.60)]


# T-001 answer; T-002 answer, below 0.60; T-003 escalate (unknown code E-21,
# no model call); T-004 escalate (model: out_of_scope).
@pytest.fixture
def tickets(make_ticket):
    return [
        make_ticket("T-001", ids=("KB-001",), question="drive shows e1 when ramping"),
        make_ticket("T-002", ids=("KB-019", "KB-022"), category="installation", question="motor runs backwards"),
        make_ticket("T-003", expected="escalate", question="display shows E-21, what is it"),
        make_ticket("T-004", expected="escalate", category="scope", question="what is the price of a spare fan"),
    ]


@pytest.fixture
def bench(tmp_path, monkeypatch, tickets, fake_retriever):
    """The 3 Part B runs (real part-b command, fakes), then a helper to run
    `confirm` on them. The bot's threshold is set to 0.60 in query.config."""
    ticket_file = tmp_path / "tickets.jsonl"
    ticket_file.write_text("".join(
        json.dumps({"ticket_id": t.ticket_id, "question": t.question, "expected": t.expected,
                    "expected_article_ids": list(t.expected_article_ids), "category": t.category}) + "\n"
        for t in tickets), encoding="utf-8")
    reports = tmp_path / "reports"
    state = SimpleNamespace(script=by_question(**SCRIPT), scores=scores, generators=0, changes=[],
                            reports=reports, handoffs=tmp_path / "handoffs", trees=dict(TREES))

    def make_real_generator():
        state.generators += 1
        return AnthropicGenerator(FakeClient(lambda q: state.script(q)))

    def refuse(*args, **kwargs):
        raise AssertionError("the bot's file handoff store must never be used by the evaluation")

    monkeypatch.setattr(ingestion, "open_retrieval",
                        lambda kb_version: fake_retriever(scores=lambda q: state.scores(q), kb_version=kb_version))
    monkeypatch.setattr(run_eval, "make_real_generator", make_real_generator)
    monkeypatch.setattr(run_eval, "HANDOFFS_DIR", state.handoffs)
    monkeypatch.setattr(pb, "uncommitted_code_changes", lambda: list(state.changes))
    monkeypatch.setattr(pb, "code_trees", lambda: dict(state.trees))
    monkeypatch.setattr(query.handoff, "JsonlHandoffStore", refuse)
    monkeypatch.setattr(query.config, "ESCALATION_THRESHOLD", THRESHOLD)

    common = ["--date", "2026-10-18", "--reports-dir", str(reports), "--tickets", str(ticket_file)]
    for n in (1, 2, 3):
        assert run_eval.main(["part-b", "--label", "whole-articles", "--run", str(n), "--confirm", *common]) == 0
    state.runs = [str(reports / f"2026-10-18-part-b-whole-articles-run{n}.json") for n in (1, 2, 3)]
    state.generators = 0

    def run(*extra, runs=None):
        return run_eval.main(["confirm", "--runs", *(runs or state.runs), *common, *extra])

    state.run = run
    state.files = lambda: sorted(p.name for p in reports.iterdir())
    state.part_b_files = state.files()
    state.new_files = lambda: [f for f in state.files() if f not in state.part_b_files]
    state.data = lambda name="2026-10-18-part-c-whole-articles-confirm-t0.60.json": json.loads(
        (reports / name).read_text(encoding="utf-8"))
    return state


# --- The happy path ------------------------------------------------------------------


def test_confirmed_run_matches_the_simulation(bench, capsys):
    assert bench.run("--confirm") == 0
    out = capsys.readouterr().out
    assert "at threshold 0.6 (read from query/config.py)" in out
    assert "MATCH with the sweep's simulation: 4/4 tickets, all 3 runs" in out
    assert bench.new_files() == [
        "2026-10-18-part-c-whole-articles-confirm-t0.60-handoffs.jsonl",
        "2026-10-18-part-c-whole-articles-confirm-t0.60.json",
        "2026-10-18-part-c-whole-articles-confirm-t0.60.md",
    ]
    assert not bench.handoffs.exists()
    data = bench.data()
    assert (data["kind"], data["threshold"], data["threshold_source"], data["valid"]) == (
        "part-c-confirm", 0.60, "query/config.py", True)
    assert data["comparison"]["match"] is True and data["comparison"]["differences"] == []
    assert data["comparison"]["runs_compared"] == [1, 2, 3]
    # T-002 scores 0.55: at 0.60 it never reaches the model.
    rows = {r["ticket_id"]: r for r in data["tickets"]}
    assert rows["T-002"]["escalation_reason"] == "low_similarity" and rows["T-002"]["model_called"] is False
    assert data["model_calls"] == 2  # T-001 and T-004
    full = data["summary"]["full"]
    assert full["ac1"]["passed"] == 1 and full["ac1"]["total"] == 2
    assert full["ac2"] == {"passed": 2, "total": 2, "rate": 1.0}
    assert full["wrong_escalation"]["passed"] == 1
    assert set(data["summary"]) == set(data["simulated"]) == {"calibration", "holdout", "full"}
    assert data["simulated"]["full"]["worst"]["ac1"] == full["ac1"]
    md = (bench.reports / "2026-10-18-part-c-whole-articles-confirm-t0.60.md").read_text(encoding="utf-8")
    assert "**MATCH**: 4/4 tickets agree with all 3 runs" in md
    assert "Simulated by the sweep (worst of the 3 runs)" in md and "No differences." in md
    lines = (bench.reports / data["handoffs_file"]).read_text(encoding="utf-8").splitlines()
    assert len(lines) == data["handoff_records"] == 3  # T-002, T-003, T-004


def test_confirmation_file_is_never_read_as_a_part_b_run(bench):
    assert bench.run("--confirm") == 0
    path = bench.reports / "2026-10-18-part-c-whole-articles-confirm-t0.60.json"
    with pytest.raises(EvalError, match="not a Part B run"):
        load_part_b(path)
    with pytest.raises(EvalError, match="not a Part B run"):
        load_run(path)


# --- The threshold comes from query/config.py only ------------------------------------


def test_threshold_follows_the_config_setting(bench, monkeypatch):
    monkeypatch.setattr(query.config, "ESCALATION_THRESHOLD", 0.50)
    assert bench.run("--confirm") == 0
    data = bench.data("2026-10-18-part-c-whole-articles-confirm-t0.50.json")
    assert data["threshold"] == 0.50 and data["comparison"]["threshold"] == 0.50
    rows = {r["ticket_id"]: r for r in data["tickets"]}
    assert rows["T-002"]["status"] == "answered" and data["model_calls"] == 3
    assert data["comparison"]["match"] is True


def test_unset_threshold_refuses_before_anything(bench, monkeypatch, capsys):
    monkeypatch.setattr(query.config, "ESCALATION_THRESHOLD", None)
    assert bench.run("--confirm") == 1
    assert "NOT YET SET" in capsys.readouterr().err
    assert bench.generators == 0 and bench.new_files() == []


@pytest.mark.parametrize("option", [["--threshold", "0.7"], ["--overwrite"]])
def test_there_is_no_threshold_or_overwrite_option(bench, option):
    with pytest.raises(SystemExit):
        bench.run(*option)
    assert bench.new_files() == []


def test_threshold_is_read_when_the_command_runs(monkeypatch):
    monkeypatch.setattr(query.config, "ESCALATION_THRESHOLD", 0.71)
    assert ec.bot_threshold() == 0.71
    monkeypatch.setattr(query.config, "ESCALATION_THRESHOLD", 1.5)
    with pytest.raises(EvalError, match="within -1.0..1.0"):
        ec.bot_threshold()


# Mutation: the real run at a threshold other than the config one.
def test_mutation_real_run_ignoring_the_threshold_is_caught(bench, monkeypatch, capsys):
    real_build = run_eval.build_flow

    def ignores_threshold(retriever, generator, store, threshold=run_eval.NO_ESCALATION_THRESHOLD):
        return real_build(retriever, generator, store)  # -1.0 instead of the config value

    monkeypatch.setattr(run_eval, "build_flow", ignores_threshold)
    assert bench.run("--confirm") == run_eval.EXIT_MISMATCH == 3
    assert "MISMATCH" in capsys.readouterr().err
    c = bench.data()["comparison"]
    assert c["match"] is False and c["tickets_differing"] == ["T-002"]


# Mutation: the simulation at a threshold other than the config one.
def test_mutation_simulation_at_another_threshold_is_caught(bench, monkeypatch):
    real_simulate = eval_sweep.simulate
    monkeypatch.setattr(ec, "simulate", lambda result, threshold: real_simulate(result, 0.50))
    assert bench.run("--confirm") == 3
    assert bench.data()["comparison"]["tickets_differing"] == ["T-002"]


# --- Differences are reported, never hidden ------------------------------------------


def test_a_different_model_decision_is_reported(bench, capsys):
    bench.script = by_question(**{**SCRIPT, "price": lambda: message(used=("KB-001",))})
    assert bench.run("--confirm") == 3
    assert "1 tickets differ (T-004)" in capsys.readouterr().err
    c = bench.data()["comparison"]
    assert c["match"] is False and c["tickets_matching"] == 3
    fields = {(d["run"], d["field"]) for d in c["differences"]}
    assert fields == {(n, f) for n in (1, 2, 3) for f in ("status", "escalation_reason", "ac_pass")}
    t4 = [d for d in c["differences"] if d["run"] == 1 and d["field"] == "status"][0]
    assert (t4["real"], t4["simulated"]) == ("answered", "escalated")
    md = (bench.reports / "2026-10-18-part-c-whole-articles-confirm-t0.60.md").read_text(encoding="utf-8")
    assert "**DIFFERENCES**: 1 of 4 tickets differ (T-004)" in md
    assert "| T-004 | holdout | escalate | 1 | status | answered | escalated |" in md


def test_a_differing_answer_ticket_is_reported(bench):
    # T-001 now cites the wrong article: same status, AC fails.
    bench.script = by_question(**{**SCRIPT, "E-01": lambda: message(used=("KB-020",))})
    assert bench.run("--confirm") == 3
    c = bench.data()["comparison"]
    assert {(d["ticket_id"], d["field"]) for d in c["differences"]} == {("T-001", "ac_pass")}


def outcome(status="answered", reason="", cited=("KB-001",)):
    return Outcome(status=status, escalation_reason=reason, cited_article_ids=cited if status == "answered" else ())


def real_row(ticket_id, top=0.8, status="answered", reason="", cited=("KB-001",)):
    return {"ticket_id": ticket_id, "top_score": top, "status": status, "escalation_reason": reason,
            "citations": [{"article_id": a} for a in cited] if status == "answered" else [],
            "failed_check": "", "model_called": True}


@pytest.mark.parametrize(
    "row, field",
    [
        (real_row("T-001", top=0.81), "top_score"),
        (real_row("T-001", status="escalated", reason="insufficient_context"), "status"),
        (real_row("T-001", cited=("KB-020",)), "ac_pass"),
    ],
)
def test_compare_reports_each_field(make_ticket, row, field):
    ticket = make_ticket("T-001")
    runs = [(n, {"T-001": RunResult(0.8, outcome())}) for n in (1, 2, 3)]
    c = ec.compare([ticket], [row], runs, THRESHOLD)
    assert c["match"] is False and field in {d["field"] for d in c["differences"]}
    assert ec.compare([ticket], [real_row("T-001")], runs, THRESHOLD)["match"] is True


def test_compare_reports_a_reason_difference(make_ticket):
    ticket = make_ticket("T-004", expected="escalate")
    runs = [(n, {"T-004": RunResult(0.8, outcome("escalated", "out_of_scope"))}) for n in (1, 2, 3)]
    row = real_row("T-004", status="escalated", reason="insufficient_context")
    c = ec.compare([ticket], [row], runs, THRESHOLD)
    assert [d["field"] for d in c["differences"]] == ["escalation_reason"] * 3


def test_runs_that_disagree_never_count_as_a_match(make_ticket):
    ticket = make_ticket("T-001")
    runs = [(1, {"T-001": RunResult(0.8, outcome())}), (2, {"T-001": RunResult(0.8, outcome())}),
            (3, {"T-001": RunResult(0.8, outcome("escalated", "insufficient_context"))})]
    c = ec.compare([ticket], [real_row("T-001")], runs, THRESHOLD)
    assert c["match"] is False and {d["run"] for d in c["differences"]} == {3}


def test_compare_refuses_missing_tickets(make_ticket):
    runs = [(n, {"T-001": RunResult(0.8, outcome())}) for n in (1, 2, 3)]
    with pytest.raises(EvalError, match="no result for T-001"):
        ec.compare([make_ticket("T-001")], [], runs, THRESHOLD)


# --- Checks before any money is spent --------------------------------------------------


def test_dry_run_loads_no_key_and_writes_nothing(bench, capsys):
    assert bench.run() == 0
    out = capsys.readouterr().out
    assert "planned model calls:  2 (limit 100 per run)" in out
    assert "Simulated by the sweep at this threshold" in out and "full" in out
    assert "Dry run: nothing was called or written." in out
    assert "confirm --runs " in out and out.rstrip().endswith("--confirm")
    assert bench.generators == 0 and bench.new_files() == []


def test_more_calls_than_the_limit_are_refused(bench, monkeypatch, capsys):
    monkeypatch.setattr(pb, "MAX_MODEL_CALLS", 1)
    assert bench.run("--confirm") == 1
    assert "exceed the limit of 1" in capsys.readouterr().err
    assert bench.generators == 0 and bench.new_files() == []


def test_uncommitted_code_blocks_a_paid_run(bench, capsys):
    bench.changes = ["evals/eval_confirm.py"]
    assert bench.run("--confirm") == 1
    assert "evals/eval_confirm.py" in capsys.readouterr().err
    assert bench.generators == 0 and bench.new_files() == []
    assert bench.run() == 0  # the free dry run is still allowed


def test_a_valid_confirmation_is_never_replaced(bench, capsys):
    assert bench.run("--confirm") == 0
    before = {p.name: p.read_bytes() for p in bench.reports.iterdir()}
    assert bench.run("--confirm") == 1
    assert "already exists" in capsys.readouterr().err
    assert bench.generators == 1
    assert {p.name: p.read_bytes() for p in bench.reports.iterdir()} == before
    assert bench.run() == 1  # the dry run says so too


def test_service_error_writes_an_invalid_run_that_never_blocks_a_rerun(bench, capsys):
    bench.script = by_question(**{**SCRIPT, "price": anthropic.AnthropicError("overloaded")})
    assert bench.run("--confirm") == run_eval.EXIT_INVALID_RUN == 4
    data = bench.data("2026-10-18-part-c-whole-articles-confirm-t0.60-invalid-1.json")
    assert data["valid"] is False and data["comparison"] is None
    assert data["stopped"] == {"reason": "service_error", "ticket_id": "T-004"}
    bench.script = by_question(**SCRIPT)
    assert bench.run("--confirm") == 0
    assert "2026-10-18-part-c-whole-articles-confirm-t0.60.json" in bench.files()


def test_handoffs_folder_change_makes_the_run_invalid(bench, monkeypatch):
    real = pb.run_tickets

    def touching(*args):
        bench.handoffs.mkdir()
        (bench.handoffs / "handoffs.jsonl").write_text("{}\n")
        return real(*args)

    monkeypatch.setattr(pb, "run_tickets", touching)
    assert bench.run("--confirm") == 1
    data = bench.data("2026-10-18-part-c-whole-articles-confirm-t0.60-invalid-1.json")
    assert data["stopped"]["reason"] == "handoffs/ changed during the run"


def test_needs_three_different_part_b_runs(bench, capsys):
    assert bench.run(runs=bench.runs[:2]) == 1
    assert bench.run(runs=[bench.runs[0], bench.runs[0], bench.runs[1]]) == 1
    assert "3 different Part B run files" in capsys.readouterr().err


def test_runs_that_do_not_belong_together_are_refused(bench, capsys):
    data = json.loads(open(bench.runs[2], encoding="utf-8").read())
    data["label"] = "other"
    open(bench.runs[2], "w", encoding="utf-8").write(json.dumps(data))
    assert bench.run() == 1
    assert "label" in capsys.readouterr().err and bench.new_files() == []


def test_changed_ingestion_is_refused(bench, capsys):
    bench.trees = {**TREES, "ingestion": "i-other"}
    assert bench.run() == 1
    assert "ingestion/ differs" in capsys.readouterr().err and bench.generators == 0


def test_query_changes_other_than_config_are_refused(bench, monkeypatch, capsys):
    bench.trees = {**TREES, "query": "q-other"}
    monkeypatch.setattr(ec, "changed_files", lambda a, b: ["config.py", "flow.py"])
    assert bench.run() == 1
    assert "query/ differs from the Part B runs in flow.py" in capsys.readouterr().err


def test_a_config_only_change_is_allowed_and_recorded(bench, monkeypatch):
    bench.trees = {**TREES, "query": "q-other", "evals/*.py": "e-other"}
    monkeypatch.setattr(ec, "changed_files", lambda a, b: (a, b) == ("q-tree", "q-other") and ["config.py"])
    assert bench.run("--confirm") == 0
    assert bench.data()["code_since_runs"] == {
        "query_files_changed_since_runs": ["config.py"], "evals_code_changed_since_runs": True}


def test_different_retrieval_is_refused_before_the_key(bench, capsys):
    bench.scores = lambda q: [("KB-001", 0.79), ("KB-020", 0.60)] if "backwards" not in q else scores(q)
    assert bench.run("--confirm") == 1
    assert "retrieval differs from Part B run 1" in capsys.readouterr().err
    assert bench.generators == 0 and bench.new_files() == []


def test_different_model_settings_are_refused(bench, monkeypatch, capsys):
    real = pb.request_settings
    monkeypatch.setattr(pb, "request_settings", lambda g: {**real(g), "system_prompt_sha256": "x" * 64})
    assert bench.run() == 1
    assert "system_prompt_sha256" in capsys.readouterr().err and bench.generators == 0


def test_check_code_refuses_unknown_trees():
    with pytest.raises(EvalError, match="unknown"):
        ec.check_code({**TREES, "query": None}, TREES)
    assert ec.check_code(TREES, TREES) == {"query_files_changed_since_runs": [], "evals_code_changed_since_runs": False}


def test_names():
    assert ec.confirm_name("whole-articles", 0.6) == "part-c-whole-articles-confirm-t0.60"
    assert ec.confirm_name("whole-articles", 0.605) == "part-c-whole-articles-confirm-t0.605"
    with pytest.raises(EvalError):
        pb.check_label("confirm")
