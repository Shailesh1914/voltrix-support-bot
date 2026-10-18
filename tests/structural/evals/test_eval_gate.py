"""Evaluation gate for CI (spec 06, Workflow 2).

Fakes only: a scripted Anthropic client (or a mocked HTTP API) and a fake
index. AnthropicGenerator, QueryFlow and every check in query/ are the real
ones. Includes mutation checks: each one plants a specific defect and shows
that a test catches it.
"""

import ast
import json
import re
import subprocess
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

import ingestion
import query.anthropic_api
import query.config
import query.handoff
from evals import eval_gate as gate
from evals import eval_part_b as pb
from evals import run_eval
from evals.eval_aggregate import load_part_b
from evals.eval_recorders import EvalError
from query.anthropic_api import KEY_NAME, AnthropicGenerator
from query.config import MODEL_ID
from query.prompt import TOOL_NAME

THRESHOLD = 0.60
DATE = "2026-10-18"
TREES = {"query": "q-tree", "ingestion": "i-tree", "evals/*.py": "e-id"}
REPORT = f"{DATE}-gate.json"
FILES = [f"{DATE}-gate-handoffs.jsonl", f"{DATE}-gate.json", f"{DATE}-gate.md"]

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
    """T-002 ("backwards") scores 0.70: answered at 0.60, low_similarity above 0.70."""
    if "backwards" in query:
        return [("KB-019", 0.70), ("KB-022", 0.65)]
    return [("KB-001", 0.80), ("KB-020", 0.60)]


# T-001 answer; T-002 answer (score 0.70); T-003 escalate (unknown code E-21,
# no model call); T-004 escalate (model: out_of_scope). All pass at 0.60.
@pytest.fixture
def tickets(make_ticket):
    return [
        make_ticket("T-001", ids=("KB-001",), question="drive shows e1 when ramping"),
        make_ticket("T-002", ids=("KB-019", "KB-022"), category="installation", question="motor runs backwards"),
        make_ticket("T-003", expected="escalate", question="display shows E-21, what is it"),
        make_ticket("T-004", expected="escalate", category="scope", question="what is the price of a spare fan"),
    ]


def write_tickets(path, tickets):
    path.write_text("".join(
        json.dumps({"ticket_id": t.ticket_id, "question": t.question, "expected": t.expected,
                    "expected_article_ids": list(t.expected_article_ids), "category": t.category}) + "\n"
        for t in tickets), encoding="utf-8")
    return path


@pytest.fixture
def bench(tmp_path, monkeypatch, tickets, fake_retriever):
    """`gate` on the fakes. The bot's threshold is 0.60 in query.config; the
    output folder is a fresh folder outside the repository."""
    ticket_file = write_tickets(tmp_path / "tickets.jsonl", tickets)
    state = SimpleNamespace(script=by_question(**SCRIPT), scores=scores, generators=0, changes=[],
                            out=tmp_path / "gate-report", handoffs=tmp_path / "handoffs", trees=dict(TREES),
                            flow_thresholds=[], ticket_file=ticket_file)

    def make_real_generator():
        state.generators += 1
        return AnthropicGenerator(FakeClient(lambda q: state.script(q)))

    def refuse(*args, **kwargs):
        raise AssertionError("the bot's file handoff store must never be used by the evaluation")

    real_build_flow = run_eval.build_flow

    def spy_build_flow(retriever, generator, store, threshold=run_eval.NO_ESCALATION_THRESHOLD):
        state.flow_thresholds.append(threshold)
        return real_build_flow(retriever, generator, store, threshold)

    monkeypatch.setattr(ingestion, "open_retrieval",
                        lambda kb_version: fake_retriever(scores=lambda q: state.scores(q), kb_version=kb_version))
    monkeypatch.setattr(run_eval, "make_real_generator", make_real_generator)
    monkeypatch.setattr(run_eval, "HANDOFFS_DIR", state.handoffs)
    monkeypatch.setattr(run_eval, "build_flow", spy_build_flow)
    monkeypatch.setattr(pb, "uncommitted_code_changes", lambda: list(state.changes))
    monkeypatch.setattr(pb, "code_trees", lambda: dict(state.trees))
    monkeypatch.setattr(query.handoff, "JsonlHandoffStore", refuse)
    monkeypatch.setattr(query.config, "ESCALATION_THRESHOLD", THRESHOLD)

    def run(*extra, out=None):
        return run_eval.main(["gate", "--out-dir", str(out or state.out), "--date", DATE,
                              "--tickets", str(state.ticket_file), *extra])

    state.run = run
    state.files = lambda: sorted(p.name for p in state.out.iterdir()) if state.out.exists() else []
    state.data = lambda: json.loads((state.out / REPORT).read_text(encoding="utf-8"))
    state.md = lambda: (state.out / f"{DATE}-gate.md").read_text(encoding="utf-8")
    return state


