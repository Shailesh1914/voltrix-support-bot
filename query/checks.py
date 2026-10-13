"""Checks on the model's answer (spec 02, step 4c, criterion 7,
decisions 4, 5 and 7).

- Citation check: every used_article_id is among the retrieved chunks.
- Grounding check: every E-xx code, P-xx code and number with a unit in
  the answer appears in the retrieved chunks. Never edits the answer.
- Safety warnings: WARNING / DANGER / CAUTION lines in the retrieved
  chunks of used articles, appended word for word if the answer lacks
  them.
"""

import re
from decimal import Decimal

from ingestion import Chunk
from query.normalise import normalise_codes

# --- Citation check (step 4c) -----------------------------------------------------


def uncited_retrieved(used_article_ids, chunks: list[Chunk]) -> list[str]:
    """used_article_ids that are NOT among the retrieved chunks."""
    retrieved = {c.article_id for c in chunks}
    return [a for a in used_article_ids if a not in retrieved]


# --- Grounding check (criterion 7, decision 4) ---------------------------------------

CODE_PATTERN = re.compile(r"(?<![A-Za-z0-9])[EP]-[0-9]{2,3}(?![A-Za-z0-9])")

# Spelling -> canonical unit. Every unit in config.UNITS appears here,
# plus the aliases of decision 9 ("tolerant of spacing and aliases").
UNIT_ALIASES = {
    "V": "V", "kV": "kV", "A": "A", "mA": "mA", "Hz": "Hz", "kHz": "kHz",
    "W": "W", "kW": "kW", "hp": "hp", "ms": "ms",
    "s": "s", "sec": "s", "secs": "s", "second": "s", "seconds": "s",
    "min": "min", "mins": "min", "minute": "min", "minutes": "min",
    "h": "h", "hr": "h", "hrs": "h", "hour": "h", "hours": "h",
    "°C": "°C", "° C": "°C",
    "%": "%",
    "mm": "mm", "mm²": "mm²", "mm2": "mm²", "sq mm": "mm²",
    "m": "m", "Nm": "Nm", "N m": "Nm", "N·m": "Nm", "rpm": "rpm",
    "Ω": "Ω", "ohm": "Ω", "ohms": "Ω", "kΩ": "kΩ", "kohm": "kΩ", "kohms": "kΩ",
    "µF": "µF", "μF": "µF", "uF": "µF",
    "VAC": "VAC", "V AC": "VAC", "Vac": "VAC", "V ac": "VAC",
    "VDC": "VDC", "V DC": "VDC", "Vdc": "VDC", "V dc": "VDC",
}
# A plain voltage in an answer is supported by the same voltage with AC
# or DC in a chunk (less specific, not different). The reverse is not.
UNIT_ALSO_MATCHES = {"V": {"VAC", "VDC"}}

_UNIT_RE = "|".join(re.escape(u) for u in sorted(UNIT_ALIASES, key=len, reverse=True))
_NUMBER_RE = r"[+\-−]?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?"
_RANGE_SEP_RE = r"\s*(?:–|-|to)\s*"

# One or more numbers (a range shares its unit: "380–480 V AC"), then the
# unit. A number glued to letters, a dot or a code hyphen is not one
# ("R2A", "E-01", "VX-200", "1.5" inside "11.5").
QUANTITY_PATTERN = re.compile(
    rf"(?<![A-Za-z0-9_.,])(?<![A-Za-z]-)(?P<numbers>{_NUMBER_RE}(?:{_RANGE_SEP_RE}{_NUMBER_RE})*)"
    rf"\s?(?P<unit>{_UNIT_RE})(?![A-Za-z0-9µμΩ°²])"
)
# Each number of a range, left to right: the separator is consumed first,
# so in "10-15 s" the hyphen is never read as a minus sign.
_RANGE_NUMBER_PATTERN = re.compile(rf"(?:^|{_RANGE_SEP_RE})({_NUMBER_RE})")


def _canonical_number(text: str) -> str:
    negative = text[0] in "-−"
    value = Decimal(text.lstrip("+-−").replace(",", "")).normalize()
    return f"-{value:f}" if negative and value else f"{value:f}"


def quantities_in(text: str) -> set[tuple[str, str]]:
    """(number, canonical unit) pairs, e.g. "380–480 V AC" ->
    {("380", "VAC"), ("480", "VAC")}."""
    found = set()
    for match in QUANTITY_PATTERN.finditer(text):
        unit = UNIT_ALIASES[match.group("unit")]
        for number in _RANGE_NUMBER_PATTERN.findall(match.group("numbers")):
            found.add((_canonical_number(number), unit))
    return found


def codes_in(text: str) -> set[str]:
    return set(CODE_PATTERN.findall(normalise_codes(text)))


def ungrounded(answer: str, chunks: list[Chunk]) -> list[str]:
    """Codes and quantities in the answer that no retrieved chunk has.

    Empty list = criterion 7 holds.
    """
    chunk_text = "\n".join(c.text for c in chunks)
    chunk_codes = codes_in(chunk_text)
    chunk_quantities = quantities_in(chunk_text)

    missing = sorted(codes_in(answer) - chunk_codes)
    for number, unit in sorted(quantities_in(answer)):
        units = {unit} | UNIT_ALSO_MATCHES.get(unit, set())
        if not any((number, u) in chunk_quantities for u in units):
            missing.append(f"{number} {unit}")
    return missing


# --- Safety warnings (decision 5) -------------------------------------------------

# Case-sensitive marker at the start of a line. Leading Markdown quote,
# list or emphasis marks are skipped ("> WARNING", "**WARNING:**").
SAFETY_LINE_PATTERN = re.compile(r"^[ \t>*_\-]*(?:WARNING|DANGER|CAUTION)\b")


def safety_warnings(used_article_ids, chunks: list[Chunk]) -> list[str]:
    """Warning lines in every retrieved chunk of a used article, in
    retrieval order, without repeats."""
    used = set(used_article_ids)
    lines = [
        line.strip()
        for c in chunks
        if c.article_id in used
        for line in c.text.splitlines()
        if SAFETY_LINE_PATTERN.match(line)
    ]
    return list(dict.fromkeys(lines))


def with_safety_warnings(answer: str, warnings: list[str]) -> str:
    """answer, plus each warning it does not already contain word for word."""
    missing = [w for w in warnings if w not in answer]
    if not missing:
        return answer
    return answer.rstrip() + "\n\n" + "\n".join(missing)
