"""Report files: evals/reports/<YYYY-MM-DD>-<name>.json and .md (spec 05).

The .json holds everything (for scripts and for Step 10 review); the .md
is what Shailesh reads.
"""

import json
from pathlib import Path

from evals.eval_scoring import AC1_TARGET_PCT, AC2_TARGET_PCT
from evals.eval_tickets import CALIBRATION, FULL, HOLDOUT, SETS

REPORTS_DIR = Path(__file__).resolve().parent / "reports"


class ReportExists(Exception):
    pass


def report_paths(reports_dir: Path, date: str, name: str) -> tuple[Path, Path]:
    stem = f"{date}-{name}"
    return reports_dir / f"{stem}.json", reports_dir / f"{stem}.md"


def write_report(reports_dir: Path, date: str, name: str, data: dict, markdown: str, overwrite: bool = False):
    json_path, md_path = report_paths(Path(reports_dir), date, name)
    if not overwrite:
        existing = [p for p in (json_path, md_path) if p.exists()]
        if existing:
            raise ReportExists(
                f"{', '.join(str(p) for p in existing)} already exists; pass --overwrite to replace it"
            )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return json_path, md_path


# --- Formatting helpers ------------------------------------------------------------


def fmt_score(value) -> str:
    return "–" if value is None else f"{value:.4f}"


def fmt_rate(rate: dict) -> str:
    if not rate["total"]:
        return "– (0 tickets)"
    return f"{rate['passed']}/{rate['total']} ({100 * rate['rate']:.1f}%)"


def fmt_flag(flag) -> str:
    return {True: "yes", False: "**no**", None: "–"}[flag]


def provenance_lines(data: dict) -> list[str]:
    commit = data.get("git_commit") or "unknown"
    if data.get("git_dirty"):
        commit += " (with uncommitted changes)"
    return [
        f"- Date: {data['date']}",
        f"- Git commit: {commit}",
        f"- Ticket file SHA-256: `{data['ticket_file_sha256']}`",
    ]


