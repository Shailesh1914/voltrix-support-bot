"""The generator interface (spec 02, Processing steps 5b and 7).

One model call per question returns structured output: decision,
answer and used_article_ids. Whatever produced it (the real model or
the fake), the output only reaches the flow through validate_output().

Two failures, two escalation reasons (spec 02, decision 6):
- MalformedOutput -> "insufficient_context"
- GeneratorServiceError -> "service_error"
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ingestion import Chunk

DECISIONS = ("answer", "insufficient_context", "out_of_scope")
OUTPUT_FIELDS = ("decision", "answer", "used_article_ids")


class MalformedOutput(Exception):
    """The model's output is not valid structured output."""


class GeneratorServiceError(Exception):
    """The model service failed (e.g. an Anthropic API error)."""


@dataclass(frozen=True)
class GeneratorOutput:
    decision: str
    answer: str
    used_article_ids: tuple[str, ...]


class Generator(Protocol):
    def generate(self, question: str, chunks: list[Chunk]) -> GeneratorOutput:
        """One model call. Raises MalformedOutput or GeneratorServiceError."""
        ...


def validate_output(raw: object) -> GeneratorOutput:
    """Check raw structured output; raise MalformedOutput if invalid.

    Structure only. Whether the cited articles were retrieved, and
    whether an answer cites anything at all, are flow checks (steps 5c and 5d,
    decision 7).
    """
    if not isinstance(raw, dict):
        raise MalformedOutput(f"output must be an object, got {type(raw).__name__}")
    if set(raw) != set(OUTPUT_FIELDS):
        raise MalformedOutput(
            f"output fields must be exactly {sorted(OUTPUT_FIELDS)}, got {sorted(raw)}"
        )
    decision, answer, used = raw["decision"], raw["answer"], raw["used_article_ids"]
    if decision not in DECISIONS:
        raise MalformedOutput(f"decision must be one of {DECISIONS}, got {decision!r}")
    if not isinstance(answer, str):
        raise MalformedOutput("answer must be text")
    if decision == "answer" and not answer.strip():
        raise MalformedOutput("decision is 'answer' but the answer text is empty")
    if not isinstance(used, list) or not all(isinstance(a, str) and a.strip() for a in used):
        raise MalformedOutput("used_article_ids must be a list of non-empty strings")
    # Repeats carry no meaning; keep the first of each, in order.
    return GeneratorOutput(decision, answer, tuple(dict.fromkeys(a.strip() for a in used)))


FakeResponse = GeneratorOutput | dict | BaseException


class FakeGenerator:
    """Fixed responses, no model calls (spec 02, Processing step 7).

    response is one of:
    - a GeneratorOutput, returned as is
    - a dict, passed through validate_output() like real model output
    - an exception, raised (e.g. GeneratorServiceError)
    - a function (question, chunks) -> any of the above
    Every call is recorded in .calls.
    """

    def __init__(self, response: FakeResponse | Callable[[str, list[Chunk]], FakeResponse]):
        self._response = response
        self.calls: list[tuple[str, list[Chunk]]] = []

    def generate(self, question: str, chunks: list[Chunk]) -> GeneratorOutput:
        self.calls.append((question, list(chunks)))
        response = self._response
        if not isinstance(response, (BaseException, GeneratorOutput, dict)) and callable(response):
            response = response(question, chunks)
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, GeneratorOutput):
            return response
        return validate_output(response)
