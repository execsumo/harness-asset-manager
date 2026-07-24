from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .model import AgentDefinition, AgentParseError

_yaml = YAML(typ="safe")


def parse_agent_file(path: Path) -> AgentDefinition:
    try:
        document = path.read_text(encoding="utf-8")
    except OSError as error:
        raise AgentParseError(f"unable to read agent file {path}: {error}") from error
    return parse_agent_document(document, slug=path.stem, path=path)


def parse_agent_document(document: str, *, slug: str, path: Path) -> AgentDefinition:
    """Parse an agent definition.

    Only ``name``, ``description``, and ``tools`` are meaningful. Legacy keys from the
    retired compile model (``capabilities``, ``harnesses``) are ignored on read and
    dropped on the next write, so existing files keep working without a migration.
    """
    metadata, prompt = split_frontmatter(document)
    return AgentDefinition(
        slug=slug,
        name=_required_str(metadata, "name", slug),
        description=str(metadata.get("description", "") or "").strip(),
        prompt=prompt.strip(),
        tools=_str_tuple(metadata.get("tools"), "tools"),
        path=path,
    )


def render_agent_document(
    *, name: str, description: str, prompt: str, tools: tuple[str, ...] = ()
) -> str:
    """Render an agent file. Emits only the keys the current model understands."""
    lines = ["---", f"name: {name}", f"description: {description}"]
    if tools:
        lines.append("tools: " + ", ".join(tools))
    lines.append("---")
    return "\n".join(lines) + "\n\n" + prompt.strip() + "\n"


def split_frontmatter(document: str) -> tuple[dict, str]:
    lines = document.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise AgentParseError("agent definition is missing YAML frontmatter")
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            frontmatter_text = "".join(lines[1:index])
            body = "".join(lines[index + 1 :])
            try:
                metadata = _yaml.load(frontmatter_text) or {}
            except YAMLError as error:
                raise AgentParseError(f"invalid YAML frontmatter: {error}") from error
            if not isinstance(metadata, dict):
                raise AgentParseError("agent frontmatter must be a YAML mapping")
            return metadata, body
    raise AgentParseError("agent frontmatter is not terminated with ---")


def _required_str(metadata: dict, key: str, fallback: str) -> str:
    value = str(metadata.get(key, "") or "").strip()
    return value or fallback


def _str_tuple(value: object, label: str) -> tuple[str, ...]:
    """Accept both the list form and Claude Code's comma-separated string form."""
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    if not isinstance(value, list):
        raise AgentParseError(f"{label} must be a list or comma-separated string")
    return tuple(str(item).strip() for item in value if str(item).strip())


__all__ = [
    "parse_agent_document",
    "parse_agent_file",
    "render_agent_document",
    "split_frontmatter",
]
