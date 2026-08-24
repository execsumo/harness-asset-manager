#!/usr/bin/env python3
"""Pressure test for Skills Routing and missing sub-route 404 behavior."""

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
    print("Starting Skills Routing Pressure Test (404 vs 405 fix)...")
    print("==========================================================")

    with AppTestHarness() as harness:
        # Seed managed skill 'academic-research'
        slug = "academic-research"
        name = "Academic Research"
        desc = "Research assistant workflow"
        pkg = seed_skill_package(harness.spec.skills_store_root, slug, name, body=f"# {name}\n\n{desc}")
        rev, _ = fingerprint_package(pkg)
        seed_store_manifest(
            harness.spec,
            [
                SkillStoreEntry(
                    package_dir=slug,
                    declared_name=name,
                    source_kind="github",
                    source_locator=f"github:org/{slug}",
                    revision=rev,
                )
            ],
        )
        harness.container.skills_read_models.invalidate()
        print("✓ Seeded skill 'academic-research'")

        # -----------------------------------------------------------------
        # DoD Item 1: GET /api/skills/shared%3Aacademic-research -> 200
        # -----------------------------------------------------------------
        detail_encoded = harness.get_json("/api/skills/shared%3Aacademic-research")
        assert detail_encoded["name"] == "Academic Research"
        assert detail_encoded["skillRef"] == "shared:academic-research"
        print("✓ [DoD 1] GET /api/skills/shared%3Aacademic-research returned 200 OK")

        detail_raw = harness.get_json("/api/skills/shared:academic-research")
        assert detail_raw["name"] == "Academic Research"
        print("✓ [Extra] GET /api/skills/shared:academic-research returned 200 OK")

        # -----------------------------------------------------------------
        # DoD Item 2: GET /api/skills/shared%3Aacademic-research/source-status -> 200
        # -----------------------------------------------------------------
        source_status = harness.get_json("/api/skills/shared%3Aacademic-research/source-status")
        assert isinstance(source_status, dict)
        assert "updateStatus" in source_status
        print("✓ [DoD 2] GET /api/skills/shared%3Aacademic-research/source-status returned 200 OK")

        # -----------------------------------------------------------------
        # DoD Item 3: PUT /api/skills/shared%3Aacademic-research/tags with {"tags": ["test"]} -> 200
        # -----------------------------------------------------------------
        tags_resp = harness.put_json(
            "/api/skills/shared%3Aacademic-research/tags",
            {"tags": ["test"]},
        )
        assert tags_resp == {"tags": ["test"]}
        print("✓ [DoD 3] PUT /api/skills/shared%3Aacademic-research/tags returned 200 with {'tags': ['test']}")

        # -----------------------------------------------------------------
        # DoD Item 4: PUT /api/skills/shared%3Aacademic-research/nonexistent-subroute -> 404
        # -----------------------------------------------------------------
        put_404 = harness.put_json(
            "/api/skills/shared%3Aacademic-research/nonexistent-subroute",
            {"tags": ["test"]},
            expected_status=404,
        )
        assert put_404.get("code") == "not_found"
        print("✓ [DoD 4] PUT /api/skills/shared%3Aacademic-research/nonexistent-subroute returned 404 Not Found")

        # -----------------------------------------------------------------
        # Comprehensive verb sweep for unknown sub-routes
        # -----------------------------------------------------------------
        for verb, caller in [
            ("GET", lambda p: harness.get_json(p, expected_status=404)),
            ("POST", lambda p: harness.post_json(p, {}, expected_status=404)),
            ("PUT", lambda p: harness.put_json(p, {}, expected_status=404)),
            ("DELETE", lambda p: harness.delete_json(p, expected_status=404)),
        ]:
            resp = caller("/api/skills/shared%3Aacademic-research/another-unknown-subroute")
            assert resp.get("code") == "not_found", f"Expected code 'not_found' for {verb}, got {resp}"
            print(f"✓ {verb} /api/skills/shared%3Aacademic-research/another-unknown-subroute returned 404")

        # -----------------------------------------------------------------
        # Root API unknown endpoints
        # -----------------------------------------------------------------
        for verb, caller in [
            ("GET", lambda p: harness.get_json(p, expected_status=404)),
            ("POST", lambda p: harness.post_json(p, {}, expected_status=404)),
            ("PUT", lambda p: harness.put_json(p, {}, expected_status=404)),
            ("DELETE", lambda p: harness.delete_json(p, expected_status=404)),
        ]:
            resp = caller("/api/unknown-service/endpoint")
            assert resp.get("code") == "not_found"
            assert "unknown api path" in resp.get("error", "")
            print(f"✓ {verb} /api/unknown-service/endpoint returned 404 with JSON envelope")

    print("==========================================================")
    print("✓ ALL ROUTING PRESSURE TESTS PASSED 100% CLEANLY")
    print("==========================================================")


if __name__ == "__main__":
    run_pressure_test()
