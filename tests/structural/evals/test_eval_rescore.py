"""Rescoring after a label review (spec 05 v1.8). Hand-made run files and
ticket files only: no flow, no model, no real reports."""

import hashlib
import json
import subprocess

import pytest

from evals import eval_rescore as er
from evals import run_eval
from evals.eval_aggregate import aggregate, load_part_b
from evals.eval_recorders import EvalError
from evals.eval_report import rescore_markdown
from evals.eval_tickets import read_records


def raw(ticket_id, expected="answer", ids=("KB-001",), category="fault", match=None, **extra):
    r = {
        "ticket_id": ticket_id,
        "question": f"question of {ticket_id}",
        "expected": expected,
        "expected_article_ids": list(ids) if expected == "answer" else [],
        "category": category,
        "notes": f"notes of {ticket_id}",
    }
    if match is not None:
        r["article_match"] = match
    r.update(extra)
    return r


def text_of(records) -> str:
    return "".join(json.dumps(r) + "\n" for r in records)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def old_records():
    return [
        raw("T-001", ids=("KB-001",)),  # runs cite KB-019: fails with the old label
        raw("T-002", ids=("KB-019", "KB-022"), category="installation"),
        raw("T-003", ids=("KB-020",), category="parameters"),
        raw("T-004", expected="escalate", category="scope"),
        raw("T-005", expected="escalate", category="scope"),
    ]


def with_change(records, ticket_id, **fields):
    out = []
    for r in records:
        r = dict(r)
        if r["ticket_id"] == ticket_id:
            r.update(fields)
        out.append(r)
    return out


OLD = text_of(old_records())
# The review: T-001 also accepts KB-019.
NEW = text_of(with_change(old_records(), "T-001", expected_article_ids=["KB-001", "KB-019"], article_match="any"))


def row(ticket_id, status="answered", cited=(), reason="", labels=None):
    r = {
        "ticket_id": ticket_id,
        "top_score": 0.8,
        "status": status,
        "escalation_reason": reason if status == "escalated" else "",
        "citations": [{"article_id": a, "title": a} for a in cited],
        "failed_check": "",
        "answer": "text",
        "model_called": True,
    }
    r.update(labels or {})
    return r


def labels_from(text):
    return {t.ticket_id: er.label_of(t) for _, t in read_records(text)}


def rows(t001=None, t004=None, ticket_text=OLD):
    """Run rows that store the labels of `ticket_text`, like real Part B rows."""
    lab = labels_from(ticket_text)
    return [
        t001 or row("T-001", cited=("KB-019",), labels=lab["T-001"]),
        row("T-002", cited=("KB-019", "KB-022"), labels=lab["T-002"]),
        row("T-003", cited=("KB-020",), labels=lab["T-003"]),
        t004 or row("T-004", "escalated", reason="out_of_scope", labels=lab["T-004"]),
        row("T-005", "escalated", reason="insufficient_context", labels=lab["T-005"]),
    ]


def run_file(n, ticket_rows=None, ticket_sha=None, **over):
    data = {
        "kind": "part-b", "run": n, "label": "whole-articles", "threshold": -1.0, "valid": True,
        "date": "2026-10-17", "git_commit": "c0ffee",
        "code_trees": {"query": "q1", "ingestion": "i1", "evals/*.py": "e1"}, "model_id": "claude-haiku-4-5-20251001",
        "temperature": 0, "system_prompt_sha256": "p" * 64, "ticket_file_sha256": ticket_sha or sha(OLD),
        "kb_version": "v1", "model_calls": 5, "tokens": {"input": 1000, "output": 100, "calls_without_usage": 0},
        "malformed_outputs": 0, "cost_usd": 0.0, "tickets": ticket_rows or rows(),
    }
    data.update(over)
    return data


def three_runs(**kw):
    return [run_file(n, **kw) for n in (1, 2, 3)]


def worst(data, set_name, when, metric="ac1"):
    r = data["sets"][set_name][when]["worst"][metric]
    return r["passed"], r["total"]


# --- BEFORE and AFTER -------------------------------------------------------------------


