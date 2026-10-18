# Part C: confirmation run at threshold 0.6 (whole-articles)

Spec 05, Part C: "After the threshold is chosen, one confirmation run of
the real flow at that threshold checks the simulation matched." Every
ticket went through QueryFlow with the real model at the threshold in
query/config.py (read as the real bot reads it; no other source). Each
ticket's real outcome is compared with the sweep's simulated outcome at
the same threshold, for each of the 3 Part B runs. A ticket matches only
if it agrees with all 3. Handoffs went to the evaluation-only file below,
never to handoffs/.

- Result: **MATCH**: 70/70 tickets agree with all 3 runs
- Tickets run: 70/70
- Date: 2026-10-18
- Git commit: ad13048cfdecde4be0a2103b73d9889d664cc300
- Ticket file SHA-256: `c07524bc9a4f251340ed5ee4f9730c3f57307d978df875d389a43d1022fdb80a`
- Code trees at HEAD: query `7bef9407f2f0`, ingestion `16f1e659e66d`, evals/*.py `4a9dd046a8b2`
- query/ files changed since the Part B runs: config.py; evals/*.py changed: yes (this command)
- Model: claude-haiku-4-5-20251001, temperature 0, max output tokens 2048
- System prompt SHA-256: `57a9ae57e9648952a933b60d9785122fb3e5d356b2445ce97bca4da1b09f2ac8`
- KB version: v1; threshold 0.6 from query/config.py
- Handoffs: `2026-10-18-part-c-whole-articles-confirm-t0.60-handoffs.jsonl` (29 records)
- Part B runs simulated:
  - `evals/reports/2026-10-17-part-b-whole-articles-run1.json` (SHA-256 `5110fdf73c42618f…`)
  - `evals/reports/2026-10-17-part-b-whole-articles-run2.json` (SHA-256 `f86750d5ac9b66d6…`)
  - `evals/reports/2026-10-17-part-b-whole-articles-run3.json` (SHA-256 `e05759fa4fea73c4…`)
- Model calls: 66
- Tokens: 312,746 input, 13,209 output
- Cost: $0.3788 ($1.00 / $5.00 per million input / output tokens)
- Malformed model outputs: 0. Malformed model outputs have no token counts (the generator raises before returning usage). They are still billed, so the cost is slightly underestimated for them.

## Results at this threshold

Real run:

| Set | AC1 (target 85%) | AC2 (target 95%) | Wrong escalation | Both articles cited |
|---|---|---|---|---|
| calibration | 19/24 (79.2%) | 11/11 (100.0%) | 4/24 (16.7%) | 2/3 (66.7%) |
| holdout | 21/24 (87.5%) | 11/11 (100.0%) | 3/24 (12.5%) | 3/6 (50.0%) |
| full | 40/48 (83.3%) | 22/22 (100.0%) | 7/48 (14.6%) | 5/9 (55.6%) |

Simulated by the sweep (worst of the 3 runs):

| Set | AC1 | AC2 | Wrong escalation |
|---|---|---|---|
| calibration | 19/24 (79.2%) | 11/11 (100.0%) | 4/24 (16.7%) |
| holdout | 21/24 (87.5%) | 11/11 (100.0%) | 3/24 (12.5%) |
| full | 40/48 (83.3%) | 22/22 (100.0%) | 7/48 (14.6%) |

| Set | AC1 meets target | AC2 meets target (real run) |
|---|---|---|
| calibration | **no** | yes |
| holdout | yes | yes |
| full | **no** | yes |

## Against the simulation

Compared per ticket and per run: top_score, status, escalation_reason, ac_pass.

No differences.

## All tickets (real run)

| Ticket | Set | Expected | Top score | Status | Reason | failed_check | Cited | Pass | Matches |
|---|---|---|---|---|---|---|---|---|---|
| T-001 | calibration | answer | 0.8205 | answered | – | – | KB-001 | yes | yes |
| T-002 | holdout | answer | 0.8379 | answered | – | – | KB-002, KB-025 | yes | yes |
| T-003 | calibration | answer | 0.8094 | answered | – | – | KB-003 | yes | yes |
| T-004 | holdout | answer | 0.8745 | answered | – | – | KB-004 | yes | yes |
| T-005 | calibration | answer | 0.8853 | escalated | insufficient_context | grounding | – | **no** | yes |
| T-006 | holdout | answer | 0.8341 | answered | – | – | KB-006 | yes | yes |
| T-007 | calibration | answer | 0.8087 | answered | – | – | KB-007, KB-030 | yes | yes |
| T-008 | holdout | answer | 0.8260 | answered | – | – | KB-008, KB-009 | yes | yes |
| T-009 | calibration | answer | 0.8234 | escalated | insufficient_context | grounding | – | **no** | yes |
| T-010 | holdout | answer | 0.7945 | answered | – | – | KB-010 | yes | yes |
| T-011 | calibration | answer | 0.8713 | answered | – | – | KB-011 | yes | yes |
| T-012 | holdout | answer | 0.8267 | answered | – | – | KB-012 | yes | yes |
| T-013 | calibration | answer | 0.8719 | answered | – | – | KB-013 | yes | yes |
| T-014 | holdout | answer | 0.8594 | answered | – | – | KB-014, KB-036 | yes | yes |
| T-015 | calibration | answer | 0.8242 | answered | – | – | KB-015, KB-028 | yes | yes |
| T-016 | holdout | answer | 0.8523 | escalated | insufficient_context | – | – | **no** | yes |
| T-017 | calibration | answer | 0.8159 | answered | – | – | KB-017 | yes | yes |
| T-018 | holdout | answer | 0.7636 | answered | – | – | KB-018 | yes | yes |
| T-019 | calibration | answer | 0.8021 | answered | – | – | KB-018 | yes | yes |
| T-020 | holdout | answer | 0.6985 | answered | – | – | KB-019, KB-034 | yes | yes |
| T-021 | calibration | answer | 0.6694 | escalated | insufficient_context | grounding | – | **no** | yes |
| T-022 | holdout | answer | 0.7044 | answered | – | – | KB-027, KB-020 | yes | yes |
| T-023 | calibration | answer | 0.8526 | answered | – | – | KB-021 | yes | yes |
| T-024 | holdout | answer | 0.7054 | answered | – | – | KB-022 | yes | yes |
| T-025 | calibration | answer | 0.7266 | answered | – | – | KB-023 | yes | yes |
| T-026 | holdout | answer | 0.7176 | answered | – | – | KB-027, KB-023 | yes | yes |
| T-027 | calibration | answer | 0.7312 | answered | – | – | KB-024, KB-022 | yes | yes |
| T-028 | holdout | answer | 0.7308 | answered | – | – | KB-025 | yes | yes |
| T-029 | calibration | answer | 0.7828 | answered | – | – | KB-026 | yes | yes |
| T-030 | holdout | answer | 0.8205 | escalated | insufficient_context | – | – | **no** | yes |
| T-031 | calibration | answer | 0.6435 | answered | – | – | KB-028 | yes | yes |
| T-032 | holdout | answer | 0.7304 | answered | – | – | KB-028 | yes | yes |
| T-033 | calibration | answer | 0.7056 | answered | – | – | KB-029 | yes | yes |
| T-034 | holdout | answer | 0.6627 | answered | – | – | KB-030 | yes | yes |
| T-035 | calibration | answer | 0.7655 | answered | – | – | KB-031 | yes | yes |
| T-036 | holdout | answer | 0.7939 | answered | – | – | KB-032 | yes | yes |
| T-037 | calibration | answer | 0.7062 | answered | – | – | KB-033 | yes | yes |
| T-038 | holdout | answer | 0.7163 | answered | – | – | KB-034 | yes | yes |
| T-039 | calibration | answer | 0.7861 | answered | – | – | KB-036, KB-032 | **no** | yes |
| T-040 | holdout | answer | 0.6642 | answered | – | – | KB-035 | yes | yes |
| T-041 | calibration | answer | 0.6806 | answered | – | – | KB-035 | yes | yes |
| T-042 | holdout | answer | 0.8844 | answered | – | – | KB-036 | yes | yes |
| T-043 | calibration | escalate | 0.6729 | escalated | insufficient_context | – | – | yes | yes |
| T-044 | holdout | escalate | 0.7659 | escalated | insufficient_context | – | – | yes | yes |
| T-045 | calibration | escalate | 0.6755 | escalated | insufficient_context | – | – | yes | yes |
| T-046 | holdout | escalate | 0.6980 | escalated | insufficient_context | – | – | yes | yes |
| T-047 | calibration | escalate | 0.6336 | escalated | insufficient_context | – | – | yes | yes |
| T-048 | holdout | escalate | 0.7177 | escalated | insufficient_context | – | – | yes | yes |
| T-049 | calibration | escalate | 0.8853 | escalated | insufficient_context | – | – | yes | yes |
| T-050 | holdout | escalate | 0.6627 | escalated | insufficient_context | – | – | yes | yes |
| T-051 | calibration | escalate | 0.7053 | escalated | out_of_scope | – | – | yes | yes |
| T-052 | holdout | escalate | 0.7112 | escalated | out_of_scope | – | – | yes | yes |
| T-053 | calibration | escalate | 0.6635 | escalated | insufficient_context | – | – | yes | yes |
| T-054 | holdout | escalate | 0.6630 | escalated | insufficient_context | – | – | yes | yes |
| T-055 | calibration | escalate | 0.7221 | escalated | insufficient_context | – | – | yes | yes |
| T-056 | holdout | escalate | 0.7011 | escalated | out_of_scope | – | – | yes | yes |
| T-057 | calibration | escalate | 0.6828 | escalated | out_of_scope | – | – | yes | yes |
| T-058 | holdout | escalate | 0.7893 | escalated | out_of_scope | – | – | yes | yes |
| T-059 | calibration | escalate | 0.6344 | escalated | out_of_scope | – | – | yes | yes |
| T-060 | holdout | escalate | 0.6890 | escalated | out_of_scope | – | – | yes | yes |
| T-101 | calibration | answer | 0.6975 | escalated | insufficient_context | – | – | **no** | yes |
| T-102 | holdout | answer | 0.6246 | escalated | insufficient_context | – | – | **no** | yes |
| T-103 | calibration | answer | 0.7619 | answered | – | – | KB-034, KB-032 | yes | yes |
| T-104 | holdout | answer | 0.7376 | answered | – | – | KB-028 | yes | yes |
| T-105 | calibration | answer | 0.7282 | answered | – | – | KB-006 | yes | yes |
| T-106 | holdout | answer | 0.7825 | answered | – | – | KB-030, KB-007 | yes | yes |
| T-107 | calibration | escalate | 0.7314 | escalated | insufficient_context | – | – | yes | yes |
| T-108 | holdout | escalate | 0.6792 | escalated | out_of_scope | – | – | yes | yes |
| T-109 | calibration | escalate | 0.7741 | escalated | out_of_scope | – | – | yes | yes |
| T-110 | holdout | escalate | 0.7369 | escalated | out_of_scope | – | – | yes | yes |
