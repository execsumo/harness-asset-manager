"""One home for reading and writing harness-owned config files.

Every family that binds into a harness config (MCP, hooks, permissions) performs the
same read-modify-write: load the whole document, mutate one subtree, write the whole
document back. That makes the *load/dump* pair — not the per-family mapper — the place
where a user's configuration is preserved or destroyed.

The invariant this module exists to hold is the one already stated in
``tests/unit/test_writer_round_trip.py``: HAM must never destroy user configuration
merely because it does not model it. The mappers held that for unmodeled **fields**;
this module extends it to unmodeled **file content** — comments, key order, and
formatting — for every format we write:

``toml``
    :class:`TomlDocument` keeps a ``tomlkit`` parse of the original alongside a plain
    view, and replays only what changed, so comments, key order, and array style
    survive. (The previous ``tomllib`` -> ``tomli_w`` pair silently dropped every
    comment in ``~/.codex/config.toml``, which carries all three Codex families.)
``jsonc``
    :class:`JsoncDocument` keeps the original text and re-emits untouched regions
    byte-for-byte, so comments outside the subtree HAM edits survive. JSONC is a format
    whose entire reason to exist is comments; rewriting it with ``json.dumps`` deleted
    all of them.
``yaml``
    ``ruamel.yaml`` in round-trip mode, which already preserved comments.
``json``
    Plain JSON has no comments to lose, so it is re-emitted with ``json.dumps``.

Comment preservation is best-effort *within* a subtree HAM rewrites: a comment sitting
between two keys of an object whose contents changed may be re-emitted without its
original blank-line spacing. Everything outside the changed region is verbatim.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from io import StringIO
from typing import Iterable, Mapping, MutableMapping

import tomlkit
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from tomlkit.exceptions import TOMLKitError
from tomlkit.toml_document import TOMLDocument

#: File formats a :class:`~harness_asset_manager.harness.ConfigSubtreeBindingProfile`
#: may declare. Keep in sync with ``harness/contracts.py``.
CONFIG_FILE_FORMATS = ("json", "jsonc", "toml", "yaml")


class ConfigDocumentError(ValueError):
    """A config file could not be parsed.

    Neutral on purpose: callers add the harness name and the HTTP status, because the
    same malformed-file condition means different things to different families.
    """


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config_document(text: str, *, file_format: str) -> dict[str, object]:
    """Parse ``text`` into a mutable mapping that remembers how to re-emit itself.

    The returned object is always a ``dict`` subclass — a format-specific one for
    ``toml``/``jsonc``, ``ruamel``'s ``CommentedMap`` for ``yaml`` — so mappers that
    branch on ``isinstance(value, dict)`` and mutate in place keep working unchanged.
    """
    if not text.strip():
        return empty_config_document(file_format)
    if file_format == "toml":
        try:
            return TomlDocument.parse(text)
        except TOMLKitError as error:
            raise ConfigDocumentError(f"not valid TOML: {error}") from error
    if file_format == "yaml":
        try:
            payload = _yaml().load(text)
        except YAMLError as error:
            raise ConfigDocumentError(f"not valid YAML: {error}") from error
        return payload if isinstance(payload, dict) else empty_config_document(file_format)
    if file_format in {"json", "jsonc"}:
        return _load_jsonc(text, file_format=file_format)
    raise ConfigDocumentError(f"unsupported config file format: {file_format}")


def dump_config_document(document: Mapping[str, object], *, file_format: str) -> str:
    """Serialize ``document``, preserving whatever the format's parser captured."""
    if file_format == "toml":
        if isinstance(document, TomlDocument):
            return document.dumps()
        return tomlkit.dumps(document)
    if file_format == "yaml":
        stream = StringIO()
        _yaml().dump(document, stream)
        return stream.getvalue()
    if file_format in {"json", "jsonc"}:
        if isinstance(document, JsoncDocument):
            return document.dumps()
        return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    raise ConfigDocumentError(f"unsupported config file format: {file_format}")


def empty_config_document(file_format: str) -> dict[str, object]:
    """A fresh, empty document of the right kind for ``file_format``."""
    if file_format == "toml":
        return TomlDocument()
    if file_format in {"json", "jsonc"}:
        return JsoncDocument()
    if file_format == "yaml":
        return {}
    raise ConfigDocumentError(f"unsupported config file format: {file_format}")


