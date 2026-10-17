# Search observations from Step 7d (kb_v1, no prefix, k=5)

- T-102 style (symptom wording, no fault code): KB-001 not in top 20.
  Nearest relevant: KB-009 at rank 6.
- T-103 style: KB-034 at rank 3; KB-020 at rank 1 also contains
  the 5-minute wait.
- T-109 style (pricing, should escalate): highest score of the
  three, 0.73. Threshold alone cannot catch it.
- All scores in a narrow band: 0.59-0.73.
- My view after reading KB-001: <your expert opinion>
- CI note: full ingestion suite takes ~3.5 min (idempotence test is
  the slowest). Consider fast/slow split in Step 11.
- KB content improvement for a future version: real drive manuals
  mark hazards with WARNING / DANGER / CAUTION lines; our KB has
  none. Consider adding them (with symptom wording for fault
  articles) in a kb_v3.
- Step 13 note: config requires AWS_PROFILE; on AWS the bot will
  use an IAM role instead, so this must be relaxed then. This is done
- Step 13 note: an empty or whitespace-only question raises an
  error (no handoff). The user interface must show a friendly
  "Please type a question" message instead of an error.
- Step 9 prompt experiments: (a) whether to allow answering from
  a clearly matching symptom description (T-102 style);
  (b) schema field order: decision first vs answer first.

## Notes for later steps
- Step 9 experiment: compare Claude Haiku 4.5 (pinned) with
  Claude Haiku 5.5 (newer, cheaper, adaptive thinking) on the same
  70 tickets. Check whether Haiku 5.5's ID is a fixed snapshot and
  how thinking interacts with forced tool use and temperature 0.
- Step 9 note: the anthropic SDK 1.x sends temperature via
  extra_body. Haiku 5.5 rejects any non-default temperature, so a
  Haiku 5.5 comparison needs a spec decision on temperature first.
- Step 11 note: running all test folders together can fail at
  import (several conftest.py files; plain pytest cannot find the
  ingestion package). CI must use a command or pytest config that
  runs every folder reliably, e.g. python -m pytest per folder.
  Ingestion suite takes ~4.5 min.
- Step 11 note: test_query_cli.py:46 now always skips ("would run
  the real bot") because the threshold is set. Ask Session Q to
  rewrite it so it still tests the refusal without calling the
  real model.