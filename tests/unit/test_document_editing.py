from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.skills.document_utils import (
    parse_skill_document,
    read_skill_document_and_metadata,
    render_skill_document,
)
from harness_asset_manager.application.agents.parser import (
    parse_agent_document,
    render_agent_document,
)
from harness_asset_manager.application.slash_commands.codecs import (
    FrontmatterMarkdownCommandCodec,
    _render_frontmatter,
)
from harness_asset_manager.application.slash_commands.models import SlashCommand


class SkillDocumentUtilsTests(unittest.TestCase):
    def test_parse_and_render_skill_document_preserves_order(self) -> None:
        doc = """---
name: code-reviewer
description: Reviews pull requests
author: Jane Doe
version: 1.2.0
tags:
  - code
  - review
---

# Code Reviewer Skill

Use this skill to review code.
"""
        body, metadata = parse_skill_document(doc)
        self.assertEqual(body, "# Code Reviewer Skill\n\nUse this skill to review code.")
        keys = [m["key"] for m in metadata]
        self.assertEqual(keys, ["name", "description", "author", "version", "tags"])

        updated_metadata = [
            {"key": "name", "value": "code-reviewer-updated"},
            {"key": "description", "value": "Reviews pull requests carefully"},
            *[m for m in metadata if m["key"] not in {"name", "description"}],
        ]
        rendered = render_skill_document(
            metadata=updated_metadata,
            body="# Code Reviewer Skill (Updated)\n\nNew body.",
        )

        re_body, re_metadata = parse_skill_document(rendered)
        self.assertEqual(re_body, "# Code Reviewer Skill (Updated)\n\nNew body.")
        re_keys = [m["key"] for m in re_metadata]
        self.assertEqual(re_keys, ["name", "description", "author", "version", "tags"])
        re_dict = {m["key"]: m["value"] for m in re_metadata}
        self.assertEqual(re_dict["name"], "code-reviewer-updated")
        self.assertEqual(re_dict["description"], "Reviews pull requests carefully")
        self.assertEqual(re_dict["author"], "Jane Doe")
        self.assertEqual(re_dict["version"], "1.2.0")

    def test_read_skill_document_and_metadata_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            pkg = Path(tmpdir) / "test-skill"
            pkg.mkdir()
            skill_md = pkg / "SKILL.md"
            skill_md.write_text(
                "---\nname: my-skill\ndescription: desc\ncustom-k: custom-v\n---\nBody text\n",
                encoding="utf-8",
            )

            body, metadata = read_skill_document_and_metadata(pkg)
            self.assertEqual(body, "Body text")
            self.assertEqual(metadata, [
                {"key": "name", "value": "my-skill"},
                {"key": "description", "value": "desc"},
                {"key": "custom-k", "value": "custom-v"},
            ])


class AgentDocumentCustomMetadataTests(unittest.TestCase):
    def test_render_agent_document_with_extra_metadata(self) -> None:
        rendered = render_agent_document(
            name="test-agent",
            description="test description",
            prompt="Agent prompt here.",
            tools=("Read", "Grep"),
            extra_metadata=[
                ("model", "claude-3-opus"),
                ("permissionMode", "acceptEdits"),
                ("customFlag", "true"),
            ],
        )

        parsed = parse_agent_document(rendered, slug="test-agent", path=Path("test.md"))
        self.assertEqual(parsed.name, "test-agent")
        self.assertEqual(parsed.description, "test description")
        self.assertEqual(parsed.tools, ("Read", "Grep"))
        self.assertEqual(parsed.prompt, "Agent prompt here.")
        self.assertEqual(parsed.metadata["model"], "claude-3-opus")
        self.assertEqual(parsed.metadata["permissionMode"], "acceptEdits")
        self.assertTrue(parsed.metadata["customFlag"])


class SlashCommandFrontmatterMetadataTests(unittest.TestCase):
    def test_slash_command_custom_metadata_rendering(self) -> None:
        cmd = SlashCommand(
            name="review-pr",
            description="Review a pull request",
            prompt="Please review the PR: $ARGUMENTS",
            frontmatter=(
                'description: "Review a pull request"',
                'argument-hint: "[pr-number]"',
                'model: "gpt-4o"',
            ),
        )

        codec = FrontmatterMarkdownCommandCodec()
        rendered = codec.render(
            cmd,
            custom_metadata=[
                {"key": "argument-hint", "value": "[pr-number]"},
                {"key": "model", "value": "gpt-4o"},
                {"key": "timeout", "value": "120"},
            ],
        )

        parsed = codec.parse("review-pr", rendered)
        self.assertEqual(parsed.name, "review-pr")
        self.assertEqual(parsed.description, "Review a pull request")
        self.assertEqual(parsed.prompt, "Please review the PR: $ARGUMENTS")
        self.assertIn('argument-hint: [pr-number]', parsed.frontmatter)
        self.assertIn('model: gpt-4o', parsed.frontmatter)
        self.assertIn('timeout: 120', parsed.frontmatter)
