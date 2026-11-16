"""Disabling a managed hook removes only the occurrence Harness Asset Manager wrote.

Each case seeds a harness config holding the managed hook next to user hooks that
share its command (other events, other matcher groups, other files, other hooks in
the same entry), disables the managed one, and asserts every user hook survives.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.hooks.adapters import FileBackedHooksAdapter
from harness_asset_manager.application.hooks.store import HookSpec, HookStore
from harness_asset_manager.errors import MutationError
from harness_asset_manager.harness import HarnessKernelService, HarnessSupportStore
from harness_asset_manager.paths import resolve_app_paths


def _env(home: Path) -> dict[str, str]:
    return {"HOME": str(home), "PATH": ""}


def _adapter(harness: str, *, home: Path) -> FileBackedHooksAdapter:
    kernel = HarnessKernelService.from_environment(
        _env(home),
        support_store=HarnessSupportStore(home / "settings.json"),
    )
    binding = next(
        binding for binding in kernel.bindings_for_family("hooks") if binding.definition.harness == harness
    )
    return FileBackedHooksAdapter(
        definition=binding.definition,
        profile=binding.profile,
        context=kernel.context,
    )


def _manage(home: Path, *specs: HookSpec) -> None:
    # The adapter resolves the managed spec from the env-derived manifest path.
    store = HookStore(resolve_app_paths(_env(home)).hooks_store_manifest)
    for spec in specs:
        store.upsert_managed(spec)


def _manual_id(command: str) -> str:
    return "manual:" + hashlib.sha256(command.encode("utf-8")).hexdigest()[:16]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _cmd(command: str, **extra: object) -> dict[str, object]:
    return {"type": "command", "command": command, **extra}


class ClaudeScopedHookRemovalTests(unittest.TestCase):
    def test_disable_keeps_same_command_in_other_events_and_matchers(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, HookSpec(id="lint", event="pre_tool_use", command="lint.sh", match="shell"))
            adapter = _adapter("claude", home=home)

            def config(*, managed: bool) -> dict[str, object]:
                bash_hooks = [_cmd("lint.sh", id="lint")] if managed else []
                bash_hooks.append(_cmd("lint.sh"))
                return {
                    "theme": "dark",
                    "hooks": {
                        "PreToolUse": [
                            {"matcher": "Bash", "hooks": bash_hooks},
                            {"matcher": "Read", "hooks": [_cmd("lint.sh")]},
                            {"matcher": "Write", "hooks": []},
                        ],
                        "PostToolUse": [{"matcher": "Bash", "hooks": [_cmd("lint.sh")]}],
                    },
                }

            _write_json(adapter.config_path, config(managed=True))
            adapter.disable_hook("lint")

            self.assertEqual(_read_json(adapter.config_path), config(managed=False))

    def test_disable_adopted_hook_keeps_look_alike_in_other_event(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            hook_id = _manual_id("fmt.sh")
            _manage(home, HookSpec(id=hook_id, event="pre_tool_use", command="fmt.sh", match="shell"))
            adapter = _adapter("claude", home=home)
            _write_json(
                adapter.config_path,
                {
                    "hooks": {
                        "PreToolUse": [{"matcher": "Bash", "hooks": [_cmd("fmt.sh")]}],
                        "PostToolUse": [{"matcher": "Bash", "hooks": [_cmd("fmt.sh")]}],
                        "Stop": [{"hooks": [_cmd("fmt.sh")]}],
                    }
                },
            )

            adapter.disable_hook(hook_id)

            self.assertEqual(
                _read_json(adapter.config_path),
                {
                    "hooks": {
                        "PostToolUse": [{"matcher": "Bash", "hooks": [_cmd("fmt.sh")]}],
                        "Stop": [{"hooks": [_cmd("fmt.sh")]}],
                    }
                },
            )

    def test_id_less_copy_of_app_created_hook_is_left_alone(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, HookSpec(id="lint", event="pre_tool_use", command="lint.sh", match="shell"))
            adapter = _adapter("claude", home=home)
            _write_json(
                adapter.config_path,
                {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [_cmd("lint.sh")]}]}},
            )
            before = adapter.config_path.read_bytes()

            adapter.disable_hook("lint")

            self.assertEqual(adapter.config_path.read_bytes(), before)

    def test_duplicate_adopted_occurrences_refuse_with_409(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            hook_id = _manual_id("fmt.sh")
            _manage(home, HookSpec(id=hook_id, event="pre_tool_use", command="fmt.sh", match="shell"))
            adapter = _adapter("claude", home=home)
            _write_json(
                adapter.config_path,
                {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [_cmd("fmt.sh"), _cmd("fmt.sh")]}]}},
            )
            before = adapter.config_path.read_bytes()

            with self.assertRaises(MutationError) as ctx:
                adapter.disable_hook(hook_id)

            self.assertEqual(ctx.exception.status, 409)
            self.assertEqual(adapter.config_path.read_bytes(), before)

    def test_duplicate_tagged_occurrences_refuse_with_409(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, HookSpec(id="lint", event="pre_tool_use", command="lint.sh", match="shell"))
            adapter = _adapter("claude", home=home)
            _write_json(
                adapter.config_path,
                {
                    "hooks": {
                        "PreToolUse": [{"matcher": "Bash", "hooks": [_cmd("lint.sh", id="lint")]}],
                        "PostToolUse": [{"matcher": "Bash", "hooks": [_cmd("lint.sh", id="lint")]}],
                    }
                },
            )
            before = adapter.config_path.read_bytes()

            with self.assertRaises(MutationError) as ctx:
                adapter.disable_hook("lint")

            self.assertEqual(ctx.exception.status, 409)
            self.assertEqual(adapter.config_path.read_bytes(), before)


_CODEX_CONFIG = """\
model = "o3"

