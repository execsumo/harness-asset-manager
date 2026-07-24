from __future__ import annotations

from pathlib import Path

from skill_manager.errors import MutationError

from .model import AgentTarget


class AgentHarnessAdapter:
    """Owns one harness's agents directory.

    Ownership is a symlink pointing into the Skill Manager store — no content hashes,
    no sync-state file. ``is_symlink()`` plus a target inside the store is the whole
    "is this ours?" test. Verified: Claude Code loads a symlinked agent definition.
    """

    def __init__(self, target: AgentTarget, store_root: Path) -> None:
        self.target = target
        self.store_root = store_root.resolve()

    def binding_path(self, slug: str) -> Path:
        return self.target.output_dir / f"{slug}.md"

    def owns(self, path: Path) -> bool:
        """True when ``path`` is our symlink into the store (dangling links included)."""
        if not path.is_symlink():
            return False
        try:
            resolved = path.resolve()
        except OSError:
            return False
        return self.store_root in resolved.parents

    def is_enabled(self, slug: str) -> bool:
        return self.owns(self.binding_path(slug))

    def is_dangling(self, slug: str) -> bool:
        link = self.binding_path(slug)
        return link.is_symlink() and not link.exists()

    def enable(self, store_path: Path) -> None:
        target = store_path.resolve()
        link = self.binding_path(store_path.stem)
        if link.is_symlink():
            if link.resolve() == target:
                return
            # A stale or dangling link of ours is safe to repoint; anything else is not.
            if self.owns(link) or not link.exists():
                link.unlink()
            else:
                raise MutationError(
                    f"symlink at {link} points to {link.resolve()}, not {target}"
                )
        elif link.exists():
            raise MutationError(f"real file exists at {link}; will not overwrite")
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)

    def disable(self, slug: str) -> None:
        link = self.binding_path(slug)
        if not link.exists() and not link.is_symlink():
            return
        if not link.is_symlink():
            raise MutationError(f"not a symlink at {link}; will not delete a real file")
        link.unlink()

    def unmanaged_paths(self) -> tuple[Path, ...]:
        """Real ``*.md`` files in this harness's agents dir that we do not own."""
        if not self.target.output_dir.is_dir():
            return ()
        return tuple(
            path
            for path in sorted(self.target.output_dir.glob(self.target.file_glob))
            if not path.is_symlink()
        )

    def orphaned_links(self) -> tuple[Path, ...]:
        """Our symlinks whose store file is gone.

        Left alone these are invisible — the agent is no longer in the store, so it has
        no inventory row to hang a binding off. Surfaced as issues so a dead link in a
        harness directory is never silent.
        """
        if not self.target.output_dir.is_dir():
            return ()
        return tuple(
            path
            for path in sorted(self.target.output_dir.glob(self.target.file_glob))
            if path.is_symlink() and not path.exists()
        )

    def prune(self, path: Path) -> None:
        """Remove one of our dead links. Refuses anything that is not a symlink."""
        if not path.is_symlink():
            raise MutationError(f"not a symlink at {path}; will not delete a real file")
        path.unlink()


__all__ = ["AgentHarnessAdapter"]
