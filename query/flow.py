"""The query flow (spec 02, "Processing").

Order for one question:
1. mask personal data (decision 3), then normalise fault codes
2. search(k=5) through the retrieval contract
3. unknown fault code -> escalate "insufficient_context", no model call
4a. highest similarity_score below the threshold -> escalate
    "low_similarity", no model call
4b. one generator call (stage c), then the checks of 4c and decisions
    4-7 (stage d)
"""

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from ingestion import Chunk, KBInfo
from query.config import SEARCH_K, ConfigError, require_threshold
from query.fault_codes import known_fault_codes, unknown_fault_codes
from query.handoff import HandoffStore, build_handoff, utc_now
from query.masking import mask_personal_data
from query.normalise import normalise_codes
from query.response import QueryResponse, escalated_response


class Retriever(Protocol):
    """The two retrieval-contract functions the flow uses (spec 03)."""

    def search(self, query: str, k: int) -> list[Chunk]: ...
    def kb_info(self) -> KBInfo: ...


class Generator(Protocol):
    def generate(self, question: str, chunks: list[Chunk]): ...


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

        def escalate(reason: str) -> QueryResponse:
            return self._escalate(received, normalised, chunks, reason)

        if unknown_fault_codes(normalised, self.known_fault_codes):
            return escalate("insufficient_context")

        top_score = max((c.similarity_score for c in chunks), default=None)
        if top_score is None or top_score < self._threshold:
            return escalate("low_similarity")

        self._generator.generate(normalised, chunks)
        raise NotImplementedError("answer path: stages c and d")

    def _escalate(
        self, received: str, normalised: str, chunks: list[Chunk], reason: str
    ) -> QueryResponse:
        record = build_handoff(
            question_received=received,
            question_normalised=normalised,
            chunks=chunks,
            escalation_reason=reason,
            kb_version=self._kb_version,
            created_at=self._clock(),
        )
        # Stored before the user is told; a failed write raises, so no
        # reference is ever given for a handoff that does not exist.
        self._handoff_store.append(record)
        return escalated_response(reason, record.handoff_id)
