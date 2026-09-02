from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harness_asset_manager.application.agents.adapters import (
    _has_marker,
    render_codex_agent,
)
from harness_asset_manager.application.agents.ledger import AgentBindingLedger
from harness_asset_manager.application.agents.mutations import AgentMutationService
from harness_asset_manager.application.agents.store import AgentStore
from harness_asset_manager.application.agents.targets import (
    _is_installed as _is_agent_installed,
)
from harness_asset_manager.application.drift import classify_drift
from harness_asset_manager.application.skills.manifest import load_skill_store_manifest
from harness_asset_manager.application.skills.read_models import SkillsReadModelService
from harness_asset_manager.application.skills.store import SkillStore
from harness_asset_manager.application.slash_commands.codecs import render_slash_command
from harness_asset_manager.application.slash_commands.mutations import (
    SlashCommandMutationService,
)
from harness_asset_manager.application.slash_commands.store import SlashCommandStore
from harness_asset_manager.application.slash_commands.sync_state import (
    SlashCommandSyncStateStore,
)
from harness_asset_manager.application.slash_commands.targets import (
    _is_detected as _is_slash_detected,
)
from harness_asset_manager.harness import HarnessKernelService
from harness_asset_manager.harness.contracts import (
    AgentFileBindingProfile,
    CommandFileBindingProfile,
)
from harness_asset_manager.hashing import hash_file, hash_text

from .models import AdoptionAction, AdoptionPlan

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


def _is_agent_harness_installed(kernel: HarnessKernelService, harness: str) -> bool:
    definition = kernel.definition(harness)
    if definition is None:
        return False
    binding = kernel.binding_for(harness, "agents")
    if not isinstance(binding, AgentFileBindingProfile):
        return False
    return _is_agent_installed(kernel, definition, binding)


def _is_slash_harness_installed(kernel: HarnessKernelService, harness: str) -> bool:
    definition = kernel.definition(harness)
    if definition is None:
        return False
    binding = kernel.binding_for(harness, "slash_commands")
    if not isinstance(binding, CommandFileBindingProfile):
        return False
    return _is_slash_detected(kernel, definition, binding)


