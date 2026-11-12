"""The values the web tests read from spec 08 (guards the parser)."""


def test_values_read_from_spec_08(spec_08):
    assert "Status: Version 1.1" in spec_08.text
    assert spec_08.bad_request_texts == {
        "Body is not valid JSON, or not a JSON object": "invalid request body",
        "`question` missing": "question is required",
        "`question` is not a string": "question must be text",
        "`question` empty after trimming spaces": "question is empty",
        "`question` longer than 1000 characters (counted as sent, before trimming)": "question is longer than 1000 characters",
    }
    assert spec_08.max_question_chars == 1000
    assert spec_08.success_fields == ("status", "answer", "citations", "escalation_reason", "handoff_id")
    assert spec_08.access_denied == "access denied"
    assert spec_08.internal_error == "internal error"
    assert spec_08.min_code_length == 12
    assert spec_08.key_parameter == "/voltrix/anthropic-key"
    assert spec_08.code_parameter == "/voltrix/access-code"
