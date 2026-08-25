"""Agent Skills specification conformance, reported and never enforced.

The spec (<https://agentskills.io/specification>) constrains a skill's `name` and
`description`. HAM does not adopt those rules as gates: it keys skills on the package
directory and uses `name` as a display name, so enforcing them would retroactively
invalidate skills that work today. What HAM can do is say, precisely, where a skill
departs from the standard — one issue per departure, each naming the fix.

This is the whole of HAM's validator. There is no separate tool and no third-party
dependency: the rules live here, next to the model they check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

# `name`: 1-64 chars, lowercase alphanumeric and hyphens, no leading, trailing, or
# consecutive hyphens. Transcribed from the specification, not inferred.
NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
NAME_MAX_LENGTH = 64
DESCRIPTION_MAX_LENGTH = 1024

ConformanceCode = Literal[
    "name_missing",
    "name_invalid",
    "name_too_long",
    "name_directory_mismatch",
    "description_missing",
    "description_too_long",
]


@dataclass(frozen=True)
class ConformanceIssue:
    """One departure from the spec, phrased as what to correct."""

    code: ConformanceCode
    message: str


def check_skill_conformance(
    *,
    name: str,
    name_declared: bool,
    description: str,
    package_dir: str | None,
) -> tuple[ConformanceIssue, ...]:
    """Every way this skill departs from the Agent Skills specification.

    ``name_declared`` separates "no `name:` field" from a name that was recovered
    from the document's first heading. Without it a fallback like
    ``Academic Research Toolkit`` reports as an invalid character set, which sends
    the reader to fix the wrong thing.

    ``package_dir`` is ``None`` for a skill seen only in a harness directory, which
    has no HAM package to match against — the directory rule is skipped, not failed.
    """
    issues: list[ConformanceIssue] = []

    if not name_declared:
        issues.append(
            ConformanceIssue(
                "name_missing",
                "No `name` field in the frontmatter — the display name is taken from "
                "the document's first heading. Add `name:` to SKILL.md.",
            )
        )
    else:
        if len(name) > NAME_MAX_LENGTH:
            issues.append(
                ConformanceIssue(
                    "name_too_long",
                    f"`name` is {len(name)} characters; the specification allows "
                    f"{NAME_MAX_LENGTH}.",
                )
            )
        elif not NAME_PATTERN.match(name):
            issues.append(
                ConformanceIssue(
                    "name_invalid",
                    f"`name` is `{name}`. The specification allows lowercase letters, "
                    "numbers, and single hyphens between them — no capitals, spaces, "
                    "leading or trailing hyphens, or doubled hyphens.",
                )
            )
        if package_dir is not None and name != package_dir:
            issues.append(
                ConformanceIssue(
                    "name_directory_mismatch",
                    f"`name` is `{name}` but the package directory is `{package_dir}`. "
                    "The specification requires them to match.",
                )
            )

    if not description.strip():
        issues.append(
            ConformanceIssue(
                "description_missing",
                "No `description` field. Agents use it to decide when the skill "
                "applies, so a skill without one is effectively undiscoverable.",
            )
        )
    elif len(description) > DESCRIPTION_MAX_LENGTH:
        issues.append(
            ConformanceIssue(
                "description_too_long",
                f"`description` is {len(description)} characters; the specification "
                f"allows {DESCRIPTION_MAX_LENGTH}.",
            )
        )

    return tuple(issues)


__all__ = [
    "DESCRIPTION_MAX_LENGTH",
    "NAME_MAX_LENGTH",
    "NAME_PATTERN",
    "ConformanceIssue",
    "check_skill_conformance",
]
