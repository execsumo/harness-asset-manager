from __future__ import annotations

import shutil

from skill_manager.harness import AgentFileBindingProfile, HarnessKernelService

from .model import AgentTarget

# Only harnesses with a verified subagent-file format. Cursor has rules, not agents;
# Codex/Hermes/OpenClaw/Antigravity get a column when someone verifies a real format.
TARGET_ORDER: tuple[str, ...] = ("claude", "opencode")


def resolve_agent_targets(kernel: HarnessKernelService) -> tuple[AgentTarget, ...]:
    enabled = set(kernel.enabled_harness_ids_for_family("agents"))
    targets: dict[str, AgentTarget] = {}
    for binding in kernel.bindings_for_family("agents"):
        profile = binding.profile
        if not isinstance(profile, AgentFileBindingProfile):
            continue
        definition = binding.definition
        targets[definition.harness] = AgentTarget(
            id=definition.harness,
            label=definition.label,
            logo_key=definition.logo_key,
            root_path=profile.resolve_root_path(kernel.context),
            output_dir=profile.resolve_output_dir(kernel.context),
            file_glob=profile.file_glob,
            docs_url=profile.docs_url,
            installed=_is_installed(kernel, definition.install_probe, profile),
            enabled=definition.harness in enabled,
        )
    return tuple(targets[target_id] for target_id in TARGET_ORDER if target_id in targets)


def target_by_id(targets: tuple[AgentTarget, ...], target_id: str) -> AgentTarget | None:
    return next((target for target in targets if target.id == target_id), None)


def _is_installed(
    kernel: HarnessKernelService, install_probe: str, profile: AgentFileBindingProfile
) -> bool:
    if shutil.which(install_probe, path=kernel.context.env.get("PATH")) is not None:
        return True
    # A populated agents dir is proof enough that the harness is present.
    return profile.resolve_root_path(kernel.context).is_dir()


__all__ = ["TARGET_ORDER", "resolve_agent_targets", "target_by_id"]
