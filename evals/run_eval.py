"""Evaluation runner (spec 05). Run from the repository root:

    python -m evals.run_eval part-a
    python -m evals.run_eval sweep --runs RUN1.json RUN2.json RUN3.json

Both commands are free: they never call the model. The paid parts
(Part B and the confirmation run) are not implemented yet.
"""

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

from evals.eval_recorders import EvalError, MemoryHandoffStore, NoCallGenerator, RecordingRetriever
from evals.eval_report import REPORTS_DIR, ReportExists, part_a_markdown, sweep_markdown, write_report
from evals.eval_scoring import retrieval_row, retrieval_summary
from evals.eval_sweep import load_run, sweep, thresholds_meeting_targets
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

# Spec 05: kb_v1, search(k=5), threshold -1.0 so the retrieval check never
# escalates.
KB_VERSION = "v1"
SEARCH_K = 5
NO_ESCALATION_THRESHOLD = -1.0
RUNS_REQUIRED = 3

PART_A_NAME = "part-a-retrieval"
SWEEP_NAME = "part-c-sweep"

EXIT_FAILED = 1


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
    retrieval. retriever is open_retrieval(KB_VERSION) (or a test fake)."""
    recorder = RecordingRetriever(retriever)
    generator = NoCallGenerator()
    flow = build_flow(recorder, generator, MemoryHandoffStore())
    rows = []
    for ticket in tickets:
        calls_before = generator.calls
        flow.ask(ticket.question)
        searches = recorder.take()
        if len(searches) != 1:
            raise EvalError(f"{ticket.ticket_id}: the flow made {len(searches)} search() calls, expected 1")
        call = searches[0]
        if call.k != SEARCH_K:
            raise EvalError(f"{ticket.ticket_id}: the flow searched with k={call.k}, spec 05 needs k={SEARCH_K}")
        if not call.chunks:
            raise EvalError(f"{ticket.ticket_id}: search() returned no chunks")
        top_ids = [c.article_id for c in call.chunks]
        rows.append(
            {
                "ticket_id": ticket.ticket_id,
                "split": ticket.split,
                "expected": ticket.expected,
                "category": ticket.category,
                "expected_article_ids": list(ticket.expected_article_ids),
                "article_match": ticket.article_match,
                "query_sent": call.query,
                "top_score": call.top_score,
                "top_article_ids": top_ids,
                "top_chunks": [
                    {"chunk_id": c.chunk_id, "article_id": c.article_id, "similarity_score": c.similarity_score}
                    for c in call.chunks
                ],
                "model_called": generator.calls > calls_before,
                **retrieval_row(ticket, top_ids),
            }
        )
    by_id = {r["ticket_id"]: r for r in rows}
    return {
        "kind": "part-a",
        "kb_version": KB_VERSION,
        "k": SEARCH_K,
        "threshold": NO_ESCALATION_THRESHOLD,
        "planned_model_calls": generator.calls,
        "summary": {name: retrieval_summary(select(tickets, name), by_id) for name in SETS},
        "tickets": rows,
    }


def run_part_a(args) -> int:
    from ingestion import open_retrieval

    sha_before = file_sha256(args.tickets)
    tickets = load_tickets(args.tickets)
    data = part_a(tickets, open_retrieval(KB_VERSION))
    if file_sha256(args.tickets) != sha_before:
        raise EvalError("the ticket file changed during the run")
    commit, dirty = git_state()
    data = {"date": args.date, "git_commit": commit, "git_dirty": dirty, "ticket_file_sha256": sha_before, **data}
    paths = write_report(args.reports_dir, args.date, PART_A_NAME, data, part_a_markdown(data), args.overwrite)
    print("Part A written (no model calls):")
    for p in paths:
        print(f"  {p}")
    return 0


# --- Part C ----------------------------------------------------------------------------


def run_sweep(args) -> int:
    if len(args.runs) != RUNS_REQUIRED or len({Path(p).resolve() for p in args.runs}) != RUNS_REQUIRED:
        raise EvalError(f"the sweep needs {RUNS_REQUIRED} different Part B run files (spec 05)")
    tickets = select(load_tickets(args.tickets), CALIBRATION)
    runs = [load_run(p) for p in args.runs]
    rows = sweep(tickets, runs)
    commit, dirty = git_state()
    data = {
        "kind": "part-c",
        "date": args.date,
        "git_commit": commit,
        "git_dirty": dirty,
        "ticket_file_sha256": file_sha256(args.tickets),
        "set": CALIBRATION,
        "n_tickets": len(tickets),
        "n_answer": sum(t.expected == "answer" for t in tickets),
        "n_escalate": sum(t.expected == "escalate" for t in tickets),
        "runs": [{"file": str(p), "sha256": file_sha256(p)} for p in args.runs],
        "thresholds_meeting_targets": thresholds_meeting_targets(rows),
        "rows": rows,
    }
    paths = write_report(args.reports_dir, args.date, SWEEP_NAME, data, sweep_markdown(data), args.overwrite)
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

    common(sub.add_parser("part-a", help="retrieval report (free, no model calls)"))
    sweep_parser = sub.add_parser("sweep", help="threshold sweep from 3 Part B runs (free)")
    sweep_parser.add_argument("--runs", nargs="+", type=Path, required=True, help="the 3 Part B run .json files")
    common(sweep_parser)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return {"part-a": run_part_a, "sweep": run_sweep}[args.command](args)
    except (EvalError, ReportExists, TicketError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
