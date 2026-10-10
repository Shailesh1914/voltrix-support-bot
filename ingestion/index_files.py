"""Index file format details shared by build (writer) and retrieval (reader)."""

import hashlib
from pathlib import Path

# Field order of each chunks.jsonl record (spec 01, "Output").
METADATA_FIELDS = ("chunk_id", "article_id", "title", "category", "kb_version", "text")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
