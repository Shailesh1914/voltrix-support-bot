# Step 8 Traceability — Query Side

Date: 2026-10-14
State: after stage e (spec 02 v1.6).
Query suite: 368 tests passing. Full structural suite: 568 tests (~4.7 min).
Model never called in tests (botocore Stubber + network guard).
Live model test: pending (Bedrock unavailable on AWS account).

## Spec 02 structural acceptance criteria

| # | Criterion | Covering tests |
|---|---|---|
| 1-2 | Evaluation gates (85% answered, 95% escalated) | Not structural. Session E (eval runner), Step 9 |
| 3 | Every escalation has a complete handoff | test_every_route (all 4 reasons), test_routes_cover_every_escalation_reason, test_field_lists_match_spec_02, test_record_is_complete, test_missing_field_is_detected, test_missing_chunk_field_is_detected, test_jsonl_store_appends_one_line_per_record, test_jsonl_store_end_to_end, test_unknown_code_escalates_with_real_chunks, test_bad_answers_over_real_chunks_escalate |
| 4 | Never cites an article it did not retrieve | test_criterion_4_citation_of_unretrieved_article_escalates, test_cited_articles_all_retrieved, test_article_not_retrieved_is_reported, test_every_route (answered and not_retrieved routes), test_bad_answers_over_real_chunks_escalate[not_retrieved] |
| 5 | Fault-code normalisation | test_criterion_5_fault_code_forms_become_E_01, test_criterion_5_parameter_code_becomes_P_05, test_criterion_5_ordinary_words_unchanged, test_codes_inside_a_sentence, test_punctuation_around_codes, test_normalisation_is_idempotent, test_three_digit_number_keeps_all_digits |
| 6 | Valid status; escalation has reason, handoff_id and fixed message | test_every_route (assert_complete_escalation / assert_answered), test_answered_with_citations_in_model_order, test_each_escalation_gets_its_own_handoff, test_failed_handoff_write_raises_and_gives_no_reference |
| 7 | Every code and number-with-unit in the answer is in the chunks of the CITED articles | test_criterion_7_ungrounded_answer_escalates_and_is_never_edited, test_criterion_7_value_from_retrieved_but_uncited_article_escalates, test_grounding_uses_only_chunks_of_cited_articles, test_grounding_uses_every_chunk_of_a_cited_article, test_grounded_answers, test_ungrounded_answers, test_quantities, test_not_quantities, test_codes_are_normalised_before_comparing, test_every_route, test_bad_answers_over_real_chunks_escalate[invented_values] |
| 8 | Unknown code escalates with no model call; handoff has chunks | test_criterion_8_unknown_code_escalates_without_model_call, test_unknown_code_wins_over_low_similarity, test_unknown_code_escalates_with_real_chunks, test_E_17_is_unknown_in_v1_but_known_in_v2, test_known_codes_v1, test_known_codes_v2_adds_E_17, test_every_route[unknown_code] |
| 9 | Threshold in config equals spec | test_criterion_9_threshold_in_config_equals_spec, test_threshold_is_assigned_only_in_config |

## Spec 02 implementation decisions

| # | Decision | Covering tests |
|---|---|---|
| 1 | Threshold is a constant in config; spec has a Value: line | test_criterion_9_threshold_in_config_equals_spec, test_threshold_is_assigned_only_in_config, test_spec_values_in_env_fail_loudly, test_unset_threshold_fails_loudly, test_default_is_the_config_constant, test_threshold_none_fails_at_startup, test_invalid_threshold_fails |
| 2 | Model ID is a constant in config, checked against spec | test_model_id_in_config_equals_spec, test_model_id_comes_from_config, test_request_shape, test_spec_values_in_env_fail_loudly |
| 3 | Masking first; masked text used everywhere | test_masking_first_keeps_codes_for_normalisation, test_search_gets_masked_normalised_question_and_k_5, test_model_escalation_decision, test_handoff_stores_only_masked_questions, plus email, phone and technical-text masking tests |
| 4 | Grounding failure escalates; answer never edited | test_criterion_7_ungrounded_answer_escalates_and_is_never_edited, test_every_route[ungrounded] |
| 5 | Warning lines from used articles added at the START; prompt asks for precautions first | warning-marker tests in test_query_checks.py (renamed ..._added_at_start_... / ..._still_added), test_decision_5_* flow tests, test_system_prompt_states_the_spec_rules |
| 6 | Malformed output -> insufficient_context; API error -> service_error | test_malformed_output (10 Bedrock cases), test_malformed_output_is_rejected (17 cases), test_malformed_output_escalates_insufficient_context, test_client_errors_are_service_errors (9 codes), test_connection_and_credential_errors_are_service_errors, test_service_error_escalates_with_handoff, test_other_generator_errors_are_not_hidden, test_every_route[service_error / malformed] |
| 7 | Answer with empty used_article_ids escalates | test_decision_7_answer_without_citations_escalates, test_every_route[no_citations], test_bad_answers_over_real_chunks_escalate[no_citation] |
| 8 | Handoff path, uuid4, created_at in UTC | test_handoff_id_is_unique_uuid4, test_created_at_is_utc_iso, test_naive_time_is_rejected, test_handoff_records_kb_version_and_time, test_settings_from_environ_only, test_handoff_path_relative_to_repo_root, test_absolute_handoff_path_kept |
| 9 | Units list, tolerant of spacing and aliases | test_every_config_unit_is_recognised, test_quantities (18 spellings and ranges) |
| 10 | System prompt is product behaviour | test_system_prompt_states_the_spec_rules, plus decision 12 fingerprint (gap closed) |
| 11 | Handoff stores rejected_answer and failed_check when a check stops an answer | test_every_route, test_rejected_answer_and_failed_check_default_empty, test_rejected_answer_stored_with_its_check, test_invalid_rejected_answer_and_failed_check, test_field_lists_match_spec_02, flow tests for criteria 4 and 7 and decision 7 |
| 12 | System prompt SHA-256 fingerprint | test_decision_12_system_prompt_fingerprint |

## Command line

| Behaviour | Covering tests |
|---|---|
| python -m query.ask fails loudly (exit code 2) while threshold unset; config/index/profile errors exit 2 with one line; empty question rejected | test_query_cli.py (9 tests) |

## Mutation checks performed (tests proven able to fail)

- Stage a: 4 deliberate breaks, all caught.
- Stage b: 8 deliberate breaks, all caught. One weak test found and
  fixed (completeness check read its field list from the code's own
  constant; now uses spec 02's list independently).
- Stage c: 9 deliberate breaks, all caught.
- Stage d: 12 deliberate breaks, all caught.
- Stage e: 12 deliberate breaks, all caught. Mutation 4b (a prompt
  wording change in a line no rule test checks) was caught ONLY by
  the decision 12 fingerprint test, so the decision 10 gap is closed.

## Lesson recorded

The Session Q conversation that built stages a-d was lost. A new
session rebuilt full context from specs/, CLAUDE.md, the code,
tests and Git history, and completed stage e correctly. Only the
stage e mutation record (which lived only in the old conversation)
had to be redone.