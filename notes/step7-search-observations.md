# Search observations from Step 7d (kb_v1, no prefix, k=5)

- T-102 style (symptom wording, no fault code): KB-001 not in top 20.
  Nearest relevant: KB-009 at rank 6.
- T-103 style: KB-034 at rank 3; KB-020 at rank 1 also contains
  the 5-minute wait.
- T-109 style (pricing, should escalate): highest score of the
  three, 0.73. Threshold alone cannot catch it.
- All scores in a narrow band: 0.59-0.73.
- My view after reading KB-001: <your expert opinion>
- CI note: full ingestion suite takes ~3.5 min (idempotence test is
  the slowest). Consider fast/slow split in Step 11.
- KB content improvement for a future version: real drive manuals
  mark hazards with WARNING / DANGER / CAUTION lines; our KB has
  none. Consider adding them (with symptom wording for fault
  articles) in a kb_v3.