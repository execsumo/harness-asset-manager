from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from harness_asset_manager.api.deps import get_container
from harness_asset_manager.api.schemas import (
    AttachAgentsRequest,
    AttachAgentsResponse,
    BulkManageResultResponse,
    CreateSkillRequest,
    CreateSkillResponse,
    DisableSkillRequest,
    EnableSkillRequest,
    OkResponse,
    SetSkillHarnessesRequest,
    SetSkillHarnessesResultResponse,
    SetSkillTagsRequest,
    SkillDetailResponse,
    SkillSourceStatusResponse,
    SkillsPageResponse,
    SkillTagsResponse,
    UpdateSkillDocumentRequest,
)
from harness_asset_manager.application import BackendContainer

router = APIRouter(prefix="/api/skills")


@router.get("", response_model=SkillsPageResponse)
def list_skills(container: BackendContainer = Depends(get_container)) -> dict[str, object]:
    return container.skills_queries.list_skills()


@router.post("", response_model=CreateSkillResponse)
def create_skill(
    body: CreateSkillRequest,
    container: BackendContainer = Depends(get_container),
) -> dict[str, object]:
    return container.skills_mutations.create_skill(
        name=body.name,
        description=body.description,
        body=body.body,
        metadata=[{"key": entry.key, "value": entry.value} for entry in body.metadata],
        harnesses=body.harnesses,
    )


@router.get("/{skill_ref}/source-status", response_model=SkillSourceStatusResponse)
def get_skill_source_status(skill_ref: str, container: BackendContainer = Depends(get_container)) -> dict[str, object]:
    payload = container.skills_queries.get_skill_source_status(skill_ref)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "skill_not_found", "error": f"unknown skill ref: {skill_ref}"},
        )
    return payload


@router.get("/{skill_ref}", response_model=SkillDetailResponse)
def get_skill_detail(skill_ref: str, container: BackendContainer = Depends(get_container)) -> dict[str, object]:
    payload = container.skills_queries.get_skill_detail(skill_ref)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "skill_not_found", "error": f"unknown skill ref: {skill_ref}"},
        )
    return payload


@router.put("/{skill_ref}/tags", response_model=SkillTagsResponse)
def set_skill_tags(
    skill_ref: str,
    body: SetSkillTagsRequest,
    container: BackendContainer = Depends(get_container),
) -> dict[str, object]:
    return container.skills_mutations.set_skill_tags(skill_ref, body.tags)


@router.put("/{skill_ref}/document", response_model=OkResponse)
def update_skill_document(
    skill_ref: str,
    body: UpdateSkillDocumentRequest,
    container: BackendContainer = Depends(get_container),
) -> dict[str, bool]:
    metadata_entries: list[dict[str, str]] | None = None
    if body.metadata is not None:
        if isinstance(body.metadata, list):
            metadata_entries = [
                {"key": m.key if hasattr(m, "key") else m["key"], "value": m.value if hasattr(m, "value") else m["value"]}
                for m in body.metadata
            ]
        elif isinstance(body.metadata, dict):
            metadata_entries = [{"key": k, "value": str(v)} for k, v in body.metadata.items()]
    return container.skills_mutations.update_skill_document(
        skill_ref,
        body=body.body,
        metadata=metadata_entries,
    )


@router.post("/{skill_ref}/enable", response_model=OkResponse)
def enable_skill(
    skill_ref: str,
    body: EnableSkillRequest,
    container: BackendContainer = Depends(get_container),
) -> dict[str, bool]:
    return container.skills_mutations.enable_skill(skill_ref, body.harness)


@router.post("/{skill_ref}/disable", response_model=OkResponse)
def disable_skill(
    skill_ref: str,
    body: DisableSkillRequest,
    container: BackendContainer = Depends(get_container),
) -> dict[str, bool]:
    return container.skills_mutations.disable_skill(skill_ref, body.harness)


@router.post("/{skill_ref}/set-harnesses", response_model=SetSkillHarnessesResultResponse)
def set_skill_harnesses(
    skill_ref: str,
    body: SetSkillHarnessesRequest,
    container: BackendContainer = Depends(get_container),
) -> dict[str, object]:
    return container.skills_mutations.set_skill_all_harnesses(skill_ref, body.target)


@router.post("/{skill_ref}/manage", response_model=OkResponse)
def manage_skill(skill_ref: str, container: BackendContainer = Depends(get_container)) -> dict[str, bool]:
    return container.skills_mutations.manage_skill(skill_ref)


