# Handoff

## Phase 2: Family-Wide Asset Tagging and Stars (Completed)

Tag and star capabilities have been extended from Skills across all capability families: **Agents, Slash Commands, MCP, Hooks, and Permissions** (Configs are explicitly excluded per spec).

### Completed Features

1. **Tag and Star Data in Payloads**:
   - Backend `asset-tags.json` sidecar store tracks tags with persistent atomic writes and total reads on corrupt/missing files.
   - Pydantic response models across all families decorate list and detail endpoints with `tags: list[str]`.
   - Starred status is represented as `"starred"` tag with pinned index-0 sorting (`sort_tags`).

2. **UI & Filter Consistency**:
   - `TagFilterBar` integrated into all family pages (Agents, Slash Commands, MCP, Hooks, Permissions) with URL query parameter synchronization (`?tag=`).
   - Pinned starred quick-filter chip on tag filter bars.
   - Dedicated star column in matrix views with interactive star/unstar toggle.
   - Detail sheets and modals (Agents, Hooks, MCP, Permissions, Slash Commands) include tag viewing, addition, removal with autocomplete suggestions, and header star toggle.
   - Where managed-row multi-select is available (Skills, MCP, and Permissions), bulk action bars support starring and tagging alongside existing management actions. Agents, Hooks, and Slash Commands retain their separate untracked-adoption selection model.

3. **Validation & Testing**:
   - Unit tests covering `AssetTagStore` and `AssetTagService` (normalization, deduplication, length limits, concurrency).
   - Integration tests covering tag routes across each family (`test_*_tags_routes.py`).
   - Cross-family pressure test `tests/integration/test_cross_family_tags_pressure.py` validating end-to-end multi-family tag/star lifecycle, isolation, persistence, and error handling.
   - Frontend component and selector test suites covering tag extraction, filtering, and bulk operations.