# --- Dry run ---------------------------------------------------------------------------


def test_dry_run_is_free_writes_nothing_and_never_looks_like_a_pass(bench, capsys):
    code = bench.run()
    assert code == gate.EXIT_DRY_RUN != 0
    out = capsys.readouterr().out
    assert "at threshold 0.6 (read from query/config.py)" in out
    assert "planned model calls:  3 (limit 100 per run)" in out
    assert "DRY RUN: the gate was NOT evaluated" in out
    assert "--confirm" in out
    assert bench.generators == 0
    assert not bench.out.exists() and not bench.handoffs.exists()


# --- Pass ------------------------------------------------------------------------------


def test_gate_passes_and_writes_its_report_to_the_output_folder(bench, capsys):
    assert bench.run("--confirm") == gate.EXIT_PASS == 0
    captured = capsys.readouterr()
    assert "GATE PASSED on the full set: AC1 2/2 (100.0%, target 85%); AC2 2/2 (100.0%, target 95%)" in captured.out
    assert bench.files() == FILES
    assert not bench.handoffs.exists()
    data = bench.data()
    assert (data["kind"], data["threshold"], data["threshold_source"], data["valid"]) == (
        "gate", 0.60, "query/config.py", True)
    assert data["exit_code"] == 0 and data["gate"]["passed"] is True and data["gate"]["set"] == "full"
    assert data["model_calls"] == 3
    assert "**PASSED**" in bench.md()
    lines = (bench.out / data["handoffs_file"]).read_text(encoding="utf-8").splitlines()
    assert len(lines) == data["handoff_records"] == 2  # T-003, T-004


def test_output_folder_is_created_in_a_fresh_place(bench, tmp_path):
    out = tmp_path / "a" / "b" / "c"
    assert bench.run("--confirm", out=out) == 0
    assert sorted(p.name for p in out.iterdir()) == FILES


def test_gate_file_is_never_read_as_a_part_b_run(bench):
    assert bench.run("--confirm") == 0
    with pytest.raises(EvalError, match="not a Part B run"):
        load_part_b(bench.out / REPORT)


def test_existing_report_is_never_replaced(bench, capsys):
    assert bench.run("--confirm") == 0
    before = {p.name: p.read_bytes() for p in bench.out.iterdir()}
    bench.generators = 0
    assert bench.run("--confirm") == 1
    assert "never replaces a report" in capsys.readouterr().err
    assert bench.generators == 0
    assert {p.name: p.read_bytes() for p in bench.out.iterdir()} == before


# --- Quality failures --------------------------------------------------------------------


def test_ac1_below_target_fails_and_says_so(bench, capsys):
    bench.script = by_question(**SCRIPT, ramping=lambda: message(decision="insufficient_context"))
    assert bench.run("--confirm") == gate.EXIT_QUALITY_FAILED == 3
    err = capsys.readouterr().err
    assert "GATE FAILED: AC1 below target." in err and "AC1 1/2 (50.0%, target 85%)" in err
    assert "AC2 below target" not in err
    data = bench.data()
    assert data["gate"]["failed_criteria"] == ["AC1"] and data["exit_code"] == 3
    assert "**FAILED**: AC1 below target" in bench.md()
    assert "| T-001 |" in bench.md()  # listed under tickets that did not pass


def test_ac2_below_target_fails_and_says_so(bench, capsys):
    bench.script = by_question(**{**SCRIPT, "price": lambda: message(used=("KB-001",))})
    assert bench.run("--confirm") == 3
    err = capsys.readouterr().err
    assert "GATE FAILED: AC2 below target." in err and "AC2 1/2 (50.0%, target 95%)" in err
    assert bench.data()["gate"]["failed_criteria"] == ["AC2"]


def test_both_below_target_names_both(bench, capsys):
    bench.script = by_question(**{**SCRIPT, "price": lambda: message(used=("KB-001",)),
                                  "ramping": lambda: message(decision="insufficient_context")})
    assert bench.run("--confirm") == 3
    assert "GATE FAILED: AC1 below target and AC2 below target." in capsys.readouterr().err


