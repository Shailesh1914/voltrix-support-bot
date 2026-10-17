"""Part C: threshold sweep simulated from Part B results (spec 05).

No model calls. Why the simulation matches the real flow (spec 02):
- the unknown-fault-code check (step 4) comes before the retrieval check
  (step 5a), so a ticket it stopped stays escalated at every threshold;
- the retrieval check depends only on the top similarity score, which is
  deterministic (spec 03, contract test 5) and recorded from the flow's
  own search() call;
- every other ticket gets exactly the model call Part B made at -1.0.
The model itself is not guaranteed to repeat at temperature 0; that is
what the 3 runs and the confirmation run are for.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from evals.eval_recorders import EvalError
from evals.eval_scoring import (
    AC1_TARGET_PCT,
    AC2_TARGET_PCT,
    ESCALATED,
    LOW_SIMILARITY,
    SERVICE_ERROR,
    Outcome,
    headline,
    passes,
    worst_rate,
)
from evals.eval_tickets import Ticket

# 0.50 to 0.90 in steps of 0.01, rounded so that no value drifts.
THRESHOLDS = tuple(round(0.50 + 0.01 * i, 2) for i in range(41))

PART_B_KIND = "part-b"
PART_B_THRESHOLD = -1.0


@dataclass(frozen=True)
class RunResult:
    """One ticket in one Part B run."""

    top_score: float
    outcome: Outcome


def simulate(result: RunResult, threshold: float) -> Outcome:
    """The outcome the real flow would give at this threshold."""
    if not result.outcome.model_called and result.outcome.status == ESCALATED:
        # Stopped before the retrieval check (spec 02 step 4).
        return result.outcome
    if result.top_score < threshold:
        return Outcome(status=ESCALATED, escalation_reason=LOW_SIMILARITY, model_called=False)
    return result.outcome


def check_run(run: dict[str, RunResult], tickets: list[Ticket]) -> None:
    missing = [t.ticket_id for t in tickets if t.ticket_id not in run]
    if missing:
        raise EvalError(f"run has no result for {', '.join(missing)}")
    errors = [tid for tid, r in run.items() if r.outcome.escalation_reason == SERVICE_ERROR]
    if errors:
        raise EvalError(f"run is invalid (service_error on {', '.join(sorted(errors))}); re-run it")


def sweep(tickets: list[Ticket], runs: list[dict[str, RunResult]], thresholds=THRESHOLDS) -> list[dict]:
    """One row per threshold: each run's AC1, AC2 and wrong-escalation rate,
    the worst of the runs, and whether the worst values meet the targets.
    Pass the calibration tickets: only they may choose the threshold."""
    if not runs:
        raise EvalError("the sweep needs at least one Part B run")
    for run in runs:
        check_run(run, tickets)
    rows = []
    for t in thresholds:
        simulated = [{tid: simulate(r, t) for tid, r in run.items()} for run in runs]
        per_run = [headline(tickets, outcomes) for outcomes in simulated]
        worst = {
            "ac1": worst_rate([m["ac1"] for m in per_run]),
            "ac2": worst_rate([m["ac2"] for m in per_run]),
            # Not a gate. For this metric higher is worse.
            "wrong_escalation": worst_rate([m["wrong_escalation"] for m in per_run], higher_is_better=False),
        }
        passed_all = sum(all(passes(tk, outcomes[tk.ticket_id]) for outcomes in simulated) for tk in tickets)
        rows.append(
            {
                "threshold": t,
                "runs": [{name: rate.to_dict() for name, rate in m.items()} for m in per_run],
                "worst": {name: rate.to_dict() for name, rate in worst.items()},
                "ac1_meets_target": worst["ac1"].meets(AC1_TARGET_PCT),
                "ac2_meets_target": worst["ac2"].meets(AC2_TARGET_PCT),
                "meets_targets": worst["ac1"].meets(AC1_TARGET_PCT) and worst["ac2"].meets(AC2_TARGET_PCT),
                "tickets_passed_in_all_runs": passed_all,
            }
        )
    return rows


def thresholds_meeting_targets(rows: list[dict]) -> list[float]:
    return [row["threshold"] for row in rows if row["meets_targets"]]


# --- Reading Part B run files ----------------------------------------------------


def outcome_from_record(record: dict) -> Outcome:
    return Outcome(
        status=record["status"],
        escalation_reason=record.get("escalation_reason", ""),
        cited_article_ids=tuple(c["article_id"] for c in record.get("citations", [])),
        failed_check=record.get("failed_check", ""),
        model_called=record["model_called"],
    )


def run_from_json(data: dict, source: str = "run file") -> dict[str, RunResult]:
    """A Part B run file as RunResults; refuses anything else."""
    if data.get("kind") != PART_B_KIND:
        raise EvalError(f"{source} is not a Part B run (kind={data.get('kind')!r})")
    if data.get("threshold") != PART_B_THRESHOLD:
        raise EvalError(f"{source} was not run at threshold {PART_B_THRESHOLD}")
    if data.get("valid") is not True:
        raise EvalError(f"{source} is marked invalid; re-run it")
    try:
        return {
            rec["ticket_id"]: RunResult(float(rec["top_score"]), outcome_from_record(rec))
            for rec in data["tickets"]
        }
    except (KeyError, TypeError, ValueError) as e:
        raise EvalError(f"{source} has a malformed ticket record ({e!r})") from None


def load_run(path: Path | str) -> dict[str, RunResult]:
    return run_from_json(json.loads(Path(path).read_text(encoding="utf-8")), str(path))
