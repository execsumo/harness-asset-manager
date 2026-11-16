from __future__ import annotations

import copy
import unittest

from harness_asset_manager.application.hooks.mappers import (
    CursorHooksMapper,
    OpenCodeHooksMapper,
)
from harness_asset_manager.application.hooks.store import HookSpec
from harness_asset_manager.errors import MutationError


def _argv(command: str) -> dict[str, object]:
    return {"command": ["/bin/sh", "-c", command]}


class CursorHookEnableTests(unittest.TestCase):
    def test_enable_writes_only_the_target_event(self) -> None:
        document: dict[str, object] = {
            "version": 1,
            "hooks": {"preToolUse": [{"command": "lint.sh"}], "stop": [{"command": "lint.sh"}]},
        }
        CursorHooksMapper().enable_hook(
            document, HookSpec(id="lint", event="pre_tool_use", command="lint.sh", match="shell")
        )
        self.assertEqual(
            document["hooks"],
            {
                "preToolUse": [{"command": "lint.sh"}],
                "stop": [{"command": "lint.sh"}],
                "beforeShellExecution": [{"command": "lint.sh"}],
            },
        )

    def test_re_enable_repairs_the_one_occurrence_in_place(self) -> None:
        document: dict[str, object] = {
            "hooks": {"beforeShellExecution": [{"command": "a.sh"}, {"command": "lint.sh", "extra": 1}]}
        }
        CursorHooksMapper().enable_hook(
            document, HookSpec(id="lint", event="pre_tool_use", command="lint.sh", match="shell")
        )
        self.assertEqual(
            document["hooks"],
            {"beforeShellExecution": [{"command": "a.sh"}, {"command": "lint.sh"}]},
        )

    def test_enable_refuses_duplicates_in_the_target_event(self) -> None:
        document: dict[str, object] = {
            "hooks": {"beforeShellExecution": [{"command": "lint.sh"}, {"command": "lint.sh"}]}
        }
        before = copy.deepcopy(document)
        with self.assertRaises(MutationError) as raised:
            CursorHooksMapper().enable_hook(
                document, HookSpec(id="lint", event="pre_tool_use", command="lint.sh", match="shell")
            )
        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(document["hooks"], before["hooks"])


class OpenCodeHookEnableTests(unittest.TestCase):
    def test_stop_enable_keeps_file_edited_copies(self) -> None:
        document: dict[str, object] = {
            "experimental": {"hook": {"file_edited": {"*": [_argv("n.sh")], "*.py": [_argv("n.sh")]}}}
        }
        OpenCodeHooksMapper().enable_hook(document, HookSpec(id="n", event="stop", command="n.sh"))
        self.assertEqual(
            document,
            {
                "experimental": {
                    "hook": {
                        "file_edited": {"*": [_argv("n.sh")], "*.py": [_argv("n.sh")]},
                        "session_completed": [_argv("n.sh")],
                    }
                }
            },
        )

    def test_file_edit_enable_keeps_session_completed_copy(self) -> None:
        document: dict[str, object] = {"experimental": {"hook": {"session_completed": [_argv("f.sh")]}}}
        OpenCodeHooksMapper().enable_hook(
            document, HookSpec(id="f", event="post_tool_use", command="f.sh", match="file_write")
        )
        self.assertEqual(
            document,
            {
                "experimental": {
                    "hook": {
                        "session_completed": [_argv("f.sh")],
                        "file_edited": {"*": [_argv("f.sh")]},
                    }
                }
            },
        )


if __name__ == "__main__":
    unittest.main()
