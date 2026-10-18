#!/usr/bin/env bash
# Decide whether the evaluation gate must run (spec 06, Workflow 2).
#
# Reads changed file paths (one per line) on stdin. Prints "run=true" if any
# of them is in a gate path, otherwise "run=false", for $GITHUB_OUTPUT.
# Matching paths are listed on stderr for the log.
set -euo pipefail

# Spec 06 v1.1: query/, ingestion/, data/, evals/ (folders), two exact files,
# and the CI files that run the gate: its workflow, .github/actions/ and
# .github/scripts/.
pattern='^(query/|ingestion/|data/|evals/|specs/02-query-escalation-spec\.md$|requirements\.txt$'
pattern+='|\.github/workflows/evaluation-gate\.yml$|\.github/actions/|\.github/scripts/)'

matches=$(grep -E "$pattern" || true)
if [ -n "$matches" ]; then
  echo "Gate paths changed:" >&2
  printf '  %s\n' "$matches" >&2
  echo "run=true"
else
  echo "No gate paths changed." >&2
  echo "run=false"
fi
