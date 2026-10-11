# Step 7 Traceability — Ingestion Side

Date: 2026-10-11
Full ingestion suite: 200 tests passing (about 3.5 minutes).
Test files: tests/structural/ingestion/test_ingestion_<name>.py

## Indexes built

| Index | Articles | Chunks | index_sha256 | metadata_sha256 |
|---|---|---|---|---|
| indexes/v1/ | 36 | 172 | e34dea78...e42a89 | 16d3d32b...a140ac |
| indexes/v2/ | 39 | 187 | ed34b757...3aa0b2 | 455f8c17...770f5f51 |

## Spec 01 acceptance criteria

| # | Criterion | Covering tests |
|---|---|---|
| 1 | Every article gives at least one chunk | build: test_criterion_1_every_article_represented (v1, v2); chunking: test_real_kb_chunks; test_article_with_no_text_fails_loudly |
| 2 | Within 512 and 300 tokens | build: test_criterion_2_token_limits; chunking: test_long_article_chunks_within_token_limits, test_real_kb_chunks |
| 3 | Valid, unique article_id from the source | build: test_criterion_3_valid_article_id_from_source; articles: test_invalid_header_fails_loudly[article_id_*], test_duplicate_article_id_fails_loudly, test_real_kb_article_ids_valid_and_unique |
| 4 | README excluded; broken file fails loudly | articles: test_broken_header_fixture_fails_loudly_naming_the_file, test_broken_header_fixture_readme_is_not_read, test_readme_without_header_is_ignored, 23 test_invalid_header_fails_loudly cases; build: test_criterion_4_readme_never_in_index, test_cli_broken_header_exits_non_zero_and_leaves_nothing |
| 5 | Idempotence by SHA-256 | idempotence: test_criterion_5_two_runs_byte_identical[v1], [v2] |
| 6 | Unique chunk IDs, c1..cn with no gaps | build: test_criterion_6_chunk_ids_unique_and_gapless; chunking: test_chunk_fields_and_ids_numbered_through_article, test_long_article_chunk_ids, test_real_kb_chunks |
| 7 | Manifest counts match | build: test_criterion_7_manifest_counts |
| 8 | Split and overlap tested with a synthetic long article | chunking: test_long_article_sections_are_split, test_long_article_pieces_cover_section_at_block_boundaries, test_long_article_overlap_kinds, test_long_article_every_piece_repeats_prefix, plus 8 exact-rule tests with the fake tokenizer |

## Other spec 01 rules (v1.2 to v1.5)

| Rule | Covering tests |
|---|---|
| Oversized table / paragraph / list item | test_oversized_block_fails_loudly, test_big_table_fixture_fails_loudly, test_cli_big_table_exits_non_zero_and_leaves_nothing |
| Empty ## section | test_empty_section_fails_loudly, test_empty_last_section_fails_loudly |
| Empty folder | test_empty_folder_fails |
| Duplicate YAML keys | test_invalid_header_fails_loudly[duplicate_key_*] |
| Byte-order mark | test_byte_order_mark_* |
| Code fence | test_code_fence_fails_loudly |
| No partial output / existing index untouched | test_failure_while_writing_leaves_no_partial_output, test_failed_rebuild_keeps_existing_index, test_bad_vectors_fail_before_writing |
| Manifest contents, no timestamps | test_manifest_fields, test_manifest_has_no_timestamps |

## Spec 03 contract tests (all in test_ingestion_contract.py)

| # | Contract test | Covering tests |
|---|---|---|
| 1 | Six fields, correct types | test_contract_1_six_fields_with_correct_types, test_contract_1_text_exactly_as_stored |
| 2 | Score descending, ties by chunk_id | test_contract_2_sorted_by_score_then_chunk_id, test_contract_2_equal_scores_ordered_by_chunk_id |
| 3 | At most k | test_contract_3_at_most_k_results, test_contract_3_fewer_only_if_index_is_smaller |
| 4 | Scores in [-1, 1] | test_contract_4_scores_within_range, test_contract_4_scores_are_capped, test_contract_4_scores_are_cosine_similarity |
| 5 | Identical results within a run and across restarts | test_contract_5_same_query_same_results_within_run, test_contract_5_same_results_across_process_restarts (two subprocesses, compared bit-for-bit) |
| 6 | kb_version equals the one requested | test_contract_6_kb_version_matches_requested, test_contract_6_searches_only_the_requested_index |
| 7 | Invalid input raises | test_contract_7_invalid_input_raises (11 cases) |
| 8 | Model mismatch fails at startup | test_contract_8_model_revision_mismatch_fails, test_contract_8_model_name_mismatch_fails |
| 9 | kb_info returns every article, sorted | test_contract_9_kb_info_every_article_sorted[v1/v2], test_kb_info_is_read_only |
| 10 | Missing index fails | test_contract_10_missing_index_fails, test_contract_10_missing_manifest_fails |
| 11 | Manifest kb_version mismatch fails | test_contract_11_manifest_kb_version_mismatch_fails, test_contract_11_index_in_wrong_folder_fails |
| 12 | SHA-256 mismatch fails | test_contract_12_changed_file_fails_hash_check[vectors/metadata], test_contract_12_wrong_manifest_hash_fails[index/metadata] |

## Spec 03 startup checks (ingestion/retrieval.py)

| Check | Code | Tests |
|---|---|---|
| Index exists | Check 1 in open_retrieval | Contract test 10 |
| Manifest kb_version matches | Check 2 | Contract test 11 |
| SHA-256 matches, for both files | Check 3, _check_hash | Contract test 12, plus test_missing_index_file_fails |
| Model name and revision match | Check 4 | Contract test 8 |

## Mutation checks performed (tests proven able to fail)

- Stage b: overlap limit raised from 50 to 120 -> two fixture tests failed.
- Stage e: timestamp added to manifest -> idempotence test failed.
Code restored after each check (git showed no diff).