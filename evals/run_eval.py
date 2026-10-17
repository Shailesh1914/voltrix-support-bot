"""Evaluation runner (spec 05). Run from the repository root:

    python -m evals.run_eval part-a [--label LABEL]
    python -m evals.run_eval part-b --label LABEL --run 1            (free dry run)
    python -m evals.run_eval part-b --label LABEL --run 1 --confirm  (PAID: Shailesh only)
    python -m evals.run_eval aggregate --runs RUN1.json RUN2.json RUN3.json
    python -m evals.run_eval sweep --runs RUN1.json RUN2.json RUN3.json

Only `part-b --confirm` calls the model; everything else is free. The
confirmation run (spec 05, Part C) is not implemented yet.

Part A2 is completed (spec 05 v1.5): `part-a2` only refuses and points to
its committed report.
"""

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

from evals import eval_part_b as pb
from evals.eval_aggregate import aggregate, check_runs, load_part_b
from evals.eval_compare import PART_A2_REPORT, compare_with_part_a2
from evals.eval_experiments import BGE_QUERY_PREFIX
from evals.eval_recorders import EvalError, MemoryHandoffStore, NoCallGenerator, RecordingRetriever
from evals.eval_report import (
    REPORTS_DIR,
    ReportExists,
    aggregate_markdown,
    part_a_markdown,
    part_b_markdown,
    sweep_markdown,
    write_report,
)
from evals.eval_scoring import retrieval_row, retrieval_summary
from evals.eval_sweep import run_from_json, sweep, thresholds_meeting_targets
from evals.eval_tickets import (
    CALIBRATION,
    REPO_ROOT,
    SETS,
    TICKETS_PATH,
    Ticket,
    TicketError,
    file_sha256,
    load_tickets,
    select,
)

# Spec 05: kb_v1 and the flow's own retrieval (spec 02 step 3), threshold
# -1.0 so the retrieval check never escalates.
KB_VERSION = "v1"
NO_ESCALATION_THRESHOLD = -1.0
RUNS_REQUIRED = 3

PART_A_NAME = "part-a-retrieval"


def part_a_name(label: str | None) -> str:
    return PART_A_NAME if label is None else f"{PART_A_NAME}-{pb.check_label(label)}"


def aggregate_name(label: str) -> str:
    return f"part-b-{pb.check_label(label)}-aggregate"


def sweep_name(label: str) -> str:
    return f"part-c-{pb.check_label(label)}-sweep"

# Handoffs of evaluation runs never go here (spec 05, Part B).
HANDOFFS_DIR = REPO_ROOT / "handoffs"

EXIT_FAILED = 1
EXIT_MISMATCH = 3  # Part A differs from the Part A2 simulation (report still written)
EXIT_INVALID_RUN = 4  # Part B hit a service_error: invalid run written, re-run it

PART_A2_COMPLETED = (
    "Part A2 was completed on 2026-10-17 (spec 05 v1.5). Its simulation assumed "
    "search() without the prefix, so it cannot be re-run. Evidence: "
    "evals/reports/2026-10-17-part-a2-retrieval-experiments.md"
)

