"""Part A and the sweep command, run through the real QueryFlow with fakes."""

import ast
import json

import pytest

import ingestion
from evals import run_eval
from evals.eval_experiments import BGE_QUERY_PREFIX
from evals.eval_recorders import EvalError, MemoryHandoffStore, NoCallGenerator, RecordingRetriever
from evals.eval_report import REPORTS_DIR
from evals.eval_tickets import CALIBRATION, TICKETS_PATH, file_sha256, load_tickets, select

E01_TITLE = "E-01 Overcurrent during acceleration"
E02_TITLE = "E-02 Overcurrent during deceleration"


@pytest.fixture
def three_tickets(make_ticket):
    return [
        make_ticket("T-001", ids=("KB-001",), question="drive shows e1 when ramping, mail me at tech@example.com"),
        make_ticket("T-002", ids=("KB-019", "KB-022"), category="installation", question="motor runs backwards"),
        make_ticket("T-003", expected="escalate", question="display shows E-21, what is it"),
    ]


def test_part_a_records_the_flows_own_query(three_tickets, fake_retriever):
    data = run_eval.part_a(three_tickets, fake_retriever())
    rows = {r["ticket_id"]: r for r in data["tickets"]}
    # Clarification 3: masked and normalised (spec 02 steps 1 and 2).
    assert "E-01" in rows["T-001"]["query_sent"]
    assert "[EMAIL]" in rows["T-001"]["query_sent"]
    assert "tech@example.com" not in rows["T-001"]["query_sent"]
    assert rows["T-001"]["top_score"] == 0.80
    assert rows["T-001"]["top_article_ids"] == ["KB-001", "KB-020"]
    assert rows["T-001"]["recall_hit"] is True
    assert rows["T-002"]["recall_hit"] is False and rows["T-002"]["both_hit"] is False
    assert rows["T-003"]["recall_hit"] is None
    # The raw searches are recorded as information: the flow's query, then
    # the code-boost title search for the known code E-01.
    assert [s["query"] for s in rows["T-001"]["searches"]] == [rows["T-001"]["query_sent"], E01_TITLE]
    assert [s["query"] for s in rows["T-002"]["searches"]] == ["motor runs backwards"]
    # The unknown code E-21 stops the flow before the model, and its
    # retrieved chunks still come from the handoff record (criterion 8).
    assert rows["T-003"]["top_article_ids"] == ["KB-001", "KB-020"]


def test_part_a_counts_planned_model_calls(three_tickets, fake_retriever):
    data = run_eval.part_a(three_tickets, fake_retriever())
    rows = {r["ticket_id"]: r for r in data["tickets"]}
    # E-21 is not a known fault code: the flow stops before the model.
    assert rows["T-003"]["model_called"] is False
    assert rows["T-001"]["model_called"] is True
    assert data["planned_model_calls"] == 2
    assert data["summary"]["full"]["escalate_stopped_by_fault_code_check"] == ["T-003"]


def test_part_a_uses_threshold_minus_one(three_tickets, fake_retriever):
    data = run_eval.part_a(three_tickets, fake_retriever())
    assert (data["kb_version"], data["threshold"]) == ("v1", -1.0)
    assert "spec 02 step 3" in data["retrieval"]
    assert "k" not in data
    assert set(data["summary"]) == {"calibration", "holdout", "full"}


def test_part_a_reports_the_final_chunks_not_a_raw_search(make_ticket, fake_retriever):
    """The main search finds five KB-020 chunks first; the E-02 title search
    finds KB-002 higher. The final chunks are one per article, merged."""

    def scores(query):
        if query == E02_TITLE:
            return [("KB-002", 0.95)]
        return [("KB-020", 0.80), ("KB-020", 0.79), ("KB-020", 0.78), ("KB-020", 0.77), ("KB-020", 0.76),
                ("KB-019", 0.70), ("KB-001", 0.65)]

    ticket = make_ticket("T-001", ids=("KB-002", "KB-019"), question="drive trips with E2 when stopping")
    row = run_eval.part_a([ticket], fake_retriever(scores))["tickets"][0]
    assert row["top_article_ids"] == ["KB-002", "KB-020", "KB-019", "KB-001"]
    assert [c["chunk_id"] for c in row["top_chunks"]] == ["KB-002#c1", "KB-020#c1", "KB-019#c6", "KB-001#c7"]
    assert row["top_score"] == 0.95
    assert row["recall_hit"] is True and row["both_hit"] is True
    assert [s["query"] for s in row["searches"]] == ["drive trips with E-02 when stopping", E02_TITLE]


def test_part_a_refuses_a_prefixed_query(make_ticket, fake_retriever):
    # search() adds the prefix itself (spec 03 v1.4): a query that already
    # has it would be embedded with a double prefix.
    ticket = make_ticket("T-001", question=BGE_QUERY_PREFIX + "how do i set the ramp")
    with pytest.raises(EvalError, match="prefix"):
        run_eval.part_a([ticket], fake_retriever())