def test_only_the_full_set_gates(bench, make_ticket):
    """The full set passes while the calibration set fails both criteria:
    the gate passes (spec 06: "on the full ticket set")."""
    answer = [make_ticket(f"T-{n:03d}", ids=("KB-001",),
                          question=f"drive shows e1 case {n}" + (" special" if n in (1, 3) else ""))
              for n in range(1, 22)]
    escalate = make_ticket("T-100", expected="escalate", question="display shows E-21, what is it")
    write_tickets(bench.ticket_file, [*answer, escalate])
    bench.script = by_question(special=lambda: message(decision="insufficient_context"))
    assert bench.run("--confirm") == 0
    summary = bench.data()["summary"]
    assert (summary["full"]["ac1"]["passed"], summary["full"]["ac1"]["total"]) == (19, 21)  # 90.5%
    assert summary["calibration"]["ac1_meets_target"] is False  # 9/11 = 81.8%
    assert summary["calibration"]["ac2_meets_target"] is False  # no escalate tickets


# --- service_error is an outage, never a quality result -------------------------------


def test_service_error_has_its_own_exit_code(bench, capsys):
    bench.script = by_question(**{**SCRIPT, "price": anthropic.AnthropicError("overloaded")})
    assert bench.run("--confirm") == gate.EXIT_SERVICE_ERROR == 4
    err = capsys.readouterr().err
    assert "GATE ERROR: service_error at T-004" in err and "not a quality result" in err
    assert "GATE FAILED" not in err and "GATE PASSED" not in err
    data = bench.data()
    assert data["valid"] is False and data["gate"] is None and data["exit_code"] == 4
    assert data["stopped"] == {"reason": "service_error", "ticket_id": "T-004"}
    assert "**NO RESULT**" in bench.md()


def test_service_error_on_an_answer_ticket_is_not_a_quality_failure(bench, capsys):
    """Without the outage rule this would look like an AC1 failure."""
    bench.script = by_question(**{**SCRIPT, "ramping": anthropic.AnthropicError("connection reset")})
    assert bench.run("--confirm") == 4
    assert "GATE FAILED" not in capsys.readouterr().err


def test_other_aborted_runs_are_errors_not_results(bench, monkeypatch, capsys):
    real = pb.run_tickets

    def touching(*args):
        outcome = real(*args)
        bench.handoffs.mkdir()
        (bench.handoffs / "handoffs.jsonl").write_text("x", encoding="utf-8")
        return outcome

    monkeypatch.setattr(pb, "run_tickets", touching)
    assert bench.run("--confirm") == 1
    assert "GATE ERROR: the run is invalid (handoffs/ changed during the run)" in capsys.readouterr().err


# --- The threshold comes from query/config.py only ----------------------------------


def test_threshold_follows_the_config_setting(bench, monkeypatch, capsys):
    assert bench.run("--confirm") == 0
    assert set(bench.flow_thresholds) == {0.60}
    monkeypatch.setattr(query.config, "ESCALATION_THRESHOLD", 0.75)
    bench.flow_thresholds.clear()
    out2 = bench.out.parent / "second"
    assert bench.run("--confirm", out=out2) == 3  # T-002 (0.70) now escalates: low_similarity
    assert set(bench.flow_thresholds) == {0.75}
    data = json.loads((out2 / REPORT).read_text(encoding="utf-8"))
    assert data["threshold"] == 0.75
    rows = {r["ticket_id"]: r for r in data["tickets"]}
    assert rows["T-002"]["escalation_reason"] == "low_similarity"


def test_there_is_no_threshold_option(bench):
    with pytest.raises(SystemExit):
        bench.run("--threshold", "0.1")


def test_environment_cannot_supply_the_threshold(bench, monkeypatch):
    monkeypatch.setenv("ESCALATION_THRESHOLD", "-1.0")
    assert bench.run("--confirm") == 0
    assert set(bench.flow_thresholds) == {0.60}


def test_unset_threshold_refuses_before_anything(bench, monkeypatch, capsys):
    monkeypatch.setattr(query.config, "ESCALATION_THRESHOLD", None)
    assert bench.run("--confirm") == 1
    assert "the gate cannot run" in capsys.readouterr().err
    assert bench.generators == 0 and not bench.out.exists() and bench.flow_thresholds == []


