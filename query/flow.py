"""The query flow (spec 02, "Processing").

Order for one question:
1. mask personal data (decision 3), then normalise fault codes
2. search(k=5) through the retrieval contract
3. unknown fault code -> escalate "insufficient_context", no model call
4a. highest similarity_score below the threshold -> escalate
    "low_similarity", no model call
4b. one generator call:
    - service error -> escalate "service_error" (decision 6)
    - malformed output -> escalate "insufficient_context" (decision 6)
    - decision insufficient_context / out_of_scope -> escalate with it
    - decision answer, then in order:
      - no used_article_ids -> "insufficient_context" (decision 7)
      - citation check: a used article not retrieved -> "insufficient_context" (4c)
      - grounding check (criterion 7) fails -> "insufficient_context" (decision 4)
      each of these three stores the draft and the check's name in the
      handoff (decision 11)
      - missing safety warnings added word for word at the start (decision 5)
      -> answered, with citations
"""

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from ingestion import Chunk, KBInfo
from query.checks import safety_warnings, uncited_retrieved, ungrounded, with_safety_warnings
from query.config import SEARCH_K, ConfigError, require_threshold
from query.fault_codes import known_fault_codes, unknown_fault_codes
from query.generator import Generator, GeneratorServiceError, MalformedOutput
from query.handoff import HandoffStore, build_handoff, utc_now
from query.masking import mask_personal_data
from query.normalise import normalise_codes
from query.response import QueryResponse, answered_response, citations_for, escalated_response


class Retriever(Protocol):
    """The two retrieval-contract functions the flow uses (spec 03)."""

    def search(self, query: str, k: int) -> list[Chunk]: ...
    def kb_info(self) -> KBInfo: ...


class QueryFlow:
    def __init__(
        self,
        retriever: Retriever,
        generator: Generator,
        *,
        threshold: float,
        handoff_store: HandoffStore,
        kb_version: str,
        clock: Callable[[], datetime] = utc_now,
    ):
        self._threshold = require_threshold(threshold)
        info = retriever.kb_info()
        if info.kb_version != kb_version:
            raise ConfigError(
                f"retriever serves {info.kb_version!r} but ACTIVE_KB_VERSION is {kb_version!r}"
            )
        self._retriever = retriever
        self._generator = generator
        self._handoff_store = handoff_store
        self._kb_version = kb_version
        self._clock = clock
        # Built once at startup (step 3).
        self.known_fault_codes = known_fault_codes(info)

    def ask(self, question: str) -> QueryResponse:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be non-empty text")

        received = mask_personal_data(question)
        normalised = normalise_codes(received)
        chunks = self._retriever.search(normalised, k=SEARCH_K)

        def escalate(reason: str, rejected_answer: str = "", failed_check: str = "") -> QueryResponse:
            return self._escalate(received, normalised, chunks, reason, rejected_answer, failed_check)

        if unknown_fault_codes(normalised, self.known_fault_codes):
            return escalate("insufficient_context")

        top_score = max((c.similarity_score for c in chunks), default=None)
        if top_score is None or top_score < self._threshold:
            return escalate("low_similarity")

        try:
            output = self._generator.generate(normalised, chunks)
        except GeneratorServiceError:
            return escalate("service_error")
        except MalformedOutput:
            return escalate("insufficient_context")
        if output.decision != "answer":
            return escalate(output.decision)

        failed_check = (
            "no_citations" if not output.used_article_ids
            else "citation" if uncited_retrieved(output.used_article_ids, chunks)
            else "grounding" if ungrounded(output.answer, output.used_article_ids, chunks)
            else ""
        )
        if failed_check:
            return escalate("insufficient_context", output.answer, failed_check)

        warnings = safety_warnings(output.used_article_ids, chunks)
        return answered_response(
            with_safety_warnings(output.answer, warnings),
            citations_for(output.used_article_ids, chunks),
        )

    def _escalate(
        self,
        received: str,
        normalised: str,
        chunks: list[Chunk],
        reason: str,
        rejected_answer: str = "",
        failed_check: str = "",
    ) -> QueryResponse:
        record = build_handoff(
            question_received=received,
            question_normalised=normalised,
            chunks=chunks,
            escalation_reason=reason,
            kb_version=self._kb_version,
            created_at=self._clock(),
            rejected_answer=rejected_answer,
            failed_check=failed_check,
        )
        # Stored before the user is told; a failed write raises, so no
        # reference is ever given for a handoff that does not exist.
        self._handoff_store.append(record)
        return escalated_response(reason, record.handoff_id)
