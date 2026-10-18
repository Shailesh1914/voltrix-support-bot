CI pipeline workflow definitions (spec 06, Session D).

- structural-tests.yml (Workflow 1): every push and pull request. Builds
  kb_v1 and kb_v2, then runs tests/structural/{ingestion,query,evals}
  separately. A skipped test fails CI (../scripts/check_no_skips.py).
- evaluation-gate.yml (Workflow 2): pull requests to main, and manual start.
  Always reports a result. It runs the paid gate only when the PR changes
  query/, ingestion/, data/, evals/, specs/02-query-escalation-spec.md,
  requirements.txt, or the CI files that run the gate (evaluation-gate.yml,
  ../actions/, ../scripts/) (../scripts/gate_needed.sh, spec 06 v1.1). Otherwise it passes as
  "not needed". The report is uploaded as the artifact evaluation-gate-report.
- ../actions/setup-bot: shared setup (Python 3.14, requirements, cached
  embedding model keyed by MODEL_REVISION, index build).

Required checks for branch protection: structural-tests, evaluation-gate.
