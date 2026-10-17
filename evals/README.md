Labelled question set for the evaluation suite.

# Evaluation (spec 05, Session E)

Run from the repository root with the project virtual environment:

    .venv/bin/python -m evals.run_eval part-a --label LABEL                    # label optional
    .venv/bin/python -m evals.run_eval part-b --label LABEL --run 1            # free dry run
    .venv/bin/python -m evals.run_eval part-b --label LABEL --run 1 --confirm  # PAID, Shailesh only
    .venv/bin/python -m evals.run_eval aggregate --runs RUN1.json RUN2.json RUN3.json
    .venv/bin/python -m evals.run_eval sweep --runs RUN1.json RUN2.json RUN3.json

Only `part-b --confirm` calls the model. Reports go to
`evals/reports/<date>-<name>.json` and `.md`; an existing report is never
replaced unless `--overwrite` is given (Part B files are never replaced).

## Part A: retrieval report

Every ticket goes through `QueryFlow` (threshold -1.0, a stand-in generator
that never calls the model). The final retrieved chunks, the ones the flow's
own retrieval (spec 02 step 3) produced, are read from each ticket's handoff
record. The top score is the highest score among them. Part A fails if a
query reaches `search()` with the BGE prefix already in it, because `search()`
adds the prefix itself (spec 03 v1.4).

Since spec 02 v1.14 the flow reads every chunk of the selected articles
(step 3e, `article_chunks()`) before the model call. Part A records what
would be read and fails if the flow reads anything other than the step-d
articles in step-d order. The top score is still step d's.

The report also compares every ticket with the committed Part A2 E1+E2+E3
simulation. Spec 05 v1.6: article ids (in order), recall, both-articles
recall and top score decide the match; chunk ids, the query and the texts
searched are listed as information only.

`--label` adds a suffix to the report name (`<date>-part-a-retrieval-<label>`),
so a report of new code never replaces one of old code.

Exit codes: 0 = report written and it matches Part A2; 3 = report written but
it differs from Part A2 (see "Against the Part A2 simulation"); 1 = error,
nothing written.

## Part A2: retrieval experiments (completed)

Completed on 2026-10-17; E1+E2+E3 adopted. Its simulation added the prefix
itself, so it cannot be re-run now that `search()` adds it.
`python -m evals.run_eval part-a2` refuses. The evidence is
`reports/2026-10-17-part-a2-retrieval-experiments.md`; `eval_experiments.py`
is kept as the record of how it was computed.

## Part B: full-flow runs (real model)

Every ticket goes through `QueryFlow` with the real `AnthropicGenerator` at
threshold -1.0. The -1.0 is passed to the flow directly, for the evaluation
only: `query/config.py` is never read for it or changed, and the real bot
still refuses to start while `ESCALATION_THRESHOLD` is unset. The
unknown-fault-code check stays active.

- Without `--confirm` (dry run, free): the flow runs with a stand-in
  generator, counts the planned model calls and estimates the cost from the
  exact requests the real generator would send. No key is loaded, nothing is
  called or written.
- `--confirm` (paid): refuses if more than 100 calls are planned, if a valid
  file for that run number already exists, or if `query/`, `ingestion/`,
  `evals/*.py` or `specs/` have uncommitted changes. A 101st model call is
  refused during the run too.
- One run per command: `--run 1`, `2`, `3`, always with `--label` (lowercase
  words joined by hyphens, e.g. `whole-articles`). Files are named
  `<date>-part-b-<label>-runN`. A label is one set of 3 runs: runs with
  different labels never block each other. The unlabelled
  `2026-10-17-part-b-run1` (pilot, old code) stays as evidence; it can never
  be aggregated with labelled runs.
- Top score and retrieved chunks are step d's (spec 02). The model now reads
  whole articles (scores 0.0), so they come from the free planning pass that
  runs before every paid run (its handoff records hold the step-d chunks with
  scores). The paid run is checked against it: an escalation's handoff must
  hold the same chunks, and the model must read exactly the step-d articles.
  Any difference stops the run as invalid.
- The dry-run estimate is built from the exact requests, which now carry the
  whole selected articles; it also prints how many articles and chunks the
  model reads. (Run 1 estimated 169,812 input tokens and used 145,562.)
- Per ticket: top score, status, escalation_reason, citations, failed_check,
  rejected_answer, the answer text, the model's own output and token counts.
- Handoffs go to `reports/<date>-part-b-runN-handoffs.jsonl`, never to
  `handoffs/`; the run fails if `handoffs/` changes.
- The run stops at the first `service_error`. It is written as
  `<date>-part-b-runN-invalid-<k>` (kept as evidence; never blocks a re-run).
  Repeat the same `--run N --confirm` command.
- Malformed model outputs have no token counts (they are still billed); the
  report counts them and says the cost is slightly underestimated.

Exit codes: 0 = valid run written (or dry run done); 4 = service_error,
invalid run written, re-run it; 1 = error (an invalid run is written only if
paid calls were already made).

## Part B aggregate

`aggregate` takes the 3 valid runs (1, 2 and 3, with the same label, the
same code trees for `query/`, `ingestion/` and `evals/*.py`, and the same
model, prompt, tickets and KB; anything else is refused) and reports, per set at threshold -1.0: each
metric per run and its worst value (lowest for success rates, highest for
wrong escalation; clarification 1), unstable tickets (status or AC
pass/fail differs; clarification 4), tickets that passed in all 3 runs,
failed_check counts, tokens and cost. Output: `<date>-part-b-<label>-aggregate`.
`sweep` applies the same check to its 3 runs; output: `<date>-part-c-<label>-sweep`.

## Files

- `support_questions.jsonl`: the labelled tickets (frozen, never edited)
- `run_eval.py`: command line runner
- `eval_tickets.py`: loading tickets, calibration/holdout split
- `eval_recorders.py`: wrappers passed into `QueryFlow`
- `eval_part_b.py`: Part B plan, call limit, usage recording, run files
- `eval_aggregate.py`: worst of the 3 Part B runs, unstable tickets
- `eval_scoring.py`: AC1, AC2, metrics, retrieval recall
- `eval_compare.py`: Part A against the Part A2 simulation
- `eval_experiments.py`: Part A2 experiments (history)
- `eval_sweep.py`: Part C threshold sweep
- `eval_report.py`: report files and Markdown
- `uncovered-topics.md`: topics deliberately not in the knowledge base (used to write escalate tickets)
