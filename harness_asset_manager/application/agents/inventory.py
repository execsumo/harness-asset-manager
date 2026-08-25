from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from .adapters import AgentHarnessAdapter, TargetResolver, parse_codex_agent
from .ledger import AgentBindingLedger, AgentBindingRecord, classify_drift, hash_file
from .model import (
    AgentBinding,
    AgentDetail,
    AgentEntry,
    AgentHarnessDetail,
    AgentInventory,
    AgentIssue,
    AgentParseError,
    AgentSkill,
    AgentTarget,
)
from .parser import parse_agent_document, parse_agent_file
from .reconcile import ReconcileOutcome
from .store import AgentStore

if TYPE_CHECKING:
    from harness_asset_manager.application.asset_tags import AssetTagService
    from harness_asset_manager.application.skills import SkillsQueryService


class AgentInventoryService:
    """Read-only view over the agents matrix.

    `resolve` is called per build so newly configured or newly installed harnesses
    surface immediately.
    """

    def __init__(
        self,
        store: AgentStore,
        resolve: TargetResolver,
        ledger: AgentBindingLedger,
        reconcile: Callable[[], ReconcileOutcome] | None = None,
        asset_tags: AssetTagService | None = None,
        skills_queries: SkillsQueryService | None = None,
    ) -> None:
        self.store = store
        self._resolve = resolve
        self.ledger = ledger
        self._reconcile = reconcile
        self.asset_tags = asset_tags
        self.skills_queries = skills_queries

    @property
    def targets(self) -> tuple[AgentTarget, ...]:
        return tuple(target for target in self._resolve()[0] if target.installed)

    @property
    def adapters(self) -> dict[str, AgentHarnessAdapter]:
        return self._resolve()[1]

    def _load_skill_names(self) -> dict[str, str]:
        """Package dir → display name for every managed skill.

        Deliberately the read-only lookup, not ``SkillsQueryService.inventory()``:
        that one runs the skills reconcile, which can auto-adopt, so resolving a
        display name made ``GET /api/agents`` able to write into the skills store.

        Best-effort: an agent's skill list is a display nicety, so a skills store
        that cannot be read degrades to showing raw slugs rather than failing the
        whole matrix.
        """
        if self.skills_queries is None:
            return {}
        try:
            return self.skills_queries.managed_skill_names()
        except Exception:  # noqa: BLE001
            return {}

    def _skill_resolver(self) -> Callable[[tuple[str, ...]], tuple[AgentSkill, ...]]:
        """A skill-name resolver that scans at most once, however often it is called.

        Resolving a name rescans the skills store and every installed harness
        directory — the same reason the ledger above is loaded once per build.
        Resolving per agent turned a single list request into one full skills scan
        per agent. The scan is deferred to first use, so an inventory that
        references no skills still pays nothing, and a failing scan is not retried
        once per row.
        """
        names: dict[str, str] | None = None

        def resolve(skill_slugs: tuple[str, ...]) -> tuple[AgentSkill, ...]:
            nonlocal names
            if not skill_slugs:
                return ()
            if names is None:
                names = self._load_skill_names()
            return tuple(
                AgentSkill(slug=slug, name=names.get(slug, slug)) for slug in skill_slugs
            )

        return resolve

    def _resolve_agent_skills(self, skill_slugs: tuple[str, ...]) -> tuple[AgentSkill, ...]:
        """Single-shot resolution, for the detail paths that look at one agent."""
        return self._skill_resolver()(skill_slugs)

    def build(self) -> AgentInventory:
        # Repair first, then report: otherwise the matrix describes a state that is
        # already stale by the time it reaches the client. Reconcile is a no-op when
        # the setting is off or the ledger holds nothing.
        reconcile_issues: tuple[tuple[str, str], ...] = ()
        if self._reconcile is not None:
            reconcile_issues = self._reconcile().issues

        all_targets, adapters = self._resolve()
        targets = tuple(target for target in all_targets if target.installed)
        managed, issues = self.store.scan()
        issue_list = list(issues)
        issue_list.extend(AgentIssue(name=name, reason=reason) for name, reason in reconcile_issues)
        # Read once per build, not per binding: the ledger is a single small file and
        # this runs on every list request.
        ledger_state = self.ledger.load()
        resolve_skills = self._skill_resolver()
        tags_by_ref = (
            self.asset_tags.get_tags_for_family("agents")
            if self.asset_tags is not None
            else {}
        )

        entries = [
            self._managed_entry(
                targets,
                adapters,
                agent.slug,
                agent.name,
                agent.description,
                ledger_state.get(agent.slug, {}),
                issue_list,
                tags=tuple(tags_by_ref.get(agent.slug, ())),
                skills=resolve_skills(agent.skills),
            )
            for agent in managed
        ]
        entries.extend(
            self._unmanaged_entries(
                targets, adapters, issue_list, tags_by_ref=tags_by_ref, resolve_skills=resolve_skills
            )
        )
        return AgentInventory(
            columns=targets,
            entries=tuple(entries),
            issues=tuple(issue_list),
        )

    def detail(self, slug: str) -> AgentDetail | None:
        """Everything the detail view needs, including where each harness copy lives.

        Managed agents are addressed by their store slug. Unmanaged agents are
        addressed by ``<harness>/<slug>`` — their inventory ref — and resolve to a
        read-only inspection of the harness file, so the detail view can show what
        would be adopted before anything is adopted.
        """
        if "/" in slug:
            return self._unmanaged_detail(slug)
        agent = self.store.get(slug)
        if agent is None:
            return None
        all_targets, adapters = self._resolve()
        targets = tuple(target for target in all_targets if target.installed)
        records = self.ledger.load().get(slug, {})
        harnesses = self._harness_rows(targets, adapters, slug, records)
        tags = (
            tuple(self.asset_tags.get_tags("agents", agent.slug))
            if self.asset_tags is not None
            else ()
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
            tags=tags,
            configuration=tuple(
                (key, _format_config_value(value)) for key, value in agent.extra_metadata
            ),
            skills=self._resolve_agent_skills(agent.skills),
            model=agent.model,
            effort=agent.effort,
        )

    def _unmanaged_detail(self, ref: str) -> AgentDetail | None:
        """Read-only inspection of a harness file that Harness Asset Manager does not own.

        ``ref`` is ``<harness>/<slug>`` as the inventory lists it. Nothing here writes:
        an unmanaged agent has no store copy, so there is nothing to edit or delete
        until it is adopted.
        """
        harness_id, separator, slug = ref.partition("/")
        if not separator or not harness_id or not slug or slug != Path(slug).name:
            return None
        all_targets, adapters = self._resolve()
        owner = next((t for t in all_targets if t.id == harness_id), None)
        adapter = adapters.get(harness_id)
        if owner is None or adapter is None or not owner.supports_agents or not owner.installed:
            return None
        harness_path = adapter.binding_path(slug)
        if not harness_path.is_file():
            return None

        document = harness_path.read_text(encoding="utf-8")
        if adapter.renders:
            try:
                codex_agent = parse_codex_agent(harness_path)
            except AgentParseError:
                return None
            name = codex_agent.name
            description = codex_agent.description
            prompt = codex_agent.prompt
            tools: tuple[str, ...] = ()
            extra_metadata = tuple(codex_agent.extras.items())
            skills: tuple[AgentSkill, ...] = ()
            model: str | None = None
            effort: str | None = None
        else:
            try:
                agent = parse_agent_document(document, slug=slug, path=harness_path)
            except AgentParseError:
                return None
            name = agent.name
            description = agent.description
            prompt = agent.prompt
            tools = agent.tools
            extra_metadata = agent.extra_metadata
            skills = self._resolve_agent_skills(agent.skills)
            model = agent.model
            effort = agent.effort

        targets = tuple(target for target in all_targets if target.installed)
        harnesses = self._harness_rows(targets, adapters, slug, {})
        tags = (
            tuple(self.asset_tags.get_tags("agents", ref))
            if self.asset_tags is not None
            else ()
        )
        return AgentDetail(
            ref=ref,
            name=name,
            description=description,
            prompt=prompt,
            tools=tools,
            document=document,
            store_path=None,
            harnesses=tuple(harnesses),
            can_delete=False,
            # Rendered adapters (Codex TOML) have no Markdown frontmatter to edit.
            can_edit=not adapter.renders,
            tags=tags,
            configuration=tuple(
                (key, _format_config_value(value)) for key, value in extra_metadata
            ),
            skills=skills,
            model=model,
            effort=effort,
        )

    def _harness_rows(
        self,
        targets: tuple[AgentTarget, ...],
        adapters: dict[str, AgentHarnessAdapter],
        slug: str,
        records: dict[str, AgentBindingRecord],
    ) -> list[AgentHarnessDetail]:
        rows: list[AgentHarnessDetail] = []
        issues: list[AgentIssue] = []
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
                        adapter, target, slug, records.get(target.id), issues
                    )
                else:
                    state, detail = "disabled", None
            rows.append(
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
        return rows

    def _managed_entry(
        self,
        targets: tuple[AgentTarget, ...],
        adapters: dict[str, AgentHarnessAdapter],
        slug: str,
        name: str,
        description: str,
        records: dict[str, AgentBindingRecord],
        issues: list[AgentIssue],
        tags: tuple[str, ...] = (),
        skills: tuple[AgentSkill, ...] = (),
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
            tags=tags,
            skills=skills,
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
        tags_by_ref: dict[str, list[str]] | None = None,
        resolve_skills: Callable[[tuple[str, ...]], tuple[AgentSkill, ...]] | None = None,
    ) -> list[AgentEntry]:
        entries: list[AgentEntry] = []
        tags_map = tags_by_ref or {}
        resolve = resolve_skills or self._skill_resolver()
        for target in targets:
            adapter = adapters[target.id]
            for path in adapter.unmanaged_paths():
                ref = f"{target.id}/{path.stem}"
                entries.append(
                    self._unmanaged_entry(
                        targets,
                        target,
                        path,
                        issues,
                        tags=tuple(tags_map.get(ref, ())),
                        resolve_skills=resolve,
                    )
                )
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
        tags: tuple[str, ...] = (),
        resolve_skills: Callable[[tuple[str, ...]], tuple[AgentSkill, ...]] | None = None,
    ) -> AgentEntry:
        slug = path.stem
        resolve = resolve_skills or self._skill_resolver()
        skills: tuple[AgentSkill, ...] = ()
        try:
            if target.render_format == "codex_toml":
                parsed = parse_codex_agent(path)
                name, description = parsed.name, parsed.description
            else:
                parsed = parse_agent_file(path)
                name, description = parsed.name, parsed.description
                skills = resolve(parsed.skills)
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
            tags=tags,
            skills=skills,
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


__all__ = ["AgentInventoryService", "TargetResolver"]
