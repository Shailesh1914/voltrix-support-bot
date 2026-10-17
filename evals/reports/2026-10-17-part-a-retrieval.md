# Part A: retrieval report

Spec 05, Part A. No model calls. Each ticket went through QueryFlow with
threshold -1.0 and a stand-in generator that never calls the model, so the
query searched is the flow's own masked and normalised query
(clarification 3) and the scores equal those the sweep uses.
The final retrieved chunks (up to 5 articles, one chunk each) are read
from each ticket's handoff record; the top score is the highest score
among them.

- KB version: v1
- Retrieval: the flow's own: spec 02 step 3 (main search, code boost, merge, diversity)
- Date: 2026-10-17
- Git commit: 78ff42c5fc999a74d09b1c446ce3f2f4c12ff412
- Ticket file SHA-256: `c07524bc9a4f251340ed5ee4f9730c3f57307d978df875d389a43d1022fdb80a`
- Model calls a full-flow run would make: 66 of 70 tickets

## Retrieval recall

| Set | Recall (≥1 expected article retrieved) | Both articles retrieved (two-article tickets) |
|---|---|---|
| calibration | 22/24 (91.7%) | 3/3 (100.0%) |
| holdout | 23/24 (95.8%) | 4/6 (66.7%) |
| full | 45/48 (93.8%) | 7/9 (77.8%) |

Tickets with `article_match: "any"` (excluded from the both-articles column, clarification 2):

- T-101: expected article retrieved: **no**

### Recall misses

| Ticket | Set | Expected | Retrieved article_ids | Top score |
|---|---|---|---|---|
| T-030 | holdout | KB-026, KB-001 | KB-001, KB-002, KB-003, KB-025, KB-009 | 0.8205 |
| T-032 | holdout | KB-028, KB-024 | KB-028, KB-015, KB-003, KB-009, KB-001 | 0.7304 |
| T-039 | calibration | KB-034 | KB-011, KB-036, KB-003, KB-012, KB-032 | 0.7861 |
| T-101 | calibration | KB-019, KB-022 | KB-020, KB-001, KB-011, KB-017, KB-029 | 0.6975 |
| T-102 | holdout | KB-001 | KB-033, KB-019, KB-011, KB-009, KB-036 | 0.6246 |

## Against the Part A2 simulation (E1+E2+E3)

For every ticket: the query, the texts searched, the final chunk ids (in
order), the article ids, recall and the top score (tolerance
1e-09) must equal the committed simulation.

- Part A2 report: `/home/shailesh1914/projects/voltrix-support-bot/evals/reports/2026-10-17-part-a2-retrieval-experiments.json`
- Part A2 report SHA-256: `dba5be51f7b73308dfe4f2bbb7d7268ab7b6c95d13249cfd960e1105768a2466`
- Part A2 git commit: 18d3de790e1cc6bf4d673ef82b69e61b7b10e158 (with uncommitted changes)
- Result: **MATCH**: 70/70 tickets match; largest top-score difference 0.00e+00

| Set | Recall: real flow | Recall: Part A2 | Both articles: real flow | Both articles: Part A2 |
|---|---|---|---|---|
| calibration | 22/24 (91.7%) | 22/24 (91.7%) | 3/3 (100.0%) | 3/3 (100.0%) |
| holdout | 23/24 (95.8%) | 23/24 (95.8%) | 4/6 (66.7%) | 4/6 (66.7%) |
| full | 45/48 (93.8%) | 45/48 (93.8%) | 7/9 (77.8%) | 7/9 (77.8%) |

### Differences

None.

## Top-score distributions

"Escalate (score-dependent)" leaves out the escalate tickets stopped by the
unknown-fault-code check: they escalate at every threshold.

