#!/usr/bin/env python3
"""Pressure test for Asset Tags (Phase 1) against an isolated state store."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import seed_skill_package, seed_store_manifest
from harness_asset_manager.application.skills.manifest import SkillStoreEntry
from harness_asset_manager.application.skills.package import fingerprint_package


def run_pressure_test() -> None:
    print("==========================================================")
    print("Starting Asset Tags Pressure Test against isolated store...")
    print("==========================================================")

    with AppTestHarness() as harness:
        # 1. Seed multiple skills
        skills_to_seed = [
            ("academic-research", "Academic Research", "Research assistant"),
            ("apple-notes", "Apple Notes", "Notes integration"),
            ("doc-reviewer", "Doc Reviewer", "Document reviews"),
            ("code-analyzer", "Code Analyzer", "Static analysis"),
            ("unmanaged-skill", "Unmanaged Skill", "Found on system"),
        ]

        manifest_entries: list[SkillStoreEntry] = []
        for slug, name, desc in skills_to_seed[:-1]:
            pkg = seed_skill_package(harness.spec.skills_store_root, slug, name, body=f"# {name}\n\n{desc}")
            rev, _ = fingerprint_package(pkg)
            manifest_entries.append(
                SkillStoreEntry(
                    package_dir=slug,
                    declared_name=name,
                    source_kind="github",
                    source_locator=f"github:org/{slug}",
                    revision=rev,
                )
            )
        seed_store_manifest(harness.spec, manifest_entries)

        # Seed unmanaged skill on claude
        seed_skill_package(harness.spec.claude_root, "unmanaged-skill", "Unmanaged Skill", body="Unmanaged body")

        # Invalidate read model
        harness.container.skills_read_models.invalidate()

        print("✓ Seeded 4 managed skills and 1 unmanaged skill")

        # 2. Initial state verification
        page = harness.get_json("/api/skills")
        assert len(page["rows"]) == 5, f"Expected 5 skills, got {len(page['rows'])}"
        for row in page["rows"]:
            assert row["tags"] == [], f"Expected empty tags initially for {row['skillRef']}"
        print("✓ Initial state: all skills have empty tags")

        # 3. Setting tags individually
        resp1 = harness.put_json(
            "/api/skills/shared:academic-research/tags",
            {"tags": ["starred", "research", "core", "Research"]},  # test dedupe
        )
        assert resp1["tags"] == ["starred", "core", "research"], f"Tags normalization failed: {resp1['tags']}"

        resp2 = harness.put_json(
            "/api/skills/shared:apple-notes/tags",
            {"tags": ["devops", "productivity"]},
        )
        assert resp2["tags"] == ["devops", "productivity"]

        resp3 = harness.put_json(
            "/api/skills/shared:doc-reviewer/tags",
            {"tags": ["research", "review"]},
        )
        assert resp3["tags"] == ["research", "review"]

        resp4 = harness.put_json(
            "/api/skills/shared:code-analyzer/tags",
            {"tags": ["core", "devops"]},
        )
        assert resp4["tags"] == ["core", "devops"]
        print("✓ PUT /api/skills/{ref}/tags normalized and persisted tags for all managed skills")

        # 4. Verify tags ride along on GET /api/skills list and detail
        page_after = harness.get_json("/api/skills")
        rows_by_ref = {r["skillRef"]: r for r in page_after["rows"]}
        assert rows_by_ref["shared:academic-research"]["tags"] == ["starred", "core", "research"]
        assert rows_by_ref["shared:apple-notes"]["tags"] == ["devops", "productivity"]
        assert rows_by_ref["shared:doc-reviewer"]["tags"] == ["research", "review"]
        assert rows_by_ref["shared:code-analyzer"]["tags"] == ["core", "devops"]

        detail_ar = harness.get_json("/api/skills/shared:academic-research")
        assert detail_ar["tags"] == ["starred", "core", "research"]
        print("✓ GET list and GET detail responses include populated tags")

        # 5. Enable some skills to test composite filtering
        harness.post_json("/api/skills/shared:apple-notes/enable", {"harness": "claude"})
        harness.post_json("/api/skills/shared:code-analyzer/enable", {"harness": "claude"})

        # 6. Bulk-star simulation
        for ref in ["shared:apple-notes", "shared:doc-reviewer"]:
            cur_tags = rows_by_ref[ref]["tags"]
            next_tags = ["starred", *cur_tags]
            harness.put_json(f"/api/skills/{ref}/tags", {"tags": next_tags})

        detail_an = harness.get_json("/api/skills/shared:apple-notes")
        assert detail_an["tags"] == ["starred", "devops", "productivity"]

        detail_dr = harness.get_json("/api/skills/shared:doc-reviewer")
        assert detail_dr["tags"] == ["starred", "research", "review"]
        print("✓ Bulk star simulation successfully updated multiple skills with starred pinned first")

        # 7. Unstar toggle simulation
        cur_ar_tags = harness.get_json("/api/skills/shared:academic-research")["tags"]
        unstarred = [t for t in cur_ar_tags if t != "starred"]
        harness.put_json("/api/skills/shared:academic-research/tags", {"tags": unstarred})
        detail_ar_unstarred = harness.get_json("/api/skills/shared:academic-research")
        assert detail_ar_unstarred["tags"] == ["core", "research"]
        print("✓ Star toggle removal successfully removed 'starred' while preserving other tags")

        # 8. Error handling validation
        err_empty = harness.put_json(
            "/api/skills/shared:academic-research/tags",
            {"tags": [""]},
            expected_status=400,
        )
        assert err_empty["code"] == "invalid_tag"

        err_long = harness.put_json(
            "/api/skills/shared:academic-research/tags",
            {"tags": ["x" * 65]},
            expected_status=400,
        )
        assert err_long["code"] == "invalid_tag"

        unmanaged_row = next(r for r in page["rows"] if r["displayStatus"] == "Unmanaged")
        err_unmanaged = harness.put_json(
            f"/api/skills/{unmanaged_row['skillRef']}/tags",
            {"tags": ["test"]},
            expected_status=400,
        )
        assert "managed" in err_unmanaged["error"].lower()
        print("✓ Validation rejected empty string, oversized tags, and unmanaged skills with HTTP 400 and proper envelope")

        # 9. Verify store on disk
        tags_file = harness.container.paths.asset_tags_path
        assert tags_file.exists(), "data/asset-tags.json must exist"
        raw_content = tags_file.read_text(encoding="utf-8")
        parsed = json.loads(raw_content)
        assert parsed["version"] == 1
        assert "skills:shared:apple-notes" in parsed["tags"]
        assert "skills:shared:doc-reviewer" in parsed["tags"]
        assert "skills:shared:code-analyzer" in parsed["tags"]
        assert "skills:shared:academic-research" in parsed["tags"]
        # Invariant: No absolute file paths stored in asset-tags.json
        assert "/home" not in raw_content
        assert "/tmp" not in raw_content
        print("✓ Store on disk verified: Schema v1 valid, no absolute paths leaked")

    print("==========================================================")
    print("✓ PRESSURE TEST PASSED 100% CLEANLY")
    print("==========================================================")


if __name__ == "__main__":
    run_pressure_test()
