"""Stage d: citation check, grounding check and safety warnings (spec 02,
step 4c, criterion 7, decisions 4, 5 and 9)."""

import pytest

from query.checks import (
    UNIT_ALIASES,
    codes_in,
    quantities_in,
    safety_warnings,
    uncited_retrieved,
    ungrounded,
    with_safety_warnings,
)
from query.config import UNITS

# --- Citation check -------------------------------------------------------------------


def test_cited_articles_all_retrieved(make_chunk):
    chunks = [make_chunk("KB-001"), make_chunk("KB-002")]
    assert uncited_retrieved(("KB-002", "KB-001"), chunks) == []


def test_article_not_retrieved_is_reported(make_chunk):
    chunks = [make_chunk("KB-001")]
    assert uncited_retrieved(("KB-001", "KB-036", "kb-001"), chunks) == ["KB-036", "kb-001"]


# --- Codes ----------------------------------------------------------------------------


def test_codes_are_normalised_before_comparing():
    assert codes_in("E1, e-02, P5 and P-006, IP20, VX-200") == {"E-01", "E-02", "P-05", "P-06"}


# --- Quantities -------------------------------------------------------------------------


def test_every_config_unit_is_recognised():
    assert set(UNITS) <= set(UNIT_ALIASES)
    for unit in UNITS:
        assert quantities_in(f"7 {unit}") == {("7", UNIT_ALIASES[unit])}, unit


@pytest.mark.parametrize(
    "text, expected",
    [
        ("380–480 V AC", {("380", "VAC"), ("480", "VAC")}),
        ("0.1–600.0 s", {("0.1", "s"), ("600", "s")}),
        ("−10 °C to +60 °C", {("-10", "°C"), ("60", "°C")}),
        ("−20 to −10 °C", {("-20", "°C"), ("-10", "°C")}),
        ("10-15 s", {("10", "s"), ("15", "s")}),
        ("2 to 50 Hz", {("2", "Hz"), ("50", "Hz")}),
        ("between DI3 and +24V", {("24", "V")}),
        ("1,500 rpm", {("1500", "rpm")}),
        ("3.0 s", {("3", "s")}),
        ("85°C and 85 ° C", {("85", "°C")}),
        ("10 kΩ and 10 kohm", {("10", "kΩ")}),
        ("4700 µF, 4700 μF, 4700 uF", {("4700", "µF")}),
        ("2.5 mm2 or 2.5 mm²", {("2.5", "mm²")}),
        ("565 V DC, 565 VDC, 565 Vdc", {("565", "VDC")}),
        ("wait 5 min, 5 minutes, 5 mins", {("5", "min")}),
        ("1 hour, 1 h", {("1", "h")}),
        ("3 sec, 3 seconds, 3 s", {("3", "s")}),
        ("1.5 Nm", {("1.5", "Nm")}),
    ],
)
def test_quantities(text, expected):
    assert quantities_in(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "R2A and R1C relay terminals",
        "E-01 A fault, VX-200 V",
        "step 3 then step 4",
        "P-06 is the ramp time",
        "11.5x",
        "5 sets of 3 mats",  # "s" and "m" must be whole words
        "5 Amps",
    ],
)
def test_not_quantities(text):
    assert quantities_in(text) == set()


# --- Grounding (criterion 7) ------------------------------------------------------------


CHUNK_TEXT = (
    "E-02 Overcurrent during deceleration — Fixes\n\n"
    "Lengthen the deceleration time in P-06 (range 0.1–600.0 s). "
    "With a 400 V supply the DC bus is at about 565 V DC. Wait 5 minutes."
)


@pytest.fixture
def chunks(make_chunk):
    return [make_chunk("KB-002", text=CHUNK_TEXT), make_chunk("KB-020", text="Ramp times — P-07 sets 10 s.")]


@pytest.mark.parametrize(
    "answer",
    [
        "Lengthen P-06. It accepts 0.1 s to 600 s.",
        "E2 is overcurrent; increase P6.",
        "Wait 5 min. The DC bus is about 565 V DC (565 V).",
        "Set P-07 to 10 seconds.",  # from the second chunk
        "A 400 V supply.",
        "No numbers at all.",
    ],
)
def test_grounded_answers(chunks, answer):
    assert ungrounded(answer, chunks) == []


@pytest.mark.parametrize(
    "answer, missing",
    [
        ("Check P-08.", ["P-08"]),
        ("E-05 can also appear.", ["E-05"]),
        ("Set P-06 to 30 s.", ["30 s"]),
        ("Wait 10 minutes.", ["10 min"]),
        ("About 565 V AC.", ["565 VAC"]),  # AC is not DC
        ("565 mV.", []),  # not a listed unit: not checked by criterion 7
        ("Use 4 mm cable and P-09.", ["P-09", "4 mm"]),
    ],
)
def test_ungrounded_answers(chunks, answer, missing):
    assert ungrounded(answer, chunks) == missing


def test_grounding_uses_all_retrieved_chunks_not_only_cited(chunks):
    # Criterion 7 says "in the retrieved chunks".
    assert ungrounded("P-07: 10 s", chunks[:1]) == ["P-07", "10 s"]
    assert ungrounded("P-07: 10 s", chunks) == []


# --- Safety warnings (decision 5) -------------------------------------------------------


WARNING_TEXT = (
    "Safe isolation — Steps\n\n"
    "WARNING: The DC bus stays charged for 5 minutes after switch-off.\n"
    "1. Switch off.\n"
    "  DANGER: Never open the cover while the supply is on.\n"
    "> CAUTION: Hot surface.\n"
    "**WARNING:** Wear gloves.\n"
    "Warning: lower case is not a marker.\n"
    "Read the WARNING label.\n"
)


def test_warning_lines_found_case_sensitive(make_chunk):
    assert safety_warnings(["KB-034"], [make_chunk("KB-034", text=WARNING_TEXT)]) == [
        "WARNING: The DC bus stays charged for 5 minutes after switch-off.",
        "DANGER: Never open the cover while the supply is on.",
        "> CAUTION: Hot surface.",
        "**WARNING:** Wear gloves.",
    ]


def test_only_used_articles_and_every_chunk_of_them(make_chunk):
    chunks = [
        make_chunk("KB-034", n=1, text="WARNING: first chunk."),
        make_chunk("KB-001", n=1, text="WARNING: not used."),
        make_chunk("KB-034", n=2, text="CAUTION: second chunk."),
        make_chunk("KB-034", n=3, text="WARNING: first chunk."),  # repeat
    ]
    assert safety_warnings(["KB-034"], chunks) == ["WARNING: first chunk.", "CAUTION: second chunk."]


def test_missing_warnings_appended_word_for_word():
    warnings = ["WARNING: A.", "CAUTION: B."]
    assert with_safety_warnings("Do X.\n", warnings) == "Do X.\n\nWARNING: A.\nCAUTION: B."


def test_warning_already_in_answer_not_repeated():
    answer = "WARNING: A.\n\n1. Do X."
    assert with_safety_warnings(answer, ["WARNING: A.", "CAUTION: B."]) == answer + "\n\nCAUTION: B."
    assert with_safety_warnings(answer, ["WARNING: A."]) == answer


def test_paraphrased_warning_still_appended():
    assert with_safety_warnings("Warning: a", ["WARNING: A."]) == "Warning: a\n\nWARNING: A."
