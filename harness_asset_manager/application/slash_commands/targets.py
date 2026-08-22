from __future__ import annotations

from typing import cast

from harness_asset_manager.harness import (
    CommandFileBindingProfile,
    HarnessKernelService,
)

from .models import SlashTarget, SlashTargetId


def resolve_slash_targets(kernel: HarnessKernelService) -> tuple[SlashTarget, ...]:
    """Columns for the slash-commands matrix.

    Deliberately *not* a curated list. Which harnesses appear is decided the same way
    Skills and Agents decide it — every harness declaring a slash-commands binding,
    minus the ones the user disabled in Settings — so the pages can never disagree
    about which harnesses exist. Column order follows catalog declaration order.
    """
    enabled = set(kernel.enabled_harness_ids_for_family("slash_commands"))
    targets: list[SlashTarget] = []
    for binding in kernel.bindings_for_family("slash_commands"):
        profile = binding.profile
        if not isinstance(profile, CommandFileBindingProfile):
            continue
        definition = binding.definition
        target_id = cast(SlashTargetId, definition.harness)
        if target_id not in enabled:
            continue
        root_path = profile.resolve_root_path(kernel.context)
        output_dir = profile.resolve_output_dir(kernel.context)
        available = root_path.exists()
        installed = _is_detected(kernel, definition, profile)
        targets.append(
            SlashTarget(
                id=target_id,
                label=definition.label,
                root_path=root_path,
                output_dir=output_dir,
                invocation_prefix=profile.invocation_prefix,
                render_format=profile.render_format,
                scope=profile.scope,
                docs_url=profile.docs_url,
                file_glob=profile.file_glob,
                supports_frontmatter=profile.supports_frontmatter,
                support_note=profile.support_note,
                enabled=True,
                available=available,
                default_selected=available,
                installed=installed,
            )
        )
    return tuple(targets)


def _is_detected(
    kernel: HarnessKernelService,
    definition,
    profile: CommandFileBindingProfile,
) -> bool:
    """Derive detection from harness support status: CLI on PATH, app probe, or config present."""
    import shutil

    from harness_asset_manager.harness.contracts import (
        ConfigSubtreeBindingProfile,
        FileTreeBindingProfile,
    )

    if shutil.which(definition.install_probe, path=kernel.context.env.get("PATH")) is not None:
        return True
    skills_binding = definition.binding_for("skills")
    if isinstance(skills_binding, FileTreeBindingProfile) and skills_binding.availability == "cli_or_app":
        if any(resolver(kernel.context).exists() for resolver in skills_binding.app_probe_paths):
            return True
    for family in ("mcp", "hooks", "permissions"):
        config_profile = definition.binding_for(family)
        if isinstance(config_profile, ConfigSubtreeBindingProfile):
            if any(path.is_file() for path in config_profile.resolve_discovery_config_paths(kernel.context)):
                return True
    return False


def default_target_ids(targets: tuple[SlashTarget, ...]) -> tuple[SlashTargetId, ...]:
    return tuple(target.id for target in targets if target.default_selected)


def target_by_id(targets: tuple[SlashTarget, ...], target_id: str) -> SlashTarget | None:
    return next((target for target in targets if target.id == target_id), None)


__all__ = ["default_target_ids", "resolve_slash_targets", "target_by_id"]
