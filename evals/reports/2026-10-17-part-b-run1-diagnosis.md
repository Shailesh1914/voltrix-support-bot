# Part B run 1: free diagnosis of the AC1 failures

No model calls. Inputs (all read-only): `2026-10-17-part-b-run1.json`, `2026-10-17-part-b-run1-handoffs.jsonl`, `evals/support_questions.jsonl` (notes field), `data/kb_v1/`. Retrieval was replayed through `open_retrieval('v1')`, `search()` and `kb_info()` only.

- Run 1: commit `c69b89a03634`, model `claude-haiku-4-5-20251001`, AC1 25/48
- Wrong escalations ("answer" tickets escalated): 21

## Checks on this diagnosis

- kb_v1 chunks rebuilt from the articles with spec 01 rules: 36 articles, 172 chunks.
- Every rebuilt chunk was found in the real v1 index under the same chunk_id with identical text (one `search(chunk_text, 20)` per chunk), and every chunk text recorded in the run 1 handoffs matches. No section was split.
- Retrieval replay (spec 02 step 3) reproduces run 1's final chunk ids exactly on 70/70 tickets, so the ranks below are the run's ranks.
- Codes and numbers with units are extracted by this script, written from spec 02 (step 5e, decision 9), not by the bot's grounding check. Matching is by canonical form: codes as `E-xx`/`P-xx`; numbers as values (10.0 = 10) with unit aliases (s/sec/seconds, min/minutes, V/VAC/V DC). The bot's check may differ in detail; the run record does not say which item failed it.

## A. Grounding failures: codes and numbers in the rejected drafts

Columns: (a) in the question; (b) in the retrieved chunks of the cited articles (what the grounding check sees); (c) in other retrieved chunks; (d) in chunks of the cited articles that were NOT retrieved; (e) none of these. The last column lists other kb_v1 articles that contain an (e) item.

### T-001 (cited KB-001, KB-025)

Question: vx200 on the infeed conveyor trips evry time it ramps up, E-01 flashing. wht to check first

Retrieved: KB-001#c1, KB-002#c2, KB-003#c1, KB-009#c1, KB-025#c3

| Item | (a) question | (b) cited, retrieved | (c) other retrieved | (d) cited, not retrieved | (e) nowhere | other kb_v1 articles |
|---|---|---|---|---|---|---|
| `E-01` | yes | yes | – | KB-001#c2, KB-001#c3, KB-001#c4 | – | – |
| `P-05` | – | yes | – | KB-001#c2, KB-001#c3, KB-025#c1 | – | – |
| `P-16` | – | – | yes | KB-001#c2, KB-001#c3 | – | – |
| `P-20` | – | – | yes | KB-001#c2, KB-001#c3 | – | – |

Items the grounding check cannot find (not in b): `P-16`, `P-20`

### T-002 (cited KB-002, KB-025)

Question: Getting E-02 when we stop the mixer. Ramp down is set to 3 sec. We don't really need a controlled stop on this machine, is there a way round it?

Retrieved: KB-002#c1, KB-001#c1, KB-025#c4, KB-003#c2, KB-005#c2

| Item | (a) question | (b) cited, retrieved | (c) other retrieved | (d) cited, not retrieved | (e) nowhere | other kb_v1 articles |
|---|---|---|---|---|---|---|
| `E-02` | yes | yes | – | KB-002#c2, KB-002#c3, KB-002#c4, KB-025#c3 | – | – |
| `P-08` | – | yes | – | KB-002#c3 | – | – |
| `3 seconds` | yes | – | – | – | – | – |

Items the grounding check cannot find (not in b): `3 seconds`

### T-004 (cited KB-004, KB-034)

Question: E-04 keeps coming up overnight when the drive is just sat there not running anything. Measured the incoming supply at 535 V between phases. Is that the problem?

Retrieved: KB-004#c1, KB-005#c1, KB-006#c1, KB-002#c3, KB-034#c1

