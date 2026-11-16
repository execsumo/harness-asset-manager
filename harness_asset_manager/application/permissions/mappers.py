from __future__ import annotations

import hashlib
from typing import Callable, Iterable, Mapping, Protocol

from harness_asset_manager.errors import MutationError

from .default_policy import (
    PolicyRecord,
    claim_default_policy,
    owns_default_policy,
    release_default_policy,
)
from .store import PermissionSpec


class RawPermissionEntry:
    def __init__(self, id: str, decision: str, scope: str, pattern: str | None, payload: dict[str, object]):
        self.id = id
        self.decision = decision
        self.scope = scope
        self.pattern = pattern
        self.payload = payload


def _manual_rule_id(rule: str) -> str:
    return f"manual:{hashlib.sha256(rule.encode('utf-8')).hexdigest()[:16]}"


def _ambiguous_permission(id: str, detail: str) -> MutationError:
    return MutationError(
        f"Permission '{id}': {detail}, so the rule Harness Asset Manager wrote cannot be "
        "identified. Remove the extra copies by hand, then retry.",
        status=409,
    )


def _managed_deny_rules(
    deny: list[object],
    id: str,
    *,
    spec: PermissionSpec | None,
    pattern: str | None,
    spec_rules: Callable[[PermissionSpec], list[str]],
    parse_rule: Callable[[str], tuple[str, str | None]],
) -> set[str]:
    """The deny-list rule strings that make up managed permission ``id``.

    An adopted rule is identified by its own hash, so a rule the app never wrote is
    never mistaken for it. Otherwise the managed spec renders the exact rules the app
    wrote. With neither, a bare ``pattern`` is resolved to the one scope it appears
    under in the deny list, refusing when it appears under several.
    """
    rules = [rule for rule in deny if isinstance(rule, str)]
    if id.startswith("manual:"):
        adopted = {rule for rule in rules if _manual_rule_id(rule) == id}
        if adopted:
            return adopted
    if spec is not None:
        return set(spec_rules(spec))
    if not pattern:
        return set()
    by_scope: dict[str, set[str]] = {}
    for rule in rules:
        scope, rule_pattern = parse_rule(rule)
        if rule_pattern == pattern:
            by_scope.setdefault(scope, set()).add(rule)
    if len(by_scope) > 1:
        raise _ambiguous_permission(
            id, f"pattern '{pattern}' is denied under several scopes ({', '.join(sorted(by_scope))})"
        )
    return next(iter(by_scope.values()), set())


def _remove_deny_rules(permissions_subtree: dict[str, object], id: str, targets: set[str]) -> bool:
    """Remove each target rule from the deny list once. Allow and ask are never touched."""
    deny = permissions_subtree.get("deny")
    if not isinstance(deny, list):
        return False
    present = sorted(rule for rule in targets if rule in deny)
    duplicated = [rule for rule in present if deny.count(rule) > 1]
    if duplicated:
        raise _ambiguous_permission(id, f"the deny list holds {', '.join(duplicated)} more than once")
    if not present:
        return False
    for rule in present:
        deny.remove(rule)
    if not deny:
        permissions_subtree.pop("deny", None)
    return True


