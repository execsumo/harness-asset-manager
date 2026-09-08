from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Action = Literal["link", "skip", "conflict"]


@dataclass(frozen=True)
class BootstrapAction:
    family: str  # "skills" | "agents" | "slash_commands"
    ref: str  # skill_ref / agent slug / command name
    display_name: str
    harness: str
    action: Action
    # Where the binding would land on THIS device. ``None`` when the device cannot
    # place it at all — a target scoped to a Hermes profile that does not exist here
    # has no path until that profile is created, and inventing a plausible one would
    # be worse than showing none.
    target: Path | None
    binding_target: str | None = None
    reason: str | None = None  # machine-readable skip/conflict code
    detail: str | None = None  # human sentence for the UI

    @property
    def target_display(self) -> str:
        """Path for humans and the API; empty string when there is no path on this device."""
        return "" if self.target is None else str(self.target)

    def to_dict(self) -> dict[str, object]:
        return {
            "family": self.family,
            "ref": self.ref,
            "displayName": self.display_name,
            "display_name": self.display_name,
            "harness": self.harness,
            "bindingTarget": self.binding_target or self.harness,
            "action": self.action,
            "target": self.target_display,
            "targetPath": self.target_display,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class BootstrapPlan:
    actions: tuple[BootstrapAction, ...]

    @property
    def linkable(self) -> tuple[BootstrapAction, ...]:
        return tuple(action for action in self.actions if action.action == "link")

    @property
    def conflicts(self) -> tuple[BootstrapAction, ...]:
        return tuple(action for action in self.actions if action.action == "conflict")

    @property
    def skipped(self) -> tuple[BootstrapAction, ...]:
        return tuple(action for action in self.actions if action.action == "skip")

    def to_dict(self) -> dict[str, object]:
        return {
            "actions": [action.to_dict() for action in self.actions],
            "linkableCount": len(self.linkable),
            "conflictCount": len(self.conflicts),
            "skippedCount": len(self.skipped),
            "totalCount": len(self.actions),
        }


@dataclass(frozen=True)
class BootstrapApplyResult:
    family: str
    ref: str
    harness: str
    status: Literal["applied", "failed", "skipped"]
    target: str
    binding_target: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "family": self.family,
            "ref": self.ref,
            "harness": self.harness,
            "bindingTarget": self.binding_target or self.harness,
            "status": self.status,
            "target": self.target,
            "error": self.error,
        }


__all__ = [
    "Action",
    "BootstrapAction",
    "BootstrapApplyResult",
    "BootstrapPlan",
]