class AdoptionPlanner:
    """Computes the new-device adoption plan pure with respect to mutation.

    Reads the synced store intent and stats the filesystem on THIS device to derive
    the exact set of link, skip, and conflict actions. Writes nothing.
    """

    def __init__(
        self,
        *,
        skills_store: SkillStore,
        skills_read_models: SkillsReadModelService,
        agents_store: AgentStore,
        agents_ledger: AgentBindingLedger,
        agents_mutations: AgentMutationService,
        slash_command_store: SlashCommandStore,
        slash_command_sync_state: SlashCommandSyncStateStore,
        slash_command_mutations: SlashCommandMutationService,
        harness_kernel: HarnessKernelService,
    ) -> None:
        self.skills_store = skills_store
        self.skills_read_models = skills_read_models
        self.agents_store = agents_store
        self.agents_ledger = agents_ledger
        self.agents_mutations = agents_mutations
        self.slash_command_store = slash_command_store
        self.slash_command_sync_state = slash_command_sync_state
        self.slash_command_mutations = slash_command_mutations
        self.harness_kernel = harness_kernel

    @classmethod
    def from_container(cls, container: "BackendContainer") -> "AdoptionPlanner":
        return cls(
            skills_store=container.skills_store,
            skills_read_models=container.skills_read_models,
            agents_store=container.agents_store,
            agents_ledger=getattr(container.agents_mutations, "ledger", None)
            or AgentBindingLedger(
                container.paths.bindings_ledger_path,
                home=container.app_home,
            ),
            agents_mutations=container.agents_mutations,
            slash_command_store=container.slash_command_store,
            slash_command_sync_state=container.slash_command_sync_state,
            slash_command_mutations=container.slash_command_mutations,
            harness_kernel=container.harness_kernel,
        )

    def plan(self) -> AdoptionPlan:
        actions: list[AdoptionAction] = []
        actions.extend(self._plan_skills())
        actions.extend(self._plan_agents())
        actions.extend(self._plan_slash_commands())
        sorted_actions = tuple(
            sorted(actions, key=lambda a: (a.family, a.ref, a.harness))
        )
        return AdoptionPlan(actions=sorted_actions)

    def _plan_skills(self) -> list[AdoptionAction]:
        actions: list[AdoptionAction] = []
        try:
            manifest = load_skill_store_manifest(self.skills_store.manifest_path)
        except Exception:
            return []

        enabled_harnesses_in_settings = set(self.skills_read_models.enabled_harnesses())

        for entry in manifest.entries:
            ref = f"shared:{entry.package_dir}"
            display_name = entry.declared_name or entry.package_dir
            store_pkg = self.skills_store.root / entry.package_dir

            for harness in entry.enabled_harnesses:
                adapter = self.skills_read_models.find_adapter(harness)

                # Fallback target path if adapter cannot resolve
                default_target = (
                    self.harness_kernel.context.home / f".{harness}" / "skills" / entry.package_dir
                )
                if adapter is not None:
                    try:
                        target = adapter._binding_path(entry.package_dir)
                    except Exception:
                        target = default_target
                else:
                    target = default_target

                # 1. Harness not installed on this device
                if adapter is None or not adapter.status().installed:
                    actions.append(
                        AdoptionAction(
                            family="skills",
                            ref=ref,
                            display_name=display_name,
                            harness=harness,
                            action="skip",
                            target=target,
                            reason="harness-not-installed",
                            detail=f"Harness '{harness}' is not installed on this device",
                        )
                    )
                    continue

                # 2. Harness support disabled in settings
                if harness not in enabled_harnesses_in_settings:
                    actions.append(
                        AdoptionAction(
                            family="skills",
                            ref=ref,
                            display_name=display_name,
                            harness=harness,
                            action="skip",
                            target=target,
                            reason="harness-support-disabled",
                            detail=f"Support for harness '{harness}' is disabled in settings",
                        )
                    )
                    continue

                # 3. Store no longer holds the asset
                if not store_pkg.exists() or not store_pkg.is_dir():
                    actions.append(
                        AdoptionAction(
                            family="skills",
                            ref=ref,
                            display_name=display_name,
                            harness=harness,
                            action="skip",
                            target=target,
                            reason="asset-missing-from-store",
                            detail=f"Skill package '{entry.package_dir}' is missing from store",
                        )
                    )
                    continue

                # 4. Target already the correct binding
                if target.is_symlink():
                    try:
                        if target.resolve() == store_pkg.resolve():
                            actions.append(
                                AdoptionAction(
                                    family="skills",
                                    ref=ref,
                                    display_name=display_name,
                                    harness=harness,
                                    action="skip",
                                    target=target,
                                    reason="already-linked",
                                    detail=f"Target {target} is already bound to store asset",
                                )
                            )
                            continue
                    except OSError:
                        pass

                # 5. Target exists, foreign content
                if target.exists() or target.is_symlink():
                    drift = classify_drift(
                        baseline_sha256=None,
                        harness_sha256=None,
                        store_sha256=None,
                    )
                    actions.append(
                        AdoptionAction(
                            family="skills",
                            ref=ref,
                            display_name=display_name,
                            harness=harness,
                            action="conflict",
                            target=target,
                            reason="target-occupied",
                            detail=f"Target {target} is occupied ({drift})",
                        )
                    )
                    continue

                # 6. Otherwise
                actions.append(
                    AdoptionAction(
                        family="skills",
                        ref=ref,
                        display_name=display_name,
                        harness=harness,
                        action="link",
                        target=target,
                    )
                )

        return actions

    def _plan_agents(self) -> list[AdoptionAction]:
        actions: list[AdoptionAction] = []
        if not self.agents_ledger.path.is_file():
            return []

        try:
            raw_payload = json.loads(self.agents_ledger.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

        if not isinstance(raw_payload, dict):
            return []
        raw_agents: Any = raw_payload.get("agents")
        if not isinstance(raw_agents, dict):
            return []

        parsed_state = self.agents_ledger.load()
        targets = self.agents_mutations.targets
        target_by_id = {t.id: t for t in targets}
        adapters = self.agents_mutations.adapters

        for slug, harness_dict in raw_agents.items():
            if not isinstance(slug, str) or not isinstance(harness_dict, dict):
                continue

            agent = self.agents_store.get(slug)
            display_name = agent.name if agent is not None else slug

            for harness in harness_dict:
                if not isinstance(harness, str):
                    continue

                target_meta = target_by_id.get(harness)
                adapter = adapters.get(harness)

                default_target = (
                    self.harness_kernel.context.home / f".{harness}" / "agents" / f"{slug}.md"
                )
                if adapter is not None:
                    target = adapter.binding_path(slug)
                else:
                    target = default_target

                is_installed = _is_agent_harness_installed(self.harness_kernel, harness)
                is_support_enabled = self.harness_kernel.support_store.load().is_enabled(harness)

                # 1. Harness not installed on this device
                if not is_installed:
                    actions.append(
                        AdoptionAction(
                            family="agents",
                            ref=slug,
                            display_name=display_name,
                            harness=harness,
                            action="skip",
                            target=target,
                            reason="harness-not-installed",
                            detail=f"Harness '{harness}' is not installed on this device",
                        )
                    )
                    continue

                # 2. Harness support disabled in settings
                if not is_support_enabled:
                    actions.append(
                        AdoptionAction(
                            family="agents",
                            ref=slug,
                            display_name=display_name,
                            harness=harness,
                            action="skip",
                            target=target,
                            reason="harness-support-disabled",
                            detail=f"Support for harness '{harness}' is disabled in settings",
                        )
                    )
                    continue

                # 3. Store no longer holds the asset (or record dropped due to legacy absolute path)
                record = parsed_state.get(slug, {}).get(harness)
                if record is None or agent is None or not agent.path.is_file():
                    actions.append(
                        AdoptionAction(
                            family="agents",
                            ref=slug,
                            display_name=display_name,
                            harness=harness,
                            action="skip",
                            target=target,
                            reason="asset-missing-from-store",
                            detail=f"Asset '{slug}' is missing from store or has unresolvable path",
                        )
                    )
                    continue

                renders = adapter.renders if adapter is not None else False

                # 4. Target already the correct binding
                if renders:
                    rendered_content = render_codex_agent(agent)
                    rendered_hash = _safe_hash_text(rendered_content)
                    target_hash = _safe_hash(target)
                    if target.is_file() and _has_marker(target) and target_hash == rendered_hash:
                        actions.append(
                            AdoptionAction(
                                family="agents",
                                ref=slug,
                                display_name=display_name,
                                harness=harness,
                                action="skip",
                                target=target,
                                reason="already-linked",
                                detail=f"Agent '{slug}' is already rendered at {target}",
                            )
                        )
                        continue
                else:
                    if target.is_symlink():
                        try:
                            if target.resolve() == agent.path.resolve():
                                actions.append(
                                    AdoptionAction(
                                        family="agents",
                                        ref=slug,
                                        display_name=display_name,
                                        harness=harness,
                                        action="skip",
                                        target=target,
                                        reason="already-linked",
                                        detail=f"Agent '{slug}' is already linked at {target}",
                                    )
                                )
                                continue
                        except OSError:
                            pass

                # 5. Target exists, foreign content
                if target.exists() or target.is_symlink():
                    if renders:
                        store_sha = _safe_hash_text(render_codex_agent(agent))
                        baseline_sha = record.rendered_sha256
                    else:
                        store_sha = _safe_hash(agent.path)
                        baseline_sha = record.store_sha256
                    harness_sha = _safe_hash(target)
                    drift = classify_drift(
                        baseline_sha256=baseline_sha,
                        harness_sha256=harness_sha,
                        store_sha256=store_sha,
                    )
                    actions.append(
                        AdoptionAction(
                            family="agents",
                            ref=slug,
                            display_name=display_name,
                            harness=harness,
                            action="conflict",
                            target=target,
                            reason="target-occupied",
                            detail=f"Target {target} is occupied ({drift})",
                        )
                    )
                    continue

                # 6. Otherwise
                actions.append(
                    AdoptionAction(
                        family="agents",
                        ref=slug,
                        display_name=display_name,
                        harness=harness,
                        action="link",
                        target=target,
                    )
                )

        return actions

    def _plan_slash_commands(self) -> list[AdoptionAction]:
        actions: list[AdoptionAction] = []
        if not self.slash_command_sync_state.path.is_file():
            return []

        try:
            raw_payload = json.loads(self.slash_command_sync_state.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

        if not isinstance(raw_payload, dict):
            return []
        raw_commands: Any = raw_payload.get("commands", raw_payload)
        if not isinstance(raw_commands, dict):
            return []

        parsed_state = self.slash_command_sync_state.load()
        all_targets = self.slash_command_mutations.resolve_targets()
        target_by_id = {t.id: t for t in all_targets}

        for name, target_dict in raw_commands.items():
            if not isinstance(name, str) or not isinstance(target_dict, dict):
                continue

            command = self.slash_command_store.get_command(name)
            display_name = name

            for target_id in target_dict:
                if not isinstance(target_id, str):
                    continue

                binding = self.harness_kernel.binding_for(target_id, "slash_commands")
                render_format = (
                    binding.render_format
                    if isinstance(binding, CommandFileBindingProfile)
                    else "frontmatter_markdown"
                )

                slash_target = target_by_id.get(target_id)
                default_target = (
                    self.harness_kernel.context.home / f".{target_id}" / "commands" / f"{name}.md"
                )
                if slash_target is not None:
                    target = self.slash_command_mutations.path_policy.output_path(slash_target, name)
                elif isinstance(binding, CommandFileBindingProfile):
                    target = binding.resolve_output_dir(self.harness_kernel.context) / f"{name}.md"
                else:
                    target = default_target

                is_installed = _is_slash_harness_installed(self.harness_kernel, target_id)
                is_support_enabled = self.harness_kernel.support_store.load().is_enabled(target_id)

                # 1. Harness not installed on this device
                if not is_installed:
                    actions.append(
                        AdoptionAction(
                            family="slash_commands",
                            ref=name,
                            display_name=display_name,
                            harness=target_id,
                            action="skip",
                            target=target,
                            reason="harness-not-installed",
                            detail=f"Harness '{target_id}' is not installed on this device",
                        )
                    )
                    continue

                # 2. Harness support disabled in settings
                if not is_support_enabled:
                    actions.append(
                        AdoptionAction(
                            family="slash_commands",
                            ref=name,
                            display_name=display_name,
                            harness=target_id,
                            action="skip",
                            target=target,
                            reason="harness-support-disabled",
                            detail=f"Support for harness '{target_id}' is disabled in settings",
                        )
                    )
                    continue

                # 3. Store no longer holds the asset (or record dropped due to legacy path)
                record = parsed_state.get(name, {}).get(target_id)
                if record is None or command is None:
                    actions.append(
                        AdoptionAction(
                            family="slash_commands",
                            ref=name,
                            display_name=display_name,
                            harness=target_id,
                            action="skip",
                            target=target,
                            reason="asset-missing-from-store",
                            detail=f"Slash command '{name}' is missing from store or has unresolvable path",
                        )
                    )
                    continue

                # Rendered content for target
                rendered = render_slash_command(command, render_format)
                rendered_hash = _safe_hash_text(rendered)
                target_hash = _safe_hash(target)

                # 4. Target already the correct binding
                if target.is_file() and target_hash == rendered_hash:
                    actions.append(
                        AdoptionAction(
                            family="slash_commands",
                            ref=name,
                            display_name=display_name,
                            harness=target_id,
                            action="skip",
                            target=target,
                            reason="already-linked",
                            detail=f"Slash command '{name}' is already synced at {target}",
                        )
                    )
                    continue

                # 5. Target exists, foreign content
                if target.exists() or target.is_symlink():
                    drift = classify_drift(
                        baseline_sha256=record.content_hash,
                        harness_sha256=target_hash,
                        store_sha256=rendered_hash,
                    )
                    actions.append(
                        AdoptionAction(
                            family="slash_commands",
                            ref=name,
                            display_name=display_name,
                            harness=target_id,
                            action="conflict",
                            target=target,
                            reason="target-occupied",
                            detail=f"Target {target} is occupied ({drift})",
                        )
                    )
                    continue

                # 6. Otherwise
                actions.append(
                    AdoptionAction(
                        family="slash_commands",
                        ref=name,
                        display_name=display_name,
                        harness=target_id,
                        action="link",
                        target=target,
                    )
                )

        return actions


__all__ = ["AdoptionPlanner"]
