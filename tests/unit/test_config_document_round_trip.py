from __future__ import annotations

import json
import unittest
from typing import get_args, get_type_hints

from harness_asset_manager.config_document import (
    CONFIG_FILE_FORMATS,
    ConfigDocumentError,
    blank_jsonc_comments,
    dump_config_document,
    empty_config_document,
    load_config_document,
    new_subtree,
)
from harness_asset_manager.harness.contracts import ConfigSubtreeBindingProfile

# ``tests/unit/test_writer_round_trip.py`` pins the same invariant one layer up: a
# writer must never destroy user configuration merely because it does not model it.
# It proves that for unmodeled *fields*, at the mapper boundary (dict -> dict).
#
# This file pins it at the boundary the mappers never reach — the *file* itself. Every
# family that binds into a harness config does a whole-document read-modify-write, so
# whatever ``load`` drops, ``dump`` deletes from the user's file. Comments and
# formatting live only here, which is why the mapper-level tests could all pass while
# ``~/.opencode/opencode.jsonc`` lost every comment it had and ``~/.codex/config.toml``
# lost every comment *and* its array style.
#
# For each format we pin:
#   1. Verbatim identity  -- load + dump with no mutation returns the input unchanged.
#   2. Unowned-content preservation -- comments and untouched keys survive a mutation.
#   3. Value fidelity -- parsing agrees with the stdlib on what the document means.


class JsoncCommentBlankingTests(unittest.TestCase):
    """The comment stripper must understand strings, not just characters.

    The regex this replaced was string-unaware and had two distinct failure modes on
    real configuration, both reproduced here as regression pins.
    """

    def test_blanking_preserves_offsets(self) -> None:
        text = '{\n  // note\n  "a": 1\n}'
        self.assertEqual(len(blank_jsonc_comments(text)), len(text))

    def test_comment_marker_inside_a_string_is_not_a_comment(self) -> None:
        # Previously truncated the document and raised "not valid JSONC".
        source = '{"note": "use // to comment", "a": 1}'
        document = load_config_document(source, file_format="jsonc")
        self.assertEqual(dict(document), json.loads(source))

    def test_block_comment_marker_inside_a_string_is_not_a_comment(self) -> None:
        # Previously rewrote the value to "ac" and reported success.
        source = '{"re": "a/*b*/c"}'
        document = load_config_document(source, file_format="jsonc")
        self.assertEqual(document["re"], "a/*b*/c")

    def test_trailing_comma_shape_inside_a_string_is_not_a_trailing_comma(self) -> None:
        # Previously rewrote the value to "trailing }".
        source = '{"s": "trailing, }"}'
        document = load_config_document(source, file_format="jsonc")
        self.assertEqual(document["s"], "trailing, }")

    def test_escaped_quote_does_not_end_the_string(self) -> None:
        source = r'{"esc": "a\"// b", "x": 1}'
        document = load_config_document(source, file_format="jsonc")
        self.assertEqual(dict(document), json.loads(source))

    def test_real_comments_and_trailing_commas_are_still_removed(self) -> None:
        source = """{
          // line comment
          "a": 1,
          /* block
             comment */
          "b": [1, 2,],
        }"""
        document = load_config_document(source, file_format="jsonc")
        self.assertEqual(dict(document), {"a": 1, "b": [1, 2]})

    def test_unterminated_block_comment_does_not_hang(self) -> None:
        document = load_config_document('{"a": 1}\n/* dangling', file_format="jsonc")
        self.assertEqual(dict(document), {"a": 1})