| Item | (a) question | (b) cited, retrieved | (c) other retrieved | (d) cited, not retrieved | (e) nowhere | other kb_v1 articles |
|---|---|---|---|---|---|---|
| `E-04` | yes | yes | – | KB-004#c2, KB-004#c3, KB-004#c4 | – | – |
| `800 V DC` | – | yes | yes | – | – | – |
| `535 V` | yes | – | – | – | – | – |
| `400 V` | – | yes | – | – | – | – |
| `565 V DC` | – | yes | – | – | – | – |
| `5 minutes` | – | yes | yes | KB-034#c2 | – | – |

Items the grounding check cannot find (not in b): `535 V`

### T-005 (cited KB-005, KB-025, KB-002)

Question: big extract fan, drive throws an overvoltage code every time we stop it (E-05). decel is at 5s. what do i change and can i change it while the fan is still running or do i have to stop it first

Retrieved: KB-005#c2, KB-004#c1, KB-002#c3, KB-006#c1, KB-025#c3

| Item | (a) question | (b) cited, retrieved | (c) other retrieved | (d) cited, not retrieved | (e) nowhere | other kb_v1 articles |
|---|---|---|---|---|---|---|
| `P-06` | – | yes | – | KB-005#c3, KB-005#c4, KB-025#c1, KB-025#c4, KB-002#c2, KB-002#c4 | – | – |
| `5 s` | yes | – | – | KB-025#c1 | – | – |
| `10.0 s` | – | yes | – | KB-005#c3, KB-025#c1 | – | – |
| `E-05` | yes | yes | yes | KB-005#c1, KB-005#c3, KB-005#c4, KB-025#c4 | – | – |

Items the grounding check cannot find (not in b): `5 s`

### T-009 (cited KB-008)

Question: E-08 on a pump motor after about 20 min running. Motor plate says 8.4 A but I see P-17 is set to 6.0. Machine turns freely by hand. Is that setting wrong?

Retrieved: KB-008#c3, KB-009#c3, KB-001#c2, KB-002#c2, KB-025#c4

| Item | (a) question | (b) cited, retrieved | (c) other retrieved | (d) cited, not retrieved | (e) nowhere | other kb_v1 articles |
|---|---|---|---|---|---|---|
| `E-08` | yes | yes | yes | KB-008#c1, KB-008#c2, KB-008#c4 | – | – |
| `P-17` | yes | yes | – | KB-008#c1, KB-008#c2, KB-008#c4 | – | – |
| `8.4 A` | yes | – | – | – | – | – |
| `6.0 A` | – | – | – | – | **yes** (number in question, unit added) | – |

Items the grounding check cannot find (not in b): `8.4 A`, `6.0 A`

### T-027 (cited KB-024, KB-022)

Question: Swapped the motor for a new one today. What do I have to put into the drive for the new motor, and does the shaft turn during the tuning? Need to know if the guards have to be back on.

Retrieved: KB-022#c4, KB-024#c5, KB-003#c3, KB-008#c3, KB-028#c3

| Item | (a) question | (b) cited, retrieved | (c) other retrieved | (d) cited, not retrieved | (e) nowhere | other kb_v1 articles |
|---|---|---|---|---|---|---|
| `P-16` | – | – | yes | KB-024#c3 | – | – |
| `P-20` | – | – | yes | KB-024#c3 | – | – |
| `P-21` | – | yes | yes | – | – | – |
| `30 seconds` | – | yes | – | – | – | – |
| `5 Hz` | – | yes | – | – | – | – |

Items the grounding check cannot find (not in b): `P-16`, `P-20`

## B. Model said insufficient_context although an expected article was retrieved

Diversity keeps only the best chunk of each article, so the model sees ONE chunk per article. Rank = position in the merged list before diversity (main search plus code boost, k=20 each), with the chunk's score.

### T-001 (calibration, failed_check grounding)

