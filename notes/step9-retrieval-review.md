# Step 9 — Expert review of Part A retrieval misses (2026-10-17)

Reviewer: Shailesh. Baseline: kb_v1, no prefix, k=5, recall 38/48.

## Label checks
Checked T-005, T-014, T-027, T-030, T-101 against the KB: the
expected articles really answer the questions. Labels are correct.

## Misses by pattern
- Pattern 1 (fault code in question, article not found):
  T-004, T-005, T-006, T-014 -> candidate fix: E3 code boost.
- Pattern 2 (one article fills several slots):
  T-015, T-030, T-032 (partial misses) -> candidate fix: E2 diversity.
- Pattern 3 (technician wording / symptoms):
  T-027, T-037, T-038, T-039, T-101, T-102 -> candidate fix:
  kb_v3 content (symptom sections, plain-language safety lines).

## Safety-critical misses
- T-038: "display goes dark, so it's dead" assumption. KB-034 should
  state plainly that a dark display does not mean the DC bus is
  discharged.
- T-039: "pressed STOP, so it's safe" assumption. KB-034 should state
  plainly that the stop button does not isolate the drive.
- T-037: old spare without capacitor re-forming can damage the drive.

## Possible label additions (decide in Step 10, not now)
- T-014: also accept KB-020 / KB-036 ("any")?
- T-038: also accept KB-020 ("any")?
- T-039: also accept KB-036 ("any")?
- T-102: also accept KB-009 ("any")?

## Part A2 combinations (2026-10-17)
- E1+E3: 43/48 (as predicted). Gained T-004, T-005, T-006, T-014,
  T-027.
- E1+E2+E3: 45/48 (better than predicted). Also gained T-037 and
  T-038. E2 alone added almost nothing, but combined with E1 it lets
  KB-033 and KB-034 into the top 5 (interaction effect).
- Both-articles recall E1+E2+E3: 7/9 (baseline 5/9).
- No experiment lost any ticket.

## Decision (2026-10-17, Shailesh)
Adopt E1+E2+E3:
- E1: BGE query prefix in search() (spec 03 v1.3, Session I).
- E2: search k=20, best chunk of each article, up to 5 articles
  (spec 02 v1.12, Session Q).
- E3: code boost via kb_info() titles, merged by score
  (spec 02 v1.12, Session Q).

Reasons:
- Improves calibration (+3) and holdout confirms (+4).
- Loses no ticket.
- Each part has a clear mechanism, not just a better number.
- Recall 94% leaves room for model mistakes above the 85% AC1 target.
- Fixes T-038 (safety question).

## Watch points
- Claude now sees one chunk per article: check answer quality and
  safety warnings in Part B.
- Threshold uses the top score of the final merged list. Re-run
  Part A on the real implementation and confirm 45/48 before the
  sweep.
- No startup check for the query prefix (manifest has no field for
  it). Covered by the "chunks embedded without prefix" test.
  Consider a manifest field with the next re-index (e.g. kb_v3).
- Session E's E1 experiment adds the prefix itself; after search()
  adds it, Session E must stop doing so (handle at the Part A
  re-run). The original no-prefix baseline report stays committed.

## Still missed after E1+E2+E3
- T-039 (safety: STOP is not isolation), T-101 (reverse rotation),
  T-102 (loaded conveyor symptom) -> kb_v3 content fix.
- Both-articles partial misses: T-030, T-032.
- kb_v3 to be done AFTER Part B, as a separate measured change.