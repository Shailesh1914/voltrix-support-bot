"""Stage a: personal data masking (spec 02, "Escalation handoff",
decision 3). All addresses and numbers below are invented test
patterns, not real people's data."""

import pytest

from query.masking import mask_personal_data
from query.normalise import normalise_codes


@pytest.mark.parametrize(
    "email",
    [
        "tech@example.com",
        "first.last+vfd@plant-3.example.co.uk",
        "A_B%C@sub.domain.example.org",
    ],
)
def test_emails_are_masked(email):
    assert mask_personal_data(f"mail me at {email} please") == "mail me at [EMAIL] please"


@pytest.mark.parametrize(
    "phone",
    [
        "+44 20 7946 0958",
        "+91 98765 43210",
        "+1 (555) 010-0199",
        "(555) 010-0199",
        "555-010-0199",
        "555.010.0199",
        "9876543210",
        "020 7946 0958",
        "+919876543210",
    ],
)
def test_phone_numbers_are_masked(phone):
    assert mask_personal_data(f"call {phone} if needed") == "call [PHONE] if needed"


@pytest.mark.parametrize(
    "text",
    [
        "DC bus is at about 565 V DC",
        "wait 5 min after switching off",
        "set P-06 to 3.5 s",
        "E-001 at 1450 rpm",
        "2.2 kW motor on a 400 V supply",
        "heatsink at 85 °C, 20 % load",
        "tried 400 415 440 V supplies",
        "since 2026-10-11 it trips",
        "since 11/10/2026 it trips",
        "VX-200 serial 12345678",
        "capacitor 4700 µF, 10 kΩ resistor",
        "",
    ],
)
def test_technical_text_is_not_masked(text):
    assert mask_personal_data(text) == text


def test_both_kinds_in_one_question():
    text = "E1 on drive 3. Reach me on tech@example.com or +44 20 7946 0958."
    assert mask_personal_data(text) == "E1 on drive 3. Reach me on [EMAIL] or [PHONE]."


def test_masking_first_keeps_codes_for_normalisation():
    # Decision 3: masking runs first, then normalisation.
    text = "e1 again, call 020 7946 0958"
    assert normalise_codes(mask_personal_data(text)) == "E-01 again, call [PHONE]"


def test_no_digits_of_a_phone_survive():
    masked = mask_personal_data("ring +91 98765 43210 now")
    assert not any(c.isdigit() for c in masked)
