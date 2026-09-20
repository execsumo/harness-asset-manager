from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Mapping

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .model import (
    CONTRACT_KEY_SET,
    CONTRACT_KEYS,
    MODE_DEFAULT,
    RETIRED_KEYS,
    SPAWNING_DEFAULT,
    TRUST_PROJECT_DEFAULT,
    AgentDefinition,
    AgentParseError,
)

_yaml = YAML(typ="safe")
_rt_yaml = YAML()
_rt_yaml.default_flow_style = False

# Claude Code treats hooks as an optional collection. An empty/null value means
# the feature is unset, so do not emit a misleading frontmatter key for it.
_OPTIONAL_COLLECTION_KEYS = frozenset({"hooks"})

# Unknown *harness* keys are preserved on write. These keys are not unknown metadata:
# they were invalid HAM contract fields and are intentionally removed rather than
# carried into Claude Code agent files.

def parse_hermes_extras(raw: Mapping[str, object]) -> tuple[str | None, str | None]:
    """Read the optional Hermes sidecar values without imposing a provider vocabulary."""
    provider = raw.get("provider")
    model = raw.get("model")
    return (
        str(provider).strip() if provider is not None else None,
        str(model).strip() if model is not None else None,
    )


def parse_agent_file(path: Path) -> AgentDefinition:
    try:
        document = path.read_text(encoding="utf-8")
    except OSError as error:
        raise AgentParseError(f"unable to read agent file {path}: {error}") from error
    return parse_agent_document(document, slug=path.stem, path=path)


def parse_agent_document(document: str, *, slug: str, path: Path) -> AgentDefinition:
    """Parse an agent definition.

    Everything in ``CONTRACT_KEYS`` drives behavior as a contract field. Every other
    frontmatter key is kept verbatim in ``metadata`` — harness agents carry
    `permissionMode`, Cursor's `readonly`, and so on, and Harness Asset Manager must
    display those without interpreting or destroying them. The only keys dropped on
    write are ``RETIRED_KEYS`` and attempts to smuggle standard contract fields through
    the custom metadata channel.
    """
    try:
        metadata, prompt = split_frontmatter(document)
    except AgentParseError as error:
        # Name the file: this message is what the Needs Review row shows, and an
        # agent whose frontmatter will not parse can only be fixed at its path.
        raise AgentParseError(f"{path}: {error}") from error
    return AgentDefinition(
        slug=slug,
        name=_required_str(metadata, "name", slug),
        description=str(metadata.get("description", "") or "").strip(),
        role=_optional_str(metadata, "role"),
        harness=_optional_str(metadata, "harness"),
        prompt=prompt.strip(),
        tools=_str_tuple(metadata.get("tools"), "tools"),
        path=path,
        metadata=dict(metadata),
        skills=_str_tuple(metadata.get("skills"), "skills", dedupe=True),
        color=_optional_str(metadata, "color"),
        model=_optional_str(metadata, "model"),
        effort=_optional_str(metadata, "effort"),
        max_turns=_optional_str(metadata, "maxTurns"),
        isolation=_optional_str(metadata, "isolation"),
        disallowed_tools=_str_tuple(metadata.get("disallowedTools"), "disallowedTools"),
        background=_optional_bool_str(metadata, "background"),
        memory=_optional_str(metadata, "memory"),
        mode=_optional_str(metadata, "mode") or MODE_DEFAULT,
        spawning=_optional_bool_str(metadata, "spawning") or SPAWNING_DEFAULT,
        trust_project=_optional_bool_str(metadata, "trust-project") or TRUST_PROJECT_DEFAULT,
        deny_tools=_str_tuple(metadata.get("deny-tools"), "deny-tools"),
    )


