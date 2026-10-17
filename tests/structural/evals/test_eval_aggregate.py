"""Aggregate of 3 Part B runs (spec 05, clarifications 1, 2 and 4). Pure
functions over hand-made run files: no flow, no model."""

import json

import pytest

from evals import run_eval
from evals.eval_aggregate import aggregate, load_part_b
from evals.eval_recorders import EvalError
from evals.eval_report import aggregate_markdown

SHA = "a" * 64


@pytest.fixture
def tickets(make_ticket):
    return [
        make_ticket("T-001", ids=("KB-001",), category="fault"),
        make_ticket("T-002", ids=("KB-019", "KB-022"), category="installation"),
        make_ticket("T-003", ids=("KB-020",), category="parameters"),
        make_ticket("T-004", expected="escalate", category="scope"),
        make_ticket("T-005", expected="escalate", category="scope"),
    ]


def row(ticket_id, status="answered", cited=(), reason="", failed_check="", answer="text", score=0.8):
    return {
        "ticket_id": ticket_id,
        "top_score": score,
        "status": status,
        "escalation_reason": reason if status == "escalated" else "",
        "citations": [{"article_id": a, "title": a} for a in cited],
        "failed_check": failed_check,
        "answer": answer,
        "model_called": True,
    }


def ok_rows():
    """Every ticket right."""
    return {
        "T-001": row("T-001", cited=("KB-001",)),
        "T-002": row("T-002", cited=("KB-019", "KB-022")),
        "T-003": row("T-003", cited=("KB-020",)),
        "T-004": row("T-004", "escalated", reason="out_of_scope"),
        "T-005": row("T-005", "escalated", reason="insufficient_context"),
    }


def run_file(n, rows=None, **over):
    data = {
        "kind": "part-b", "run": n, "threshold": -1.0, "valid": True, "date": "2026-10-18", "git_commit": "c0ffee",
        "code_trees": {"query": "q1", "ingestion": "i1"}, "model_id": "claude-haiku-4-5-20251001",
        "temperature": 0, "system_prompt_sha256": "p" * 64, "ticket_file_sha256": SHA, "kb_version": "v1",
        "model_calls": 5, "tokens": {"input": 1000 * n, "output": 100 * n, "calls_without_usage": 0},
        "malformed_outputs": n - 1, "cost_usd": 0.0,
        "tickets": list((rows or ok_rows()).values()),
    }
    data.update(over)
    return data


def changed(**rows):
    base = ok_rows()
    base.update(rows)
    return base


def test_worst_is_per_metric_lowest_success_highest_error(tickets):
    runs = [
        # run 1: T-001 escalated (AC1 2/3, wrong escalation 1/3)
        run_file(1, changed(**{"T-001": row("T-001", "escalated", reason="insufficient_context")})),
        # run 2: T-004 answered (AC2 1/2), everything else right
        run_file(2, changed(**{"T-004": row("T-004", cited=("KB-001",))})),
        # run 3: T-001 and T-003 escalated (AC1 1/3, wrong escalation 2/3);
        # T-002 cites one of two articles (both-cited 0/1)
        run_file(3, changed(**{
            "T-001": row("T-001", "escalated", reason="low_similarity"),
            "T-003": row("T-003", "escalated", reason="out_of_scope"),
            "T-002": row("T-002", cited=("KB-019",)),
        })),
    ]
    data = aggregate(tickets, runs, SHA)
    worst = data["sets"]["full"]["worst"]
    assert (worst["ac1"]["passed"], worst["ac1"]["total"]) == (1, 3)  # lowest: run 3
    assert (worst["ac2"]["passed"], worst["ac2"]["total"]) == (1, 2)  # lowest: run 2
    assert (worst["wrong_escalation"]["passed"], worst["wrong_escalation"]["total"]) == (2, 3)  # highest: run 3
    assert (worst["both_cited"]["passed"], worst["both_cited"]["total"]) == (0, 1)
    assert worst["per_category"]["scope"]["passed"] == 1  # run 2
    assert worst["ac1_meets_target"] is False and worst["ac2_meets_target"] is False
    assert [r["ac1"]["passed"] for r in data["sets"]["full"]["per_run"]] == [2, 3, 1]


def test_service_error_never_counts_for_ac2(tickets):
    runs = [run_file(n) for n in (1, 2, 3)]
    runs[1]["tickets"][3] = row("T-004", "escalated", reason="service_error")
    assert aggregate(tickets, runs, SHA)["sets"]["full"]["worst"]["ac2"]["passed"] == 1


def test_unstable_means_status_or_pass_differs_not_wording(tickets):
    runs = [
        run_file(1),
        run_file(2, changed(**{
            "T-001": row("T-001", cited=("KB-020",)),  # same status, AC fails: unstable
            "T-003": row("T-003", cited=("KB-020",), answer="other words"),  # wording only: stable
            "T-005": row("T-005", "escalated", reason="out_of_scope"),  # other reason, still passes: stable
        })),
        run_file(3, changed(**{"T-004": row("T-004", cited=("KB-001",))})),  # status differs: unstable
    ]
    data = aggregate(tickets, runs, SHA)
    full = data["sets"]["full"]
    assert full["unstable"] == ["T-001", "T-004"]
    assert full["tickets_passed_in_all_runs"] == 3
    assert full["failed_in_some_run"] == ["T-001", "T-004"]
    t1 = next(t for t in data["tickets"] if t["ticket_id"] == "T-001")
    assert [v["pass"] for v in t1["runs"]] == [True, False, True]
    # The split follows the ticket number: T-001, T-003, T-005 calibrate.
    assert data["sets"]["calibration"]["unstable"] == ["T-001"]
    assert data["sets"]["holdout"]["unstable"] == ["T-004"]


