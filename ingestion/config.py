"""Fixed ingestion settings from specs/01-ingestion-spec.md, plus the
query prefix from specs/03-retrieval-contract.md.

These are spec values, not tuning knobs. Changing any of them needs a
spec change first.
"""

import re
from pathlib import Path

# Required header fields, in the order spec 01 lists them.
REQUIRED_HEADER_FIELDS = ("article_id", "title", "category", "kb_version")

CATEGORIES = frozenset(
    {"fault", "installation", "parameters", "maintenance", "safety"}
)

# KB-<3 digits>. ASCII digits only.
ARTICLE_ID_PATTERN = re.compile(r"KB-[0-9]{3}")

# Folder name kb_v1 -> kb_version "v1".
KB_FOLDER_PATTERN = re.compile(r"kb_(v[0-9]+)")

EXCLUDED_FILENAMES = frozenset({"README.md"})

# Embedding model, pinned to an exact Hugging Face commit (spec 01).
MODEL_NAME = "BAAI/bge-small-en-v1.5"
MODEL_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"

# BGE retrieval prefix that search() puts in front of every query
# (spec 03 v1.3, Step 9 experiment E1). Chunks are embedded without it.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Token limits, counted with the model's own tokenizer.
MODEL_TOKEN_LIMIT = 512
MAX_CHUNK_TOKENS = 300  # including special tokens
MAX_OVERLAP_TOKENS = 50

# Index layout: <index root>/<kb_version>/{vectors, metadata, manifest}.
# Index files are generated and never committed (indexes/ is ignored).
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX_ROOT = REPO_ROOT / "indexes"
VECTORS_FILE = "vectors.npy"
METADATA_FILE = "chunks.jsonl"
MANIFEST_FILE = "manifest.json"