def new_subtree(file_format: str) -> dict[str, object]:
    """An empty nested container that keeps ``file_format``'s round-trip properties.

    A subtree HAM creates on the fly must be the format's own container type, or the
    dumper falls back to a generic rendering for that branch and loses the surrounding
    file's style.
    """
    if file_format == "yaml":
        return _yaml().map()
    return {}


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.default_flow_style = False
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def _load_jsonc(text: str, *, file_format: str) -> "JsoncDocument":
    blanked = blank_jsonc_comments(text) if file_format == "jsonc" else text
    try:
        payload = json.loads(blanked)
    except json.JSONDecodeError as error:
        raise ConfigDocumentError(f"not valid {file_format.upper()}: {error}") from error
    if not isinstance(payload, dict):
        return JsoncDocument()
    return JsoncDocument(
        payload, text=text, shape=_scan_shape(blanked), source=_Source(text, blanked)
    )


@dataclass(frozen=True)
class _Source:
    """The original bytes, plus the same bytes with comments blanked out.

    Both are the same length, so one offset indexes either. ``blanked`` is what makes
    "is this run of text nothing but a comment?" answerable without re-parsing — which is
    what lets a comment stranded in a *removed* member's prefix be carried back to the
    member it visually belongs to instead of being deleted with it.
    """

    text: str
    blanked: str

    def is_comment_only(self, start: int, end: int) -> bool:
        return not self.blanked[start:end].strip() and bool(self.text[start:end].strip())


# ---------------------------------------------------------------------------
# JSONC: comment blanking
# ---------------------------------------------------------------------------


def blank_jsonc_comments(text: str) -> str:
    """Replace JSONC comments and trailing commas with spaces, preserving length.

    Length preservation is the point: offsets into the blanked text index the original
    text unchanged, so the span scanner can run over comment-free input while the
    renderer still slices the user's real bytes — comments included.

    This is a proper string-aware scan rather than a regular expression. The regex it
    replaces was string-unaware and had two failure modes on real config: a value
    containing ``//`` truncated the document (hard parse failure), and a value
    containing ``/*...*/`` or ``, }`` was silently rewritten.
    """
    out = list(text)
    length = len(text)
    commas: list[int] = []
    index = 0
    in_string = False
    while index < length:
        char = text[index]
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] != "\n":
                out[index] = " "
                index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            out[index] = out[index + 1] = " "
            index += 2
            while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                if text[index] != "\n":
                    out[index] = " "
                index += 1
            if index + 1 < length:
                out[index] = out[index + 1] = " "
                index += 2
            else:  # unterminated block comment: blank the remainder
                while index < length:
                    if text[index] != "\n":
                        out[index] = " "
                    index += 1
            continue
        if char == ",":
            commas.append(index)
        index += 1
    blanked = "".join(out)
    for position in commas:
        cursor = position + 1
        while cursor < length and blanked[cursor].isspace():
            cursor += 1
        if cursor < length and blanked[cursor] in "}]":
            out[position] = " "
    return "".join(out)


# ---------------------------------------------------------------------------
# JSONC: span scanning
# ---------------------------------------------------------------------------


@dataclass
class _Member:
    """One ``"key": value`` pair, plus everything that leads up to it.

    ``prefix_start`` begins right after the opening brace or the previous member's
    comma, so the slice ``text[prefix_start:value.start]`` carries the member's leading
    whitespace, its comments, the quoted key, and the colon — all re-emitted verbatim.
    """

    key: str
    prefix_start: int
    value: "_Shape"


@dataclass
class _Shape:
    start: int
    end: int
    kind: str
    members: list[_Member] = field(default_factory=list)
    close: int = -1
    member_indent: str | None = None


class _ShapeScanner:
    """Records source spans for a JSON document already stripped of comments."""

    def __init__(self, text: str) -> None:
        self._text = text
        self._index = 0

    def scan(self) -> _Shape:
        self._skip_whitespace()
        return self._value()

    def _skip_whitespace(self) -> None:
        while self._index < len(self._text) and self._text[self._index].isspace():
            self._index += 1

    def _value(self) -> _Shape:
        char = self._text[self._index]
        if char == "{":
            return self._object()
        if char == "[":
            return self._array()
        return self._scalar()

    def _object(self) -> _Shape:
        start = self._index
        self._index += 1
        members: list[_Member] = []
        close = start
        while True:
            prefix_start = self._index
            self._skip_whitespace()
            if self._index >= len(self._text):
                close = self._index
                break
            if self._text[self._index] == "}":
                close = self._index
                self._index += 1
                break
            key = self._string_literal()
            self._skip_whitespace()
            self._index += 1  # the ':'
            self._skip_whitespace()
            members.append(_Member(key, prefix_start, self._value()))
            self._skip_whitespace()
            if self._index < len(self._text) and self._text[self._index] == ",":
                self._index += 1
                continue
            if self._index < len(self._text) and self._text[self._index] == "}":
                close = self._index
                self._index += 1
            break
        shape = _Shape(start, self._index, "object", members, close)
        shape.member_indent = _detect_member_indent(self._text, members)
        return shape

    def _array(self) -> _Shape:
        start = self._index
        self._index += 1
        depth = 1
        while self._index < len(self._text) and depth:
            char = self._text[self._index]
            if char == '"':
                self._string_literal()
                continue
            if char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
            self._index += 1
        return _Shape(start, self._index, "array")

    def _scalar(self) -> _Shape:
        start = self._index
        if self._text[self._index] == '"':
            self._string_literal()
        else:
            while self._index < len(self._text) and self._text[self._index] not in ",}] \t\r\n":
                self._index += 1
        return _Shape(start, self._index, "scalar")

    def _string_literal(self) -> str:
        start = self._index
        self._index += 1
        while self._index < len(self._text):
            char = self._text[self._index]
            if char == "\\":
                self._index += 2
                continue
            self._index += 1
            if char == '"':
                break
        raw = self._text[start : self._index]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:  # pragma: no cover - json.loads already accepted the file
            return raw.strip('"')