def test_relabelled_ticket_fails_before_and_passes_after():
    data = er.rescore(three_runs(), OLD, NEW)
    # T-001 is calibration (odd number).
    assert worst(data, "calibration", "before") == (1, 2)
    assert worst(data, "calibration", "after") == (2, 2)
    assert worst(data, "full", "before") == (2, 3)
    assert worst(data, "full", "after") == (3, 3)
    assert worst(data, "holdout", "before") == worst(data, "holdout", "after") == (1, 1)
    assert data["pass_changed"] == ["T-001"]
    (change,) = data["label_changes"]
    assert change["ticket_id"] == "T-001"
    assert change["before"] == {"expected": "answer", "expected_article_ids": ["KB-001"], "article_match": "all"}
    assert change["after"] == {"expected": "answer", "expected_article_ids": ["KB-001", "KB-019"], "article_match": "any"}
    assert [(r["pass_before"], r["pass_after"]) for r in change["runs"]] == [(False, True)] * 3
    assert change["passed_all_runs_before"] is False and change["passed_all_runs_after"] is True
    assert change["pass_changed"] is True


def test_before_equals_the_original_aggregate():
    runs = three_runs()
    data = er.rescore(runs, OLD, NEW)
    original = aggregate([t for _, t in read_records(OLD)], runs, sha(OLD))
    for name, s in original["sets"].items():
        before = data["sets"][name]["before"]
        assert before["worst"] == s["worst"]
        assert before["tickets_passed_in_all_runs"] == s["tickets_passed_in_all_runs"]
        assert before["unstable"] == s["unstable"]


def test_after_equals_an_aggregate_with_the_revised_labels():
    """AFTER must be scored with the NEW labels (the runs' outcomes unchanged)."""
    runs = three_runs()
    data = er.rescore(runs, OLD, NEW)
    relabelled = [run_file(n, ticket_sha=sha(NEW)) for n in (1, 2, 3)]
    expected = aggregate([t for _, t in read_records(NEW)], relabelled, sha(NEW))
    for name, s in expected["sets"].items():
        assert data["sets"][name]["after"]["worst"] == s["worst"]


def test_worst_of_three_applies():
    """T-001 cites KB-019 only in run 2: AFTER the worst AC1 is still a fail."""
    lab = labels_from(OLD)["T-001"]
    runs = [
        run_file(1, rows(t001=row("T-001", "escalated", reason="insufficient_context", labels=lab))),
        run_file(2),
        run_file(3, rows(t001=row("T-001", "escalated", reason="insufficient_context", labels=lab))),
    ]
    data = er.rescore(runs, OLD, NEW)
    assert worst(data, "calibration", "before") == (1, 2)
    assert worst(data, "calibration", "after") == (1, 2)
    (change,) = data["label_changes"]
    assert [(r["pass_before"], r["pass_after"]) for r in change["runs"]] == [(False, False), (False, True), (False, False)]
    assert change["passed_all_runs_after"] is False
    # Run 2 changed, so pass/fail changed (and T-001 becomes unstable AFTER).
    assert data["pass_changed"] == ["T-001"]
    assert data["sets"]["calibration"]["before"]["unstable"] == ["T-001"]
    assert data["sets"]["calibration"]["after"]["unstable"] == ["T-001"]


def test_label_change_without_pass_change_is_listed():
    new = text_of(with_change(old_records(), "T-003", expected_article_ids=["KB-020", "KB-022"], article_match="any"))
    data = er.rescore(three_runs(), OLD, new)
    assert [c["ticket_id"] for c in data["label_changes"]] == ["T-003"]
    assert data["label_changes"][0]["pass_changed"] is False
    assert data["pass_changed"] == []


def test_expected_may_change_answer_to_escalate():
    """T-004 was answered; the review says it should have been an answer ticket."""
    lab = labels_from(OLD)["T-004"]
    runs = three_runs(ticket_rows=rows(t004=row("T-004", cited=("KB-001",), labels=lab)))
    new = text_of(with_change(old_records(), "T-004", expected="answer", expected_article_ids=["KB-001"]))
    data = er.rescore(runs, OLD, new)
    assert worst(data, "holdout", "before", "ac2") == (0, 1)
    assert worst(data, "holdout", "after", "ac2") == (0, 0)
    assert worst(data, "holdout", "after") == (2, 2)
    assert data["pass_changed"] == ["T-004"]


def test_any_match_leaves_both_cited_metric():
    new = text_of(with_change(old_records(), "T-002", article_match="any"))
    data = er.rescore(three_runs(), OLD, new)
    assert worst(data, "holdout", "before", "both_cited") == (1, 1)
    assert worst(data, "holdout", "after", "both_cited") == (0, 0)


