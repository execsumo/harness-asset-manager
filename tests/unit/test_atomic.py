from __future__ import annotations

import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from harness_asset_manager.atomic_files import atomic_write_text, file_lock


class AtomicWriteTextTests(unittest.TestCase):
    def test_writes_full_content_to_target_path(self) -> None:
        with TemporaryDirectory() as temp:
            target = Path(temp) / "out.json"
            atomic_write_text(target, "hello\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "hello\n")

    def test_creates_parent_directories(self) -> None:
        with TemporaryDirectory() as temp:
            target = Path(temp) / "deep" / "nested" / "file.txt"
            atomic_write_text(target, "x")
            self.assertEqual(target.read_text(encoding="utf-8"), "x")

    def test_replaces_existing_file_atomically(self) -> None:
        with TemporaryDirectory() as temp:
            target = Path(temp) / "out.txt"
            target.write_text("old", encoding="utf-8")
            atomic_write_text(target, "new")
            self.assertEqual(target.read_text(encoding="utf-8"), "new")

    def test_failed_write_leaves_no_temp_files_and_keeps_original(self) -> None:
        with TemporaryDirectory() as temp:
            target = Path(temp) / "out.txt"
            target.write_text("preserved", encoding="utf-8")
            with mock.patch("os.replace", side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    atomic_write_text(target, "broken")
            self.assertEqual(target.read_text(encoding="utf-8"), "preserved")
            tmp_files = [p for p in Path(temp).iterdir() if p.name != "out.txt"]
            self.assertEqual(tmp_files, [])


class AtomicWriteSymlinkGuardTests(unittest.TestCase):
    """`os.replace` onto a symlink destroys the link — the same mechanism by which a
    harness's atomic editor breaks a binding we created. Aimed at one of our own
    binding paths it would silently orphan a store entry, so it must be refused."""

    def test_refuses_to_write_over_a_symlink_by_default(self) -> None:
        with TemporaryDirectory() as temp:
            real = Path(temp) / "real.md"
            real.write_text("store content", encoding="utf-8")
            link = Path(temp) / "binding.md"
            link.symlink_to(real)

            with self.assertRaises(ValueError):
                atomic_write_text(link, "clobber")

            self.assertTrue(link.is_symlink())
            self.assertEqual(real.read_text(encoding="utf-8"), "store content")

    def test_follow_symlinks_writes_through_and_keeps_the_link(self) -> None:
        """The opt-in case: a harness config file the user symlinked into dotfiles."""
        with TemporaryDirectory() as temp:
            real = Path(temp) / "dotfiles" / "settings.json"
            real.parent.mkdir()
            real.write_text("{}", encoding="utf-8")
            link = Path(temp) / "settings.json"
            link.symlink_to(real)

            atomic_write_text(link, '{"ok": true}', follow_symlinks=True)

            self.assertTrue(link.is_symlink())
            self.assertEqual(real.read_text(encoding="utf-8"), '{"ok": true}')

    def test_a_dangling_symlink_is_refused_rather_than_materialised(self) -> None:
        with TemporaryDirectory() as temp:
            link = Path(temp) / "binding.md"
            link.symlink_to(Path(temp) / "missing.md")
            with self.assertRaises(ValueError):
                atomic_write_text(link, "x")
            self.assertTrue(link.is_symlink())


class FileLockTests(unittest.TestCase):
    def test_serializes_concurrent_critical_sections(self) -> None:
        with TemporaryDirectory() as temp:
            lock_path = Path(temp) / "guard.lock"
            shared: list[str] = []
            holding = threading.Event()

            def writer(label: str, hold_after_acquire: float) -> None:
                with file_lock(lock_path):
                    shared.append(f"enter:{label}")
                    if hold_after_acquire:
                        holding.set()
                        threading.Event().wait(hold_after_acquire)
                    shared.append(f"exit:{label}")

            t1 = threading.Thread(target=writer, args=("a", 0.1))
            t1.start()
            holding.wait(timeout=1.0)
            t2 = threading.Thread(target=writer, args=("b", 0.0))
            t2.start()
            t1.join()
            t2.join()
            self.assertEqual(shared, ["enter:a", "exit:a", "enter:b", "exit:b"])


if __name__ == "__main__":
    unittest.main()