def _scan_shape(text: str) -> _Shape:
    return _ShapeScanner(text).scan()


def _detect_member_indent(text: str, members: Iterable[_Member]) -> str | None:
    """The indentation an added key should adopt, read off the first existing member."""
    for member in members:
        prefix = text[member.prefix_start :]
        head = prefix.split('"', 1)[0]
        if "\n" not in head:
            return None  # a single-line object: let the caller decide
        return head.rsplit("\n", 1)[1]
    return None


# ---------------------------------------------------------------------------
# JSONC: the document
# ---------------------------------------------------------------------------


class JsoncDocument(dict):
    """A parsed JSONC document that re-emits untouched regions verbatim.

    A plain ``dict`` subclass so every existing mapper — which branches on
    ``isinstance(value, dict)`` and mutates in place — works against it unchanged. The
    original text and its span tree ride alongside; :meth:`dumps` diffs the current
    contents against what was parsed and splices only what actually changed.
    """

    def __init__(
        self,
        data: dict[str, object] | None = None,
        *,
        text: str = "",
        shape: _Shape | None = None,
        source: _Source | None = None,
    ) -> None:
        super().__init__(data or {})
        self._text = text
        self._shape = shape
        self._source = source if source is not None else _Source(text, text)
        self._original = copy.deepcopy(dict(data or {}))

    def dumps(self) -> str:
        if self._shape is None or self._shape.kind != "object":
            return json.dumps(dict(self), ensure_ascii=False, indent=2) + "\n"
        body = _render(dict(self), self._original, self._shape, self._source, "")
        return self._text[: self._shape.start] + body + self._text[self._shape.end :]


def _render(new: object, old: object, shape: _Shape, source: _Source, indent: str) -> str:
    text = source.text
    if new == old:
        return text[shape.start : shape.end]
    if shape.kind != "object" or not isinstance(new, dict) or not isinstance(old, dict):
        return _emit(new, indent)

    member_indent = shape.member_indent if shape.member_indent is not None else indent + "  "
    # (member text, same-line trailing text). The trailing slot exists because a comment
    # parked after the *last* member is the one piece of the object no following member's
    # prefix picks up, and it has to be re-emitted after the separating comma, not before
    # it, or the comma ends up commented out.
    parts: list[tuple[str, str]] = []
    last_kept: _Member | None = None
    for member in shape.members:
        if member.key not in new:
            # A comment on the *previous* member's line lands in this member's prefix, so
            # removing this member would delete a comment about a key that is staying.
            rescued = _rescued_comment(source, member)
            if rescued and parts:
                parts[-1] = (parts[-1][0], parts[-1][1] + rescued)
            continue
        prefix = text[member.prefix_start : member.value.start]
        rendered = _render(
            new[member.key], old.get(member.key, _MISSING), member.value, source, member_indent
        )
        parts.append((prefix + rendered, ""))
        last_kept = member

    # Only the final surviving member can own a trailing slot, and only when nothing was
    # dropped after it — otherwise that region holds the deleted members' text.
    inline, closing = _trailing(shape, text, indent, last_kept)
    if parts and inline:
        parts[-1] = (parts[-1][0], parts[-1][1] + inline)

    known = {member.key for member in shape.members}
    for key in [key for key in new if key not in known]:
        parts.append((f"\n{member_indent}{json.dumps(key)}: {_emit(new[key], member_indent)}", ""))

    if not parts:
        return "{}"
    pieces: list[str] = []
    for index, (body, trailing) in enumerate(parts):
        pieces.append(body)
        if index < len(parts) - 1:
            pieces.append(",")
        pieces.append(trailing)
    return "{" + "".join(pieces) + closing


