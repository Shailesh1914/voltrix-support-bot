"""Fail if a pytest JUnit XML report has any skipped test, or no tests at all.

Usage: python .github/scripts/check_no_skips.py REPORT.xml

In CI a skipped test is a failure: otherwise a missing index would make the
real-index tests skip silently and CI would still be green (spec 06).
Pytest records xfail tests as skipped too, so those also fail here.
"""

import sys
import xml.etree.ElementTree as ET


def skipped_tests(report: str) -> tuple[int, list[str]]:
    """(number of tests, one line per skipped test)."""
    root = ET.parse(report).getroot()
    suites = [root] if root.tag == "testsuite" else root.iter("testsuite")
    total, skipped = 0, []
    for suite in suites:
        for case in suite.iter("testcase"):
            total += 1
            skip = case.find("skipped")
            if skip is not None:
                name = f"{case.get('classname')}::{case.get('name')}"
                skipped.append(f"{name}: {skip.get('message', '').strip()}")
    return total, skipped


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: check_no_skips.py REPORT.xml", file=sys.stderr)
        return 2
    total, skipped = skipped_tests(argv[0])
    if total == 0:
        print(f"FAIL: no tests in {argv[0]}", file=sys.stderr)
        return 1
    if skipped:
        print(f"FAIL: {len(skipped)} of {total} tests were skipped (a skip fails CI):", file=sys.stderr)
        for line in skipped:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"OK: {total} tests, none skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
