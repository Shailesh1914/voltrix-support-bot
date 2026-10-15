"""Stage b: known and unknown fault codes (spec 02, step 4)."""

from ingestion import KBInfo
from query.fault_codes import fault_codes_in, known_fault_codes, unknown_fault_codes


def info(*titles):
    return KBInfo("v1", [(f"KB-{i:03d}", t) for i, t in enumerate(titles, 1)])


def test_known_codes_come_from_titles():
    known = known_fault_codes(info("E-01 Overcurrent", "E-16 Cooling fan failure", "Mounting the drive"))
    assert known == {"E-01", "E-16"}


def test_title_codes_are_normalised():
    assert known_fault_codes(info("E4 DC bus overvoltage", "e-007 Something")) == {"E-04", "E-07"}


def test_parameter_codes_are_not_fault_codes():
    assert known_fault_codes(info("Setting P-06 ramp time")) == frozenset()


def test_codes_in_question_in_order_without_repeats():
    assert fault_codes_in("E-12 then E-01, again E-12 and P-05") == ["E-12", "E-01"]


def test_codes_inside_words_are_ignored():
    assert fault_codes_in("XE-01 E-01x E-1234") == []


def test_unknown_codes():
    known = frozenset({"E-01", "E-02"})
    assert unknown_fault_codes("E-01 and E-33", known) == ["E-33"]
    assert unknown_fault_codes("E-01 and E-02", known) == []
    assert unknown_fault_codes("no code at all", known) == []
    assert unknown_fault_codes("E-100", known) == ["E-100"]
