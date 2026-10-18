"""Part C confirmation run (spec 05): "After the threshold is chosen, one
confirmation run of the real flow at that threshold checks the simulation
matched."

The threshold is the real bot's: query/config.py, read exactly as
query/ask.py reads it (bot_threshold()). There is no command-line value,
and the sweep, the run files and the report never supply one. The same
value drives the real run and the simulation it is compared with.

What is compared, per ticket and per Part B run (the 3 runs of one label):
- the real outcome at the threshold: top score, status, escalation_reason
  and AC pass/fail;
- the sweep's simulated outcome at the same threshold
  (eval_sweep.simulate() on that run's Part B result).
A ticket matches only if it agrees with ALL 3 runs, so a ticket the runs
disagree on can never be reported as a match. Answer wording and the
cited articles are recorded but only AC pass/fail is compared
(spec 05 clarification 4).

Before any money is spent, the free planning pass must show that the
simulation applies to today's bot:
- the model settings and the system prompt equal the runs';
- ingestion/ is the same tree, and in query/ only config.py differs
  (the threshold was set after the runs);
- every ticket retrieves exactly the step-d chunks and scores of the runs.
"""

from evals.eval_aggregate import check_runs
from evals.eval_part_b import TicketRetrieval, git
from evals.eval_recorders import EvalError
from evals.eval_scoring import ESCALATED, headline, passes, worst_rate
from evals.eval_sweep import RunResult, outcome_from_record, run_from_json, simulate
from evals.eval_tickets import REPO_ROOT, SETS, Ticket, select

CONFIRM_KIND = "part-c-confirm"

# Compared between the real outcome and each run's simulated outcome.
COMPARED_FIELDS = ("top_score", "status", "escalation_reason", "ac_pass")

# Settings the real generator sends that must equal the Part B runs'.
SETTINGS_MUST_MATCH = ("model_id", "temperature", "max_output_tokens", "system_prompt_sha256")

# Files in query/ that may differ from the Part B runs' query/ tree.
ALLOWED_QUERY_CHANGES = ("config.py",)


def bot_threshold() -> float:
    """The threshold the real bot runs at, read as query/ask.py reads it.
    Read when called (never cached), so nothing else can stand in for it."""
    from query import config

    try:
        return config.require_threshold(config.ESCALATION_THRESHOLD)
    except config.ConfigError as e:
        raise EvalError(f"cannot confirm: {e}") from None


def threshold_text(threshold: float) -> str:
    """0.6 -> '0.60'; more digits are kept if the value has them."""
    text = f"{threshold:.2f}"
    return text if float(text) == threshold else repr(threshold)


def confirm_name(label: str, threshold: float) -> str:
    return f"part-c-{label}-confirm-t{threshold_text(threshold)}"


# --- The Part B runs ---------------------------------------------------------------


def part_b_results(run_files: list[dict], tickets: list[Ticket], ticket_file_sha256: str
                   ) -> list[tuple[int, dict[str, RunResult]]]:
    """The 3 runs as (run number, results), after the sweep's own
    comparability check (same label, code, model, prompt, tickets, KB)."""
    check_runs(run_files, tickets, ticket_file_sha256)
    ordered = sorted(run_files, key=lambda r: r["run"])
    return [(r["run"], run_from_json(r, f"run {r['run']}")) for r in ordered]


# --- Checks before any paid call -----------------------------------------------------


def check_settings(settings: dict, run_files: list[dict]) -> None:
    for name in SETTINGS_MUST_MATCH:
        if settings.get(name) != run_files[0].get(name):
            raise EvalError(
                f"{name} is {settings.get(name)!r} now but {run_files[0].get(name)!r} in the Part B runs; "
                "the simulation does not apply to this bot"
            )


def changed_files(tree_a: str, tree_b: str) -> list[str]:
    """Paths that differ between two git trees."""
    try:
        return git(["diff", "--name-only", tree_a, tree_b], REPO_ROOT).split()
    except Exception as e:  # noqa: BLE001 - any git failure refuses
        raise EvalError(f"cannot compare code trees with git ({type(e).__name__})") from None


def check_code(run_trees: dict, head_trees: dict) -> dict:
    """ingestion/ must be identical; in query/ only ALLOWED_QUERY_CHANGES may
    differ. evals/*.py may differ (this command is new). Returns what differs."""
    for name in ("query", "ingestion"):
        if not run_trees.get(name) or not head_trees.get(name):
            raise EvalError(f"the {name}/ code tree is unknown; cannot tell whether the simulation applies")
    if head_trees["ingestion"] != run_trees["ingestion"]:
        raise EvalError("ingestion/ differs from the Part B runs; the simulation does not apply")
    query_changes = (
        [] if head_trees["query"] == run_trees["query"] else changed_files(run_trees["query"], head_trees["query"])
    )
    other = [f for f in query_changes if f not in ALLOWED_QUERY_CHANGES]
    if other:
        raise EvalError(
            f"query/ differs from the Part B runs in {', '.join(other)} (only {', '.join(ALLOWED_QUERY_CHANGES)} "
            "may differ); the simulation does not apply"
        )
    return {
        "query_files_changed_since_runs": query_changes,
        "evals_code_changed_since_runs": head_trees.get("evals/*.py") != run_trees.get("evals/*.py"),
    }


