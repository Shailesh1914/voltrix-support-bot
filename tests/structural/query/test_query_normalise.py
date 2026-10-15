"""Stage a: fault-code normalisation (spec 02, step 2, criterion 5)."""

import pytest

from query.normalise import normalise_codes


@pytest.mark.parametrize("code", ["E1", "e1", "E01", "E-1", "e-01", "E 01", "E-001", "e 1", "E001"])
def test_criterion_5_fault_code_forms_become_E_01(code):
    assert normalise_codes(code) == "E-01"


@pytest.mark.parametrize("code", ["P5", "p5", "P-5", "P 05", "P-005"])
def test_criterion_5_parameter_code_becomes_P_05(code):
    assert normalise_codes(code) == "P-05"


@pytest.mark.parametrize(
    "text",
    [
        "the drive trips when the motor starts",
        "Earth fault Power supply Enter Press",
        "set the ramp to 3 sec",
        "IP20 enclosure",
        "type1 cable",
        "VX-200 drive",
        "E1a",
        "E-0001",
        "e.g. the fan",
        "565 V DC",
        "",
    ],
)
def test_criterion_5_ordinary_words_unchanged(text):
    assert normalise_codes(text) == text


def test_codes_inside_a_sentence():
    original = "vx200 trips, e1 flashing, then P 6 set to 3 s and E-012 once"
    assert normalise_codes(original) == "vx200 trips, E-01 flashing, then P-06 set to 3 s and E-12 once"


def test_three_digit_number_keeps_all_digits():
    assert normalise_codes("E100") == "E-100"
    assert normalise_codes("P-123") == "P-123"


def test_punctuation_around_codes():
    assert normalise_codes("(E1), E2. E3? P-5/P-6 'e7'") == "(E-01), E-02. E-03? P-05/P-06 'E-07'"


def test_normalisation_is_idempotent():
    text = "E1 then P5 then E-001 and P 12"
    once = normalise_codes(text)
    assert normalise_codes(once) == once


def test_masks_are_unchanged():
    assert normalise_codes("call [PHONE] or [EMAIL] about E1") == "call [PHONE] or [EMAIL] about E-01"
