from __future__ import annotations

import io
from pathlib import Path
from typing import Mapping

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .model import AgentDefinition, AgentParseError

_yaml = YAML(typ="safe")
_rt_yaml = YAML()
_rt_yaml.default_flow_style = False

# Written by the retired compile model and read by nothing. Unknown *harness* keys are
# preserved on write; these two are ours, dead, and dropped so they stop showing up as
# configuration. Everything else survives untouched.
RETIRED_KEYS = frozenset({"capabilities", "harnesses"})


def parse_agent_file(path: Path) -> AgentDefinition:
    try:
        document = path.read_text(encoding="utf-8")
    except OSError as error:
        raise AgentParseError(f"unable to read agent file {path}: {error}") from error
    return parse_agent_document(document, slug=path.stem, path=path)


def parse_agent_document(document: str, *, slug: str, path: Path) -> AgentDefinition:
    """Parse an agent definition.

    ``name``, ``description``, and ``tools`` drive behavior. Every other frontmatter
    key is kept verbatim in ``metadata`` — harness agents carry `model`,
    `permissionMode`, `maxTurns`, Cursor's `readonly`, and so on, and Harness Asset Manager
    must display those without interpreting or destroying them. The only keys dropped
    on write are ``RETIRED_KEYS``, which the retired compile model wrote and nothing
    reads.
    """
    metadata, prompt = split_frontmatter(document)
    return AgentDefinition(
        slug=slug,
        name=_required_str(metadata, "name", slug),
        description=str(metadata.get("description", "") or "").strip(),
        prompt=prompt.strip(),
        tools=_str_tuple(metadata.get("tools"), "tools"),
        path=path,
        metadata=dict(metadata),
        skills=_str_tuple(metadata.get("skills"), "skills", dedupe=True),
    )


def render_agent_document(
    *,
    name: str,
    description: str,
    prompt: str,
    tools: tuple[str, ...] = (),
    skills: tuple[str, ...] = (),
    base_metadata: Mapping[str, object] | None = None,
    extra_metadata: list[tuple[str, object]] | tuple[tuple[str, object], ...] | list[dict[str, str]] | None = None,
) -> str:
    """Render an agent file.

    When ``extra_metadata`` is supplied, it replaces the non-known frontmatter keys
    with the user's ordered key/value pairs.
    When ``base_metadata`` is supplied (any edit where extra_metadata is not explicitly set)
    the original frontmatter is the starting point and only the edited keys are replaced.
    """
    if extra_metadata is not None:
        metadata: dict[str, object] = {
            "name": name,
            "description": description,
        }
        if tools:
            metadata["tools"] = ", ".join(tools)
        if skills:
            metadata["skills"] = list(skills)

        custom_keys: list[str] = []
        for item in extra_metadata:
            if isinstance(item, dict):
                k = str(item.get("key", "")).strip()
                v = item.get("value", "")
            elif isinstance(item, (tuple, list)) and len(item) == 2:
                k = str(item[0]).strip()
                v = item[1]
            else:
                continue
            if k and k not in {"name", "description", "tools", "skills"} and k not in RETIRED_KEYS:
                metadata[k] = v
                custom_keys.append(k)

        ordered = ["name", "description"]
        if "tools" in metadata:
            ordered.append("tools")
        if "skills" in metadata:
            ordered.append("skills")
        ordered.extend(custom_keys)
    else:
        metadata = {
            key: value for key, value in (base_metadata or {}).items() if key not in RETIRED_KEYS
        }
        metadata["name"] = name
        metadata["description"] = description
        if tools:
            metadata["tools"] = ", ".join(tools)
        elif "tools" in metadata:
            # An explicit empty edit clears it; leave the key out rather than writing null.
            del metadata["tools"]

        if skills:
            metadata["skills"] = list(skills)
        elif "skills" in metadata:
            del metadata["skills"]

        # `name` and `description` lead, then everything else in its original order.
        ordered = ["name", "description"] + [k for k in metadata if k not in {"name", "description"}]

    lines = ["---"]
    for key in ordered:
        lines.extend(_render_entry(key, metadata[key]))
    lines.append("---")
    return "\n".join(lines) + "\n\n" + prompt.strip() + "\n"


def _render_entry(key: str, value: object) -> list[str]:
    if isinstance(value, (list, tuple)):
        if not value:
            return [f"{key}: []"]
        return [f"{key}:"] + [f"  - {item}" for item in value]
    if isinstance(value, dict):
        stream = io.StringIO()
        _rt_yaml.dump({key: value}, stream)
        return stream.getvalue().rstrip("\n").splitlines()
    if value is None:
        return [f"{key}:"]
    if isinstance(value, str):
        # Quote the empty string so it round-trips as "" rather than becoming null.
        return [f'{key}: ""'] if value == "" else [f"{key}: {value}"]
    if isinstance(value, bool):
        return [f"{key}: {'true' if value else 'false'}"]
    if isinstance(value, (int, float)):
        return [f"{key}: {value}"]
    return [f"{key}: {value}"]


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


def _str_tuple(value: object, label: str, *, dedupe: bool = False) -> tuple[str, ...]:
    """Accept both the list form and Claude Code's comma-separated string form."""
    if value is None:
        return ()
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        raise AgentParseError(f"{label} must be a list or comma-separated string")
    if dedupe:
        seen: set[str] = set()
        deduped: list[str] = []
        for it in items:
            if it not in seen:
                seen.add(it)
                deduped.append(it)
        return tuple(deduped)
    return tuple(items)


__all__ = [
    "parse_agent_document",
    "parse_agent_file",
    "render_agent_document",
    "split_frontmatter",
]
