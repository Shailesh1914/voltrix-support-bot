"""Scoring exactly as specs 02 and 05 define it, never as the bot's code does.

Pure functions of recorded results plus tickets: no model, no retrieval.
"""

import statistics
from collections import Counter
from dataclasses import dataclass

from evals.eval_tickets import Ticket

# Spec 02 acceptance criteria 1 and 2, as whole percentages so that the
# comparison is exact integer arithmetic.
AC1_TARGET_PCT = 85
AC2_TARGET_PCT = 95

ANSWERED = "answered"
ESCALATED = "escalated"
SERVICE_ERROR = "service_error"
LOW_SIMILARITY = "low_similarity"


@dataclass(frozen=True)
class Outcome:
    """What the flow did with one ticket (the parts that are scored)."""

    status: str  # "answered" | "escalated"
    escalation_reason: str = ""
    cited_article_ids: tuple[str, ...] = ()
    failed_check: str = ""
    # False when the flow escalated before the model call (unknown fault
    # code, spec 02 step 4). Needed by the sweep, never scored.
    model_called: bool = True


@dataclass(frozen=True)
class Rate:
    passed: int
    total: int

    @property
    def rate(self) -> float | None:
        return self.passed / self.total if self.total else None

    def meets(self, target_pct: int) -> bool:
        return self.total > 0 and self.passed * 100 >= target_pct * self.total

    def to_dict(self) -> dict:
        return {"passed": self.passed, "total": self.total, "rate": self.rate}


def rate_of(flags) -> Rate:
    flags = list(flags)
    return Rate(sum(1 for f in flags if f), len(flags))


def worst_rate(rates: list[Rate], higher_is_better: bool = True) -> Rate:
    """The worst of several runs' values (spec 05 clarification 1)."""
    if not rates:
        raise ValueError("no rates to compare")
    key = (lambda r: r.rate if r.rate is not None else 0.0)
    return min(rates, key=key) if higher_is_better else max(rates, key=key)


# --- Per-ticket criteria (spec 05, "Scoring") ---------------------------------


def ac1_pass(ticket: Ticket, outcome: Outcome) -> bool:
    """Answered AND cites at least one expected article."""
    return (
        outcome.status == ANSWERED
        and bool(set(outcome.cited_article_ids) & set(ticket.expected_article_ids))
    )


def ac2_pass(ticket: Ticket, outcome: Outcome) -> bool:
    """Escalated with any reason except service_error."""
    return outcome.status == ESCALATED and outcome.escalation_reason != SERVICE_ERROR


def passes(ticket: Ticket, outcome: Outcome) -> bool:
    return ac1_pass(ticket, outcome) if ticket.expected == "answer" else ac2_pass(ticket, outcome)


def counts_for_both_cited(ticket: Ticket) -> bool:
    """Two-article tickets, except article_match "any" (clarification 2)."""
    return ticket.expected == "answer" and ticket.is_two_article and ticket.article_match == "all"


def both_cited(ticket: Ticket, outcome: Outcome) -> bool:
    return outcome.status == ANSWERED and set(ticket.expected_article_ids) <= set(outcome.cited_article_ids)


def wrongly_escalated(ticket: Ticket, outcome: Outcome) -> bool:
    return ticket.expected == "answer" and outcome.status == ESCALATED


# --- Metrics over a set of tickets ---------------------------------------------


def outcomes_for(tickets: list[Ticket], outcomes: dict[str, Outcome]) -> list[tuple[Ticket, Outcome]]:
    missing = [t.ticket_id for t in tickets if t.ticket_id not in outcomes]
    if missing:
        raise ValueError(f"no outcome recorded for {', '.join(missing)}")
    return [(t, outcomes[t.ticket_id]) for t in tickets]


def headline(tickets: list[Ticket], outcomes: dict[str, Outcome]) -> dict[str, Rate]:
    """AC1, AC2 and the wrong-escalation rate (the sweep needs only these)."""
    pairs = outcomes_for(tickets, outcomes)
    answer = [(t, o) for t, o in pairs if t.expected == "answer"]
    escalate = [(t, o) for t, o in pairs if t.expected == "escalate"]
    return {
        "ac1": rate_of(ac1_pass(t, o) for t, o in answer),
        "ac2": rate_of(ac2_pass(t, o) for t, o in escalate),
        "wrong_escalation": rate_of(wrongly_escalated(t, o) for t, o in answer),
    }


