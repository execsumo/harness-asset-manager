from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from harness_asset_manager.api.deps import get_container
from harness_asset_manager.api.schemas.agents import (
    AdoptAgentConflictResponse,
    AdoptAgentRequest,
    AdoptAgentResponse,
    AdoptAllAgentsResponse,
    AdoptAllSkippedResponse,
    AgentActionsResponse,
    AgentBindingResponse,
    AgentColumnResponse,
    AgentConfigEntryResponse,
    AgentDetailResponse,
    AgentEntryResponse,
    AgentHarnessDetailResponse,
    AgentHarnessRequest,
    AgentInventoryResponse,
    AgentIssueResponse,
    AgentMutationFailureResponse,
    AgentRepairResponse,
    AgentSkillResponse,
    AgentTagsResponse,
    AutoEnabledSkillResponse,
    AutoEnableFailureResponse,
    CreateAgentRequest,
    SetAgentHarnessesRequest,
    SetAgentHarnessesResultResponse,
    SetAgentTagsRequest,
    UpdateAgentRequest,
)
from harness_asset_manager.api.schemas.common import OkResponse
from harness_asset_manager.application import BackendContainer
from harness_asset_manager.application.agents import (
    AgentAdoptConflict,
    AgentDetail,
    validate_effort,
)
from harness_asset_manager.errors import MutationError

router = APIRouter(prefix="/api/agents", tags=["Agents"])


@router.get("", response_model=AgentInventoryResponse)
def list_agents(container: BackendContainer = Depends(get_container)) -> AgentInventoryResponse:
    inventory = container.agents_inventory.build()
    return AgentInventoryResponse(
        columns=[
            AgentColumnResponse(
                harness=column.id,
                label=column.label,
                logoKey=column.logo_key,
                installed=column.installed,
            )
            for column in inventory.columns
        ],
        entries=[
            AgentEntryResponse(
                ref=entry.ref,
                name=entry.name,
                description=entry.description,
                kind=entry.kind,
                harnessPath=str(entry.harness_path) if entry.harness_path else None,
                bindings=[
                    AgentBindingResponse(
                        harness=binding.harness, state=binding.state, detail=binding.detail
                    )
                    for binding in entry.bindings
                ],
                actions=AgentActionsResponse(
                    canAdopt=entry.can_adopt, canDelete=entry.can_delete
                ),
                tags=list(entry.tags),
                skills=[
                    AgentSkillResponse(slug=s.slug, name=s.name) for s in entry.skills
                ],
            )
            for entry in inventory.entries
        ],
        issues=[
            AgentIssueResponse(name=issue.name, reason=issue.reason) for issue in inventory.issues
        ],
        recentRepairs=[
            AgentRepairResponse(
                at=repair.at,
                ref=repair.ref,
                harness=repair.harness,
                action=repair.action,
                detail=repair.detail,
            )
            for repair in container.agents_audit.recent()
        ],
    )


@router.post("", response_model=AgentDetailResponse)
def create_agent(
    body: CreateAgentRequest,
    container: BackendContainer = Depends(get_container),
) -> AgentDetailResponse:
    validated_skills = container.agents_mutations.validate_skills(body.skills)
    agent = container.agents_store.create(
        name=body.name,
        description=body.description,
        prompt=body.prompt,
        tools=tuple(body.tools),
        skills=validated_skills,
        model=body.model,
        effort=validate_effort(body.effort),
    )
    container.invalidation.invalidate_all()
    return _require_detail(container, agent.slug)


@router.post("/adopt-all", response_model=AdoptAllAgentsResponse)
def adopt_all_agents(
    container: BackendContainer = Depends(get_container),
) -> AdoptAllAgentsResponse:
    result = container.agents_mutations.adopt_all()
    container.invalidation.invalidate_all()
    return AdoptAllAgentsResponse(
        ok=True,
        adopted=list(result.adopted),
        skipped=[AdoptAllSkippedResponse(ref=ref, reason=reason) for ref, reason in result.skipped],
    )


