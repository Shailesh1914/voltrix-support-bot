"""deploy/ scripts are plain files, not a package: make them importable."""

import sys
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[1]
REPO_ROOT = DEPLOY.parent
for path in (str(DEPLOY), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)
