from __future__ import annotations

from typing import Literal

# What an unmanaged or drifted file at a binding path actually is. Derived, never
# stored — the caller's ledger/sync-state records evidence, this names the
# conclusion drawn from it.
DriftKind = Literal[
    "collision",  # no usable baseline: a genuine name clash, indistinguishable from today's case
    "clobber_clean",  # the binding was replaced by an identical copy; no content decision
    "clobber_one_sided",  # replaced and edited, but provably the only edit that exists
    "two_sided_conflict",  # store and harness both moved; nobody can pick for the user
]


def classify_drift(
    *,
    baseline_sha256: str | None,
    harness_sha256: str | None,
    store_sha256: str | None,
) -> DriftKind:
    """The decision table of ``plan-auto-adoption.md`` §4, as a pure function.

    Family-agnostic: it only ever looks at three hashes — what we recorded when we
    last made the binding (``baseline_sha256``), what the harness-owned copy holds
    now (``harness_sha256``), and what the store would produce now (``store_sha256``).
    Any family whose binding shape is "Harness Asset Manager writes a real file a
    harness can independently overwrite" can reuse this without adopting the
    agents-specific ``AgentBindingRecord`` shape — the agents ledger is a thin
    wrapper over this, and slash commands call it directly.

    Deliberately has no filesystem access and takes no action — naming what
    happened is separate from deciding whether to act on it, which is a caller
    concern that also knows about user settings and destructive operations.
    """
    if baseline_sha256 is None or harness_sha256 is None or store_sha256 is None:
        # No usable baseline, or an unreadable side: we cannot tell a clobbered
        # binding from a name collision, so we must not claim we can.
        return "collision"
    if harness_sha256 == store_sha256:
        return "clobber_clean"
    if store_sha256 == baseline_sha256:
        # The store has not moved since we last wrote it, so the harness copy is
        # the only edit in existence. Nothing can be discarded by preferring it.
        return "clobber_one_sided"
    return "two_sided_conflict"


__all__ = ["DriftKind", "classify_drift"]
