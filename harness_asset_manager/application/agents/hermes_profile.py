from __future__ import annotations

import copy
import json
import logging
import os
from collections.abc import Iterable, Mapping, MutableMapping
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
    root_doc: dict[str, object] = {}
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
    explicit_model = agent.hermes_model.strip() if agent.hermes_model else None
    # The shared frontmatter model is the portable default; Hermes-specific model
    # metadata remains an override for agents that need a different route.
    model = explicit_model or (agent.model.strip() if agent.model else None)
    inferred_provider = _provider_for_model(root_doc, model)
    if provider is None:
        provider = inferred_provider
    provider_owned = bool(
        previous
        and (
            (previous.hermes_provider and previous.hermes_provider.strip())
            or _provider_for_model(
                root_doc,
                previous.hermes_model or previous.model,
            )
        )
    )
    model_owned = bool(
        previous
        and (
            (previous.hermes_model and previous.hermes_model.strip())
            or (not previous.hermes_model and previous.model and previous.model.strip())
        )
    )
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

    _seed_configured_provider(config_doc, root_doc, provider)
    rendered_config = dump_config_document(config_doc, file_format="yaml")
    atomic_write_text(config_file, rendered_config, follow_symlinks=False)


def hermes_provider_options(hermes_root: Path) -> tuple[dict[str, object], ...]:
    """Return configured Hermes providers and the model ids they advertise.

    This is intentionally a read-only view of the root config: selecting an option
    does not make a Bot inherit the root profile. Built-in providers appear when
    they are selected by the root model block or have an explicit credential in
    Hermes' auth pool; custom providers come from the root ``providers`` mapping.
    """
    config_file = hermes_root / "config.yaml"
    document: Mapping[str, object] = {}
    if config_file.is_file():
        try:
            document = load_config_document(config_file.read_text(encoding="utf-8"), file_format="yaml")
        except Exception:
            pass
    return _provider_options_from_document(document, _auth_provider_names(hermes_root))


def _provider_options_from_document(
    document: Mapping[str, object],
    extra_provider_names: Iterable[str] = (),
) -> tuple[dict[str, object], ...]:
    model_config = document.get("model")
    configured_provider = None
    configured_model = None
    if isinstance(model_config, Mapping):
        configured_provider = _config_string(model_config.get("provider"))
        configured_model = _config_string(model_config.get("default")) or _config_string(model_config.get("model"))
    providers = document.get("providers")
    provider_map = providers if isinstance(providers, Mapping) else {}
    names: list[str] = []
    if configured_provider:
        names.append(configured_provider)
    names.extend(str(name) for name in provider_map if str(name) not in names)
    names.extend(name for name in extra_provider_names if name not in names)

    options: list[dict[str, object]] = []
    for name in names:
        models: list[str] = []
        if name == configured_provider and configured_model:
            models.append(configured_model)
        definition = provider_map.get(name)
        if isinstance(definition, Mapping):
            for key in ("default", "model"):
                value = _config_string(definition.get(key))
                if value and value not in models:
                    models.append(value)
            declared = definition.get("models")
            if isinstance(declared, (list, tuple)):
                for value in declared:
                    model_id = _config_string(value)
                    if model_id and model_id not in models:
                        models.append(model_id)
        options.append({"id": name, "models": models})
    return tuple(options)


def _auth_provider_names(hermes_root: Path) -> tuple[str, ...]:
    """Return providers with explicit credentials in Hermes' auth store.

    The root config only contains the active model and named custom endpoints.
    OAuth and pooled API-key providers live in ``auth.json`` instead. Ambient
    credentials borrowed from another CLI (for example GitHub's ``gh`` token)
    are deliberately excluded, matching Hermes' explicit-provider semantics.
    """
    auth_file = hermes_root / "auth.json"
    if not auth_file.is_file():
        return ()
    try:
        auth_store = json.loads(auth_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    pool = auth_store.get("credential_pool") if isinstance(auth_store, Mapping) else None
    if not isinstance(pool, Mapping):
        return ()

    names: list[str] = []
    for provider, entries in pool.items():
        if not isinstance(provider, str) or not isinstance(entries, list):
            continue
        if any(_is_explicit_auth_entry(entry) for entry in entries):
            names.append(provider)
    return tuple(names)


def _is_explicit_auth_entry(entry: object) -> bool:
    if not isinstance(entry, Mapping):
        return False
    source = _config_string(entry.get("source"))
    if not source:
        return False
    source_lower = source.lower()
    if source_lower.startswith("env:"):
        env_name = source.split(":", 1)[1].strip()
        return bool(env_name and os.environ.get(env_name, "").strip())
    return source_lower in {"device_code", "loopback_pkce", "hermes_pkce", "manual"} or source_lower.startswith("manual:")


def _provider_for_model(document: Mapping[str, object], model: str | None) -> str | None:
    if not model:
        return None
    matches = []
    for option in _provider_options_from_document(document):
        advertised_models = option.get("models")
        if isinstance(advertised_models, list) and any(
            isinstance(value, str) and value == model for value in advertised_models
        ):
            matches.append(str(option["id"]))
    return matches[0] if len(matches) == 1 else None


def _config_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _seed_configured_provider(
    config_doc: MutableMapping[str, object],
    root_doc: Mapping[str, object],
    provider: str | None,
) -> None:
    """Copy a selected custom provider definition without copying credentials."""
    if not provider:
        return
    root_providers = root_doc.get("providers")
    if not isinstance(root_providers, Mapping):
        return
    definition = root_providers.get(provider)
    if not isinstance(definition, Mapping):
        return
    profile_providers = config_doc.get("providers")
    if profile_providers is None:
        profile_providers = new_subtree("yaml")
        config_doc["providers"] = profile_providers
    if not isinstance(profile_providers, MutableMapping):
        return
    if provider not in profile_providers:
        safe_definition = copy.deepcopy(dict(definition))
        for key in ("api_key", "apiKey", "token", "secret", "password"):
            safe_definition.pop(key, None)
        profile_providers[provider] = safe_definition


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
