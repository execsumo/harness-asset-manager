from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from harness_asset_manager.application.agents.adapters import (
    _has_marker,
    render_codex_agent,
)
from harness_asset_manager.application.mutation_audit import MutationAuditJournal
from harness_asset_manager.application.slash_commands.codecs import render_slash_command
from harness_asset_manager.harness.contracts import CommandFileBindingProfile
from harness_asset_manager.hashing import hash_file, hash_text

from .models import AdoptionAction, AdoptionApplyResult

if TYPE_CHECKING:
    from harness_asset_manager.application import BackendContainer


def _safe_hash(path: Path) -> str | None:
    try:
        if path.is_file():
            return hash_file(path)
    except (OSError, ValueError):
        pass
    return None


def _safe_hash_text(payload: str) -> str | None:
    try:
        return hash_text(payload)
    except Exception:
        return None


def record_adopt(
    journal: MutationAuditJournal,
    *,
    family: str,
    ref: str,
    harness: str,
    target_paths: Iterable[str] = (),
    outcome: str = "succeeded",
    error_type: str | None = None,
) -> None:
    """Record an adopted binding in the MutationAuditJournal, mirroring record_auto_adopt."""
    event: dict[str, object] = {
        "family": family,
        "operation": "adopt",
        "parameters": {"ref": ref, "harness": harness},
        "target_paths": tuple(target_paths),
        "outcome": outcome,
    }
    if error_type is not None:
        event["error_type"] = error_type
    try:
        journal.append(**event)  # type: ignore[arg-type]
    except OSError:
        return


