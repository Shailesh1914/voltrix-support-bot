"""Rescoring Part B runs after a label review (spec 05 v1.8). No model calls.

The 3 runs are scored twice: BEFORE with the ticket file they were made on
(original labels), AFTER with the revised ticket file. Worst of 3 applies
as in Part B (clarification 1).

Allowed only if both ticket files hold the same ticket ids and every field
other than "expected", "expected_article_ids" and "article_match" is
identical (question, category, notes, ...). Anything else refuses.

The runs record only the SHA-256 of their ticket file, so the original file
is taken from git history: the committed version with exactly that SHA.
Rescoring never replaces the run files or their reports.
"""

import hashlib
import subprocess
from pathlib import Path

from evals.eval_aggregate import MUST_MATCH, check_runs, score_runs
from evals.eval_recorders import EvalError
from evals.eval_tickets import REPO_ROOT, SETS, TICKETS_PATH, Ticket, read_records

RESCORE_KIND = "part-b-rescore"

# Spec 05 v1.8: the only fields a label review may change.
RELABEL_FIELDS = ("expected", "expected_article_ids", "article_match")

_MISSING = object()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- The ticket file the runs were made on -----------------------------------------------


def ticket_file_from_git(sha256: str, repo_root: Path = REPO_ROOT, path: Path = TICKETS_PATH) -> tuple[str, str]:
    """(commit, text) of the committed ticket file whose SHA-256 is `sha256`.
    Refuses if no committed version matches."""
    rel = Path(path).resolve().relative_to(Path(repo_root).resolve()).as_posix()
    try:
        commits = subprocess.run(
            ["git", "log", "--format=%H", "--", rel], cwd=repo_root, capture_output=True, text=True, check=True
        ).stdout.split()
        for commit in commits:
            blob = subprocess.run(
                ["git", "show", f"{commit}:{rel}"], cwd=repo_root, capture_output=True, check=True
            ).stdout
            if hashlib.sha256(blob).hexdigest() == sha256:
                return commit, blob.decode("utf-8")
    except (OSError, subprocess.CalledProcessError) as e:
        raise EvalError(f"cannot read the history of {rel} from git ({e})") from None
    raise EvalError(
        f"no committed version of {rel} has SHA-256 {sha256} (the runs' ticket file); "
        "rescoring needs the original labels"
    )


# --- Checks ---------------------------------------------------------------------------


def label_of(ticket: Ticket) -> dict:
    return {
        "expected": ticket.expected,
        "expected_article_ids": list(ticket.expected_article_ids),
        "article_match": ticket.article_match,
    }


def compare_ticket_files(old_text: str, new_text: str) -> list[dict]:
    """The tickets whose label changed, in the new file's order.

    Refuses if a ticket id was added or removed, or if any field other than
    RELABEL_FIELDS differs. Labels are compared after parsing, so an absent
    article_match equals "all"."""
    old = {t.ticket_id: (raw, t) for raw, t in read_records(old_text, "the runs' ticket file")}
    new_records = read_records(new_text, "the revised ticket file")
    new = {t.ticket_id: (raw, t) for raw, t in new_records}

    removed = sorted(set(old) - set(new))
    added = sorted(set(new) - set(old))
    if removed or added:
        parts = ([f"missing in the revised file: {', '.join(removed)}"] if removed else []) + (
            [f"not in the runs' file: {', '.join(added)}"] if added else []
        )
        raise EvalError("the ticket ids differ (" + "; ".join(parts) + "); rescoring refuses (spec 05 v1.8)")

    differences = []
    for _, t in new_records:
        old_raw, new_raw = old[t.ticket_id][0], new[t.ticket_id][0]
        for field in sorted(set(old_raw) | set(new_raw)):
            if field in RELABEL_FIELDS:
                continue
            if old_raw.get(field, _MISSING) != new_raw.get(field, _MISSING):
                differences.append(f"{t.ticket_id} {field}")
    if differences:
        raise EvalError(
            "only expected, expected_article_ids and article_match may differ; these differ: "
            + ", ".join(differences) + "; rescoring refuses (spec 05 v1.8)"
        )

    changes = []
    for _, t in new_records:
        before, after = label_of(old[t.ticket_id][1]), label_of(t)
        if before != after:
            changes.append({"ticket_id": t.ticket_id, "before": before, "after": after})
    return changes


