from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.agents.parser import (
    parse_agent_document,
    render_agent_document,
)
from harness_asset_manager.application.skills.document_utils import (
    parse_skill_document,
    read_skill_document_and_metadata,
    render_skill_document,
)
from harness_asset_manager.application.slash_commands.codecs import (
    FrontmatterMarkdownCommandCodec,
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


class SkillDocumentNestedFrontmatterTests(unittest.TestCase):
    """Nested frontmatter must survive a read-edit-write round trip byte for byte.

    HAM's document editor is the only thing that rewrites a `SKILL.md`, and it used
    to flatten every nested structure: a key whose value is a map or a list parsed
    as an empty scalar and its indented lines were dropped on the floor. The four
    shapes below are the ones that actually occur in a real skills store.
    """

    def _round_trip(self, document: str) -> str:
        body, metadata = parse_skill_document(document)
        assert body is not None
        return render_skill_document(body=body, metadata=metadata)

    def test_nested_map_survives(self) -> None:
        document = (
            "---\n"
            "name: academic-research\n"
            "metadata:\n"
            "  hermes: true\n"
            "  version: \"1.0\"\n"
            "---\n"
            "\n"
            "body\n"
        )
        self.assertEqual(self._round_trip(document), document)

    def test_list_survives(self) -> None:
        document = (
            "---\n"
            "name: local-backend-service-setup\n"
            "tags:\n"
            "  - monorepo\n"
            "  - backend\n"
            "---\n"
            "\n"
            "body\n"
        )
        self.assertEqual(self._round_trip(document), document)

    def test_list_of_maps_survives(self) -> None:
        document = (
            "---\n"
            "name: google-workspace\n"
            "required_credential_files:\n"
            "  - path: google_token.json\n"
            "    description: OAuth2 token\n"
            "---\n"
            "\n"
            "body\n"
        )
        self.assertEqual(self._round_trip(document), document)

    def test_literal_block_scalar_survives(self) -> None:
        """`|` keeps newlines, so re-rendering it inline produced invalid YAML."""
        document = (
            "---\n"
            "name: comfyui\n"
            "setup: |\n"
            "  first line\n"
            "  second line\n"
            "---\n"
            "\n"
            "body\n"
        )
        self.assertEqual(self._round_trip(document), document)

    def test_a_nested_block_is_not_mistaken_for_the_body(self) -> None:
        document = (
            "---\n"
            "metadata:\n"
            "  author: someone\n"
            "name: after-the-block\n"
            "---\n"
            "\n"
            "real body\n"
        )
        body, metadata = parse_skill_document(document)
        self.assertEqual(body, "real body")
        self.assertEqual([entry["key"] for entry in metadata], ["metadata", "name"])
        self.assertEqual(metadata[1]["value"], "after-the-block")

    def test_a_scalar_that_cannot_be_written_plain_is_re_quoted(self) -> None:
        """The other half of the same defect: unwrapping quotes broke the file.

        A description holding ``toolkit: paper discovery`` was written back plain, and
        the second colon turned the line into a nested mapping — the file stopped
        parsing. 18 skills in a real store carry a description like this.
        """
        document = (
            '---\n'
            'description: "Research toolkit: paper discovery and review"\n'
            '---\n'
            '\n'
            'body\n'
        )
        body, metadata = parse_skill_document(document)
        assert body is not None
        self.assertEqual(metadata[0]["value"], "Research toolkit: paper discovery and review")
        self.assertEqual(render_skill_document(body=body, metadata=metadata), document)

    def test_a_flow_collection_is_not_quoted_into_a_string(self) -> None:
        """Quoting must stay narrow: `[linux, macos]` is a list, not a string."""
        body, metadata = parse_skill_document(
            "---\nplatforms: [linux, macos]\n---\n\nbody\n"
        )
        assert body is not None
        rendered = render_skill_document(body=body, metadata=metadata)
        self.assertIn("platforms: [linux, macos]", rendered)

    def test_embedded_quotes_survive_the_round_trip(self) -> None:
        document = '---\ntitle: "The \\"Pricing Man\\": a study"\n---\n\nbody\n'
        body, metadata = parse_skill_document(document)
        assert body is not None
        self.assertEqual(metadata[0]["value"], 'The "Pricing Man": a study')
        self.assertEqual(render_skill_document(body=body, metadata=metadata), document)

    def test_folded_block_scalars_still_fold_to_one_line(self) -> None:
        """Unchanged behaviour: `>-` is a display nicety, and folding loses nothing."""
        body, metadata = parse_skill_document(
            "---\ndescription: >-\n  Line one\n  line two\n---\n\nbody\n"
        )
        self.assertEqual(metadata, [{"key": "description", "value": "Line one line two"}])


class AgentDocumentCustomMetadataTests(unittest.TestCase):
    def test_render_agent_document_with_extra_metadata(self) -> None:
        rendered = render_agent_document(
            name="test-agent",
            description="test description",
            prompt="Agent prompt here.",
            tools=("Read", "Grep"),
            model="claude-3-opus",
            effort="high",
            extra_metadata=[
                ("permissionMode", "acceptEdits"),
                ("customFlag", "true"),
            ],
        )

        parsed = parse_agent_document(rendered, slug="test-agent", path=Path("test.md"))
        self.assertEqual(parsed.name, "test-agent")
        self.assertEqual(parsed.description, "test description")
        self.assertEqual(parsed.tools, ("Read", "Grep"))
        self.assertEqual(parsed.prompt, "Agent prompt here.")
        # Contract fields ride their own kwargs and land in canonical position.
        self.assertEqual(parsed.model, "claude-3-opus")
        self.assertEqual(parsed.effort, "high")
        self.assertEqual(rendered.splitlines()[3], "model: claude-3-opus")
        self.assertEqual(rendered.splitlines()[4], "effort: high")
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
