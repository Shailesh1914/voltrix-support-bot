"""The response object and fixed escalation message (spec 02, "Output")."""

from dataclasses import dataclass, field

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
