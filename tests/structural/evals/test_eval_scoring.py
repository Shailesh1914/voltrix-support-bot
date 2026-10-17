"""Scoring as spec 05 and spec 02 define it."""

import pytest

from evals.eval_scoring import (
    Rate,
    ac1_pass,
    ac2_pass,
    both_cited,
    counts_for_both_cited,
    distribution,
    headline,
    retrieval_row,
    retrieval_summary,
    score,
    worst_rate,
    wrongly_escalated,
)

# --- AC1 -------------------------------------------------------------------------


def test_ac1_answered_and_cites_an_expected_article(make_ticket, answered):
    assert ac1_pass(make_ticket(ids=("KB-001",)), answered("KB-001"))


def test_ac1_extra_citations_are_allowed(make_ticket, answered):
    assert ac1_pass(make_ticket(ids=("KB-001",)), answered("KB-020", "KB-001"))


def test_ac1_fails_on_wrong_article(make_ticket, answered):
    assert not ac1_pass(make_ticket(ids=("KB-001",)), answered("KB-020"))


def test_ac1_fails_without_citations(make_ticket, answered):
    assert not ac1_pass(make_ticket(ids=("KB-001",)), answered())


@pytest.mark.parametrize("reason", ["low_similarity", "insufficient_context", "out_of_scope", "service_error"])
def test_ac1_fails_when_escalated(make_ticket, escalated, reason):
    assert not ac1_pass(make_ticket(ids=("KB-001",)), escalated(reason))


def test_ac1_two_article_ticket_needs_only_one(make_ticket, answered):
    assert ac1_pass(make_ticket(ids=("KB-019", "KB-022")), answered("KB-022"))


# --- AC2 -------------------------------------------------------------------------


@pytest.mark.parametrize("reason", ["low_similarity", "insufficient_context", "out_of_scope"])
def test_ac2_any_reason_counts(make_ticket, escalated, reason):
    assert ac2_pass(make_ticket(expected="escalate"), escalated(reason))


def test_ac2_service_error_never_counts(make_ticket, escalated):
    assert not ac2_pass(make_ticket(expected="escalate"), escalated("service_error"))


def test_ac2_fails_when_answered(make_ticket, answered):
    assert not ac2_pass(make_ticket(expected="escalate"), answered("KB-001"))


# --- Metrics -----------------------------------------------------------------------


def test_both_cited(make_ticket, answered, escalated):
    t = make_ticket(ids=("KB-019", "KB-022"))
    assert counts_for_both_cited(t)
    assert both_cited(t, answered("KB-022", "KB-019"))
    assert not both_cited(t, answered("KB-019"))
    assert not both_cited(t, escalated())


def test_any_match_ticket_is_excluded_from_both_cited(make_ticket):
    assert not counts_for_both_cited(make_ticket(ids=("KB-019", "KB-022"), match="any"))
    assert not counts_for_both_cited(make_ticket(ids=("KB-001",)))
    assert not counts_for_both_cited(make_ticket(expected="escalate"))


def test_wrong_escalation(make_ticket, answered, escalated):
    assert wrongly_escalated(make_ticket(), escalated("low_similarity"))
    assert not wrongly_escalated(make_ticket(), answered("KB-020"))
    assert not wrongly_escalated(make_ticket(expected="escalate"), escalated())


@pytest.mark.parametrize(
    "passed, total, target, meets",
    [
        (17, 20, 85, True),  # exactly 85%
        (16, 20, 85, False),
        (21, 22, 95, True),  # spec 02: 1 miss of 22 = 95.5%
        (10, 11, 95, False),  # clarification 6: calibration needs 11/11
        (11, 11, 95, True),
        (0, 0, 85, False),
    ],
)
def test_rate_meets_target_exactly(passed, total, target, meets):
    assert Rate(passed, total).meets(target) is meets


def test_worst_rate():
    rates = [Rate(20, 24), Rate(18, 24), Rate(22, 24)]
    assert worst_rate(rates) == Rate(18, 24)
    assert worst_rate(rates, higher_is_better=False) == Rate(22, 24)


