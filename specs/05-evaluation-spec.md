# Evaluation Spec — Voltrix VX-200 Support Bot

Status: Version 1.3, approved by Shailesh on 2026-10-17

## Purpose
Measure spec 02 acceptance criteria 1-2 and metrics, and produce
the evidence Shailesh needs to set ESCALATION_THRESHOLD.
This spec is written BEFORE any evaluation results exist.

## Independence (Section 2.2)
- Built by Session E, which never edits query/, ingestion/, data/,
  specs/ or evals/support_questions.jsonl.
- Uses the bot only through its public parts: QueryFlow,
  AnthropicGenerator and open_retrieval.
- Scoring follows this spec and spec 02, never the bot's code.

## Data split (fixed before any results)
- Calibration set: tickets whose number is ODD (T-001, T-003, ...,
  T-101, T-103, ...). Used to choose the threshold.
- Holdout set: tickets whose number is EVEN. Only measured, never
  used to choose anything.
- Results are reported for calibration, holdout and the full set.

## Part A: Retrieval report (no model calls)
For every ticket, using kb_v1 and search(k=5):
- the top similarity score and the top 5 article_ids.
- Retrieval recall: for "answer" tickets, whether at least one
  expected article is in the top 5; for two-article tickets,
  whether both are.
- Score distributions for "answer" and "escalate" tickets.

## Part A2: Retrieval experiments (no model calls)
Each experiment is simulated through the public retrieval contract
only (open_retrieval, search, kb_info), without changing query/:
- E1: BGE retrieval prefix added to the query text.
- E2: diversity: search(k=20), then the best chunks from up to 5
  different articles.
- E3: code boost: if the normalised question contains a known
  E-xx code, also search with that article's title (from kb_info)
  and merge the results.
- E2+E3 combined.
For each: recall and both-articles recall on calibration, holdout
and full sets, compared with the baseline. Choose using the
calibration set; the holdout set must confirm the improvement.
Adopting an experiment is a spec 02 change, approved by Shailesh.

## Part B: Full-flow run (real model)
- Every ticket goes through QueryFlow with threshold -1.0, so the
  retrieval check never escalates and every model decision is
  recorded. The unknown-fault-code check stays active.
- Per ticket, record: top score, status, escalation_reason,
  citations, failed_check, answer text, token counts.
- Handoffs are written to an evaluation-only file, never to
  handoffs/.
- Part B runs 3 times. The WORST result is used (spec 02).
  Tickets whose outcome differs between runs are listed as unstable.
- Any service_error makes that run invalid; it must be re-run.

## Part C: Threshold sweep (no extra model calls)
- For each candidate threshold t from 0.50 to 0.90 in steps of
  0.01: a ticket escalates if its top score < t, otherwise it gets
  its Part B outcome.
- For each t, report AC1, AC2 and the wrong-escalation rate, on the
  calibration set.
- Report which values of t meet the targets. The report does NOT
  choose the threshold; Shailesh does.
- After the threshold is chosen, one confirmation run of the real
  flow at that threshold checks the simulation matched.

## Scoring
- AC1 (target 85%): an "answer" ticket counts if the response is
  answered AND cites at least one of its expected_article_ids.
- AC2 (target 95%): an "escalate" ticket counts if the response is
  escalated with any reason except service_error.
- Metrics (not gates): wrong-escalation rate, both-articles-cited
  rate for two-article tickets, results per category, counts of
  failed_check values, total tokens and estimated cost.
- Answer quality beyond criterion 7 is not scored automatically.
  All answers are saved for human review in Step 10.

## Clarifications (Version 1.1)
1. WORST result: for each metric, the worst value across the 3
   runs: the LOWEST value for success rates (AC1, AC2,
   both-articles-cited rate) and the HIGHEST value for error rates
   (wrong-escalation rate). For the sweep, each run is simulated
   separately and the worst value per threshold is reported, using
   the same rule. Also reported (not a gate): the number of tickets
   that passed in all 3 runs.
2. Tickets with "article_match": "any" (e.g. T-101): any one
   expected article counts as correct. They are excluded from the
   both-articles-cited metric and reported separately.
3. Part A searches the flow's own masked and normalised query, so
   its scores equal the scores used by the sweep.
4. Unstable ticket: its status, or its AC pass/fail, differs between
   runs. Different answer wording alone does not count.
5. All outputs are committed: summary reports, per-run .json files
   and handoff .jsonl files (all data is synthetic).
6. On the calibration set, AC2 effectively requires 11/11. A failing
   escalate ticket is investigated, not explained away by lowering
   the target.

## Cost control
- The runner shows the number of planned model calls and the
  estimated cost, and runs only with an explicit --confirm flag.
- Hard limit: 100 model calls per run.
- Only Shailesh runs the paid parts (B and the confirmation run).

## Outputs
- evals/reports/<YYYY-MM-DD>-<name>.json and .md, committed to Git.

## Experiments (only after the baseline, each a separate decision)
- BGE query prefix (Part A only, free).
- Prompt wording for symptom questions (needs a prompt change,
  decision 10 of spec 02).
- Claude Haiku 5.5 (needs a temperature decision, see notes).