def git_state(repo_root: Path = REPO_ROOT) -> tuple[str | None, bool | None]:
    """(commit, has uncommitted changes); (None, None) if git is unavailable."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None, None
    return commit, bool(status.strip())


def build_flow(retriever, generator, handoff_store, threshold: float = NO_ESCALATION_THRESHOLD):
    from query.flow import QueryFlow

    return QueryFlow(
        retriever, generator, threshold=threshold, handoff_store=handoff_store, kb_version=KB_VERSION
    )


# --- Part A ----------------------------------------------------------------------------


def part_a(tickets: list[Ticket], retriever) -> dict:
    """Run every ticket through the flow without the model and record its
    retrieval. retriever is open_retrieval(KB_VERSION) (or a test fake).

    The final retrieved chunks are read from each ticket's handoff record
    (spec 02: it holds all retrieved chunks), so Part A follows whatever
    the flow's retrieval does and never re-implements it. The raw search()
    calls are recorded as information only.

    Step 3e (spec 02 v1.14): before the model call, the flow reads every
    chunk of the selected articles with article_chunks(). Part A checks it
    reads exactly the step-d articles, in step-d order.
    """
    recorder = RecordingRetriever(retriever)
    generator = NoCallGenerator()
    store = MemoryHandoffStore()
    flow = build_flow(recorder, generator, store)
    rows = []
    for ticket in tickets:
        calls_before = generator.calls
        response = flow.ask(ticket.question)
        searches = recorder.take()
        reads = recorder.take_reads()
        # search() adds the prefix itself (spec 03 v1.4); a query that
        # already has it would be embedded with a double prefix.
        if any(BGE_QUERY_PREFIX in call.query for call in searches):
            raise EvalError(
                f"{ticket.ticket_id}: a query reached search() with the BGE prefix already in it; "
                "search() adds it itself (spec 03 v1.4)"
            )
        record = store.by_id(response.handoff_id)
        if record is None:
            raise EvalError(f"{ticket.ticket_id}: the flow left no handoff record (status {response.status!r})")
        chunks = record.retrieved_chunks
        if not chunks:
            raise EvalError(f"{ticket.ticket_id}: the flow retrieved no chunks")
        top_ids = [c.article_id for c in chunks]
        model_called = generator.calls > calls_before
        read_ids = [r.article_id for r in reads]
        if (model_called or reads) and read_ids != top_ids:
            raise EvalError(
                f"{ticket.ticket_id}: the flow read articles {read_ids}, but step d selected {top_ids} "
                "(spec 02 step 3e)"
            )
        rows.append(
            {
                "ticket_id": ticket.ticket_id,
                "split": ticket.split,
                "expected": ticket.expected,
                "category": ticket.category,
                "expected_article_ids": list(ticket.expected_article_ids),
                "article_match": ticket.article_match,
                "query_sent": record.question_normalised,
                # Spec 05: the highest score among the final retrieved chunks.
                "top_score": max(c.similarity_score for c in chunks),
                "top_article_ids": top_ids,
                "top_chunks": [
                    {"chunk_id": c.chunk_id, "article_id": c.article_id, "similarity_score": c.similarity_score}
                    for c in chunks
                ],
                "searches": [{"query": call.query, "k": call.k, "n_chunks": len(call.chunks)} for call in searches],
                # Step 3e: what the model would read (whole articles).
                "read_article_ids": read_ids,
                "read_chunks": sum(len(r.chunks) for r in reads),
                "model_called": model_called,
                **retrieval_row(ticket, top_ids),
            }
        )
    by_id = {r["ticket_id"]: r for r in rows}
    return {
        "kind": "part-a",
        "kb_version": KB_VERSION,
        "retrieval": "the flow's own: spec 02 step 3 (main search, code boost, merge, diversity)",
        "threshold": NO_ESCALATION_THRESHOLD,
        "planned_model_calls": generator.calls,
        "summary": {name: retrieval_summary(select(tickets, name), by_id) for name in SETS},
        "tickets": rows,
    }


def run_part_a(args) -> int:
    from ingestion import open_retrieval

    name = part_a_name(args.label)  # a bad label fails before any work
    sha_before = file_sha256(args.tickets)
    tickets = load_tickets(args.tickets)
    data = part_a(tickets, open_retrieval(KB_VERSION))
    if file_sha256(args.tickets) != sha_before:
        raise EvalError("the ticket file changed during the run")
    commit, dirty = git_state()
    data = {"date": args.date, "git_commit": commit, "git_dirty": dirty, "ticket_file_sha256": sha_before, **data}
    comparison = compare_with_part_a2(data, args.part_a2_report)
    data["against_part_a2"] = comparison
    data["label"] = args.label
    paths = write_report(
        args.reports_dir, args.date, name, data, part_a_markdown(data), args.overwrite
    )
    print("Part A written (no model calls):")
    for p in paths:
        print(f"  {p}")
    matched = f"{comparison['tickets_matching']}/{comparison['tickets_compared']} tickets"
    if not comparison["match"]:
        print(
            f"MISMATCH with the Part A2 {comparison['experiment']} simulation: {matched} match, "
            f"{len(comparison['differences'])} differences (see the report)",
            file=sys.stderr,
        )
        return EXIT_MISMATCH
    print(f"MATCH with the Part A2 {comparison['experiment']} simulation: {matched}")
    return 0


# --- Part B ----------------------------------------------------------------------------


def make_real_generator():
    """The real generator (loads the key). Called only after --confirm."""
    from query.anthropic_api import AnthropicGenerator

    return AnthropicGenerator.from_environment()


def part_b_plan(tickets: list[Ticket], retriever) -> tuple[dict, dict]:
    """Free: no key, no model calls. Returns the plan and each ticket's
    retrieval (step-d chunks with scores)."""
    planner = pb.PlanningGenerator()
    store = MemoryHandoffStore()
    return pb.plan(tickets, build_flow(retriever, planner, store), planner, store)


def part_b(tickets: list[Ticket], retriever, generator: pb.UsageRecordingGenerator,
           retrieval: dict | None = None) -> pb.RunOutcome:
    """One Part B run. The handoffs stay in memory (never handoffs/).
    retrieval is from part_b_plan() on the same retriever; computed here
    (free) if not given."""
    if retrieval is None:
        _, retrieval = part_b_plan(tickets, retriever)
    store = MemoryHandoffStore()
    flow = build_flow(retriever, generator, store)
    return pb.run_tickets(tickets, flow, generator, store, retrieval)


def run_part_b(args) -> int:
    from ingestion import open_retrieval

    reports_dir = Path(args.reports_dir)
    label = pb.check_label(args.label)
    sha_before = file_sha256(args.tickets)
    tickets = load_tickets(args.tickets)
    retriever = open_retrieval(KB_VERSION)
    plan, retrieval = part_b_plan(tickets, retriever)
    print(f"Part B run {args.run} ({label}): plan (free: no key loaded, no model calls)")
    for line in pb.plan_lines(plan):
        print(f"  {line}")
    if not plan["within_limit"]:
        raise EvalError(f"{plan['planned_model_calls']} planned model calls exceed the limit of {pb.MAX_MODEL_CALLS}")
    existing = pb.existing_valid_runs(reports_dir, label, args.run)
    if existing:
        raise EvalError(
            f"a valid run {args.run} with label {label!r} already exists ({', '.join(map(str, existing))}); "
            "Part B files are never replaced"
        )
    if not args.confirm:
        print("Dry run: nothing was called or written.")
        print(f"To make the PAID run: python -m evals.run_eval part-b --label {label} --run {args.run} --confirm")
        return 0

    changes = pb.uncommitted_code_changes()
    if changes:
        raise EvalError(
            "uncommitted changes in query/, ingestion/, evals/*.py or specs/; commit first so the run maps "
            f"to a commit: {', '.join(changes)}"
        )
    handoffs_before = pb.folder_snapshot(HANDOFFS_DIR)
    try:
        real = make_real_generator()
    except Exception as e:  # e.g. ConfigError: missing key, refused variable
        # Its messages name variables and files, never the key (query/anthropic_api.py).
        raise EvalError(f"the real generator cannot start: {type(e).__name__}: {e}") from None
    settings = pb.request_settings(real)
    generator = pb.UsageRecordingGenerator(real)

    print(f"Running {plan['planned_model_calls']} model calls ...")
    outcome = part_b(tickets, retriever, generator, retrieval)
    if outcome.stopped is None and file_sha256(args.tickets) != sha_before:
        outcome.stopped = {"reason": "the ticket file changed during the run", "ticket_id": None}
    if outcome.stopped is None and pb.folder_snapshot(HANDOFFS_DIR) != handoffs_before:
        outcome.stopped = {"reason": "handoffs/ changed during the run", "ticket_id": None}

    commit, dirty = git_state()
    data = {
        "date": args.date,
        "git_commit": commit,
        "git_dirty": dirty,
        "code_trees": pb.code_trees(),
        "ticket_file_sha256": sha_before,
        "kb_version": KB_VERSION,
        **settings,
        "plan": plan,
        **pb.run_data(tickets, outcome, args.run, label),
    }
    name = pb.run_name(label, args.run) if data["valid"] else pb.invalid_name(reports_dir, args.date, label, args.run)
    handoffs = pb.handoffs_path(reports_dir, args.date, name)
    data["handoffs_file"] = handoffs.name
    paths = [pb.write_handoffs(handoffs, outcome.handoffs)]
    paths += write_report(reports_dir, args.date, name, data, part_b_markdown(data))
    print(f"Part B run {args.run} written ({data['model_calls']} model calls, ${data['cost_usd']:.4f}):")
    for p in paths:
        print(f"  {p}")
    if data["valid"]:
        print(f"VALID run {args.run}.")
        return 0
    reason = data["stopped"]["reason"] if data["stopped"] else "incomplete handoff records"
    print(f"INVALID run {args.run} ({reason}). Re-run: "
          f"python -m evals.run_eval part-b --label {label} --run {args.run} --confirm", file=sys.stderr)
    return EXIT_INVALID_RUN if data["stopped"] and data["stopped"]["reason"] == "service_error" else EXIT_FAILED


def run_aggregate(args) -> int:
    if len(args.runs) != RUNS_REQUIRED or len({Path(p).resolve() for p in args.runs}) != RUNS_REQUIRED:
        raise EvalError(f"the aggregate needs {RUNS_REQUIRED} different Part B run files (spec 05)")
    sha = file_sha256(args.tickets)
    runs = [load_part_b(p) for p in args.runs]
    commit, dirty = git_state()
    data = {
        "date": args.date,
        "git_commit": commit,
        "git_dirty": dirty,
        **aggregate(load_tickets(args.tickets), runs, sha),
        "run_files": [{"file": str(p), "sha256": file_sha256(p)} for p in args.runs],
    }
    paths = write_report(
        args.reports_dir, args.date, aggregate_name(data["label"]), data, aggregate_markdown(data), args.overwrite
    )
    print("Part B aggregate written (no model calls):")
    for p in paths:
        print(f"  {p}")
    return 0


# --- Part A2 (completed) ---------------------------------------------------------------


def run_part_a2(args) -> int:
    """Part A2 is history: refuse, without searching or writing anything."""
    raise EvalError(PART_A2_COMPLETED)


# --- Part C ----------------------------------------------------------------------------


def run_sweep(args) -> int:
    if len(args.runs) != RUNS_REQUIRED or len({Path(p).resolve() for p in args.runs}) != RUNS_REQUIRED:
        raise EvalError(f"the sweep needs {RUNS_REQUIRED} different Part B run files (spec 05)")
    sha = file_sha256(args.tickets)
    all_tickets = load_tickets(args.tickets)
    tickets = select(all_tickets, CALIBRATION)
    run_files = [load_part_b(p) for p in args.runs]
    # Same rule as the aggregate: same label, code trees, model, prompt,
    # tickets and KB, runs 1, 2 and 3 once each.
    check_runs(run_files, all_tickets, sha)
    runs = [run_from_json(data, str(p)) for data, p in zip(run_files, args.runs)]
    rows = sweep(tickets, runs)
    commit, dirty = git_state()
    data = {
        "kind": "part-c",
        "date": args.date,
        "git_commit": commit,
        "git_dirty": dirty,
        "label": run_files[0]["label"],
        "code_trees": run_files[0]["code_trees"],
        "ticket_file_sha256": sha,
        "set": CALIBRATION,
        "n_tickets": len(tickets),
        "n_answer": sum(t.expected == "answer" for t in tickets),
        "n_escalate": sum(t.expected == "escalate" for t in tickets),
        "runs": [{"file": str(p), "sha256": file_sha256(p)} for p in args.runs],
        "thresholds_meeting_targets": thresholds_meeting_targets(rows),
        "rows": rows,
    }
    paths = write_report(
        args.reports_dir, args.date, sweep_name(data["label"]), data, sweep_markdown(data), args.overwrite
    )
    print("Part C sweep written (no model calls):")
    for p in paths:
        print(f"  {p}")
    return 0


# --- Command line ------------------------------------------------------------------------


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m evals.run_eval", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--date", default=date.today().isoformat(), help="report date (default: today)")
        sp.add_argument("--reports-dir", type=Path, default=REPORTS_DIR, help=argparse.SUPPRESS)
        sp.add_argument("--tickets", type=Path, default=TICKETS_PATH, help=argparse.SUPPRESS)
        sp.add_argument("--overwrite", action="store_true", help="replace existing report files")

    part_a_parser = sub.add_parser("part-a", help="retrieval report (free, no model calls)")
    part_a_parser.add_argument("--part-a2-report", type=Path, default=PART_A2_REPORT, help=argparse.SUPPRESS)
    part_a_parser.add_argument("--label", help="added to the report name, e.g. whole-articles (optional)")
    common(part_a_parser)
    sub.add_parser("part-a2", help="completed 2026-10-17; refuses to run (spec 05 v1.5)")
    part_b_parser = sub.add_parser("part-b", help="full-flow run with the real model (dry run unless --confirm)")
    part_b_parser.add_argument("--run", type=int, choices=pb.RUN_NUMBERS, required=True, help="run number: 1, 2 or 3")
    part_b_parser.add_argument(
        "--label", required=True,
        help="names this set of 3 runs, e.g. whole-articles: <date>-part-b-<label>-runN.json",
    )
    part_b_parser.add_argument("--confirm", action="store_true", help="make the PAID run (Shailesh only)")
    part_b_parser.add_argument("--date", default=date.today().isoformat(), help="report date (default: today)")
    part_b_parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR, help=argparse.SUPPRESS)
    part_b_parser.add_argument("--tickets", type=Path, default=TICKETS_PATH, help=argparse.SUPPRESS)
    aggregate_parser = sub.add_parser("aggregate", help="worst of the 3 Part B runs (free)")
    aggregate_parser.add_argument("--runs", nargs="+", type=Path, required=True, help="the 3 Part B run .json files")
    common(aggregate_parser)
    sweep_parser = sub.add_parser("sweep", help="threshold sweep from 3 Part B runs (free)")
    sweep_parser.add_argument("--runs", nargs="+", type=Path, required=True, help="the 3 Part B run .json files")
    common(sweep_parser)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        commands = {
            "part-a": run_part_a,
            "part-a2": run_part_a2,
            "part-b": run_part_b,
            "aggregate": run_aggregate,
            "sweep": run_sweep,
        }
        return commands[args.command](args)
    except (EvalError, ReportExists, TicketError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
