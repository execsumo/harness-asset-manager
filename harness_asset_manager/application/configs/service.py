from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness_asset_manager.application.asset_tags import AssetTagService
from harness_asset_manager.atomic_files import atomic_write_text, file_lock
from harness_asset_manager.config_document import (
    ConfigDocumentError,
    dump_config_document,
    load_config_document,
)
from harness_asset_manager.errors import MutationError
from harness_asset_manager.harness import (
    ConfigSubtreeBindingProfile,
    HarnessKernelService,
)

from .extraction import extract_preferences
from .model import ConfigRecord
from .store import ConfigStore


class ConfigsService:
    def __init__(self, store: ConfigStore, kernel: HarnessKernelService, asset_tag_service: AssetTagService) -> None:
        self.store = store
        self.kernel = kernel
        self.asset_tag_service = asset_tag_service

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
        doc = _read(path, profile.file_format, harness_name)
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
            record = manifest.configs.get(harness)
            
            config_path = binding.profile.resolve_config_path(self.kernel.context)
            if not record or not config_path.is_file():
                continue
                
            local_prefs = self._extract_local(harness)
            local_hash = self._hash_prefs(local_prefs)

            if not explicit and record.preferences != local_prefs:
                continue

            new_record = ConfigRecord(
                sourceFile=str(config_path),
                preferences=local_prefs,
                capturedAt=datetime.now(timezone.utc).isoformat(),
                revision=local_hash,
            )
            self.store.write_config(harness, new_record)

    def enable(self, harness: str) -> None:
        """Enable managing a harness's config by capturing it."""
        binding = self._get_binding_profile(harness)
        if not binding:
            raise MutationError(
                f"{harness} is not a harness with a config binding.",
                status=404,
                code="unknown_harness",
            )
            
        config_path = binding.resolve_config_path(self.kernel.context)
        if not config_path.is_file():
            raise MutationError(
                f"{harness} has no config file to manage.",
                status=409,
                code="missing_config_file",
            )
        
        local_prefs = self._extract_local(harness)
        local_hash = self._hash_prefs(local_prefs)
        new_record = ConfigRecord(
            sourceFile=str(config_path),
            preferences=local_prefs,
            capturedAt=datetime.now(timezone.utc).isoformat(),
            revision=local_hash,
        )
        self.store.write_config(harness, new_record)

    def disable(self, harness: str) -> None:
        """Disable managing a harness's config by removing it from the manifest."""
        if not self._get_binding_profile(harness):
            raise MutationError(
                f"{harness} is not a harness with a config binding.",
                status=404,
                code="unknown_harness",
            )
        self.store.remove_config(harness)

    def restore(self, harness: str) -> None:
        """Restore preferences from manifest to the local file."""
        profile = self._get_binding_profile(harness)
        if not profile:
            raise MutationError(
                f"{harness} is not a harness with a managed config.",
                status=404,
                code="unknown_harness",
            )

        manifest = self.store.load()
        record = manifest.configs.get(harness)
        if not record:
            raise MutationError(
                f"{harness} has no captured preferences to restore.",
                status=404,
                code="not_captured",
            )

        path = profile.resolve_config_path(self.kernel.context)
        doc = _read(path, profile.file_format, harness)
        for key, value in record.preferences.items():
            doc[key] = value

        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(path.suffix + ".lock")
        with file_lock(lock_path):
            atomic_write_text(
                path,
                dump_config_document(doc, file_format=profile.file_format),
                follow_symlinks=True,
            )

    def list(self) -> dict[str, Any]:
        manifest = self.store.load()
        result = {}
        for binding in self.kernel.bindings_for_family("configs"):
            harness = binding.definition.harness
            record = manifest.configs.get(harness)
            local_prefs = self._extract_local(harness)
            config_path = binding.profile.resolve_config_path(self.kernel.context)
            
            if not record or not config_path.is_file():
                result[harness] = {
                    "managed": False,
                    "keyCount": 0,
                    "driftState": "—",
                    "sourceFile": str(config_path),
                    "capturedAt": None,
                    "preferences": {},
                    "tags": self.asset_tag_service.get_tags("configs", harness)
                }
            else:
                key_count = len(record.preferences)
                if local_prefs == record.preferences:
                    drift_state = "—"
                else:
                    drift_state = "drifted"
                    
                result[harness] = {
                    "managed": True,
                    "keyCount": key_count,
                    "driftState": drift_state,
                    "sourceFile": record.sourceFile,
                    "capturedAt": record.capturedAt,
                    "preferences": record.preferences,
                    "tags": self.asset_tag_service.get_tags("configs", harness)
                }
        return result

    def diff(self, harness: str) -> dict[str, Any]:
        profile = self._get_binding_profile(harness)
        if profile is None:
            raise MutationError(
                f"{harness} is not a harness with a managed config.",
                status=404,
                code="unknown_harness",
            )

        manifest = self.store.load()
        record = manifest.configs.get(harness)
        local_prefs = self._extract_local(harness)
        config_path = profile.resolve_config_path(self.kernel.context)

        if not record or not config_path.is_file():
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

def _read(path: Path, file_format: str, harness: str) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return load_config_document(path.read_text(encoding="utf-8"), file_format=file_format)
    except ConfigDocumentError as error:
        raise MutationError(f"{harness} config file is {error}", status=409) from error