def test_part_a_does_not_reimplement_retrieval(repo_root):
    """Part A takes the final chunks from the flow; the runner imports
    nothing from the Part A2 simulation except the prefix for the guard."""
    tree = ast.parse((repo_root / "evals" / "run_eval.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "evals.eval_experiments":
            assert {a.name for a in node.names} == {"BGE_QUERY_PREFIX"}


def test_part_a_low_scores_never_escalate_at_minus_one(make_ticket, fake_retriever):
    # With threshold -1.0 even a very low score reaches the model.
    data = run_eval.part_a([make_ticket("T-001")], fake_retriever(lambda q: [("KB-001", -0.5)]))
    assert data["tickets"][0]["model_called"] is True


def test_part_a_fails_loudly_without_chunks(make_ticket, fake_retriever):
    with pytest.raises(EvalError, match="no chunks"):
        run_eval.part_a([make_ticket("T-001")], fake_retriever(lambda q: []))


def test_recorders(fake_retriever):
    recorder = RecordingRetriever(fake_retriever())
    recorder.search("a", 5)
    recorder.search("b", 3)
    calls = recorder.take()
    assert [(c.query, c.k) for c in calls] == [("a", 5), ("b", 3)]
    assert calls[0].top_score == 0.80
    assert recorder.take() == []
    gen = NoCallGenerator()
    assert gen.generate("q", []).decision == "insufficient_context"
    assert gen.calls == 1
    assert MemoryHandoffStore().by_id("x") is None


def handoffs_snapshot(repo_root):
    folder = repo_root / "handoffs"
    if not folder.exists():
        return None
    return {p.name: p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def write_fake_part_a2(path, fake_retriever, make_part_a2, change=None):
    """A Part A2 report equal to what Part A finds with the fake retriever."""
    data = run_eval.part_a(load_tickets(), fake_retriever())
    a2 = make_part_a2(data, file_sha256(TICKETS_PATH))
    if change:
        change(a2)
    path.write_text(json.dumps(a2), encoding="utf-8")
    return path


def test_part_a_command_writes_reports_only(tmp_path, monkeypatch, fake_retriever, make_part_a2, repo_root, capsys):
    monkeypatch.setattr(ingestion, "open_retrieval", lambda kb_version: fake_retriever(kb_version=kb_version))
    a2 = write_fake_part_a2(tmp_path / "a2.json", fake_retriever, make_part_a2)
    out = tmp_path / "reports"
    before_tickets = file_sha256(TICKETS_PATH)
    before_handoffs = handoffs_snapshot(repo_root)
    argv = ["part-a", "--date", "2026-10-16", "--reports-dir", str(out), "--part-a2-report", str(a2)]

    assert run_eval.main(argv) == 0
    assert "MATCH with the Part A2 E1+E2+E3 simulation: 70/70 tickets" in capsys.readouterr().out

    data = json.loads((out / "2026-10-16-part-a-retrieval.json").read_text(encoding="utf-8"))
    md = (out / "2026-10-16-part-a-retrieval.md").read_text(encoding="utf-8")
    assert data["kind"] == "part-a" and len(data["tickets"]) == 70
    assert data["ticket_file_sha256"] == before_tickets
    assert data["against_part_a2"]["match"] is True
    assert "## Retrieval recall" in md and "## Top-score distributions" in md
    assert "## Against the Part A2 simulation (E1+E2+E3)" in md and "**MATCH**" in md
    assert sorted(p.name for p in out.iterdir()) == [
        "2026-10-16-part-a-retrieval.json",
        "2026-10-16-part-a-retrieval.md",
    ]
    assert file_sha256(TICKETS_PATH) == before_tickets
    assert handoffs_snapshot(repo_root) == before_handoffs


def test_part_a_command_mismatch_writes_report_then_exits_3(tmp_path, monkeypatch, fake_retriever, make_part_a2,
                                                           capsys):
    def change(a2):
        a2["tickets"][4]["results"]["E1+E2+E3"]["top_score"] += 0.01

    monkeypatch.setattr(ingestion, "open_retrieval", lambda kb_version: fake_retriever(kb_version=kb_version))
    a2 = write_fake_part_a2(tmp_path / "a2.json", fake_retriever, make_part_a2, change)
    out = tmp_path / "reports"
    argv = ["part-a", "--date", "2026-10-16", "--reports-dir", str(out), "--part-a2-report", str(a2)]

    assert run_eval.main(argv) == run_eval.EXIT_MISMATCH == 3
    assert "MISMATCH" in capsys.readouterr().err
    data = json.loads((out / "2026-10-16-part-a-retrieval.json").read_text(encoding="utf-8"))
    md = (out / "2026-10-16-part-a-retrieval.md").read_text(encoding="utf-8")
    assert data["against_part_a2"]["match"] is False
    assert [d["field"] for d in data["against_part_a2"]["differences"]] == ["top_score"]
    assert "**MISMATCH**" in md and "69/70 tickets match" in md


def test_part_a_command_refuses_to_overwrite(tmp_path, monkeypatch, fake_retriever, make_part_a2, capsys):
    monkeypatch.setattr(ingestion, "open_retrieval", lambda kb_version: fake_retriever(kb_version=kb_version))
    a2 = write_fake_part_a2(tmp_path / "a2.json", fake_retriever, make_part_a2)
    argv = ["part-a", "--date", "2026-10-16", "--reports-dir", str(tmp_path / "r"), "--part-a2-report", str(a2)]
    assert run_eval.main(argv) == 0
    assert run_eval.main(argv) == 1
    assert "--overwrite" in capsys.readouterr().err
    assert run_eval.main(argv + ["--overwrite"]) == 0


def test_part_a2_command_refuses(monkeypatch, capsys):
    def no_retrieval(kb_version):
        raise AssertionError("part-a2 must not open retrieval")

    monkeypatch.setattr(ingestion, "open_retrieval", no_retrieval)
    before = sorted(p.name for p in REPORTS_DIR.iterdir())
    assert run_eval.main(["part-a2"]) == 1
    err = capsys.readouterr().err
    assert "completed on 2026-10-17" in err and "cannot be re-run" in err
    assert "evals/reports/2026-10-17-part-a2-retrieval-experiments.md" in err
    assert sorted(p.name for p in REPORTS_DIR.iterdir()) == before


def write_part_b(path, tickets, score=0.75):
    records = [
        {
            "ticket_id": t.ticket_id,
            "top_score": score,
            "status": "answered" if t.expected == "answer" else "escalated",
            "escalation_reason": "" if t.expected == "answer" else "out_of_scope",
            "citations": [{"article_id": a, "title": a} for a in t.expected_article_ids[:1]],
            "failed_check": "",
            "model_called": True,
        }
        for t in tickets
    ]
    path.write_text(json.dumps({"kind": "part-b", "threshold": -1.0, "valid": True, "tickets": records}))
    return path


def test_sweep_command(tmp_path):
    calibration = select(load_tickets(), CALIBRATION)
    runs = [str(write_part_b(tmp_path / f"run{i}.json", calibration)) for i in (1, 2, 3)]
    out = tmp_path / "reports"
    assert run_eval.main(["sweep", "--runs", *runs, "--date", "2026-10-16", "--reports-dir", str(out)]) == 0
    data = json.loads((out / "2026-10-16-part-c-sweep.json").read_text(encoding="utf-8"))
    md = (out / "2026-10-16-part-c-sweep.md").read_text(encoding="utf-8")
    assert data["set"] == "calibration" and data["n_tickets"] == 35
    assert (data["n_answer"], data["n_escalate"]) == (24, 11)
    assert len(data["rows"]) == 41
    # Every ticket is right at -1.0 and every score is 0.75: targets are met
    # up to 0.75, and above it every answer ticket is cut.
    assert data["thresholds_meeting_targets"] == [r["threshold"] for r in data["rows"] if r["threshold"] <= 0.75]
    assert "does NOT choose the threshold" in md


def test_sweep_command_needs_three_different_runs(tmp_path, capsys):
    calibration = select(load_tickets(), CALIBRATION)
    run = str(write_part_b(tmp_path / "run1.json", calibration))
    other = str(write_part_b(tmp_path / "run2.json", calibration))
    assert run_eval.main(["sweep", "--runs", run, other, "--reports-dir", str(tmp_path)]) == 1
    assert run_eval.main(["sweep", "--runs", run, run, other, "--reports-dir", str(tmp_path)]) == 1
    assert "3 different Part B run files" in capsys.readouterr().err


def test_sweep_command_refuses_invalid_run(tmp_path, capsys):
    calibration = select(load_tickets(), CALIBRATION)
    runs = [write_part_b(tmp_path / f"run{i}.json", calibration) for i in (1, 2, 3)]
    data = json.loads(runs[2].read_text())
    data["valid"] = False
    runs[2].write_text(json.dumps(data))
    assert run_eval.main(["sweep", "--runs", *map(str, runs), "--reports-dir", str(tmp_path)]) == 1
    assert "invalid" in capsys.readouterr().err


# Spec 05 "Independence": only the bot's public parts (QueryFlow,
# AnthropicGenerator, open_retrieval) and their inputs and outputs are
# imported. The two generator exceptions are AnthropicGenerator's outputs
# (Part B records malformed output and service errors).
ALLOWED_IMPORTS = {
    "ingestion": {"Chunk", "KBInfo", "open_retrieval"},
    "query.flow": {"QueryFlow"},
    "query.anthropic_api": {"AnthropicGenerator"},
    "query.generator": {"GeneratorOutput", "MalformedOutput", "GeneratorServiceError"},
    "query.handoff": {"HandoffRecord"},
}


def test_evals_import_only_public_parts(repo_root):
    for path in sorted((repo_root / "evals").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in ("query", "ingestion"), f"{path.name}: import {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top in ("query", "ingestion"):
                    names = {a.name for a in node.names}
                    assert node.module in ALLOWED_IMPORTS, f"{path.name}: from {node.module}"
                    assert names <= ALLOWED_IMPORTS[node.module], f"{path.name}: {names}"
