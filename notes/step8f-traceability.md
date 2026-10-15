# Step 8f Traceability — Anthropic API generator (spec 02 v1.7-v1.10)

Date: 2026-10-15
Full structural suite: 659+ tests passing (ingestion and query).
Query suite also passes in a hostile shell (all refused ANTHROPIC_*
variables set). Model never called in tests (MockTransport,
no_network fixture).

| Spec 02 requirement | Code | Covering tests |
|---|---|---|
| Model ID claude-haiku-4-5-20251001 (step 7, decision 2) | config.MODEL_ID | test_model_id_in_config_equals_spec, test_model_id_pattern (3), test_model_id_comes_from_config |
| Temperature 0 (step 7) | anthropic_api.request(): extra_body (SDK 1.x removed the argument) | test_request_shape, test_one_call_with_exact_request_on_the_wire, test_one_call_to_the_generator_with_real_shaped_chunks |
| One call, submit_response forced, max tokens 2048 | AnthropicGenerator.request() | test_request_shape, test_one_call_with_exact_request_on_the_wire |
| Retries and timeouts explicit, never SDK defaults | MAX_RETRIES=2, TIMEOUT(60, connect=10), make_client() | test_retries_timeout_and_address_are_explicit, test_every_connection_setting_is_passed_explicitly, test_explicit_values_differ_from_sdk_defaults, test_timeout_reaches_every_request, test_rate_limit_is_retried_then_succeeds, test_retryable_errors_stop_after_three_attempts (5), test_client_errors_are_not_retried (5) |
| API address fixed to https://api.anthropic.com (v1.9) | API_BASE_URL, make_client() | test_retries_timeout_and_address_are_explicit, test_every_connection_setting_is_passed_explicitly, test_from_environment_builds_the_configured_client, test_one_call_with_exact_request_on_the_wire |
| Refuse to start on ANTHROPIC_API_KEY / _AUTH_TOKEN / _BASE_URL / _CUSTOM_HEADERS / _LOG (v1.10) | check_environment(), REFUSED_ENV_NAMES | test_refuses_to_start_if_an_sdk_variable_is_set (10, cases from SPEC_REFUSED_NAMES), test_refused_names_are_the_five_in_spec_02 |
| Key from VOLTRIX_ANTHROPIC_API_KEY, else ~/.config/voltrix/secrets.env; never a project file | load_api_key() | test_key_from_environment_first, test_key_from_secrets_file_when_not_in_environment, test_only_the_voltrix_name_is_read_from_the_file, test_missing_key_fails_loudly, test_default_secrets_path_is_outside_the_project, test_files_inside_the_project_are_never_read (3), test_symlink_into_the_project_is_refused |
| Key never logged, printed or in errors | error mapping (class + status only) | test_key_never_in_logs_errors_or_output, test_key_never_printed_or_logged (smoke), test_module_never_names_the_sdk_default_key_variable_as_a_source |
| Model API errors -> service_error (decision 6) | generate_with_usage(): AnthropicError -> GeneratorServiceError | test_status_errors_are_service_errors (8), test_connection_errors_are_service_errors (2), test_any_sdk_error_is_a_service_error (3), test_service_error_escalates_through_the_flow, test_errors_are_logged_without_question_text |
| Malformed output -> insufficient_context (decision 6) | parse_message() + validate_output() | test_malformed_output (9) |
| Structural tests make no model calls (step 7) | MockTransport, no_network fixture | every test in test_query_anthropic.py and test_query_smoke.py; suite passes with hostile ANTHROPIC_* shell variables |
| AWS_PROFILE / AWS_REGION optional; required only for Bedrock (Configuration) | load_settings(), BedrockGenerator.from_settings() | test_aws_settings_are_optional (2), test_settings_with_no_aws_values_at_all, test_aws_settings_required_only_when_bedrock_is_selected (2), test_build_flow_wires_config_settings_index_and_anthropic |
| Bedrock generator kept but unused (step 7) | bedrock.py, not imported by ask.py | test_cli_never_imports_bedrock, test_query_bedrock.py |
| Answer-path order d, c, e, then f (step 5, v1.7) | flow.py failed_check chain | test_first_failing_check_in_spec_order_decides (3), test_safety_warnings_only_after_every_check_passed |
| Handoff fields incl. created_at, rejected_answer, failed_check (v1.7) | handoff.py (unchanged) | test_field_lists_match_spec_02 (already matched v1.7) |
| Masking is Processing step 1; renumbered steps (v1.7) | docstrings and comments only | n/a (no test parses step numbers) |
| CLI: key checked before the index; startup errors exit 2 | ask.build_flow(), ask.main() | test_api_key_checked_before_index_is_opened, test_startup_errors_exit_2_with_message (3), test_threshold_checked_before_anything_is_loaded |
| Smoke test: one fixed question, v1 chunks, generator only | query/smoke.py | test_query_smoke.py (10 tests) |

## Mutation checks performed (tests proven able to fail)

- Breaks 1-25: all caught; files restored byte for byte.
  Breaks 4 and 5 (max_retries and base_url arguments dropped) were
  invisible to value checks because they equal SDK defaults;
  test_every_connection_setting_is_passed_explicitly was added to
  catch them. Breaks 22-25 were also caught by the new tests alone.
  One test made shell-independent: the log-text check now reads
  only query.anthropic_api records.
- Break 26: ANTHROPIC_LOG not refused, caught by 3 tests. A weak
  test was found and fixed: the refusal test read its cases from
  the code's own REFUSED_ENV_NAMES, and now uses SPEC_REFUSED_NAMES
  written from spec 02 (same weakness as Step 8b).

## Lesson recorded

A test must take its expected values from the spec, never from the
code it tests (found twice: Step 8b handoff fields, Step 8f refused
names). Settings equal to library defaults must still be passed
explicitly and tested as such (embedding model, botocore retries,
anthropic retries and base_url).