def score(tickets: list[Ticket], outcomes: dict[str, Outcome]) -> dict:
    """All gates and metrics of spec 05 for one set of tickets."""
    pairs = outcomes_for(tickets, outcomes)
    main = headline(tickets, outcomes)
    by_category: dict[str, list[bool]] = {}
    for t, o in pairs:
        by_category.setdefault(t.category, []).append(passes(t, o))
    return {
        "n_tickets": len(pairs),
        "ac1": main["ac1"].to_dict(),
        "ac1_meets_target": main["ac1"].meets(AC1_TARGET_PCT),
        "ac2": main["ac2"].to_dict(),
        "ac2_meets_target": main["ac2"].meets(AC2_TARGET_PCT),
        "wrong_escalation": main["wrong_escalation"].to_dict(),
        "both_cited": rate_of(both_cited(t, o) for t, o in pairs if counts_for_both_cited(t)).to_dict(),
        "any_match_tickets": [
            {"ticket_id": t.ticket_id, "ac1_pass": ac1_pass(t, o)}
            for t, o in pairs
            if t.expected == "answer" and t.article_match == "any"
        ],
        "per_category": {c: rate_of(f).to_dict() for c, f in sorted(by_category.items())},
        "failed_check_counts": dict(sorted(Counter(o.failed_check for _, o in pairs if o.failed_check).items())),
        "escalation_reason_counts": dict(
            sorted(Counter(o.escalation_reason for _, o in pairs if o.status == ESCALATED).items())
        ),
    }


# --- Part A: retrieval (no model) ------------------------------------------------


def retrieval_row(ticket: Ticket, top_article_ids: list[str]) -> dict:
    """Recall for one ticket from the article_ids of its top 5 chunks."""
    found = set(top_article_ids)
    expected = set(ticket.expected_article_ids)
    row = {"recall_hit": None, "both_hit": None}
    if ticket.expected == "answer":
        row["recall_hit"] = bool(found & expected)
        if counts_for_both_cited(ticket):
            row["both_hit"] = expected <= found
    return row


def distribution(scores: list[float]) -> dict:
    scores = sorted(scores)
    if not scores:
        return {"n": 0}
    if len(scores) == 1:
        q1 = median = q3 = scores[0]
    else:
        q1, median, q3 = statistics.quantiles(scores, n=4, method="inclusive")
    return {
        "n": len(scores),
        "min": scores[0],
        "q1": q1,
        "median": median,
        "q3": q3,
        "max": scores[-1],
        "mean": statistics.fmean(scores),
    }


def retrieval_summary(tickets: list[Ticket], rows: dict[str, dict]) -> dict:
    """Part A metrics for one set. rows[ticket_id] holds top_score,
    recall_hit, both_hit and model_called."""
    pairs = [(t, rows[t.ticket_id]) for t in tickets]
    answer = [(t, r) for t, r in pairs if t.expected == "answer"]
    escalate = [(t, r) for t, r in pairs if t.expected == "escalate"]
    # Escalate tickets stopped by the unknown-fault-code check escalate at
    # every threshold; only the others depend on the score.
    escalate_reaching_check = [(t, r) for t, r in escalate if r["model_called"]]
    answer_scores = [r["top_score"] for _, r in answer]
    escalate_scores = [r["top_score"] for _, r in escalate_reaching_check]
    overlap = {}
    if answer_scores and escalate_scores:
        lowest_answer = min(answer_scores)
        highest_escalate = max(escalate_scores)
        overlap = {
            "lowest_answer_score": lowest_answer,
            "highest_escalate_score": highest_escalate,
            "separated": highest_escalate < lowest_answer,
            "answer_tickets_at_or_below_highest_escalate": sum(s <= highest_escalate for s in answer_scores),
            "escalate_tickets_at_or_above_lowest_answer": sum(s >= lowest_answer for s in escalate_scores),
        }
    return {
        "n_tickets": len(pairs),
        "recall": rate_of(r["recall_hit"] for _, r in answer).to_dict(),
        "both_recall": rate_of(r["both_hit"] for t, r in answer if counts_for_both_cited(t)).to_dict(),
        "any_match_tickets": [
            {"ticket_id": t.ticket_id, "recall_hit": r["recall_hit"]} for t, r in answer if t.article_match == "any"
        ],
        "answer_scores": distribution(answer_scores),
        "escalate_scores": distribution([r["top_score"] for _, r in escalate]),
        "escalate_scores_reaching_threshold_check": distribution(escalate_scores),
        "escalate_stopped_by_fault_code_check": [t.ticket_id for t, r in escalate if not r["model_called"]],
        "overlap": overlap,
    }
