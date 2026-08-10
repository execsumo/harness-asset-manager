from __future__ import annotations

from pathlib import Path
from typing import Literal, Mapping

from harness_asset_manager.settings_file import (
    load_settings_document,
    update_settings_document,
)

AutoAdoptFamily = Literal["agents", "skills", "slash_commands", "mcp", "hooks", "permissions"]
AUTO_ADOPT_FAMILIES = tuple(("agents", "skills", "slash_commands", "mcp", "hooks", "permissions"))

# Agents default **on**: every repair it takes is provable. The remaining families
# default **off** because adoption changes ownership of user-created files or
# config entries. They can be enabled independently once the user has reviewed the
# family-specific safety rules.
DEFAULTS: Mapping[str, bool] = {
    "agents": True,
    "skills": False,
    "slash_commands": False,
    "mcp": False,
    "hooks": False,
    "permissions": False,
}
DEFAULT_HARNESSES: Mapping[str, tuple[str, ...]] = {
    family: () for family in AUTO_ADOPT_FAMILIES
}
IMPLEMENTED: set[str] = set(DEFAULTS)

SETTINGS_KEY = "autoAdopt"
HARNESS_DEFAULTS_KEY = "autoAdoptHarnesses"


class AutoAdoptStore:
    """Whether Harness Asset Manager may repair drifted bindings without being asked.

    Read **per call**, never cached: turning this off in Settings has to stop the next
    reconcile, not the next restart. It is the kill switch for every automatic action,
    so a missing or unreadable settings file must fall back to the declared defaults
    rather than to "whatever was in memory".
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def preferences(self) -> dict[str, bool]:
        stored = load_settings_document(self.path).get(SETTINGS_KEY)
        values = dict(DEFAULTS)
        if isinstance(stored, dict):
            for family, value in stored.items():
                if family in values and isinstance(value, bool):
                    values[family] = value
        return values

    def is_enabled(self, family: AutoAdoptFamily) -> bool:
        return self.preferences().get(family, DEFAULTS.get(family, False))

    def default_harnesses(self) -> dict[str, tuple[str, ...]]:
        stored = load_settings_document(self.path).get(HARNESS_DEFAULTS_KEY)
        values = {family: tuple(harnesses) for family, harnesses in DEFAULT_HARNESSES.items()}
        if isinstance(stored, dict):
            for family in DEFAULT_HARNESSES:
                raw = stored.get(family)
                if isinstance(raw, list):
                    values[family] = tuple(
                        dict.fromkeys(item for item in raw if isinstance(item, str) and item)
                    )
        return values

    def set_default_harnesses(self, family: str, harnesses: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
        if family not in DEFAULT_HARNESSES:
            raise KeyError(family)
        values = self.default_harnesses()
        values[family] = tuple(dict.fromkeys(harnesses))
        update_settings_document(
            self.path,
            lambda document: document.update(
                {HARNESS_DEFAULTS_KEY: {key: list(items) for key, items in values.items()}}
            ),
        )
        return values

    def set_enabled(self, family: str, enabled: bool) -> dict[str, bool]:
        if family not in DEFAULTS:
            raise KeyError(family)
        if family not in IMPLEMENTED and enabled:
            raise ValueError(f"auto-adopt for '{family}' is not implemented yet")
        values = self.preferences()
        values[family] = enabled
        update_settings_document(
            self.path, lambda document: document.update({SETTINGS_KEY: dict(values)})
        )
        return values


__all__ = [
    "AUTO_ADOPT_FAMILIES",
    "DEFAULTS",
    "DEFAULT_HARNESSES",
    "HARNESS_DEFAULTS_KEY",
    "IMPLEMENTED",
    "SETTINGS_KEY",
    "AutoAdoptFamily",
    "AutoAdoptStore",
]