def histogram(scores: list[float], low: float = 0.50, high: float = 1.00, step: float = 0.025) -> list[str]:
    """Text histogram bins [low, low+step), ... ; scores outside go to the end bins."""
    n_bins = round((high - low) / step)
    counts = [0] * n_bins
    for s in scores:
        i = int((s - low) // step)
        counts[min(max(i, 0), n_bins - 1)] += 1
    lines = []
    for i, c in enumerate(counts):
        lo = low + i * step
        label = f"{lo:.3f}–{lo + step:.3f}"
        if i == 0:
            label = f"<{lo + step:.3f}".ljust(len(label))
        elif i == n_bins - 1:
            label = f"≥{lo:.3f}".ljust(len(label))
        lines.append(f"{label}  {'#' * c} {c if c else ''}".rstrip())
    return lines


def part_a2_comparison_lines(c: dict) -> list[str]:
    """Part A (real flow) against the committed Part A2 simulation."""
    commit = c.get("part_a2_git_commit") or "unknown"
    if c.get("part_a2_git_dirty"):
        commit += " (with uncommitted changes)"
    verdict = "**MATCH**" if c["match"] else "**MISMATCH**"
    out = [
        "",
        f"## Against the Part A2 simulation ({c['experiment']})",
        "",
        "For every ticket: the query, the texts searched, the final chunk ids (in",
        "order), the article ids, recall and the top score (tolerance",
        f"{c['score_tolerance']:g}) must equal the committed simulation.",
        "",
        f"- Part A2 report: `{c['part_a2_report']}`",
        f"- Part A2 report SHA-256: `{c['part_a2_report_sha256']}`",
        f"- Part A2 git commit: {commit}",
        f"- Result: {verdict}: {c['tickets_matching']}/{c['tickets_compared']} tickets match; "
        f"largest top-score difference {c['max_score_difference']:.2e}",
        "",
        "| Set | Recall: real flow | Recall: Part A2 | Both articles: real flow | Both articles: Part A2 |",
        "|---|---|---|---|---|",
    ]
    for name in SETS:
        s = c["summary"][name]
        out.append(
            f"| {name} | {fmt_rate(s['part_a']['recall'])} | {fmt_rate(s['part_a2']['recall'])} | "
            f"{fmt_rate(s['part_a']['both_recall'])} | {fmt_rate(s['part_a2']['both_recall'])} |"
        )
    out += ["", "### Differences", ""]
    if c["differences"]:
        out += ["| Ticket | Field | Real flow | Part A2 |", "|---|---|---|---|"]
        for d in c["differences"]:
            out.append(f"| {d['ticket_id']} | {d['field']} | {fmt_value(d['part_a'])} | {fmt_value(d['part_a2'])} |")
    else:
        out.append("None.")
    return out


def fmt_value(value) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    if isinstance(value, list):
        value = ", ".join(map(str, value))
    return str(value).replace("|", "\\|")


# --- Part A --------------------------------------------------------------------------


def part_a_markdown(data: dict) -> str:
    out = [
        "# Part A: retrieval report",
        "",
        "Spec 05, Part A. No model calls. Each ticket went through QueryFlow with",
        "threshold -1.0 and a stand-in generator that never calls the model, so the",
        "query searched is the flow's own masked and normalised query",
        "(clarification 3) and the scores equal those the sweep uses.",
        "The final retrieved chunks (up to 5 articles, one chunk each) are read",
        "from each ticket's handoff record; the top score is the highest score",
        "among them.",
        "",
        f"- KB version: {data['kb_version']}",
        f"- Retrieval: {data['retrieval']}",
        *provenance_lines(data),
        f"- Model calls a full-flow run would make: {data['planned_model_calls']} of {len(data['tickets'])} tickets",
        "",
        "## Retrieval recall",
        "",
        "| Set | Recall (≥1 expected article retrieved) | Both articles retrieved (two-article tickets) |",
        "|---|---|---|",
    ]
    for name in SETS:
        s = data["summary"][name]
        out.append(f"| {name} | {fmt_rate(s['recall'])} | {fmt_rate(s['both_recall'])} |")
    any_match = data["summary"][FULL]["any_match_tickets"]
    if any_match:
        out += [
            "",
            'Tickets with `article_match: "any"` (excluded from the both-articles column, clarification 2):',
            "",
        ]
        out += [f"- {t['ticket_id']}: expected article retrieved: {fmt_flag(t['recall_hit'])}" for t in any_match]

    misses = [t for t in data["tickets"] if t["recall_hit"] is False or t["both_hit"] is False]
    out += ["", "### Recall misses", ""]
    if misses:
        out += ["| Ticket | Set | Expected | Retrieved article_ids | Top score |", "|---|---|---|---|---|"]
        for t in misses:
            out.append(
                f"| {t['ticket_id']} | {t['split']} | {', '.join(t['expected_article_ids'])} | "
                f"{', '.join(t['top_article_ids'])} | {fmt_score(t['top_score'])} |"
            )
    else:
        out.append("None.")

    if "against_part_a2" in data:
        out += part_a2_comparison_lines(data["against_part_a2"])

    out += [
        "",
        "## Top-score distributions",
        "",
        "\"Escalate (score-dependent)\" leaves out the escalate tickets stopped by the",
        "unknown-fault-code check: they escalate at every threshold.",
        "",
        "| Set | Group | n | min | q1 | median | q3 | max | mean |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name in SETS:
        s = data["summary"][name]
        for label, key in (
            ("answer", "answer_scores"),
            ("escalate (all)", "escalate_scores"),
            ("escalate (score-dependent)", "escalate_scores_reaching_threshold_check"),
        ):
            d = s[key]
            cells = [fmt_score(d.get(k)) for k in ("min", "q1", "median", "q3", "max", "mean")]
            out.append(f"| {name} | {label} | {d['n']} | " + " | ".join(cells) + " |")

    out += ["", "### Overlap between answer and escalate scores", ""]
    for name in SETS:
        o = data["summary"][name]["overlap"]
        if not o:
            continue
        out.append(
            f"- {name}: lowest answer score {fmt_score(o['lowest_answer_score'])}, highest "
            f"score-dependent escalate score {fmt_score(o['highest_escalate_score'])}; "
            + (
                "the groups are separated."
                if o["separated"]
                else f"overlap: {o['answer_tickets_at_or_below_highest_escalate']} answer tickets at or below "
                f"the highest escalate score, {o['escalate_tickets_at_or_above_lowest_answer']} escalate "
                "tickets at or above the lowest answer score."
            )
        )
    stopped = data["summary"][FULL]["escalate_stopped_by_fault_code_check"]
    out.append(f"- Stopped by the unknown-fault-code check (no model call): {', '.join(stopped) or 'none'}")

    for name in (CALIBRATION, HOLDOUT):
        tickets = [t for t in data["tickets"] if t["split"] == name]
        out += ["", f"### Histogram: {name} set", "", "```", "answer"]
        out += histogram([t["top_score"] for t in tickets if t["expected"] == "answer"])
        out += ["", "escalate (score-dependent)"]
        out += histogram([t["top_score"] for t in tickets if t["expected"] == "escalate" and t["model_called"]])
        out.append("```")

    out += [
        "",
        "## All tickets, by top score",
        "",
        "| Ticket | Set | Expected | Category | Top score | Retrieved article_ids | Recall | Model call |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for t in sorted(data["tickets"], key=lambda t: (t["top_score"], t["ticket_id"])):
        recall = fmt_flag(t["recall_hit"])
        if t["both_hit"] is not None:
            recall += f" (both: {fmt_flag(t['both_hit'])})"
        out.append(
            f"| {t['ticket_id']} | {t['split']} | {t['expected']} | {t['category']} | {fmt_score(t['top_score'])} | "
            f"{', '.join(t['top_article_ids'])} | {recall} | {'yes' if t['model_called'] else 'no'} |"
        )
    return "\n".join(out) + "\n"


# --- Part C --------------------------------------------------------------------------


def sweep_markdown(data: dict) -> str:
    meeting = data["thresholds_meeting_targets"]
    out = [
        "# Part C: threshold sweep",
        "",
        "Spec 05, Part C. No model calls: each Part B run is simulated separately",
        "(a ticket escalates if its top score < t, otherwise it keeps its Part B",
        "outcome) and the WORST value of the runs is shown (clarification 1).",
        "Calibration set only; the holdout set is never used to choose.",
        "",
        "**This report does NOT choose the threshold. Shailesh does (spec 02).**",
        "",
        *provenance_lines(data),
        f"- Calibration tickets: {data['n_tickets']} "
        f"({data['n_answer']} answer, {data['n_escalate']} escalate)",
        f"- Targets: AC1 ≥ {AC1_TARGET_PCT}%, AC2 ≥ {AC2_TARGET_PCT}% (worst of the runs)",
        "- Part B runs:",
    ]
    out += [f"  - `{r['file']}` (SHA-256 `{r['sha256'][:16]}…`)" for r in data["runs"]]
    out += [
        "",
        "## Thresholds meeting both targets",
        "",
        (", ".join(f"{t:.2f}" for t in meeting) if meeting else "**None** of 0.50–0.90 meets both targets."),
        "",
        "## Sweep",
        "",
        "Wrong escalation is a metric, not a gate; its worst value is the highest.",
        "\"Passed in all runs\" counts tickets that passed AC1 or AC2 in every run (not a gate).",
        "",
        "| t | AC1 (worst) | AC2 (worst) | Wrong escalation (worst) | Passed in all runs | Meets targets |",
        "|---|---|---|---|---|---|",
    ]
    for row in data["rows"]:
        w = row["worst"]
        out.append(
            f"| {row['threshold']:.2f} | {fmt_rate(w['ac1'])} | {fmt_rate(w['ac2'])} | "
            f"{fmt_rate(w['wrong_escalation'])} | {row['tickets_passed_in_all_runs']}/{data['n_tickets']} | "
            f"{'**yes**' if row['meets_targets'] else 'no'} |"
        )
    return "\n".join(out) + "\n"


# --- Part A2 -------------------------------------------------------------------------


def fmt_change(n: int) -> str:
    return f"{n:+d}" if n else "±0"


def part_a2_markdown(data: dict) -> str:
    from evals.eval_experiments import BASELINE, EXPERIMENTS

    summary = data["summary"]
    out = [
        "# Part A2: retrieval experiments",
        "",
        "Spec 05, Part A2. No model calls. Each experiment starts from the flow's own",
        "masked and normalised query and is simulated through search() and kb_info()",
        "only; query/ is unchanged.",
        "",
        "**Choose using the calibration set; the holdout set must confirm the",
        "improvement. Adopting an experiment is a spec 02 change, approved by",
        "Shailesh. This report does not choose.**",
        "",
        f"- KB version: {data['kb_version']}",
        *provenance_lines(data),
        f"- E1 prefix: `{data['bge_query_prefix']}`",
        "",
        "## Experiments",
        "",
    ]
    out += [f"- **{name}**: {desc}" for name, desc in data["experiments"].items()]

    for title, key in (("Recall (≥1 expected article in top 5)", "recall"),
                       ("Both articles in top 5 (two-article tickets)", "both_recall")):
        out += ["", f"## {title}", "", "| Experiment | calibration | holdout | full |", "|---|---|---|---|"]
        for name in EXPERIMENTS:
            cells = []
            for set_name in SETS:
                r = summary[set_name][name]
                cell = fmt_rate(r[key])
                if name != BASELINE:
                    cell += f" ({fmt_change(r[key + '_change'])})"
                cells.append(cell)
            out.append(f"| {name} | " + " | ".join(cells) + " |")

    out += [
        "",
        "## Against the baseline",
        "",
        "\"Improves\" (summary only) = more recall hits and no fewer both-articles hits",
        "than the baseline on that set.",
        "",
        "| Experiment | Improves on calibration | Holdout confirms | Gained (full set) | Lost (full set) |",
        "|---|---|---|---|---|",
    ]
    for name in EXPERIMENTS:
        if name == BASELINE:
            continue
        full = summary[FULL][name]
        out.append(
            f"| {name} | {fmt_flag(summary[CALIBRATION][name]['improves_on_baseline'])} | "
            f"{fmt_flag(summary[HOLDOUT][name]['improves_on_baseline'])} | "
            f"{', '.join(full['gained']) or '–'} | {', '.join(full['lost']) or '–'} |"
        )

    any_ids = [t["ticket_id"] for t in summary[FULL][BASELINE]["any_match_tickets"]]
    if any_ids:
        out += ["", 'Tickets with `article_match: "any"` (excluded from both-articles recall, clarification 2):', ""]
        for tid in any_ids:
            hits = []
            for name in EXPERIMENTS:
                hit = next(t["recall_hit"] for t in summary[FULL][name]["any_match_tickets"] if t["ticket_id"] == tid)
                hits.append(f"{name}: {fmt_flag(hit)}")
            out.append(f"- {tid}: " + ", ".join(hits))

    boosted = [t for t in data["tickets"] if t["boost_titles"]]
    out += ["", "## E3 code boost: where it applied", ""]
    if boosted:
        out += ["| Ticket | Set | Expected | Titles searched |", "|---|---|---|---|"]
        for t in boosted:
            out.append(
                f"| {t['ticket_id']} | {t['split']} | {t['expected']} | {'; '.join(t['boost_titles'])} |"
            )
    else:
        out.append("No ticket contained a known E-xx code.")

    def cell(t, name):
        r = t["results"][name]
        text = fmt_flag(r["recall_hit"])
        if r["both_hit"] is not None:
            text += f" (both: {fmt_flag(r['both_hit'])})"
        return text

    # Any change from the baseline means a miss somewhere (in the baseline
    # or in the experiment), so listing every ticket with a miss shows both.
    changed = [
        t for t in data["tickets"]
        if t["expected"] == "answer"
        and any(t["results"][n]["recall_hit"] is False or t["results"][n]["both_hit"] is False for n in EXPERIMENTS)
    ]
    out += [
        "",
        "## Answer tickets with a miss in any experiment",
        "",
    ]
    if changed:
        out += [
            "| Ticket | Set | Expected | " + " | ".join(EXPERIMENTS) + " |",
            "|---|---|---|" + "---|" * len(EXPERIMENTS),
        ]
        for t in changed:
            out.append(
                f"| {t['ticket_id']} | {t['split']} | {', '.join(t['expected_article_ids'])} | "
                + " | ".join(cell(t, n) for n in EXPERIMENTS) + " |"
            )
    else:
        out.append("None.")

    out += [
        "",
        "## Note on scores",
        "",
        "Recall is the only measure here. Top scores are saved in the .json, but E1 and",
        "E3 change the scores the threshold would see (E3 merges scores of title",
        "searches), so the sweep must be redone on any adopted experiment.",
    ]
    return "\n".join(out) + "\n"
