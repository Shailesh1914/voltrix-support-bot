"""The response object and fixed escalation message (spec 02, "Output")."""

from dataclasses import dataclass, field

from ingestion import Chunk

ESCALATION_MESSAGE = (
    "I can't answer this reliably. Your question has been passed to a "
    "support engineer with the details found so far. Reference: {handoff_id}."
)


@dataclass(frozen=True)
class Citation:
    article_id: str
    title: str


@dataclass(frozen=True)
class QueryResponse:
    status: str  # "answered" | "escalated"
    answer: str
    citations: list[Citation] = field(default_factory=list)
    escalation_reason: str = ""  # empty if answered
    handoff_id: str = ""  # empty if answered


def escalated_response(escalation_reason: str, handoff_id: str) -> QueryResponse:
    return QueryResponse(
        status="escalated",
        answer=ESCALATION_MESSAGE.format(handoff_id=handoff_id),
        escalation_reason=escalation_reason,
        handoff_id=handoff_id,
    )


def answered_response(answer: str, citations: list[Citation]) -> QueryResponse:
    return QueryResponse(status="answered", answer=answer, citations=citations)


def citations_for(used_article_ids, chunks: list[Chunk]) -> list[Citation]:
    """article_id and title of each used article, in the model's order.

    Every used article must be among the chunks (citation check first).
    """
    titles = {}
    for c in chunks:
        titles.setdefault(c.article_id, c.title)
    return [Citation(a, titles[a]) for a in used_article_ids]
