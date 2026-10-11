"""Stage e: idempotence (spec 01 acceptance criterion 5).

Running ingestion twice on the same unchanged KB must give
byte-identical index, metadata and manifest files, checked by SHA-256.
Each run is a separate `python -m ingestion.build` process, as a real
rebuild would be. Same-machine idempotence only (spec decision, Step 7).
"""

import subprocess
import sys

import pytest
from conftest import DATA_DIR, REPO_ROOT

from ingestion.build import build_index
from ingestion.config import MANIFEST_FILE, METADATA_FILE, VECTORS_FILE
from ingestion.index_files import sha256_file

INDEX_FILES = (VECTORS_FILE, METADATA_FILE, MANIFEST_FILE)


def hashes(folder):
    return {name: sha256_file(folder / name) for name in INDEX_FILES}


def run_build(kb_folder, out_root):
    result = subprocess.run(
        [sys.executable, "-m", "ingestion.build", str(kb_folder), "--out-root", str(out_root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_criterion_5_two_runs_byte_identical(version, tmp_path, embedding_model, token_counter):
    kb_folder = DATA_DIR / f"kb_{version}"
    first_root, second_root = tmp_path / "first", tmp_path / "second"

    run_build(kb_folder, first_root)
    first = hashes(first_root / version)

    # Second run in a new process, into a separate folder.
    run_build(kb_folder, second_root)
    assert hashes(second_root / version) == first

    # Third run rebuilding over the first index in place.
    run_build(kb_folder, first_root)
    assert hashes(first_root / version) == first

    # An in-process build (as the tests use) gives the same bytes too.
    in_process = build_index(
        kb_folder, tmp_path / "in_process", model=embedding_model, counter=token_counter
    )
    assert hashes(in_process) == first
