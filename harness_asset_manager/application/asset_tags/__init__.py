from __future__ import annotations

from .service import (
    MAX_TAG_LENGTH,
    STARRED_TAG,
    AssetTagService,
    normalize_and_dedupe_tags,
    normalize_tag,
    sort_tags,
)
from .store import ASSET_TAG_SCHEMA_VERSION, AssetTagStore

__all__ = [
    "ASSET_TAG_SCHEMA_VERSION",
    "MAX_TAG_LENGTH",
    "STARRED_TAG",
    "AssetTagService",
    "AssetTagStore",
    "normalize_and_dedupe_tags",
    "normalize_tag",
    "sort_tags",
]
