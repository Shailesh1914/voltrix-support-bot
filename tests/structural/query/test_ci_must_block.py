def test_ci_must_block_this_pull_request():
    # Deliberately failing test, to prove CI blocks a merge.
    # This branch must NEVER be merged.
    assert 1 == 2