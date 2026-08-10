from __future__ import annotations

import hashlib
from typing import Iterable, Mapping, Protocol

from harness_asset_manager.errors import MutationError

from .store import PermissionSpec


class RawPermissionEntry:
    def __init__(self, id: str, decision: str, scope: str, pattern: str | None, payload: dict[str, object]):
        self.id = id
        self.decision = decision
        self.scope = scope
        self.pattern = pattern
        self.payload = payload


class PermissionMapper(Protocol):
    """Translates between PermissionSpec and a single harness's permission configuration shape."""

    def read_entries(self, document: dict[str, object], specs: Iterable[PermissionSpec] = ()) -> list[RawPermissionEntry]: ...

    def enable_permission(self, document: dict[str, object], spec: PermissionSpec) -> None: ...

    def disable_permission(self, document: dict[str, object], id: str, pattern: str | None = None) -> None: ...

    def spec_to_dict(self, spec: PermissionSpec) -> dict[str, object]: ...

    def dict_to_spec(
        self,
        decision: str,
        scope: str,
        pattern: str | None,
        raw: Mapping[str, object],
    ) -> PermissionSpec: ...

    def representable(self, spec: PermissionSpec) -> tuple[bool, str | None, str | None]: ...


class ClaudeCodePermissionsMapper:
    """Mapper for Claude Code permissions under ~/.claude/settings.json."""

    def representable(self, spec: PermissionSpec) -> tuple[bool, str | None, str | None]:
        supported_decisions = {"deny"}
        if spec.decision not in supported_decisions:
            return False, f"HAM operates in Denylist ONLY mode (decision '{spec.decision}' is unsupported)", None

        supported_scopes = {"shell", "file_read", "file_write", "web", "mcp"}
        if spec.scope not in supported_scopes:
            return False, f"Scope '{spec.scope}' is not supported by Claude Code", None

        return True, None, None

    def spec_to_dict(self, spec: PermissionSpec) -> dict[str, object]:
        if spec.scope == "shell":
            return {"rules": [f"Bash({spec.pattern})"]}
        elif spec.scope == "file_read":
            return {"rules": [f"Read({spec.pattern})"]}
        elif spec.scope == "file_write":
            return {"rules": [f"Edit({spec.pattern})", f"Write({spec.pattern})"]}
        elif spec.scope == "web":
            return {"rules": [f"WebFetch({spec.pattern})"]}
        elif spec.scope == "mcp":
            if not spec.pattern:
                return {"rules": []}
            if "/" in spec.pattern:
                server, tool = spec.pattern.split("/", 1)
                return {"rules": [f"mcp__{server}__{tool}"]}
            elif spec.pattern.endswith("/*"):
                server = spec.pattern[:-2]
                return {"rules": [f"mcp__{server}"]}
            else:
                server = spec.pattern
                return {"rules": [f"mcp__{server}"]}
        return {"rules": []}

    def dict_to_spec(
        self,
        decision: str,
        scope: str,
        pattern: str | None,
        raw: Mapping[str, object],
    ) -> PermissionSpec:
        return PermissionSpec(
            id="",
            decision=decision,
            scope=scope,
            pattern=pattern,
        )

    def read_entries(self, document: dict[str, object], specs: Iterable[PermissionSpec] = ()) -> list[RawPermissionEntry]:
        permissions_subtree = document.get("permissions")
        if not isinstance(permissions_subtree, dict):
            return []

        entries: list[RawPermissionEntry] = []
        specs_list = list(specs)

        for decision in ("deny",):
            rules_list = permissions_subtree.get(decision, [])
            if not isinstance(rules_list, list):
                continue

            unprocessed = set(str(r) for r in rules_list)
            yielded_spec_ids: set[str] = set()

            # First pass: find exact matches for all representable specs
            for spec in specs_list:
                is_repr, _, _ = self.representable(spec)
                if not is_repr or spec.decision != decision:
                    continue

                expected = set(self.spec_to_dict(spec)["rules"])
                if expected and expected.issubset(unprocessed):
                    entries.append(
                        RawPermissionEntry(
                            id=spec.id,
                            decision=decision,
                            scope=spec.scope,
                            pattern=spec.pattern,
                            payload={"rules": sorted(list(expected))},
                        )
                    )
                    unprocessed -= expected
                    yielded_spec_ids.add(spec.id)

            # Second pass: partial matches (e.g. file_write has only one of Edit/Write)
            for spec in specs_list:
                if spec.id in yielded_spec_ids:
                    continue
                is_repr, _, _ = self.representable(spec)
                if not is_repr:
                    continue

                expected = self.spec_to_dict(spec)["rules"]
                found = [r for r in expected if r in unprocessed]
                if found:
                    entries.append(
                        RawPermissionEntry(
                            id=spec.id,
                            decision=decision,
                            scope=spec.scope,
                            pattern=spec.pattern,
                            payload={"rules": sorted(found)},
                        )
                    )
                    unprocessed -= set(found)
                    yielded_spec_ids.add(spec.id)

            # Third pass: unmanaged/manual rule strings
            for rule_string in sorted(unprocessed):
                scope, pattern = self._parse_rule_string(rule_string)
                hash_id = hashlib.sha256(rule_string.encode("utf-8")).hexdigest()[:16]
                entries.append(
                    RawPermissionEntry(
                        id=f"manual:{hash_id}",
                        decision=decision,
                        scope=scope,
                        pattern=pattern,
                        payload={"rules": [rule_string]},
                    )
                )

        return entries

    def enable_permission(self, document: dict[str, object], spec: PermissionSpec) -> None:
        if "permissions" not in document:
            document["permissions"] = {}
        permissions_subtree = document["permissions"]
        if not isinstance(permissions_subtree, dict):
            raise MutationError("The top-level 'permissions' key is not an object", status=409)

        # A denylist is only useful as the sole policy when the harness does
        # not put unmatched requests back through its approval flow.  Deny
        # rules are evaluated before this mode, so recorded rules still block.
        permissions_subtree["defaultMode"] = "bypassPermissions"

        expected_rules = self.spec_to_dict(spec)["rules"]

        # Ensure target decision array has these rules
        if spec.decision not in permissions_subtree:
            permissions_subtree[spec.decision] = []
        target_list = permissions_subtree[spec.decision]
        if not isinstance(target_list, list):
            raise MutationError(f"The permission decision '{spec.decision}' is not an array", status=409)

        for rule in expected_rules:
            if rule not in target_list:
                target_list.append(rule)

        # Remove these rules from other decision arrays to avoid conflicts
        for other_decision in ("allow", "deny", "ask"):
            if other_decision == spec.decision:
                continue
            other_list = permissions_subtree.get(other_decision)
            if isinstance(other_list, list):
                permissions_subtree[other_decision] = [r for r in other_list if r not in expected_rules]
                if not permissions_subtree[other_decision]:
                    permissions_subtree.pop(other_decision, None)

    def disable_permission(self, document: dict[str, object], id: str, pattern: str | None = None) -> None:
        permissions_subtree = document.get("permissions")
        if not isinstance(permissions_subtree, dict):
            return

        def rule_matches(rule_string: str) -> bool:
            rule_hash = hashlib.sha256(rule_string.encode("utf-8")).hexdigest()[:16]
            if f"manual:{rule_hash}" == id:
                return True
            if pattern:
                candidates = [
                    f"Bash({pattern})",
                    f"Read({pattern})",
                    f"Edit({pattern})",
                    f"Write({pattern})",
                    f"MultiEdit({pattern})",
                    f"NotebookEdit({pattern})",
                    f"WebFetch({pattern})",
                ]
                if "/" in pattern:
                    s, t = pattern.split("/", 1)
                    candidates.append(f"mcp__{s}__{t}")
                else:
                    candidates.append(f"mcp__{pattern}")
                    if pattern.endswith("/*"):
                        candidates.append(f"mcp__{pattern[:-2]}")
                if rule_string in candidates:
                    return True
            return False

        for decision in ("allow", "deny", "ask"):
            rules_list = permissions_subtree.get(decision)
            if isinstance(rules_list, list):
                permissions_subtree[decision] = [r for r in rules_list if not rule_matches(r)]
                if not permissions_subtree[decision]:
                    permissions_subtree.pop(decision, None)

        if not permissions_subtree:
            document.pop("permissions", None)
        elif not permissions_subtree.get("deny"):
            # The mode is part of HAM's denylist adoption, not a permanent
            # global setting after the last adopted rule is removed.
            permissions_subtree.pop("defaultMode", None)
            if not permissions_subtree:
                document.pop("permissions", None)

    def _parse_rule_string(self, rule: str) -> tuple[str, str | None]:
        if rule.startswith("Bash(") and rule.endswith(")"):
            return "shell", rule[5:-1]
        if rule.startswith("Read(") and rule.endswith(")"):
            return "file_read", rule[5:-1]
        if (rule.startswith("Edit(") or rule.startswith("Write(") or
            rule.startswith("MultiEdit(") or rule.startswith("NotebookEdit(")) and rule.endswith(")"):
            idx = rule.find("(")
            return "file_write", rule[idx+1:-1]
        if rule.startswith("WebFetch(") and rule.endswith(")"):
            return "web", rule[9:-1]
        if rule.startswith("mcp__"):
            parts = rule.split("__")
            if len(parts) >= 3:
                return "mcp", f"{parts[1]}/{parts[2]}"
            elif len(parts) == 2:
                return "mcp", parts[1]
        return "any", None