class JsoncRoundTripTests(unittest.TestCase):
    """``~/.opencode/opencode.jsonc`` — MCP, hooks and permissions all write here."""

    FIXTURE = """{
  // My OpenCode config -- hand written
  "theme": "dark",
  "mcp": {
    "exa": { "type": "local", "command": ["npx", "exa"] }
  },
  /* keep this one until the API key rotates */
  "model": "big"
}
"""

    def _round_trip(self, document: object) -> str:
        return dump_config_document(document, file_format="jsonc")

    def test_untouched_document_is_returned_verbatim(self) -> None:
        document = load_config_document(self.FIXTURE, file_format="jsonc")
        self.assertEqual(self._round_trip(document), self.FIXTURE)

    def test_dump_is_idempotent(self) -> None:
        once = self._round_trip(load_config_document(self.FIXTURE, file_format="jsonc"))
        twice = self._round_trip(load_config_document(once, file_format="jsonc"))
        self.assertEqual(once, twice)

    def test_comments_survive_an_added_subtree_entry(self) -> None:
        document = load_config_document(self.FIXTURE, file_format="jsonc")
        document["mcp"]["context7"] = {"type": "local", "command": ["npx", "c7"]}
        rendered = self._round_trip(document)
        self.assertIn("// My OpenCode config -- hand written", rendered)
        self.assertIn("/* keep this one until the API key rotates */", rendered)
        self.assertEqual(
            json.loads(blank_jsonc_comments(rendered))["mcp"]["context7"]["command"],
            ["npx", "c7"],
        )

    def test_comments_survive_a_removed_subtree_entry(self) -> None:
        document = load_config_document(self.FIXTURE, file_format="jsonc")
        del document["mcp"]["exa"]
        rendered = self._round_trip(document)
        self.assertIn("// My OpenCode config -- hand written", rendered)
        self.assertIn("/* keep this one until the API key rotates */", rendered)
        self.assertEqual(json.loads(blank_jsonc_comments(rendered))["mcp"], {})

    def test_untouched_keys_keep_their_original_formatting(self) -> None:
        document = load_config_document(self.FIXTURE, file_format="jsonc")
        document["mcp"]["exa"] = {"type": "local", "command": ["npx", "exa", "--v2"]}
        rendered = self._round_trip(document)
        # "theme" and "model" were never touched, so their lines are byte-identical.
        self.assertIn('  "theme": "dark",', rendered)
        self.assertIn('  "model": "big"', rendered)

    def test_added_top_level_key_adopts_the_document_indentation(self) -> None:
        document = load_config_document(self.FIXTURE, file_format="jsonc")
        document["hooks"] = {"beforeShell": []}
        rendered = self._round_trip(document)
        self.assertIn('\n  "hooks": {', rendered)
        self.assertIn("// My OpenCode config -- hand written", rendered)

    def test_written_output_is_valid_json_once_comments_are_stripped(self) -> None:
        document = load_config_document(self.FIXTURE, file_format="jsonc")
        document["mcp"]["context7"] = {"type": "local"}
        del document["theme"]
        rendered = self._round_trip(document)
        self.assertEqual(
            json.loads(blank_jsonc_comments(rendered)),
            {
                "mcp": {
                    "exa": {"type": "local", "command": ["npx", "exa"]},
                    "context7": {"type": "local"},
                },
                "model": "big",
            },
        )

    def test_trailing_comment_survives_an_appended_key(self) -> None:
        """The comma has to go *before* the comment, or it gets commented out."""
        source = '{\n  "a": 1  // muscle memory\n}\n'
        document = load_config_document(source, file_format="jsonc")
        document["b"] = 2
        rendered = dump_config_document(document, file_format="jsonc")
        self.assertIn("// muscle memory", rendered)
        self.assertEqual(json.loads(blank_jsonc_comments(rendered)), {"a": 1, "b": 2})

    def test_comment_about_a_kept_key_survives_removal_of_the_next_key(self) -> None:
        """The comment sits in the *removed* key's prefix, but describes the kept one."""
        source = '{\n  "a": 1,  // about a\n  "b": 2\n}\n'
        document = load_config_document(source, file_format="jsonc")
        del document["b"]
        rendered = dump_config_document(document, file_format="jsonc")
        self.assertIn("// about a", rendered)
        self.assertEqual(json.loads(blank_jsonc_comments(rendered)), {"a": 1})

    def test_removed_key_on_a_shared_line_does_not_drag_its_neighbour_back(self) -> None:
        """The rescue must fire on comments only — never on a same-line sibling key."""
        document = load_config_document('{"a": 1, "b": 2}', file_format="jsonc")
        del document["b"]
        rendered = dump_config_document(document, file_format="jsonc")
        self.assertEqual(json.loads(blank_jsonc_comments(rendered)), {"a": 1})

    def test_add_then_remove_returns_the_file_to_its_original_shape(self) -> None:
        """The full enable/disable cycle a user actually drives."""
        added = load_config_document(self.FIXTURE, file_format="jsonc")
        added["mcp"]["context7"] = {"type": "local"}
        intermediate = dump_config_document(added, file_format="jsonc")

        removed = load_config_document(intermediate, file_format="jsonc")
        del removed["mcp"]["context7"]
        final = dump_config_document(removed, file_format="jsonc")

        self.assertEqual(json.loads(blank_jsonc_comments(final)), json.loads(blank_jsonc_comments(self.FIXTURE)))
        for comment in ("// My OpenCode config -- hand written", "/* keep this one until the API key rotates */"):
            self.assertIn(comment, final)

    def test_single_line_object_gains_a_key_without_breaking(self) -> None:
        document = load_config_document('{"mcp": {"a": 1}}', file_format="jsonc")
        document["mcp"]["b"] = 2
        rendered = dump_config_document(document, file_format="jsonc")
        self.assertEqual(json.loads(blank_jsonc_comments(rendered)), {"mcp": {"a": 1, "b": 2}})

    def test_absent_file_produces_a_writable_document(self) -> None:
        document = empty_config_document("jsonc")
        document["mcp"] = {"exa": {"type": "local"}}
        rendered = dump_config_document(document, file_format="jsonc")
        self.assertEqual(json.loads(rendered), {"mcp": {"exa": {"type": "local"}}})

    def test_malformed_document_is_reported_not_silently_emptied(self) -> None:
        with self.assertRaises(ConfigDocumentError) as caught:
            load_config_document('{"a": ', file_format="jsonc")
        self.assertIn("not valid JSONC", str(caught.exception))


