# Query and Escalation Spec — Voltrix VX-200 Support Bot

Status: Version 1.7, approved by Shailesh on 2026-10-14

## Goal
Given one user question, retrieve relevant chunks, generate an answer
grounded ONLY in those chunks, and escalate to a human queue when
the system should not answer.
The query flow runs synchronously, in the request path. It is the
ONLY place an escalation decision is made.

## Input
- One question as text. No conversation memory (one question at a time).

## Configuration
- ACTIVE_KB_VERSION: the KB version served (default v1). The handoff
  records it. Index promotion (Step 12) changes it.
- ESCALATION_THRESHOLD: see below.

## Processing
1. Personal data masking: emails and phone numbers in the question
   are replaced with [EMAIL] and [PHONE]. The masked text is used
   in every later step: retrieval, the model call and the handoff
   record. See Implementation decision 3.
2. Query normalisation: the letter E or P (any case), an optional
   space or hyphen, then 1-3 digits, is converted to "E-" or "P-"
   plus the number zero-padded to 2 digits.
   Examples: E1, e-1, E 01, E-001 -> E-01; P5 -> P-05.
   The normalised text replaces the original in the retrieval query.
   The masked question as received is also kept for the handoff
   record.
3. Retrieval: call search(query, k=5) from the retrieval contract
   (specs/03-retrieval-contract.md). The query flow never reads
   index files directly. The score scale and the output of search()
   are defined in specs/03-retrieval-contract.md (Step 5).
4. Unknown fault codes (after retrieval): at startup, build the set
   of known fault codes from the E-xx codes in the article titles
   returned by kb_info() (specs/03-retrieval-contract.md). If the
   normalised question contains an E-xx code not in that set,
   escalate (reason: "insufficient_context") without calling the
   model. The handoff record includes the retrieved
   chunks.
5. Escalation decision (ONE decision, two signals):
   a. Retrieval check: if the highest single chunk similarity_score
      is below ESCALATION_THRESHOLD, escalate (reason: "low_similarity").
   b. Answerability check and generation: otherwise, ONE model call.
      The model reads the retrieved chunks and returns structured
      output:
      - decision: "answer" | "insufficient_context" | "out_of_scope"
      - answer text
      - used_article_ids
      If the decision is "insufficient_context" or "out_of_scope",
      escalate with that reason.
   c. Citation check: the code checks that every used_article_id is
      among the retrieved chunks. If not, escalate
      (reason: "insufficient_context").
   d. Empty citations: if the decision is "answer" but
      used_article_ids is empty, escalate (reason:
      "insufficient_context"). See Implementation decision 7.
   e. Grounding check: every E-xx code, P-xx code and number with a
      unit in the answer must appear in the chunks of the cited
      articles (criterion 7). If not, escalate (reason:
      "insufficient_context").
   f. Safety warnings: missing warning lines from the cited
      articles are added at the start of the answer (decision 5).
   The first check that fails decides the escalation. Order:
   d, c, e, then f.
6. Escalation reasons:
   - out_of_scope = the out-of-scope list in specs/00-scope.md.
   - Everything else not answered by the chunks = insufficient_context.
   - Partial questions: if any part of the question is not answered
     by the retrieved chunks, escalate the whole question.
   - Live-electrical work: questions asking how to work on an
     energised drive or motor are out_of_scope. Safety information
     that IS in the KB (e.g. isolation, discharge time) may be
     answered.
   - The escalation reason is recorded for the human agent but is
     NOT graded in the evaluation.
7. Generation rules (apply to the model call in step 4b):
   - Generation model: Claude Haiku 4.5 via the Anthropic API
     (Claude Console). Amazon Bedrock is not available on this AWS
     account (AWS declined access, case 179169048500913).
     Model ID: claude-haiku-4-5-20251001. Temperature 0.
   - The API key is read from VOLTRIX_ANTHROPIC_API_KEY, loaded from
  ~/.config/voltrix/secrets.env (outside the project). It is never 
  named ANTHROPIC_API_KEY, and the bot refuses to start if 
  ANTHROPIC_API_KEY is set in its environment.
   - The Bedrock generator is kept but unused. Switching back to 
   Bedrock is a spec change and requires re-running the evaluation.
   - Structural tests use a fake generator (fixed responses, no model
     calls). The real model is called only in evaluation runs and manual smoke tests.
   - Every factual statement must come from the retrieved chunks.
     No outside knowledge. Never invent numbers, codes or settings.
   - Safety warning = any line starting with WARNING, DANGER or
   CAUTION (case-sensitive). See Implementation decision 5.

## Output
A response object with:
- status: "answered" or "escalated"
- answer: the answer text; if escalated, the fixed escalation
  message below with the handoff_id filled in
- citations: list of article_id and title of the articles in
  used_article_ids (empty if escalated)
- escalation_reason: "low_similarity" | "insufficient_context" |
  "out_of_scope" | "service_error" (empty if answered)
- handoff_id: the handoff_id of the handoff record (empty if
  answered)

Escalation message to the user (fixed text):
"I can't answer this reliably. Your question has been passed to a
support engineer with the details found so far. Reference: <handoff_id>."

## Escalation handoff
Every escalation creates a handoff record for the human queue with:
- a unique handoff_id
- created_at (UTC)
- the question (as received, and after normalisation), masked
- all retrieved chunks: chunk_id, article_id, text, similarity_score
- the escalation_reason
- the kb_version used (ACTIVE_KB_VERSION)
- rejected_answer and failed_check (filled only when a check stops
  an answer; see Implementation decision 11)