def test_absent_article_match_equals_all():
    """Writing the default out explicitly is not a label change."""
    new = text_of(with_change(old_records(), "T-003", article_match="all"))
    data = er.rescore(three_runs(), OLD, new)
    assert data["label_changes"] == [] and data["pass_changed"] == []


# --- Refusals ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field, value",
    [
        ("question", "a different question"),
        ("question", "question of T-001 "),  # trailing space counts
        ("category", "maintenance"),
        ("notes", "rewritten notes"),
        ("source", "new field"),
    ],
)
def test_any_other_field_differing_refuses(field, value):
    new = text_of(with_change(old_records(), "T-001", **{field: value}, article_match="any"))
    with pytest.raises(EvalError, match=f"T-001 {field}"):
        er.rescore(three_runs(), OLD, new)


def test_removed_field_refuses():
    records = old_records()
    del records[2]["notes"]
    with pytest.raises(EvalError, match="T-003 notes"):
        er.rescore(three_runs(), OLD, text_of(records))


def test_removed_ticket_refuses():
    with pytest.raises(EvalError, match="missing in the revised file: T-005"):
        er.rescore(three_runs(), OLD, text_of(old_records()[:4]))


def test_added_ticket_refuses():
    new = text_of(old_records() + [raw("T-006")])
    with pytest.raises(EvalError, match="not in the runs' file: T-006"):
        er.rescore(three_runs(), OLD, new)


def test_renamed_ticket_refuses():
    records = old_records()
    records[4]["ticket_id"] = "T-007"
    with pytest.raises(EvalError, match="ticket ids differ"):
        er.rescore(three_runs(), OLD, text_of(records))


def test_unchanged_ticket_file_refuses():
    with pytest.raises(EvalError, match="unchanged"):
        er.rescore(three_runs(), OLD, OLD)


def test_runs_made_on_another_ticket_file_refuse():
    """The 'old' text must be the runs' own ticket file (same SHA)."""
    other = text_of(with_change(old_records(), "T-003", notes="other"))
    with pytest.raises(EvalError, match="different ticket file"):
        er.rescore(three_runs(), other, NEW)


def test_run_rows_with_other_labels_refuse():
    """A run whose rows were scored with other labels than the old file."""
    lab = labels_from(NEW)["T-001"]
    runs = [run_file(1, rows(t001=row("T-001", cited=("KB-019",), labels=lab))), run_file(2), run_file(3)]
    with pytest.raises(EvalError, match="run 1 recorded other labels for T-001"):
        er.rescore(runs, OLD, NEW)


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda runs: runs[2].update(run=2), "runs 1, 2 and 3"),
        (lambda runs: runs[1].update(label="other"), "label"),
        (lambda runs: runs[1].update(model_id="other"), "model_id"),
        (lambda runs: runs[0]["tickets"].pop(), "exactly the 5 tickets"),
    ],
)
def test_runs_that_do_not_belong_together_refuse(change, message):
    runs = three_runs()
    change(runs)
    with pytest.raises(EvalError, match=message):
        er.rescore(runs, OLD, NEW)


# --- The original ticket file from git -----------------------------------------------


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
                   cwd=cwd, check=True, capture_output=True)


def test_ticket_file_from_git_finds_the_version_with_the_runs_sha(tmp_path):
    path = tmp_path / "evals" / "support_questions.jsonl"
    path.parent.mkdir()
    git(tmp_path, "init", "-q")
    path.write_text(OLD, encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "old labels")
    path.write_text(NEW, encoding="utf-8")
    git(tmp_path, "commit", "-q", "-am", "label review")
    commit, text = er.ticket_file_from_git(sha(OLD), repo_root=tmp_path, path=path)
    assert text == OLD and len(commit) == 40
    assert er.ticket_file_from_git(sha(NEW), repo_root=tmp_path, path=path)[1] == NEW
    with pytest.raises(EvalError, match="no committed version"):
        er.ticket_file_from_git("0" * 64, repo_root=tmp_path, path=path)


# --- The command -----------------------------------------------------------------------


