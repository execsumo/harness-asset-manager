from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from harness_asset_manager.atomic_files import atomic_write_text
from harness_asset_manager.errors import MutationError

from .adapters import AgentHarnessAdapter, parse_codex_agent
from .inventory import TargetResolver
from .ledger import AgentBindingLedger, build_record
from .model import AgentAdoptConflict, AgentDefinition, AgentTarget
from .parser import parse_agent_document, render_agent_document
from .store import AgentStore

ConflictResolution = Literal["keep_store", "replace_store"]


@dataclass(frozen=True)
class BulkAdoptResult:
    adopted: tuple[str, ...]
    skipped: tuple[tuple[str, str], ...]  # (ref, reason)


class AgentMutationService:
    """Writes agent bindings.

    Like the inventory service, targets are resolved per call so a harness the user
    just enabled or disabled in Settings takes effect without a restart.

    Every successful binding change is recorded in the ledger here rather than inside
    ``AgentHarnessAdapter``: this service is the only write funnel (the adapters are
    also used by the read-only inventory), so one place records and one place forgets.
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

    # -- per-harness binding ------------------------------------------------

    def enable(self, slug: str, harness: str) -> None:
        agent = self._require_agent(slug)
        self._enable(self._adapter(harness), harness, agent)

    def disable(self, slug: str, harness: str) -> None:
        self._require_agent(slug)
        self._disable(self._adapter(harness), harness, slug)

    def set_harnesses(self, slug: str, harnesses: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
        agent = self._require_agent(slug)
        wanted = set(harnesses)
        for harness in wanted:
            self._adapter(harness)  # validate before mutating anything
        succeeded: list[str] = []
        failed: list[tuple[str, str]] = []
        for target in self.targets:
            if not target.supports_agents:
                # Nothing to enable or disable; not a failure either.
                continue
            adapter = self.adapters[target.id]
            try:
                if target.id in wanted:
                    self._enable(adapter, target.id, agent)
                else:
                    self._disable(adapter, target.id, slug)
                succeeded.append(target.id)
            except MutationError as error:
                failed.append((target.id, str(error)))
        return succeeded, failed

    # -- adoption -----------------------------------------------------------

    def adopt(self, ref: str, on_conflict: ConflictResolution | None = None) -> str:
        """Take ownership of an unmanaged harness file.

        ``ref`` is ``<harness>/<slug>``. On a store-name collision this raises
        ``AgentAdoptConflict`` unless the caller states which side wins — the server
        never guesses, because either choice discards someone's content.
        """
        harness, slug = self._split_ref(ref)
        adapter = self._adapter(harness)
        harness_path = adapter.binding_path(slug)
        if not harness_path.is_file() or harness_path.is_symlink():
            raise MutationError(f"no unmanaged agent at {harness_path}")

        store_path = self.store.path_for(slug)
        if store_path.exists():
            if on_conflict is None:
                raise AgentAdoptConflict(slug, store_path, harness_path)
            if on_conflict == "replace_store":
                self._write_store_from_harness(adapter, harness_path, slug)
            elif on_conflict != "keep_store":
                raise MutationError(f"unknown conflict resolution: {on_conflict}")
            # keep_store: the store file stands; the harness copy is simply displaced.
            harness_path.unlink()
        elif adapter.renders:
            # Codex agents are TOML; convert into the store's markdown rather than
            # moving a file the store cannot parse.
            self.store.agents_root.mkdir(parents=True, exist_ok=True)
            self._write_store_from_harness(adapter, harness_path, slug)
            harness_path.unlink()
        else:
            self.store.agents_root.mkdir(parents=True, exist_ok=True)
            self.store.write_codex_extras(slug, {})
            shutil.move(str(harness_path), str(store_path))

        # Re-links and re-records in one step: the fresh record's store hash is taken
        # from the file we just wrote, so a later clobber is measured against the
        # content this harness actually received.
        self._enable(adapter, harness, self._require_agent(slug))
        return slug

    def _write_store_from_harness(self, adapter: AgentHarnessAdapter, harness_path: Path, slug: str) -> None:
        """Whatever the harness holds, expressed in the store's markdown format."""
        if not adapter.renders:
            self.store.write_raw(slug, harness_path.read_text(encoding="utf-8"))
            self.store.write_codex_extras(slug, {})
            return
        parsed = parse_codex_agent(harness_path)
        self.store.write_codex_agent(
            slug,
            name=parsed.name,
            description=parsed.description,
            prompt=parsed.prompt,
            extras=dict(parsed.extras),
        )

    def adopt_all(self) -> BulkAdoptResult:
        """Adopt every non-conflicting unmanaged agent; report the rest for the user."""
        adopted: list[str] = []
        skipped: list[tuple[str, str]] = []
        for target in self.targets:
            adapter = self.adapters[target.id]
            for path in adapter.unmanaged_paths():
                ref = f"{target.id}/{path.stem}"
                try:
                    adopted.append(self.adopt(ref))
                except AgentAdoptConflict:
                    skipped.append((ref, "an agent with this name already exists in the store"))
                except MutationError as error:
                    skipped.append((ref, str(error)))
        return BulkAdoptResult(tuple(adopted), tuple(skipped))

    # -- store lifecycle ----------------------------------------------------

    def update_unmanaged(
        self,
        ref: str,
        *,
        name: str | None = None,
        description: str | None = None,
        prompt: str | None = None,
        tools: tuple[str, ...] | None = None,
        metadata: list[tuple[str, object]] | list[dict[str, str]] | None = None,
    ) -> None:
        """Edit an unmanaged agent's file in place (``<harness>/<slug>`` ref).

        Same rendering contract as the managed path: ``name``/``description``/
        ``tools`` are structured arguments and ``metadata`` carries the ordered
        custom frontmatter keys, so nothing the user added is silently dropped.
        Rendered adapters (Codex TOML) are refused: their files have no Markdown
        frontmatter to edit — adopt first, then edit the store copy.
        """
        harness_id, separator, slug = ref.partition("/")
        if not separator or not harness_id or not slug:
            raise MutationError(f"expected an unmanaged ref of the form <harness>/<slug>: {ref}")
        if slug != Path(slug).name or slug in {".", ".."}:
            raise MutationError(f"unsafe agent ref: {ref!r}", status=404)
        adapter = self.adapters.get(harness_id)
        if adapter is None:
            raise MutationError(f"harness does not support agents: {harness_id}", status=404)
        if adapter.renders:
            raise MutationError(
                f"this agent is rendered as a native {harness_id} file; adopt it before editing"
            )
        path = adapter.binding_path(slug)
        if not path.is_file() or path.is_symlink():
            raise MutationError(f"no unmanaged agent at {path}", status=404)

        try:
            current = parse_agent_document(path.read_text(encoding="utf-8"), slug=slug, path=path)
        except Exception as error:  # noqa: BLE001 - surfaced verbatim as a 4xx/5xx body
            raise MutationError(f"cannot parse {path}: {error}") from error

        rendered = render_agent_document(
            name=name if name is not None else current.name,
            description=description if description is not None else current.description,
            prompt=prompt if prompt is not None else current.prompt,
            tools=tools if tools is not None else current.tools,
            base_metadata=current.metadata if metadata is None else None,
            extra_metadata=metadata,
        )
        atomic_write_text(path, rendered)

    def delete(self, slug: str) -> None:
        self._require_agent(slug)
        for target in self.targets:
            if target.supports_agents:
                self._disable(self.adapters[target.id], target.id, slug)
        self.store.delete(slug)
        # Covers harnesses the user has since disabled in Settings, which are not in
        # `targets` and so were never asked to unbind.
        self.ledger.forget_slug(slug)

    # -- ledger -------------------------------------------------------------

    def _enable(self, adapter: AgentHarnessAdapter, harness: str, agent: AgentDefinition) -> None:
        adapter.enable(agent)
        self.ledger.upsert(
            agent.slug,
            build_record(
                harness=harness,
                store_path=agent.path,
                rendered_path=adapter.binding_path(agent.slug) if adapter.renders else None,
            ),
        )

    def _disable(self, adapter: AgentHarnessAdapter, harness: str, slug: str) -> None:
        adapter.disable(slug)
        self.ledger.forget(slug, harness)

    # -- helpers ------------------------------------------------------------

    def _require_agent(self, slug: str) -> AgentDefinition:
        agent = self.store.get(slug)
        if agent is None:
            raise MutationError(f"agent not found: {slug}")
        return agent

    def _adapter(self, harness: str) -> AgentHarnessAdapter:
        adapter = self.adapters.get(harness)
        if adapter is None:
            raise MutationError(f"harness does not support agents: {harness}")
        return adapter

    @staticmethod
    def _split_ref(ref: str) -> tuple[str, str]:
        harness, separator, slug = ref.partition("/")
        if not separator or not harness or not slug:
            raise MutationError(f"expected an unmanaged ref of the form <harness>/<slug>: {ref}")
        if slug != Path(slug).name or slug in {".", ".."}:
            raise MutationError(f"unsafe agent ref: {ref!r}")
        return harness, slug


__all__ = ["AgentMutationService", "BulkAdoptResult", "ConflictResolution"]
