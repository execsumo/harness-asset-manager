from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from harness_asset_manager.application.container import build_backend_container
from harness_asset_manager.cli.main import main, normalize_argv
from tests.support.fake_home import create_fake_home_spec, seed_skill_package


class AdoptCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = TemporaryDirectory(prefix="harnessam-adopt-cli-")
        self.addCleanup(self._tempdir.cleanup)
        self.spec = create_fake_home_spec(Path(self._tempdir.name))
        env_patch = mock.patch.dict("os.environ", self.spec.env(), clear=True)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        isatty_patch = mock.patch("sys.stdin.isatty", return_value=False)
        isatty_patch.start()
        self.addCleanup(isatty_patch.stop)

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def run_json(self, *argv: str) -> object:
        code, out, err = self.run_cli(*argv, "--json")
        self.assertEqual(code, 0, msg=err or out)
        return json.loads(out)

    def test_adopt_group_is_not_treated_as_serve_argument(self) -> None:
        self.assertEqual(normalize_argv(["adopt"]), ["adopt"])
        self.assertEqual(normalize_argv(["adopt", "--dry-run"]), ["adopt", "--dry-run"])

    def test_adopt_nothing_to_adopt(self) -> None:
        code, out, _ = self.run_cli("adopt")
        self.assertEqual(code, 0)
        self.assertIn("Nothing to adopt", out)

    def test_adopt_dry_run_and_json(self) -> None:
        container = build_backend_container(self.spec.env())
        skill_src = seed_skill_package(self.spec.home / "downloads", "my-skill", "My Skill")
        dest = container.skills_store.ingest(
            source_path=skill_src,
            declared_name="My Skill",
            source_kind="github",
            source_locator="github:org/my-skill",
            source_ref="main",
        )
        container.skills_mutations.enable_managed_package(dest, "claude")
        (self.spec.claude_root / "my-skill").unlink()

        # Dry run text
        code, out, _ = self.run_cli("adopt", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("skills", out)
        self.assertIn("My Skill", out)
        self.assertIn("LINK", out)
        # Should not have linked
        self.assertFalse((self.spec.claude_root / "my-skill").exists())

        # Dry run json
        payload = self.run_json("adopt", "--dry-run")
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload.get("linkableCount"), 1)
        self.assertFalse((self.spec.claude_root / "my-skill").exists())

    def test_adopt_non_interactive_requires_yes(self) -> None:
        container = build_backend_container(self.spec.env())
        skill_src = seed_skill_package(self.spec.home / "downloads", "my-skill", "My Skill")
        dest = container.skills_store.ingest(
            source_path=skill_src,
            declared_name="My Skill",
            source_kind="github",
            source_locator="github:org/my-skill",
            source_ref="main",
        )
        container.skills_mutations.enable_managed_package(dest, "claude")
        (self.spec.claude_root / "my-skill").unlink()

        # Running without --yes in non-tty raises / exits 1
        code, _, err = self.run_cli("adopt")
        self.assertEqual(code, 1)
        self.assertIn("pass --yes", err)

    def test_adopt_yes_applies_links(self) -> None:
        container = build_backend_container(self.spec.env())
        skill_src = seed_skill_package(self.spec.home / "downloads", "my-skill", "My Skill")
        dest = container.skills_store.ingest(
            source_path=skill_src,
            declared_name="My Skill",
            source_kind="github",
            source_locator="github:org/my-skill",
            source_ref="main",
        )
        container.skills_mutations.enable_managed_package(dest, "claude")
        (self.spec.claude_root / "my-skill").unlink()

        # Run with --yes
        code, out, _ = self.run_cli("adopt", "--yes")
        self.assertEqual(code, 0)
        self.assertIn("Adopted 1 binding(s)", out)
        self.assertTrue((self.spec.claude_root / "my-skill").is_symlink())

        # Next run reports nothing to adopt
        code, out, _ = self.run_cli("adopt")
        self.assertEqual(code, 0)
        self.assertIn("Nothing to adopt", out)

    def test_adopt_interactive_confirm(self) -> None:
        container = build_backend_container(self.spec.env())
        skill_src = seed_skill_package(self.spec.home / "downloads", "my-skill", "My Skill")
        dest = container.skills_store.ingest(
            source_path=skill_src,
            declared_name="My Skill",
            source_kind="github",
            source_locator="github:org/my-skill",
            source_ref="main",
        )
        container.skills_mutations.enable_managed_package(dest, "claude")
        (self.spec.claude_root / "my-skill").unlink()

        with mock.patch("sys.stdin.isatty", return_value=True), mock.patch("builtins.input", return_value="y"):
            code, out, _ = self.run_cli("adopt")
            self.assertEqual(code, 0)
            self.assertIn("Adopted 1 binding(s)", out)
            self.assertTrue((self.spec.claude_root / "my-skill").is_symlink())


if __name__ == "__main__":
    unittest.main()
