from dataclasses import dataclass

from harness_asset_manager.application.agents.store import AgentStore


@dataclass(frozen=True)
class AgentAttachment:
    ref: str
    name: str


def skill_attachments(store: AgentStore) -> dict[str, tuple[AgentAttachment, ...]]:
    """slug -> the managed agents whose `skills:` list names it.

    A read-only inversion of the agent store. Deliberately takes the store and
    not AgentInventoryService: build() runs the agent reconcile, which writes,
    and this is called from GET /api/skills (see S4).
    """
    agents, _issues = store.scan()
    attachments: dict[str, list[AgentAttachment]] = {}

    for agent in agents:
        att = AgentAttachment(ref=agent.ref, name=agent.name)
        for skill in agent.skills:
            if skill not in attachments:
                attachments[skill] = []
            attachments[skill].append(att)

    return {k: tuple(v) for k, v in attachments.items()}