So the human agent never starts cold.
Locally: appended to a JSONL file. On AWS: decided at Step 13.
No data beyond the question text is stored about the person asking.
Personal data: masking happens first (Processing step 1), so the
handoff only ever contains masked text.

## ESCALATION_THRESHOLD (the most important number in this spec)
This number trades off two costs:
- Too LOW: the bot answers when it should escalate.
  Cost: a wrong answer reaches a technician (possible equipment
  damage or safety risk).
- Too HIGH: the bot escalates when it could have answered.
  Cost: needless human workload; slower help for the technician.

Given the safety risk in industrial equipment, wrong answers are
treated as more costly than extra escalations.

Value: NOT YET SET. To be set by Shailesh at Step 9 using this method:
1. Run retrieval for every ticket in evals/support_questions.jsonl
   against kb_v1.
2. Record the highest similarity_score for each ticket.
3. Compare the scores of "answer" tickets with "escalate" tickets.
4. Choose the value that meets the targets below.
5. Record here: the value, the date, and a short reason.
The value lives in this spec and in ONE config setting.
It must never be changed in code without updating this spec.

Note: tuning and measuring on the same tickets can flatter the
results. To be reviewed at Step 9.

## Acceptance criteria
Evaluation (measured on evals/support_questions.jsonl):
1. Answerable tickets: at least 85% are answered AND cite at least
   one of their expected_article_ids.
2. Escalate tickets: at least 95% are escalated.
   Note: the escalate set is small (22 tickets), so 1 miss = 95.5%.
   Revisit at Step 9.

Metrics (reported, not gates):
- Wrong-escalation rate: answerable tickets that were escalated.
- Two-article tickets: the rate at which BOTH expected articles are
  cited.

Reproducibility: evaluation runs once per pull request. For the
threshold decision and before release, run 3 times and use the
WORST score.

Structural (must hold 100% of the time):
3. Every escalation produces a complete handoff record.
   "Complete" = all handoff fields listed above are present,
   independent of where the record is stored.
4. Every citation refers to an article that was in the retrieved
   chunks. The bot never cites an article it did not retrieve.
5. Fault code normalisation: E1, e1, E01, E-1, e-01, E 01, E-001 all
   become E-01; P5 becomes P-05; ordinary words are unchanged.
6. Every response has a valid status, and escalated responses have
   an escalation_reason, a handoff_id, and an answer containing the
   fixed escalation message with that handoff_id.
7. Every E-xx code, P-xx code and number with a unit in an answer
   must appear in the chunks of the CITED articles.
8. Unknown fault codes (Processing step 4) always escalate without
   a model call, and their handoff record includes the retrieved
   chunks.
9. The ESCALATION_THRESHOLD in config equals the value written in
   this spec (automated test).

Grounding beyond criterion 7 (every statement supported by chunks)
will be measured by an evaluation designed at Step 9.

## Out of scope for the query flow
- Building or changing the index (ingestion side).
- Multi-turn conversation memory.

## Implementation decisions (Version 1.3-1.7)
1. ESCALATION_THRESHOLD is a constant in query/config.py, never in
   .env. When set, this spec records it as a line "Value: <number>",
   and a test checks the two match.
2. The model ID is also a constant in query/config.py, checked
   against this spec by a test. Pinned model ID (Anthropic API):
   claude-haiku-4-5-20251001.
3. Personal data masking (emails, phone numbers) is applied FIRST,
   before normalisation. The masked text is used everywhere:
   retrieval, the model, and the handoff record.
4. If the grounding check (criterion 7) fails, escalate with
   reason "insufficient_context". The answer text is never edited.
5. Safety warnings: a line starting with WARNING, DANGER or
   CAUTION (case-sensitive) in any retrieved chunk of a used
   article. If the answer lacks it, the code adds it word for word at the START of the answer. Heading-based detection is not used (it would depend on
   ingestion's chunk format). The prompt also instructs the model
   to include safety precautions from the chunks.
6. Malformed model output -> escalate, reason "insufficient_context".
   Model API errors (Anthropic API, or Bedrock if used) -> escalate
   with a handoff, reason "service_error". The evaluation treats
   service_error as a run failure, never as a correct escalation.
7. decision="answer" with empty used_article_ids -> escalate,
   reason "insufficient_context".
8. Handoff records go to HANDOFF_PATH (default
   handoffs/handoffs.jsonl). handoff_id is a uuid4. Each record
   includes created_at (UTC).
9. Units for criterion 7: V, kV, A, mA, Hz, kHz, W, kW, hp, ms, s,
   sec, min, minutes, h, hours, °C, %, mm, mm², m, Nm, rpm, Ω, kΩ,
   µF, VAC, VDC, tolerant of spacing and aliases.
10. The system prompt in query/prompt.py is product behaviour.
    Any change to it requires Shailesh's approval, like a spec
    change, and is recorded in the commit message.
11. When a check stops an answer (no_citations, citation, grounding),
    the handoff record also stores rejected_answer (the model's
    draft, never shown to the user) and failed_check (the name of
    the check). Both are empty for other escalations.
12. A test stores a SHA-256 fingerprint of the system prompt. Any
    change to the prompt fails this test until Shailesh approves it
    and the fingerprint is updated in the same commit.
