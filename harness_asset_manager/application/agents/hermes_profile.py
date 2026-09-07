from __future__ import annotations

import logging
import os
from collections.abc import MutableMapping
from pathlib import Path

from harness_asset_manager.application.agents.model import AgentDefinition
from harness_asset_manager.atomic_files import atomic_write_text
from harness_asset_manager.config_document import (
    dump_config_document,
    empty_config_document,
    load_config_document,
    new_subtree,
)
from harness_asset_manager.errors import MutationError
from harness_asset_manager.harness.hermes_profiles import (
    hermes_profile_name,
    profile_home,
    profile_is_tombstoned,
    profile_skills_harnessam_dir,
    profile_tombstone_path,
)

_logger = logging.getLogger(__name__)

_HERMES_SUBDIRS = (
    "memories",
    "sessions",
    "skills",
    "skins",
    "logs",
    "plans",
    "workspace",
    "cron",
    "home",
)


def ensure_profile(
    agent: AgentDefinition,
    hermes_root: Path,
    *,
    previous: AgentDefinition | None = None,
) -> None:
    """Idempotently provision or update a Hermes profile for a HAM agent.

    This is best-effort and non-transactional. A failure here should not
    roll back the HAM-side agent creation.

    Explicitly NOT replicated: the PATH wrapper script and the gateway
    service registration. HAM-managed Bots are addressed as `hermes -p <name>`.
    """
    name = hermes_profile_name(agent.slug)
    home = profile_home(hermes_root, name)

    # Check tombstone
    if profile_is_tombstoned(hermes_root, name):
        # A tombstoned profile dir may only be reclaimed when it is an
        # identity-free empty shell.
        if (home / "config.yaml").exists() or (home / ".env").exists():
            raise MutationError(
                f"Profile '{name}' is deleted but still contains identity files. "
                "Cannot resurrect it safely.",
                status=409,
                code="hermes_profile_tombstoned_with_identity",
            )
        else:
            # Reclaiming means the profile is live again; Hermes' own create_profile
            # clears the marker on this path (clear_named_profile_deleted), and leaving
            # it would make the profile exist while Hermes still reads it as deleted.
            profile_tombstone_path(hermes_root, name).unlink(missing_ok=True)

    # Subdirectories
    for subdir in _HERMES_SUBDIRS:
        (home / subdir).mkdir(parents=True, exist_ok=True)

    profile_skills_harnessam_dir(hermes_root, name).mkdir(parents=True, exist_ok=True)

    # .env
    env_file = home / ".env"
    if not env_file.exists():
        # seed empty with mode 0o600
        try:
            fd = os.open(env_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("# Hermes environment variables\n")
        except FileExistsError:
            pass

    # SOUL.md
    soul_file = home / "SOUL.md"
    atomic_write_text(soul_file, agent.prompt, follow_symlinks=False)

    # .no-bundled-skills
    no_bundled_skills_file = home / ".no-bundled-skills"
    if not no_bundled_skills_file.exists():
        no_bundled_skills_file.write_text(
            "# Written by HAM. Deleting this file re-enables bundled-skill seeding.\n",
            encoding="utf-8",
        )

    # config.yaml. The profile adapter is the sole writer for this file's model
    # subtree. In particular, it never synthesizes a provider-prefixed model id.
    config_file = home / "config.yaml"
    root_config_file = hermes_root / "config.yaml"

    root_version = None
    if root_config_file.is_file():
        try:
            root_doc = load_config_document(
                root_config_file.read_text(encoding="utf-8"), file_format="yaml"
            )
            root_version = root_doc.get("_config_version")
        except Exception:
            pass

    if config_file.is_file():
        content = config_file.read_text(encoding="utf-8")
        config_doc = load_config_document(content, file_format="yaml")
    else:
        config_doc = empty_config_document("yaml")

    if root_version is not None:
        config_doc["_config_version"] = root_version

    provider = agent.hermes_provider.strip() if agent.hermes_provider else None
    model = agent.hermes_model.strip() if agent.hermes_model else None
    provider_owned = bool(previous and previous.hermes_provider and previous.hermes_provider.strip())
    model_owned = bool(previous and previous.hermes_model and previous.hermes_model.strip())
    provider_touched = provider is not None or provider_owned
    model_touched = model is not None or model_owned
    if provider_touched or model_touched:
        model_config = config_doc.get("model")
        if model_config is None and (provider is not None or model is not None):
            model_config = new_subtree("yaml")
            config_doc["model"] = model_config
        elif model_config is not None and not isinstance(model_config, MutableMapping):
            raise MutationError(
                f"Hermes profile config {config_file} has a non-mapping model value",
                status=409,
                code="invalid_hermes_model_config",
            )

        if isinstance(model_config, MutableMapping) and provider_touched:
            _set_or_clear_model_key(model_config, "provider", provider, provider_owned)
        if isinstance(model_config, MutableMapping) and model_touched:
            _set_or_clear_model_key(model_config, "default", model, model_owned)
        if isinstance(model_config, MutableMapping) and not model_config:
            del config_doc["model"]

    rendered_config = dump_config_document(config_doc, file_format="yaml")
    atomic_write_text(config_file, rendered_config, follow_symlinks=False)


def _set_or_clear_model_key(
    model_config: MutableMapping[str, object],
    key: str,
    value: str | None,
    previously_owned: bool,
) -> None:
    """Apply one explicitly edited HAM key while leaving user model keys alone."""
    if value is not None and value.strip():
        model_config[key] = value.strip()
    elif previously_owned:
        model_config.pop(key, None)


def detach_profile(agent: AgentDefinition, hermes_root: Path) -> None:
    """Orphan-safe detach of a HAM agent from its Hermes profile.

    Removing HAM's ownership of a profile must not delete sessions, memory,
    or the profile directory. Detach removes only what HAM wrote and owns.
    In Phase 1, there are no HAM-owned skill links yet, so this is a documented
    no-op on the filesystem. (HAM forgets the binding in its ledger; Phase 2
    adds link removal).
    """
    pass
