# Part A: retrieval report

Spec 05, Part A. No model calls. Each ticket went through QueryFlow with
threshold -1.0 and a stand-in generator that never calls the model, so the
query searched is the flow's own masked and normalised query
(clarification 3) and the scores equal those the sweep uses.

- KB version: v1, search k = 5
- Date: 2026-10-16
- Git commit: 6a2934223b385895648951484cfc8594e3586f18 (with uncommitted changes)
- Ticket file SHA-256: `c07524bc9a4f251340ed5ee4f9730c3f57307d978df875d389a43d1022fdb80a`
- Model calls a full-flow run would make: 66 of 70 tickets

## Retrieval recall

| Set | Recall (≥1 expected article in top 5) | Both articles in top 5 (two-article tickets) |
|---|---|---|
| calibration | 19/24 (79.2%) | 1/3 (33.3%) |
| holdout | 19/24 (79.2%) | 4/6 (66.7%) |
| full | 38/48 (79.2%) | 5/9 (55.6%) |

Tickets with `article_match: "any"` (excluded from the both-articles column, clarification 2):

- T-101: expected article in top 5: **no**

### Recall misses

| Ticket | Set | Expected | Top 5 article_ids | Top score |
|---|---|---|---|---|
| T-004 | holdout | KB-004 | KB-010, KB-006, KB-001, KB-007, KB-011 | 0.7263 |
| T-005 | calibration | KB-005, KB-025 | KB-016, KB-007, KB-002, KB-001, KB-007 | 0.7852 |
| T-006 | holdout | KB-006 | KB-003, KB-016, KB-012, KB-001, KB-009 | 0.7355 |
| T-014 | holdout | KB-014 | KB-011, KB-020, KB-022, KB-019, KB-019 | 0.7416 |
| T-015 | calibration | KB-015, KB-028 | KB-015, KB-015, KB-015, KB-015, KB-036 | 0.8210 |
| T-027 | calibration | KB-024 | KB-022, KB-003, KB-001, KB-008, KB-028 | 0.7593 |
| T-030 | holdout | KB-026, KB-001 | KB-009, KB-009, KB-001, KB-003, KB-002 | 0.7329 |
| T-032 | holdout | KB-028, KB-024 | KB-028, KB-015, KB-003, KB-001, KB-012 | 0.7526 |
| T-037 | calibration | KB-033 | KB-017, KB-018, KB-017, KB-029, KB-017 | 0.7137 |
| T-038 | holdout | KB-034 | KB-022, KB-032, KB-019, KB-032, KB-029 | 0.7499 |
| T-039 | calibration | KB-034 | KB-011, KB-003, KB-012, KB-036, KB-032 | 0.8076 |
| T-101 | calibration | KB-019, KB-022 | KB-001, KB-003, KB-011, KB-020, KB-012 | 0.7395 |
| T-102 | holdout | KB-001 | KB-019, KB-033, KB-010, KB-033, KB-011 | 0.6488 |

## Top-score distributions

"Escalate (score-dependent)" leaves out the escalate tickets stopped by the
unknown-fault-code check: they escalate at every threshold.

| Set | Group | n | min | q1 | median | q3 | max | mean |
|---|---|---|---|---|---|---|---|---|
| calibration | answer | 24 | 0.6540 | 0.7436 | 0.7801 | 0.8082 | 0.8852 | 0.7747 |
| calibration | escalate (all) | 11 | 0.6486 | 0.6725 | 0.7225 | 0.7326 | 0.7786 | 0.7095 |
| calibration | escalate (score-dependent) | 8 | 0.6486 | 0.6653 | 0.7085 | 0.7396 | 0.7786 | 0.7086 |
| holdout | answer | 24 | 0.6488 | 0.7244 | 0.7416 | 0.7715 | 0.8804 | 0.7493 |
| holdout | escalate (all) | 11 | 0.6951 | 0.7024 | 0.7225 | 0.7562 | 0.7852 | 0.7293 |
| holdout | escalate (score-dependent) | 10 | 0.6951 | 0.7023 | 0.7227 | 0.7623 | 0.7852 | 0.7317 |
| full | answer | 48 | 0.6488 | 0.7339 | 0.7518 | 0.7985 | 0.8852 | 0.7620 |
| full | escalate (all) | 22 | 0.6486 | 0.6956 | 0.7225 | 0.7416 | 0.7852 | 0.7194 |
| full | escalate (score-dependent) | 18 | 0.6486 | 0.6956 | 0.7227 | 0.7601 | 0.7852 | 0.7214 |

