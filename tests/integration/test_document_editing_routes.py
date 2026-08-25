from __future__ import annotations

import unittest

from harness_asset_manager.application.skills.manifest import SkillStoreEntry
from harness_asset_manager.application.skills.package import fingerprint_package
from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import seed_skill_package, seed_store_manifest


class DocumentEditingRoutesTests(unittest.TestCase):
    def test_skills_document_update_roundtrip(self) -> None:
        with AppTestHarness() as harness:
            # Seed a skill in the shared store
            package_root = seed_skill_package(
                harness.spec.skills_store_root,
                "doc-skill",
                "Document Skill",
                body="Original markdown body.",
                source_kind="github",
                source_locator="github:mode-io/doc-skill",
            )
            revision, _ = fingerprint_package(package_root)
            seed_store_manifest(
                harness.spec,
                [
                    SkillStoreEntry(
                        package_dir="doc-skill",
                        declared_name="Document Skill",
                        source_kind="github",
                        source_locator="github:mode-io/doc-skill",
                        revision=revision,
                    )
                ],
            )

            # Get initial skill detail
            detail = harness.get_json("/api/skills/shared:doc-skill")
            self.assertEqual(detail["documentMarkdown"], "# Document Skill\n\nOriginal markdown body.")
            self.assertEqual(detail["name"], "Document Skill")

            # Update document via PUT /api/skills/{ref}/document
            update_resp = harness.put_json(
                "/api/skills/shared:doc-skill/document",
                {
                    "body": "Updated markdown body with extra instructions.",
                    "metadata": [
                        {"key": "name", "value": "Document Skill Pro"},
                        {"key": "description", "value": "Enhanced skill description"},
                        {"key": "custom-tag", "value": "production"},
                        {"key": "author", "value": "Alice"},
                    ],
                },
            )
            self.assertTrue(update_resp["ok"])

            # Verify updated detail
            updated_detail = harness.get_json("/api/skills/shared:doc-skill")
            self.assertEqual(updated_detail["documentMarkdown"], "Updated markdown body with extra instructions.")
            self.assertEqual(updated_detail["name"], "Document Skill Pro")
            self.assertEqual(updated_detail["description"], "Enhanced skill description")
            metadata_dict = {m["key"]: m["value"] for m in updated_detail["metadata"]}
            self.assertEqual(metadata_dict["custom-tag"], "production")
            self.assertEqual(metadata_dict["author"], "Alice")

    def test_update_skill_document_without_metadata_carries_frontmatter_forward(self) -> None:
        """An edit that omits metadata must not silently strip existing frontmatter."""
        with AppTestHarness() as harness:
            package_root = seed_skill_package(
                harness.spec.skills_store_root,
                "doc-skill",
                "Document Skill",
                body="Original markdown body.",
                source_kind="github",
                source_locator="github:mode-io/doc-skill",
            )
            # Add a custom frontmatter key HAM does not interpret.
            skill_md = package_root / "SKILL.md"
            skill_md.write_text(
                skill_md.read_text(encoding="utf-8").replace(
                    "---\n", "---\ncustom-k: custom-v\n", 1
                ),
                encoding="utf-8",
            )
            revision, _ = fingerprint_package(package_root)
            seed_store_manifest(
                harness.spec,
                [
                    SkillStoreEntry(
                        package_dir="doc-skill",
                        declared_name="Document Skill",
                        source_kind="github",
                        source_locator="github:mode-io/doc-skill",
                        revision=revision,
                    )
                ],
            )

            update_resp = harness.put_json(
                "/api/skills/shared:doc-skill/document",
                {"body": "Updated markdown body."},
            )
            self.assertTrue(update_resp["ok"])

            updated_detail = harness.get_json("/api/skills/shared:doc-skill")
            self.assertEqual(updated_detail["documentMarkdown"], "Updated markdown body.")
            # Frontmatter untouched by the request survives verbatim.
            self.assertEqual(updated_detail["name"], "Document Skill")
            metadata_dict = {m["key"]: m["value"] for m in updated_detail["metadata"]}
            self.assertEqual(metadata_dict.get("custom-k"), "custom-v")

    def test_agents_update_with_metadata_roundtrip(self) -> None:
        with AppTestHarness() as harness:
            # Create an agent
            created = harness.post_json(
                "/api/agents",
                {
                    "name": "Planner Agent",
                    "description": "Plans execution paths",
                    "prompt": "You plan everything carefully.",
                    "tools": ["Read", "Grep"],
                },
            )
            ref = created["ref"]

            # Update agent with custom metadata
            updated = harness.put_json(
                f"/api/agents/{ref}",
                {
                    "name": "Planner Agent v2",
                    "description": "Plans execution paths with speed",
                    "prompt": "You plan fast.",
                    "tools": ["Read", "Edit", "Bash"],
                    "model": "claude-3-5-sonnet",
                    "effort": "high",
                    "metadata": [
                        {"key": "permissionMode", "value": "acceptEdits"},
                        {"key": "customKey", "value": "customVal"},
                    ],
                },
            )
            self.assertEqual(updated["name"], "Planner Agent v2")
            self.assertEqual(updated["description"], "Plans execution paths with speed")
            self.assertEqual(updated["tools"], ["Read", "Edit", "Bash"])
            self.assertEqual(updated["model"], "claude-3-5-sonnet")
            self.assertEqual(updated["effort"], "high")
            config_dict = {c["key"]: c["value"] for c in updated["configuration"]}
            self.assertNotIn("model", config_dict)
            self.assertNotIn("effort", config_dict)
            self.assertEqual(config_dict["permissionMode"], "acceptEdits")
            self.assertEqual(config_dict["customKey"], "customVal")

    def test_slash_command_update_with_metadata_roundtrip(self) -> None:
        with AppTestHarness() as harness:
            # Create a slash command
            harness.post_json(
                "/api/slash-commands",
                {
                    "name": "summarize",
                    "description": "Summarize content",
                    "prompt": "Summarize the following text:\n$ARGUMENTS",
                },
            )

            # Update slash command with custom metadata
            updated = harness.put_json(
                "/api/slash-commands/summarize",
                {
                    "description": "Summarize content briefly",
                    "prompt": "Summarize briefly:\n$ARGUMENTS",
                    "targets": ["codex"],
                    "metadata": [
                        {"key": "argument-hint", "value": "[text]"},
                        {"key": "max-tokens", "value": "500"},
                    ],
                },
            )
            self.assertTrue(updated["ok"])
            cmd = updated["command"]
            self.assertEqual(cmd["description"], "Summarize content briefly")
            self.assertEqual(cmd["prompt"], "Summarize briefly:\n$ARGUMENTS")
            meta_dict = {m["key"]: m["value"] for m in cmd["metadata"]}
            self.assertEqual(meta_dict["argument-hint"], "[text]")
            self.assertEqual(meta_dict["max-tokens"], "500")
