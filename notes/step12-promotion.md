# Step 12 — Index promotion kb_v1 -> kb_v2 (Shailesh, 2026-11-01)

## What changed in kb_v2
- Updated KB-001: restarting after a coast stop -> flying start
  (P-11) or let the motor stop completely.
- Updated KB-006: trip level lowered 350 -> 320 V DC (rides through
  more dips); new step: automatic restart (P-09) if the machine is
  safe to restart on its own.
- Updated KB-028: fault codes up to E-17; a factory reset also
  disables automatic restart, flying start and underload detection.
- New: KB-037 (E-17 motor underload), KB-038 (automatic restart),
  KB-039 (flying start).

## Label decisions (based on the KB text)
| Ticket | Decision | Reason |
|---|---|---|
| T-105 | Expected: KB-006 or KB-038 ("any") | v2 KB-006 says no restart by default and points to KB-038, which answers "doesn't start again by itself" |
| T-006 | Expected: KB-006 or KB-038 ("any") | v2 KB-006 offers drive-side options: lower trip level and automatic restart (KB-038) |
| T-001, T-030, T-102 | Keep | KB-001 still the right article |
| T-015, T-031, T-032, T-104 | Keep | KB-028 still the right article |
| Escalate tickets | Keep | No new topic covers them |
Adding KB-038 does not change v1 scores (v1 has no KB-038).

## Watch points
- Automatic restart is a safety topic: answers must keep the
  condition "only if the machine is safe to restart on its own".
- No ticket tests the NEW content (E-17, flying start, automatic
  restart as a topic). The v2 evaluation proves "no regression",
  not that new content is found. Add such tickets next iteration.
- Also fix later: the stray line "CI: first structural-tests run
  passed" sits under "Next iteration" in step10-review.md.

## Free retrieval check (spec 07 step 3), 2026-11-01
| Set | v1 recall | v2 recall |
|---|---|---|
| Calibration | 23/24 | 23/24 |
| Holdout | 23/24 | 23/24 |
| Full | 46/48 | 46/48 |
Both articles: 7/9 on both. No regression.
- 46 (not 45 as in Step 9) because of the reviewed labels: T-039
  now accepts KB-036, which retrieval already found.
- Lowest found-answer score: v1 0.6435, v2 0.6439. The 0.60
  threshold keeps its margin on v2; no flag needed.
- Chunks read per full run: v1 1,547, v2 1,561 (about 1% more).

## Promotion attempt 1 (PR #5, 2026-11-08): BLOCKED by the gate
- Gate on kb v2: AC1 40/48 (83.3%), AC2 22/22; on v1: AC1 41/48.
- Regressed ticket: T-002 (E-02 on deceleration). Failed grounding:
  the draft said "3 seconds to 6 seconds"; KB-002 says to double the
  deceleration time. Claude calculated "6 seconds", which is in no
  article. Citations (KB-002, KB-025) were correct.
- Cause: a fragile bot habit (same as T-005 since Step 9), exposed by
  slightly different reading on v2. Not a v2 content error.
- Fix: prompt rule against calculated values (spec 02 decision 15),
  tested on v1 first, then the promotion is retried.
- Cost of the blocked attempt: $0.3861.
- First rule wording missed suggested example values (local T-005
  check: "try 15 s or 20 s"). Revised rule: T-005 answered locally.

## Fix and successful promotion (2026-11-09)
- Prompt rule added (spec 02 decision 15, PR #6): never calculate or
  suggest values. The first wording missed suggested example values
  ("try 15 s or 20 s", local T-005 check); the revised wording works.
- Gate on v1 after the fix (PR #6): AC1 43/48 (89.6%), AC2 22/22
  (was 41/48). The rule also fixed T-005, failing since Step 9.
- Promotion retried (PR #5, updated with main): gate on kb v2
  PASSED, AC1 43/48, AC2 22/22, same as v1. Merged: the bot now
  serves v2 (data/ACTIVE_KB_VERSION = v2).

## Rollback drill (2026-11-09)
- Revert of PR #5 opened as PR #7: gate on kb v1 PASSED, AC1 43/48,
  AC2 22/22 ($0.3838). Closed WITHOUT merging; the bot still serves v2.
- Rollback = one click on "Revert" + a green gate.

## Spec 07 acceptance criteria: all met
1. Version read only from data/ACTIVE_KB_VERSION; .env refused.
2. Gate and Part B evaluate that version (logs show the version).
3. Changing the file runs the gate (PR #5, PR #7).
4. Promotion to v2 passed the gate and was merged (PR #5).
5. Rollback drill passed on v1 and was closed unmerged (PR #7).

## Lessons
- The paid gate caught a regression (T-002) that the free retrieval
  check could not see: retrieval was fine, the model's wording
  changed. Both checks are needed.
- The regression was not a v2 content error but an existing bot
  habit (inventing values) exposed by slightly different reading.
  Fixing the root cause improved v1 too (41 -> 43/48).
- A cheap local check (one question, under 1 rupee) caught that the
  first rule wording was too narrow, before a paid gate run.
- Step 12 model cost: about $1.94 (5 gate runs).