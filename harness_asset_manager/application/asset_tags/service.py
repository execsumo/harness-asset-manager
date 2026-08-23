from __future__ import annotations

from typing import Iterable

from harness_asset_manager.errors import MutationError

from .store import AssetTagStore

MAX_TAG_LENGTH = 64
STARRED_TAG = "starred"


def normalize_tag(tag: str) -> str:
    """Trim and validate a single tag string."""
    if not isinstance(tag, str):
        raise MutationError("tag must be a string", status=400, code="invalid_tag")
    trimmed = tag.strip()
    if not trimmed:
        raise MutationError("tag cannot be empty", status=400, code="invalid_tag")
    if len(trimmed) > MAX_TAG_LENGTH:
        raise MutationError(
            f"tag exceeds maximum length of {MAX_TAG_LENGTH} characters: {tag!r}",
            status=400,
            code="invalid_tag",
        )
    return trimmed


def normalize_and_dedupe_tags(tags: Iterable[str]) -> list[str]:
    """Validate, trim, case-fold dedupe while preserving first-seen display form."""
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        normalized = normalize_tag(tag)
        fold = normalized.casefold()
        if fold not in seen:
            seen.add(fold)
            result.append(normalized)
    return result


def sort_tags(tags: Iterable[str]) -> list[str]:
    """Sort tags alphabetically (case-insensitive) with ``starred`` pinned to the first position."""
    return sorted(
        tags,
        key=lambda t: (0 if t.casefold() == STARRED_TAG else 1, t.casefold()),
    )


class AssetTagService:
    def __init__(self, store: AssetTagStore) -> None:
        self.store = store

    def get_tags(self, family: str, ref: str) -> list[str]:
        raw = self.store.get_tags(f"{family}:{ref}")
        return sort_tags(raw)

    def get_tags_for_family(self, family: str) -> dict[str, list[str]]:
        all_tags = self.store.load()
        prefix = f"{family}:"
        return {
            key[len(prefix):]: sort_tags(tags)
            for key, tags in all_tags.items()
            if key.startswith(prefix)
        }

    def set_tags(self, family: str, ref: str, tags: Iterable[str]) -> list[str]:
        normalized = normalize_and_dedupe_tags(tags)
        sorted_tags = sort_tags(normalized)
        self.store.set_tags(f"{family}:{ref}", sorted_tags)
        return sorted_tags

    def delete_tags_for_ref(self, family: str, ref: str) -> None:
        self.store.set_tags(f"{family}:{ref}", [])