def check_retrieval(retrieval: dict[str, TicketRetrieval], run_files: list[dict]) -> None:
    """Every ticket's step-d chunks and scores (free planning pass) equal
    each Part B run's. Retrieval is deterministic (spec 03), so any
    difference means the simulation is about a different retrieval."""
    for r in run_files:
        for row in r["tickets"]:
            tid = row["ticket_id"]
            if tid not in retrieval:
                raise EvalError(f"{tid}: not in the planning pass")
            recorded = tuple((c["chunk_id"], c["article_id"], c["similarity_score"]) for c in row["retrieved_chunks"])
            if recorded != retrieval[tid].chunks:
                raise EvalError(
                    f"{tid}: retrieval differs from Part B run {r['run']} (chunks or scores); "
                    "the simulation does not apply"
                )


# --- What the sweep predicts ---------------------------------------------------------


def simulated_summary(tickets: list[Ticket], part_b: list[tuple[int, dict[str, RunResult]]], threshold: float
                      ) -> dict:
    """AC1, AC2 and wrong escalation at the threshold, per run and worst of
    the runs (spec 05 clarification 1), for each set."""
    out = {}
    for name in SETS:
        chosen = select(tickets, name)
        per_run = [
            headline(chosen, {tid: simulate(res, threshold) for tid, res in results.items()})
            for _, results in part_b
        ]
        out[name] = {
            "per_run": [{k: v.to_dict() for k, v in m.items()} for m in per_run],
            "worst": {
                "ac1": worst_rate([m["ac1"] for m in per_run]).to_dict(),
                "ac2": worst_rate([m["ac2"] for m in per_run]).to_dict(),
                "wrong_escalation": worst_rate(
                    [m["wrong_escalation"] for m in per_run], higher_is_better=False
                ).to_dict(),
            },
        }
    return out


# --- The comparison ------------------------------------------------------------------


def real_view(ticket: Ticket, row: dict) -> dict:
    return {
        "top_score": row["top_score"],
        "status": row["status"],
        "escalation_reason": row["escalation_reason"],
        # Scored here from the spec (eval_scoring), never taken on trust.
        "ac_pass": passes(ticket, outcome_from_record(row)),
        "cited": [c["article_id"] for c in row["citations"]],
        "failed_check": row["failed_check"],
    }


def simulated_view(ticket: Ticket, result: RunResult, threshold: float) -> dict:
    outcome = simulate(result, threshold)
    return {
        "top_score": result.top_score,
        "status": outcome.status,
        "escalation_reason": outcome.escalation_reason,
        "ac_pass": passes(ticket, outcome),
        "cited": list(outcome.cited_article_ids) if outcome.status != ESCALATED else [],
        "failed_check": outcome.failed_check,
    }


def compare(tickets: list[Ticket], rows: list[dict], part_b: list[tuple[int, dict[str, RunResult]]],
            threshold: float) -> dict:
    """Every ticket's real outcome against each run's simulated outcome."""
    by_id = {r["ticket_id"]: r for r in rows}
    missing = [t.ticket_id for t in tickets if t.ticket_id not in by_id]
    if missing:
        raise EvalError(f"the confirmation run has no result for {', '.join(missing)}")
    per_ticket, differences = [], []
    for t in tickets:
        real = real_view(t, by_id[t.ticket_id])
        simulated = []
        for run_number, results in part_b:
            if t.ticket_id not in results:
                raise EvalError(f"Part B run {run_number} has no result for {t.ticket_id}")
            sim = simulated_view(t, results[t.ticket_id], threshold)
            simulated.append({"run": run_number, **sim})
            for name in COMPARED_FIELDS:
                if sim[name] != real[name]:
                    differences.append(
                        {"ticket_id": t.ticket_id, "split": t.split, "expected": t.expected, "run": run_number,
                         "field": name, "real": real[name], "simulated": sim[name]}
                    )
        per_ticket.append(
            {
                "ticket_id": t.ticket_id,
                "split": t.split,
                "expected": t.expected,
                "real": real,
                "simulated": simulated,
                "match": not any(d["ticket_id"] == t.ticket_id for d in differences),
            }
        )
    matching = sum(p["match"] for p in per_ticket)
    return {
        "threshold": threshold,
        "compared_fields": list(COMPARED_FIELDS),
        "runs_compared": [n for n, _ in part_b],
        "tickets_compared": len(per_ticket),
        "tickets_matching": matching,
        "tickets_differing": [p["ticket_id"] for p in per_ticket if not p["match"]],
        "differences": differences,
        "match": not differences and matching == len(per_ticket) == len(tickets),
        "tickets": per_ticket,
    }