[[hooks.PreToolUse]]
matcher = "Bash"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "lint.sh"
id = "lint"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "lint.sh"

[[hooks.PreToolUse]]
matcher = "Read"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "lint.sh"

[[hooks.PostToolUse]]
matcher = "Bash"

[[hooks.PostToolUse.hooks]]
type = "command"
command = "lint.sh"
"""


class CodexScopedHookRemovalTests(unittest.TestCase):
    def test_disable_keeps_same_command_in_other_events_and_matchers(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, HookSpec(id="lint", event="pre_tool_use", command="lint.sh", match="shell"))
            adapter = _adapter("codex", home=home)
            adapter.config_path.parent.mkdir(parents=True, exist_ok=True)
            adapter.config_path.write_text(_CODEX_CONFIG, encoding="utf-8")

            adapter.disable_hook("lint")

            self.assertEqual(
                tomllib.loads(adapter.config_path.read_text(encoding="utf-8")),
                {
                    "model": "o3",
                    "hooks": {
                        "PreToolUse": [
                            {"matcher": "Bash", "hooks": [_cmd("lint.sh")]},
                            {"matcher": "Read", "hooks": [_cmd("lint.sh")]},
                        ],
                        "PostToolUse": [{"matcher": "Bash", "hooks": [_cmd("lint.sh")]}],
                    },
                },
            )


class CursorScopedHookRemovalTests(unittest.TestCase):
    def test_disable_keeps_same_command_in_other_events(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, HookSpec(id="guard", event="pre_tool_use", command="guard.sh", match="shell"))
            adapter = _adapter("cursor", home=home)
            _write_json(
                adapter.config_path,
                {
                    "version": 1,
                    "hooks": {
                        "beforeShellExecution": [{"command": "guard.sh"}, {"command": "audit.sh"}],
                        "afterShellExecution": [{"command": "guard.sh"}],
                        "preToolUse": [{"command": "guard.sh"}],
                    },
                },
            )

            adapter.disable_hook("guard")

            self.assertEqual(
                _read_json(adapter.config_path),
                {
                    "version": 1,
                    "hooks": {
                        "beforeShellExecution": [{"command": "audit.sh"}],
                        "afterShellExecution": [{"command": "guard.sh"}],
                        "preToolUse": [{"command": "guard.sh"}],
                    },
                },
            )

    def test_duplicate_occurrences_refuse_with_409(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, HookSpec(id="guard", event="pre_tool_use", command="guard.sh", match="shell"))
            adapter = _adapter("cursor", home=home)
            _write_json(
                adapter.config_path,
                {"version": 1, "hooks": {"beforeShellExecution": [{"command": "guard.sh"}, {"command": "guard.sh"}]}},
            )
            before = adapter.config_path.read_bytes()

            with self.assertRaises(MutationError) as ctx:
                adapter.disable_hook("guard")

            self.assertEqual(ctx.exception.status, 409)
            self.assertEqual(adapter.config_path.read_bytes(), before)


def _argv(command: str) -> dict[str, object]:
    return {"command": ["/bin/sh", "-c", command]}


class OpenCodeScopedHookRemovalTests(unittest.TestCase):
    def test_disable_stop_hook_keeps_same_command_on_file_edited(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, HookSpec(id="notify", event="stop", command="notify.sh"))
            adapter = _adapter("opencode", home=home)
            _write_json(
                adapter.config_path,
                {
                    "experimental": {
                        "hook": {
                            "session_completed": [_argv("notify.sh")],
                            "file_edited": {"*.py": [_argv("notify.sh")]},
                        }
                    }
                },
            )

            adapter.disable_hook("notify")

            self.assertEqual(
                _read_json(adapter.config_path),
                {"experimental": {"hook": {"file_edited": {"*.py": [_argv("notify.sh")]}}}},
            )

    def test_disable_file_edit_hook_keeps_same_command_elsewhere(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, HookSpec(id="fmt", event="post_tool_use", command="fmt.sh", match="file_write"))
            adapter = _adapter("opencode", home=home)
            _write_json(
                adapter.config_path,
                {
                    "experimental": {
                        "hook": {
                            "session_completed": [_argv("fmt.sh")],
                            "file_edited": {"*": [_argv("fmt.sh")], "*.md": [_argv("fmt.sh")]},
                        }
                    }
                },
            )

            adapter.disable_hook("fmt")

            self.assertEqual(
                _read_json(adapter.config_path),
                {
                    "experimental": {
                        "hook": {
                            "session_completed": [_argv("fmt.sh")],
                            "file_edited": {"*.md": [_argv("fmt.sh")]},
                        }
                    }
                },
            )


class AntigravityScopedHookRemovalTests(unittest.TestCase):
    def test_disable_leaves_user_entry_with_same_command_in_another_file(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, HookSpec(id="guard", event="stop", command="guard.sh"))
            adapter = _adapter("agy", home=home)
            _write_json(adapter.config_path, {"guard": {"enabled": True, "Stop": [_cmd("guard.sh")]}})
            user_path = home / ".gemini" / "antigravity-cli" / "hooks.json"
            _write_json(
                user_path,
                {
                    "user-guard": {
                        "enabled": True,
                        "Stop": [_cmd("guard.sh")],
                        "PreToolUse": [{"matcher": "*", "hooks": [_cmd("audit.sh")]}],
                    }
                },
            )
            user_before = user_path.read_bytes()

            adapter.disable_hook("guard")

            self.assertEqual(_read_json(adapter.config_path), {})
            self.assertEqual(user_path.read_bytes(), user_before)

    def test_disable_adopted_multi_hook_entry_removes_only_the_managed_hook(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, HookSpec(id="team", event="stop", command="guard.sh"))
            adapter = _adapter("agy", home=home)
            _write_json(
                adapter.config_path,
                {"team": {"enabled": True, "Stop": [_cmd("guard.sh"), _cmd("audit.sh")]}},
            )

            adapter.disable_hook("team")

            self.assertEqual(
                _read_json(adapter.config_path),
                {"team": {"enabled": True, "Stop": [_cmd("audit.sh")]}},
            )


if __name__ == "__main__":
    unittest.main()
