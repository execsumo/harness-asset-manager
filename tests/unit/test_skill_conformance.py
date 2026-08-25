from __future__ import annotations

import unittest

from harness_asset_manager.application.skills.conformance import (
    DESCRIPTION_MAX_LENGTH,
    NAME_MAX_LENGTH,
    check_skill_conformance,
)


def codes(**kwargs) -> list[str]:
    defaults = {
        "name": "pdf-processing",
        "name_declared": True,
        "description": "Extract PDF text. Use when handling PDFs.",
        "package_dir": "pdf-processing",
    }
    defaults.update(kwargs)
    return [issue.code for issue in check_skill_conformance(**defaults)]


class SkillConformanceTests(unittest.TestCase):
    """Report, never enforce. Every rule is transcribed from the specification."""

    def test_a_conformant_skill_reports_nothing(self) -> None:
        self.assertEqual(codes(), [])

    def test_name_charset_rules(self) -> None:
        self.assertEqual(codes(name="PDF-Processing"), ["name_invalid", "name_directory_mismatch"])
        self.assertEqual(codes(name="-pdf"), ["name_invalid", "name_directory_mismatch"])
        self.assertEqual(codes(name="pdf-"), ["name_invalid", "name_directory_mismatch"])
        self.assertEqual(codes(name="pdf--processing"), ["name_invalid", "name_directory_mismatch"])
        self.assertEqual(codes(name="pdf processing"), ["name_invalid", "name_directory_mismatch"])

    def test_name_length(self) -> None:
        long_name = "a" * (NAME_MAX_LENGTH + 1)
        self.assertEqual(codes(name=long_name, package_dir=long_name), ["name_too_long"])
        ok_name = "a" * NAME_MAX_LENGTH
        self.assertEqual(codes(name=ok_name, package_dir=ok_name), [])

    def test_length_wins_over_charset_so_one_departure_gives_one_issue(self) -> None:
        """A 65-character name is one problem, not two — say the actionable one."""
        long_bad = "A" * (NAME_MAX_LENGTH + 1)
        self.assertEqual(codes(name=long_bad, package_dir=long_bad), ["name_too_long"])

    def test_a_missing_name_is_not_reported_as_an_invalid_one(self) -> None:
        """`declared_name` falls back to the first heading, which fails the charset
        rule. Reporting that would send the reader to fix the wrong thing."""
        self.assertEqual(
            codes(name="Academic Research Toolkit", name_declared=False, package_dir="academic"),
            ["name_missing"],
        )

    def test_name_must_match_the_package_directory(self) -> None:
        self.assertEqual(codes(name="ideation", package_dir="creative-ideation"), ["name_directory_mismatch"])

    def test_the_directory_rule_is_skipped_when_there_is_no_package(self) -> None:
        """An unmanaged skill has no HAM package directory to match against."""
        self.assertEqual(codes(name="ideation", package_dir=None), [])

    def test_description_presence_and_length(self) -> None:
        self.assertEqual(codes(description=""), ["description_missing"])
        self.assertEqual(codes(description="   "), ["description_missing"])
        self.assertEqual(codes(description="x" * (DESCRIPTION_MAX_LENGTH + 1)), ["description_too_long"])
        self.assertEqual(codes(description="x" * DESCRIPTION_MAX_LENGTH), [])

    def test_issues_accumulate_rather_than_short_circuiting(self) -> None:
        self.assertEqual(
            codes(name="Bad Name", package_dir="bad-name", description=""),
            ["name_invalid", "name_directory_mismatch", "description_missing"],
        )

    def test_every_message_names_the_correction(self) -> None:
        """The panel shows these verbatim, so a bare code is not enough."""
        for issue in check_skill_conformance(
            name="Bad Name", name_declared=True, description="", package_dir="bad-name"
        ):
            self.assertGreater(len(issue.message), 30, issue.code)
            self.assertTrue(issue.message.endswith("."), issue.code)


if __name__ == "__main__":
    unittest.main()
