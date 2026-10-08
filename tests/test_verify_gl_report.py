"""A green dedicated GL job cannot be fabricated by skip policy or absent renderer evidence."""
from pathlib import Path

import pytest

from scripts.verify_gl_report import verify_report


@pytest.mark.parametrize("body", ["", "<testcase><skipped/></testcase>",
                                  "<testcase><failure/></testcase>",
                                  "<testcase><error/></testcase>", "<testcase/>"])
def test_empty_skipped_failed_or_unproven_report_rejected(tmp_path, body):
    path = tmp_path / "report.xml"
    path.write_text(f"<testsuite>{body}</testsuite>", encoding="utf-8")
    with pytest.raises(ValueError):
        verify_report(path)


def test_actual_renderer_and_successful_cases_accepted(tmp_path):
    path = tmp_path / "report.xml"
    path.write_text('<testsuites><testsuite><testcase><properties>'
                    '<property name="gl_renderer" value="llvmpipe"/>'
                    '</properties></testcase><testcase/></testsuite></testsuites>', encoding="utf-8")
    assert verify_report(path) == 2
    with pytest.raises(ValueError, match="fewer cases"):
        verify_report(path, minimum_cases=3)


def test_missing_report_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        verify_report(Path(tmp_path) / "absent.xml")


@pytest.mark.parametrize("minimum", [0, -1])
def test_invalid_case_requirement_cannot_disable_gate(tmp_path, minimum):
    with pytest.raises(ValueError, match="must be positive"):
        verify_report(tmp_path / "unused.xml", minimum_cases=minimum)
