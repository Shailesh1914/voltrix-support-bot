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