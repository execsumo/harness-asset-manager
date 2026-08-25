from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping

from harness_asset_manager.errors import MutationError


class AgentParseError(ValueError):
    """Raised when an agent definition file cannot be parsed safely."""


# The agent contract, in canonical render order: these frontmatter keys are parsed
# into their own ``AgentDefinition`` fields, rendered first and in this order, and
# never surfaced or accepted as custom configuration. Single source of truth --
# the parser, the renderer, and ``extra_metadata`` all derive from it, so adding a
# contract field is a one-line change here.
CONTRACT_KEYS: tuple[str, ...] = ("name", "description", "model", "effort", "tools", "skills")
CONTRACT_KEY_SET = frozenset(CONTRACT_KEYS)

# ``effort`` is a fixed, global vocabulary — not per-harness, unlike ``model``, whose
# value set is genuinely open-ended and therefore stays free text. The picker offers
# exactly these plus an empty choice that clears the key, and the write paths reject
# anything else, so a hand-edited file or a raw-YAML edit cannot smuggle in a value
# the picker could not have produced. Mirrored by ``EFFORT_VALUES`` in
# frontend/src/features/agents/api/types.ts and pinned by ``EffortValueParityTests``.
EFFORT_VALUES: tuple[str, ...] = ("low", "medium", "high")


def validate_effort(effort: str | None) -> str | None:
    """Normalize an effort value on its way into an agent file.

    ``None`` means the caller omitted the field, so whatever the file holds stands;
    an empty string is an explicit clear. Matching is exact: accepting ``HIGH`` and
    silently rewriting it would invent a case-insensitive contract the picker cannot
    produce and the file does not describe.
    """
    if effort is None:
        return None
    value = effort.strip()
    if value and value not in EFFORT_VALUES:
        raise MutationError(
            f"unknown effort: {effort!r}; expected one of "
            f"{', '.join(EFFORT_VALUES)}, or empty to clear the key",
            status=400,
            code="invalid_effort",
        )
    return value


@dataclass(frozen=True)
class AgentSkill:
    slug: str
    name: str


@dataclass(frozen=True)
class AgentDefinition:
    """A subagent: a markdown file with `name`, `description`, and a prompt body.

    ``metadata`` is the frontmatter mapping **verbatim**, including custom keys Harness
    Asset Manager does not interpret (``permissionMode``, ``maxTurns``, Cursor's
    ``readonly``, …). Standard contract fields (including ``model``, ``effort``,
    ``tools``, and ``skills``) are parsed separately and never treated as custom metadata.
    Custom keys are surfaced and written back untouched — an edit here must never silently
    drop a harness's own configuration.
    """

    slug: str
    name: str
    description: str
    prompt: str
    tools: tuple[str, ...]
    path: Path
    metadata: Mapping[str, object] = field(default_factory=dict)
    # Codex-only TOML fields live beside the Markdown store file. Keeping them
    # outside frontmatter prevents Codex configuration from leaking into the
    # Markdown file symlinked into Claude, Agy, or Cursor.
    codex_extras: Mapping[str, object] = field(default_factory=dict)
    skills: tuple[str, ...] = ()
    # Contract fields: parsed and rendered as their own frontmatter keys, never
    # treated as custom metadata.
    model: str | None = None
    effort: str | None = None

    @property
    def ref(self) -> str:
        return self.slug

    @property
    def extra_metadata(self) -> tuple[tuple[str, object], ...]:
        """Frontmatter beyond the fields the detail view renders on their own."""
        return tuple(
            (key, value)
            for key, value in self.metadata.items()
            if key not in CONTRACT_KEY_SET
        )


@dataclass(frozen=True)
class AgentTarget:
    """A harness that stores subagents as flat files in a directory."""

    id: str
    label: str
    logo_key: str | None
    root_path: Path
    output_dir: Path
    file_glob: str
    render_format: Literal["markdown", "codex_toml"]
    docs_url: str
    installed: bool
    unavailable_reason: str | None = None

    @property
    def supports_agents(self) -> bool:
        return self.unavailable_reason is None


BindingState = Literal["enabled", "disabled", "unsupported"]


@dataclass(frozen=True)
class AgentBinding:
    harness: str
    state: BindingState
    detail: str | None = None


@dataclass(frozen=True)
class AgentEntry:
    """One row of the agents inventory.

    ``managed`` entries live in the Harness Asset Manager store; ``unmanaged`` entries are real
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
    tags: tuple[str, ...] = ()
    skills: tuple[AgentSkill, ...] = ()


@dataclass(frozen=True)
class AgentIssue:
    name: str
    reason: str


@dataclass(frozen=True)
class AgentHarnessDetail:
    """One harness row in the detail view: state plus where the file actually is."""

    harness: str
    label: str
    logo_key: str | None
    state: BindingState
    detail: str | None
    path: Path
    install_method: Literal["symlink", "rendered", "none"]
    installed: bool


@dataclass(frozen=True)
class AgentDetail:
    ref: str
    name: str
    description: str
    prompt: str
    tools: tuple[str, ...]
    document: str
    # None for unmanaged inspections: there is no store copy until adoption.
    store_path: Path | None
    harnesses: tuple[AgentHarnessDetail, ...]
    can_delete: bool
    can_edit: bool = True
    tags: tuple[str, ...] = ()
    # Frontmatter beyond name/description, verbatim and in file order.
    configuration: tuple[tuple[str, str], ...] = ()
    skills: tuple[AgentSkill, ...] = ()
    model: str | None = None
    effort: str | None = None


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
    "CONTRACT_KEYS",
    "CONTRACT_KEY_SET",
    "EFFORT_VALUES",
    "AgentAdoptConflict",
    "AgentBinding",
    "AgentDefinition",
    "AgentEntry",
    "AgentInventory",
    "AgentIssue",
    "AgentParseError",
    "AgentSkill",
    "AgentTarget",
    "BindingState",
    "validate_effort",
]
