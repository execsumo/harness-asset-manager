from __future__ import annotations

import json
import re
import tomllib
from collections.abc import MutableMapping
from io import StringIO
from pathlib import Path

import tomli_w
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from harness_asset_manager.errors import MutationError


def get_yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.default_flow_style = False
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml

def _strip_jsonc(text: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    without_line = re.sub(r"(^|[^:])//.*$", r"\1", without_block, flags=re.MULTILINE)
    return re.sub(r",(\s*[}\]])", r"\1", without_line)

def load_document(config_path: Path, file_format: str, harness_name: str) -> dict[str, object]:
    if not config_path.is_file():
        return {}
    text = config_path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    if file_format in {"json", "jsonc"}:
        try:
            payload = json.loads(_strip_jsonc(text) if file_format == "jsonc" else text)
        except json.JSONDecodeError as error:
            raise MutationError(
                f"{harness_name} config file is not valid {file_format.upper()}: {error}",
                status=409,
            ) from error
        return payload if isinstance(payload, MutableMapping) else {}
    if file_format == "yaml":
        try:
            payload = get_yaml().load(text) if text.strip() else {}
        except YAMLError as error:
            raise MutationError(
                f"{harness_name} config file is not valid YAML: {error}",
                status=409,
            ) from error
        return payload if isinstance(payload, MutableMapping) else {}
    try:
        payload = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise MutationError(
            f"{harness_name} config file is not valid TOML: {error}",
            status=409,
        ) from error
    return payload

def dump_document(document: dict[str, object], file_format: str) -> str:
    if file_format in {"json", "jsonc"}:
        return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if file_format == "yaml":
        stream = StringIO()
        get_yaml().dump(document, stream)
        return stream.getvalue()
    return tomli_w.dumps(document)
