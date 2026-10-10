# Session Plan — Voltrix VX-200 Support Bot

Status: Version 1.1, approved by Shailesh on 2026-10-10

## Principle (Section 1.5)
Ingestion and query share no evolving state once the retrieval
contract is fixed, so they are built in separate Claude Code
sessions. The escalation threshold is NOT split: decisions about it
belong to the query side and the human approver only.

## Sessions and ownership
| Session | Owns (may edit) | Implements |
|---|---|---|
| I: Ingestion | ingestion/, tests/structural/ingestion/ (incl. its conftest.py), tests/fixtures/ | specs 01 and 03 |
| Q: Query | query/, tests/structural/query/ (incl. its conftest.py) | spec 02, using spec 03 |
| E: Evaluation | evals/*.py, evals/reports/ | eval runner, threshold calibration report |
| D: Delivery | .github/, deployment files | CI, index promotion, AWS deployment |

Shared files (requirements.txt, config): changed only with the
human's approval, and noted in the session summary.

## Read-only for ALL sessions
- specs/ (human-owned)
- data/ (frozen knowledge base)
- evals/support_questions.jsonl (frozen labelled tickets)

## Escalation threshold
- Value lives in spec 02 and one config setting only.
- Session E produces the evidence (score distributions, metrics).
- Shailesh decides the value and records it in spec 02.
- Session Q reads it from config; it never sets it.

## Contract changes
Neither side changes specs/03-retrieval-contract.md. If a change is
needed, the session stops and explains why; the human decides.

## Session hygiene
- Start each session fresh with `claude`.
- Return to an unfinished session with /resume, not by mixing
  ingestion and query work in one session.
- Before every commit, the human checks with `git status` and
  `git diff --stat` that only the session's own folders changed.
