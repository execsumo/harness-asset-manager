from __future__ import annotations

from pathlib import Path
import pytest

from harness_asset_manager.application.config_snapshots import (
    ConfigSnapshotService,
    HarnessConfigTarget,
    redact_secrets,
)
from harness_asset_manager.paths import AppPaths


def test_redact_secrets():
    raw_content = '{"api_key": "sk-proj-123456789012345678901234", "theme": "dark"}'
    redacted = redact_secrets(raw_content)
    assert "sk-proj-123456789012345678901234" not in redacted
    assert "[REDACTED]" in redacted
    assert '"theme": "dark"' in redacted


def test_capture_snapshot_and_deduplication(tmp_path: Path):
    app_paths = AppPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
        skills_store_root=tmp_path / "data" / "skills",
        skills_store_manifest=tmp_path / "data" / "skills-manifest.json",
        agents_root=tmp_path / "data" / "agents",
        marketplace_cache_root=tmp_path / "data" / "marketplace",
        mcp_store_manifest=tmp_path / "data" / "mcp" / "manifest.json",
        hooks_store_manifest=tmp_path / "data" / "hooks" / "manifest.json",
        permissions_store_manifest=tmp_path / "data" / "permissions" / "manifest.json",
        slash_command_store_root=tmp_path / "data" / "slash-commands",
        slash_command_commands_dir=tmp_path / "data" / "slash-commands" / "commands",
        slash_command_sync_state_path=tmp_path / "data" / "slash-commands" / "sync-state.json",
        settings_path=tmp_path / "config" / "settings.json",
        runtime_state_path=tmp_path / "state" / "runtime.json",
        server_log_path=tmp_path / "state" / "server.log",
        configs_dir=tmp_path / "data" / "configs",
    )

    service = ConfigSnapshotService(app_paths)

    # Create mock native harness config
    claude_settings = tmp_path / "mock_claude" / "settings.json"
    claude_settings.parent.mkdir(parents=True, exist_ok=True)
    claude_settings.write_text('{"theme": "dark"}', encoding="utf-8")

    target = HarnessConfigTarget(
        harness="claude",
        label="Claude",
        config_name="settings.json",
        path=claude_settings,
        file_format="json",
    )

    # First capture
    snapshot1 = service.capture_snapshot(target, trigger="manual")
    assert snapshot1 is not None
    assert snapshot1.harness == "claude"
    assert snapshot1.config_name == "settings.json"
    assert snapshot1.trigger == "manual"
    assert snapshot1.snapshot_path.is_file()

    # Canonical baseline file should also be created
    canonical_file = app_paths.configs_dir / "claude" / "settings.json"
    assert canonical_file.is_file()
    assert canonical_file.read_text(encoding="utf-8") == '{"theme": "dark"}'

    # Second capture without changes (deduplication check)
    snapshot2 = service.capture_snapshot(target, trigger="external")
    assert snapshot2 is None  # Skipped because SHA-256 is unchanged

    # Modify native config file
    claude_settings.write_text('{"theme": "light"}', encoding="utf-8")

    # Third capture after modification
    snapshot3 = service.capture_snapshot(target, trigger="external")
    assert snapshot3 is not None
    assert snapshot3.sha256 != snapshot1.sha256

    # Verify listing snapshots
    all_snapshots = service.list_snapshots(harness="claude")
    assert len(all_snapshots) == 2
