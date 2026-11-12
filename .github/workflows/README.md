CI pipeline workflow definitions (spec 06, Session D).

- structural-tests.yml (Workflow 1): every push and pull request. Builds
  kb_v1 and kb_v2, then runs tests/structural/{ingestion,query,web,evals}
  separately (spec 06 v1.2). A skipped test fails CI (../scripts/check_no_skips.py).
- evaluation-gate.yml (Workflow 2): pull requests to main, and manual start.
  Always reports a result. It runs the paid gate only when the PR changes
  query/, ingestion/, data/, evals/, specs/02-query-escalation-spec.md,
  requirements.txt, or the CI files that run the gate (evaluation-gate.yml,
  ../actions/, ../scripts/) (../scripts/gate_needed.sh, spec 06 v1.1). Otherwise it passes as
  "not needed". It builds only the index of the version in
  data/ACTIVE_KB_VERSION (spec 07), so a pull request that changes that file
  runs the gate on the new version (data/ is a gate path). The report is
  uploaded as the artifact evaluation-gate-report.
- ../actions/setup-bot: shared setup (Python 3.14, requirements, cached
  embedding model keyed by MODEL_REVISION, index build). Inputs: kb-folders
  (fixed folders) and/or active-kb: "true" (the active version, read with the
  bot's own reader via ../scripts/active_kb_version.py).

Required checks for branch protection: structural-tests, evaluation-gate.
