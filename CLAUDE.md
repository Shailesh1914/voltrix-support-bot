# Project briefing for Claude Code

Voltrix VX-200 support bot: a RAG support bot for a FICTIONAL
variable frequency drive. All data is synthetic. Spec-first project:
specs are written and approved by the human (Shailesh) before code.

## Read first
- specs/00-scope.md                 scope and out-of-scope list
- specs/01-ingestion-spec.md        ingestion rules
- specs/02-query-escalation-spec.md query flow and escalation
- specs/03-retrieval-contract.md    the ONLY ingestion/query interface
- specs/04-session-plan.md          which session owns which folders

## Hard rules for every session
1. NEVER edit anything in specs/. If a spec is wrong, ambiguous or
   blocks the work, STOP and explain the problem to the human.
2. NEVER edit data/ or evals/support_questions.jsonl. They are frozen.
3. Only edit the folders your session owns (see specs/04-session-plan.md).
   If the task needs changes elsewhere, STOP and ask.
4. The query side uses ingestion ONLY through open_retrieval() and
   the Retriever methods search(), kb_info() and article_chunks()
   (specs/03-retrieval-contract.md). Never read index, metadata or
   manifest files from query code.
5. ESCALATION_THRESHOLD lives only in spec 02 and one config setting.
   Never choose or change its value yourself.
6. Never put secrets (AWS keys etc.) in code or commit them. Use .env.
7. Never commit or push. The human reviews and commits.

## Working style
- Python, with the project virtual environment in .venv.
- Write tests alongside code; run them before saying you are done.
- When finished, summarise which files you changed and why.