class PermissionMapper(Protocol):
    """Translates between PermissionSpec and a single harness's permission configuration shape."""

    def read_entries(self, document: dict[str, object], specs: Iterable[PermissionSpec] = ()) -> list[RawPermissionEntry]: ...

    def enable_permission(
        self,
        document: dict[str, object],
        spec: PermissionSpec,
        *,
        policy: PolicyRecord | None = None,
        legacy: bool = False,
    ) -> PolicyRecord:
        """Add the managed rule and claim only the default policy the user has not set.

        Other decision lists and user rules are never touched. ``policy`` is the
        harness's ownership record (updated and returned); see ``default_policy``.
        """
        ...

    def disable_permission(
        self,
        document: dict[str, object],
        id: str,
        pattern: str | None = None,
        *,
        spec: PermissionSpec | None = None,
        policy: PolicyRecord | None = None,
    ) -> bool:
        """Remove only the rule the app wrote or adopted, and only policy it owns.

        With a ``policy`` record, the defaults restored are exactly those it says the
        app wrote; without one (state from before records existed) a default is
        removed when it still holds the app's value.

        Returns whether anything changed; raises a 409 ``MutationError`` when the
        managed rule cannot be told apart from look-alikes.
        """
        ...

    def denylist_empty(self, document: Mapping[str, object]) -> bool:
        """Whether no deny rule is left that the owned default policy serves."""
        ...

    def spec_to_dict(self, spec: PermissionSpec) -> dict[str, object]: ...

    def dict_to_spec(
        self,
        decision: str,
        scope: str,
        pattern: str | None,
        raw: Mapping[str, object],
    ) -> PermissionSpec: ...

    def representable(self, spec: PermissionSpec) -> tuple[bool, str | None, str | None]: ...