@router.put("/{agent_ref:path}/tags", response_model=AgentTagsResponse)
def set_agent_tags(
    agent_ref: str,
    body: SetAgentTagsRequest,
    container: BackendContainer = Depends(get_container),
) -> dict[str, object]:
    result = container.agents_mutations.set_tags(agent_ref, body.tags)
    container.invalidation.invalidate_all()
    return result


@router.get("/{agent_ref:path}", response_model=AgentDetailResponse)
def get_agent(
    agent_ref: str,
    container: BackendContainer = Depends(get_container),
) -> AgentDetailResponse:
    detail = container.agents_inventory.detail(agent_ref)
    if detail is None:
        raise MutationError(f"agent not found: {agent_ref}", status=404)
    return _detail(detail)


@router.put("/{agent_ref:path}", response_model=AgentDetailResponse)
def update_agent(
    agent_ref: str,
    body: UpdateAgentRequest,
    container: BackendContainer = Depends(get_container),
) -> AgentDetailResponse:
    extra_metadata = None
    if body.metadata is not None:
        extra_metadata = [(entry.key, entry.value) for entry in body.metadata]

    validated_skills = (
        container.agents_mutations.validate_skills(body.skills)
        if body.skills is not None
        else None
    )
    validated_effort = validate_effort(body.effort)

    if "/" in agent_ref:
        # Unmanaged ref (<harness>/<slug>): edit the harness file in place.
        if body.name is None or body.description is None:
            raise MutationError("name and description are required to edit an unmanaged agent")
        unmanaged_detail = container.agents_inventory.detail(agent_ref)
        if unmanaged_detail is None:
            raise MutationError(f"agent not found: {agent_ref}", status=404)
        prev_skills = tuple(s.slug for s in unmanaged_detail.skills)
        container.agents_mutations.update_unmanaged(
            agent_ref,
            name=body.name,
            description=body.description,
            prompt=body.prompt,
            tools=tuple(body.tools) if body.tools is not None else None,
            skills=validated_skills,
            model=body.model,
            effort=validated_effort,
            metadata=extra_metadata,
        )
    else:
        current = container.agents_store.get(agent_ref)
        if current is None:
            raise MutationError(f"agent not found: {agent_ref}", status=404)
        prev_skills = current.skills
        container.agents_store.update(
            agent_ref,
            name=body.name,
            description=body.description,
            prompt=body.prompt,
            tools=tuple(body.tools) if body.tools is not None else None,
            skills=validated_skills,
            model=body.model,
            effort=validated_effort,
            metadata=extra_metadata,
        )

    skills_changed = validated_skills is not None and validated_skills != prev_skills
    auto_enabled_pairs: list[tuple[str, str]] = []
    failed_pairs: list[tuple[str, str, str]] = []
    if skills_changed and validated_skills:
        auto_enabled_pairs, failed_pairs = (
            container.agents_mutations.auto_enable_skills_for_agent(agent_ref, validated_skills)
        )

    container.invalidation.invalidate_all()
    return _require_detail(
        container,
        agent_ref,
        auto_enabled=[
            AutoEnabledSkillResponse(skillRef=ref, harness=h)
            for ref, h in auto_enabled_pairs
        ],
        failed=[
            AutoEnableFailureResponse(skillRef=ref, harness=h, error=err)
            for ref, h, err in failed_pairs
        ],
    )


@router.delete("/{agent_ref:path}", response_model=OkResponse)
def delete_agent(
    agent_ref: str,
    container: BackendContainer = Depends(get_container),
) -> OkResponse:
    container.agents_mutations.delete(agent_ref)
    container.invalidation.invalidate_all()
    return OkResponse(ok=True)


@router.post("/{agent_ref:path}/enable", response_model=OkResponse)
def enable_agent(
    agent_ref: str,
    body: AgentHarnessRequest,
    container: BackendContainer = Depends(get_container),
) -> OkResponse:
    container.agents_mutations.enable(agent_ref, body.harness)
    container.invalidation.invalidate_all()
    return OkResponse(ok=True)