Question: vx200 on the infeed conveyor trips evry time it ramps up, E-01 flashing. wht to check first

Ticket note: E-01 overcurrent during acceleration is fully covered by KB-001.

- KB-001: kept `KB-001#c1` "Meaning" at #1 (0.8205)
  - dropped `KB-001#c2` "Possible causes" at #3 (0.7912)
  - dropped `KB-001#c3` "Recommended actions" at #4 (0.7802)
  - dropped `KB-001#c4` "When to contact support" at #2 (0.7949)

### T-002 (holdout, failed_check grounding)

Question: Getting E-02 when we stop the mixer. Ramp down is set to 3 sec. We don't really need a controlled stop on this machine, is there a way round it?

Ticket note: KB-002 gives both fixes: lengthen P-06 or set P-08 to coast to stop.

- KB-002: kept `KB-002#c1` "Meaning" at #1 (0.8379)
  - dropped `KB-002#c2` "Possible causes" at #2 (0.8304)
  - dropped `KB-002#c3` "Recommended actions" at #4 (0.8209)
  - dropped `KB-002#c4` "When to contact support" at #3 (0.8248)

### T-003 (calibration, model decision insufficient_context)

Question: Drive cut out while running at steady speed, red fault light on and E-03 on the display. One of the operators had flicked the local isolator next to the motor while it was running. Could that be the cause or is the drive damaged?

Ticket note: KB-003 lists switching an isolator between drive and motor while running as a cause of E-03.

- KB-003: kept `KB-003#c4` "When to contact support" at #1 (0.8094)
  - dropped `KB-003#c1` "Meaning" at #2 (0.8081)
  - dropped `KB-003#c2` "Possible causes" at #3 (0.7956)
  - dropped `KB-003#c3` "Recommended actions" at #4 (0.7570)

### T-004 (holdout, failed_check grounding)

Question: E-04 keeps coming up overnight when the drive is just sat there not running anything. Measured the incoming supply at 535 V between phases. Is that the problem?

Ticket note: KB-004 states the highest permitted supply is 528 V AC, so 535 V explains E-04.

- KB-004: kept `KB-004#c1` "Meaning" at #1 (0.8745)
  - dropped `KB-004#c2` "Possible causes" at #3 (0.8023)
  - dropped `KB-004#c3` "Recommended actions" at #5 (0.7753)
  - dropped `KB-004#c4` "When to contact support" at #6 (0.7747)

### T-005 (calibration, failed_check grounding)

Question: big extract fan, drive throws an overvoltage code every time we stop it (E-05). decel is at 5s. what do i change and can i change it while the fan is still running or do i have to stop it first

Ticket note: KB-005 gives the E-05 fix (increase P-06); KB-025 says ramp times can be changed while running.

- KB-005: kept `KB-005#c2` "Possible causes" at #1 (0.8853)
  - dropped `KB-005#c1` "Meaning" at #2 (0.8841)
  - dropped `KB-005#c3` "Recommended actions" at #3 (0.8386)
  - dropped `KB-005#c4` "When to contact support" at #6 (0.7886)
- KB-025: kept `KB-025#c3` "Signs that a ramp is too short" at #9 (0.7494)
  - dropped `KB-025#c1` "The two ramp parameters" at not in top 20 of any search
  - dropped `KB-025#c2` "Choosing the values" at not in top 20 of any search
  - dropped `KB-025#c4` "Stop mode" at not in top 20 of any search
  - dropped `KB-025#c5` "Changing the values" at not in top 20 of any search

### T-006 (holdout, model decision insufficient_context)

Question: Our drive drops out whenever the big compressor on the same board kicks in. Display says E-06. Motor just coasts down. Anything we can do on the drive side?

Ticket note: KB-006 covers undervoltage from a weak supply when other large loads start.

