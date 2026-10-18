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
        "For every ticket the article ids (in order), recall, both-articles",
        f"recall and the top score (tolerance {c['score_tolerance']:g}) must equal the",
        "committed simulation (spec 05 v1.6). Chunk ids are not compared: since",
        "spec 02 v1.14 the model reads whole articles.",
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
    if "information_differences" in c:
        info = c["information_differences"]
        out += ["", "### Other differences (information only, not part of the match)", ""]
        if info:
            out += ["| Ticket | Field | Real flow | Part A2 |", "|---|---|---|---|"]
            for d in info:
                out.append(
                    f"| {d['ticket_id']} | {d['field']} | {fmt_value(d['part_a'])} | {fmt_value(d['part_a2'])} |"
                )
        else:
            out.append("None (query, texts searched and chunk ids also equal).")
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
        "The final retrieved chunks (step d: up to 5 articles, one chunk each) are",
        "read from each ticket's handoff record; the top score is the highest",
        "score among them. Before a model call the flow reads every chunk of",
        "those articles (step 3e); Part A checks it reads exactly those articles.",
        "",
        f"- KB version: {data['kb_version']}",
        f"- Retrieval: {data['retrieval']}",
        *provenance_lines(data),
        f"- Model calls a full-flow run would make: {data['planned_model_calls']} of {len(data['tickets'])} tickets",
        f"- Chunks the model would read (whole articles, step 3e): "
        f"{sum(t.get('read_chunks', 0) for t in data['tickets'])} in total",
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
        f"- Runs label: {data.get('label')}",
        "- Code trees (identical in all runs): "
        + ", ".join(f"{k} `{(v or 'unknown')[:12]}`" for k, v in (data.get("code_trees") or {}).items()),
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


# --- Part B ----------------------------------------------------------------------------


def fmt_usd(value: float) -> str:
    return f"${value:.4f}"


def quote(text: str) -> list[str]:
    return [f"> {line}" if line else ">" for line in (text or "(empty)").splitlines()] or ["> (empty)"]


def part_b_provenance_lines(data: dict) -> list[str]:
    trees = ", ".join(f"{k} `{(v or 'unknown')[:12]}`" for k, v in data["code_trees"].items())
    return [
        *provenance_lines(data),
        f"- Code trees at HEAD: {trees}",
        f"- Model: {data['model_id']}, temperature {data['temperature']}, max output tokens {data['max_output_tokens']}",
        f"- System prompt SHA-256: `{data['system_prompt_sha256']}`",
        f"- KB version: {data['kb_version']}; threshold {data['threshold']} (evaluation only, passed to the flow)",
    ]


def summary_table(summaries: dict, label: str = "") -> list[str]:
    out = [
        f"| Set{label} | AC1 (target {AC1_TARGET_PCT}%) | AC2 (target {AC2_TARGET_PCT}%) | Wrong escalation | "
        "Both articles cited |",
        "|---|---|---|---|---|",
    ]
    for name in SETS:
        s = summaries[name]
        out.append(
            f"| {name} | {fmt_rate(s['ac1'])} | {fmt_rate(s['ac2'])} | {fmt_rate(s['wrong_escalation'])} | "
            f"{fmt_rate(s['both_cited'])} |"
        )
    return out


def usage_lines(data: dict) -> list[str]:
    tokens = data["tokens"]
    return [
        f"- Model calls: {data['model_calls']}",
        f"- Tokens: {tokens['input']:,} input, {tokens['output']:,} output",
        f"- Cost: {fmt_usd(data['cost_usd'])} (${data['prices_usd_per_mtok']['input']:.2f} / "
        f"${data['prices_usd_per_mtok']['output']:.2f} per million input / output tokens)",
        f"- Malformed model outputs: {data['malformed_outputs']}. {data['cost_note']}",
    ]