@pytest.fixture
def command_files(tmp_path, monkeypatch):
    tickets = tmp_path / "support_questions.jsonl"
    tickets.write_bytes(NEW.encode("utf-8"))
    paths = []
    for n in (1, 2, 3):
        p = tmp_path / f"run{n}.json"
        p.write_text(json.dumps(run_file(n)), encoding="utf-8")
        paths.append(p)
    seen = []

    def fake_git(sha256):
        seen.append(sha256)
        if sha256 != sha(OLD):
            raise EvalError("no committed version")
        return "abc123" * 6 + "abcd", OLD

    monkeypatch.setattr(er, "ticket_file_from_git", fake_git)
    reports = tmp_path / "reports"
    argv = ["rescore", "--runs", *map(str, paths), "--tickets", str(tickets), "--reports-dir", str(reports),
            "--date", "2026-10-18"]
    return argv, paths, reports, seen


def test_rescore_command_writes_its_own_report_only(command_files, capsys):
    argv, paths, reports, seen = command_files
    before = {p: p.read_bytes() for p in paths}
    assert run_eval.main(argv) == 0
    assert seen == [sha(OLD)]
    assert sorted(p.name for p in reports.iterdir()) == [
        "2026-10-18-part-b-whole-articles-rescore.json", "2026-10-18-part-b-whole-articles-rescore.md",
    ]
    assert {p: p.read_bytes() for p in paths} == before
    data = json.loads((reports / "2026-10-18-part-b-whole-articles-rescore.json").read_text(encoding="utf-8"))
    assert data["kind"] == er.RESCORE_KIND
    assert data["ticket_file_sha256_before"] == sha(OLD)
    assert data["ticket_file_sha256_after"] == sha(NEW)
    assert "ticket_file_sha256" not in data
    assert data["pass_changed"] == ["T-001"]
    out = capsys.readouterr().out
    assert "calibration: AC1 1/2 (50.0%) -> 2/2 (100.0%)" in out
    assert "pass/fail changed: T-001" in out
    md = (reports / "2026-10-18-part-b-whole-articles-rescore.md").read_text(encoding="utf-8")
    assert "| T-001 | calibration | answer: KB-001 | answer: KB-001, KB-019 (any) |" in md
    # A rescoring report can never be used as a Part B run.
    with pytest.raises(EvalError, match="not a Part B run"):
        load_part_b(reports / "2026-10-18-part-b-whole-articles-rescore.json")


def test_rescore_command_refuses_to_overwrite(command_files, capsys):
    argv, _, _, _ = command_files
    assert run_eval.main(argv) == 0
    assert run_eval.main(argv) == 1
    assert "already exists" in capsys.readouterr().err


def test_rescore_command_reads_the_ticket_file_as_bytes(command_files, capsys):
    """CRLF line endings change the SHA; read_text() would hide that."""
    argv, _, reports, _ = command_files
    tickets = argv[argv.index("--tickets") + 1]
    with open(tickets, "wb") as f:
        f.write(NEW.replace("\n", "\r\n").encode("utf-8"))
    assert run_eval.main(argv) == 0
    data = json.loads((reports / "2026-10-18-part-b-whole-articles-rescore.json").read_text(encoding="utf-8"))
    assert data["ticket_file_sha256_after"] == sha(NEW.replace("\n", "\r\n"))


@pytest.mark.parametrize("n_runs", [2, 4])
def test_rescore_command_needs_three_runs(command_files, capsys, n_runs):
    argv, paths, reports, _ = command_files
    i = argv.index("--runs")
    argv = argv[: i + 1] + [str(p) for p in (paths * 2)[:n_runs]] + argv[i + 4:]
    assert run_eval.main(argv) == 1
    assert "3 different Part B run files" in capsys.readouterr().err
    assert not reports.exists()


def test_rescore_command_refuses_a_changed_question(command_files, capsys):
    argv, _, reports, _ = command_files
    tickets = argv[argv.index("--tickets") + 1]
    changed = text_of(with_change(old_records(), "T-002", question="another question"))
    with open(tickets, "wb") as f:
        f.write(changed.encode("utf-8"))
    assert run_eval.main(argv) == 1
    assert "T-002 question" in capsys.readouterr().err
    assert not reports.exists()


def test_markdown_shows_before_and_after():
    md = rescore_markdown({**er.rescore(three_runs(), OLD, NEW), "ticket_file_commit_before": "abc"})
    assert "| AC1 (target 85%) | 1/2 (50.0%) | 2/2 (100.0%) | +1 |" in md
    assert "Tickets whose pass/fail changed: T-001." in md
    for name in ("calibration", "holdout", "full"):
        assert f"### {name} set" in md
