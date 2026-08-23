from __future__ import annotations

import re
import tomllib
from dataclasses import replace
from pathlib import Path
from typing import Callable

from harness_asset_manager.atomic_files import atomic_write_text
from harness_asset_manager.errors import MutationError
from harness_asset_manager.portable_paths import is_sync_artifact

from .model import AgentDefinition, AgentIssue, AgentParseError
from .parser import parse_agent_file, render_agent_document

_SLUG_SAFE = re.compile(r"[^a-z0-9._-]+")


def slugify(name: str) -> str:
    slug = _SLUG_SAFE.sub("-", name.strip().lower()).strip("-.")
    if not slug:
        raise MutationError(f"cannot derive a file name from {name!r}")
    return slug


class AgentStore:
    """The agents Harness Asset Manager owns: flat ``<slug>.md`` files under ``agents_root``."""

    def __init__(
        self, agents_root: Path, on_store_write: Callable[[str], None] | None = None
    ) -> None:
        self.agents_root = agents_root
        # One notification point for "the store file for this slug changed", so the
        # binding ledger has a single owner for its store baseline. Routers call
        # `create`/`update` directly, bypassing the mutation service, which is exactly
        # why this hangs off the store rather than off the service.
        self._on_store_write = on_store_write

    def path_for(self, slug: str) -> Path:
        if slug != Path(slug).name or slug in {"", ".", ".."}:
            raise MutationError(f"unsafe agent ref: {slug!r}")
        return self.agents_root / f"{slug}.md"

    def codex_extras_path(self, slug: str) -> Path:
        """Return the opaque Codex metadata sidecar for a stored agent."""
        self.path_for(slug)  # validate the slug before constructing a second path
        return self.agents_root / f".{slug}.codex.toml"

    def scan(self) -> tuple[tuple[AgentDefinition, ...], tuple[AgentIssue, ...]]:
        agents: list[AgentDefinition] = []
        issues: list[AgentIssue] = []
        if not self.agents_root.is_dir():
            return (), ()
        try:
            entries = sorted(self.agents_root.iterdir())
        except OSError:
            return (), ()
        for path in entries:
            if is_sync_artifact(path.name):
                continue
            if not path.is_file() or path.suffix != ".md":
                continue
            try:
                agents.append(self._load_agent(path))
            except AgentParseError as error:
                issues.append(AgentIssue(name=path.stem, reason=str(error)))
            except OSError as error:
                issues.append(AgentIssue(name=path.stem, reason=str(error)))
        return tuple(agents), tuple(issues)

    def get(self, slug: str) -> AgentDefinition | None:
        path = self.path_for(slug)
        if not path.is_file():
            return None
        try:
            return self._load_agent(path)
        except AgentParseError:
            return None

    def exists(self, slug: str) -> bool:
        return self.path_for(slug).is_file()

    def create(
        self, *, name: str, description: str, prompt: str, tools: tuple[str, ...] = ()
    ) -> AgentDefinition:
        slug = slugify(name)
        path = self.path_for(slug)
        if path.exists():
            raise MutationError(f"an agent named {slug} already exists")
        self.agents_root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            path,
            render_agent_document(
                name=name, description=description, prompt=prompt, tools=tools
            ),
        )
        self._notify_write(slug)
        return self._load_agent(path)

    def update(
        self,
        slug: str,
        *,
        name: str | None = None,
        description: str | None = None,
        prompt: str | None = None,
        tools: tuple[str, ...] | None = None,
        metadata: list[tuple[str, object]] | tuple[tuple[str, object], ...] | list[dict[str, str]] | None = None,
    ) -> AgentDefinition:
        current = self.get(slug)
        if current is None:
            raise MutationError(f"agent not found: {slug}")
        atomic_write_text(
            current.path,
            render_agent_document(
                name=name if name is not None else current.name,
                description=description if description is not None else current.description,
                prompt=prompt if prompt is not None else current.prompt,
                tools=tools if tools is not None else current.tools,
                base_metadata=current.metadata if metadata is None else None,
                extra_metadata=metadata,
            ),
        )
        self._notify_write(slug)
        return self._load_agent(current.path)

    def write_raw(self, slug: str, document: str) -> None:
        """Adopt path: keep the harness file's bytes verbatim rather than re-rendering."""
        self.agents_root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.path_for(slug), document)
        self._notify_write(slug)

    def write_codex_extras(self, slug: str, extras: dict[str, object]) -> None:
        """Persist unmodeled Codex TOML fields outside the shared Markdown file."""
        path = self.codex_extras_path(slug)
        if extras:
            import tomli_w

            atomic_write_text(path, tomli_w.dumps(extras))
        elif path.exists():
            path.unlink()

    def write_codex_agent(
        self,
        slug: str,
        *,
        name: str,
        description: str,
        prompt: str,
        extras: dict[str, object],
    ) -> None:
        """Write a Codex adoption without placing Codex-only fields in Markdown."""
        self.write_raw(
            slug,
            render_agent_document(name=name, description=description, prompt=prompt),
        )
        self.write_codex_extras(slug, extras)

    def delete(self, slug: str) -> None:
        path = self.path_for(slug)
        if not path.exists():
            raise MutationError(f"agent not found: {slug}")
        if path.is_symlink():
            raise MutationError(f"refusing to delete a symlink in the store: {path}")
        path.unlink()
        extras_path = self.codex_extras_path(slug)
        if extras_path.exists():
            extras_path.unlink()

    def _notify_write(self, slug: str) -> None:
        if self._on_store_write is not None:
            self._on_store_write(slug)

    def _load_agent(self, path: Path) -> AgentDefinition:
        agent = parse_agent_file(path)
        extras_path = self.codex_extras_path(path.stem)
        if not extras_path.is_file():
            return agent
        try:
            raw = tomllib.loads(extras_path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise AgentParseError(f"invalid Codex metadata for {path.stem}: {error}") from error
        if not isinstance(raw, dict):
            raise AgentParseError(f"Codex metadata for {path.stem} must be a table")
        return replace(agent, codex_extras=raw)


__all__ = ["AgentStore", "slugify"]
