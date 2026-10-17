"""Part A and the sweep command, run through the real QueryFlow with fakes."""

import ast
import json

import pytest

import ingestion
from evals import run_eval
from evals.eval_recorders import EvalError, MemoryHandoffStore, NoCallGenerator, RecordingRetriever
from evals.eval_tickets import CALIBRATION, TICKETS_PATH, file_sha256, load_tickets, select


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


def test_part_a_counts_planned_model_calls(three_tickets, fake_retriever):
    data = run_eval.part_a(three_tickets, fake_retriever())
    rows = {r["ticket_id"]: r for r in data["tickets"]}
    # E-21 is not a known fault code: the flow stops before the model.
    assert rows["T-003"]["model_called"] is False
    assert rows["T-001"]["model_called"] is True
    assert data["planned_model_calls"] == 2
    assert data["summary"]["full"]["escalate_stopped_by_fault_code_check"] == ["T-003"]


def test_part_a_uses_k5_and_threshold_minus_one(three_tickets, fake_retriever):
    retriever = fake_retriever()
    data = run_eval.part_a(three_tickets, retriever)
    assert {k for _, k in retriever.queries} == {5}
    assert (data["kb_version"], data["k"], data["threshold"]) == ("v1", 5, -1.0)
    assert set(data["summary"]) == {"calibration", "holdout", "full"}


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


def test_part_a_command_writes_reports_only(tmp_path, monkeypatch, fake_retriever, repo_root):
    monkeypatch.setattr(ingestion, "open_retrieval", lambda kb_version: fake_retriever(kb_version=kb_version))
    before_tickets = file_sha256(TICKETS_PATH)
    before_handoffs = handoffs_snapshot(repo_root)
    argv = ["part-a", "--date", "2026-10-16", "--reports-dir", str(tmp_path)]

    assert run_eval.main(argv) == 0

    data = json.loads((tmp_path / "2026-10-16-part-a-retrieval.json").read_text(encoding="utf-8"))
    md = (tmp_path / "2026-10-16-part-a-retrieval.md").read_text(encoding="utf-8")
    assert data["kind"] == "part-a" and len(data["tickets"]) == 70
    assert data["ticket_file_sha256"] == before_tickets
    assert "## Retrieval recall" in md and "## Top-score distributions" in md
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "2026-10-16-part-a-retrieval.json",
        "2026-10-16-part-a-retrieval.md",
    ]
    assert file_sha256(TICKETS_PATH) == before_tickets
    assert handoffs_snapshot(repo_root) == before_handoffs


def test_part_a_command_refuses_to_overwrite(tmp_path, monkeypatch, fake_retriever, capsys):
    monkeypatch.setattr(ingestion, "open_retrieval", lambda kb_version: fake_retriever(kb_version=kb_version))
    argv = ["part-a", "--date", "2026-10-16", "--reports-dir", str(tmp_path)]
    assert run_eval.main(argv) == 0
    assert run_eval.main(argv) == 1
    assert "--overwrite" in capsys.readouterr().err
    assert run_eval.main(argv + ["--overwrite"]) == 0


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


# Spec 05 "Independence": only the bot's public parts and their inputs and
# outputs are imported.
ALLOWED_IMPORTS = {
    "ingestion": {"Chunk", "KBInfo", "open_retrieval"},
    "query.flow": {"QueryFlow"},
    "query.generator": {"GeneratorOutput"},
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