### Overlap between answer and escalate scores

- calibration: lowest answer score 0.6540, highest score-dependent escalate score 0.7786; overlap: 11 answer tickets at or below the highest escalate score, 7 escalate tickets at or above the lowest answer score.
- holdout: lowest answer score 0.6488, highest score-dependent escalate score 0.7852; overlap: 19 answer tickets at or below the highest escalate score, 10 escalate tickets at or above the lowest answer score.
- full: lowest answer score 0.6488, highest score-dependent escalate score 0.7852; overlap: 32 answer tickets at or below the highest escalate score, 17 escalate tickets at or above the lowest answer score.
- Stopped by the unknown-fault-code check (no model call): T-053, T-054, T-055, T-107

### Histogram: calibration set

```
answer
<0.525
0.525–0.550
0.550–0.575
0.575–0.600
0.600–0.625
0.625–0.650
0.650–0.675  # 1
0.675–0.700
0.700–0.725  ### 3
0.725–0.750  #### 4
0.750–0.775  ## 2
0.775–0.800  ###### 6
0.800–0.825  ###### 6
0.825–0.850
0.850–0.875  # 1
0.875–0.900  # 1
0.900–0.925
0.925–0.950
0.950–0.975
≥0.975

escalate (score-dependent)
<0.525
0.525–0.550
0.550–0.575
0.575–0.600
0.600–0.625
0.625–0.650  # 1
0.650–0.675  ## 2
0.675–0.700  # 1
0.700–0.725  # 1
0.725–0.750  # 1
0.750–0.775  # 1
0.775–0.800  # 1
0.800–0.825
0.825–0.850
0.850–0.875
0.875–0.900
0.900–0.925
0.925–0.950
0.950–0.975
≥0.975
```

### Histogram: holdout set

```
answer
<0.525
0.525–0.550
0.550–0.575
0.575–0.600
0.600–0.625
0.625–0.650  # 1
0.650–0.675
0.675–0.700  ### 3
0.700–0.725  ## 2
0.725–0.750  ######### 9
0.750–0.775  #### 4
0.775–0.800  # 1
0.800–0.825  ## 2
0.825–0.850  # 1
0.850–0.875
0.875–0.900  # 1
0.900–0.925
0.925–0.950
0.950–0.975
≥0.975

escalate (score-dependent)
<0.525
0.525–0.550
0.550–0.575
0.575–0.600
0.600–0.625
0.625–0.650
0.650–0.675
0.675–0.700  ### 3
0.700–0.725  ### 3
0.725–0.750  # 1
0.750–0.775  ## 2
0.775–0.800  # 1
0.800–0.825
0.825–0.850
0.850–0.875
0.875–0.900
0.900–0.925
0.925–0.950
0.950–0.975
≥0.975
```

## All tickets, by top score

