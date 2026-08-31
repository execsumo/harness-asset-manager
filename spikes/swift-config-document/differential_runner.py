#!/usr/bin/env python3
"""Differential Runner for Phase 0 Spike.

Compares Python harness_asset_manager.config_document against Swift candidates
(JsoncDocument, TomlKitAdapter, TomlSurgicalEngine, YamsDocument) over identical
fixtures and mutations, reporting byte-level diffs and verdict classification.
"""

from __future__ import annotations

import difflib
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from harness_asset_manager.config_document import (
    dump_config_document as py_dump,
    load_config_document as py_load,
    ConfigDocumentError,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "Fixtures"
SWIFT_CLI = Path(__file__).resolve().parent / ".build" / "debug" / "SwiftConfigDocumentDiffCLI"


def run_swift(fixture_path: Path, file_format: str, backend: str, mutation: str) -> tuple[str, str | None]:
    cmd = [
        str(SWIFT_CLI),
        "--format", file_format,
        "--backend", backend,
        "--mutation", mutation,
        "--file", str(fixture_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        return "", proc.stderr.decode("utf-8")
    return proc.stdout.decode("utf-8"), None


def run_python(fixture_path: Path, file_format: str, mutation: str) -> tuple[str, str | None]:
    with open(fixture_path, "r", encoding="utf-8") as f:
        text = f.read()

    try:
        doc = py_load(text, file_format=file_format)
    except ConfigDocumentError as e:
        # If UTF-8 BOM caused python json.loads failure, try with utf-8-sig
        if "BOM" in str(e):
            with open(fixture_path, "r", encoding="utf-8-sig") as f:
                text_clean = f.read()
            try:
                doc = py_load(text_clean, file_format=file_format)
            except Exception as e2:
                return "", str(e2)
        else:
            return "", str(e)
    except Exception as e:
        return "", str(e)

    if mutation == "none":
        pass
    elif mutation == "add_mcp":
        if file_format == "toml":
            doc.setdefault("mcp_servers", {})["context7"] = {"command": "npx", "args": ["-y", "c7"]}
        elif file_format == "yaml":
            doc.setdefault("mcp_servers", {})["context7"] = {"command": "npx"}
        else:
            doc.setdefault("mcp", {})["context7"] = {"type": "local", "command": ["npx", "c7"]}
    elif mutation == "remove_mcp":
        if file_format in {"toml", "yaml"}:
            if "mcp_servers" in doc and "exa" in doc["mcp_servers"]:
                del doc["mcp_servers"]["exa"]
        else:
            if "mcp" in doc and "exa" in doc["mcp"]:
                del doc["mcp"]["exa"]
    elif mutation == "edit_scalar":
        if file_format == "toml":
            doc["model"] = "gpt-5-codex"
        elif file_format == "yaml":
            doc["model"] = "claude-3-7-sonnet-latest"
        else:
            doc["theme"] = "system"

    try:
        return py_dump(doc, file_format=file_format), None
    except Exception as e:
        return "", str(e)


def classify_diff(py_out: str, swift_out: str, original: str) -> str:
    if py_out == swift_out:
        return "IDENTICAL (0 bytes diff)"
    
    py_lines = py_out.splitlines()
    swift_lines = swift_out.splitlines()
    
    lost_comments = 0
    for line in py_lines:
        trimmed = line.strip()
        if (trimmed.startswith("#") or trimmed.startswith("//") or trimmed.startswith("/*")) and line not in swift_out:
            lost_comments += 1
            
    if lost_comments > 0:
        return f"DESTRUCTIVE: lost {lost_comments} comments"
    
    return "COSMETIC: style/order variance"


def main():
    if not SWIFT_CLI.exists():
        print(f"Building Swift CLI at {SWIFT_CLI}...")
        subprocess.run(["swift", "build"], cwd=Path(__file__).parent, check=True)

    fixtures = [
        ("opencode.jsonc", "jsonc", ["default"]),
        ("adversarial_crlf_bom_unicode.jsonc", "jsonc", ["default"]),
        ("codex_config.toml", "toml", ["tomlkit", "surgical"]),
        ("adversarial_toml_advanced.toml", "toml", ["tomlkit", "surgical"]),
        ("adversarial_yaml.yaml", "yaml", ["yams"]),
    ]

    mutations = ["none", "add_mcp", "remove_mcp", "edit_scalar"]

    results = []

    print("=" * 110)
    print(f"{'Fixture':<34} | {'Backend':<8} | {'Mutation':<12} | {'Verdict':<35} | {'Py vs Swift Bytes'}")
    print("=" * 110)

    for filename, fmt, backends in fixtures:
        fixture_path = FIXTURES_DIR / filename
        with open(fixture_path, "r", encoding="utf-8", errors="replace") as f:
            original_text = f.read()

        for backend in backends:
            for mut in mutations:
                py_out, py_err = run_python(fixture_path, fmt, mut)
                swift_out, swift_err = run_swift(fixture_path, fmt, backend, mut)

                if py_err:
                    verdict = f"PYTHON ERROR ({py_err.strip()})"
                elif swift_err:
                    verdict = f"SWIFT ERROR ({swift_err.strip()})"
                else:
                    verdict = classify_diff(py_out, swift_out, original_text)

                py_len = len(py_out.encode("utf-8")) if py_out else 0
                swift_len = len(swift_out.encode("utf-8")) if swift_out else 0

                results.append({
                    "fixture": filename,
                    "format": fmt,
                    "backend": backend,
                    "mutation": mut,
                    "verdict": verdict,
                    "py_bytes": py_len,
                    "swift_bytes": swift_len,
                })

                status_symbol = "✓" if "IDENTICAL" in verdict else ("~" if "COSMETIC" in verdict else "✗")
                byte_str = f"{py_len}B / {swift_len}B"
                print(f"[{status_symbol}] {filename:<31} | {backend:<8} | {mut:<12} | {verdict:<35} | {byte_str}")

    print("=" * 110)
    return 0


if __name__ == "__main__":
    sys.exit(main())