def test_score_full_metrics(make_ticket, answered, escalated):
    tickets = [
        make_ticket("T-001", ids=("KB-001",), category="fault"),
        make_ticket("T-002", ids=("KB-020",), category="parameters"),
        make_ticket("T-003", ids=("KB-019", "KB-022"), category="installation"),
        make_ticket("T-004", ids=("KB-019", "KB-022"), category="installation", match="any"),
        make_ticket("T-005", expected="escalate", category="out_of_scope"),
        make_ticket("T-006", expected="escalate", category="fault"),
    ]
    outcomes = {
        "T-001": answered("KB-001"),
        "T-002": escalated("insufficient_context", failed_check="grounding"),
        "T-003": answered("KB-019"),
        "T-004": answered("KB-022"),
        "T-005": escalated("out_of_scope"),
        "T-006": answered("KB-001"),
    }
    s = score(tickets, outcomes)
    assert s["ac1"] == {"passed": 3, "total": 4, "rate": 0.75}
    assert s["ac1_meets_target"] is False
    assert s["ac2"] == {"passed": 1, "total": 2, "rate": 0.5}
    assert s["wrong_escalation"] == {"passed": 1, "total": 4, "rate": 0.25}
    assert s["both_cited"] == {"passed": 0, "total": 1, "rate": 0.0}
    assert s["any_match_tickets"] == [{"ticket_id": "T-004", "ac1_pass": True}]
    assert s["per_category"]["installation"] == {"passed": 2, "total": 2, "rate": 1.0}
    assert s["per_category"]["fault"] == {"passed": 1, "total": 2, "rate": 0.5}
    assert s["failed_check_counts"] == {"grounding": 1}
    assert s["escalation_reason_counts"] == {"insufficient_context": 1, "out_of_scope": 1}


def test_score_needs_every_outcome(make_ticket, answered):
    with pytest.raises(ValueError, match="T-002"):
        headline([make_ticket("T-001"), make_ticket("T-002")], {"T-001": answered("KB-001")})


# --- Part A ----------------------------------------------------------------------------


def test_retrieval_row(make_ticket):
    assert retrieval_row(make_ticket(ids=("KB-001",)), ["KB-020", "KB-001"]) == {"recall_hit": True, "both_hit": None}
    assert retrieval_row(make_ticket(ids=("KB-001",)), ["KB-020"]) == {"recall_hit": False, "both_hit": None}
    two = make_ticket(ids=("KB-019", "KB-022"))
    assert retrieval_row(two, ["KB-019", "KB-019"]) == {"recall_hit": True, "both_hit": False}
    assert retrieval_row(two, ["KB-022", "KB-019"]) == {"recall_hit": True, "both_hit": True}
    any_match = make_ticket(ids=("KB-019", "KB-022"), match="any")
    assert retrieval_row(any_match, ["KB-019"]) == {"recall_hit": True, "both_hit": None}
    assert retrieval_row(make_ticket(expected="escalate"), ["KB-001"]) == {"recall_hit": None, "both_hit": None}


def test_distribution():
    d = distribution([0.9, 0.5, 0.7, 0.6, 0.8])
    assert (d["n"], d["min"], d["median"], d["max"]) == (5, 0.5, 0.7, 0.9)
    assert d["q1"] == pytest.approx(0.6) and d["q3"] == pytest.approx(0.8)
    assert d["mean"] == pytest.approx(0.7)
    assert distribution([0.4])["median"] == 0.4
    assert distribution([]) == {"n": 0}


def test_retrieval_summary(make_ticket):
    tickets = [
        make_ticket("T-001", ids=("KB-001",)),
        make_ticket("T-002", ids=("KB-019", "KB-022")),
        make_ticket("T-003", expected="escalate"),
        make_ticket("T-004", expected="escalate"),
    ]
    rows = {
        "T-001": {"top_score": 0.80, "recall_hit": True, "both_hit": None, "model_called": True},
        "T-002": {"top_score": 0.62, "recall_hit": True, "both_hit": False, "model_called": True},
        "T-003": {"top_score": 0.65, "recall_hit": None, "both_hit": None, "model_called": True},
        "T-004": {"top_score": 0.90, "recall_hit": None, "both_hit": None, "model_called": False},
    }
    s = retrieval_summary(tickets, rows)
    assert s["recall"]["passed"] == 2 and s["recall"]["total"] == 2
    assert s["both_recall"] == {"passed": 0, "total": 1, "rate": 0.0}
    assert s["escalate_scores"]["n"] == 2
    # T-004 escalates at every threshold, so it does not count as overlap.
    assert s["escalate_scores_reaching_threshold_check"]["n"] == 1
    assert s["escalate_stopped_by_fault_code_check"] == ["T-004"]
    assert s["overlap"]["separated"] is False
    assert s["overlap"]["highest_escalate_score"] == 0.65
    assert s["overlap"]["answer_tickets_at_or_below_highest_escalate"] == 1
    assert s["overlap"]["escalate_tickets_at_or_above_lowest_answer"] == 1