def test_stable_runs_have_no_unstable_tickets(tickets):
    data = aggregate(tickets, [run_file(n) for n in (1, 2, 3)], SHA)
    assert data["sets"]["full"]["unstable"] == [] and data["sets"]["full"]["tickets_passed_in_all_runs"] == 5


def test_any_match_tickets_are_reported_separately(make_ticket):
    tickets = [make_ticket("T-101", ids=("KB-005", "KB-006"), match="any"), make_ticket("T-102", expected="escalate")]
    rows = {"T-101": row("T-101", cited=("KB-006",)), "T-102": row("T-102", "escalated", reason="out_of_scope")}
    data = aggregate(tickets, [run_file(n, rows) for n in (1, 2, 3)], SHA)
    full = data["sets"]["full"]
    assert full["worst"]["ac1"]["passed"] == 1
    assert full["worst"]["both_cited"]["total"] == 0  # excluded (clarification 2)
    assert full["per_run"][0]["any_match_tickets"] == [{"ticket_id": "T-101", "ac1_pass": True}]


def test_usage_totals(tickets):
    data = aggregate(tickets, [run_file(n) for n in (1, 2, 3)], SHA)
    assert data["usage_total"]["input_tokens"] == 6000 and data["usage_total"]["output_tokens"] == 600
    assert data["usage_total"]["malformed_outputs"] == 3
    assert data["usage_total"]["cost_usd"] == pytest.approx((6000 * 1.0 + 600 * 5.0) / 1e6)
    md = aggregate_markdown({**data})
    assert "Malformed model outputs: 3." in md and "slightly underestimated" in md


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda runs: runs[2].update(run=2), "runs 1, 2 and 3 once each"),
        (lambda runs: runs[1].update(model_id="other"), "model_id"),
        (lambda runs: runs[1].update(code_trees={"query": "q2", "ingestion": "i1"}), "code_trees"),
        (lambda runs: runs[0].update(system_prompt_sha256="x"), "system_prompt_sha256"),
        (lambda runs: runs[2].update(temperature=1), "temperature"),
        (lambda runs: [r.update(ticket_file_sha256="b" * 64) for r in runs], "different ticket file"),
        (lambda runs: runs[0]["tickets"].pop(), "exactly the 5 tickets"),
        (lambda runs: [r.pop("kb_version") for r in runs], "kb_version"),
    ],
)
def test_aggregate_refuses_runs_that_do_not_fit(tickets, change, message):
    runs = [run_file(n) for n in (1, 2, 3)]
    change(runs)
    with pytest.raises(EvalError, match=message):
        aggregate(tickets, runs, SHA)


@pytest.mark.parametrize(
    "over, message",
    [({"valid": False}, "invalid"), ({"kind": "part-a"}, "not a Part B run"),
     ({"threshold": 0.7}, "threshold"), ({"run": 4}, "run number")],
)
def test_load_part_b_refuses(tmp_path, over, message):
    path = tmp_path / "run.json"
    path.write_text(json.dumps(run_file(1, **over)))
    with pytest.raises(EvalError, match=message):
        load_part_b(path)


def test_aggregate_command(tmp_path, tickets, capsys):
    ticket_file = tmp_path / "tickets.jsonl"
    ticket_file.write_text("".join(
        json.dumps({"ticket_id": t.ticket_id, "question": t.question, "expected": t.expected,
                    "expected_article_ids": list(t.expected_article_ids), "category": t.category}) + "\n"
        for t in tickets), encoding="utf-8")
    from evals.eval_tickets import file_sha256

    paths = []
    for n in (1, 2, 3):
        p = tmp_path / f"run{n}.json"
        p.write_text(json.dumps(run_file(n, ticket_file_sha256=file_sha256(ticket_file))))
        paths.append(str(p))
    out = tmp_path / "reports"
    argv = ["aggregate", "--runs", *paths, "--date", "2026-10-18", "--reports-dir", str(out), "--tickets", str(ticket_file)]
    assert run_eval.main(argv) == 0
    md = (out / "2026-10-18-part-b-aggregate.md").read_text(encoding="utf-8")
    assert "## Worst of 3" in md and "## Unstable tickets (clarification 4)" in md
    assert "Passed in all 3 runs" in md and "## Escalate tickets to watch" in md
    data = json.loads((out / "2026-10-18-part-b-aggregate.json").read_text(encoding="utf-8"))
    assert [f["file"] for f in data["run_files"]] == paths
    assert run_eval.main(argv) == 1  # no silent overwrite
    assert run_eval.main(["aggregate", "--runs", paths[0], paths[0], paths[1], "--reports-dir", str(out)]) == 1
    assert "3 different Part B run files" in capsys.readouterr().err
