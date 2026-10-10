"""Fixed ingestion settings from specs/01-ingestion-spec.md.

These are spec values, not tuning knobs. Changing any of them needs a
spec change first.
"""

import re

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
