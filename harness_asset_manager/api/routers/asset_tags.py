import logging
from collections.abc import Callable, Iterable
from typing import Any, cast

from fastapi import APIRouter, Depends

from harness_asset_manager.api.deps import get_container
from harness_asset_manager.application import BackendContainer
from harness_asset_manager.application.asset_tags import normalize_and_dedupe_tags, sort_tags

router = APIRouter(prefix="/api/asset-tags", tags=["asset-tags"])
logger = logging.getLogger(__name__)


@router.get("/")
def list_asset_tags(container: BackendContainer = Depends(get_container)) -> dict[str, list[str]]:
    def skill_tags() -> Iterable[str]:
        tags_by_ref = container.asset_tags.get_tags_for_family("skills")
        return [tag for skill in container.skills_queries._inventory_snapshot().entries
                for tag in tags_by_ref.get(skill.skill_ref, [])]

    def agent_tags() -> Iterable[str]:
        return [tag for agent in container.agents_inventory.snapshot().entries for tag in agent.tags]

    def row_tags(snapshot: Callable[[], dict[str, Any]]) -> Iterable[str]:
        rows = cast(list[dict[str, Any]], snapshot()["entries"])
        return [tag for row in rows for tag in row.get("tags", [])]

    def config_tags() -> Iterable[str]:
        tags_by_ref = container.asset_tags.get_tags_for_family("configs")
        return [tag for binding in container.harness_kernel.bindings_for_family("configs")
                for tag in tags_by_ref.get(binding.definition.harness, [])]

    sources: dict[str, Callable[[], Iterable[str]]] = {
        "skills": skill_tags,
        "agents": agent_tags,
        "slash_commands": container.slash_command_read_models.vocabulary_tags,
        "mcp": lambda: row_tags(container.mcp_queries._list_snapshot),
        "hooks": lambda: row_tags(container.hooks_queries._list_snapshot),
        "permissions": lambda: row_tags(container.permissions_queries._list_snapshot),
        "configs": config_tags,
    }
    tags: list[str] = []
    for family, collect in sources.items():
        try:
            tags.extend(collect())
        except Exception:
            logger.exception("Failed to collect shared tags for %s", family)
    return {"tags": sort_tags(normalize_and_dedupe_tags(tags))}
