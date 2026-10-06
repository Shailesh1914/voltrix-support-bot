# Voltrix VX-200 Support Bot — Scope Statement

## Product
Fictional variable frequency drive "Voltrix VX-200" from fictional
company "Voltrix Drives". All data is synthetic.

## Users
Maintenance technicians and plant engineers asking questions about
installation, fault codes, parameters and routine maintenance.

## What the bot does
- Answers one question at a time using only the knowledge base.
- Cites the source article in every answer.
- Escalates to a human queue when confidence is low.

## The ONE judgement call
Answer, or escalate. (keep it to one.)

## Out of scope
- Calculations or drive sizing for a user's application → escalate.
- Pricing, ordering, delivery questions → escalate.
- Multi-turn conversation memory. There is no conversation memory;
  "one escalation handoff" means only the handoff record passed to
  the human.
- Safety-critical live-electrical work instructions beyond what the
  knowledge base states → escalate.
- Questions about other manufacturers' products → escalate.

## Data rules
- All data synthetic. No personal data of any kind in tickets
  (no names, emails, phone numbers, addresses — not even fake ones).
- Knowledge base: Markdown articles. Two versions: kb_v1, kb_v2.

## Technology
Python, run locally first; deploy to AWS later.

## Human roles
- Owner and independent reviewer of labelled questions: Shailesh
- Approver of escalation threshold: Shailesh