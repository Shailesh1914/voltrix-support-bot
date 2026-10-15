"""Unknown fault codes (spec 02, Processing step 4, criterion 8).

The known codes are the E-xx codes in the article titles returned by
kb_info(). Titles are normalised the same way as questions, so both
sides compare in the "E-01" form.
"""

import re

from ingestion import KBInfo
from query.normalise import normalise_codes

# A normalised fault code (2 or 3 digits) as a word of its own.
FAULT_CODE_PATTERN = re.compile(r"(?<![A-Za-z0-9])E-[0-9]{2,3}(?![A-Za-z0-9])")


def fault_codes_in(text: str) -> list[str]:
    """Distinct fault codes in already-normalised text, in order of appearance."""
    return list(dict.fromkeys(FAULT_CODE_PATTERN.findall(text)))


def known_fault_codes(info: KBInfo) -> frozenset[str]:
    return frozenset(
        code for _, title in info.articles for code in fault_codes_in(normalise_codes(title))
    )


def unknown_fault_codes(normalised_question: str, known: frozenset[str]) -> list[str]:
    """Codes in the question that no article title names."""
    return [code for code in fault_codes_in(normalised_question) if code not in known]
