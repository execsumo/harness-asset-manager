from __future__ import annotations

from pathlib import Path
from typing import Callable

from .adapters import AgentHarnessAdapter, parse_codex_agent
from .ledger import AgentBindingLedger, AgentBindingRecord, classify_drift, hash_file
from .model import (
    AgentBinding,
    AgentDetail,
    AgentEntry,
    AgentHarnessDetail,
    AgentInventory,
    AgentIssue,
    AgentParseError,
    AgentTarget,
)
from .parser import parse_agent_file
from .store import AgentStore

TargetResolver = Callable[[], tuple[tuple[AgentTarget, ...], dict[str, AgentHarnessAdapter]]]


class AgentInventoryService:
    """Reads the agents inventory.

    Targets are resolved **per call**, not cached at construction: the user can
    enable or disable a harness in Settings at any time, and the matrix has to follow
    immediately, exactly as the skills read model does.

    This is also where binding drift is *named*. It is strictly read-only: the
    inventory says what happened to a binding, it never repairs one.
    """

    def __init__(
        self,
        store: AgentStore,
        resolve: TargetResolver,
        ledger: AgentBindingLedger,
    ) -> None:
        self.store = store
        self._resolve = resolve
        self.ledger = ledger

    @property
    def targets(self) -> tuple[AgentTarget, ...]:
        return self._resolve()[0]

    @property
    def adapters(self) -> dict[str, AgentHarnessAdapter]:
        return self._resolve()[1]

    def build(self) -> AgentInventory:
        targets, adapters = self._resolve()
        managed, issues = self.store.scan()
        issue_list = list(issues)
        # Read once per build, not per binding: the ledger is a single small file and
        # this runs on every list request.
        ledger_state = self.ledger.load()

        entries = [
            self._managed_entry(
                targets,
                adapters,
                agent.slug,
                agent.name,
                agent.description,
                ledger_state.get(agent.slug, {}),
                issue_list,
            )
            for agent in managed
        ]
        entries.extend(self._unmanaged_entries(targets, adapters, issue_list))
        return AgentInventory(
            columns=targets,
            entries=tuple(entries),
            issues=tuple(issue_list),
        )

    def detail(self, slug: str) -> AgentDetail | None:
        """Everything the detail view needs, including where each harness copy lives."""
        agent = self.store.get(slug)
        if agent is None:
            return None
        targets, adapters = self._resolve()
        records = self.ledger.load().get(slug, {})
        discarded_issues: list[AgentIssue] = []
        harnesses: list[AgentHarnessDetail] = []
        for target in targets:
            adapter = adapters[target.id]
            if not target.supports_agents:
                state, detail = "unsupported", target.unavailable_reason
                method = "none"
            else:
                method = "rendered" if adapter.renders else "symlink"
                if adapter.is_dangling(slug):
                    state, detail = "disabled", "symlink points at a missing file"
                elif adapter.is_enabled(slug):
                    state, detail = "enabled", None
                elif adapter.binding_path(slug).exists():
                    # Same diagnosis the matrix shows; the issue text belongs to the
                    # inventory, so it is dropped here rather than duplicated.
                    state = "disabled"
                    detail = self._diagnose_occupied_binding(
                        adapter, target, slug, records.get(target.id), discarded_issues
                    )
                else:
                    state, detail = "disabled", None
            harnesses.append(
                AgentHarnessDetail(
                    harness=target.id,
                    label=target.label,
                    logo_key=target.logo_key,
                    state=state,
                    detail=detail,
                    path=adapter.binding_path(slug),
                    install_method=method,
                    installed=target.installed,
                )
            )
        return AgentDetail(
            ref=agent.slug,
            name=agent.name,
            description=agent.description,
            prompt=agent.prompt,
            tools=agent.tools,
            document=agent.path.read_text(encoding="utf-8"),
            store_path=agent.path,
            harnesses=tuple(harnesses),
            can_delete=True,
            configuration=tuple(
                (key, _format_config_value(value)) for key, value in agent.extra_metadata
            ),
        )

    def _managed_entry(
        self,
        targets: tuple[AgentTarget, ...],
        adapters: dict[str, AgentHarnessAdapter],
        slug: str,
        name: str,
        description: str,
        records: dict[str, AgentBindingRecord],
        issues: list[AgentIssue],
    ) -> AgentEntry:
        bindings: list[AgentBinding] = []
        for target in targets:
            adapter = adapters[target.id]
            if not target.supports_agents:
                # Keeps the column for parity with the other families, but says why
                # rather than offering a toggle that cannot work.
                bindings.append(
                    AgentBinding(target.id, "unsupported", target.unavailable_reason)
                )
            elif adapter.is_dangling(slug):
                bindings.append(
                    AgentBinding(target.id, "disabled", "symlink points at a missing file")
                )
            elif adapter.is_enabled(slug):
                self._report_rendered_drift(adapter, target, slug, records.get(target.id), issues)
                bindings.append(AgentBinding(target.id, "enabled"))
            else:
                detail = None
                if adapter.binding_path(slug).exists():
                    detail = self._diagnose_occupied_binding(
                        adapter, target, slug, records.get(target.id), issues
                    )
                bindings.append(AgentBinding(target.id, "disabled", detail))
        return AgentEntry(
            ref=slug,
            name=name,
            description=description,
            kind="managed",
            harness_path=None,
            bindings=tuple(bindings),
            can_adopt=False,
            can_delete=True,
        )

    def _diagnose_occupied_binding(
        self,
        adapter: AgentHarnessAdapter,
        target: AgentTarget,
        slug: str,
        record: AgentBindingRecord | None,
        issues: list[AgentIssue],
    ) -> str:
        """Say *why* something we do not own sits at this binding path.

        Without a ledger record there is nothing to distinguish a binding a harness
        destroyed from an unrelated file that happens to share the name, so this
        reports exactly what it did before. With one, the two become separable — and
        in the one-sided case, provably so.
        """
        unknown = "a file we do not manage occupies this name"
        path = adapter.binding_path(slug)
        if record is None or path.is_symlink() or not path.is_file():
            return unknown

        # Cost rule: a ledger record is what earns the two hashes. Everything without
        # one stays a stat().
        kind = classify_drift(
            record=record,
            harness_sha256=_safe_hash(path),
            store_sha256=_safe_hash(self.store.path_for(slug)),
        )
        if kind == "collision":
            return unknown

        name = f"{target.id}/{slug}"
        if kind == "clobber_clean":
            issues.append(
                AgentIssue(
                    name=name,
                    reason=(
                        f"{target.label} replaced the link at {path} with a copy of the same "
                        "content — re-enable the agent to restore the binding; nothing is lost"
                    ),
                )
            )
            return "the link was replaced by an identical file"
        if kind == "clobber_one_sided":
            issues.append(
                AgentIssue(
                    name=name,
                    reason=(
                        f"{target.label} replaced the link at {path} with an edited copy. The "
                        "store has not changed since it was linked, so that copy holds the only "
                        "edit — adopt it to fold the change back in"
                    ),
                )
            )
            return "the link was replaced by an edited file"
        issues.append(
            AgentIssue(
                name=name,
                reason=(
                    f"{target.label} replaced the link at {path} with an edited copy, and the "
                    "store has changed too. Both sides hold edits — pick one; adopting either "
                    "discards the other"
                ),
            )
        )
        return "the link was replaced and both copies have changed"

    def _report_rendered_drift(
        self,
        adapter: AgentHarnessAdapter,
        target: AgentTarget,
        slug: str,
        record: AgentBindingRecord | None,
        issues: list[AgentIssue],
    ) -> None:
        """Detection only, for the harnesses we render into rather than link.

        A rendered file (Codex) is a real file with no symlink to destroy, so it never
        looks drifted — it just quietly stops matching. Re-enabling overwrites it. We
        say so; we do not adopt it automatically, because the TOML round-trip drops
        keys we do not model.
        """
        if not adapter.renders or record is None or record.rendered_sha256 is None:
            return
        path = adapter.binding_path(slug)
        try:
            stat = path.stat()
        except OSError:
            return
        if record.rendered_size == stat.st_size and record.rendered_mtime_ns == stat.st_mtime_ns:
            return  # untouched since we wrote it; no reason to hash
        if _safe_hash(path) == record.rendered_sha256:
            return
        issues.append(
            AgentIssue(
                name=f"{target.id}/{slug}",
                reason=(
                    f"{path} was edited outside Harness Asset Manager. {target.label} reads a "
                    "rendered copy, so those edits are not in the store and re-enabling this "
                    "agent overwrites them"
                ),
            )
        )

    def _unmanaged_entries(
        self,
        targets: tuple[AgentTarget, ...],
        adapters: dict[str, AgentHarnessAdapter],
        issues: list[AgentIssue],
    ) -> list[AgentEntry]:
        entries: list[AgentEntry] = []
        for target in targets:
            adapter = adapters[target.id]
            for path in adapter.unmanaged_paths():
                entries.append(self._unmanaged_entry(targets, target, path, issues))
            for path in adapter.orphaned_links():
                issues.append(
                    AgentIssue(
                        name=f"{target.id}/{path.stem}",
                        reason=(
                            f"{path} links to an agent that is no longer in the store; "
                            "remove it or re-create the agent"
                        ),
                    )
                )
        return entries

    def _unmanaged_entry(
        self,
        targets: tuple[AgentTarget, ...],
        target: AgentTarget,
        path: Path,
        issues: list[AgentIssue],
    ) -> AgentEntry:
        slug = path.stem
        try:
            if target.render_format == "codex_toml":
                name, description, _prompt = parse_codex_agent(path)
            else:
                parsed = parse_agent_file(path)
                name, description = parsed.name, parsed.description
        except AgentParseError as error:
            issues.append(AgentIssue(name=f"{target.id}/{slug}", reason=str(error)))
            name, description = slug, ""
        return AgentEntry(
            # Namespaced so the same slug found in two harnesses stays two distinct rows.
            ref=f"{target.id}/{slug}",
            name=name,
            description=description,
            kind="unmanaged",
            harness_path=path,
            bindings=tuple(
                AgentBinding(column.id, "unsupported", column.unavailable_reason)
                if not column.supports_agents
                else AgentBinding(column.id, "enabled" if column.id == target.id else "disabled")
                for column in targets
            ),
            can_adopt=True,
            can_delete=False,
        )


def _safe_hash(path: Path) -> str | None:
    try:
        return hash_file(path)
    except OSError:
        return None


def _format_config_value(value: object) -> str:
    """Render a frontmatter value for display without interpreting it."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[]" if not value else ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        count = len(value)
        return f"({count} {'entry' if count == 1 else 'entries'})"
    return str(value)


__all__ = ["AgentInventoryService"]