def part_b_markdown(data: dict) -> str:
    verdict = "**VALID**" if data["valid"] else "**INVALID: re-run it (spec 05)**"
    out = [
        f"# Part B: full-flow run {data['run']}" + (f" ({data['label']})" if data.get("label") else ""),
        "",
        "Spec 05, Part B. Every ticket through QueryFlow with the real model at",
        "threshold -1.0, so the retrieval check never escalates; the",
        "unknown-fault-code check stays active. Handoffs went to the",
        "evaluation-only file below, never to handoffs/.",
        "",
        f"- Run: {verdict}",
        f"- Tickets run: {data['tickets_run']}/{data['tickets_total']}",
    ]
    if data["stopped"]:
        out.append(f"- Stopped at {data['stopped']['ticket_id']}: {data['stopped']['reason']}")
    if data["incomplete_handoff_records"]:
        out.append(f"- **Incomplete handoff records (criterion 3):** {', '.join(data['incomplete_handoff_records'])}")
    out += [
        *part_b_provenance_lines(data),
        f"- Label: {data.get('label') or 'none (made before labels existed)'}",
        f"- Handoffs: `{data['handoffs_file']}` ({data['handoff_records']} records)",
        "- Top score and retrieved chunks: step d of spec 02, from the free planning pass "
        "(checked against this run); the model read the whole selected articles (step 3e)",
        *usage_lines(data),
    ]
    if data["summary"]:
        full = data["summary"][FULL]
        out += [
            "",
            "## Results at threshold -1.0 (this run only)",
            "",
            "The threshold itself is simulated by the sweep (Part C).",
            "",
            *summary_table(data["summary"]),
            "",
            "- failed_check counts (full set): "
            + (", ".join(f"{k} {v}" for k, v in full["failed_check_counts"].items()) or "none"),
            "- Escalation reasons (full set): "
            + (", ".join(f"{k} {v}" for k, v in full["escalation_reason_counts"].items()) or "none"),
        ]
        for t in full["any_match_tickets"]:
            out.append(f'- {t["ticket_id"]} (article_match "any"): AC1 {fmt_flag(t["ac1_pass"])}')
    out += [
        "",
        "## All tickets",
        "",
        "| Ticket | Set | Expected | Top score | Status | Reason | failed_check | Cited | Pass | Tokens in/out |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for t in data["tickets"]:
        tokens = "–" if t["input_tokens"] is None else f"{t['input_tokens']}/{t['output_tokens']}"
        if t["malformed_output"]:
            tokens = "malformed (unknown)"
        out.append(
            f"| {t['ticket_id']} | {t['split']} | {t['expected']} | {fmt_score(t['top_score'])} | {t['status']} | "
            f"{t['escalation_reason'] or '–'} | {t['failed_check'] or '–'} | "
            f"{', '.join(c['article_id'] for c in t['citations']) or '–'} | {fmt_flag(t['ac_pass'])} | {tokens} |"
        )
    out += [
        "",
        "## Answers (for the Step 10 review)",
        "",
        "Not scored automatically beyond criterion 7 (spec 05, Scoring).",
    ]
    for t in data["tickets"]:
        if not t["model_called"]:
            continue
        m = t["model_output"]
        out += ["", f"### {t['ticket_id']} ({t['expected']}; {t['status']}"
                + (f", {t['escalation_reason']}" if t["escalation_reason"] else "") + ")", ""]
        out += [f"Question: {t['question_sent']}", ""]
        if m is None:
            out.append("Model output: malformed or service error (no structured output).")
            continue
        out.append(f"Model decision: {m['decision']}; used_article_ids: {', '.join(m['used_article_ids']) or '–'}")
        if t["status"] == "answered":
            out += ["", "Answer shown to the user:", "", *quote(t["answer"])]
        elif t["rejected_answer"]:
            out += ["", f"Rejected draft (failed_check {t['failed_check']}, never shown):", "", *quote(t["rejected_answer"])]
    return "\n".join(out) + "\n"


def aggregate_markdown(data: dict) -> str:
    out = [
        "# Part B: aggregate of 3 runs",
        "",
        "Spec 05, Part B and clarification 1. Results at threshold -1.0. For each",
        "metric the WORST value across the 3 runs: the lowest for success rates,",
        "the highest for the wrong-escalation rate; each metric's worst value may",
        "come from a different run. The threshold itself is simulated by the",
        "sweep (Part C).",
        "",
        f"- Runs label: {data['label']}",
        f"- Model: {data['model_id']}, temperature {data['temperature']}",
        f"- System prompt SHA-256: `{data['system_prompt_sha256']}`",
        f"- Ticket file SHA-256: `{data['ticket_file_sha256']}`",
        "- Code trees: " + ", ".join(f"{k} `{(v or 'unknown')[:12]}`" for k, v in data["code_trees"].items()),
        "- Runs: " + "; ".join(f"run {r['run']} ({r['date']}, {(r['git_commit'] or 'unknown')[:12]})" for r in data["runs"]),
        "",
        "## Worst of 3",
        "",
        *summary_table({n: s["worst"] for n, s in data["sets"].items()}, " (worst)"),
        "",
        "| Set | AC1 meets target | AC2 meets target | Passed in all 3 runs (not a gate) |",
        "|---|---|---|---|",
    ]
    for name in SETS:
        s = data["sets"][name]
        out.append(
            f"| {name} | {fmt_flag(s['worst']['ac1_meets_target'])} | {fmt_flag(s['worst']['ac2_meets_target'])} | "
            f"{s['tickets_passed_in_all_runs']}/{s['n_tickets']} |"
        )
    for name in SETS:
        s = data["sets"][name]
        out += ["", f"### Per run: {name} set", ""]
        out += ["| Run | AC1 | AC2 | Wrong escalation | Both articles cited |", "|---|---|---|---|---|"]
        for run, r in zip(data["runs"], s["per_run"]):
            out.append(
                f"| {run['run']} | {fmt_rate(r['ac1'])} | {fmt_rate(r['ac2'])} | {fmt_rate(r['wrong_escalation'])} | "
                f"{fmt_rate(r['both_cited'])} |"
            )
        out += ["", "Per category (worst of 3): "
                + ", ".join(f"{c} {fmt_rate(v)}" for c, v in s["worst"]["per_category"].items())]

    full = data["sets"][FULL]
    out += ["", "## Unstable tickets (clarification 4)", "",
            "Status or AC pass/fail differs between runs; wording alone does not count.", ""]
    unstable = [t for t in data["tickets"] if t["unstable"]]
    out += ticket_runs_table(unstable) if unstable else ["None."]
    out += ["", "## Tickets that failed in at least one run", ""]
    failed = [t for t in data["tickets"] if not t["passed_all_runs"]]
    out += ticket_runs_table(failed) if failed else ["None."]
    out += ["", "## Escalate tickets to watch (notes/step9-retrieval-review.md)", ""]
    out += ticket_runs_table(data["watch_tickets"]) if data["watch_tickets"] else ["None in this ticket set."]

    out += ["", "## failed_check and escalation reasons per run (full set)", "",
            "| Run | failed_check | Escalation reasons |", "|---|---|---|"]
    for run, r in zip(data["runs"], full["per_run"]):
        out.append(
            f"| {run['run']} | {', '.join(f'{k} {v}' for k, v in r['failed_check_counts'].items()) or 'none'} | "
            f"{', '.join(f'{k} {v}' for k, v in r['escalation_reason_counts'].items()) or 'none'} |"
        )
    total = data["usage_total"]
    out += ["", "## Tokens and cost", "", "| Run | Model calls | Input tokens | Output tokens | Malformed | Cost |",
            "|---|---|---|---|---|---|"]
    for u in data["usage"]:
        out.append(f"| {u['run']} | {u['model_calls']} | {u['input_tokens']:,} | {u['output_tokens']:,} | "
                   f"{u['malformed_outputs']} | {fmt_usd(u['cost_usd'])} |")
    out.append(f"| total | {total['model_calls']} | {total['input_tokens']:,} | {total['output_tokens']:,} | "
               f"{total['malformed_outputs']} | {fmt_usd(total['cost_usd'])} |")
    out += ["", f"Malformed model outputs: {total['malformed_outputs']}. They have no token counts but are still "
            "billed, so the cost is slightly underestimated for them."]
    return "\n".join(out) + "\n"


def ticket_runs_table(tickets: list[dict]) -> list[str]:
    out = ["| Ticket | Set | Expected | Top score | Run 1 | Run 2 | Run 3 |", "|---|---|---|---|---|---|---|"]
    for t in tickets:
        cells = []
        for v in t["runs"]:
            text = v["status"] + (f" ({v['escalation_reason']})" if v["escalation_reason"] else "")
            if v["failed_check"]:
                text += f" [{v['failed_check']}]"
            if v["cited"]:
                text += f" cites {', '.join(v['cited'])}"
            cells.append(text + (" ✓" if v["pass"] else " ✗"))
        out.append(f"| {t['ticket_id']} | {t['split']} | {t['expected']} | {fmt_score(t['top_score'])} | "
                   + " | ".join(cells) + " |")
    return out


# --- Part C: confirmation run --------------------------------------------------------


def fmt_compared(name: str, value) -> str:
    if name == "top_score":
        return fmt_score(value)
    if name == "ac_pass":
        return "pass" if value else "fail"
    return str(value) if value else "–"


def confirm_markdown(data: dict) -> str:
    c = data["comparison"]
    if not data["valid"]:
        verdict = "**INVALID: re-run it (spec 05)**"
    elif c["match"]:
        verdict = f"**MATCH**: {c['tickets_matching']}/{c['tickets_compared']} tickets agree with all 3 runs"
    else:
        verdict = (f"**DIFFERENCES**: {len(c['tickets_differing'])} of {c['tickets_compared']} tickets differ "
                   f"({', '.join(c['tickets_differing'])})")
    code = data["code_since_runs"]
    out = [
        f"# Part C: confirmation run at threshold {data['threshold']} ({data['label']})",
        "",
        "Spec 05, Part C: \"After the threshold is chosen, one confirmation run of",
        "the real flow at that threshold checks the simulation matched.\" Every",
        "ticket went through QueryFlow with the real model at the threshold in",
        "query/config.py (read as the real bot reads it; no other source). Each",
        "ticket's real outcome is compared with the sweep's simulated outcome at",
        "the same threshold, for each of the 3 Part B runs. A ticket matches only",
        "if it agrees with all 3. Handoffs went to the evaluation-only file below,",
        "never to handoffs/.",
        "",
        f"- Result: {verdict}",
        f"- Tickets run: {data['tickets_run']}/{data['tickets_total']}",
    ]
    if data["stopped"]:
        out.append(f"- Stopped at {data['stopped']['ticket_id']}: {data['stopped']['reason']}")
    if data["incomplete_handoff_records"]:
        out.append(f"- **Incomplete handoff records (criterion 3):** {', '.join(data['incomplete_handoff_records'])}")
    trees = ", ".join(f"{k} `{(v or 'unknown')[:12]}`" for k, v in data["code_trees"].items())
    out += [
        *provenance_lines(data),
        f"- Code trees at HEAD: {trees}",
        "- query/ files changed since the Part B runs: "
        + (", ".join(code["query_files_changed_since_runs"]) or "none")
        + "; evals/*.py changed: " + ("yes (this command)" if code["evals_code_changed_since_runs"] else "no"),
        f"- Model: {data['model_id']}, temperature {data['temperature']}, max output tokens {data['max_output_tokens']}",
        f"- System prompt SHA-256: `{data['system_prompt_sha256']}`",
        f"- KB version: {data['kb_version']}; threshold {data['threshold']} from {data['threshold_source']}",
        f"- Handoffs: `{data['handoffs_file']}` ({data['handoff_records']} records)",
        "- Part B runs simulated:",
        *[f"  - `{r['file']}` (SHA-256 `{r['sha256'][:16]}…`)" for r in data["part_b_runs"]],
        *usage_lines(data),
    ]
    if data["summary"]:
        out += ["", "## Results at this threshold", "", "Real run:", "", *summary_table(data["summary"]), "",
                "Simulated by the sweep (worst of the 3 runs):", "",
                "| Set | AC1 | AC2 | Wrong escalation |", "|---|---|---|---|"]
        for name in SETS:
            w = data["simulated"][name]["worst"]
            out.append(f"| {name} | {fmt_rate(w['ac1'])} | {fmt_rate(w['ac2'])} | {fmt_rate(w['wrong_escalation'])} |")
        out += ["", "| Set | AC1 meets target | AC2 meets target (real run) |", "|---|---|---|"]
        for name in SETS:
            s = data["summary"][name]
            out.append(f"| {name} | {fmt_flag(s['ac1_meets_target'])} | {fmt_flag(s['ac2_meets_target'])} |")
    if c is not None:
        out += ["", "## Against the simulation", "",
                "Compared per ticket and per run: " + ", ".join(c["compared_fields"]) + ".", ""]
        if not c["differences"]:
            out.append("No differences.")
        else:
            out += ["| Ticket | Set | Expected | Run | Field | Real | Simulated |", "|---|---|---|---|---|---|---|"]
            for d in c["differences"]:
                out.append(f"| {d['ticket_id']} | {d['split']} | {d['expected']} | {d['run']} | {d['field']} | "
                           f"{fmt_compared(d['field'], d['real'])} | {fmt_compared(d['field'], d['simulated'])} |")
        out += ["", "## All tickets (real run)", "",
                "| Ticket | Set | Expected | Top score | Status | Reason | failed_check | Cited | Pass | Matches |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        for t in c["tickets"]:
            r = t["real"]
            out.append(
                f"| {t['ticket_id']} | {t['split']} | {t['expected']} | {fmt_score(r['top_score'])} | {r['status']} | "
                f"{r['escalation_reason'] or '–'} | {r['failed_check'] or '–'} | {', '.join(r['cited']) or '–'} | "
                f"{fmt_flag(r['ac_pass'])} | {'yes' if t['match'] else '**no**'} |"
            )
    return "\n".join(out) + "\n"


# --- Rescoring after a label review (spec 05 v1.8) ---------------------------------


def fmt_label(label: dict) -> str:
    ids = ", ".join(label["expected_article_ids"]) or "–"
    match = f" ({label['article_match']})" if len(label["expected_article_ids"]) > 1 else ""
    return f"{label['expected']}: {ids}{match}"


def fmt_delta(before: dict, after: dict) -> str:
    if before["total"] != after["total"]:
        return "total changed"
    diff = after["passed"] - before["passed"]
    return "–" if diff == 0 else f"{diff:+d}"


def rescore_markdown(data: dict) -> str:
    out = [
        "# Part B: rescoring after a label review",
        "",
        "Spec 05 v1.8. The same 3 Part B runs (no model calls), scored BEFORE with",
        "the ticket file they were made on and AFTER with the revised ticket file.",
        "Only expected, expected_article_ids and article_match differ between the",
        "two files (checked). Worst of 3 as in Part B (clarification 1), at",
        "threshold -1.0. The original run files and reports are unchanged.",
        "",
        f"- Runs label: {data['label']}",
        f"- Model: {data['model_id']}, temperature {data['temperature']}",
        f"- Ticket file BEFORE: `{data['ticket_file_sha256_before']}` (git {(data.get('ticket_file_commit_before') or 'unknown')[:12]})",
        f"- Ticket file AFTER: `{data['ticket_file_sha256_after']}`",
        "- Runs: " + "; ".join(f"run {r['run']} ({r['date']}, {(r['git_commit'] or 'unknown')[:12]})" for r in data["runs"]),
        "",
        "## Changed labels",
        "",
    ]
    if data["label_changes"]:
        out += ["| Ticket | Set | BEFORE label | AFTER label | Run 1 | Run 2 | Run 3 | Pass/fail changed |",
                "|---|---|---|---|---|---|---|---|"]
        for c in data["label_changes"]:
            cells = []
            for v in c["runs"]:
                text = v["status"] + (f" ({v['escalation_reason']})" if v["escalation_reason"] else "")
                if v["cited"]:
                    text += f" cites {', '.join(v['cited'])}"
                mark = lambda p: "✓" if p else "✗"  # noqa: E731
                cells.append(f"{text}: {mark(v['pass_before'])} → {mark(v['pass_after'])}")
            out.append(
                f"| {c['ticket_id']} | {c['split']} | {fmt_label(c['before'])} | {fmt_label(c['after'])} | "
                + " | ".join(cells) + f" | {'**yes**' if c['pass_changed'] else 'no'} |"
            )
    else:
        out.append("None (the files differ only in formatting).")
    out += ["", "Tickets whose pass/fail changed: " + (", ".join(data["pass_changed"]) or "none") + "."]

    out += ["", "## BEFORE and AFTER per set (worst of 3)", ""]
    for name in SETS:
        b, a = data["sets"][name]["before"], data["sets"][name]["after"]
        out += [f"### {name} set ({b['n_tickets']} tickets)", "",
                "| Metric | BEFORE | AFTER | Change |", "|---|---|---|---|"]
        rows = (
            (f"AC1 (target {AC1_TARGET_PCT}%)", "ac1"),
            (f"AC2 (target {AC2_TARGET_PCT}%)", "ac2"),
            ("Wrong escalation", "wrong_escalation"),
            ("Both articles cited", "both_cited"),
        )
        for title, key in rows:
            out.append(f"| {title} | {fmt_rate(b['worst'][key])} | {fmt_rate(a['worst'][key])} | "
                       f"{fmt_delta(b['worst'][key], a['worst'][key])} |")
        out += [
            f"| AC1 meets target | {fmt_flag(b['worst']['ac1_meets_target'])} | {fmt_flag(a['worst']['ac1_meets_target'])} | |",
            f"| AC2 meets target | {fmt_flag(b['worst']['ac2_meets_target'])} | {fmt_flag(a['worst']['ac2_meets_target'])} | |",
            f"| Passed in all 3 runs (not a gate) | {b['tickets_passed_in_all_runs']}/{b['n_tickets']} | "
            f"{a['tickets_passed_in_all_runs']}/{a['n_tickets']} | "
            f"{a['tickets_passed_in_all_runs'] - b['tickets_passed_in_all_runs']:+d} |",
            "",
            "Unstable BEFORE: " + (", ".join(b["unstable"]) or "none")
            + "; AFTER: " + (", ".join(a["unstable"]) or "none") + ".",
            "",
        ]
    return "\n".join(out).rstrip() + "\n"
