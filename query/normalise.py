"""Fault-code normalisation (spec 02, Processing step 1, criterion 5).

The letter E or P (any case), an optional space or hyphen, then 1-3
digits becomes "E-" or "P-" plus the number zero-padded to 2 digits:
E1, e-1, E 01, E-001 -> E-01; P5 -> P-05.

A code only matches as a word of its own: a letter or digit directly
before the E/P, or directly after the digits, means it is part of a
longer word (IP20, type1, E1a) and is left unchanged. The same goes for
four or more digits.
"""

import re

CODE_PATTERN = re.compile(r"(?<![A-Za-z0-9])([EePp])[ -]?([0-9]{1,3})(?![A-Za-z0-9])")


def _replace(match: re.Match) -> str:
    return f"{match.group(1).upper()}-{int(match.group(2)):02d}"


def normalise_codes(text: str) -> str:
    """text with every fault (E) and parameter (P) code normalised."""
    return CODE_PATTERN.sub(_replace, text)
