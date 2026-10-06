# Query and Escalation Spec — Voltrix VX-200 Support Bot

Status: Version 1.1, approved by Shailesh on 2026-10-06

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
1. Query normalisation: the letter E or P (any case), an optional
   space or hyphen, then 1-3 digits, is converted to "E-" or "P-"
   plus the number zero-padded to 2 digits.
   Examples: E1, e-1, E 01, E-001 -> E-01; P5 -> P-05.
   The normalised text replaces the original in the retrieval query.
   The original question is kept for the handoff record.
2. Retrieval: call search(query, k=5) from the retrieval contract
   (specs/03-retrieval-contract.md). The query flow never reads
   index files directly. The score scale and the output of search()
   are defined in specs/03-retrieval-contract.md (Step 5).
3. Unknown fault codes (after retrieval): at startup, build the set
   of known fault codes from the E-xx codes in article titles in the
   index metadata. If the normalised question contains an E-xx code
   not in that set, escalate (reason: "insufficient_context") without
   calling the model. The handoff record includes the retrieved
   chunks.
4. Escalation decision (ONE decision, two signals):
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
5. Escalation reasons:
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
6. Generation rules (apply to the model call in step 4b):
   - Generation model: a Claude model on Amazon Bedrock, used both
     when running locally and when deployed on AWS (same model ID).
     Exact model ID pinned at Step 8. Temperature 0.
   - Structural tests use a fake generator (fixed responses, no model
     calls). The real model is called only in evaluation runs.
   - Every factual statement must come from the retrieved chunks.
     No outside knowledge. Never invent numbers, codes or settings.
   - Safety warning = any line starting with WARNING, DANGER or
     CAUTION, or any section whose heading contains "Safety" or
     "Warning". If a used chunk contains one, the answer includes it.

## Output
A response object with:
- status: "answered" or "escalated"
- answer: the answer text; if escalated, the fixed escalation
  message below with the handoff_id filled in
- citations: list of article_id and title of the articles in
  used_article_ids (empty if escalated)
- escalation_reason: "low_similarity" | "insufficient_context" |
  "out_of_scope" (empty if answered)
- handoff_id: the handoff_id of the handoff record (empty if
  answered)

Escalation message to the user (fixed text):
"I can't answer this reliably. Your question has been passed to a
support engineer with the details found so far. Reference: <handoff_id>."

## Escalation handoff
Every escalation creates a handoff record for the human queue with:
- a unique handoff_id
- the question (as received, and after normalisation), with
  personal data masked (see below)
- all retrieved chunks: chunk_id, article_id, text, similarity_score
- the escalation_reason
- the kb_version used (ACTIVE_KB_VERSION)
So the human agent never starts cold.
Locally: appended to a JSONL file. On AWS: decided at Step 13.
No data beyond the question text is stored about the person asking.
Personal data: before a handoff record is stored, emails and phone
numbers in the question are masked (e.g. [EMAIL], [PHONE]). The
handoff stores only the masked text.

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
   must appear in the retrieved chunks.
8. Unknown fault codes (Processing step 3) always escalate without
   a model call, and their handoff record includes the retrieved
   chunks.
9. The ESCALATION_THRESHOLD in config equals the value written in
   this spec (automated test).

Grounding beyond criterion 7 (every statement supported by chunks)
will be measured by an evaluation designed at Step 9.

## Out of scope for the query flow
- Building or changing the index (ingestion side).
- Multi-turn conversation memory.
