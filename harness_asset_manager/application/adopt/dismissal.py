from __future__ import annotations

import json
import time
from pathlib import Path

from harness_asset_manager.atomic_files import atomic_write_text


class AdoptionDismissalStore:
    """Device-local dismissal persistence for the adoption banner.

    Stored under xdg_state_home (state_dir), NEVER in the synced store data_dir.
    A dismissal that traveled with the store would suppress the banner on every
    future device, defeating the adoption flow on new devices.
    """

    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / "adopt_dismissal.json"

    def is_dismissed(self) -> bool:
        if not self.path.is_file():
            return False
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return bool(payload.get("dismissed", False))
        except (OSError, ValueError):
            return False
        return False

    def dismiss(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "dismissed": True,
            "dismissedAt": time.time(),
        }
        atomic_write_text(self.path, json.dumps(payload, indent=2) + "\n")

    def reset(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "dismissed": False,
        }
        atomic_write_text(self.path, json.dumps(payload, indent=2) + "\n")


__all__ = ["AdoptionDismissalStore"]