def check_run_labels(runs: list[dict], tickets: list[Ticket]) -> None:
    """The labels stored in every run row must equal the original file's: proof
    that BEFORE uses the labels the runs were scored with."""
    by_id = {t.ticket_id: label_of(t) for t in tickets}
    for r in runs:
        for row in r["tickets"]:
            stored = {f: row.get(f) for f in RELABEL_FIELDS if f in row}
            expected = {f: by_id[row["ticket_id"]][f] for f in stored}
            if stored != expected:
                raise EvalError(
                    f"run {r['run']} recorded other labels for {row['ticket_id']} than the runs' ticket file "
                    f"({stored} vs {expected})"
                )


# --- Rescoring ------------------------------------------------------------------------


def set_view(s: dict) -> dict:
    return {
        "n_tickets": s["n_tickets"],
        "worst": s["worst"],
        "per_run": [
            {k: r[k] for k in ("ac1", "ac2", "wrong_escalation", "both_cited", "any_match_tickets")}
            for r in s["per_run"]
        ],
        "tickets_passed_in_all_runs": s["tickets_passed_in_all_runs"],
        "failed_in_some_run": s["failed_in_some_run"],
        "unstable": s["unstable"],
    }


def rescore(runs: list[dict], old_text: str, new_text: str) -> dict:
    old_sha, new_sha = text_sha256(old_text), text_sha256(new_text)
    if old_sha == new_sha:
        raise EvalError("the ticket file is unchanged since the runs; use aggregate, there is nothing to rescore")
    old_tickets = [t for _, t in read_records(old_text, "the runs' ticket file")]
    new_tickets = [t for _, t in read_records(new_text, "the revised ticket file")]

    # The runs must belong together AND have been made on old_text.
    check_runs(runs, old_tickets, old_sha)
    check_run_labels(runs, old_tickets)
    changes = compare_ticket_files(old_text, new_text)

    before = score_runs(old_tickets, runs)
    after = score_runs(new_tickets, runs)
    before_t = {t["ticket_id"]: t for t in before["tickets"]}
    after_t = {t["ticket_id"]: t for t in after["tickets"]}

    relabelled = {c["ticket_id"] for c in changes}
    pass_changed = []
    for tid in before_t:
        b = [v["pass"] for v in before_t[tid]["runs"]]
        a = [v["pass"] for v in after_t[tid]["runs"]]
        if a != b:
            if tid not in relabelled:
                raise EvalError(f"internal error: pass/fail of {tid} changed although its label did not")
            pass_changed.append(tid)

    label_changes = []
    for c in changes:
        b, a = before_t[c["ticket_id"]], after_t[c["ticket_id"]]
        label_changes.append(
            {
                **c,
                "split": b["split"],
                "runs": [
                    {**{k: v for k, v in rb.items() if k != "pass"}, "pass_before": rb["pass"], "pass_after": ra["pass"]}
                    for rb, ra in zip(b["runs"], a["runs"])
                ],
                "passed_all_runs_before": b["passed_all_runs"],
                "passed_all_runs_after": a["passed_all_runs"],
                "pass_changed": c["ticket_id"] in pass_changed,
            }
        )

    return {
        "kind": RESCORE_KIND,
        "threshold": before["threshold"],
        **{name: runs[0][name] for name in MUST_MATCH if name != "ticket_file_sha256"},
        "ticket_file_sha256_before": old_sha,
        "ticket_file_sha256_after": new_sha,
        "runs": before["runs"],
        "label_changes": label_changes,
        "pass_changed": pass_changed,
        "sets": {name: {"before": set_view(before["sets"][name]), "after": set_view(after["sets"][name])} for name in SETS},
    }