| Set | Group | n | min | q1 | median | q3 | max | mean |
|---|---|---|---|---|---|---|---|---|
| calibration | answer | 24 | 0.6435 | 0.7215 | 0.7844 | 0.8213 | 0.8853 | 0.7738 |
| calibration | escalate (all) | 11 | 0.6336 | 0.6682 | 0.6828 | 0.7267 | 0.8853 | 0.7074 |
| calibration | escalate (score-dependent) | 8 | 0.6336 | 0.6633 | 0.6791 | 0.7225 | 0.8853 | 0.7080 |
| holdout | answer | 24 | 0.6246 | 0.7136 | 0.7731 | 0.8285 | 0.8844 | 0.7685 |
| holdout | escalate (all) | 11 | 0.6627 | 0.6841 | 0.7011 | 0.7273 | 0.7893 | 0.7104 |
| holdout | escalate (score-dependent) | 10 | 0.6627 | 0.6912 | 0.7062 | 0.7321 | 0.7893 | 0.7151 |
| full | answer | 48 | 0.6246 | 0.7138 | 0.7827 | 0.8246 | 0.8853 | 0.7711 |
| full | escalate (all) | 22 | 0.6336 | 0.6735 | 0.6996 | 0.7290 | 0.8853 | 0.7089 |
| full | escalate (score-dependent) | 18 | 0.6336 | 0.6764 | 0.6996 | 0.7321 | 0.8853 | 0.7119 |

### Overlap between answer and escalate scores

- calibration: lowest answer score 0.6435, highest score-dependent escalate score 0.8853; overlap: 24 answer tickets at or below the highest escalate score, 6 escalate tickets at or above the lowest answer score.
- holdout: lowest answer score 0.6246, highest score-dependent escalate score 0.7893; overlap: 13 answer tickets at or below the highest escalate score, 10 escalate tickets at or above the lowest answer score.
- full: lowest answer score 0.6246, highest score-dependent escalate score 0.8853; overlap: 48 answer tickets at or below the highest escalate score, 18 escalate tickets at or above the lowest answer score.
- Stopped by the unknown-fault-code check (no model call): T-053, T-054, T-055, T-107

### Histogram: calibration set

