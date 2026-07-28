from __future__ import annotations

from pathlib import Path
from typing import Literal, Mapping

from harness_asset_manager.settings_file import (
    load_settings_document,
    update_settings_document,
)

AutoAdoptFamily = Literal["agents", "skills"]

# Agents default **on**: every action it can take is provable — the harness copy is
# either identical to the store or the only edit in existence (see the decision table
# in plan-auto-adoption.md §4). Skills default **off**: adopting a local skill
# directory means `shutil.rmtree` on a real directory of the user's, which is a
# different class of operation and is not implemented here yet.
DEFAULTS: Mapping[str, bool] = {"agents": True, "skills": False}
IMPLEMENTED: set[str] = {"agents"}

SETTINGS_KEY = "autoAdopt"


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


__all__ = ["DEFAULTS", "IMPLEMENTED", "SETTINGS_KEY", "AutoAdoptFamily", "AutoAdoptStore"]
