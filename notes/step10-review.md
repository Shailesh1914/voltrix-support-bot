# Step 10 — Independent review (Shailesh, 2026-10-18)

Scope: label review of the 8 failing tickets, answer review of a
sample, free rescoring of the 3 whole-articles runs.
Deferred to the next iteration: kb_v3 content, new "statement
without a question" tickets, grounding fixes (T-009, T-021).

Principle: every label decision is based on what the KB says,
not on what improves the score.

## Label decisions
| Ticket | Decision | Reason (KB evidence) |
|---|---|---|
| T-005 | Keep (answer) | KB answers it ("try doubling"); the bot invented "15 s or 20 s" and grounding correctly stopped it. Real bot weakness. |
| T-009 | Keep (answer) | KB answers it; grounding false alarm ("6.0" vs "6.0 A"). Fix in next iteration. |
| T-016 | Keep (answer) | KB-031 has a "Fans per frame size" table and says "On frame B, replace both fans at the same time"; 5.5 kW is frame B; procedure in the same article. KB-031 was retrieved; the bot was over-cautious. |
| T-021 | Keep (answer) | KB-020: "Use a 10 kΩ potentiometer between +10V, AI1 and AGND". The rejected draft was correct; grounding falsely rejected "10 kΩ". Grounding bug, next iteration. |
| T-030 | Keep (answer); expected articles unchanged (KB-026, KB-001) | KB-026: ramp times are measured between 0 Hz and P-04; raising P-04 makes the motor accelerate faster unless the ramps are lengthened. The bot was over-cautious. |
| T-039 | Expected: KB-034 or KB-036 ("any") | KB-036 states that STOP does not isolate the drive and the power terminals stay live; the bot's answer was correct and passed all checks in 3 runs. |
| T-101 | Keep (answer) | KB is meant to answer it; retrieval gap. Fix with kb_v3 (next iteration). |
| T-102 | Keep (answer) | Same as T-101. |

## Findings
- 1 label changed out of 8 reviewed (T-039).
- My initial guesses for T-016 and T-021 were wrong; the KB answered
  both. Decisions were made from the KB text, not from guesses.
- T-016, T-021, T-030: the bot had the information and still
  escalated (over-cautious). Next iteration.
- T-021 shows a grounding false rejection ("10 kΩ" is in KB-020).

## Answer review (10.2)
<to be filled>

## Rescoring (10.4)
<to be filled>