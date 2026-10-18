# CI Spec — Voltrix VX-200 Support Bot

Status: Version 1.1, approved by Shailesh on 2026-10-18

## Goal (Section 2.3)
Structural tests run on every push. The evaluation gate runs on pull
requests to main. Nothing reaches main unless both pass.

## Working method
- Changes are made on branches and merged to main through pull
  requests. main is protected: direct pushes are not allowed, and
  both checks below must pass before merging.

## Workflow 1: structural tests
- Runs on every push to any branch and on every pull request.
- Python 3.14 (same as development); requirements.txt as pinned
  (CPU-only torch).
- The pinned embedding model is cached between runs.
- Builds the kb_v1 and kb_v2 indexes, then runs each test folder
  separately: tests/structural/ingestion, tests/structural/query,
  tests/structural/evals. All must pass; no test may call the model.

## Workflow 2: evaluation gate
- Runs on pull requests to main ONLY when the pull request changes
  query/, ingestion/, data/, evals/,
  specs/02-query-escalation-spec.md, requirements.txt, or the CI
  files that run the gate (.github/workflows/evaluation-gate.yml,
  .github/actions/, .github/scripts/). Can also be started manually.
- One full-flow run of all tickets with the real model at the
  threshold in query/config.py.
- Passes only if, on the full ticket set, AC1 >= 85% and
  AC2 >= 95% (spec 02). Otherwise the pull request is blocked.
- One run (not three) because the runs were shown to be identical
  (Step 9). Three runs remain required for threshold decisions.
- The report is kept as a downloadable artifact of the CI run.
- Limits: 100 model calls per run. The API key comes from the
  GitHub secret VOLTRIX_ANTHROPIC_API_KEY and is never printed.

## Acceptance criteria
1. A deliberately failing structural test blocks the pull request.
2. A pull request that only changes notes/ or other documentation
   does not run the evaluation gate.
3. The gate fails when AC1 or AC2 is below target (tested with
   fakes, without model calls).
4. The API key never appears in any log.
5. Both workflows pass on main after setup.