- KB-006: kept `KB-006#c1` "Meaning" at #1 (0.8341)
  - dropped `KB-006#c2` "Possible causes" at #2 (0.7536)
  - dropped `KB-006#c3` "Recommended actions" at #3 (0.7525)
  - dropped `KB-006#c4` "When to contact support" at #4 (0.7524)

### T-009 (calibration, failed_check grounding)

Question: E-08 on a pump motor after about 20 min running. Motor plate says 8.4 A but I see P-17 is set to 6.0. Machine turns freely by hand. Is that setting wrong?

Ticket note: KB-008 lists P-17 set below nameplate current as a cause and says to correct it.

- KB-008: kept `KB-008#c3` "Recommended actions" at #1 (0.8234)
  - dropped `KB-008#c1` "Meaning" at #3 (0.8117)
  - dropped `KB-008#c2` "Possible causes" at #2 (0.8199)
  - dropped `KB-008#c4` "When to contact support" at #10 (0.7371)

### T-015 (calibration, model decision insufficient_context)

Question: Power went off on site while I was halfway through saving a parameter. Now it comes up with E-15 and won't run. How do I get it back, and what exactly will I lose if I do the reset to defaults?

Ticket note: KB-015 gives the E-15 recovery; KB-028 details the restore steps and what is reset or kept.

- KB-015: kept `KB-015#c2` "Possible causes" at #1 (0.8242)
  - dropped `KB-015#c1` "Meaning" at #3 (0.8029)
  - dropped `KB-015#c3` "Recommended actions" at #2 (0.8045)
  - dropped `KB-015#c4` "When to contact support" at #4 (0.7836)
- KB-028: kept `KB-028#c4` "When to restore" at #5 (0.6978)
  - dropped `KB-028#c1` "Viewing the fault history" at not in top 20 of any search
  - dropped `KB-028#c2` "Restoring factory defaults" at #6 (0.6899)
  - dropped `KB-028#c3` "After a restore" at #12 (0.6606)

### T-016 (holdout, model decision insufficient_context)

Question: E-16 on a 5.5 kW unit. how many fans has this size got and whats the procedure to swap them, do i need to do both

Ticket note: KB-016 explains E-16 and fans per frame; KB-031 gives the replacement procedure (both fans on frame B).

- KB-016: kept `KB-016#c1` "Meaning" at #1 (0.8523)
  - dropped `KB-016#c2` "Possible causes" at #3 (0.8274)
  - dropped `KB-016#c3` "Recommended actions" at #2 (0.8449)
  - dropped `KB-016#c4` "When to contact support" at #5 (0.7693)
- KB-031: kept `KB-031#c6` "Testing" at #4 (0.8038)
  - dropped `KB-031#c1` "Overview" at #8 (0.6863)
  - dropped `KB-031#c2` "Fans per frame size" at #6 (0.7570)
  - dropped `KB-031#c3` "Preparation" at #21 (0.6388)
  - dropped `KB-031#c4` "Removing the old fan" at #10 (0.6714)
  - dropped `KB-031#c5` "Fitting the new fan" at #7 (0.7224)

### T-021 (calibration, model decision insufficient_context)

Question: Want to add a speed pot on the panel door. Which terminals does it go on and what value pot do I need?

Ticket note: KB-020 specifies a 10 kOhm potentiometer between +10V, AI1 and AGND.

- KB-020: kept `KB-020#c2` "Control terminal list" at #1 (0.6694)
  - dropped `KB-020#c1` "Overview" at #20 (0.5964)
  - dropped `KB-020#c3` "Default functions" at not in top 20 of any search
  - dropped `KB-020#c4` "Wiring rules" at #2 (0.6586)

### T-022 (holdout, model decision insufficient_context)

Question: we have a 4-20mA speed signal coming from the control room. where does it land on the drive and what do i need to set so the drive actually follows it and starts from a remote contact

Ticket note: Terminal wiring (AI2, AGND, DI1) is in KB-020; the P-01 = 1 / P-02 = 2 settings are in KB-027.

