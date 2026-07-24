from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from skill_manager.errors import MutationError


class AgentParseError(ValueError):
    """Raised when an agent definition file cannot be parsed safely."""


@dataclass(frozen=True)
class AgentDefinition:
    """A subagent: a markdown file with `name`, `description`, and a prompt body."""

    slug: str
    name: str
    description: str
    prompt: str
    tools: tuple[str, ...]
    path: Path

    @property
    def ref(self) -> str:
        return self.slug


@dataclass(frozen=True)
class AgentTarget:
    """A harness that stores subagents as flat ``<slug>.md`` files."""

    id: str
    label: str
    logo_key: str | None
    root_path: Path
    output_dir: Path
    file_glob: str
    docs_url: str
    installed: bool
    enabled: bool


BindingState = Literal["enabled", "disabled", "unsupported"]


@dataclass(frozen=True)
class AgentBinding:
    harness: str
    state: BindingState
    detail: str | None = None


@dataclass(frozen=True)
class AgentEntry:
    """One row of the agents inventory.

    ``managed`` entries live in the Skill Manager store; ``unmanaged`` entries are real
    files found in a harness directory that we do not own.
    """

    ref: str
    name: str
    description: str
    kind: Literal["managed", "unmanaged"]
    harness_path: Path | None
    bindings: tuple[AgentBinding, ...]
    can_adopt: bool
    can_delete: bool


@dataclass(frozen=True)
class AgentIssue:
    name: str
    reason: str


@dataclass(frozen=True)
class AgentInventory:
    columns: tuple[AgentTarget, ...]
    entries: tuple[AgentEntry, ...]
    issues: tuple[AgentIssue, ...]


class AgentAdoptConflict(MutationError):
    """An unmanaged agent's slug already names an entry in the store.

    Carries both sides so the caller can present the choice; the server never picks.
    The agents router catches this to return a structured 409 body; inheriting from
    ``MutationError`` means any other path still degrades to a normal 409 with a
    message rather than a bare 500.
    """

    def __init__(self, slug: str, store_path: Path, harness_path: Path) -> None:
        super().__init__(f"an agent named {slug} already exists in the store", status=409)
        self.slug = slug
        self.store_path = store_path
        self.harness_path = harness_path


__all__ = [
    "AgentAdoptConflict",
    "AgentBinding",
    "AgentDefinition",
    "AgentEntry",
    "AgentInventory",
    "AgentIssue",
    "AgentParseError",
    "AgentTarget",
    "BindingState",
]
