from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AgentColumnResponse(BaseModel):
    harness: str
    label: str
    logoKey: str | None = None
    installed: bool


class AgentBindingResponse(BaseModel):
    harness: str
    state: Literal["enabled", "disabled", "unsupported"]
    detail: str | None = None


class AgentActionsResponse(BaseModel):
    canAdopt: bool
    canDelete: bool


class AgentSkillResponse(BaseModel):
    slug: str
    name: str


class AutoEnabledSkillResponse(BaseModel):
    skillRef: str
    harness: str


class AutoEnableFailureResponse(BaseModel):
    skillRef: str
    harness: str
    error: str


class AgentEntryResponse(BaseModel):
    ref: str
    name: str
    description: str
    kind: Literal["managed", "unmanaged"]
    harnessPath: str | None = None
    bindings: list[AgentBindingResponse]
    actions: AgentActionsResponse
    tags: list[str] = Field(default_factory=list)
    skills: list[AgentSkillResponse] = Field(default_factory=list)


class AgentIssueResponse(BaseModel):
    name: str
    reason: str


class AgentRepairResponse(BaseModel):
    """One automatic binding repair, newest first.

    Surfaced because silent repair is nearly as bad as silent breakage: the user has
    to be able to see that Harness Asset Manager moved their content, and what it decided.
    """

    at: float
    ref: str
    harness: str
    action: Literal["relinked", "adopted", "conflict_preserved", "refused"]
    detail: str


class AgentInventoryResponse(BaseModel):
    columns: list[AgentColumnResponse]
    entries: list[AgentEntryResponse]
    issues: list[AgentIssueResponse] = Field(default_factory=list)
    recentRepairs: list[AgentRepairResponse] = Field(default_factory=list)


class AgentHarnessRequest(BaseModel):
    harness: str


class SetAgentHarnessesRequest(BaseModel):
    harnesses: list[str] = Field(default_factory=list)


class AgentMutationFailureResponse(BaseModel):
    harness: str
    error: str


class SetAgentHarnessesResultResponse(BaseModel):
    ok: bool
    succeeded: list[str]
    failed: list[AgentMutationFailureResponse]


class AdoptAgentRequest(BaseModel):
    onConflict: Literal["keep_store", "replace_store"] | None = None


class AdoptAgentConflictResponse(BaseModel):
    """Body of the 409 an unresolved adopt returns. Nothing was mutated; the user decides."""

    code: str = "agent_conflict"
    error: str = "An agent with this name already exists in the store."
    conflict: Literal["store-name-exists"] = "store-name-exists"
    slug: str
    storePath: str
    harnessPath: str


class AdoptAgentResponse(BaseModel):
    ok: bool
    ref: str


class AdoptAllSkippedResponse(BaseModel):
    ref: str
    reason: str


class AdoptAllAgentsResponse(BaseModel):
    ok: bool
    adopted: list[str]
    skipped: list[AdoptAllSkippedResponse]


class CreateAgentRequest(BaseModel):
    name: str
    description: str = ""
    prompt: str = ""
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    color: str | None = None
    model: str | None = None
    effort: str | None = None
    allowedSubagents: str | None = None
    maxTurns: str | None = None
    isolation: str | None = None


class AgentConfigEntryResponse(BaseModel):
    """One frontmatter key we do not interpret, shown verbatim."""

    key: str
    value: str


class UpdateAgentRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    prompt: str | None = None
    tools: list[str] | None = None
    skills: list[str] | None = None
    # Contract fields: omitted carries the file's current value forward, an explicit
    # empty string clears the key.
    color: str | None = None
    model: str | None = None
    effort: str | None = None
    allowedSubagents: str | None = None
    maxTurns: str | None = None
    isolation: str | None = None
    metadata: list[AgentConfigEntryResponse] | None = None


class AgentHarnessDetailResponse(BaseModel):
    harness: str
    label: str
    logoKey: str | None = None
    state: Literal["enabled", "disabled", "unsupported"]
    detail: str | None = None
    path: str
    installMethod: Literal["symlink", "rendered", "none"]
    installed: bool


class SetAgentTagsRequest(BaseModel):
    tags: list[str] = Field(default_factory=list)


class AgentTagsResponse(BaseModel):
    tags: list[str] = Field(default_factory=list)


class AgentDetailResponse(BaseModel):
    ref: str
    name: str
    description: str
    prompt: str
    tools: list[str]
    document: str
    storePath: str | None = None
    harnesses: list[AgentHarnessDetailResponse]
    configuration: list[AgentConfigEntryResponse] = Field(default_factory=list)
    canDelete: bool
    canEdit: bool = True
    tags: list[str] = Field(default_factory=list)
    skills: list[AgentSkillResponse] = Field(default_factory=list)
    color: str | None = None
    model: str | None = None
    effort: str | None = None
    allowedSubagents: str | None = None
    maxTurns: str | None = None
    isolation: str | None = None
    ok: bool = True
    autoEnabled: list[AutoEnabledSkillResponse] = Field(default_factory=list)
    failed: list[AutoEnableFailureResponse] = Field(default_factory=list)


__all__ = [
    "AdoptAgentConflictResponse",
    "AdoptAgentRequest",
    "AdoptAgentResponse",
    "AdoptAllAgentsResponse",
    "AdoptAllSkippedResponse",
    "AgentActionsResponse",
    "AgentBindingResponse",
    "AgentColumnResponse",
    "AgentConfigEntryResponse",
    "AgentDetailResponse",
    "AgentEntryResponse",
    "AgentHarnessDetailResponse",
    "AgentHarnessRequest",
    "AgentInventoryResponse",
    "AgentIssueResponse",
    "AgentMutationFailureResponse",
    "AgentRepairResponse",
    "AgentSkillResponse",
    "AgentTagsResponse",
    "AutoEnableFailureResponse",
    "AutoEnabledSkillResponse",
    "CreateAgentRequest",
    "SetAgentHarnessesRequest",
    "SetAgentHarnessesResultResponse",
    "SetAgentTagsRequest",
    "UpdateAgentRequest",
]
