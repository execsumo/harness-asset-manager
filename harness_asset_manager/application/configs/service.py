from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from harness_asset_manager.application.config_documents import (
    dump_document,
    load_document,
)
from harness_asset_manager.atomic_files import atomic_write_text, file_lock
from harness_asset_manager.errors import MutationError
from harness_asset_manager.harness import (
    ConfigSubtreeBindingProfile,
    HarnessKernelService,
)

from .extraction import extract_preferences
from .model import ConfigRecord
from .store import ConfigStore


class ConfigsService:
    def __init__(self, store: ConfigStore, kernel: HarnessKernelService) -> None:
        self.store = store
        self.kernel = kernel

    def _hash_prefs(self, prefs: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(prefs, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def _get_binding_profile(
        self, harness_name: str
    ) -> ConfigSubtreeBindingProfile | None:
        bindings = self.kernel.bindings_for_family("configs")
        for binding in bindings:
            if binding.definition.harness == harness_name:
                if isinstance(binding.profile, ConfigSubtreeBindingProfile):
                    return binding.profile
        return None

    def _extract_local(self, harness_name: str) -> dict[str, Any]:
        profile = self._get_binding_profile(harness_name)
        if not profile:
            return {}
        path = profile.resolve_config_path(self.kernel.context)
        if not path.is_file():
            return {}
        doc = load_document(path, profile.file_format, harness_name)
        # The Configs family targets the whole file (unlike MCP which targets a subtree).
        # We extract from the top-level document.
        home_dir = str(self.kernel.context.home)
        definition = self.kernel.definition(harness_name)
        family_owned_keys = (
            definition.bindings["configs"].exclusion_keys
            if definition
            and "configs" in definition.bindings
            and hasattr(definition.bindings["configs"], "exclusion_keys")
            else frozenset()
        )
        return extract_preferences(doc, family_owned_keys, home_dir)

    def capture(self, explicit: bool = False) -> None:
        """Capture local preferences to the manifest."""
        manifest = self.store.load()
        for binding in self.kernel.bindings_for_family("configs"):
            harness = binding.definition.harness
            local_prefs = self._extract_local(harness)
            local_hash = self._hash_prefs(local_prefs)

            record = manifest.configs.get(harness)

            # The manifest is synced between machines, so an automatic capture that
            # always wrote would make the last machine to start up the winner.
            # ``drift.classify_drift`` cannot arbitrate here: it needs a baseline of
            # what *this* machine last captured, and the family keeps no local ledger
            # to hold one. So a divergence is left for the user to resolve explicitly
            # rather than guessed at.
            if not explicit and record and record.preferences != local_prefs:
                continue

            new_record = ConfigRecord(
                sourceFile=str(
                    binding.profile.resolve_config_path(self.kernel.context)
                ),
                preferences=local_prefs,
                capturedAt=datetime.now(timezone.utc).isoformat(),
                revision=local_hash,
            )
            self.store.write_config(harness, new_record)

    def restore(self, harness: str) -> None:
        """Restore preferences from manifest to the local file."""
        profile = self._get_binding_profile(harness)
        if not profile:
            raise MutationError(
                f"{harness} is not a harness with a managed config.",
                status=404,
                code="unknown_harness",
            )

        # Reported rather than silently ignored: a caller asking to restore a
        # harness that was never captured has nothing to restore, and answering
        # "ok" would let a typo read as a successful write.
        manifest = self.store.load()
        record = manifest.configs.get(harness)
        if not record:
            raise MutationError(
                f"{harness} has no captured preferences to restore.",
                status=404,
                code="not_captured",
            )


        if profile.file_format in {"toml", "jsonc"}:
            raise MutationError(
                f"Cannot restore {profile.file_format} files without rewriting unowned content or stripping comments. Restore refused.",
                status=400,
                code="format_refused"
            )

        path = profile.resolve_config_path(self.kernel.context)
        doc = (
            load_document(path, profile.file_format, harness) if path.is_file() else {}
        )

        # Merge record.preferences into doc
        # We only overwrite keys that are in the preferences.
        for k, v in record.preferences.items():
            doc[k] = v

        # Write back
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(path.suffix + ".lock")
        with file_lock(lock_path):
            atomic_write_text(
                path, dump_document(doc, profile.file_format), follow_symlinks=True
            )

    def list(self) -> dict[str, Any]:
        manifest = self.store.load()
        result = {}
        for harness, record in manifest.configs.items():
            result[harness] = {
                "capturedAt": record.capturedAt,
                "revision": record.revision,
                "preferences": record.preferences,
            }
        return result

    def diff(self, harness: str) -> dict[str, Any]:
        if self._get_binding_profile(harness) is None:
            raise MutationError(
                f"{harness} is not a harness with a managed config.",
                status=404,
                code="unknown_harness",
            )

        manifest = self.store.load()
        record = manifest.configs.get(harness)
        local_prefs = self._extract_local(harness)

        # A known harness that has never been captured is "unmanaged", which is a
        # real state — distinct from the unknown name rejected above.
        if not record:
            return {"state": "unmanaged", "missing": [], "extra": [], "changed": []}

        if local_prefs == record.preferences:
            return {"state": "managed", "missing": [], "extra": [], "changed": []}

        missing = sorted(set(record.preferences) - set(local_prefs))
        extra = sorted(set(local_prefs) - set(record.preferences))
        changed = sorted(
            k
            for k in set(record.preferences) & set(local_prefs)
            if record.preferences[k] != local_prefs[k]
        )

        return {
            "state": "drifted",
            "missing": missing,
            "extra": extra,
            "changed": changed,
        }
