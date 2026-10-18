Labelled question set for the evaluation suite.

# Evaluation (spec 05, Session E)

Run from the repository root with the project virtual environment:

    .venv/bin/python -m evals.run_eval part-a --label LABEL                    # label optional
    .venv/bin/python -m evals.run_eval part-b --label LABEL --run 1            # free dry run
    .venv/bin/python -m evals.run_eval part-b --label LABEL --run 1 --confirm  # PAID, Shailesh only
    .venv/bin/python -m evals.run_eval aggregate --runs RUN1.json RUN2.json RUN3.json
    .venv/bin/python -m evals.run_eval sweep --runs RUN1.json RUN2.json RUN3.json
    .venv/bin/python -m evals.run_eval confirm --runs RUN1.json RUN2.json RUN3.json            # free dry run
    .venv/bin/python -m evals.run_eval confirm --runs RUN1.json RUN2.json RUN3.json --confirm  # PAID, Shailesh only
    .venv/bin/python -m evals.run_eval rescore --runs RUN1.json RUN2.json RUN3.json

Only `part-b --confirm` and `confirm --confirm` call the model. Reports go to
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

## Part B rescoring after a label review (spec 05 v1.8)

`rescore` takes the same 3 Part B run files as `aggregate` and scores them
twice, without model calls: BEFORE with the ticket file the runs were made
on, AFTER with the current `support_questions.jsonl`. The runs record only
their ticket file's SHA-256, so the original file is taken from git history
(the committed version with exactly that SHA); none found = refused.

- Refuses unless both files hold the same ticket ids and every field other
  than `expected`, `expected_article_ids` and `article_match` is identical
  (question, category, notes, any other field). An absent `article_match`
  equals `"all"`.
- Also refuses: the runs do not belong together (same rule as `aggregate`),
  the labels stored in the run rows differ from the original file, or the
  ticket file is unchanged (use `aggregate`).
- Reports per set (calibration, holdout, full) AC1, AC2, wrong escalation,
  both-articles-cited and tickets passed in all 3 runs, BEFORE and AFTER,
  worst of 3; every ticket whose label changed, with pass/fail per run
  before and after; and the tickets whose pass/fail changed. A pass/fail
  change on a ticket whose label did not change stops it as an internal error.
- BEFORE equals the original aggregate. The run files and their reports are
  never touched. Output: `<date>-part-b-<label>-rescore`, kind
  `part-b-rescore` (never readable as a Part B run).

## Part C: confirmation run (real model)

Spec 05, Part C: "After the threshold is chosen, one confirmation run of the
real flow at that threshold checks the simulation matched." `confirm` takes
the same 3 Part B run files as the sweep.

- Threshold: the bot's own, read from `query/config.py` as `query/ask.py`
  reads it (`require_threshold(config.ESCALATION_THRESHOLD)`), when the
  command runs. There is no option for it. The real run and the simulation
  both use this one value. It refuses while the threshold is unset.
- Every ticket goes through `QueryFlow` at that threshold with the real
  `AnthropicGenerator` (unknown-fault-code and retrieval checks active).
- For each ticket and each of the 3 runs, the real top score, status,
  escalation_reason and AC pass/fail are compared with the sweep's simulated
  outcome (`eval_sweep.simulate`) at the same threshold. A ticket matches only
  if it agrees with all 3 runs. The report shows MATCH or every difference,
  and AC1, AC2 and wrong escalation (real, and simulated worst of 3) for
  calibration, holdout and full.
- Free checks before any money is spent (also in the dry run): the 3 runs
  belong together (same rule as the sweep); the model settings and system
  prompt equal the runs'; `ingestion/` is the same tree and in `query/` only
  `config.py` differs; every ticket retrieves exactly the runs' step-d chunks
  and scores.
- Same safeguards as Part B: dry run by default (no key, nothing written),
  `--confirm` to pay, 100-call limit (planned and during the run), refuses
  uncommitted changes, never replaces a valid result (no `--overwrite`),
  handoffs only to `reports/`, the run fails if `handoffs/` changes, and it
  stops at the first `service_error` (written as `...-invalid-<k>`).
- Output: `<date>-part-c-<label>-confirm-t<threshold>.json`, `.md` and
  `-handoffs.jsonl`. Its kind is `part-c-confirm`, so it can never be read as
  a Part B run.

Exit codes: 0 = MATCH (or dry run done); 3 = valid run written but it differs
from the simulation; 4 = service_error, invalid run written, re-run it;
1 = error.

## Evaluation gate for CI (spec 06, Workflow 2)

    .venv/bin/python -m evals.run_eval gate --out-dir DIR            # free dry run (exit 5)
    .venv/bin/python -m evals.run_eval gate --out-dir DIR --confirm  # PAID: what CI runs

One full-flow run of every ticket with the real model, at the threshold in
`query/config.py` (read through the same single reader as `confirm`; there is
no option for it). It passes only if, on the FULL ticket set, AC1 >= 85% and
AC2 >= 95% (spec 02). One run, not three (spec 06).

- Needs the kb_v1 index (`python -m ingestion.build data/kb_v1`); without it
  the gate stops before anything else with a clear error.
- Writes `<date>-gate.json`, `.md` and `-handoffs.jsonl` to `--out-dir`
  (created if needed), for CI to keep as an artifact. Never to `handoffs/`
  (the run fails if `handoffs/` changes). An existing report is never replaced.
- The output folder may be outside the repository or e.g. `evals/reports/`;
  it may not be the repository root, `evals/` itself, or inside or around
  `handoffs/`, `data/`, `query/`, `ingestion/` or `specs/`.
- Same safeguards as Part B: dry run by default (no key, nothing written),
  `--confirm` to pay, 100-call limit (planned and during the run), refuses
  uncommitted changes in `query/`, `ingestion/`, `evals/*.py` or `specs/`.
  Files inside its own output folder never count as such changes. The key
  is read from `VOLTRIX_ANTHROPIC_API_KEY` (in CI: the GitHub secret) and is
  never printed or written.

Exit codes (each means one thing only):

| Code | Meaning |
|---|---|
| 0 | PASSED: AC1 and AC2 meet their targets on the full set |
| 3 | FAILED: a valid run, and AC1 and/or AC2 is below target (the message names which) |
| 4 | service_error: the model API failed (an outage, never a quality result); re-run |
| 5 | dry run: the gate was NOT evaluated (never 0, so a missing `--confirm` cannot pass) |
| 1 | error: no index, threshold unset, refused output folder, uncommitted changes, other invalid run |
| 2 | wrong command-line arguments (argparse) |

## Files

- `support_questions.jsonl`: the labelled tickets (frozen, never edited)
- `run_eval.py`: command line runner
- `eval_tickets.py`: loading tickets, calibration/holdout split
- `eval_recorders.py`: wrappers passed into `QueryFlow`
- `eval_part_b.py`: Part B plan, call limit, usage recording, run files
- `eval_aggregate.py`: worst of the 3 Part B runs, unstable tickets
- `eval_rescore.py`: rescoring the 3 runs after a label review (BEFORE and AFTER)
- `eval_scoring.py`: AC1, AC2, metrics, retrieval recall
- `eval_compare.py`: Part A against the Part A2 simulation
- `eval_experiments.py`: Part A2 experiments (history)
- `eval_sweep.py`: Part C threshold sweep
- `eval_confirm.py`: Part C confirmation run against the sweep's simulation
- `eval_gate.py`: CI evaluation gate (spec 06): verdict on the full set, exit codes, output folder rules
- `eval_report.py`: report files and Markdown
- `uncovered-topics.md`: topics deliberately not in the knowledge base (used to write escalate tickets)
