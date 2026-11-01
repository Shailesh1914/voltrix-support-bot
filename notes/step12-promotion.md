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