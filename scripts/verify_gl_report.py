"""Fail the dedicated GL job if it ran no tests, skipped tests, or recorded no actual renderer."""
from __future__ import annotations

import argparse
from pathlib import Path

from defusedxml import ElementTree


def verify_report(path: Path, *, minimum_cases: int = 1) -> int:
    """Return successful test count only after actual unskipped GL evidence is present."""
    if minimum_cases < 1:
        raise ValueError("minimum GL case count must be positive")
    root = ElementTree.parse(path).getroot()
    cases = list(root.iter("testcase"))
    if not cases:
        raise ValueError("GL report contains no executed tests")
    if len(cases) < minimum_cases:
        raise ValueError("GL report contains fewer cases than the dedicated suite requires")
    if any(case.find(tag) is not None for case in cases
           for tag in ("skipped", "failure", "error")):
        raise ValueError("GL job must pass every selected case without skips")
    renderers = [p.get("value", "").strip() for p in root.iter("property")
                 if p.get("name") == "gl_renderer"]
    if not any(renderers):
        raise ValueError("No actual OpenGL renderer was recorded")
    return len(cases)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--minimum-cases", type=int, default=10)
    args = parser.parse_args()
    print(f"Verified {verify_report(args.report, minimum_cases=args.minimum_cases)} "
          "actual GL regression cases")


if __name__ == "__main__":
    main()