```
answer
<0.525
0.525–0.550
0.550–0.575
0.575–0.600
0.600–0.625
0.625–0.650  # 1
0.650–0.675  # 1
0.675–0.700  ## 2
0.700–0.725  ## 2
0.725–0.750  ### 3
0.750–0.775  ## 2
0.775–0.800  ## 2
0.800–0.825  ####### 7
0.825–0.850
0.850–0.875  ### 3
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
0.625–0.650  ## 2
0.650–0.675  # 1
0.675–0.700  ## 2
0.700–0.725  # 1
0.725–0.750
0.750–0.775  # 1
0.775–0.800
0.800–0.825
0.825–0.850
0.850–0.875
0.875–0.900  # 1
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
0.600–0.625  # 1
0.625–0.650
0.650–0.675  ## 2
0.675–0.700  # 1
0.700–0.725  #### 4
0.725–0.750  ### 3
0.750–0.775  # 1
0.775–0.800  ### 3
0.800–0.825  # 1
0.825–0.850  #### 4
0.850–0.875  ### 3
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
0.650–0.675  # 1
0.675–0.700  ### 3
0.700–0.725  ### 3
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

## All tickets, by top score

| Ticket | Set | Expected | Category | Top score | Retrieved article_ids | Recall | Model call |
|---|---|---|---|---|---|---|---|
| T-102 | holdout | answer | fault | 0.6246 | KB-033, KB-019, KB-011, KB-009, KB-036 | **no** | yes |
| T-047 | calibration | escalate | out_of_scope | 0.6336 | KB-022, KB-001, KB-003, KB-033, KB-002 | – | yes |
| T-059 | calibration | escalate | out_of_scope | 0.6344 | KB-017, KB-014, KB-033, KB-029, KB-030 | – | yes |
| T-031 | calibration | answer | parameters | 0.6435 | KB-028, KB-029, KB-017, KB-023, KB-009 | yes | yes |
| T-034 | holdout | answer | maintenance | 0.6627 | KB-030, KB-018, KB-008, KB-007, KB-009 | yes | yes |
| T-050 | holdout | escalate | out_of_scope | 0.6627 | KB-017, KB-007, KB-032, KB-022, KB-011 | – | yes |
| T-054 | holdout | escalate | fault | 0.6630 | KB-015, KB-016, KB-001, KB-010, KB-011 | – | no |
| T-053 | calibration | escalate | fault | 0.6635 | KB-009, KB-014, KB-007, KB-015, KB-001 | – | no |
| T-040 | holdout | answer | safety | 0.6642 | KB-035, KB-025, KB-009, KB-008, KB-023 | yes | yes |
| T-021 | calibration | answer | installation | 0.6694 | KB-020, KB-019, KB-027, KB-024, KB-032 | yes | yes |
| T-043 | calibration | escalate | out_of_scope | 0.6729 | KB-017, KB-003, KB-014, KB-009, KB-028 | – | yes |
| T-045 | calibration | escalate | out_of_scope | 0.6755 | KB-019, KB-027, KB-020, KB-022, KB-023 | – | yes |
| T-108 | holdout | escalate | out_of_scope | 0.6792 | KB-017, KB-024, KB-015, KB-026, KB-009 | – | yes |
| T-041 | calibration | answer | safety | 0.6806 | KB-035, KB-008, KB-003, KB-001, KB-016 | yes | yes |
| T-057 | calibration | escalate | out_of_scope | 0.6828 | KB-005, KB-002, KB-025, KB-008, KB-003 | – | yes |
| T-060 | holdout | escalate | out_of_scope | 0.6890 | KB-003, KB-011, KB-001, KB-010, KB-004 | – | yes |
| T-101 | calibration | answer | installation | 0.6975 | KB-020, KB-001, KB-011, KB-017, KB-029 | **no** | yes |
| T-046 | holdout | escalate | out_of_scope | 0.6980 | KB-014, KB-023, KB-017, KB-009, KB-027 | – | yes |
| T-020 | holdout | answer | installation | 0.6985 | KB-019, KB-035, KB-032, KB-020, KB-034 | yes | yes |
| T-056 | holdout | escalate | out_of_scope | 0.7011 | KB-017, KB-026, KB-029, KB-024, KB-009 | – | yes |
| T-022 | holdout | answer | installation | 0.7044 | KB-020, KB-027, KB-014, KB-022, KB-004 | yes (both: yes) | yes |
| T-051 | calibration | escalate | out_of_scope | 0.7053 | KB-010, KB-021, KB-017, KB-022, KB-011 | – | yes |
| T-024 | holdout | answer | installation | 0.7054 | KB-017, KB-022, KB-010, KB-011, KB-030 | yes | yes |
| T-033 | calibration | answer | maintenance | 0.7056 | KB-029, KB-033, KB-022, KB-003, KB-023 | yes | yes |
| T-037 | calibration | answer | maintenance | 0.7062 | KB-017, KB-018, KB-029, KB-033, KB-031 | yes | yes |
| T-052 | holdout | escalate | out_of_scope | 0.7112 | KB-010, KB-022, KB-011, KB-030, KB-019 | – | yes |
| T-038 | holdout | answer | safety | 0.7163 | KB-032, KB-022, KB-019, KB-034, KB-029 | yes | yes |
| T-026 | holdout | answer | parameters | 0.7176 | KB-027, KB-023, KB-036, KB-020, KB-028 | yes | yes |
| T-048 | holdout | escalate | out_of_scope | 0.7177 | KB-026, KB-027, KB-020, KB-023, KB-001 | – | yes |
| T-055 | calibration | escalate | fault | 0.7221 | KB-016, KB-031, KB-014, KB-022, KB-011 | – | no |
| T-025 | calibration | answer | parameters | 0.7266 | KB-023, KB-028, KB-015, KB-027, KB-022 | yes | yes |
| T-105 | calibration | answer | fault | 0.7282 | KB-006, KB-010, KB-015, KB-012, KB-011 | yes | yes |
| T-032 | holdout | answer | parameters | 0.7304 | KB-028, KB-015, KB-003, KB-009, KB-001 | yes (both: **no**) | yes |
| T-028 | holdout | answer | parameters | 0.7308 | KB-026, KB-025, KB-005, KB-024, KB-002 | yes | yes |
| T-027 | calibration | answer | parameters | 0.7312 | KB-022, KB-024, KB-003, KB-008, KB-028 | yes | yes |
| T-107 | calibration | escalate | fault | 0.7314 | KB-003, KB-010, KB-001, KB-002, KB-023 | – | no |
| T-110 | holdout | escalate | out_of_scope | 0.7369 | KB-017, KB-015, KB-028, KB-033, KB-035 | – | yes |
| T-104 | holdout | answer | parameters | 0.7376 | KB-028, KB-023, KB-027, KB-015, KB-032 | yes | yes |
| T-103 | calibration | answer | safety | 0.7619 | KB-020, KB-032, KB-011, KB-034, KB-019 | yes | yes |
| T-018 | holdout | answer | installation | 0.7636 | KB-018, KB-019, KB-022, KB-030, KB-017 | yes | yes |
| T-035 | calibration | answer | maintenance | 0.7655 | KB-031, KB-030, KB-016, KB-018, KB-017 | yes | yes |
| T-044 | holdout | escalate | out_of_scope | 0.7659 | KB-017, KB-015, KB-029, KB-028, KB-033 | – | yes |
| T-109 | calibration | escalate | out_of_scope | 0.7741 | KB-031, KB-017, KB-016, KB-029, KB-030 | – | yes |
| T-106 | holdout | answer | fault | 0.7825 | KB-030, KB-007, KB-035, KB-032, KB-029 | yes (both: yes) | yes |
| T-029 | calibration | answer | parameters | 0.7828 | KB-026, KB-025, KB-002, KB-028, KB-027 | yes | yes |
| T-039 | calibration | answer | safety | 0.7861 | KB-011, KB-036, KB-003, KB-012, KB-032 | **no** | yes |
| T-058 | holdout | escalate | out_of_scope | 0.7893 | KB-031, KB-016, KB-030, KB-017, KB-007 | – | yes |
| T-036 | holdout | answer | maintenance | 0.7939 | KB-032, KB-017, KB-019, KB-010, KB-018 | yes | yes |
| T-010 | holdout | answer | fault | 0.7945 | KB-010, KB-011, KB-015, KB-006, KB-036 | yes | yes |
| T-019 | calibration | answer | installation | 0.8021 | KB-018, KB-007, KB-035, KB-013, KB-030 | yes | yes |
| T-007 | calibration | answer | fault | 0.8087 | KB-007, KB-013, KB-030, KB-031, KB-003 | yes (both: yes) | yes |
| T-003 | calibration | answer | fault | 0.8094 | KB-003, KB-014, KB-009, KB-001, KB-002 | yes | yes |
| T-017 | calibration | answer | installation | 0.8159 | KB-017, KB-021, KB-020, KB-027, KB-014 | yes | yes |
| T-001 | calibration | answer | fault | 0.8205 | KB-001, KB-002, KB-003, KB-009, KB-025 | yes | yes |
| T-030 | holdout | answer | parameters | 0.8205 | KB-001, KB-002, KB-003, KB-025, KB-009 | yes (both: **no**) | yes |
| T-009 | calibration | answer | fault | 0.8234 | KB-008, KB-009, KB-001, KB-002, KB-025 | yes | yes |
| T-015 | calibration | answer | fault | 0.8242 | KB-015, KB-028, KB-036, KB-010, KB-009 | yes (both: yes) | yes |
| T-008 | holdout | answer | fault | 0.8260 | KB-009, KB-008, KB-003, KB-007, KB-002 | yes (both: yes) | yes |
| T-012 | holdout | answer | fault | 0.8267 | KB-012, KB-003, KB-008, KB-011, KB-010 | yes | yes |
| T-006 | holdout | answer | fault | 0.8341 | KB-006, KB-005, KB-004, KB-003, KB-016 | yes | yes |
| T-002 | holdout | answer | fault | 0.8379 | KB-002, KB-001, KB-025, KB-003, KB-005 | yes | yes |
| T-016 | holdout | answer | fault | 0.8523 | KB-016, KB-031, KB-007, KB-013, KB-030 | yes (both: yes) | yes |
| T-023 | calibration | answer | installation | 0.8526 | KB-021, KB-020, KB-019, KB-012, KB-004 | yes | yes |
| T-014 | holdout | answer | fault | 0.8594 | KB-014, KB-036, KB-022, KB-020, KB-019 | yes | yes |
| T-011 | calibration | answer | fault | 0.8713 | KB-011, KB-010, KB-012, KB-008, KB-032 | yes | yes |
| T-013 | calibration | answer | fault | 0.8719 | KB-013, KB-007, KB-008, KB-012, KB-030 | yes | yes |
| T-004 | holdout | answer | fault | 0.8745 | KB-004, KB-005, KB-006, KB-002, KB-034 | yes | yes |
| T-042 | holdout | answer | safety | 0.8844 | KB-036, KB-014, KB-006, KB-012, KB-020 | yes | yes |
| T-005 | calibration | answer | fault | 0.8853 | KB-005, KB-004, KB-002, KB-006, KB-025 | yes (both: yes) | yes |
| T-049 | calibration | escalate | out_of_scope | 0.8853 | KB-005, KB-004, KB-002, KB-006, KB-025 | – | yes |
