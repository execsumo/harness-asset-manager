from __future__ import annotations

import concurrent.futures
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.asset_tags import (
    MAX_TAG_LENGTH,
    STARRED_TAG,
    AssetTagService,
    AssetTagStore,
    normalize_and_dedupe_tags,
    normalize_tag,
    sort_tags,
)
from harness_asset_manager.errors import MutationError


class AssetTagStoreTests(unittest.TestCase):
    def test_total_read_on_missing_file(self) -> None:
        with TemporaryDirectory() as tmp:
            store = AssetTagStore(Path(tmp) / "asset-tags.json")
            self.assertEqual(store.load(), {})
            self.assertEqual(store.get_tags("skills:unknown"), [])

    def test_total_read_on_corrupt_json(self) -> None:
        with TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "asset-tags.json"
            file_path.write_text("{ this is malformed json truncated...", encoding="utf-8")
            store = AssetTagStore(file_path)
            self.assertEqual(store.load(), {})
            self.assertEqual(store.get_tags("skills:test"), [])

    def test_total_read_on_invalid_schema(self) -> None:
        with TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "asset-tags.json"
            # Not a dict
            file_path.write_text("[\"not\", \"a\", \"dict\"]", encoding="utf-8")
            store = AssetTagStore(file_path)
            self.assertEqual(store.load(), {})

            # tags is not a dict
            file_path.write_text("{\"version\": 1, \"tags\": \"not-a-dict\"}", encoding="utf-8")
            self.assertEqual(store.load(), {})

            # invalid entries ignored safely
            file_path.write_text(
                json.dumps({
                    "version": 1,
                    "tags": {
                        "skills:good": ["starred", "core"],
                        "skills:bad-val": "not-a-list",
                        123: ["invalid-key"],
                    },
                }),
                encoding="utf-8",
            )
            self.assertEqual(store.load(), {"skills:good": ["starred", "core"]})

    def test_round_trip_preservation_of_unknown_keys(self) -> None:
        with TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "asset-tags.json"
            initial_data = {
                "version": 1,
                "customTopLevelField": "preserve-this-value",
                "anotherCustomField": {"nested": True},
                "tags": {
                    "agents:auditor": ["review", "security"],
                    "slash_commands:deploy": ["ops"],
                    "skills:existing": ["initial"],
                },
            }
            file_path.write_text(json.dumps(initial_data, indent=2), encoding="utf-8")

            store = AssetTagStore(file_path)
            # Update one skill
            store.set_tags("skills:academic-research", ["starred", "research"])

            # Read raw JSON back from disk
            saved = json.loads(file_path.read_text(encoding="utf-8"))
            self.assertEqual(saved.get("customTopLevelField"), "preserve-this-value")
            self.assertEqual(saved.get("anotherCustomField"), {"nested": True})
            self.assertEqual(saved.get("version"), 1)
            self.assertEqual(saved["tags"]["agents:auditor"], ["review", "security"])
            self.assertEqual(saved["tags"]["slash_commands:deploy"], ["ops"])
            self.assertEqual(saved["tags"]["skills:existing"], ["initial"])
            self.assertEqual(saved["tags"]["skills:academic-research"], ["starred", "research"])

    def test_clear_tags_when_empty_list(self) -> None:
        with TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "asset-tags.json"
            store = AssetTagStore(file_path)
            store.set_tags("skills:temp", ["tag1", "tag2"])
            self.assertEqual(store.get_tags("skills:temp"), ["tag1", "tag2"])

            # Clear tags
            store.set_tags("skills:temp", [])
            self.assertEqual(store.get_tags("skills:temp"), [])
            saved = json.loads(file_path.read_text(encoding="utf-8"))
            self.assertNotIn("skills:temp", saved.get("tags", {}))

    def test_concurrent_write_atomicity(self) -> None:
        with TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "asset-tags.json"
            store = AssetTagStore(file_path)

            def write_tag(i: int) -> None:
                store.set_tags(f"skills:skill-{i}", [f"tag-{i}", "concurrent"])

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(write_tag, i) for i in range(50)]
                for f in concurrent.futures.as_completed(futures):
                    f.result()

            loaded = store.load()
            self.assertEqual(len(loaded), 50)
            for i in range(50):
                self.assertEqual(loaded[f"skills:skill-{i}"], [f"tag-{i}", "concurrent"])


class AssetTagServiceTests(unittest.TestCase):
    def test_normalize_tag_rules(self) -> None:
        # Valid tag trimmed
        self.assertEqual(normalize_tag("  devops  "), "devops")
        self.assertEqual(normalize_tag("core"), "core")

        # Empty string / whitespace only rejected
        with self.assertRaises(MutationError) as ctx:
            normalize_tag("")
        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(ctx.exception.code, "invalid_tag")

        with self.assertRaises(MutationError) as ctx:
            normalize_tag("   ")
        self.assertEqual(ctx.exception.status, 400)

        # Overly long tag rejected
        with self.assertRaises(MutationError) as ctx:
            normalize_tag("a" * (MAX_TAG_LENGTH + 1))
        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(ctx.exception.code, "invalid_tag")

        # Non-string rejected
        with self.assertRaises(MutationError) as ctx:
            normalize_tag(123)  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.status, 400)

    def test_normalize_and_dedupe_preserves_first_seen_display_form(self) -> None:
        raw_tags = ["DevOps", "devops", "Core", "CORE", "devops", "starred", "Starred"]
        deduped = normalize_and_dedupe_tags(raw_tags)
        self.assertEqual(deduped, ["DevOps", "Core", "starred"])

    def test_sort_tags_pins_starred_first(self) -> None:
        tags = ["zebra", "core", "starred", "alpha", "DevOps"]
        sorted_tags = sort_tags(tags)
        self.assertEqual(sorted_tags, ["starred", "alpha", "core", "DevOps", "zebra"])

        # Case-insensitive starred check
        tags2 = ["zebra", "Starred", "alpha"]
        self.assertEqual(sort_tags(tags2), ["Starred", "alpha", "zebra"])

        # No starred tag
        tags3 = ["zebra", "alpha", "beta"]
        self.assertEqual(sort_tags(tags3), ["alpha", "beta", "zebra"])

    def test_service_get_and_set_tags(self) -> None:
        with TemporaryDirectory() as tmp:
            store = AssetTagStore(Path(tmp) / "asset-tags.json")
            service = AssetTagService(store)

            # Initially empty
            self.assertEqual(service.get_tags("skills", "academic-research"), [])

            # Set tags with mixed cases, duplicates, whitespace
            result = service.set_tags(
                "skills",
                "academic-research",
                ["  devops  ", "DevOps", " starred ", "Core "],
            )
            # Should be normalized, deduped, and sorted with starred first
            self.assertEqual(result, ["starred", "Core", "devops"])
            self.assertEqual(service.get_tags("skills", "academic-research"), ["starred", "Core", "devops"])

            # Add another skill
            service.set_tags("skills", "apple-notes", ["productivity", "notes"])

            # get_tags_for_family
            family_tags = service.get_tags_for_family("skills")
            self.assertEqual(
                family_tags,
                {
                    "academic-research": ["starred", "Core", "devops"],
                    "apple-notes": ["notes", "productivity"],
                },
            )
