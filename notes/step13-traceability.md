# Step 13.3 – Web interface traceability (spec 08 v1.1)

Built by Session Q on branch `web-interface`, 2026-11-11/12.

## Test results

| Folder | Passed | Failed | Skipped |
|---|---|---|---|
| tests/structural/web | 182 | 0 | 0 |
| tests/structural/query | 571 (8 new) | 0 | 0 |
| tests/structural/ingestion | 232 | 0 | 0 |
| tests/structural/evals | 378 | 0 | 0 |

Real-app check: `python -m web` started with the real index and a fake secrets file. `/health` returned v2, the page loaded, a wrong code got 401, a blank question got "question is empty". One log line per request. No Claude call made.

## Requirement -> test

| Spec 08 requirement | Test |
|---|---|
| 4.1 /health works without a code, 200 | test_health_without_code_is_200, test_health_ignores_the_code |
| 4.1 never calls Claude or retrieval | test_health_never_calls_claude_or_retrieval |
| 4.1 fields and values | test_health_fields, test_health_kb_version_is_the_pointer_file |
| 4.1 image_tag from IMAGE_TAG, else "local" | test_image_tag |
| 4.1 no secret in /health | test_health_contains_no_secret |
| 4.2 missing or wrong code -> 401, zero Claude calls, zero retrieval | test_missing_code_401, test_wrong_code_401 (7 variants) |
| 4.2 code checked before the body is read | test_bad_code_with_bad_body_gives_401, test_code_checked_before_body_is_read |
| 4.2 constant-time compare | test_code_compared_in_constant_time |
| 4.2 each 400 case with its exact text | test_400_cases_with_exact_text (19 bodies), test_spec_lists_these_400_cases |
| 4.2 1000-character limit, counted as sent | test_question_over_the_limit_is_400, test_question_at_the_limit_is_accepted, test_limit_counted_as_sent_before_trimming, test_limit_counts_characters_not_bytes |
| 4.2 extra fields ignored | test_extra_fields_are_ignored |
| 4.2 flow's result returned unchanged, spec 02 field names | test_answer_returns_the_flow_result_unchanged, test_escalation_returns_the_flow_result_unchanged, test_question_reaches_the_flow_unchanged, test_low_similarity_escalates_without_claude |
| 4.2 service error -> 200 escalation with handoff id | test_service_error_is_a_200_escalation (529, 500, 429, connection), test_client_error_is_a_200_escalation_without_retry |
| 4.2 unexpected error -> 500, no stack trace | test_unexpected_error_is_500_without_details |
| 4.2 X-Request-Id uuid4 on every /ask | test_every_ask_response_has_a_request_id, test_request_ids_differ |
| 4.2 no new prompt text, checks or threshold | test_web_isolation.py (5 static checks) |
| 4.3 page elements and demo note | test_page_has_code_field_question_box_button_and_result_area, test_page_shows_the_demo_note |
| 4.3 nothing loaded from elsewhere | test_page_loads_nothing_from_elsewhere, test_browser_is_told_to_load_nothing_from_elsewhere |
| 4.3 code kept only in page memory | test_page_does_not_store_the_code, test_code_field_is_not_remembered |
| 4.4 one line: id, decision (-), latency, status | test_one_request_line_per_ask, test_written_lines_per_ask |
| 4.4 uvicorn access log off | test_uvicorn_access_log_off_and_port_8080, test_log_levels_keep_library_info_lines_out |
| 4.4 Anthropic warning allowed in addition | test_only_the_allowed_anthropic_warning_is_added |
| 4.4 / 4.6 no question, answer or secret in any log or response | test_no_question_answer_or_secret_in_any_response_or_log (6 cases), test_no_secret_in_any_endpoint_response |
| 4.5 HANDOFF_DIR, and both set stops the start-up | test_handoffs_go_to_handoff_dir, test_handoff_dir_and_path_together_stop_the_start_up, plus 6 query tests |
| 5 VOLTRIX_SECRETS_SOURCE: file, parameter_store, anything else stops | test_file_mode_reads_both_from_the_secrets_file, test_any_other_source_stops_the_start_up |
| 5 Parameter Store read once at start-up, with decryption | test_parameter_store_reads_both_once_with_decryption, test_parameter_store_app_reads_secrets_once_and_serves |
| 5 key or code also in the environment stops the start-up | test_parameter_store_refuses_secrets_in_the_environment |
| 5 any ANTHROPIC_ variable refused, both modes | test_anthropic_variables_refused_in_both_modes (12 cases), test_anthropic_variable_stops_the_start_up |
| 5 code at least 12 characters | test_code_length_file_mode, test_code_length_parameter_store_mode |
| 5 start-up errors name the setting, never the value | assert_names_setting_not_value in the secrets tests, test_start_up_error_never_shows_a_secret, test_python_m_web_start_up_error_is_one_line |
| 4.6 expected values come from the spec | web_testkit.parse_spec_08 reads them from spec 08; test_values_read_from_spec_08 guards the parser |

## Mutation check

| # | Mutation | Failed tests | Caught |
|---|---|---|---|
| 1 | Remove the access code check in /ask | 17 | yes |
| 2 | Check the access code after the body is read | 5 | yes |
| 3 | Limit 1000 -> 1001 | 2 | yes |
| 4 | hmac.compare_digest -> == | 1 | yes |
| 5 | Log the question text in the request log line | 10 | yes |
| 6 | Read the parameters on every request | 1 | yes |

Mutations 4 and 6 are caught by one test each. Accepted: constant time can only be checked by seeing compare_digest is called; the mutation 6 test also counts Parameter Store calls after a 401. All mutations undone (checksums for web/, git diff --stat for query/).

## Decisions on Session Q's notes

- Accepted as built: library logging set to WARNING (the Anthropic SDK logs the question at DEBUG); empty VOLTRIX_SECRETS_SOURCE stops start-up; ANTHROPIC_ prefix refusal for the web app only; /health reads kb_version once at start-up; other start-up failures may print a stack trace (no secret).
- File mode reads environment first, then the secrets file (same as the command-line bot).
- opentelemetry-api is a required dependency of fastapi 0.162.4; only the interface is installed, FastAPI telemetry is switched off, and a test checks it. Pinned in requirements.txt.

## Notes for Session D

- Run the app with `python -m web`, not the uvicorn command.
- Mount the secrets file at `~/.config/voltrix/secrets.env` of the user the container runs as.
- Model loading prints a progress bar to the log at start-up.

## Open items for spec 08 v1.2

- 500 log line: add the error class name (not the message).
- A question of only spaces and over 1000 characters gives "question is empty" (table order wins).
- Record the extras: Content-Security-Policy header, /docs /redoc /openapi.json off, FastAPI telemetry off, question box limited to 1000 characters.
