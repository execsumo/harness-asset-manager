#!/usr/bin/env python3
"""Pressure test for Agent Skills frontmatter, validation, auto-enable on save, and non-destructive removal."""

from __future__ import annotations

import sys
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from harness_asset_manager.application.skills.manifest import SkillStoreEntry
from harness_asset_manager.application.skills.package import fingerprint_package
from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import seed_skill_package, seed_store_manifest


def run_pressure_test() -> None:
    print("==========================================================")
    print("Starting Agent Skills Pressure Test...")
    print("==========================================================")

    # Use isolated AppTestHarness with mixed=True
    with AppTestHarness(mixed=True) as harness:
        # 1. Create managed agent `code-sheriff` without skills
        print("\n--- Step 1: Create managed agent code-sheriff without skills ---")
        created_agent = harness.post_json(
            "/api/agents",
            {
                "name": "Code Sheriff",
                "description": "Enforces code standards",
                "prompt": "You are the code sheriff. Be strict.",
                "tools": ["Read", "Bash"],
            },
        )
        assert created_agent["ref"] == "code-sheriff"
        assert created_agent["skills"] == []
        print("✓ Agent code-sheriff created without skills")

        # 2. Adopt / seed managed skills: `code-review`, `frontend-debugging`
        print("\n--- Step 2: Seed managed skills: code-review, frontend-debugging ---")
        skill_entries = []
        for slug, name in [
            ("code-review", "Code Review"),
            ("frontend-debugging", "Frontend Debugging"),
        ]:
            pkg = seed_skill_package(
                harness.spec.skills_store_root,
                slug,
                name,
                body=f"# {name}\n\nPerforms {name.lower()} workflows.",
            )
            rev, _ = fingerprint_package(pkg)
            skill_entries.append(
                SkillStoreEntry(
                    package_dir=slug,
                    declared_name=name,
                    source_kind="github",
                    source_locator=f"github:org/{slug}",
                    revision=rev,
                )
            )
        seed_store_manifest(harness.spec, skill_entries)
        harness.container.skills_read_models.invalidate()
        harness.container.invalidation.invalidate_all()
        print("✓ Seeded managed skills: code-review, frontend-debugging")

        # 3. Enable agent `code-sheriff` on `claude` and `cursor`
        print("\n--- Step 3: Enable agent code-sheriff on claude and cursor ---")
        harness.post_json("/api/agents/code-sheriff/enable", {"harness": "claude"})
        harness.post_json("/api/agents/code-sheriff/enable", {"harness": "cursor"})

        claude_agent = harness.spec.home / ".claude" / "agents" / "code-sheriff.md"
        cursor_agent = harness.spec.home / ".cursor" / "agents" / "code-sheriff.md"
        assert claude_agent.exists()
        assert cursor_agent.exists()
        print("✓ Agent enabled on claude and cursor")

        # Ensure skills are not enabled yet on claude/cursor
        assert not (harness.spec.claude_root / "code-review").exists()
        assert not (harness.spec.claude_root / "frontend-debugging").exists()
        assert not (harness.spec.cursor_root / "code-review").exists()
        assert not (harness.spec.cursor_root / "frontend-debugging").exists()

        # 4. Edit `code-sheriff` frontmatter to add skills: [code-review, frontend-debugging]
        print("\n--- Step 4 & 5: Edit code-sheriff to attach skills and verify auto-enable ---")
        update_resp = harness.put_json(
            "/api/agents/code-sheriff",
            {
                "skills": ["code-review", "frontend-debugging"],
            },
        )
        assert update_resp.get("ok") is True
        auto_enabled = update_resp.get("autoEnabled", [])
        failed = update_resp.get("failed", [])
        assert failed == []

        auto_pairs = {(item["skillRef"], item["harness"]) for item in auto_enabled}
        expected_pairs = {
            ("shared:code-review", "claude"),
            ("shared:code-review", "cursor"),
            ("shared:frontend-debugging", "claude"),
            ("shared:frontend-debugging", "cursor"),
        }
        assert auto_pairs == expected_pairs, f"Expected {expected_pairs}, got {auto_pairs}"
        print(f"✓ Response returned autoEnabled for all 4 pairs: {auto_pairs}")

        # 5. Verify file on disk and symlinks
        store_file = harness.spec.agents_root / "code-sheriff.md"
        store_content = store_file.read_text(encoding="utf-8")
        assert "skills:\n  - code-review\n  - frontend-debugging" in store_content, (
            f"Store file skills YAML formatting mismatch:\n{store_content}"
        )
        print("✓ Store file contains properly formatted YAML list for skills")

        assert (harness.spec.claude_root / "code-review").is_symlink()
        assert (harness.spec.claude_root / "frontend-debugging").is_symlink()
        assert (harness.spec.cursor_root / "code-review").is_symlink()
        assert (harness.spec.cursor_root / "frontend-debugging").is_symlink()
        print("✓ All skills symlinks exist in .claude/skills and .cursor/skills")

        # 6 & 7. Edit frontmatter again to drop frontend-debugging (skills: [code-review])
        print("\n--- Step 6 & 7: Drop frontend-debugging and verify non-destructive removal ---")
        update_resp_2 = harness.put_json(
            "/api/agents/code-sheriff",
            {
                "skills": ["code-review"],
            },
        )
        assert update_resp_2.get("ok") is True
        assert update_resp_2.get("autoEnabled") == []
        assert [s["slug"] for s in update_resp_2.get("skills", [])] == ["code-review"]

        store_content_2 = store_file.read_text(encoding="utf-8")
        assert "skills:\n  - code-review" in store_content_2
        assert "frontend-debugging" not in store_content_2

        # Non-destructive removal: frontend-debugging remains enabled on claude and cursor!
        assert (harness.spec.claude_root / "frontend-debugging").is_symlink()
        assert (harness.spec.cursor_root / "frontend-debugging").is_symlink()
        print("✓ Non-destructive removal verified: frontend-debugging remains enabled in harnesses")

        # 8 & 9. Attempt to save agent with skills: [nonexistent-skill] -> 400 rejection and unchanged store
        print("\n--- Step 8 & 9: Save with nonexistent skill -> 400 rejection ---")
        err_nonexistent = harness.put_json(
            "/api/agents/code-sheriff",
            {
                "skills": ["nonexistent-skill"],
            },
            expected_status=400,
        )
        assert err_nonexistent.get("code") == "invalid_skill"
        assert store_file.read_text(encoding="utf-8") == store_content_2
        print("✓ Rejected nonexistent skill with 400 invalid_skill; store file unchanged")

        # 10 & 11. Attempt to save agent with unmanaged skill -> 400 rejection
        print("\n--- Step 10 & 11: Save with unmanaged skill -> 400 rejection ---")
        # In mixed fixture, trace-lens is unmanaged (located in codex_legacy_root)
        err_unmanaged = harness.put_json(
            "/api/agents/code-sheriff",
            {
                "skills": ["trace-lens"],
            },
            expected_status=400,
        )
        assert err_unmanaged.get("code") == "invalid_skill"
        assert store_file.read_text(encoding="utf-8") == store_content_2
        print("✓ Rejected unmanaged skill with 400 invalid_skill; store file unchanged")

    print("\n==========================================================")
    print("✓ ALL AGENT SKILLS PRESSURE TESTS PASSED 100% CLEANLY")
    print("==========================================================")


if __name__ == "__main__":
    run_pressure_test()
