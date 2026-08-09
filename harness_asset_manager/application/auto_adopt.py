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
    """Record an automatic ownership change (new-file adoption) in the Activity journal."""

    _append(
        journal,
        family=family,
        operation="auto_adopt",
        parameters={"ref": ref, "automatic": True},
        target_paths=target_paths,
        outcome=outcome,
        error_type=error_type,
    )


def record_auto_repair(
    journal: MutationAuditJournal,
    *,
    family: str,
    ref: str,
    action: str,
    target_paths: Iterable[str] = (),
    outcome: str = "succeeded",
    error_type: str | None = None,
) -> None:
    """Record an automatic repair of an already-managed binding's drift.

    Distinct from ``record_auto_adopt``: adoption changes *ownership* of something
    new, while repair fixes a binding Harness Asset Manager already owned. Kept as
    a separate operation name so the Activity view can tell the two apart.
    """

    _append(
        journal,
        family=family,
        operation="auto_repair",
        parameters={"ref": ref, "action": action, "automatic": True},
        target_paths=target_paths,
        outcome=outcome,
        error_type=error_type,
    )


def _append(
    journal: MutationAuditJournal,
    *,
    family: str,
    operation: str,
    parameters: dict[str, object],
    target_paths: Iterable[str],
    outcome: str,
    error_type: str | None,
) -> None:
    event: dict[str, object] = {
        "family": family,
        "operation": operation,
        "parameters": parameters,
        "target_paths": tuple(target_paths),
        "outcome": outcome,
    }
    if error_type is not None:
        event["error_type"] = error_type
    try:
        journal.append(**event)  # type: ignore[arg-type]
    except OSError:
        # The automatic action has already happened; a full audit disk must not
        # turn it into a retryable failure or claim that nothing was done.
        return


__all__ = ["record_auto_adopt", "record_auto_repair"]
