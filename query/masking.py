"""Personal data masking (spec 02, "Escalation handoff", decision 3).

Applied FIRST, before normalisation. The masked text is used
everywhere: retrieval, the model call and the handoff record.

- Emails -> [EMAIL]
- Phone numbers -> [PHONE]

Phone numbers are recognised by shape, so the rule leans towards
masking: a run of digits (with optional leading +, spaces, hyphens,
dots or brackets between them) is a phone number when it holds 9 to 15
digits (15 is the international maximum). Shorter numbers (565 V,
2.2 kW, P-05, 1450 rpm) are never masked. Two exceptions keep
technical text intact: a date like 2026-10-11, and a run followed by a
unit (e.g. "400 415 440 V", which lists voltages).
"""

import re

from query.config import UNITS

EMAIL_MASK = "[EMAIL]"
PHONE_MASK = "[PHONE]"

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")

# A candidate: optional + or (, digits, single separators between digit
# groups (a bracket may sit next to a separator), not inside a word.
PHONE_CANDIDATE = re.compile(
    r"(?<![\w+.-])\+?\(?[0-9]+(?:(?:[ .-]|\)[ .-]?|[ .-]?\()[0-9]+)*(?![\w])"
)
MIN_PHONE_DIGITS = 9
MAX_PHONE_DIGITS = 15

DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{4}")

# Longest units first so "kHz" is not read as "k".
_UNIT_ALTERNATION = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
FOLLOWED_BY_UNIT = re.compile(rf"\s?(?:{_UNIT_ALTERNATION})(?![A-Za-z])")


def _mask_phone(match: re.Match) -> str:
    candidate = match.group(0)
    digits = sum(c.isdigit() for c in candidate)
    if not MIN_PHONE_DIGITS <= digits <= MAX_PHONE_DIGITS:
        return candidate
    if DATE_PATTERN.fullmatch(candidate):
        return candidate
    if FOLLOWED_BY_UNIT.match(match.string, match.end()):
        return candidate
    return PHONE_MASK


def mask_personal_data(text: str) -> str:
    """text with emails and phone numbers masked."""
    text = EMAIL_PATTERN.sub(EMAIL_MASK, text)
    return PHONE_CANDIDATE.sub(_mask_phone, text)
