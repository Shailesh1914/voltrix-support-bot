"""Evaluation gate for CI (spec 06, Workflow 2).

One full-flow run of every ticket with the real model, at the threshold in
query/config.py (read as the real bot reads it; there is no other source).
The gate passes only if, on the FULL ticket set, AC1 >= 85% and AC2 >= 95%
(spec 02 acceptance criteria 1 and 2, scored by eval_scoring).

One run, not three: the runs were shown to be identical at Step 9
(spec 06). Three runs remain required for threshold decisions.

Exit codes are chosen so that CI can never mistake one failure for another:
- EXIT_PASS: both criteria met.
- EXIT_QUALITY_FAILED: a valid run, and AC1 or AC2 is below target.
- EXIT_SERVICE_ERROR: the model API failed (an outage). The run is invalid
  and says nothing about quality; re-run it.
- EXIT_ERROR (from run_eval): anything else, e.g. the kb_v1 index is
  missing, a refused output folder, or a run aborted for another reason.
- EXIT_DRY_RUN: the free dry run. Deliberately not 0, so a workflow that
  forgets --confirm can never show a passing gate.
"""

from pathlib import Path

from evals import eval_confirm as ec
from evals.eval_recorders import EvalError
from evals.eval_scoring import AC1_TARGET_PCT, AC2_TARGET_PCT, SERVICE_ERROR, Rate
from evals.eval_tickets import FULL, REPO_ROOT

GATE_KIND = "gate"
GATE_NAME = "gate"

EXIT_PASS = 0
EXIT_QUALITY_FAILED = 3
EXIT_SERVICE_ERROR = 4
EXIT_DRY_RUN = 5

# Folders the output folder must stay out of (and must not contain): the
# bot's handoff queue, the frozen data, and every folder whose uncommitted
# changes block a paid run. evals/ itself is listed because evals/*.py is
# protected; a subfolder such as evals/reports/ is fine.
FORBIDDEN_OUTPUT_FOLDERS = ("handoffs", "data", "query", "ingestion", "specs")
PROTECTED_EXACT_FOLDERS = ("evals",)


def bot_threshold() -> float:
    """The threshold the real bot runs at. The gate reads it through the
    evaluation's ONE threshold reader (eval_confirm.bot_threshold: query/
    config.py, as query/ask.py reads it, when called), so there is still a
    single place in evals/ that touches the setting."""
    try:
        return ec.bot_threshold()
    except EvalError as e:
        raise EvalError(f"the gate cannot run: {e}") from None


# --- Output folder ---------------------------------------------------------------


def check_output_folder(out_dir: Path, repo_root: Path | None = None) -> Path:
    """The resolved output folder, or EvalError. Outside the repository is
    always fine; inside it, the folder must not touch handoffs/, data/ or a
    protected code folder, so its own files can never hide (or be) a change
    to code, specs or data."""
    out = Path(out_dir).resolve()
    root = Path(repo_root if repo_root is not None else REPO_ROOT).resolve()
    if not out.is_relative_to(root):
        return out
    if out == root:
        raise EvalError("the output folder must not be the repository root")
    for name in FORBIDDEN_OUTPUT_FOLDERS:
        folder = root / name
        if out.is_relative_to(folder) or folder.is_relative_to(out):
            raise EvalError(f"the output folder must not be inside or contain {name}/")
    for name in PROTECTED_EXACT_FOLDERS:
        folder = root / name
        if out == folder or folder.is_relative_to(out):
            raise EvalError(f"the output folder must not be {name}/ itself (use a subfolder or a folder elsewhere)")
    return out


def report_files(out_dir: Path, date: str) -> list[Path]:
    """Every file the gate writes."""
    out = Path(out_dir)
    return [out / f"{date}-{GATE_NAME}.json", out / f"{date}-{GATE_NAME}.md",
            out / f"{date}-{GATE_NAME}-handoffs.jsonl"]


def check_not_written(out_dir: Path, date: str) -> None:
    existing = [str(p) for p in report_files(out_dir, date) if p.exists()]
    if existing:
        raise EvalError(f"{', '.join(existing)} already exists; the gate never replaces a report")


def blocking_changes(changes: list[str], out_dir: Path, repo_root: Path | None = None) -> list[str]:
    """changes are the uncommitted changes in the protected folders
    (eval_part_b.uncommitted_code_changes(), as for Part B). Anything inside
    the gate's own output folder never blocks the gate."""
    out = Path(out_dir).resolve()
    root = Path(repo_root if repo_root is not None else REPO_ROOT).resolve()
    return [c for c in changes if not (root / c.strip('"')).resolve().is_relative_to(out)]


# --- The verdict -----------------------------------------------------------------


def verdict(summary_full: dict) -> dict:
    """The gate's verdict from the FULL set's scores (spec 06: "on the full
    ticket set"). Exact integer comparison (Rate.meets)."""
    criteria = []
    for name, target in (("ac1", AC1_TARGET_PCT), ("ac2", AC2_TARGET_PCT)):
        r = summary_full[name]
        rate = Rate(r["passed"], r["total"])
        criteria.append({"criterion": name.upper(), "passed": rate.passed, "total": rate.total,
                         "target_pct": target, "met": rate.meets(target)})
    failed = [c["criterion"] for c in criteria if not c["met"]]
    return {"set": FULL, "passed": not failed, "failed_criteria": failed, "criteria": criteria}


def has_service_error(data: dict) -> bool:
    stopped = data.get("stopped") or {}
    return stopped.get("reason") == SERVICE_ERROR or any(
        row.get("escalation_reason") == SERVICE_ERROR for row in data.get("tickets", [])
    )


def criterion_text(c: dict) -> str:
    pct = 100 * c["passed"] / c["total"] if c["total"] else 0.0
    return f"{c['criterion']} {c['passed']}/{c['total']} ({pct:.1f}%, target {c['target_pct']}%)"


def decide(data: dict) -> tuple[int, str]:
    """(exit code, one-line message) for a finished run. A service_error is
    always an outage, checked first, so it can never be read as a quality
    result; an invalid run is never scored."""
    if has_service_error(data):
        where = (data.get("stopped") or {}).get("ticket_id") or "a ticket"
        return EXIT_SERVICE_ERROR, (
            f"GATE ERROR: service_error at {where} (model API failure, not a quality result). "
            "Re-run the gate."
        )
    if not data.get("valid") or not data.get("summary"):
        reason = (data.get("stopped") or {}).get("reason") or "incomplete handoff records"
        return 1, f"GATE ERROR: the run is invalid ({reason}); no quality result."
    v = verdict(data["summary"][FULL])  # always from the scores, never from a stored verdict
    details = "; ".join(criterion_text(c) for c in v["criteria"])
    if v["passed"]:
        return EXIT_PASS, f"GATE PASSED on the full set: {details}"
    failed = " and ".join(f"{c['criterion']} below target" for c in v["criteria"] if not c["met"])
    return EXIT_QUALITY_FAILED, f"GATE FAILED: {failed}. Full set: {details}"
