"""Build-time check: the installed packages are exactly the pins in
requirements.txt, and torch is the CPU-only build (spec 08 section 6).

Usage (inside the image build):  python deploy/check_pins.py requirements.txt

Exit 0 if everything matches, 1 with one line per problem otherwise.
"""

import re
import sys
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

PIN_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==(\S+)$")


def normalise(name: str) -> str:
    """PEP 503 name: lower case, runs of - _ . become one -."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_pins(text: str) -> dict[str, str]:
    """name -> version for every 'name==version' line. Comments, blank
    lines and pip options (--extra-index-url ...) are skipped. Any other
    line is an error, so a loose requirement can never slip through."""
    pins: dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = PIN_LINE.match(line)
        if not match:
            raise ValueError(f"requirements.txt line {number} is not an exact pin: {raw.strip()!r}")
        name = normalise(match.group(1))
        if name in pins:
            raise ValueError(f"requirements.txt pins {match.group(1)} twice")
        pins[name] = match.group(2)
    if not pins:
        raise ValueError("requirements.txt has no pins")
    return pins


def pin_problems(pins: dict[str, str], installed: Callable[[str], str | None]) -> list[str]:
    """installed(name) gives the installed version, or None if missing."""
    problems = []
    for name, wanted in sorted(pins.items()):
        got = installed(name)
        if got is None:
            problems.append(f"{name}: pinned {wanted}, not installed")
        elif got != wanted:
            problems.append(f"{name}: pinned {wanted}, installed {got}")
    return problems


def installed_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python deploy/check_pins.py requirements.txt", file=sys.stderr)
        return 2
    try:
        pins = parse_pins(Path(argv[0]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"check_pins: {e}", file=sys.stderr)
        return 1
    problems = pin_problems(pins, installed_version)

    import torch

    if torch.version.cuda is not None:
        problems.append(f"torch: built with CUDA {torch.version.cuda}, expected CPU-only")
    if problems:
        for problem in problems:
            print(f"check_pins: {problem}", file=sys.stderr)
        return 1
    print(f"check_pins: {len(pins)} pins installed exactly; torch is CPU-only")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