| Ticket | Set | Expected | Category | Top score | Top 5 article_ids | Recall | Model call |
|---|---|---|---|---|---|---|---|
| T-059 | calibration | escalate | out_of_scope | 0.6486 | KB-017, KB-017, KB-017, KB-014, KB-014 | – | yes |
| T-102 | holdout | answer | fault | 0.6488 | KB-019, KB-033, KB-010, KB-033, KB-011 | **no** | yes |
| T-031 | calibration | answer | parameters | 0.6540 | KB-028, KB-029, KB-028, KB-028, KB-015 | yes | yes |
| T-047 | calibration | escalate | out_of_scope | 0.6618 | KB-022, KB-001, KB-003, KB-010, KB-033 | – | yes |
| T-043 | calibration | escalate | out_of_scope | 0.6664 | KB-017, KB-003, KB-014, KB-017, KB-028 | – | yes |
| T-053 | calibration | escalate | fault | 0.6786 | KB-009, KB-015, KB-015, KB-007, KB-003 | – | no |
| T-034 | holdout | answer | maintenance | 0.6911 | KB-030, KB-030, KB-030, KB-030, KB-018 | yes | yes |
| T-045 | calibration | escalate | out_of_scope | 0.6933 | KB-019, KB-027, KB-020, KB-027, KB-022 | – | yes |
| T-008 | holdout | answer | fault | 0.6933 | KB-009, KB-008, KB-008, KB-035, KB-009 | yes (both: yes) | yes |
| T-040 | holdout | answer | safety | 0.6951 | KB-035, KB-035, KB-035, KB-035, KB-035 | yes | yes |
| T-108 | holdout | escalate | out_of_scope | 0.6951 | KB-017, KB-024, KB-024, KB-026, KB-015 | – | yes |
| T-050 | holdout | escalate | out_of_scope | 0.6973 | KB-017, KB-011, KB-010, KB-032, KB-022 | – | yes |
| T-046 | holdout | escalate | out_of_scope | 0.6995 | KB-023, KB-014, KB-015, KB-036, KB-017 | – | yes |
| T-021 | calibration | answer | installation | 0.7006 | KB-020, KB-020, KB-019, KB-027, KB-019 | yes | yes |
| T-054 | holdout | escalate | fault | 0.7053 | KB-015, KB-022, KB-015, KB-016, KB-001 | – | no |
| T-060 | holdout | escalate | out_of_scope | 0.7109 | KB-010, KB-010, KB-003, KB-014, KB-011 | – | yes |
| T-022 | holdout | answer | installation | 0.7124 | KB-020, KB-014, KB-022, KB-027, KB-003 | yes (both: yes) | yes |
| T-037 | calibration | answer | maintenance | 0.7137 | KB-017, KB-018, KB-017, KB-029, KB-017 | **no** | yes |
| T-020 | holdout | answer | installation | 0.7188 | KB-019, KB-032, KB-032, KB-020, KB-020 | yes | yes |
| T-041 | calibration | answer | safety | 0.7199 | KB-035, KB-035, KB-035, KB-001, KB-008 | yes | yes |
| T-048 | holdout | escalate | out_of_scope | 0.7225 | KB-026, KB-026, KB-027, KB-001, KB-026 | – | yes |
| T-107 | calibration | escalate | fault | 0.7225 | KB-015, KB-003, KB-015, KB-003, KB-010 | – | no |
| T-056 | holdout | escalate | out_of_scope | 0.7228 | KB-017, KB-026, KB-029, KB-017, KB-019 | – | yes |
| T-057 | calibration | escalate | out_of_scope | 0.7236 | KB-008, KB-003, KB-002, KB-005, KB-009 | – | yes |
| T-004 | holdout | answer | fault | 0.7263 | KB-010, KB-006, KB-001, KB-007, KB-011 | **no** | yes |
| T-051 | calibration | escalate | out_of_scope | 0.7310 | KB-010, KB-010, KB-021, KB-017, KB-004 | – | yes |
| T-030 | holdout | answer | parameters | 0.7329 | KB-009, KB-009, KB-001, KB-003, KB-002 | yes (both: **no**) | yes |
| T-055 | calibration | escalate | fault | 0.7342 | KB-016, KB-022, KB-016, KB-031, KB-016 | – | no |
| T-026 | holdout | answer | parameters | 0.7343 | KB-027, KB-023, KB-036, KB-023, KB-027 | yes | yes |
| T-033 | calibration | answer | maintenance | 0.7346 | KB-029, KB-029, KB-029, KB-033, KB-033 | yes | yes |
| T-006 | holdout | answer | fault | 0.7355 | KB-003, KB-016, KB-012, KB-001, KB-009 | **no** | yes |
| T-024 | holdout | answer | installation | 0.7366 | KB-017, KB-022, KB-010, KB-017, KB-017 | yes | yes |
| T-101 | calibration | answer | installation | 0.7395 | KB-001, KB-003, KB-011, KB-020, KB-012 | **no** | yes |
| T-014 | holdout | answer | fault | 0.7416 | KB-011, KB-020, KB-022, KB-019, KB-019 | **no** | yes |
| T-028 | holdout | answer | parameters | 0.7416 | KB-005, KB-025, KB-026, KB-001, KB-002 | yes | yes |
| T-104 | holdout | answer | parameters | 0.7427 | KB-028, KB-023, KB-028, KB-023, KB-027 | yes | yes |
| T-110 | holdout | escalate | out_of_scope | 0.7441 | KB-017, KB-015, KB-017, KB-015, KB-017 | – | yes |
| T-025 | calibration | answer | parameters | 0.7450 | KB-023, KB-015, KB-028, KB-022, KB-027 | yes | yes |
| T-105 | calibration | answer | fault | 0.7491 | KB-006, KB-010, KB-010, KB-006, KB-015 | yes | yes |
| T-038 | holdout | answer | safety | 0.7499 | KB-022, KB-032, KB-019, KB-032, KB-029 | **no** | yes |
| T-002 | holdout | answer | fault | 0.7510 | KB-003, KB-002, KB-025, KB-001, KB-010 | yes | yes |
| T-032 | holdout | answer | parameters | 0.7526 | KB-028, KB-015, KB-003, KB-001, KB-012 | yes (both: **no**) | yes |
| T-003 | calibration | answer | fault | 0.7544 | KB-003, KB-012, KB-003, KB-014, KB-010 | yes | yes |
| T-027 | calibration | answer | parameters | 0.7593 | KB-022, KB-003, KB-001, KB-008, KB-028 | **no** | yes |
| T-049 | calibration | escalate | out_of_scope | 0.7654 | KB-001, KB-006, KB-002, KB-005, KB-003 | – | yes |
| T-044 | holdout | escalate | out_of_scope | 0.7684 | KB-017, KB-017, KB-017, KB-015, KB-029 | – | yes |
| T-018 | holdout | answer | installation | 0.7709 | KB-018, KB-018, KB-018, KB-018, KB-030 | yes | yes |
| T-052 | holdout | escalate | out_of_scope | 0.7711 | KB-010, KB-011, KB-022, KB-030, KB-033 | – | yes |
| T-016 | holdout | answer | fault | 0.7731 | KB-016, KB-031, KB-031, KB-031, KB-016 | yes (both: yes) | yes |
| T-035 | calibration | answer | maintenance | 0.7751 | KB-031, KB-031, KB-030, KB-016, KB-030 | yes | yes |
| T-109 | calibration | escalate | out_of_scope | 0.7786 | KB-031, KB-017, KB-029, KB-016, KB-031 | – | yes |
| T-001 | calibration | answer | fault | 0.7791 | KB-001, KB-002, KB-001, KB-003, KB-010 | yes | yes |
| T-103 | calibration | answer | safety | 0.7812 | KB-020, KB-032, KB-011, KB-019, KB-034 | yes | yes |
| T-058 | holdout | escalate | out_of_scope | 0.7852 | KB-031, KB-031, KB-016, KB-031, KB-030 | – | yes |
| T-005 | calibration | answer | fault | 0.7852 | KB-016, KB-007, KB-002, KB-001, KB-007 | **no** (both: **no**) | yes |
| T-029 | calibration | answer | parameters | 0.7914 | KB-026, KB-026, KB-026, KB-026, KB-026 | yes | yes |
| T-009 | calibration | answer | fault | 0.7960 | KB-008, KB-008, KB-001, KB-001, KB-002 | yes | yes |
| T-036 | holdout | answer | maintenance | 0.7973 | KB-032, KB-032, KB-032, KB-032, KB-017 | yes | yes |
| T-010 | holdout | answer | fault | 0.8024 | KB-010, KB-010, KB-010, KB-011, KB-015 | yes | yes |
| T-106 | holdout | answer | fault | 0.8059 | KB-030, KB-030, KB-007, KB-030, KB-007 | yes (both: yes) | yes |
| T-019 | calibration | answer | installation | 0.8060 | KB-018, KB-007, KB-007, KB-007, KB-018 | yes | yes |
| T-039 | calibration | answer | safety | 0.8076 | KB-011, KB-003, KB-012, KB-036, KB-032 | **no** | yes |
| T-017 | calibration | answer | installation | 0.8100 | KB-017, KB-017, KB-020, KB-021, KB-019 | yes | yes |
| T-013 | calibration | answer | fault | 0.8108 | KB-013, KB-013, KB-013, KB-013, KB-007 | yes | yes |
| T-007 | calibration | answer | fault | 0.8135 | KB-007, KB-007, KB-013, KB-030, KB-007 | yes (both: yes) | yes |
| T-015 | calibration | answer | fault | 0.8210 | KB-015, KB-015, KB-015, KB-015, KB-036 | yes (both: **no**) | yes |
| T-012 | holdout | answer | fault | 0.8495 | KB-012, KB-003, KB-008, KB-011, KB-010 | yes | yes |
| T-023 | calibration | answer | installation | 0.8614 | KB-021, KB-021, KB-021, KB-021, KB-020 | yes | yes |
| T-042 | holdout | answer | safety | 0.8804 | KB-036, KB-036, KB-014, KB-036, KB-014 | yes | yes |
| T-011 | calibration | answer | fault | 0.8852 | KB-011, KB-011, KB-010, KB-011, KB-012 | yes | yes |