class PlainJsonRoundTripTests(unittest.TestCase):
    """``settings.json`` / ``hooks.json`` — no comments to keep, but key order is."""

    FIXTURE = '{\n  "b": 2,\n  "a": 1\n}\n'

    def test_untouched_document_is_returned_verbatim(self) -> None:
        document = load_config_document(self.FIXTURE, file_format="json")
        self.assertEqual(dump_config_document(document, file_format="json"), self.FIXTURE)

    def test_unowned_keys_survive_a_mutation(self) -> None:
        document = load_config_document(self.FIXTURE, file_format="json")
        document["c"] = 3
        rendered = dump_config_document(document, file_format="json")
        self.assertEqual(json.loads(rendered), {"b": 2, "a": 1, "c": 3})

    def test_comment_syntax_is_not_accepted_as_json(self) -> None:
        with self.assertRaises(ConfigDocumentError):
            load_config_document('{\n // nope\n "a": 1\n}', file_format="json")


class TomlRoundTripTests(unittest.TestCase):
    """``~/.codex/config.toml`` — MCP, hooks and permissions all write here."""

    FIXTURE = """# Codex config -- hand written, do not reformat
model = "gpt-5"

[mcp_servers.exa]
command = "npx"
args = ["-y", "exa-mcp-server"]  # pinned to npx on purpose
"""

    def test_untouched_document_is_returned_verbatim(self) -> None:
        document = load_config_document(self.FIXTURE, file_format="toml")
        self.assertEqual(dump_config_document(document, file_format="toml"), self.FIXTURE)

    def test_dump_is_idempotent(self) -> None:
        once = dump_config_document(
            load_config_document(self.FIXTURE, file_format="toml"), file_format="toml"
        )
        twice = dump_config_document(
            load_config_document(once, file_format="toml"), file_format="toml"
        )
        self.assertEqual(once, twice)

    def test_comments_survive_an_added_table(self) -> None:
        document = load_config_document(self.FIXTURE, file_format="toml")
        document["mcp_servers"]["context7"] = {"command": "npx", "args": ["-y", "c7"]}
        rendered = dump_config_document(document, file_format="toml")
        self.assertIn("# Codex config -- hand written, do not reformat", rendered)
        self.assertIn("# pinned to npx on purpose", rendered)

    def test_untouched_array_keeps_its_inline_style(self) -> None:
        document = load_config_document(self.FIXTURE, file_format="toml")
        document["model"] = "gpt-5-codex"
        rendered = dump_config_document(document, file_format="toml")
        self.assertIn('args = ["-y", "exa-mcp-server"]', rendered)

    def test_comments_survive_a_removed_table(self) -> None:
        document = load_config_document(self.FIXTURE, file_format="toml")
        del document["mcp_servers"]["exa"]
        rendered = dump_config_document(document, file_format="toml")
        self.assertIn("# Codex config -- hand written, do not reformat", rendered)
        self.assertNotIn("exa-mcp-server", rendered)

    def test_callers_see_plain_containers_not_tomlkit_wrappers(self) -> None:
        """The contract mappers were written against, and quietly depend on.

        ``tomlkit`` converts values on insertion, so a mapper that appends a dict and
        then mutates its own reference writes nothing. Handing out plain containers is
        what keeps those mappers correct.
        """
        document = load_config_document(self.FIXTURE, file_format="toml")
        self.assertIs(type(document["mcp_servers"]), dict)
        self.assertIs(type(document["mcp_servers"]["exa"]["args"]), list)
        self.assertIs(type(document["model"]), str)

    def test_mutation_after_insertion_is_not_lost(self) -> None:
        document = load_config_document(self.FIXTURE, file_format="toml")
        document["hooks"] = {}
        document["hooks"]["PreToolUse"] = []
        group: dict[str, object] = {"matcher": "Bash"}
        document["hooks"]["PreToolUse"].append(group)
        group["hooks"] = [{"id": "my-hook", "command": "echo hello"}]
        rendered = dump_config_document(document, file_format="toml")
        reloaded = load_config_document(rendered, file_format="toml")
        self.assertEqual(
            reloaded["hooks"]["PreToolUse"][0]["hooks"][0]["id"], "my-hook"
        )

    def test_absent_file_produces_a_writable_document(self) -> None:
        document = empty_config_document("toml")
        document["mcp_servers"] = {"exa": {"command": "npx"}}
        rendered = dump_config_document(document, file_format="toml")
        self.assertEqual(
            dict(load_config_document(rendered, file_format="toml")),
            {"mcp_servers": {"exa": {"command": "npx"}}},
        )

    def test_malformed_document_is_reported_not_silently_emptied(self) -> None:
        with self.assertRaises(ConfigDocumentError) as caught:
            load_config_document("model = = 1", file_format="toml")
        self.assertIn("not valid TOML", str(caught.exception))


