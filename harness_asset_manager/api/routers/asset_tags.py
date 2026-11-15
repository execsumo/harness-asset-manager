from typing import Any, cast

from fastapi import APIRouter, Depends

from harness_asset_manager.api.deps import get_container
from harness_asset_manager.application import BackendContainer
from harness_asset_manager.application.asset_tags import normalize_and_dedupe_tags, sort_tags

router = APIRouter(prefix="/api/asset-tags", tags=["asset-tags"])


@router.get("/")
def list_asset_tags(container: BackendContainer = Depends(get_container)) -> dict[str, list[str]]:
    skills = container.skills_queries._inventory_snapshot().entries
    agents = container.agents_inventory.build().entries
    commands = container.slash_command_read_models.list_commands()
    mcp = container.mcp_queries._list_snapshot()["entries"]
    hooks = container.hooks_queries._list_snapshot()["entries"]
    permissions = container.permissions_queries._list_snapshot()["entries"]
    config_tags = container.asset_tags.get_tags_for_family("configs")
    skill_tags = container.asset_tags.get_tags_for_family("skills")
    rows = [
        *cast(list[dict[str, Any]], commands["commands"]),
        *cast(list[dict[str, Any]], commands["reviewCommands"]),
        *cast(list[dict[str, Any]], mcp),
        *cast(list[dict[str, Any]], hooks),
        *cast(list[dict[str, Any]], permissions),
    ]
    tags = [tag for row in rows for tag in row.get("tags", [])]
    tags.extend(tag for agent in agents for tag in agent.tags)
    tags.extend(tag for skill in skills for tag in skill_tags.get(skill.skill_ref, []))
    tags.extend(
        tag
        for binding in container.harness_kernel.bindings_for_family("configs")
        for tag in config_tags.get(binding.definition.harness, [])
    )
    return {"tags": sort_tags(normalize_and_dedupe_tags(tags))}