@router.post("/{agent_ref:path}/disable", response_model=OkResponse)
def disable_agent(
    agent_ref: str,
    body: AgentHarnessRequest,
    container: BackendContainer = Depends(get_container),
) -> OkResponse:
    container.agents_mutations.disable(agent_ref, body.harness)
    container.invalidation.invalidate_all()
    return OkResponse(ok=True)


@router.post("/{agent_ref:path}/set-harnesses", response_model=SetAgentHarnessesResultResponse)
def set_agent_harnesses(
    agent_ref: str,
    body: SetAgentHarnessesRequest,
    container: BackendContainer = Depends(get_container),
) -> SetAgentHarnessesResultResponse:
    succeeded, failed = container.agents_mutations.set_harnesses(agent_ref, body.harnesses)
    container.invalidation.invalidate_all()
    return SetAgentHarnessesResultResponse(
        ok=not failed,
        succeeded=succeeded,
        failed=[
            AgentMutationFailureResponse(harness=harness, error=error) for harness, error in failed
        ],
    )


@router.post(
    "/{agent_ref:path}/adopt",
    response_model=AdoptAgentResponse,
    responses={409: {"model": AdoptAgentConflictResponse}},
)
def adopt_agent(
    agent_ref: str,
    body: AdoptAgentRequest,
    container: BackendContainer = Depends(get_container),
):
    try:
        slug = container.agents_mutations.adopt(agent_ref, body.onConflict)
    except AgentAdoptConflict as conflict:
        # 409 with both sides: the client asks the user which version wins, then retries
        # with onConflict. Nothing has been mutated at this point.
        return JSONResponse(
            status_code=409,
            content=AdoptAgentConflictResponse(
                error="An agent with this name already exists in the store.",
                slug=conflict.slug,
                storePath=str(conflict.store_path),
                harnessPath=str(conflict.harness_path),
            ).model_dump(),
        )
    container.invalidation.invalidate_all()
    return AdoptAgentResponse(ok=True, ref=slug)


def _detail(
    detail: AgentDetail,
    *,
    auto_enabled: list[AutoEnabledSkillResponse] | None = None,
    failed: list[AutoEnableFailureResponse] | None = None,
) -> AgentDetailResponse:
    failed_list = failed or []
    return AgentDetailResponse(
        ref=detail.ref,
        name=detail.name,
        description=detail.description,
        prompt=detail.prompt,
        tools=list(detail.tools),
        document=detail.document,
        storePath=str(detail.store_path) if detail.store_path is not None else None,
        harnesses=[
            AgentHarnessDetailResponse(
                harness=harness.harness,
                label=harness.label,
                logoKey=harness.logo_key,
                state=harness.state,
                detail=harness.detail,
                path=str(harness.path),
                installMethod=harness.install_method,
                installed=harness.installed,
            )
            for harness in detail.harnesses
        ],
        configuration=[
            AgentConfigEntryResponse(key=key, value=value) for key, value in detail.configuration
        ],
        canDelete=detail.can_delete,
        canEdit=detail.can_edit,
        tags=list(detail.tags),
        skills=[
            AgentSkillResponse(slug=s.slug, name=s.name) for s in detail.skills
        ],
        model=detail.model,
        effort=detail.effort,
        ok=len(failed_list) == 0,
        autoEnabled=auto_enabled or [],
        failed=failed_list,
    )


def _require_detail(
    container: BackendContainer,
    ref: str,
    *,
    auto_enabled: list[AutoEnabledSkillResponse] | None = None,
    failed: list[AutoEnableFailureResponse] | None = None,
) -> AgentDetailResponse:
    detail = container.agents_inventory.detail(ref)
    if detail is None:
        raise MutationError(f"agent not found: {ref}", status=404)
    return _detail(detail, auto_enabled=auto_enabled, failed=failed)
