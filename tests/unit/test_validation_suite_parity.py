"""Keeps ``npm run validate`` a true mirror of what CI enforces.

``validate`` and ``.github/workflows/ci.yml`` are two hand-maintained lists that have
to agree, and twice now they have not: first when ``lint:backend`` was missing, and
again when ``codegen:check`` was, which is how commit 92bc4b5 put a stale OpenAPI
client on a red ``main``. Both times the omission was invisible locally — ``validate``
passed, CI did not.

This test removes the need to remember: add a validation step to CI without adding it
to ``validate`` and this fails, naming the command that would only ever have been
caught after the push.

``core-harness-gate`` is deliberately out of scope. It runs bare ``python`` with no
Node toolchain so it can report in seconds, and the test it runs is already covered by
``scripts/test_backend.sh`` discovering ``tests/unit``.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PACKAGE_JSON = REPO_ROOT / "package.json"

# Jobs whose steps are validation the developer is expected to be able to run locally.
VALIDATION_JOBS = ("backend-compat", "frontend-validate")

# Toolchain setup, not validation: these exist only to make the steps below runnable.
SETUP_PREFIXES = (
    "python -m venv",
    "pip install",
    "npm ci",
    "./.venv/bin/pip install",
    "./.venv/bin/python -m pip install",
)


def _job_blocks(workflow: str) -> dict[str, list[str]]:
    """Split the workflow into ``{job name: its lines}`` by two-space indent."""
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in workflow.splitlines():
        header = re.fullmatch(r"  ([A-Za-z][\w-]*):", line)
        if header:
            current = header.group(1)
            blocks[current] = []
        elif current is not None:
            blocks[current].append(line)
    return blocks


def _run_commands(lines: list[str]) -> list[str]:
    """Every shell command a job's ``run:`` steps execute, block scalars included."""
    commands: list[str] = []
    index = 0
    while index < len(lines):
        match = re.fullmatch(r"(\s*)run: (.*)", lines[index])
        index += 1
        if not match:
            continue
        indent, value = match.group(1), match.group(2).strip()
        if value not in ("|", "|-", ">", ">-"):
            commands.append(value)
            continue
        while index < len(lines):
            body = lines[index]
            if body.strip() and not body.startswith(indent + " "):
                break
            if body.strip():
                commands.append(body.strip())
            index += 1
    return commands


def _leaf_commands(script: str, scripts: dict[str, str]) -> set[str]:
    """Expand an npm script into the commands it ultimately runs."""
    leaves: set[str] = set()
    for part in script.split("&&"):
        command = part.strip()
        if not command:
            continue
        referenced = re.fullmatch(r"npm run ([\w:-]+)", command)
        if referenced and referenced.group(1) in scripts:
            leaves |= _leaf_commands(scripts[referenced.group(1)], scripts)
        else:
            leaves.add(command)
    return leaves


class ValidationSuiteParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scripts = json.loads(PACKAGE_JSON.read_text())["scripts"]
        self.jobs = _job_blocks(CI_WORKFLOW.read_text())

    def test_validate_runs_every_ci_validation_step(self) -> None:
        covered = _leaf_commands(self.scripts["validate"], self.scripts)
        for job in VALIDATION_JOBS:
            self.assertIn(job, self.jobs, f"CI job {job!r} disappeared or was renamed")
            for command in _run_commands(self.jobs[job]):
                if command.startswith(SETUP_PREFIXES):
                    continue
                # Expand both sides the same way: CI names npm scripts for some steps
                # and raw commands for others, and either spelling means the same work.
                for leaf in _leaf_commands(command, self.scripts):
                    self.assertIn(
                        leaf,
                        covered,
                        f"CI job {job!r} runs {command!r} but `npm run validate` does "
                        "not. Add it to the validate script in package.json so the "
                        "suite keeps matching CI.",
                    )

    def test_validation_jobs_still_have_steps_to_check(self) -> None:
        # Guards the parity test itself: a parse that silently found nothing would
        # pass the assertion above no matter how far validate drifted.
        for job in VALIDATION_JOBS:
            checked = [
                command
                for command in _run_commands(self.jobs[job])
                if not command.startswith(SETUP_PREFIXES)
            ]
            self.assertGreater(len(checked), 1, f"parsed no CI steps for job {job!r}")


if __name__ == "__main__":
    unittest.main()
