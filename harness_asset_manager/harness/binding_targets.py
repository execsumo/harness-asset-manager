from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BindingTarget:
    """A harness family and optional narrower target within that family."""

    harness: str
    scope: str | None = None

    @classmethod
    def parse(cls, value: str) -> "BindingTarget":
        """Parse permissively so malformed persisted intent cannot break inventory.

        ``:scope`` drops its empty harness part and becomes the usable unscoped
        harness ``scope``; ``hermes:`` treats the empty scope as harness-wide.
        """
        harness, separator, scope = value.partition(":")
        if not harness:
            harness, scope = scope, ""
        return cls(harness, scope if separator and scope else None)

    def __str__(self) -> str:
        return self.harness if self.scope is None else f"{self.harness}:{self.scope}"


def harness_of(value: str) -> str:
    """Return the family portion of a persisted binding target."""
    return BindingTarget.parse(value).harness


__all__ = ["BindingTarget", "harness_of"]
