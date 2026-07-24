from __future__ import annotations

from pathlib import Path

from .adapters import AgentHarnessAdapter
from .model import (
    AgentBinding,
    AgentEntry,
    AgentInventory,
    AgentIssue,
    AgentParseError,
    AgentTarget,
)
from .parser import parse_agent_file
from .store import AgentStore


class AgentInventoryService:
    def __init__(
        self,
        store: AgentStore,
        targets: tuple[AgentTarget, ...],
        adapters: dict[str, AgentHarnessAdapter],
    ) -> None:
        self.store = store
        self.targets = targets
        self.adapters = adapters

    def build(self) -> AgentInventory:
        managed, issues = self.store.scan()
        issue_list = list(issues)

        entries = [self._managed_entry(agent.slug, agent.name, agent.description) for agent in managed]
        entries.extend(self._unmanaged_entries(issue_list))
        return AgentInventory(
            columns=self.targets,
            entries=tuple(entries),
            issues=tuple(issue_list),
        )

    def _managed_entry(self, slug: str, name: str, description: str) -> AgentEntry:
        bindings: list[AgentBinding] = []
        for target in self.targets:
            adapter = self.adapters[target.id]
            if adapter.is_dangling(slug):
                bindings.append(
                    AgentBinding(target.id, "disabled", "symlink points at a missing file")
                )
            elif adapter.is_enabled(slug):
                bindings.append(AgentBinding(target.id, "enabled"))
            else:
                detail = None
                if adapter.binding_path(slug).exists():
                    detail = "a file we do not manage occupies this name"
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

    def _unmanaged_entries(self, issues: list[AgentIssue]) -> list[AgentEntry]:
        entries: list[AgentEntry] = []
        for target in self.targets:
            adapter = self.adapters[target.id]
            for path in adapter.unmanaged_paths():
                entries.append(self._unmanaged_entry(target, path, issues))
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
        self, target: AgentTarget, path: Path, issues: list[AgentIssue]
    ) -> AgentEntry:
        slug = path.stem
        try:
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
                AgentBinding(column.id, "enabled" if column.id == target.id else "disabled")
                for column in self.targets
            ),
            can_adopt=True,
            can_delete=False,
        )


__all__ = ["AgentInventoryService"]