class AntigravityPermissionsMapper:
    """Mapper for Antigravity permissions under ~/.gemini/antigravity-cli/settings.json."""

    def representable(self, spec: PermissionSpec) -> tuple[bool, str | None, str | None]:
        supported_decisions = {"deny"}
        if spec.decision not in supported_decisions:
            return False, f"HAM operates in Denylist ONLY mode (decision '{spec.decision}' is unsupported)", None

        supported_scopes = {"shell", "mcp"}
        if spec.scope not in supported_scopes:
            return False, f"Scope '{spec.scope}' is not supported by Antigravity", None

        return True, None, None

    def spec_to_dict(self, spec: PermissionSpec) -> dict[str, object]:
        if spec.scope == "shell":
            return {"rules": [f"command({spec.pattern})"]}
        elif spec.scope == "mcp":
            return {"rules": [f"mcp({spec.pattern})"]}
        return {"rules": []}

    def dict_to_spec(
        self,
        decision: str,
        scope: str,
        pattern: str | None,
        raw: Mapping[str, object],
    ) -> PermissionSpec:
        return PermissionSpec(
            id="",
            decision=decision,
            scope=scope,
            pattern=pattern,
        )

    def read_entries(self, document: dict[str, object], specs: Iterable[PermissionSpec] = ()) -> list[RawPermissionEntry]:
        permissions_subtree = document.get("permissions")
        if not isinstance(permissions_subtree, dict):
            return []

        entries: list[RawPermissionEntry] = []
        specs_list = list(specs)

        for decision in ("deny",):
            rules_list = permissions_subtree.get(decision, [])
            if not isinstance(rules_list, list):
                continue

            unprocessed = set(str(r) for r in rules_list)
            yielded_spec_ids: set[str] = set()

            # First pass: find exact matches
            for spec in specs_list:
                is_repr, _, _ = self.representable(spec)
                if not is_repr or spec.decision != decision:
                    continue

                expected = set(self.spec_to_dict(spec)["rules"])
                if expected and expected.issubset(unprocessed):
                    entries.append(
                        RawPermissionEntry(
                            id=spec.id,
                            decision=decision,
                            scope=spec.scope,
                            pattern=spec.pattern,
                            payload={"rules": sorted(list(expected))},
                        )
                    )
                    unprocessed -= expected
                    yielded_spec_ids.add(spec.id)

            # Second pass: partial matches (normally 1-to-1 but for robustness)
            for spec in specs_list:
                if spec.id in yielded_spec_ids:
                    continue
                is_repr, _, _ = self.representable(spec)
                if not is_repr:
                    continue

                expected = self.spec_to_dict(spec)["rules"]
                found = [r for r in expected if r in unprocessed]
                if found:
                    entries.append(
                        RawPermissionEntry(
                            id=spec.id,
                            decision=decision,
                            scope=spec.scope,
                            pattern=spec.pattern,
                            payload={"rules": sorted(found)},
                        )
                    )
                    unprocessed -= set(found)
                    yielded_spec_ids.add(spec.id)

            # Third pass: unmanaged
            for rule_string in sorted(unprocessed):
                scope, pattern = self._parse_rule_string(rule_string)
                hash_id = hashlib.sha256(rule_string.encode("utf-8")).hexdigest()[:16]
                entries.append(
                    RawPermissionEntry(
                        id=f"manual:{hash_id}",
                        decision=decision,
                        scope=scope,
                        pattern=pattern,
                        payload={"rules": [rule_string]},
                    )
                )

        return entries

    def enable_permission(self, document: dict[str, object], spec: PermissionSpec) -> None:
        if "permissions" not in document:
            document["permissions"] = {}
        permissions_subtree = document["permissions"]
        if not isinstance(permissions_subtree, dict):
            raise MutationError("The top-level 'permissions' key is not an object", status=409)

        # Antigravity's request-review default prompts for unlisted actions.
        # always-proceed makes the deny list the only HAM-managed decision
        # boundary; native deny rules still take precedence.
        document["toolPermission"] = "always-proceed"

        expected_rules = self.spec_to_dict(spec)["rules"]

        if spec.decision not in permissions_subtree:
            permissions_subtree[spec.decision] = []
        target_list = permissions_subtree[spec.decision]
        if not isinstance(target_list, list):
            raise MutationError(f"The permission decision '{spec.decision}' is not an array", status=409)

        for rule in expected_rules:
            if rule not in target_list:
                target_list.append(rule)

        for other_decision in ("allow", "deny", "ask"):
            if other_decision == spec.decision:
                continue
            other_list = permissions_subtree.get(other_decision)
            if isinstance(other_list, list):
                permissions_subtree[other_decision] = [r for r in other_list if r not in expected_rules]
                if not permissions_subtree[other_decision]:
                    permissions_subtree.pop(other_decision, None)

    def disable_permission(self, document: dict[str, object], id: str, pattern: str | None = None) -> None:
        permissions_subtree = document.get("permissions")
        if not isinstance(permissions_subtree, dict):
            return

        def rule_matches(rule_string: str) -> bool:
            rule_hash = hashlib.sha256(rule_string.encode("utf-8")).hexdigest()[:16]
            if f"manual:{rule_hash}" == id:
                return True
            if pattern:
                candidates = [
                    f"command({pattern})",
                    f"mcp({pattern})",
                ]
                if rule_string in candidates:
                    return True
            return False

        for decision in ("allow", "deny", "ask"):
            rules_list = permissions_subtree.get(decision)
            if isinstance(rules_list, list):
                permissions_subtree[decision] = [r for r in rules_list if not rule_matches(r)]
                if not permissions_subtree[decision]:
                    permissions_subtree.pop(decision, None)

        if not permissions_subtree:
            document.pop("permissions", None)
        if not permissions_subtree or not permissions_subtree.get("deny"):
            if document.get("toolPermission") == "always-proceed":
                document.pop("toolPermission", None)

    def _parse_rule_string(self, rule: str) -> tuple[str, str | None]:
        if rule.startswith("command(") and rule.endswith(")"):
            return "shell", rule[8:-1]
        if rule.startswith("mcp(") and rule.endswith(")"):
            return "mcp", rule[4:-1]
        return "any", None


