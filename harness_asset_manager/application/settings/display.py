from __future__ import annotations

from pathlib import Path

from harness_asset_manager.settings_file import (
    load_settings_document,
    update_settings_document,
)

DISPLAY_KEY = "display"
SHOW_SKILL_AGENT_TAGS = "showSkillAgentTags"
DISPLAY_DEFAULTS: dict[str, bool] = {SHOW_SKILL_AGENT_TAGS: True}


class DisplayPreferencesStore:
    """UI display preferences persisted in the shared settings file.

    Read per call so a change in Settings applies on the next request, and a
    missing or malformed value falls back to the declared default.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def preferences(self) -> dict[str, bool]:
        stored = load_settings_document(self.path).get(DISPLAY_KEY)
        values = dict(DISPLAY_DEFAULTS)
        if isinstance(stored, dict):
            for key in DISPLAY_DEFAULTS:
                raw = stored.get(key)
                if isinstance(raw, bool):
                    values[key] = raw
        return values

    def set_preference(self, key: str, value: bool) -> dict[str, bool]:
        if key not in DISPLAY_DEFAULTS:
            raise KeyError(key)
        values = self.preferences()
        values[key] = value
        update_settings_document(self.path, lambda document: document.update({DISPLAY_KEY: dict(values)}))
        return values


__all__ = ["DISPLAY_DEFAULTS", "DISPLAY_KEY", "SHOW_SKILL_AGENT_TAGS", "DisplayPreferencesStore"]
