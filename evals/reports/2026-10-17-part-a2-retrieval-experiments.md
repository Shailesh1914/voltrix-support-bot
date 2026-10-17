# Part A2: retrieval experiments

Spec 05, Part A2. No model calls. Each experiment starts from the flow's own
masked and normalised query and is simulated through search() and kb_info()
only; query/ is unchanged.

**Choose using the calibration set; the holdout set must confirm the
improvement. Adopting an experiment is a spec 02 change, approved by
Shailesh. This report does not choose.**

- KB version: v1
- Date: 2026-10-17
- Git commit: 18d3de790e1cc6bf4d673ef82b69e61b7b10e158 (with uncommitted changes)
- Ticket file SHA-256: `c07524bc9a4f251340ed5ee4f9730c3f57307d978df875d389a43d1022fdb80a`
- E1 prefix: `Represent this sentence for searching relevant passages: `

## Experiments

- **baseline**: the flow as it is: search(query, k=5)
- **E1**: BGE query prefix: search(prefix + query, k=5)
- **E2**: diversity: search(query, k=20), best chunk of each of up to 5 articles
- **E3**: code boost: also search each known E-xx code's article title (k=5); merge, top 5 by score
- **E2+E3**: code boost at k=20, merged, then diversity to up to 5 articles
- **E1+E3**: code boost with the prefix on every search (question and titles), k=5; merge, top 5 by score
- **E1+E2+E3**: code boost with the prefix on every search, k=20, merged, then diversity to up to 5 articles

## Recall (≥1 expected article in top 5)

| Experiment | calibration | holdout | full |
|---|---|---|---|
| baseline | 19/24 (79.2%) | 19/24 (79.2%) | 38/48 (79.2%) |
| E1 | 21/24 (87.5%) (+2) | 20/24 (83.3%) (+1) | 41/48 (85.4%) (+3) |
| E2 | 19/24 (79.2%) (±0) | 20/24 (83.3%) (+1) | 39/48 (81.2%) (+1) |
| E3 | 20/24 (83.3%) (+1) | 22/24 (91.7%) (+3) | 42/48 (87.5%) (+4) |
| E2+E3 | 20/24 (83.3%) (+1) | 22/24 (91.7%) (+3) | 42/48 (87.5%) (+4) |
| E1+E3 | 21/24 (87.5%) (+2) | 22/24 (91.7%) (+3) | 43/48 (89.6%) (+5) |
| E1+E2+E3 | 22/24 (91.7%) (+3) | 23/24 (95.8%) (+4) | 45/48 (93.8%) (+7) |

## Both articles in top 5 (two-article tickets)

| Experiment | calibration | holdout | full |
|---|---|---|---|
| baseline | 1/3 (33.3%) | 4/6 (66.7%) | 5/9 (55.6%) |
| E1 | 2/3 (66.7%) (+1) | 4/6 (66.7%) (±0) | 6/9 (66.7%) (+1) |
| E2 | 2/3 (66.7%) (+1) | 4/6 (66.7%) (±0) | 6/9 (66.7%) (+1) |
| E3 | 1/3 (33.3%) (±0) | 4/6 (66.7%) (±0) | 5/9 (55.6%) (±0) |
| E2+E3 | 2/3 (66.7%) (+1) | 4/6 (66.7%) (±0) | 6/9 (66.7%) (+1) |
| E1+E3 | 2/3 (66.7%) (+1) | 4/6 (66.7%) (±0) | 6/9 (66.7%) (+1) |
| E1+E2+E3 | 3/3 (100.0%) (+2) | 4/6 (66.7%) (±0) | 7/9 (77.8%) (+2) |

## Against the baseline

"Improves" (summary only) = more recall hits and no fewer both-articles hits
than the baseline on that set.

| Experiment | Improves on calibration | Holdout confirms | Gained (full set) | Lost (full set) |
|---|---|---|---|---|
| E1 | yes | yes | T-004, T-005, T-027 | – |
| E2 | **no** | yes | T-014 | – |
| E3 | yes | yes | T-004, T-005, T-006, T-014 | – |
| E2+E3 | yes | yes | T-004, T-005, T-006, T-014 | – |
| E1+E3 | yes | yes | T-004, T-005, T-006, T-014, T-027 | – |
| E1+E2+E3 | yes | yes | T-004, T-005, T-006, T-014, T-027, T-037, T-038 | – |