def _rescued_comment(source: _Source, member: _Member) -> str:
    """The comment-only head of a removed member's prefix, which belongs to its neighbour.

    ``{"a": 1,  // about a\n "b": 2}`` puts ``// about a`` in ``b``'s prefix because the
    prefix starts right after the comma. Dropping ``b`` must not take the note about ``a``
    with it.
    """
    head_end = source.text.find("\n", member.prefix_start, member.value.start)
    if head_end == -1 or not source.is_comment_only(member.prefix_start, head_end):
        return ""
    return source.text[member.prefix_start : head_end]


def _trailing(
    shape: _Shape,
    text: str,
    indent: str,
    last_kept: _Member | None,
) -> tuple[str, str]:
    """Split what sits between the last surviving member and ``}``.

    Returns ``(same_line, closing)``: the remainder of the last member's own line — a
    trailing comment, typically — and everything from the following newline through the
    closing brace. Splitting there is what lets a new member be appended *after* the last
    member's comment without the comment swallowing the comma that has to precede it.
    """
    default_closing = f"\n{indent}}}"
    if last_kept is None or not shape.members or last_kept is not shape.members[-1]:
        within = text[shape.start : shape.close]
        reindent = within[len(within.rstrip(" \t\r\n")) :]
        return "", (reindent + "}" if "\n" in reindent else default_closing)

    region = text[last_kept.value.end : shape.close]
    stripped = region.lstrip()
    if stripped.startswith(","):
        region = region[region.index(",") + 1 :]
    head, newline, rest = region.partition("\n")
    if not newline:
        # Single-line object: nothing to carry, and the brace keeps its own spacing.
        return "", (region + "}" if region.strip() else default_closing)
    return (head if head.strip() else ""), newline + rest + "}"


def _emit(value: object, indent: str) -> str:
    rendered = json.dumps(value, ensure_ascii=False, indent=2)
    if "\n" not in rendered:
        return rendered
    return ("\n" + indent).join(rendered.split("\n"))


# ---------------------------------------------------------------------------
# TOML: the document
# ---------------------------------------------------------------------------


class TomlDocument(dict):
    """A parsed TOML document that replays only what changed onto the original.

    ``tomlkit`` preserves comments, key order, and array style, but its containers
    **convert values on insertion** — append a plain ``dict`` to a ``tomlkit`` array and
    you get a converted copy, so a mapper that keeps its own reference and mutates it
    afterwards silently writes nothing. Several mappers do exactly that.

    So callers never see ``tomlkit`` types at all. They get plain ``dict``/``list``
    values — the same semantics ``tomllib`` gave them before — and :meth:`dumps` diffs
    the result against the parse and applies only the differences to the ``tomlkit``
    document. Untouched tables keep their comments and formatting; touched ones are
    edited in place rather than re-rendered wholesale.
    """

    def __init__(
        self,
        data: dict[str, object] | None = None,
        *,
        source: TOMLDocument | None = None,
    ) -> None:
        super().__init__(data or {})
        self._source: TOMLDocument = source if source is not None else tomlkit.document()
        self._original = copy.deepcopy(dict(data or {}))

    @classmethod
    def parse(cls, text: str) -> "TomlDocument":
        source = tomlkit.parse(text)
        return cls(_plain_mapping(source), source=source)

    def dumps(self) -> str:
        _apply_changes(self._source, dict(self), self._original)
        return tomlkit.dumps(self._source)


def _plain_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return {key: _plain(item) for key, item in value.items()}


def _plain(value: object) -> object:
    """Strip ``tomlkit`` wrappers so callers work with ordinary Python containers."""
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, bool) or value is None:
        return value
    for builtin in (str, int, float):
        if isinstance(value, builtin) and type(value) is not builtin:
            return builtin(value)
    return value


def _apply_changes(
    target: MutableMapping[str, object],
    new: Mapping[str, object],
    old: Mapping[str, object],
) -> None:
    """Write ``new`` into ``target``, touching only the keys that actually differ."""
    for key in [key for key in target if key not in new]:
        del target[key]
    for key, value in new.items():
        if key in old and value == old[key]:
            continue  # untouched: leave the original item, and its comments, alone
        existing = target.get(key)
        if isinstance(value, dict) and isinstance(old.get(key), dict) and isinstance(existing, dict):
            _apply_changes(existing, value, old[key])
            continue
        target[key] = value


class _Missing:
    """Sentinel: a key present after mutation that the parse never saw."""

    def __eq__(self, other: object) -> bool:
        return self is other

    def __hash__(self) -> int:
        return id(self)


_MISSING = _Missing()


__all__ = [
    "CONFIG_FILE_FORMATS",
    "ConfigDocumentError",
    "JsoncDocument",
    "TomlDocument",
    "blank_jsonc_comments",
    "dump_config_document",
    "empty_config_document",
    "load_config_document",
    "new_subtree",
]