- KB-020: kept `KB-020#c4` "Wiring rules" at #1 (0.7044)
  - dropped `KB-020#c1` "Overview" at not in top 20 of any search
  - dropped `KB-020#c2` "Control terminal list" at not in top 20 of any search
  - dropped `KB-020#c3` "Default functions" at not in top 20 of any search
- KB-027: kept `KB-027#c4` "Common combinations" at #2 (0.6909)
  - dropped `KB-027#c1` "Overview" at #15 (0.6472)
  - dropped `KB-027#c2` "Start and stop command: `P-01`" at not in top 20 of any search
  - dropped `KB-027#c3` "Speed reference: `P-02`" at #19 (0.6459)
  - dropped `KB-027#c5` "Points to note" at #5 (0.6656)

### T-024 (holdout, model decision insufficient_context)

Question: about to switch on a newly installed drive for the first time. is there a list of things to check before i do, and what should the display look like if all is ok?

Ticket note: KB-022 holds the pre-power-up checklist and the expected first power-up display.

- KB-022: kept `KB-022#c3` "First power-up" at #3 (0.6857)
  - dropped `KB-022#c1` "Overview" at #14 (0.6495)
  - dropped `KB-022#c2` "Checks with the supply isolated" at #6 (0.6703)
  - dropped `KB-022#c4` "Next steps" at #20 (0.6352)

### T-027 (calibration, failed_check grounding)

Question: Swapped the motor for a new one today. What do I have to put into the drive for the new motor, and does the shaft turn during the tuning? Need to know if the guards have to be back on.

Ticket note: KB-024 covers P-16 to P-20, the P-21 auto-tune, and that the motor is energised but does not rotate.

- KB-024: kept `KB-024#c5` "Step 3: run the auto-tune" at #2 (0.7053)
  - dropped `KB-024#c1` "Overview" at #18 (0.6509)
  - dropped `KB-024#c2` "Before you start" at #9 (0.6777)
  - dropped `KB-024#c3` "Step 1: enter the motor data" at #10 (0.6756)
  - dropped `KB-024#c4` "Step 2: choose the control mode" at not in top 20 of any search
  - dropped `KB-024#c6` "Step 4: set the basic application values" at not in top 20 of any search
  - dropped `KB-024#c7` "Step 5: test" at #13 (0.6657)

### T-030 (holdout, model decision insufficient_context)

Question: i put the max frequency up from 50 to 70 last week and since then the drive trips with E-01 on start. didnt touch anything else. why would that do it?

Ticket note: KB-026 explains raising P-04 steepens the ramp; KB-001 gives the E-01 fix of increasing P-05.

- KB-026: **not retrieved**
- KB-001: kept `KB-001#c1` "Meaning" at #1 (0.8205)
  - dropped `KB-001#c2` "Possible causes" at #3 (0.7912)
  - dropped `KB-001#c3` "Recommended actions" at #4 (0.7802)
  - dropped `KB-001#c4` "When to contact support" at #2 (0.7949)

### T-033 (calibration, model decision insufficient_context)

Question: Putting together our PM plan. What routine maintenance do these drives need and how often?

Ticket note: KB-029 is the routine maintenance schedule with all intervals.

- KB-029: kept `KB-029#c5` "Related articles" at #1 (0.7056)
  - dropped `KB-029#c1` "Overview" at #6 (0.6518)
  - dropped `KB-029#c2` "Schedule" at #2 (0.7054)
  - dropped `KB-029#c3` "Before any task with the supply isolated" at #19 (0.6125)
  - dropped `KB-029#c4` "Records" at #3 (0.6954)
  - dropped `KB-029#c6` "When to contact support" at #15 (0.6210)

### T-037 (calibration, model decision insufficient_context)

Question: got a spare vx200 thats been sat on the stores shelf about 18 months, never powered. can i just fit it and run?

