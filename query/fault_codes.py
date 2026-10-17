"""Unknown fault codes (spec 02, Processing step 4, criterion 8).

The known codes are the E-xx codes in the article titles returned by
kb_info(). Titles are normalised the same way as questions, so both
sides compare in the "E-01" form.
"""

import re

from ingestion import KBInfo
from query.config import ConfigError
from query.normalise import normalise_codes

# A normalised fault code (2 or 3 digits) as a word of its own.
FAULT_CODE_PATTERN = re.compile(r"(?<![A-Za-z0-9])E-[0-9]{2,3}(?![A-Za-z0-9])")


def fault_codes_in(text: str) -> list[str]:
    """Distinct fault codes in already-normalised text, in order of appearance."""
    return list(dict.fromkeys(FAULT_CODE_PATTERN.findall(text)))


class DuplicateFaultCode(ConfigError):
    """Two article titles name the same fault code (fail loudly at startup)."""


def code_titles(info: KBInfo) -> dict[str, str]:
    """Each known fault code -> the title, exactly as kb_info() gives it,
    of the article that names it. Used by the code boost (spec 02,
    step 3b) and for the set of known codes (step 4)."""
    found: dict[str, tuple[str, str]] = {}
    for article_id, title in info.articles:
        for code in fault_codes_in(normalise_codes(title)):
            if code in found:
                raise DuplicateFaultCode(
                    f"{code} is named by the titles of both {found[code][0]} and {article_id}"
                )
            found[code] = (article_id, title)
    return {code: title for code, (_, title) in found.items()}


def known_fault_codes(info: KBInfo) -> frozenset[str]:
    return frozenset(code_titles(info))


def unknown_fault_codes(normalised_question: str, known: frozenset[str]) -> list[str]:
    """Codes in the question that no article title names."""
    return [code for code in fault_codes_in(normalised_question) if code not in known]