def _rules(payload: Mapping[str, object]) -> list[str]:
    rules = payload.get("rules")
    return [rule for rule in rules if isinstance(rule, str)] if isinstance(rules, list) else []


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

    def enable_permission(
        self,
        document: dict[str, object],
        spec: PermissionSpec,
        *,
        policy: PolicyRecord | None = None,
        legacy: bool = False,
    ) -> PolicyRecord:
        if "permissions" not in document:
            document["permissions"] = {}
        permissions_subtree = document["permissions"]
        if not isinstance(permissions_subtree, dict):
            raise MutationError("The top-level 'permissions' key is not an object", status=409)

        # A denylist is only useful as the sole policy when the harness does
        # not put unmatched requests back through its approval flow.  Deny
        # rules are evaluated before this mode, so recorded rules still block.
        record: PolicyRecord = {} if policy is None else policy
        claim_default_policy(
            document, ("permissions", "defaultMode"), "bypassPermissions", record, legacy=legacy
        )

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

        return record

    def disable_permission(
        self,
        document: dict[str, object],
        id: str,
        pattern: str | None = None,
        *,
        spec: PermissionSpec | None = None,
        policy: PolicyRecord | None = None,
    ) -> bool:
        permissions_subtree = document.get("permissions")
        if not isinstance(permissions_subtree, dict):
            return False
        deny = permissions_subtree.get("deny")
        if not isinstance(deny, list):
            return False

        targets = _managed_deny_rules(
            deny,
            id,
            spec=spec,
            pattern=pattern,
            spec_rules=lambda managed: _rules(self.spec_to_dict(managed)),
            parse_rule=self._parse_rule_string,
        )
        if not _remove_deny_rules(permissions_subtree, id, targets):
            return False

        # The mode is part of HAM's denylist adoption, not a permanent global
        # setting after the last deny rule is removed. A different value is the
        # user's own choice and stays.
        if self.denylist_empty(document):
            if policy is not None:
                release_default_policy(document, policy)
            elif permissions_subtree.get("defaultMode") == "bypassPermissions":
                permissions_subtree.pop("defaultMode", None)
        if not permissions_subtree:
            document.pop("permissions", None)
        return True

    def denylist_empty(self, document: Mapping[str, object]) -> bool:
        permissions_subtree = document.get("permissions")
        return not (isinstance(permissions_subtree, Mapping) and permissions_subtree.get("deny"))

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

    def enable_permission(
        self,
        document: dict[str, object],
        spec: PermissionSpec,
        *,
        policy: PolicyRecord | None = None,
        legacy: bool = False,
    ) -> PolicyRecord:
        if "permissions" not in document:
            document["permissions"] = {}
        permissions_subtree = document["permissions"]
        if not isinstance(permissions_subtree, dict):
            raise MutationError("The top-level 'permissions' key is not an object", status=409)

        # Antigravity's request-review default prompts for unlisted actions.
        # always-proceed makes the deny list the only HAM-managed decision
        # boundary; native deny rules still take precedence.
        record: PolicyRecord = {} if policy is None else policy
        claim_default_policy(document, ("toolPermission",), "always-proceed", record, legacy=legacy)

        expected_rules = self.spec_to_dict(spec)["rules"]

        if spec.decision not in permissions_subtree:
            permissions_subtree[spec.decision] = []
        target_list = permissions_subtree[spec.decision]
        if not isinstance(target_list, list):
            raise MutationError(f"The permission decision '{spec.decision}' is not an array", status=409)

        for rule in expected_rules:
            if rule not in target_list:
                target_list.append(rule)

        return record

    def disable_permission(
        self,
        document: dict[str, object],
        id: str,
        pattern: str | None = None,
        *,
        spec: PermissionSpec | None = None,
        policy: PolicyRecord | None = None,
    ) -> bool:
        permissions_subtree = document.get("permissions")
        if not isinstance(permissions_subtree, dict):
            return False
        deny = permissions_subtree.get("deny")
        if not isinstance(deny, list):
            return False

        targets = _managed_deny_rules(
            deny,
            id,
            spec=spec,
            pattern=pattern,
            spec_rules=lambda managed: _rules(self.spec_to_dict(managed)),
            parse_rule=self._parse_rule_string,
        )
        if not _remove_deny_rules(permissions_subtree, id, targets):
            return False

        if not permissions_subtree:
            document.pop("permissions", None)
        if self.denylist_empty(document):
            if policy is not None:
                release_default_policy(document, policy)
            elif document.get("toolPermission") == "always-proceed":
                document.pop("toolPermission", None)
        return True

    def denylist_empty(self, document: Mapping[str, object]) -> bool:
        permissions_subtree = document.get("permissions")
        return not (isinstance(permissions_subtree, Mapping) and permissions_subtree.get("deny"))

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

    def enable_permission(
        self,
        document: dict[str, object],
        spec: PermissionSpec,
        *,
        policy: PolicyRecord | None = None,
        legacy: bool = False,
    ) -> PolicyRecord:
        document.setdefault("version", 1)
        editor = document.setdefault("editor", {})
        if isinstance(editor, dict):
            editor.setdefault("vimMode", False)

        record: PolicyRecord = {} if policy is None else policy
        claim_default_policy(document, ("approvalMode",), "unrestricted", record, legacy=legacy)

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
        return record

    def disable_permission(
        self,
        document: dict[str, object],
        id: str,
        pattern: str | None = None,
        *,
        spec: PermissionSpec | None = None,
        policy: PolicyRecord | None = None,
    ) -> bool:
        permissions_subtree = document.get("permissions")
        if not isinstance(permissions_subtree, dict):
            return False
        deny = permissions_subtree.get("deny")
        if not isinstance(deny, list):
            return False

        targets = _managed_deny_rules(
            deny,
            id,
            spec=spec,
            pattern=pattern,
            spec_rules=lambda managed: _rules(self.spec_to_dict(managed)),
            parse_rule=self._parse_rule_string,
        )
        if not _remove_deny_rules(permissions_subtree, id, targets):
            return False

        if not permissions_subtree:
            document.pop("permissions", None)
        if self.denylist_empty(document):
            if policy is not None:
                release_default_policy(document, policy)
            elif document.get("approvalMode") == "unrestricted":
                document.pop("approvalMode", None)
        return True

    def denylist_empty(self, document: Mapping[str, object]) -> bool:
        permissions_subtree = document.get("permissions")
        return not (isinstance(permissions_subtree, Mapping) and permissions_subtree.get("deny"))

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

    def enable_permission(
        self,
        document: dict[str, object],
        spec: PermissionSpec,
        *,
        policy: PolicyRecord | None = None,
        legacy: bool = False,
    ) -> PolicyRecord:
        if "permissions" not in document:
            document["permissions"] = {}
        perms = document["permissions"]
        if not isinstance(perms, dict):
            raise MutationError("The 'permissions' key is not an object", status=409)

        # Activate HAM's profile and disable approval prompts.  Without
        # default_permissions, Codex merely stores this profile and continues
        # using its normal approval/sandbox defaults.  The two go together: with
        # the user's own profile active, turning prompts off would drop their
        # approval flow while none of HAM's rules apply.
        record: PolicyRecord = {} if policy is None else policy
        if claim_default_policy(
            document, ("default_permissions",), "harness-asset-manager", record, legacy=legacy
        ):
            claim_default_policy(document, ("approval_policy",), "never", record, legacy=legacy)
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
        return record

    def disable_permission(
        self,
        document: dict[str, object],
        id: str,
        pattern: str | None = None,
        *,
        spec: PermissionSpec | None = None,
        policy: PolicyRecord | None = None,
    ) -> bool:
        perms = document.get("permissions")
        if not isinstance(perms, dict):
            return False
        sm_profile = perms.get("harness-asset-manager")
        if not isinstance(sm_profile, dict):
            return False
        filesystem = sm_profile.get("filesystem")
        network = sm_profile.get("network")
        domains = network.get("domains") if isinstance(network, dict) else None

        # A rule is one key in one table: filesystem rules for file scopes, network
        # domains for web. The app only ever writes "deny" there, so another value
        # under the same key is not the managed rule.
        target = self._managed_rule(id, pattern, spec, filesystem, domains)
        if target is None:
            return False
        table, key = target
        table.pop(key, None)

        if isinstance(filesystem, dict) and not filesystem:
            sm_profile.pop("filesystem", None)
        if isinstance(network, dict):
            # Keep the allow-by-default network baseline while any HAM filesystem
            # deny remains active. It is removed with the profile once the final HAM
            # rule is disabled, unless the user added settings of their own to it.
            has_filesystem_rules = isinstance(filesystem, dict) and bool(filesystem)
            if (
                not network.get("domains")
                and not has_filesystem_rules
                and set(network) <= {"enabled", "mode", "domains"}
            ):
                sm_profile.pop("network", None)

        if len(sm_profile) <= 1 and "extends" in sm_profile:
            perms.pop("harness-asset-manager", None)
        if not perms:
            document.pop("permissions", None)

        # The app activates its profile and turns off approval prompts together. If
        # the user has since pointed default_permissions elsewhere, both settings are
        # theirs now.
        if "harness-asset-manager" in perms:
            return True
        if policy is not None:
            if owns_default_policy(policy, ("default_permissions",)):
                release_default_policy(document, policy)
        elif document.get("default_permissions") == "harness-asset-manager":
            document.pop("default_permissions", None)
            if document.get("approval_policy") == "never":
                document.pop("approval_policy", None)
        return True

    def denylist_empty(self, document: Mapping[str, object]) -> bool:
        perms = document.get("permissions")
        return not (isinstance(perms, Mapping) and "harness-asset-manager" in perms)

    def _managed_rule(
        self,
        id: str,
        pattern: str | None,
        spec: PermissionSpec | None,
        filesystem: object,
        domains: object,
    ) -> tuple[dict[str, object], str] | None:
        def denied(table: object, key: str | None) -> tuple[dict[str, object], str] | None:
            if isinstance(table, dict) and key is not None and table.get(key) == "deny":
                return table, key
            return None

        if spec is not None:
            if spec.scope in ("file_read", "file_write"):
                return denied(filesystem, spec.pattern)
            if spec.scope == "web":
                return denied(domains, spec.pattern)
            return None
        if id.startswith("manual:fs_deny:"):
            return denied(filesystem, id[len("manual:fs_deny:") :])
        if id.startswith("manual:net_deny:"):
            return denied(domains, id[len("manual:net_deny:") :])
        if not pattern:
            return None
        matches = [match for match in (denied(filesystem, pattern), denied(domains, pattern)) if match]
        if len(matches) > 1:
            raise _ambiguous_permission(id, f"pattern '{pattern}' is denied for both filesystem and network")
        return matches[0] if matches else None


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