class CursorPermissionsMapper:
    """Mapper for Cursor CLI permissions under ~/.cursor/cli-config.json."""

    def representable(self, spec: PermissionSpec) -> tuple[bool, str | None, str | None]:
        if spec.decision != "deny":
            return False, f"HAM operates in Denylist ONLY mode (decision '{spec.decision}' is unsupported)", None

        supported_scopes = {"shell", "file_read", "file_write", "web", "mcp"}
        if spec.scope not in supported_scopes:
            return False, f"Scope '{spec.scope}' is not supported by Cursor", None

        if spec.pattern is None or not spec.pattern:
            return False, "Cursor permission tokens require a non-empty pattern", None

        if spec.scope == "shell" and any(character.isspace() for character in spec.pattern):
            return (
                False,
                "Cursor Shell(...) only supports a single-token command name; shell patterns containing whitespace are not representable",
                None,
            )

        if spec.scope == "mcp" and "/" not in spec.pattern:
            return False, "Cursor Mcp(...) only supports server:tool; bare-server MCP patterns are not representable", None

        return True, None, None

    def spec_to_dict(self, spec: PermissionSpec) -> dict[str, object]:
        if spec.scope == "shell":
            return {"rules": [f"Shell({spec.pattern})"]}
        elif spec.scope == "file_read":
            return {"rules": [f"Read({spec.pattern})"]}
        elif spec.scope == "file_write":
            return {"rules": [f"Write({spec.pattern})"]}
        elif spec.scope == "web":
            return {"rules": [f"WebFetch({spec.pattern})"]}
        elif spec.scope == "mcp" and spec.pattern and "/" in spec.pattern:
            server, tool = spec.pattern.split("/", 1)
            return {"rules": [f"Mcp({server}:{tool})"]}
        return {"rules": []}

    def dict_to_spec(
        self,
        decision: str,
        scope: str,
        pattern: str | None,
        raw: Mapping[str, object],
    ) -> PermissionSpec:
        return PermissionSpec(
            id="",
            decision=decision,
            scope=scope,
            pattern=pattern,
        )

    def read_entries(self, document: dict[str, object], specs: Iterable[PermissionSpec] = ()) -> list[RawPermissionEntry]:
        permissions_subtree = document.get("permissions")
        if not isinstance(permissions_subtree, dict):
            return []

        rules_list = permissions_subtree.get("deny", [])
        if not isinstance(rules_list, list):
            return []

        entries: list[RawPermissionEntry] = []
        specs_list = list(specs)
        unprocessed = set(str(rule) for rule in rules_list)
        yielded_spec_ids: set[str] = set()

        # First pass: find exact matches for all representable specs.
        for spec in specs_list:
            is_repr, _, _ = self.representable(spec)
            if not is_repr:
                continue

            expected = set(self.spec_to_dict(spec)["rules"])
            if expected and expected.issubset(unprocessed):
                entries.append(
                    RawPermissionEntry(
                        id=spec.id,
                        decision="deny",
                        scope=spec.scope,
                        pattern=spec.pattern,
                        payload={"rules": sorted(list(expected))},
                    )
                )
                unprocessed -= expected
                yielded_spec_ids.add(spec.id)

        # Second pass: partial matches (kept for consistency with the other mappers).
        for spec in specs_list:
            if spec.id in yielded_spec_ids:
                continue
            is_repr, _, _ = self.representable(spec)
            if not is_repr:
                continue

            expected = self.spec_to_dict(spec)["rules"]
            found = [rule for rule in expected if rule in unprocessed]
            if found:
                entries.append(
                    RawPermissionEntry(
                        id=spec.id,
                        decision="deny",
                        scope=spec.scope,
                        pattern=spec.pattern,
                        payload={"rules": sorted(found)},
                    )
                )
                unprocessed -= set(found)
                yielded_spec_ids.add(spec.id)

        # Third pass: unmanaged/manual rule strings.
        for rule_string in sorted(unprocessed):
            scope, pattern = self._parse_rule_string(rule_string)
            hash_id = hashlib.sha256(rule_string.encode("utf-8")).hexdigest()[:16]
            entries.append(
                RawPermissionEntry(
                    id=f"manual:{hash_id}",
                    decision="deny",
                    scope=scope,
                    pattern=pattern,
                    payload={"rules": [rule_string]},
                )
            )

        return entries

    def enable_permission(self, document: dict[str, object], spec: PermissionSpec) -> None:
        document.setdefault("version", 1)
        editor = document.setdefault("editor", {})
        if isinstance(editor, dict):
            editor.setdefault("vimMode", False)

        if "permissions" not in document:
            document["permissions"] = {}
        permissions_subtree = document["permissions"]
        if not isinstance(permissions_subtree, dict):
            raise MutationError("The top-level 'permissions' key is not an object", status=409)

        expected_rules = self.spec_to_dict(spec)["rules"]
        if "deny" not in permissions_subtree:
            permissions_subtree["deny"] = []
        target_list = permissions_subtree["deny"]
        if not isinstance(target_list, list):
            raise MutationError("The permission decision 'deny' is not an array", status=409)

        for rule in expected_rules:
            if rule not in target_list:
                target_list.append(rule)

    def disable_permission(self, document: dict[str, object], id: str, pattern: str | None = None) -> None:
        permissions_subtree = document.get("permissions")
        if not isinstance(permissions_subtree, dict):
            return

        def rule_matches(rule_string: str) -> bool:
            rule_hash = hashlib.sha256(rule_string.encode("utf-8")).hexdigest()[:16]
            if f"manual:{rule_hash}" == id:
                return True
            if pattern:
                candidates = [
                    f"Shell({pattern})",
                    f"Read({pattern})",
                    f"Write({pattern})",
                    f"WebFetch({pattern})",
                ]
                if "/" in pattern:
                    server, tool = pattern.split("/", 1)
                    candidates.append(f"Mcp({server}:{tool})")
                if rule_string in candidates:
                    return True
            return False

        rules_list = permissions_subtree.get("deny")
        if isinstance(rules_list, list):
            permissions_subtree["deny"] = [rule for rule in rules_list if not rule_matches(str(rule))]
            if not permissions_subtree["deny"]:
                permissions_subtree.pop("deny", None)

        if not permissions_subtree:
            document.pop("permissions", None)

    def _parse_rule_string(self, rule: str) -> tuple[str, str | None]:
        if rule.startswith("Shell(") and rule.endswith(")"):
            return "shell", rule[6:-1]
        if rule.startswith("Read(") and rule.endswith(")"):
            return "file_read", rule[5:-1]
        if rule.startswith("Write(") and rule.endswith(")"):
            return "file_write", rule[6:-1]
        if rule.startswith("WebFetch(") and rule.endswith(")"):
            return "web", rule[9:-1]
        if rule.startswith("Mcp(") and rule.endswith(")"):
            value = rule[4:-1]
            if ":" in value:
                server, tool = value.split(":", 1)
                return "mcp", f"{server}/{tool}"
            return "mcp", value
        return "any", None