def test_gate_code_never_names_the_threshold_setting(repo_root):
    """The gate reads the threshold only through the one reader in
    eval_confirm (guarded in test_eval_part_b)."""
    for name in ("eval_gate.py", "run_eval.py"):
        source = (repo_root / "evals" / name).read_text(encoding="utf-8")
        assert not re.search(r"\bESCALATION_THRESHOLD\b", source), name
    tree = ast.parse((repo_root / "evals" / "eval_gate.py").read_text(encoding="utf-8"))
    calls = [ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert "ec.bot_threshold" in calls


# --- kb_v1 index ------------------------------------------------------------------


def test_missing_kb_v1_index_fails_clearly(bench, monkeypatch, tmp_path, capsys):
    from ingestion.retrieval import open_retrieval as real_open

    monkeypatch.setattr(ingestion, "open_retrieval", lambda v: real_open(v, index_root=tmp_path / "no-indexes"))
    assert bench.run() == 1
    err = capsys.readouterr().err
    assert "the gate needs the kb_v1 index" in err and "no index for kb_version 'v1'" in err
    assert bench.generators == 0 and not bench.out.exists()


# --- Output folder and git state --------------------------------------------------


@pytest.mark.parametrize("inside", ["handoffs", "handoffs/sub", "query", "ingestion/x", "specs", "data/kb_v1",
                                    "evals", ".", ""])
def test_output_folder_refused_where_it_could_hide_or_be_a_change(tmp_path, inside):
    root = tmp_path / "repo"
    with pytest.raises(EvalError, match="output folder"):
        gate.check_output_folder(root / inside, root)


@pytest.mark.parametrize("inside", ["evals/reports", "evals/gate-out", "gate-report", "build/gate"])
def test_output_folder_allowed(tmp_path, inside):
    root = tmp_path / "repo"
    assert gate.check_output_folder(root / inside, root) == (root / inside).resolve()
    assert gate.check_output_folder(tmp_path / "elsewhere", root) == (tmp_path / "elsewhere").resolve()


def test_handoffs_output_folder_refused_end_to_end(bench, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    assert bench.run("--confirm", out=tmp_path / "handoffs") == 1
    assert "must not be inside or contain handoffs/" in capsys.readouterr().err
    assert bench.generators == 0


def test_own_output_folder_never_blocks_but_code_changes_do(bench, monkeypatch, tmp_path, capsys):
    root = tmp_path / "repo"
    monkeypatch.setattr(gate, "REPO_ROOT", root)
    out = root / "evals" / "gate-out"
    bench.changes = ["evals/gate-out/old.json", "evals/gate-out/sub/x.md"]
    assert bench.run("--confirm", out=out) == 0
    bench.changes = ["evals/gate-out/old.json", "query/flow.py"]
    bench.generators = 0
    assert bench.run("--confirm", "--date", "2026-10-19", out=out) == 1
    err = capsys.readouterr().err
    assert "uncommitted changes" in err and "query/flow.py" in err and "old.json" not in err
    assert bench.generators == 0


def test_blocking_changes_on_a_real_git_repository(tmp_path):
    repo = tmp_path / "repo"
    (repo / "query").mkdir(parents=True)
    (repo / "evals").mkdir()
    (repo / "query" / "flow.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "evals" / "run.py").write_text("y = 1\n", encoding="utf-8")

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q")
    git("-c", "user.email=t@example.invalid", "-c", "user.name=t", "add", ".")
    git("-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "init")
    out = repo / "evals" / "gate-out"
    out.mkdir()
    (out / f"{DATE}-gate.json").write_text("{}", encoding="utf-8")
    (out / "fake.py").write_text("", encoding="utf-8")
    assert gate.blocking_changes(pb.uncommitted_code_changes(repo), out, repo) == []
    (repo / "query" / "flow.py").write_text("x = 2\n", encoding="utf-8")
    assert gate.blocking_changes(pb.uncommitted_code_changes(repo), out, repo) == ["query/flow.py"]


# --- Cost control and the key ----------------------------------------------------


def test_call_limit_refuses_before_any_paid_call(bench, make_ticket, capsys):
    many = [make_ticket(f"T-{n:03d}", ids=("KB-001",), question=f"drive shows e1 case {n}") for n in range(1, 102)]
    write_tickets(bench.ticket_file, many)
    assert bench.run() == 1
    assert "101 planned model calls exceed the limit of 100" in capsys.readouterr().err
    assert bench.run("--confirm") == 1
    assert bench.generators == 0 and not bench.out.exists()


def test_call_limit_holds_during_the_run(bench, monkeypatch, capsys):
    """The run itself refuses a call beyond the limit (here 2 of 3 planned)."""
    real = pb.UsageRecordingGenerator
    monkeypatch.setattr(pb, "UsageRecordingGenerator", lambda inner: real(inner, max_calls=2))
    assert bench.run("--confirm") == 1
    assert "refused model call 3" in capsys.readouterr().err
    assert bench.data()["model_calls"] == 2


SECRET = "sk-ant-test-GATE-SECRET-0123456789"


def api_message(tool_input):
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": MODEL_ID,
            "content": [{"type": "tool_use", "id": "toolu_1", "name": TOOL_NAME, "input": tool_input}],
            "stop_reason": "tool_use", "stop_sequence": None, "usage": {"input_tokens": 900, "output_tokens": 80}}


@pytest.mark.parametrize("status, expected_code", [(200, 0), (401, 4), (500, 4)])
def test_key_never_appears_in_output_or_files(bench, monkeypatch, capsys, status, expected_code):
    """The real make_real_generator() and from_environment(), the key in the
    environment as in CI, and a mocked HTTP API (no network)."""
    monkeypatch.setattr(run_eval, "make_real_generator", lambda: AnthropicGenerator.from_environment())
    monkeypatch.setenv(KEY_NAME, SECRET)
    monkeypatch.setattr(anthropic._base_client.time, "sleep", lambda s: None)
    seen = []

    def handler(request):
        seen.append(request.headers.get("x-api-key"))
        if status != 200:
            return httpx2.Response(status, json={"type": "error", "error": {"type": "api_error", "message": "boom"}},
                                   request=request)
        question = json.loads(request.content)["messages"][0]["content"]
        if "backwards" in question:
            body = {"decision": "answer", "answer": "Swap two motor phases.", "used_article_ids": ["KB-019"]}
        elif "price" in question:
            body = {"decision": "out_of_scope", "answer": "", "used_article_ids": []}
        else:
            body = {"decision": "answer", "answer": "Check the motor wiring.", "used_article_ids": ["KB-001"]}
        return httpx2.Response(200, json=api_message(body), request=request)

    real_make_client = query.anthropic_api.make_client
    monkeypatch.setattr(query.anthropic_api, "make_client",
                        lambda key, http_client=None: real_make_client(
                            key, httpx2.Client(transport=httpx2.MockTransport(handler))))
    assert bench.run("--confirm") == expected_code
    assert seen and set(seen) == {SECRET}  # the key was used ...
    captured = capsys.readouterr()
    assert SECRET not in captured.out and SECRET not in captured.err  # ... and never printed
    for path in bench.out.iterdir():
        assert SECRET not in path.read_text(encoding="utf-8"), path.name
        assert SECRET[-12:] not in path.read_text(encoding="utf-8"), path.name


def test_missing_key_fails_without_printing_anything_secret(bench, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(run_eval, "make_real_generator",
                        lambda: AnthropicGenerator.from_environment(secrets_path=tmp_path / "none.env"))
    assert bench.run("--confirm") == 1
    assert "the real generator cannot start: ConfigError" in capsys.readouterr().err
    assert not bench.out.exists()


# --- The verdict and the exit decision (mutation checks on the pure parts) -----------


def full_summary(ac1, ac2):
    def r(p, t):
        return {"passed": p, "total": t, "rate": p / t if t else None}

    return {"ac1": r(*ac1), "ac2": r(*ac2)}


@pytest.mark.parametrize("ac1, ac2, passed, failed", [
    ((41, 48), (22, 22), True, []),          # Step 10 result: 85.4%
    ((40, 48), (22, 22), False, ["AC1"]),    # 83.3%
    ((17, 20), (20, 20), True, []),          # exactly 85%
    ((16, 19), (20, 20), False, ["AC1"]),    # 84.2%
    ((11, 13), (20, 20), False, ["AC1"]),    # 84.6%: rounds to 85, still below
    ((48, 48), (21, 22), True, []),          # 95.5%: one miss allowed (spec 02 note)
    ((48, 48), (20, 22), False, ["AC2"]),    # 90.9%
    ((48, 48), (19, 20), True, []),          # exactly 95%
    ((40, 48), (20, 22), False, ["AC1", "AC2"]),
    ((0, 0), (22, 22), False, ["AC1"]),      # no answer tickets: never a pass
    ((48, 48), (0, 0), False, ["AC2"]),
])
def test_verdict_boundaries(ac1, ac2, passed, failed):
    v = gate.verdict(full_summary(ac1, ac2))
    assert (v["passed"], v["failed_criteria"], v["set"]) == (passed, failed, "full")


def valid_data(ac1, ac2, **over):
    summary = {"full": {**full_summary(ac1, ac2)}, "calibration": {}, "holdout": {}}
    return {"valid": True, "stopped": None, "summary": summary, "tickets": [], **over}


def test_decide_pass_and_fail():
    assert gate.decide(valid_data((41, 48), (22, 22)))[0] == 0
    code, message = gate.decide(valid_data((40, 48), (22, 22)))
    assert code == 3 and "AC1 below target" in message and "AC1 40/48 (83.3%, target 85%)" in message


def test_decide_never_trusts_a_stored_verdict():
    data = valid_data((40, 48), (22, 22), gate={"passed": True, "failed_criteria": [], "criteria": []})
    assert gate.decide(data)[0] == 3


def test_decide_service_error_wins_over_any_quality_result():
    stopped = {"reason": "service_error", "ticket_id": "T-009"}
    assert gate.decide(valid_data((1, 48), (0, 22), valid=False, stopped=stopped))[0] == 4
    assert gate.decide(valid_data((48, 48), (22, 22), valid=False, stopped=stopped))[0] == 4
    # Even a "valid" body with one service_error row is an outage.
    rows = [{"ticket_id": "T-002", "escalation_reason": "service_error"}]
    assert gate.decide(valid_data((48, 48), (22, 22), tickets=rows))[0] == 4


def test_decide_invalid_run_is_never_scored():
    data = valid_data((48, 48), (22, 22), valid=False, stopped={"reason": "aborted: X", "ticket_id": "T-1"})
    code, message = gate.decide(data)
    assert code == 1 and "invalid" in message
    assert gate.decide({**valid_data((48, 48), (22, 22)), "summary": None})[0] == 1


def test_exit_codes_are_distinct():
    codes = [gate.EXIT_PASS, gate.EXIT_QUALITY_FAILED, gate.EXIT_SERVICE_ERROR, gate.EXIT_DRY_RUN,
             run_eval.EXIT_FAILED, 2]  # 2 = argparse usage error
    assert len(set(codes)) == len(codes)


# --- Mutations: plant a defect, show the tests catch it --------------------------


def test_mutation_gate_that_passes_below_85_is_caught(monkeypatch):
    monkeypatch.setattr(gate, "AC1_TARGET_PCT", 80)  # a gate that lets 83.3% through
    with pytest.raises(AssertionError):
        test_verdict_boundaries((40, 48), (22, 22), False, ["AC1"])


def test_mutation_float_comparison_is_caught(monkeypatch):
    """A rate compared as a rounded percentage would let 84.6% (11/13) pass."""
    monkeypatch.setattr(gate.Rate, "meets",
                        lambda self, t: self.total > 0 and round(100 * self.passed / self.total) >= t)
    with pytest.raises(AssertionError):
        test_verdict_boundaries((11, 13), (20, 20), False, ["AC1"])


def test_mutation_service_error_reported_as_quality_failure_is_caught(monkeypatch):
    monkeypatch.setattr(gate, "has_service_error", lambda data: False)
    with pytest.raises(AssertionError):
        test_decide_service_error_wins_over_any_quality_result()


def test_mutation_threshold_from_elsewhere_is_caught(bench, monkeypatch):
    """A gate that ran at the evaluation's -1.0 (or any value but config's)."""
    monkeypatch.setattr(gate, "bot_threshold", lambda: run_eval.NO_ESCALATION_THRESHOLD)
    monkeypatch.setattr(query.config, "ESCALATION_THRESHOLD", 0.75)
    with pytest.raises(AssertionError):
        assert bench.run("--confirm") == 3
        assert set(bench.flow_thresholds) == {0.75}


def test_mutation_dry_run_returning_zero_is_caught(bench, monkeypatch):
    monkeypatch.setattr(gate, "EXIT_DRY_RUN", 0)
    with pytest.raises(AssertionError):
        assert bench.run() != 0


def test_mutation_split_instead_of_full_set_is_caught(monkeypatch):
    """A verdict on the calibration set instead of the full set."""
    data = valid_data((48, 48), (22, 22))
    data["summary"]["calibration"] = full_summary((10, 24), (11, 11))
    monkeypatch.setattr(gate, "FULL", "calibration")
    with pytest.raises(AssertionError):
        assert gate.decide(data)[0] == 0
