"""Part A against the committed Part A2 simulation (spec 05 v1.6; spec 02
decision 13).

Part A2 simulated E1+E2+E3 before the query flow implemented it. Part A
now measures the real flow. Spec 05 v1.6: the comparison is on article
ids, recall and top score, NOT chunk ids (since spec 02 v1.14 the model
reads whole articles, so which chunk of an article was best no longer
changes what the model sees). Only these fields decide the match.

The query sent, the texts searched and the chunk ids are still compared,
as information only: they explain a difference, but never make one.

The Part A2 report is only read, never re-computed: its simulation added
the BGE prefix itself and cannot run against search() that adds it too.
"""

import json
from pathlib import Path

from evals.eval_recorders import EvalError
from evals.eval_report import REPORTS_DIR
from evals.eval_tickets import SETS, file_sha256

PART_A2_REPORT = REPORTS_DIR / "2026-10-17-part-a2-retrieval-experiments.json"
ADOPTED_EXPERIMENT = "E1+E2+E3"

# The real flow sends search() the same text the simulation did (search()
# now adds the prefix that the simulation added), so scores should be
# identical. The tolerance only allows for float noise.
SCORE_TOLERANCE = 1e-9


def load_part_a2(path: Path | str) -> dict:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise EvalError(f"cannot read the Part A2 report {path}: {e}") from e
    if data.get("kind") != "part-a2":
        raise EvalError(f"{path} is not a Part A2 report")
    return data


def searched_texts_a2(row: dict) -> list[str]:
    """What the simulation searched: the flow's query, then the boost titles."""
    return [row["query_sent"], *row["boost_titles"]]


def searched_texts_a(row: dict) -> list[str]:
    """What the real flow passed to search(), in call order."""
    return [s["query"] for s in row["searches"]]


# Spec 05 v1.6: these decide the match (plus the top score).
COMPARED_FIELDS = ("article_ids", "recall_hit", "both_hit", "top_score")
# Information only.
INFORMATION_FIELDS = ("query_sent", "searched_texts", "chunk_ids")


def ticket_differences(row_a: dict, row_a2: dict) -> tuple[list[dict], float, list[dict]]:
    """Differences for one ticket (they decide the match), the absolute
    top-score difference, and information-only differences."""
    sim = row_a2["results"][ADOPTED_EXPERIMENT]

    def found(pairs):
        return [
            {"ticket_id": row_a["ticket_id"], "field": name, "part_a": real, "part_a2": simulated}
            for name, real, simulated in pairs
            if real != simulated
        ]

    diffs = found([
        ("article_ids", row_a["top_article_ids"], sim["top_article_ids"]),
        ("recall_hit", row_a["recall_hit"], sim["recall_hit"]),
        ("both_hit", row_a["both_hit"], sim["both_hit"]),
    ])
    info = found([
        ("query_sent", row_a["query_sent"], row_a2["query_sent"]),
        ("searched_texts", searched_texts_a(row_a), searched_texts_a2(row_a2)),
        ("chunk_ids", [c["chunk_id"] for c in row_a["top_chunks"]], sim["top_chunk_ids"]),
    ])
    score_diff = abs(row_a["top_score"] - sim["top_score"])
    if score_diff > SCORE_TOLERANCE:
        diffs.append(
            {"ticket_id": row_a["ticket_id"], "field": "top_score", "part_a": row_a["top_score"],
             "part_a2": sim["top_score"]}
        )
    return diffs, score_diff, info


def compare_with_part_a2(part_a: dict, a2_path: Path | str = PART_A2_REPORT) -> dict:
    """part_a is the Part A data including ticket_file_sha256.

    Raises EvalError if the two reports cannot be compared (different
    ticket file, KB version or tickets). Differences in results are
    returned, not raised: the runner writes them into the report first.
    """
    a2_path = Path(a2_path)
    a2 = load_part_a2(a2_path)
    if a2.get("ticket_file_sha256") != part_a["ticket_file_sha256"]:
        raise EvalError("the Part A2 report was made from a different ticket file (SHA-256 differs)")
    if a2.get("kb_version") != part_a["kb_version"]:
        raise EvalError(f"the Part A2 report used kb {a2.get('kb_version')!r}, Part A used {part_a['kb_version']!r}")
    if ADOPTED_EXPERIMENT not in a2.get("experiments", {}):
        raise EvalError(f"the Part A2 report has no {ADOPTED_EXPERIMENT} results")
    rows_a2 = {r["ticket_id"]: r for r in a2["tickets"]}
    ids_a = [r["ticket_id"] for r in part_a["tickets"]]
    if set(ids_a) != set(rows_a2) or len(ids_a) != len(rows_a2):
        raise EvalError("Part A and the Part A2 report do not cover the same tickets")

    differences: list[dict] = []
    information: list[dict] = []
    max_score_diff = 0.0
    matching = 0
    for row in part_a["tickets"]:
        diffs, score_diff, info = ticket_differences(row, rows_a2[row["ticket_id"]])
        differences += diffs
        information += info
        max_score_diff = max(max_score_diff, score_diff)
        matching += not diffs

    summary = {
        name: {
            "part_a": {k: part_a["summary"][name][k] for k in ("recall", "both_recall")},
            "part_a2": {k: a2["summary"][name][ADOPTED_EXPERIMENT][k] for k in ("recall", "both_recall")},
        }
        for name in SETS
    }
    summary_match = all(s["part_a"] == s["part_a2"] for s in summary.values())
    return {
        "part_a2_report": str(a2_path),
        "part_a2_report_sha256": file_sha256(a2_path),
        "part_a2_git_commit": a2.get("git_commit"),
        "part_a2_git_dirty": a2.get("git_dirty"),
        "experiment": ADOPTED_EXPERIMENT,
        "compared_fields": list(COMPARED_FIELDS),
        "information_fields": list(INFORMATION_FIELDS),
        "score_tolerance": SCORE_TOLERANCE,
        "max_score_difference": max_score_diff,
        "tickets_compared": len(ids_a),
        "tickets_matching": matching,
        "match": not differences and summary_match,
        "summary": summary,
        "differences": differences,
        "information_differences": information,
    }