def render_agent_document(
    *,
    name: str,
    description: str,
    prompt: str,
    tools: tuple[str, ...] = (),
    skills: tuple[str, ...] = (),
    mcp_servers: tuple[str, ...] = (),
    color: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    max_turns: str | None = None,
    isolation: str | None = None,
    disallowed_tools: tuple[str, ...] = (),
    background: str | None = None,
    role: str | None = None,
    harness: str | None = None,
    memory: str | None = None,
    mode: str = MODE_DEFAULT,
    spawning: str = SPAWNING_DEFAULT,
    trust_project: str = TRUST_PROJECT_DEFAULT,
    deny_tools: tuple[str, ...] = (),
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
        if mcp_servers:
            metadata["mcpServers"] = list(mcp_servers)
        # Written unquoted, so `maxTurns: 30` and `background: true` come back out of
        # YAML as the int and bool Claude Code expects rather than as strings.
        for scalar_key, scalar_value in (
            ("color", color),
            ("role", role),
            ("harness", harness),
            ("model", model),
            ("effort", effort),
            ("maxTurns", max_turns),
            ("isolation", isolation),
            ("background", background),
            ("memory", memory),
            ("mode", mode),
            ("spawning", spawning),
            ("trust-project", trust_project),
        ):
            if scalar_value:
                metadata[scalar_key] = scalar_value
        if disallowed_tools:
            metadata["disallowedTools"] = list(disallowed_tools)
        # Keep the optional list in the canonical contract position when an edit is
        # rendered with an explicit metadata payload. An empty list is still an
        # explicit, harmless value and preserves the contract's stable field order.
        metadata["deny-tools"] = list(deny_tools)

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
            if (
                k
                and k not in CONTRACT_KEY_SET
                and k not in RETIRED_KEYS
                and not _is_unset_optional_collection(k, v)
            ):
                metadata[k] = v
                custom_keys.append(k)

        if mcp_servers and "mcpServers" not in custom_keys:
            custom_keys.append("mcpServers")

        ordered = [k for k in CONTRACT_KEYS if k in metadata]
        ordered.extend(custom_keys)
    else:
        metadata = {
            key: value for key, value in (base_metadata or {}).items() if key not in RETIRED_KEYS
        }
        for key in _OPTIONAL_COLLECTION_KEYS:
            if _is_unset_optional_collection(key, metadata.get(key)):
                metadata.pop(key, None)
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

        if mcp_servers:
            metadata["mcpServers"] = list(mcp_servers)

        # Contract fields: an explicit empty string clears the key; None leaves a
        # configured base value untouched, but drops a base YAML null as unset.
        for contract_key, contract_value in (
            ("role", role),
            ("harness", harness),
            ("color", color),
            ("model", model),
            ("effort", effort),
            ("maxTurns", max_turns),
            ("isolation", isolation),
            ("background", background),
            ("memory", memory),
            ("mode", mode),
            ("spawning", spawning),
            ("trust-project", trust_project),
        ):
            if contract_value is None:
                # YAML ``null`` is the parsed form of an empty optional field. It
                # carries no Claude Code configuration and should not be rendered
                # back as ``key:``.
                if metadata.get(contract_key) is None:
                    metadata.pop(contract_key, None)
                continue
            if contract_value:
                metadata[contract_key] = contract_value
            elif contract_key in metadata:
                del metadata[contract_key]

        if disallowed_tools:
            metadata["disallowedTools"] = list(disallowed_tools)
        else:
            metadata.pop("disallowedTools", None)
        if deny_tools:
            metadata["deny-tools"] = list(deny_tools)
        elif "deny-tools" in metadata:
            del metadata["deny-tools"]

        # Contract fields lead in canonical order, then everything else in its original order.
        lead = [k for k in CONTRACT_KEYS if k in metadata]
        ordered = lead + [k for k in metadata if k not in lead]

    lines = ["---"]
    for key in ordered:
        lines.extend(_render_entry(key, metadata[key]))
    lines.append("---")
    document = "\n".join(lines) + "\n\n" + prompt.strip() + "\n"
    _verify_round_trip(document, ordered)
    return document


def _verify_round_trip(document: str, expected_keys: list[str]) -> None:
    """Refuse to hand back frontmatter that will not parse.

    Every writer renders first and writes second, so raising here turns a bad edit
    into a message instead of replacing a working agent file with one nothing can
    read. Without it a single unquotable value made the agent vanish from the list
    and left its binding stranded under Needs Review.
    """
    try:
        metadata, _ = split_frontmatter(document)
    except AgentParseError as error:
        raise AgentParseError(
            f"refusing to write unparseable agent frontmatter: {error}"
        ) from error
    missing = [key for key in expected_keys if key not in metadata]
    if missing:
        raise AgentParseError(
            "refusing to write agent frontmatter that does not round-trip; "
            f"these keys did not survive: {', '.join(missing)}"
        )


def _is_unset_optional_collection(key: str, value: object) -> bool:
    """Whether an optional Claude collection has no configured entries."""
    return key in _OPTIONAL_COLLECTION_KEYS and value in (None, "", [], {}, ())


def _quoted(text: str) -> str:
    """Emit ``text`` as a YAML double-quoted scalar.

    JSON string syntax is a subset of YAML's double-quoted style and ``json.dumps``
    already escapes everything that needs it, so it is the shortest correct emitter
    for the values a plain scalar cannot carry.
    """
    return json.dumps(text, ensure_ascii=False)


def _plain_scalar_survives(text: str, *, key: str | None) -> bool:
    """Whether ``text`` can be written unquoted without changing what YAML reads back.

    Contract fields are deliberately unquoted so ``maxTurns: 30`` and
    ``background: true`` come back as the int and bool Claude Code expects. That is
    only safe for text YAML resolves to itself. A description containing ``": "``
    parses as a nested mapping ("mapping values are not allowed here") and a ``#``
    silently truncates the value into a comment -- so rather than maintain a list of
    dangerous characters, emit the candidate line and ask the parser.
    """
    if text != text.strip() or "\n" in text:
        return False
    probe = f"- {text}\n" if key is None else f"{key}: {text}\n"
    try:
        loaded = _yaml.load(probe)
    except YAMLError:
        return False
    if key is None:
        if not isinstance(loaded, list) or len(loaded) != 1:
            return False
        parsed = loaded[0]
    else:
        if not isinstance(loaded, dict) or len(loaded) != 1:
            return False
        parsed = next(iter(loaded.values()))
    if isinstance(parsed, bool):
        # ``str(True)`` is ``"True"``; only the YAML spellings survive unquoted.
        return text in ("true", "false")
    if parsed is None:
        # Includes the empty string, which must be quoted or it reads back as null.
        return False
    return str(parsed) == text


def _scalar(value: object, *, key: str | None) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = value if isinstance(value, str) else str(value)
    return text if _plain_scalar_survives(text, key=key) else _quoted(text)


def _render_key(key: str) -> str:
    """Custom frontmatter keys come from the user too, so they get the same check."""
    try:
        loaded = _yaml.load(f"{key}: 0\n")
    except YAMLError:
        return _quoted(key)
    if isinstance(loaded, dict) and list(loaded) == [key]:
        return key
    return _quoted(key)


def _render_entry(key: str, value: object) -> list[str]:
    rendered_key = _render_key(key)
    if isinstance(value, (list, tuple)):
        if not value:
            return [f"{rendered_key}: []"]
        return [f"{rendered_key}:"] + [f"  - {_scalar(item, key=None)}" for item in value]
    if isinstance(value, dict):
        stream = io.StringIO()
        _rt_yaml.dump({key: value}, stream)
        return stream.getvalue().rstrip("\n").splitlines()
    if value is None:
        return [f"{rendered_key}:"]
    return [f"{rendered_key}: {_scalar(value, key=rendered_key)}"]


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


def _optional_str(metadata: dict, key: str) -> str | None:
    """Absent/null → None; otherwise the stripped string, empty string included."""
    if key not in metadata or metadata[key] is None:
        return None
    return str(metadata[key]).strip()


def _optional_bool_str(metadata: dict, key: str) -> str | None:
    """Like ``_optional_str``, but for a key YAML resolves to a real boolean.

    ``str(True)`` is ``"True"``, which is neither what the file said nor a value the
    picker offers, so the two literals are normalized back to their YAML spelling.
    """
    if key not in metadata or metadata[key] is None:
        return None
    value = metadata[key]
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


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
    "parse_hermes_extras",
    "parse_agent_document",
    "parse_agent_file",
    "render_agent_document",
    "split_frontmatter",
]
