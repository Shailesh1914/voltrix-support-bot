Labelled question set for the evaluation suite.

# Evaluation (spec 05, Session E)

Run from the repository root with the project virtual environment:

    .venv/bin/python -m evals.run_eval part-a
    .venv/bin/python -m evals.run_eval sweep --runs RUN1.json RUN2.json RUN3.json

Both are free (no model calls). Reports go to `evals/reports/<date>-<name>.json`
and `.md`; an existing report is never replaced unless `--overwrite` is given.

## Part A: retrieval report

Every ticket goes through `QueryFlow` (threshold -1.0, a stand-in generator
that never calls the model). The final retrieved chunks, the ones the flow's
own retrieval (spec 02 step 3) produced, are read from each ticket's handoff
record. The top score is the highest score among them. Part A fails if a
query reaches `search()` with the BGE prefix already in it, because `search()`
adds the prefix itself (spec 03 v1.4).

The report also compares every ticket with the committed Part A2 E1+E2+E3
simulation (query, texts searched, final chunks, top score, recall).

Exit codes: 0 = report written and it matches Part A2; 3 = report written but
it differs from Part A2 (see "Against the Part A2 simulation"); 1 = error,
nothing written.

## Part A2: retrieval experiments (completed)

Completed on 2026-10-17; E1+E2+E3 adopted. Its simulation added the prefix
itself, so it cannot be re-run now that `search()` adds it.
`python -m evals.run_eval part-a2` refuses. The evidence is
`reports/2026-10-17-part-a2-retrieval-experiments.md`; `eval_experiments.py`
is kept as the record of how it was computed.

## Files

- `support_questions.jsonl`: the labelled tickets (frozen, never edited)
- `run_eval.py`: command line runner
- `eval_tickets.py`: loading tickets, calibration/holdout split
- `eval_recorders.py`: wrappers passed into `QueryFlow`
- `eval_scoring.py`: AC1, AC2, metrics, retrieval recall
- `eval_compare.py`: Part A against the Part A2 simulation
- `eval_experiments.py`: Part A2 experiments (history)
- `eval_sweep.py`: Part C threshold sweep
- `eval_report.py`: report files and Markdown
- `uncovered-topics.md`: topics deliberately not in the knowledge base (used to write escalate tickets)