class CodexPermissionsMapper:
    """Mapper for OpenAI Codex permissions under ~/.codex/config.toml."""

    def representable(self, spec: PermissionSpec) -> tuple[bool, str | None, str | None]:
        if spec.decision != "deny":
            return False, f"HAM operates in Denylist ONLY mode (decision '{spec.decision}' is unsupported)", None

        supported_scopes = {"file_read", "file_write", "web"}
        if spec.scope not in supported_scopes:
            caveats = {
                "shell": "sandbox/approval govern shell",
                "mcp": "config.toml has no MCP allowlist",
                "any": None,
            }
            return False, f"Scope '{spec.scope}' is not supported by Codex config.toml", caveats.get(spec.scope)

        return True, None, None

    def spec_to_dict(self, spec: PermissionSpec) -> dict[str, object]:
        if spec.scope == "file_read":
            val = "read" if spec.decision == "allow" else "deny"
            return {"type": "filesystem", "pattern": spec.pattern, "value": val}
        elif spec.scope == "file_write":
            val = "write" if spec.decision == "allow" else "deny"
            return {"type": "filesystem", "pattern": spec.pattern, "value": val}
        elif spec.scope == "web":
            val = "allow" if spec.decision == "allow" else "deny"
            return {"type": "network", "pattern": spec.pattern, "value": val}
        return {}

    def dict_to_spec(
        self,
        decision: str,
        scope: str,
        pattern: str | None,
        raw: Mapping[str, object],
    ) -> PermissionSpec:
        return PermissionSpec(
            id="",
            decision=decision,
            scope=scope,
            pattern=pattern,
        )

    def read_entries(self, document: dict[str, object], specs: Iterable[PermissionSpec] = ()) -> list[RawPermissionEntry]:
        perms = document.get("permissions")
        if not isinstance(perms, dict):
            return []
        sm_profile = perms.get("harness-asset-manager")
        if not isinstance(sm_profile, dict):
            return []

        filesystem = sm_profile.get("filesystem", {})
        network = sm_profile.get("network", {})
        domains = network.get("domains", {}) if isinstance(network, dict) else {}

        entries: list[RawPermissionEntry] = []
        specs_list = list(specs)

        # Process filesystem rules (deny only)
        if isinstance(filesystem, dict):
            for pat, val in filesystem.items():
                if val == "deny":
                    matched_specs = [
                        spec for spec in specs_list
                        if spec.scope in ("file_read", "file_write") and spec.pattern == pat and spec.decision == "deny"
                    ]
                    if matched_specs:
                        for spec in matched_specs:
                            entries.append(
                                RawPermissionEntry(
                                    id=spec.id,
                                    decision="deny",
                                    scope=spec.scope,
                                    pattern=pat,
                                    payload={"type": "filesystem", "pattern": pat, "value": "deny"},
                                )
                            )
                    else:
                        entries.append(
                            RawPermissionEntry(
                                id=f"manual:fs_deny:{pat}",
                                decision="deny",
                                scope="file_read",
                                pattern=pat,
                                payload={"type": "filesystem", "pattern": pat, "value": "deny"},
                            )
                        )

        # Process network domains (deny only)
        if isinstance(domains, dict):
            for pat, val in domains.items():
                if val == "deny":
                    matched_id = None
                    for spec in specs_list:
                        if spec.scope == "web" and spec.pattern == pat and spec.decision == "deny":
                            matched_id = spec.id
                            break
                    id_ = matched_id if matched_id else f"manual:net_deny:{pat}"
                    entries.append(
                        RawPermissionEntry(
                            id=id_,
                            decision="deny",
                            scope="web",
                            pattern=pat,
                            payload={"type": "network", "pattern": pat, "value": "deny"},
                        )
                    )

        return entries

    def enable_permission(self, document: dict[str, object], spec: PermissionSpec) -> None:
        if "permissions" not in document:
            document["permissions"] = {}
        perms = document["permissions"]
        if not isinstance(perms, dict):
            raise MutationError("The 'permissions' key is not an object", status=409)

        # Activate HAM's profile and disable approval prompts.  Without
        # default_permissions, Codex merely stores this profile and continues
        # using its normal approval/sandbox defaults.
        document["approval_policy"] = "never"
        document["default_permissions"] = "harness-asset-manager"
        if "harness-asset-manager" not in perms:
            perms["harness-asset-manager"] = {"extends": ":workspace"}
        sm_profile = perms["harness-asset-manager"]
        if not isinstance(sm_profile, dict):
            raise MutationError("The 'permissions.harness-asset-manager' key is not an object", status=409)

        sm_profile["extends"] = ":workspace"

        # A denylist profile must allow unlisted network access.  Individual
        # domains recorded by HAM are then applied as explicit denies below.
        if "network" not in sm_profile:
            sm_profile["network"] = {}
        network = sm_profile["network"]
        if not isinstance(network, dict):
            raise MutationError("The 'permissions.harness-asset-manager.network' key is not an object", status=409)
        network["enabled"] = True
        network["mode"] = "allow"
        if "domains" not in network:
            network["domains"] = {}
        if not isinstance(network["domains"], dict):
            raise MutationError("The 'permissions.harness-asset-manager.network.domains' key is not an object", status=409)

        if spec.scope in ("file_read", "file_write"):
            if "filesystem" not in sm_profile:
                sm_profile["filesystem"] = {}
            fs = sm_profile["filesystem"]
            if not isinstance(fs, dict):
                raise MutationError("The 'permissions.harness-asset-manager.filesystem' key is not an object", status=409)

            if spec.decision == "deny":
                fs[spec.pattern] = "deny"
            elif spec.scope == "file_read":
                fs[spec.pattern] = "read"
            elif spec.scope == "file_write":
                fs[spec.pattern] = "write"

        elif spec.scope == "web":
            doms = network["domains"]
            assert isinstance(doms, dict)
            doms[spec.pattern] = "allow" if spec.decision == "allow" else "deny"

    def disable_permission(self, document: dict[str, object], id: str, pattern: str | None = None) -> None:
        perms = document.get("permissions")
        if not isinstance(perms, dict):
            return
        sm_profile = perms.get("harness-asset-manager")
        if not isinstance(sm_profile, dict):
            return

        filesystem = sm_profile.get("filesystem")
        if isinstance(filesystem, dict):
            for pat in list(filesystem.keys()):
                candidates = [
                    f"manual:fs_read:{pat}",
                    f"manual:fs_write:{pat}",
                    f"manual:fs_deny:{pat}"
                ]
                if id in candidates or pat == pattern:
                    filesystem.pop(pat, None)
            if not filesystem:
                sm_profile.pop("filesystem", None)

        network = sm_profile.get("network")
        if isinstance(network, dict):
            domains = network.get("domains")
            if isinstance(domains, dict):
                for pat in list(domains.keys()):
                    candidates = [
                        f"manual:net_allow:{pat}",
                        f"manual:net_deny:{pat}"
                    ]
                    if id in candidates or pat == pattern:
                        domains.pop(pat, None)
            # Keep the allow-by-default network baseline while any HAM
            # filesystem deny remains active.  It is removed with the profile
            # once the final HAM rule is disabled.
            has_filesystem_rules = isinstance(filesystem, dict) and bool(filesystem)
            if not network.get("domains") and not has_filesystem_rules:
                sm_profile.pop("network", None)

        if len(sm_profile) <= 1 and "extends" in sm_profile:
            perms.pop("harness-asset-manager", None)
        if not perms:
            document.pop("permissions", None)

        if "harness-asset-manager" not in perms:
            if document.get("default_permissions") == "harness-asset-manager":
                document.pop("default_permissions", None)
            if document.get("approval_policy") == "never":
                document.pop("approval_policy", None)


_MAPPERS: dict[str, PermissionMapper] = {
    "claude-code-permissions": ClaudeCodePermissionsMapper(),
    "antigravity-permissions": AntigravityPermissionsMapper(),
    "cursor-permissions": CursorPermissionsMapper(),
    "codex-permissions": CodexPermissionsMapper(),
}


def get_mapper(kind: str) -> PermissionMapper:
    if kind not in _MAPPERS:
        raise ValueError(f"unknown permissions mapper kind: {kind}")
    return _MAPPERS[kind]


__all__ = [
    "ClaudeCodePermissionsMapper",
    "AntigravityPermissionsMapper",
    "CursorPermissionsMapper",
    "CodexPermissionsMapper",
    "PermissionMapper",
    "RawPermissionEntry",
    "get_mapper",
]