class YamlRoundTripTests(unittest.TestCase):
    """``~/.hermes/config.yaml`` — already round-tripping; pinned so it stays that way."""

    FIXTURE = """# Hermes config
model: big

mcp_servers:
  exa:
    command: npx  # keep npx
"""

    def test_comments_survive_a_mutation(self) -> None:
        document = load_config_document(self.FIXTURE, file_format="yaml")
        document["mcp_servers"]["context7"] = {"command": "npx"}
        rendered = dump_config_document(document, file_format="yaml")
        self.assertIn("# Hermes config", rendered)
        self.assertIn("# keep npx", rendered)
        self.assertIn("context7", rendered)

    def test_malformed_document_is_reported_not_silently_emptied(self) -> None:
        with self.assertRaises(ConfigDocumentError) as caught:
            load_config_document("a:\n- b\n  c: [", file_format="yaml")
        self.assertIn("not valid YAML", str(caught.exception))


class SubtreeFactoryTests(unittest.TestCase):
    def test_yaml_subtree_is_a_round_trip_container(self) -> None:
        document = load_config_document("# top\na: 1\n", file_format="yaml")
        document["nested"] = new_subtree("yaml")
        document["nested"]["b"] = 2
        rendered = dump_config_document(document, file_format="yaml")
        self.assertIn("# top", rendered)
        self.assertIn("b: 2", rendered)

    def test_json_family_subtrees_are_plain_dicts(self) -> None:
        for file_format in ("json", "jsonc", "toml"):
            with self.subTest(file_format=file_format):
                self.assertIs(type(new_subtree(file_format)), dict)


class ConfigFileFormatParityTests(unittest.TestCase):
    """A declarable ``file_format`` with no round-trip implementation is a trap.

    ``ConfigSubtreeBindingProfile.file_format`` is what a harness author picks; this
    module is what actually reads and writes it. Drift between the two means a catalog
    entry type-checks and then fails at the first mutation.
    """

    def test_every_declarable_format_is_implemented(self) -> None:
        # ``from __future__ import annotations`` makes the raw annotation a string.
        hints = get_type_hints(ConfigSubtreeBindingProfile)
        declared = set(get_args(hints["file_format"]))
        self.assertEqual(declared, set(CONFIG_FILE_FORMATS))

    def test_every_implemented_format_round_trips_an_empty_document(self) -> None:
        for file_format in CONFIG_FILE_FORMATS:
            with self.subTest(file_format=file_format):
                document = empty_config_document(file_format)
                document["a"] = {"b": 1}
                rendered = dump_config_document(document, file_format=file_format)
                reloaded = load_config_document(rendered, file_format=file_format)
                self.assertEqual(reloaded["a"]["b"], 1)


class UnsupportedFormatTests(unittest.TestCase):
    def test_load_rejects_an_unknown_format(self) -> None:
        with self.assertRaises(ConfigDocumentError):
            load_config_document("a = 1", file_format="ini")

    def test_dump_rejects_an_unknown_format(self) -> None:
        with self.assertRaises(ConfigDocumentError):
            dump_config_document({}, file_format="ini")

    def test_empty_rejects_an_unknown_format(self) -> None:
        with self.assertRaises(ConfigDocumentError):
            empty_config_document("ini")


if __name__ == "__main__":
    unittest.main()
