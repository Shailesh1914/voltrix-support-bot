"""Part C: the threshold sweep simulated from Part B results."""

import pytest

from evals.eval_recorders import EvalError
from evals.eval_sweep import (
    THRESHOLDS,
    check_run,
    run_from_json,
    simulate,
    sweep,
    thresholds_meeting_targets,
)


def test_thresholds_are_exact_hundredths_from_050_to_090():
    assert len(THRESHOLDS) == 41
    assert THRESHOLDS[0] == 0.50 and THRESHOLDS[-1] == 0.90
    assert 0.57 in THRESHOLDS and 0.83 in THRESHOLDS
    assert all(round(t, 2) == t for t in THRESHOLDS)
    assert list(THRESHOLDS) == sorted(set(THRESHOLDS))


def test_score_below_threshold_escalates_low_similarity(run_result, answered):
    out = simulate(run_result(0.6499, answered("KB-001")), 0.65)
    assert (out.status, out.escalation_reason, out.cited_article_ids) == ("escalated", "low_similarity", ())


def test_score_equal_to_threshold_keeps_part_b_outcome(run_result, answered):
    # Spec 02: escalate only if the score is BELOW the threshold.
    result = run_result(0.65, answered("KB-001"))
    assert simulate(result, 0.65) == result.outcome


def test_unknown_fault_code_escalation_is_kept(run_result, escalated):
    # Spec 02 step 4 comes before the retrieval check (step 5a).
    stopped = escalated("insufficient_context", model_called=False)
    assert simulate(run_result(0.30, stopped), 0.90) == stopped


def test_model_escalation_below_threshold_becomes_low_similarity(run_result, escalated):
    out = simulate(run_result(0.55, escalated("out_of_scope")), 0.60)
    assert out.escalation_reason == "low_similarity"


def scenario(make_ticket, answered, escalated, run_result):
    tickets = [
        make_ticket("T-001", ids=("KB-001",)),
        make_ticket("T-003", ids=("KB-020",)),
        make_ticket("T-005", expected="escalate"),
    ]
    run1 = {
        "T-001": run_result(0.80, answered("KB-001")),
        "T-003": run_result(0.60, answered("KB-020")),
        "T-005": run_result(0.55, answered("KB-001")),  # wrongly answered by the model
    }
    run2 = dict(run1, **{"T-003": run_result(0.60, escalated("insufficient_context"))})
    return tickets, [run1, run2]


def test_sweep_reports_worst_run_per_threshold(make_ticket, answered, escalated, run_result):
    tickets, runs = scenario(make_ticket, answered, escalated, run_result)
    rows = {r["threshold"]: r for r in sweep(tickets, runs, thresholds=(0.50, 0.56, 0.61, 0.81))}

    # t=0.50: nothing is cut. Run 2 is worse on AC1 (T-003 escalated).
    r = rows[0.50]
    assert [m["ac1"]["passed"] for m in r["runs"]] == [2, 1]
    assert r["worst"]["ac1"]["passed"] == 1
    assert r["worst"]["ac2"]["passed"] == 0
    assert r["worst"]["wrong_escalation"]["passed"] == 1  # highest is worst
    assert r["tickets_passed_in_all_runs"] == 1
    assert r["meets_targets"] is False

    # t=0.56: T-005 (0.55) now escalates, in both runs.
    r = rows[0.56]
    assert r["worst"]["ac2"] == {"passed": 1, "total": 1, "rate": 1.0}
    assert r["ac2_meets_target"] is True
    assert r["worst"]["ac1"]["passed"] == 1
    assert r["meets_targets"] is False

    # t=0.61: T-003 (0.60) escalates in both runs.
    assert rows[0.61]["worst"]["ac1"]["passed"] == 1
    assert [m["ac1"]["passed"] for m in rows[0.61]["runs"]] == [1, 1]

    # t=0.81: every answer ticket is cut.
    assert rows[0.81]["worst"]["ac1"]["passed"] == 0
    assert rows[0.81]["worst"]["wrong_escalation"] == {"passed": 2, "total": 2, "rate": 1.0}


def test_thresholds_meeting_targets(make_ticket, answered, run_result):
    tickets = [make_ticket("T-001", ids=("KB-001",)), make_ticket("T-003", expected="escalate")]
    run = {"T-001": run_result(0.80, answered("KB-001")), "T-003": run_result(0.70, answered("KB-001"))}
    rows = sweep(tickets, [run, run, run])
    # T-003 must be cut (t > 0.70) and T-001 kept (t <= 0.80).
    assert thresholds_meeting_targets(rows) == [t for t in THRESHOLDS if 0.70 < t <= 0.80]


def test_service_error_run_is_refused(make_ticket, answered, escalated, run_result):
    tickets = [make_ticket("T-001")]
    with pytest.raises(EvalError, match="invalid"):
        check_run({"T-001": run_result(0.8, escalated("service_error"))}, tickets)
    with pytest.raises(EvalError, match="invalid"):
        sweep(tickets, [{"T-001": run_result(0.8, escalated("service_error"))}])


def test_run_missing_a_ticket_is_refused(make_ticket, answered, run_result):
    with pytest.raises(EvalError, match="T-003"):
        sweep([make_ticket("T-001"), make_ticket("T-003")], [{"T-001": run_result(0.8, answered("KB-001"))}])


def test_sweep_needs_runs(make_ticket):
    with pytest.raises(EvalError):
        sweep([make_ticket()], [])


def part_b_json(**overrides):
    data = {
        "kind": "part-b",
        "threshold": -1.0,
        "valid": True,
        "tickets": [
            {
                "ticket_id": "T-001",
                "top_score": 0.71,
                "status": "answered",
                "escalation_reason": "",
                "citations": [{"article_id": "KB-001", "title": "E-01"}],
                "failed_check": "",
                "model_called": True,
            },
            {
                "ticket_id": "T-053",
                "top_score": 0.52,
                "status": "escalated",
                "escalation_reason": "insufficient_context",
                "citations": [],
                "failed_check": "",
                "model_called": False,
            },
        ],
    }
    data.update(overrides)
    return data


def test_run_from_json():
    run = run_from_json(part_b_json())
    assert run["T-001"].top_score == 0.71
    assert run["T-001"].outcome.cited_article_ids == ("KB-001",)
    assert run["T-053"].outcome.model_called is False


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"kind": "part-a"}, "not a Part B run"),
        ({"threshold": 0.7}, "threshold"),
        ({"valid": False}, "invalid"),
        ({"tickets": [{"ticket_id": "T-001"}]}, "malformed"),
    ],
)
def test_run_from_json_refuses(overrides, message):
    with pytest.raises(EvalError, match=message):
        run_from_json(part_b_json(**overrides))
