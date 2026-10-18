"""Print the pinned embedding model as GitHub step outputs (slug=..., revision=...).

Reads MODEL_NAME and MODEL_REVISION from ingestion/config.py without
importing it, so this runs before anything heavy is loaded. Fails if
either is missing or the revision is not a full commit hash.
"""

import ast
import re
import sys
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / "ingestion" / "config.py"


def pinned(path: Path = CONFIG) -> tuple[str, str]:
    values = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("MODEL_NAME", "MODEL_REVISION"):
                    values[target.id] = node.value.value
    name, revision = values.get("MODEL_NAME"), values.get("MODEL_REVISION")
    if not isinstance(name, str) or not name:
        sys.exit(f"MODEL_NAME not found in {path}")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        sys.exit(f"MODEL_REVISION in {path} is not a 40-character commit hash")
    return name, revision


if __name__ == "__main__":
    name, revision = pinned()
    print(f"slug={re.sub(r'[^A-Za-z0-9._-]', '_', name)}")
    print(f"revision={revision}")