Ticket note: KB-033: after 1 to 2 years the capacitors must be re-formed for at least 1 hour with no run command.

- KB-033: kept `KB-033#c1` "Storage conditions" at #6 (0.6583)
  - dropped `KB-033#c2` "Why long storage matters" at not in top 20 of any search
  - dropped `KB-033#c3` "What to do after storage" at #15 (0.6278)
  - dropped `KB-033#c4` "Re-forming procedure (1 to 2 years)" at not in top 20 of any search
  - dropped `KB-033#c5` "Drives kept as spares" at not in top 20 of any search
  - dropped `KB-033#c6` "After storage in a cold place" at not in top 20 of any search

### T-041 (calibration, model decision insufficient_context)

Question: There is a triangle symbol with wavy lines on the side of the unit. One of the apprentices asked what it means and I wasn't sure.

Ticket note: KB-035 explains the hot-surface symbol near the heatsink.

- KB-035: kept `KB-035#c2` "Lightning flash in a triangle: dangerous voltage" at #1 (0.6806)
  - dropped `KB-035#c1` "Overview" at #11 (0.5682)
  - dropped `KB-035#c3` "Lightning flash with "5 min": stored charge" at #9 (0.5794)
  - dropped `KB-035#c4` "Wavy lines in a triangle: hot surface" at #3 (0.6701)
  - dropped `KB-035#c5` "Open book: read the instructions" at #4 (0.6075)
  - dropped `KB-035#c6` "Earth symbol" at #2 (0.6711)
  - dropped `KB-035#c7` "The rating label" at #5 (0.6019)

### T-105 (calibration, model decision insufficient_context)

Question: during rainy season our supply voltage dips sometimes and drive stops with fault. after supply ok it doesnt start again by itself

Ticket note: Undervoltage symptom described without code; may also involve auto-restart setting if covered

- KB-006: kept `KB-006#c2` "Possible causes" at #1 (0.7282)
  - dropped `KB-006#c1` "Meaning" at not in top 20 of any search
  - dropped `KB-006#c3` "Recommended actions" at #3 (0.6957)
  - dropped `KB-006#c4` "When to contact support" at not in top 20 of any search

## C. Summary: what each cause would explain

21 "answer" tickets were escalated in run 1. AC1 also fails on T-039, T-104 (answered, but not citing an expected article); not covered here.

| Cause | Tickets | Count |
|---|---|---|
| 1. Grounding: every unsupported item is in a dropped chunk of a cited article (d); the check sees only ONE chunk per cited article | T-001, T-027 | 2 |
| 2. Grounding: every unsupported item is a number taken from the question (a), incl. a bare number given a unit | T-002, T-004, T-005, T-009 | 4 |
| 2b. Grounding: unsupported items from more than one of these sources | none | 0 |
| 3. Grounding: an unsupported item not in the question nor in any chunk of a cited article (invented, or from a non-cited article) | none | 0 |
| 4. Model chose insufficient_context with an expected article retrieved (B, no failed_check) | T-003, T-006, T-015, T-016, T-021, T-022, T-024, T-030, T-033, T-037, T-041, T-105 | 12 |
| 4a. of which the expected article(s) reached the model only as a chunk other than "Possible causes" / "Recommended actions" | T-003, T-006, T-016, T-021, T-022, T-024, T-030, T-033, T-037, T-041 | 10 |
| 5. No expected article retrieved (retrieval miss) | T-101, T-102 | 2 |
| 6. Model chose out_of_scope | T-010 | 1 |

Grounding rows 1-3 classify each unsupported item (not in b) once: from the question if the question has it, or has its bare number (even if a dropped chunk also has it, e.g. T-005 `5 s`; T-009 `6.0 A` is the question's "6.0" with a unit added); else from a dropped chunk if (d); else invented.

Cause 4a is a free proxy only: it shows which section the model saw, not whether the answer was in it. The ticket notes in section B let a human check.
