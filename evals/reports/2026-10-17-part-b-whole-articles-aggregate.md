# Part B: aggregate of 3 runs

Spec 05, Part B and clarification 1. Results at threshold -1.0. For each
metric the WORST value across the 3 runs: the lowest for success rates,
the highest for the wrong-escalation rate; each metric's worst value may
come from a different run. The threshold itself is simulated by the
sweep (Part C).

- Runs label: whole-articles
- Model: claude-haiku-4-5-20251001, temperature 0
- System prompt SHA-256: `57a9ae57e9648952a933b60d9785122fb3e5d356b2445ce97bca4da1b09f2ac8`
- Ticket file SHA-256: `c07524bc9a4f251340ed5ee4f9730c3f57307d978df875d389a43d1022fdb80a`
- Code trees: query `8b48ca796e94`, ingestion `16f1e659e66d`, evals/*.py `e9ed6b85bf52`
- Runs: run 1 (2026-10-17, f416c18e3153); run 2 (2026-10-17, 211c5aef7d8e); run 3 (2026-10-17, 211c5aef7d8e)

## Worst of 3

| Set (worst) | AC1 (target 85%) | AC2 (target 95%) | Wrong escalation | Both articles cited |
|---|---|---|---|---|
| calibration | 19/24 (79.2%) | 11/11 (100.0%) | 4/24 (16.7%) | 2/3 (66.7%) |
| holdout | 21/24 (87.5%) | 11/11 (100.0%) | 3/24 (12.5%) | 3/6 (50.0%) |
| full | 40/48 (83.3%) | 22/22 (100.0%) | 7/48 (14.6%) | 5/9 (55.6%) |

| Set | AC1 meets target | AC2 meets target | Passed in all 3 runs (not a gate) |
|---|---|---|---|
| calibration | **no** | yes | 30/35 |
| holdout | yes | yes | 32/35 |
| full | **no** | yes | 62/70 |

### Per run: calibration set

| Run | AC1 | AC2 | Wrong escalation | Both articles cited |
|---|---|---|---|---|
| 1 | 19/24 (79.2%) | 11/11 (100.0%) | 4/24 (16.7%) | 2/3 (66.7%) |
| 2 | 19/24 (79.2%) | 11/11 (100.0%) | 4/24 (16.7%) | 2/3 (66.7%) |
| 3 | 19/24 (79.2%) | 11/11 (100.0%) | 4/24 (16.7%) | 2/3 (66.7%) |

Per category (worst of 3): fault 10/12 (83.3%), installation 3/5 (60.0%), maintenance 3/3 (100.0%), out_of_scope 8/8 (100.0%), parameters 4/4 (100.0%), safety 2/3 (66.7%)

### Per run: holdout set

| Run | AC1 | AC2 | Wrong escalation | Both articles cited |
|---|---|---|---|---|
| 1 | 21/24 (87.5%) | 11/11 (100.0%) | 3/24 (12.5%) | 3/6 (50.0%) |
| 2 | 21/24 (87.5%) | 11/11 (100.0%) | 3/24 (12.5%) | 3/6 (50.0%) |
| 3 | 21/24 (87.5%) | 11/11 (100.0%) | 3/24 (12.5%) | 3/6 (50.0%) |

Per category (worst of 3): fault 9/11 (81.8%), installation 4/4 (100.0%), maintenance 2/2 (100.0%), out_of_scope 10/10 (100.0%), parameters 4/5 (80.0%), safety 3/3 (100.0%)

### Per run: full set

| Run | AC1 | AC2 | Wrong escalation | Both articles cited |
|---|---|---|---|---|
| 1 | 40/48 (83.3%) | 22/22 (100.0%) | 7/48 (14.6%) | 5/9 (55.6%) |
| 2 | 40/48 (83.3%) | 22/22 (100.0%) | 7/48 (14.6%) | 5/9 (55.6%) |
| 3 | 40/48 (83.3%) | 22/22 (100.0%) | 7/48 (14.6%) | 5/9 (55.6%) |

Per category (worst of 3): fault 19/23 (82.6%), installation 7/9 (77.8%), maintenance 5/5 (100.0%), out_of_scope 18/18 (100.0%), parameters 8/9 (88.9%), safety 5/6 (83.3%)

## Unstable tickets (clarification 4)

Status or AC pass/fail differs between runs; wording alone does not count.

None.

## Tickets that failed in at least one run

| Ticket | Set | Expected | Top score | Run 1 | Run 2 | Run 3 |
|---|---|---|---|---|---|---|
| T-005 | calibration | answer | 0.8853 | escalated (insufficient_context) [grounding] ✗ | escalated (insufficient_context) [grounding] ✗ | escalated (insufficient_context) [grounding] ✗ |
| T-009 | calibration | answer | 0.8234 | escalated (insufficient_context) [grounding] ✗ | escalated (insufficient_context) [grounding] ✗ | escalated (insufficient_context) [grounding] ✗ |
| T-016 | holdout | answer | 0.8523 | escalated (insufficient_context) ✗ | escalated (insufficient_context) ✗ | escalated (insufficient_context) ✗ |
| T-021 | calibration | answer | 0.6694 | escalated (insufficient_context) [grounding] ✗ | escalated (insufficient_context) [grounding] ✗ | escalated (insufficient_context) [grounding] ✗ |
| T-030 | holdout | answer | 0.8205 | escalated (insufficient_context) ✗ | escalated (insufficient_context) ✗ | escalated (insufficient_context) ✗ |
| T-039 | calibration | answer | 0.7861 | answered cites KB-036, KB-032 ✗ | answered cites KB-036, KB-032 ✗ | answered cites KB-036, KB-032 ✗ |
| T-101 | calibration | answer | 0.6975 | escalated (insufficient_context) ✗ | escalated (insufficient_context) ✗ | escalated (insufficient_context) ✗ |
| T-102 | holdout | answer | 0.6246 | escalated (insufficient_context) ✗ | escalated (insufficient_context) ✗ | escalated (insufficient_context) ✗ |

## Escalate tickets to watch (notes/step9-retrieval-review.md)

| Ticket | Set | Expected | Top score | Run 1 | Run 2 | Run 3 |
|---|---|---|---|---|---|---|
| T-044 | holdout | escalate | 0.7659 | escalated (insufficient_context) ✓ | escalated (insufficient_context) ✓ | escalated (insufficient_context) ✓ |
| T-049 | calibration | escalate | 0.8853 | escalated (insufficient_context) ✓ | escalated (insufficient_context) ✓ | escalated (insufficient_context) ✓ |
| T-058 | holdout | escalate | 0.7893 | escalated (out_of_scope) ✓ | escalated (out_of_scope) ✓ | escalated (out_of_scope) ✓ |
| T-109 | calibration | escalate | 0.7741 | escalated (out_of_scope) ✓ | escalated (out_of_scope) ✓ | escalated (out_of_scope) ✓ |

## failed_check and escalation reasons per run (full set)

| Run | failed_check | Escalation reasons |
|---|---|---|
| 1 | grounding 3 | insufficient_context 19, out_of_scope 10 |
| 2 | grounding 3 | insufficient_context 19, out_of_scope 10 |
| 3 | grounding 3 | insufficient_context 19, out_of_scope 10 |

## Tokens and cost

| Run | Model calls | Input tokens | Output tokens | Malformed | Cost |
|---|---|---|---|---|---|
| 1 | 66 | 312,746 | 13,209 | 0 | $0.3788 |
| 2 | 66 | 312,746 | 13,209 | 0 | $0.3788 |
| 3 | 66 | 312,746 | 13,209 | 0 | $0.3788 |
| total | 198 | 938,238 | 39,627 | 0 | $1.1364 |

Malformed model outputs: 0. They have no token counts but are still billed, so the cost is slightly underestimated for them.
