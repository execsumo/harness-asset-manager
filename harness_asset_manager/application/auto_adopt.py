from __future__ import annotations

from collections.abc import Iterable

from .mutation_audit import MutationAuditJournal


def record_auto_adopt(
    journal: MutationAuditJournal,
    *,
    family: str,
    ref: str,
    target_paths: Iterable[str] = (),
    outcome: str = "succeeded",
    error_type: str | None = None,
) -> None:
    """Record an automatic ownership change in the shared Activity journal."""

    event: dict[str, object] = {
        "family": family,
        "operation": "auto_adopt",
        "parameters": {"ref": ref, "automatic": True},
        "target_paths": tuple(target_paths),
        "outcome": outcome,
    }
    if error_type is not None:
        event["error_type"] = error_type
    try:
        journal.append(**event)  # type: ignore[arg-type]
    except OSError:
        # Adoption has already happened; a full audit disk must not turn it into a
        # retryable failure or claim that content was not adopted.
        return


__all__ = ["record_auto_adopt"]
