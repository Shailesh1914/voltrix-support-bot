"""Aggregate of the 3 Part B runs (spec 05, Part B and clarifications 1, 2, 4).

No model calls. For each set (calibration, holdout, full), at threshold -1.0:
- each metric per run, and its WORST value (clarification 1): the lowest
  for success rates (AC1, AC2, both-articles-cited, per-category pass
  rates), the highest for the wrong-escalation rate. Each metric's worst
  value may come from a different run;
- unstable tickets: status or AC pass/fail differs between runs
  (clarification 4); different answer wording alone does not count;
- the number of tickets that passed in all 3 runs (not a gate).
"""

import json
from pathlib import Path

from evals.eval_part_b import RUN_NUMBERS, cost_usd
from evals.eval_recorders import EvalError
from evals.eval_scoring import AC1_TARGET_PCT, AC2_TARGET_PCT, Rate, passes, score, worst_rate
from evals.eval_sweep import PART_B_KIND, PART_B_THRESHOLD, outcome_from_record
from evals.eval_tickets import SETS, Ticket, select

# Every run must have been made with the same bot on the same tickets, and
# belong to the same labelled set of runs. code_trees covers query/,
# ingestion/ and evals/*.py. A missing value refuses too, so runs made
# before labels existed (the old run 1) are never combined with new ones.
MUST_MATCH = (
    "label", "code_trees", "model_id", "temperature", "system_prompt_sha256", "ticket_file_sha256", "kb_version",
)

# Escalate tickets only the model can catch (notes/step9-retrieval-review.md,
# 2026-10-17). Highlighted in the report; scored like every other ticket.
WATCH_TICKETS = ("T-044", "T-049", "T-058", "T-109")

SUCCESS_RATES = ("ac1", "ac2", "both_cited")
ERROR_RATES = ("wrong_escalation",)


def load_part_b(path: Path | str) -> dict:
    """A valid Part B run file; refuses anything else."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("kind") != PART_B_KIND:
        raise EvalError(f"{path} is not a Part B run (kind={data.get('kind')!r})")
    if data.get("threshold") != PART_B_THRESHOLD:
        raise EvalError(f"{path} was not run at threshold {PART_B_THRESHOLD}")
    if data.get("valid") is not True:
        raise EvalError(f"{path} is marked invalid; re-run it")
    if data.get("run") not in RUN_NUMBERS:
        raise EvalError(f"{path} has no run number 1, 2 or 3")
    return data


def check_runs(runs: list[dict], tickets: list[Ticket], ticket_file_sha256: str) -> None:
    if sorted(r["run"] for r in runs) != list(RUN_NUMBERS):
        raise EvalError(f"the aggregate needs runs 1, 2 and 3 once each, got {sorted(r['run'] for r in runs)}")
    for name in MUST_MATCH:
        values = [json.dumps(r.get(name), sort_keys=True) for r in runs]
        if len(set(values)) != 1 or runs[0].get(name) is None:
            raise EvalError(f"the runs differ in {name} (or it is missing); they are not comparable")
    if runs[0]["ticket_file_sha256"] != ticket_file_sha256:
        raise EvalError("the runs were made on a different ticket file")
    expected = sorted(t.ticket_id for t in tickets)
    for r in runs:
        if sorted(row["ticket_id"] for row in r["tickets"]) != expected:
            raise EvalError(f"run {r['run']} does not cover exactly the {len(expected)} tickets")


def rate(d: dict) -> Rate:
    return Rate(d["passed"], d["total"])


def worst_summary(per_run: list[dict]) -> dict:
    """Worst value of each metric across the runs (clarification 1)."""
    worst = {name: worst_rate([rate(s[name]) for s in per_run]).to_dict() for name in SUCCESS_RATES}
    worst.update(
        {name: worst_rate([rate(s[name]) for s in per_run], higher_is_better=False).to_dict() for name in ERROR_RATES}
    )
    categories = sorted({c for s in per_run for c in s["per_category"]})
    worst["per_category"] = {
        c: worst_rate([rate(s["per_category"][c]) for s in per_run]).to_dict() for c in categories
    }
    worst["ac1_meets_target"] = rate(worst["ac1"]).meets(AC1_TARGET_PCT)
    worst["ac2_meets_target"] = rate(worst["ac2"]).meets(AC2_TARGET_PCT)
    return worst


def ticket_view(row: dict) -> dict:
    return {
        "status": row["status"],
        "escalation_reason": row["escalation_reason"],
        "failed_check": row["failed_check"],
        "cited": [c["article_id"] for c in row["citations"]],
        "pass": None,  # filled by aggregate()
    }


def aggregate(tickets: list[Ticket], runs: list[dict], ticket_file_sha256: str) -> dict:
    check_runs(runs, tickets, ticket_file_sha256)
    runs = sorted(runs, key=lambda r: r["run"])
    rows = [{row["ticket_id"]: row for row in r["tickets"]} for r in runs]
    outcomes = [{tid: outcome_from_record(row) for tid, row in by_id.items()} for by_id in rows]

    per_ticket = []
    for t in tickets:
        views = []
        for by_id, outs in zip(rows, outcomes):
            v = ticket_view(by_id[t.ticket_id])
            v["pass"] = passes(t, outs[t.ticket_id])
            views.append(v)
        per_ticket.append(
            {
                "ticket_id": t.ticket_id,
                "split": t.split,
                "expected": t.expected,
                "category": t.category,
                "expected_article_ids": list(t.expected_article_ids),
                "top_score": rows[0][t.ticket_id]["top_score"],
                "runs": views,
                # Clarification 4: status or AC pass/fail differs.
                "unstable": len({v["status"] for v in views}) > 1 or len({v["pass"] for v in views}) > 1,
                "passed_all_runs": all(v["pass"] for v in views),
            }
        )
    by_id = {p["ticket_id"]: p for p in per_ticket}

    sets = {}
    for name in SETS:
        chosen = select(tickets, name)
        per_run = [score(chosen, outs) for outs in outcomes]
        sets[name] = {
            "n_tickets": len(chosen),
            "per_run": per_run,
            "worst": worst_summary(per_run),
            "tickets_passed_in_all_runs": sum(by_id[t.ticket_id]["passed_all_runs"] for t in chosen),
            "failed_in_some_run": [t.ticket_id for t in chosen if not by_id[t.ticket_id]["passed_all_runs"]],
            "unstable": [t.ticket_id for t in chosen if by_id[t.ticket_id]["unstable"]],
        }

    usage = [
        {
            "run": r["run"],
            "model_calls": r["model_calls"],
            "input_tokens": r["tokens"]["input"],
            "output_tokens": r["tokens"]["output"],
            "malformed_outputs": r["malformed_outputs"],
            "cost_usd": r["cost_usd"],
        }
        for r in runs
    ]
    total_in = sum(u["input_tokens"] for u in usage)
    total_out = sum(u["output_tokens"] for u in usage)
    return {
        "kind": "part-b-aggregate",
        "threshold": PART_B_THRESHOLD,
        **{name: runs[0][name] for name in MUST_MATCH},
        "runs": [{"run": r["run"], "date": r.get("date"), "git_commit": r.get("git_commit")} for r in runs],
        "sets": sets,
        "usage": usage,
        "usage_total": {
            "model_calls": sum(u["model_calls"] for u in usage),
            "input_tokens": total_in,
            "output_tokens": total_out,
            "malformed_outputs": sum(u["malformed_outputs"] for u in usage),
            "cost_usd": cost_usd(total_in, total_out),
        },
        "watch_tickets": [by_id[tid] for tid in WATCH_TICKETS if tid in by_id],
        "tickets": per_ticket,
    }
