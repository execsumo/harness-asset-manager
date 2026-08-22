from __future__ import annotations

import unittest
from pathlib import Path

from harness_asset_manager.portable_paths import from_portable_path, resolve_home, to_portable_path


class PortablePathsTests(unittest.TestCase):
    def test_to_portable_path_under_home(self) -> None:
        home = Path("/home/alice")
        path = Path("/home/alice/.claude/agents/reviewer.md")
        self.assertEqual(to_portable_path(path, home=home), "~/.claude/agents/reviewer.md")

    def test_to_portable_path_already_tilde(self) -> None:
        home = Path("/home/alice")
        self.assertEqual(
            to_portable_path("~/.claude/agents/reviewer.md", home=home),
            "~/.claude/agents/reviewer.md",
        )

    def test_to_portable_path_outside_home(self) -> None:
        home = Path("/home/alice")
        path = Path("/var/custom/agents/reviewer.md")
        self.assertEqual(to_portable_path(path, home=home), "/var/custom/agents/reviewer.md")

    def test_from_portable_path_tilde(self) -> None:
        home = Path("/home/bob")
        resolved = from_portable_path("~/.claude/agents/reviewer.md", home=home)
        self.assertEqual(resolved, Path("/home/bob/.claude/agents/reviewer.md"))

    def test_from_portable_path_tilde_root(self) -> None:
        home = Path("/home/bob")
        self.assertEqual(from_portable_path("~", home=home), Path("/home/bob"))
        self.assertEqual(from_portable_path("~/", home=home), Path("/home/bob"))

    def test_from_portable_path_legacy_local_absolute(self) -> None:
        home = Path("/home/bob")
        legacy_local = Path("/home/bob/.claude/agents/reviewer.md")
        resolved = from_portable_path(legacy_local, home=home)
        self.assertEqual(resolved, legacy_local)

    def test_from_portable_path_legacy_foreign_absolute(self) -> None:
        home = Path("/home/bob")
        foreign_path = Path("/Users/alice/.claude/agents/reviewer.md")
        self.assertIsNone(from_portable_path(foreign_path, home=home))

    def test_from_portable_path_empty_or_whitespace(self) -> None:
        home = Path("/home/bob")
        self.assertIsNone(from_portable_path("", home=home))
        self.assertIsNone(from_portable_path("   ", home=home))

    def test_from_portable_path_relative(self) -> None:
        home = Path("/home/bob")
        resolved = from_portable_path(".claude/agents/reviewer.md", home=home)
        self.assertEqual(resolved, Path("/home/bob/.claude/agents/reviewer.md"))


if __name__ == "__main__":
    unittest.main()
