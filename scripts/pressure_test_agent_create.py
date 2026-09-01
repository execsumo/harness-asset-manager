#!/usr/bin/env python3
"""Pressure test for Agent creation flow: defaults, none, uninstalled/unknown harnesses, and contract fields."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Ensure virtualenv python is used if invoked with system python
VENV_DIR = REPO_ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "bin" / "python3"
if VENV_DIR.exists() and sys.prefix != str(VENV_DIR):
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

from tests.support.app_harness import AppTestHarness


def run_pressure_test() -> None:
    print("==========================================================")
    print("Starting Agent Create Flow Pressure Test...")
    print("==========================================================")

    with AppTestHarness(mixed=True) as harness:
        # Step 1: Create agent with defaults (configured auto-adopt defaults)
        print("\n--- Step 1: Configure auto-adopt defaults and create agent with defaults ---")
        harness.put_json(
            "/api/settings/auto-adopt/agents/harnesses",
            {"harnesses": ["claude", "cursor"]},
        )
        settings = harness.get_json("/api/settings")
        default_harnesses = settings["autoAdoptHarnesses"]["agents"]
        assert default_harnesses == ["claude", "cursor"], f"Expected ['claude', 'cursor'], got {default_harnesses}"
        print(f"✓ Configured auto-adopt default harnesses: {default_harnesses}")

        created_default = harness.post_json(
            "/api/agents",
            {
                "name": "Default Agent",
                "description": "Created with auto-adopt default harnesses",
                "prompt": "You are the default agent.",
                "harnesses": default_harnesses,
            },
        )
        assert created_default["ok"] is True, f"Expected ok=True, got {created_default.get('ok')}"
        assert created_default["harnessFailures"] == [], f"Expected empty harnessFailures, got {created_default.get('harnessFailures')}"
        assert created_default["ref"] == "default-agent"
        enabled_harnesses = {h["harness"] for h in created_default["harnesses"] if h["state"] == "enabled"}
        assert enabled_harnesses == {"claude", "cursor"}, f"Expected enabled {{'claude', 'cursor'}}, got {enabled_harnesses}"

        # Assert on files actually written to disk
        store_file_default = harness.spec.agents_root / "default-agent.md"
        assert store_file_default.is_file(), f"Store file missing: {store_file_default}"
        store_text = store_file_default.read_text(encoding="utf-8")
        assert "name: Default Agent" in store_text
        assert "description: Created with auto-adopt default harnesses" in store_text
        assert "You are the default agent." in store_text

        claude_binding = harness.spec.home / ".claude" / "agents" / "default-agent.md"
        cursor_binding = harness.spec.home / ".cursor" / "agents" / "default-agent.md"
        assert claude_binding.exists(), f"Claude binding missing: {claude_binding}"
        assert cursor_binding.exists(), f"Cursor binding missing: {cursor_binding}"
        assert claude_binding.is_symlink(), f"Claude binding should be symlink: {claude_binding}"
        assert cursor_binding.is_symlink(), f"Cursor binding should be symlink: {cursor_binding}"
        print("✓ Agent created with defaults; verified files and symlinks on disk for claude and cursor")

        # Step 2: Create agent with no harnesses (bound to nothing)
        print("\n--- Step 2: Create agent with empty harness list (bound to nothing) ---")
        created_bare = harness.post_json(
            "/api/agents",
            {
                "name": "Bare Agent",
                "description": "Agent bound to zero harnesses",
                "prompt": "You have no active harness bindings yet.",
                "harnesses": [],
            },
        )
        assert created_bare["ok"] is True, f"Expected ok=True, got {created_bare.get('ok')}"
        assert created_bare["harnessFailures"] == []
        assert created_bare["ref"] == "bare-agent"
        bare_enabled = [h["harness"] for h in created_bare["harnesses"] if h["state"] == "enabled"]
        assert bare_enabled == [], f"Expected 0 enabled harnesses, got {bare_enabled}"

        # Assert on files on disk: store exists, but NO harness directory has this agent
        store_file_bare = harness.spec.agents_root / "bare-agent.md"
        assert store_file_bare.is_file(), f"Store file missing: {store_file_bare}"
        assert not (harness.spec.home / ".claude" / "agents" / "bare-agent.md").exists()
        assert not (harness.spec.home / ".cursor" / "agents" / "bare-agent.md").exists()
        assert not (harness.spec.home / ".codex" / "agents" / "bare-agent.toml").exists()
        print("✓ Agent created with no harnesses; verified store exists and zero harness files written")

        # Step 3: Create agent against an uninstalled / unknown harness
        print("\n--- Step 3: Create agent with supported and uninstalled/unknown harness ---")
        created_partial = harness.post_json(
            "/api/agents",
            {
                "name": "Partial Agent",
                "description": "Testing unsupported harness handling",
                "prompt": "Test unsupported harness behavior.",
                "harnesses": ["claude", "phantom-unknown-harness"],
            },
            expected_status=200,
        )
        # 200 response, agent created, partial success surfaced cleanly
        assert created_partial["ok"] is False, f"Expected ok=False, got {created_partial.get('ok')}"
        assert created_partial["ref"] == "partial-agent"
        assert len(created_partial["harnessFailures"]) == 1, f"Expected 1 failure, got {created_partial.get('harnessFailures')}"
        failure = created_partial["harnessFailures"][0]
        assert failure["harness"] == "phantom-unknown-harness"
        assert "phantom-unknown-harness" in failure["error"]

        # The good harness (claude) was still bound
        partial_claude = next(h for h in created_partial["harnesses"] if h["harness"] == "claude")
        assert partial_claude["state"] == "enabled", f"Expected claude enabled, got {partial_claude['state']}"

        # Assert on files on disk
        store_file_partial = harness.spec.agents_root / "partial-agent.md"
        assert store_file_partial.is_file(), f"Store file missing: {store_file_partial}"
        claude_partial_file = harness.spec.home / ".claude" / "agents" / "partial-agent.md"
        assert claude_partial_file.is_file() and claude_partial_file.is_symlink()
        print("✓ Partial success returns 200: agent created, claude bound on disk, failure reported in harnessFailures")

        # Step 4: Create agent expressing full contract fields
        print("\n--- Step 4: Create agent with all contract fields ---")
        created_full = harness.post_json(
            "/api/agents",
            {
                "name": "Full Contract Agent",
                "description": "Full contract test",
                "prompt": "Instructions for full contract.",
                "color": "blue",
                "model": "claude-3-7-sonnet",
                "effort": "high",
                "tools": ["bash", "read_file"],
                "allowedSubagents": "true",
                "maxTurns": "45",
                "isolation": "worktree",
                "harnesses": ["claude"],
            },
        )
        assert created_full["ok"] is True
        assert created_full["color"] == "blue"
        assert created_full["model"] == "claude-3-7-sonnet"
        assert created_full["effort"] == "high"
        assert created_full["tools"] == ["bash", "read_file"]
        assert created_full["allowedSubagents"] == "true"
        assert created_full["maxTurns"] == "45"
        assert created_full["isolation"] == "worktree"

        store_file_full = harness.spec.agents_root / "full-contract-agent.md"
        full_text = store_file_full.read_text(encoding="utf-8")
        assert "color: blue" in full_text
        assert "model: claude-3-7-sonnet" in full_text
        assert "effort: high" in full_text
        assert "allowed_subagents: true" in full_text
        assert "max_turns: 45" in full_text
        assert "isolation: worktree" in full_text
        print("✓ Full contract fields correctly serialized and verified on disk")

    print("\n==========================================================")
    print("✓ ALL AGENT CREATE FLOW PRESSURE TESTS PASSED 100% CLEANLY")
    print("==========================================================")


if __name__ == "__main__":
    run_pressure_test()
