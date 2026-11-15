"""Did CI pass for this commit on main? (spec 08 section 9: only images
built from a commit on main that passed CI are deployed.)

    .venv/bin/python deploy/ci_passed.py <full-commit-sha>

Read-only: runs `gh run list` only. Passes when the "Structural tests"
workflow (spec 06; it runs on every push) has a successful run for a push
of exactly this commit to main, none of its runs for the commit is still
going, and no workflow run for the commit failed. Cancelled runs are
ignored (a newer push cancels an older run).

Exit 0 passed, 1 not passed or gh failed.
"""

import json
import sys

from stage_b import REPO_ROOT, run_process

WORKFLOW = "Structural tests"
FAILED = {"failure", "timed_out", "startup_failure", "action_required"}
FIELDS = "databaseId,workflowName,event,headBranch,headSha,status,conclusion,url"


def runs_for(commit: str, runner=run_process) -> list[dict]:
    result = runner(["gh", "run", "list", "--commit", commit, "--limit", "100", "--json", FIELDS])
    if result.returncode != 0:
        raise RuntimeError(f"gh run list failed (exit {result.returncode}): {(result.stderr or '').strip()[-300:]}")
    return json.loads(result.stdout or "[]")


def verdict(runs: list[dict], commit: str) -> tuple[bool, str]:
    mine = [r for r in runs if r.get("headSha") == commit]
    failed = [r for r in mine if r.get("status") == "completed" and r.get("conclusion") in FAILED]
    if failed:
        return False, "failed runs: " + ", ".join(f"{r['workflowName']} ({r['conclusion']}) {r.get('url', '')}" for r in failed)
    structural = [r for r in mine if r.get("workflowName") == WORKFLOW and r.get("event") == "push"
                  and r.get("headBranch") == "main" and r.get("conclusion") != "cancelled"]
    if not structural:
        return False, f"no {WORKFLOW!r} run for a push of {commit[:7]} to main"
    running = [r for r in structural if r.get("status") != "completed"]
    if running:
        return False, f"{WORKFLOW!r} is still running for {commit[:7]}; wait and re-run"
    if not any(r.get("conclusion") == "success" for r in structural):
        return False, f"{WORKFLOW!r} did not succeed for {commit[:7]}"
    return True, f"{WORKFLOW!r} passed for the push of {commit[:7]} to main"


def main(argv: list[str] | None = None, runner=run_process) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or len(args[0]) != 40:
        print("usage: deploy/ci_passed.py <full-commit-sha>", file=sys.stderr)
        return 2
    try:
        ok, message = verdict(runs_for(args[0], runner), args[0])
    except (RuntimeError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(("CI passed: " if ok else "CI NOT passed: ") + message, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    import os
    os.chdir(REPO_ROOT)  # gh finds the GitHub repository from this checkout's remote
    sys.exit(main())