Tickets with `article_match: "any"` (excluded from both-articles recall, clarification 2):

- T-101: baseline: **no**, E1: **no**, E2: **no**, E3: **no**, E2+E3: **no**, E1+E3: **no**, E1+E2+E3: **no**

## E3 code boost: where it applied

| Ticket | Set | Expected | Titles searched |
|---|---|---|---|
| T-001 | calibration | answer | E-01 Overcurrent during acceleration |
| T-002 | holdout | answer | E-02 Overcurrent during deceleration |
| T-003 | calibration | answer | E-03 Overcurrent at constant speed |
| T-004 | holdout | answer | E-04 DC bus overvoltage at standstill or constant speed |
| T-005 | calibration | answer | E-05 DC bus overvoltage during fast deceleration |
| T-006 | holdout | answer | E-06 DC bus undervoltage |
| T-008 | holdout | answer | E-08 Motor overload; E-09 Drive overload |
| T-009 | calibration | answer | E-08 Motor overload |
| T-011 | calibration | answer | E-11 Output phase loss |
| T-012 | holdout | answer | E-12 Earth (ground) fault |
| T-013 | calibration | answer | E-13 Motor thermistor overtemperature |
| T-014 | holdout | answer | E-14 External fault input active |
| T-015 | calibration | answer | E-15 Parameter memory error |
| T-016 | holdout | answer | E-16 Cooling fan failure |
| T-030 | holdout | answer | E-01 Overcurrent during acceleration |
| T-049 | calibration | escalate | E-05 DC bus overvoltage during fast deceleration |

## Answer tickets with a miss in any experiment

| Ticket | Set | Expected | baseline | E1 | E2 | E3 | E2+E3 | E1+E3 | E1+E2+E3 |
|---|---|---|---|---|---|---|---|---|---|
| T-004 | holdout | KB-004 | **no** | yes | **no** | yes | yes | yes | yes |
| T-005 | calibration | KB-005, KB-025 | **no** (both: **no**) | yes (both: **no**) | **no** (both: **no**) | yes (both: **no**) | yes (both: **no**) | yes (both: **no**) | yes (both: yes) |
| T-006 | holdout | KB-006 | **no** | **no** | **no** | yes | yes | yes | yes |
| T-014 | holdout | KB-014 | **no** | **no** | yes | yes | yes | yes | yes |
| T-015 | calibration | KB-015, KB-028 | yes (both: **no**) | yes (both: yes) | yes (both: yes) | yes (both: **no**) | yes (both: yes) | yes (both: yes) | yes (both: yes) |
| T-027 | calibration | KB-024 | **no** | yes | **no** | **no** | **no** | yes | yes |
| T-030 | holdout | KB-026, KB-001 | yes (both: **no**) | yes (both: **no**) | yes (both: **no**) | yes (both: **no**) | yes (both: **no**) | yes (both: **no**) | yes (both: **no**) |
| T-032 | holdout | KB-028, KB-024 | yes (both: **no**) | yes (both: **no**) | yes (both: **no**) | yes (both: **no**) | yes (both: **no**) | yes (both: **no**) | yes (both: **no**) |
| T-037 | calibration | KB-033 | **no** | **no** | **no** | **no** | **no** | **no** | yes |
| T-038 | holdout | KB-034 | **no** | **no** | **no** | **no** | **no** | **no** | yes |
| T-039 | calibration | KB-034 | **no** | **no** | **no** | **no** | **no** | **no** | **no** |
| T-101 | calibration | KB-019, KB-022 | **no** | **no** | **no** | **no** | **no** | **no** | **no** |
| T-102 | holdout | KB-001 | **no** | **no** | **no** | **no** | **no** | **no** | **no** |

## Note on scores

Recall is the only measure here. Top scores are saved in the .json, but E1 and
E3 change the scores the threshold would see (E3 merges scores of title
searches), so the sweep must be redone on any adopted experiment.