class AdoptionApplier:
    """Applies reviewed adoption actions to create local bindings.

    Takes an explicit list of actions, re-checks each target immediately before acting,
    aggregates failures without aborting the run, applies conflict actions only when
    explicitly permitted, invalidates read models once at the end, and writes audit logs.
    """

    def __init__(
        self,
        container: "BackendContainer" | None = None,
        *,
        skills_store: Any = None,
        skills_read_models: Any = None,
        skills_mutations: Any = None,
        agents_store: Any = None,
        agents_mutations: Any = None,
        slash_command_store: Any = None,
        slash_command_sync_state: Any = None,
        slash_command_mutations: Any = None,
        harness_kernel: Any = None,
        mutation_audit: Any = None,
    ) -> None:
        if container is not None:
            self.skills_store = container.skills_store
            self.skills_read_models = container.skills_read_models
            self.skills_mutations = container.skills_mutations
            self.agents_store = container.agents_store
            self.agents_mutations = container.agents_mutations
            self.slash_command_store = container.slash_command_store
            self.slash_command_sync_state = container.slash_command_sync_state
            self.slash_command_mutations = container.slash_command_mutations
            self.harness_kernel = container.harness_kernel
            self.mutation_audit = container.mutation_audit
        else:
            self.skills_store = skills_store
            self.skills_read_models = skills_read_models
            self.skills_mutations = skills_mutations
            self.agents_store = agents_store
            self.agents_mutations = agents_mutations
            self.slash_command_store = slash_command_store
            self.slash_command_sync_state = slash_command_sync_state
            self.slash_command_mutations = slash_command_mutations
            self.harness_kernel = harness_kernel
            self.mutation_audit = mutation_audit

    def apply(
        self,
        actions: tuple[AdoptionAction, ...] | list[AdoptionAction],
        *,
        allow_conflicts: bool = False,
    ) -> tuple[AdoptionApplyResult, ...]:
        results: list[AdoptionApplyResult] = []

        for action in actions:
            result = self._apply_one(action, allow_conflicts=allow_conflicts)
            results.append(result)

        # Invalidate read models once at the end
        try:
            self.skills_read_models.invalidate()
        except Exception:
            pass

        return tuple(results)

    def _apply_one(
        self,
        action: AdoptionAction,
        *,
        allow_conflicts: bool,
    ) -> AdoptionApplyResult:
        target = Path(action.target)

        # Re-check on disk immediately before acting
        already_linked = self._check_already_linked(action, target)
        if already_linked:
            return AdoptionApplyResult(
                family=action.family,
                ref=action.ref,
                harness=action.harness,
                status="applied",
                target=str(target),
            )

        # Check for occupied target (conflict)
        if target.exists() or target.is_symlink():
            if action.action != "conflict" and not allow_conflicts:
                msg = f"Target {target} is occupied; refusing to overwrite"
                record_adopt(
                    self.mutation_audit,
                    family=action.family,
                    ref=action.ref,
                    harness=action.harness,
                    target_paths=(str(target),),
                    outcome="failed",
                    error_type="TargetOccupiedConflict",
                )
                return AdoptionApplyResult(
                    family=action.family,
                    ref=action.ref,
                    harness=action.harness,
                    status="failed",
                    target=str(target),
                    error=msg,
                )

        # Execute the family-specific primitive
        try:
            if action.family == "agents":
                self.agents_mutations.enable(action.ref, action.harness)
            elif action.family == "skills":
                package_dir = action.ref.removeprefix("shared:")
                package_path = self.skills_store.root / package_dir
                self.skills_mutations.enable_managed_package(
                    package_path, action.harness
                )
            elif action.family == "slash_commands":
                self._apply_slash_command(action.ref, action.harness)
            else:
                raise ValueError(f"Unknown family: {action.family}")

            record_adopt(
                self.mutation_audit,
                family=action.family,
                ref=action.ref,
                harness=action.harness,
                target_paths=(str(target),),
                outcome="succeeded",
            )
            return AdoptionApplyResult(
                family=action.family,
                ref=action.ref,
                harness=action.harness,
                status="applied",
                target=str(target),
            )
        except Exception as error:  # noqa: BLE001
            record_adopt(
                self.mutation_audit,
                family=action.family,
                ref=action.ref,
                harness=action.harness,
                target_paths=(str(target),),
                outcome="failed",
                error_type=error.__class__.__name__,
            )
            return AdoptionApplyResult(
                family=action.family,
                ref=action.ref,
                harness=action.harness,
                status="failed",
                target=str(target),
                error=str(error),
            )

    def _check_already_linked(self, action: AdoptionAction, target: Path) -> bool:
        if action.family == "skills":
            package_dir = action.ref.removeprefix("shared:")
            store_pkg = self.skills_store.root / package_dir
            if target.is_symlink():
                try:
                    return target.resolve() == store_pkg.resolve()
                except OSError:
                    return False
            return False

        if action.family == "agents":
            agent = self.agents_store.get(action.ref)
            if agent is None:
                return False
            adapter = self.agents_mutations.adapters.get(action.harness)
            if adapter is not None and adapter.renders:
                rendered_content = render_codex_agent(agent)
                target_hash = _safe_hash(target)
                return (
                    target.is_file()
                    and _has_marker(target)
                    and target_hash == _safe_hash_text(rendered_content)
                )
            if target.is_symlink():
                try:
                    return target.resolve() == agent.path.resolve()
                except OSError:
                    return False
            return False

        if action.family == "slash_commands":
            command = self.slash_command_store.get_command(action.ref)
            if command is None or not target.is_file():
                return False
            binding = self.harness_kernel.binding_for(action.harness, "slash_commands")
            render_format = (
                binding.render_format
                if isinstance(binding, CommandFileBindingProfile)
                else "frontmatter_markdown"
            )
            rendered = render_slash_command(command, render_format)
            return _safe_hash(target) == _safe_hash_text(rendered)

        return False

    def _apply_slash_command(self, name: str, harness: str) -> None:
        # Find all targets currently live on disk for this command
        all_targets = self.slash_command_mutations.resolve_targets()
        active_targets = {
            t.id
            for t in all_targets
            if self.slash_command_mutations.path_policy.output_path(t, name).is_file()
        }
        targets_to_sync = list(active_targets | {harness})

        # Preserve any unselected intent from sync_state
        previous_records = dict(
            self.slash_command_sync_state.load().get(name, {})
        )

        self.slash_command_mutations.sync_command(name, targets=targets_to_sync)

        # Restore unselected previous records so they aren't lost from intent
        for target_id, rec in previous_records.items():
            if target_id not in targets_to_sync:
                self.slash_command_sync_state.add_target(name, rec)


__all__ = ["AdoptionApplier", "record_adopt"]
