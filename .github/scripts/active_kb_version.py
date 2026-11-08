"""Print the knowledge base folder of the active KB version (spec 07).

Uses the bot's own reader (query.config.read_active_kb_version), so CI and
the bot can never disagree about data/ACTIVE_KB_VERSION. Prints one line,
e.g. "data/kb_v1". Fails if the file is missing or invalid, or if the
folder does not exist. Needs the requirements installed (query.config
imports python-dotenv).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from query.config import ConfigError, read_active_kb_version  # noqa: E402


def main() -> int:
    try:
        version = read_active_kb_version()
    except ConfigError as e:
        print(f"::error::{e}", file=sys.stderr)
        return 1
    folder = f"data/kb_{version}"
    if not (REPO_ROOT / folder).is_dir():
        print(
            f"::error::data/ACTIVE_KB_VERSION says {version}, but {folder}/ does not exist",
            file=sys.stderr,
        )
        return 1
    print(folder)
    return 0


if __name__ == "__main__":
    sys.exit(main())
