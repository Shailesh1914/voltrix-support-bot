# Part B: rescoring after a label review

Spec 05 v1.8. The same 3 Part B runs (no model calls), scored BEFORE with
the ticket file they were made on and AFTER with the revised ticket file.
Only expected, expected_article_ids and article_match differ between the
two files (checked). Worst of 3 as in Part B (clarification 1), at
threshold -1.0. The original run files and reports are unchanged.

- Runs label: whole-articles
- Model: claude-haiku-4-5-20251001, temperature 0
- Ticket file BEFORE: `c07524bc9a4f251340ed5ee4f9730c3f57307d978df875d389a43d1022fdb80a` (git dfdee7bfd718)
- Ticket file AFTER: `6ae85bcf8b118ae17d88952ca5474887d7c066f492428278de2844a618fda782`
- Runs: run 1 (2026-10-17, f416c18e3153); run 2 (2026-10-17, 211c5aef7d8e); run 3 (2026-10-17, 211c5aef7d8e)

## Changed labels

| Ticket | Set | BEFORE label | AFTER label | Run 1 | Run 2 | Run 3 | Pass/fail changed |
|---|---|---|---|---|---|---|---|
| T-039 | calibration | answer: KB-034 | answer: KB-034, KB-036 (any) | answered cites KB-036, KB-032: ✗ → ✓ | answered cites KB-036, KB-032: ✗ → ✓ | answered cites KB-036, KB-032: ✗ → ✓ | **yes** |

Tickets whose pass/fail changed: T-039.

## BEFORE and AFTER per set (worst of 3)

### calibration set (35 tickets)

| Metric | BEFORE | AFTER | Change |
|---|---|---|---|
| AC1 (target 85%) | 19/24 (79.2%) | 20/24 (83.3%) | +1 |
| AC2 (target 95%) | 11/11 (100.0%) | 11/11 (100.0%) | – |
| Wrong escalation | 4/24 (16.7%) | 4/24 (16.7%) | – |
| Both articles cited | 2/3 (66.7%) | 2/3 (66.7%) | – |
| AC1 meets target | **no** | **no** | |
| AC2 meets target | yes | yes | |
| Passed in all 3 runs (not a gate) | 30/35 | 31/35 | +1 |

Unstable BEFORE: none; AFTER: none.

### holdout set (35 tickets)

| Metric | BEFORE | AFTER | Change |
|---|---|---|---|
| AC1 (target 85%) | 21/24 (87.5%) | 21/24 (87.5%) | – |
| AC2 (target 95%) | 11/11 (100.0%) | 11/11 (100.0%) | – |
| Wrong escalation | 3/24 (12.5%) | 3/24 (12.5%) | – |
| Both articles cited | 3/6 (50.0%) | 3/6 (50.0%) | – |
| AC1 meets target | yes | yes | |
| AC2 meets target | yes | yes | |
| Passed in all 3 runs (not a gate) | 32/35 | 32/35 | +0 |

Unstable BEFORE: none; AFTER: none.

### full set (70 tickets)

| Metric | BEFORE | AFTER | Change |
|---|---|---|---|
| AC1 (target 85%) | 40/48 (83.3%) | 41/48 (85.4%) | +1 |
| AC2 (target 95%) | 22/22 (100.0%) | 22/22 (100.0%) | – |
| Wrong escalation | 7/48 (14.6%) | 7/48 (14.6%) | – |
| Both articles cited | 5/9 (55.6%) | 5/9 (55.6%) | – |
| AC1 meets target | **no** | yes | |
| AC2 meets target | yes | yes | |
| Passed in all 3 runs (not a gate) | 62/70 | 63/70 | +1 |

Unstable BEFORE: none; AFTER: none.