@router.post("/manage-all", response_model=BulkManageResultResponse)
def manage_all_skills(container: BackendContainer = Depends(get_container)) -> dict[str, object]:
    return container.skills_mutations.manage_all_skills()


@router.post("/{skill_ref}/update", response_model=OkResponse)
def update_skill(skill_ref: str, container: BackendContainer = Depends(get_container)) -> dict[str, bool]:
    return container.skills_mutations.update_skill(skill_ref)


@router.post("/{skill_ref}/unmanage", response_model=OkResponse)
def unmanage_skill(skill_ref: str, container: BackendContainer = Depends(get_container)) -> dict[str, bool]:
    return container.skills_mutations.unmanage_skill(skill_ref)


@router.post("/{skill_ref}/delete", response_model=OkResponse)
def delete_skill(skill_ref: str, container: BackendContainer = Depends(get_container)) -> dict[str, bool]:
    return container.skills_mutations.delete_skill(skill_ref)

@router.post("/attach-agents", response_model=AttachAgentsResponse)
def attach_agents(
    req: AttachAgentsRequest,
    container: BackendContainer = Depends(get_container),
) -> dict[str, object]:
    from harness_asset_manager.api.schemas import (
        AutoEnabledSkillResponse,
        AutoEnableFailureResponse,
        SkippedAgentResponse,
    )
    from harness_asset_manager.application.agents.hermes_profile import ensure_profile

    # 1. Normalise skillRefs and validate
    bare_slugs = [ref.removeprefix("shared:") for ref in req.skillRefs]
    validated_skills = container.agents_mutations.validate_skills(bare_slugs)

    changed = []
    skipped = []
    auto_enabled = []
    failed = []

    for agent_ref in req.agentRefs:
        agent = container.agents_store.get(agent_ref)
        if agent is None:
            skipped.append(SkippedAgentResponse(ref=agent_ref, reason="agent not found"))
            continue

        current_skills = agent.skills or ()

        if req.mode == "attach":
            new_skills = list(current_skills)
            for slug in validated_skills:
                if slug not in new_skills:
                    new_skills.append(slug)
            next_skills = tuple(new_skills)
        else:  # detach
            next_skills = tuple(s for s in current_skills if s not in validated_skills)

        if next_skills == current_skills:
            skipped.append(SkippedAgentResponse(ref=agent_ref, reason="no changes needed"))
            continue

        if req.dryRun:
            changed.append(agent_ref)
            projected, proj_failed = container.agents_mutations.project_auto_enable_bindings(
                agent_ref, next_skills
            )
            for s_ref, h in projected:
                auto_enabled.append(AutoEnabledSkillResponse(skillRef=s_ref, harness=h))
            for s_ref, h, err in proj_failed:
                failed.append(AutoEnableFailureResponse(skillRef=s_ref, harness=h, error=err))
            continue

        # apply
        previous = agent
        try:
            updated = container.agents_store.update(
                agent_ref,
                skills=next_skills,
            )
        except Exception as e:
            skipped.append(SkippedAgentResponse(ref=agent_ref, reason=str(e)))
            continue

        changed.append(agent_ref)

        try:
            ensure_profile(
                updated,
                container.hermes_root,
                previous=previous,
            )
        except Exception as e:  # noqa: BLE001 - keep the HAM agent update
            for slug in validated_skills:
                failed.append(
                    AutoEnableFailureResponse(
                        skillRef=f"shared:{slug}",
                        harness="hermes",
                        error=f"Hermes profile configuration failed: {e}",
                    )
                )

        try:
            ae, af = container.agents_mutations.auto_enable_skills_for_agent(
                agent_ref, next_skills
            )
        except Exception as e:  # noqa: BLE001 - keep the HAM agent update
            for slug in validated_skills:
                failed.append(
                    AutoEnableFailureResponse(
                        skillRef=f"shared:{slug}",
                        harness="unknown",
                        error=str(e),
                    )
                )
            continue
        for s_ref, h in ae:
            auto_enabled.append(AutoEnabledSkillResponse(skillRef=s_ref, harness=h))
        for s_ref, h, err in af:
            failed.append(AutoEnableFailureResponse(skillRef=s_ref, harness=h, error=err))

    if not req.dryRun:
        container.invalidation.invalidate_all()

    return {
        "changed": changed,
        "skipped": skipped,
        "autoEnabled": auto_enabled,
        "failed": failed,
    }
