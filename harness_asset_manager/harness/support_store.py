from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness_asset_manager.settings_file import (
    load_settings_document,
    update_settings_document,
)


@dataclass(frozen=True)
class HarnessSupportPreferences:
    disabled_harnesses: tuple[str, ...] = ()

    def is_enabled(self, harness: str) -> bool:
        return harness not in self.disabled_harnesses

class HarnessSupportStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> HarnessSupportPreferences:
        payload = load_settings_document(self.path)
        disabled = payload.get("disabledHarnesses", [])
        if not isinstance(disabled, list):
            return HarnessSupportPreferences()
        values = tuple(sorted({item for item in disabled if isinstance(item, str) and item}))
        return HarnessSupportPreferences(disabled_harnesses=values)

    def set_enabled(self, harness: str, enabled: bool) -> HarnessSupportPreferences:
        current = set(self.load().disabled_harnesses)
        if enabled:
            current.discard(harness)
        else:
            current.add(harness)
        next_preferences = HarnessSupportPreferences(disabled_harnesses=tuple(sorted(current)))
        # Merge, rather than serialising this store's view of the file: settings.json
        # is shared, and rewriting it from one store's keys deletes every other
        # store's. The read-modify-write happens under the shared settings lock.
        update_settings_document(
            self.path,
            lambda document: document.update(
                {"disabledHarnesses": list(next_preferences.disabled_harnesses)}
            ),
        )
        return next_preferences

    def enabled_harnesses(self, supported_harnesses: tuple[str, ...]) -> tuple[str, ...]:
        preferences = self.load()
        return tuple(harness for harness in supported_harnesses if preferences.is_enabled(harness))
