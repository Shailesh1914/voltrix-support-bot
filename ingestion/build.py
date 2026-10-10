"""Build the vector index for one knowledge base folder (spec 01).

Usage:
    .venv/bin/python -m ingestion.build data/kb_v1

Writes <index root>/<kb_version>/ with:
    vectors.npy    float32 unit vectors, row i = line i of chunks.jsonl
    chunks.jsonl   one chunk per line, sorted by chunk_id
    manifest.json  versions, settings, counts and SHA-256 hashes

Fail loudly: any problem gives a non-zero exit code and a message
naming the file. Everything is written to a temporary folder first and
only swapped into place when complete, so a failed build leaves no
partial output and an existing index is left untouched.
"""

import argparse
import json
import shutil
import sys
import tempfile
from importlib.metadata import version as package_version
from pathlib import Path

import numpy as np

from ingestion.articles import kb_version_from_folder, load_articles
from ingestion.chunking import Chunk, chunk_article
from ingestion.config import (
    DEFAULT_INDEX_ROOT,
    MANIFEST_FILE,
    MAX_CHUNK_TOKENS,
    MAX_OVERLAP_TOKENS,
    METADATA_FILE,
    MODEL_NAME,
    MODEL_REVISION,
    MODEL_TOKEN_LIMIT,
    VECTORS_FILE,
)
from ingestion.embedding import embed, load_model, load_token_counter
from ingestion.errors import IngestionError
from ingestion.index_files import METADATA_FIELDS, sha256_file

# Library versions recorded in the manifest (they affect the vectors).
RECORDED_LIBRARIES = (
    "sentence-transformers",
    "transformers",
    "tokenizers",
    "torch",
    "numpy",
)

NORM_TOLERANCE = 1e-3
INDEX_DIR_MODE = 0o755


def _check_vectors(kb_folder: Path, vectors: np.ndarray, chunk_count: int) -> None:
    if vectors.ndim != 2 or vectors.shape[0] != chunk_count:
        raise IngestionError(
            kb_folder, f"embedding returned shape {vectors.shape} for {chunk_count} chunks"
        )
    if not np.all(np.isfinite(vectors)):
        raise IngestionError(kb_folder, "embedding returned non-finite values")
    norms = np.linalg.norm(vectors, axis=1)
    if np.any(np.abs(norms - 1.0) > NORM_TOLERANCE):
        raise IngestionError(kb_folder, "embedding returned vectors that are not unit length")


def _write_metadata(path: Path, chunks: list[Chunk]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in chunks:
            record = {field: getattr(chunk, field) for field in METADATA_FIELDS}
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _manifest(kb_version, article_count, chunks, vectors, folder: Path) -> dict:
    return {
        "kb_version": kb_version,
        "model_name": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "model_token_limit": MODEL_TOKEN_LIMIT,
        "max_chunk_tokens": MAX_CHUNK_TOKENS,
        "max_overlap_tokens": MAX_OVERLAP_TOKENS,
        "embedding_dimension": int(vectors.shape[1]),
        "similarity": "cosine",
        "vectors_normalised": True,
        "article_count": article_count,
        "chunk_count": len(chunks),
        "index_file": VECTORS_FILE,
        "index_sha256": sha256_file(folder / VECTORS_FILE),
        "metadata_file": METADATA_FILE,
        "metadata_sha256": sha256_file(folder / METADATA_FILE),
        "library_versions": {name: package_version(name) for name in RECORDED_LIBRARIES},
    }


def _write_index(folder: Path, kb_version, article_count, chunks, vectors) -> None:
    np.save(folder / VECTORS_FILE, vectors, allow_pickle=False)
    _write_metadata(folder / METADATA_FILE, chunks)
    manifest = _manifest(kb_version, article_count, chunks, vectors, folder)
    (folder / MANIFEST_FILE).write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _swap_into_place(staging: Path, final: Path) -> None:
    """Replace final with staging; on failure keep the old final."""
    backup = None
    if final.exists():
        backup = final.with_name(f".{final.name}.old-{staging.name}")
        final.rename(backup)
    try:
        staging.rename(final)
    except BaseException:
        if backup is not None:
            backup.rename(final)
        raise
    if backup is not None:
        shutil.rmtree(backup)


def build_index(
    kb_folder: Path,
    index_root: Path = DEFAULT_INDEX_ROOT,
    *,
    model=None,
    counter=None,
) -> Path:
    """Build <index_root>/<kb_version>/ from kb_folder; return its path."""
    kb_folder = Path(kb_folder)
    index_root = Path(index_root)
    kb_version = kb_version_from_folder(kb_folder)

    articles = load_articles(kb_folder)
    counter = counter or load_token_counter()
    chunks = [chunk for article in articles for chunk in chunk_article(article, counter)]
    chunks.sort(key=lambda chunk: chunk.chunk_id)

    model = model or load_model()
    vectors = embed(model, [chunk.text for chunk in chunks])
    _check_vectors(kb_folder, vectors, len(chunks))

    index_root.mkdir(parents=True, exist_ok=True)
    final = index_root / kb_version
    staging = Path(tempfile.mkdtemp(prefix=f".{kb_version}.building-", dir=index_root))
    try:
        staging.chmod(INDEX_DIR_MODE)  # mkdtemp creates it owner-only (0700)
        _write_index(staging, kb_version, len(articles), chunks, vectors)
        _swap_into_place(staging, final)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return final


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ingestion.build",
        description="Build the vector index for one knowledge base folder.",
    )
    parser.add_argument("kb_folder", type=Path, help="e.g. data/kb_v1")
    parser.add_argument(
        "--out-root",
        type=Path,
        default=DEFAULT_INDEX_ROOT,
        help="index root folder (default: indexes/; tests use a temp folder)",
    )
    args = parser.parse_args(argv)
    try:
        final = build_index(args.kb_folder, args.out_root)
    except IngestionError as error:
        print(f"ingestion failed: {error}", file=sys.stderr)
        return 1
    manifest = json.loads((final / MANIFEST_FILE).read_text(encoding="utf-8"))
    print(
        f"Built {final}: {manifest['article_count']} articles, "
        f"{manifest['chunk_count']} chunks"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
