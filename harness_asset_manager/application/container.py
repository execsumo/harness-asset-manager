from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from harness_asset_manager.atomic_files import file_lock
from harness_asset_manager.harness import HarnessKernelService, HarnessSupportStore
from harness_asset_manager.harness.resolution import resolve_context
from harness_asset_manager.hashing import hash_file
from harness_asset_manager.paths import AppPaths, resolve_app_paths

from .agents import (
    AgentAuditLog,
    AgentBindingLedger,
    AgentHarnessAdapter,
    AgentInventoryService,
    AgentMutationService,
    AgentReconcileService,
    AgentStore,
    resolve_agent_targets,
)
from .cli_marketplace import CliMarketplaceCatalog
from .config_auto_adopt import McpAutoAdoptService, ObservedConfigAutoAdoptService
from .config_snapshots import ConfigSnapshotService
from .hooks import (
    HooksMutationService,
    HooksQueryService,
    HooksReadModelService,
    HookStore,
)
from .invalidation import InvalidationFanout
from .marketplace_cache import MarketplaceCache
from .mcp.availability import McpAvailabilityProbe
from .mcp.enrichment import McpEnrichmentService
from .mcp.marketplace import McpMarketplaceCatalog
from .mcp.mutations import McpMutationService
from .mcp.planner import McpAdoptionPlanner
from .mcp.query import McpQueryService
from .mcp.read_models import McpReadModelService
from .mcp.store import McpServerStore
from .mutation_audit import (
    AuditedMutationService,
    MutationAuditJournal,
    MutationPathTracker,
)
from .permissions import (
    PermissionsMutationService,
    PermissionsQueryService,
    PermissionsReadModelService,
    PermissionStore,
)
from .scaffold import ScaffoldService
from .settings import AutoAdoptStore, SettingsMutationService, SettingsQueryService
from .skills import SkillsMutationService, SkillsQueryService
from .skills.auto_adopt import SkillsAutoAdoptService
from .skills.marketplace import (
    MarketplaceCatalog,
    MarketplaceDocumentService,
    MarketplaceInstallService,
    MarketplaceQueryService,
)
from .skills.read_models import SkillsReadModelService
from .skills.source_fetch import SourceFetchService
from .skills.store import SkillStore
from .slash_commands import (
    SlashCommandMutationService,
    SlashCommandPathPolicy,
    SlashCommandPlanner,
    SlashCommandQueryService,
    SlashCommandReadModelService,
    SlashCommandStore,
    SlashCommandStorePaths,
    SlashCommandSyncStateStore,
    migrate_legacy_slash_commands,
    resolve_slash_targets,
)
from .slash_commands.auto_adopt import SlashCommandsAutoAdoptService


@dataclass(frozen=True)
class BackendContainer:
    paths: AppPaths
    harness_kernel: HarnessKernelService
    support_store: HarnessSupportStore
    invalidation: InvalidationFanout
    skills_source_fetcher: SourceFetchService
    skills_store: SkillStore
    skills_read_models: SkillsReadModelService
    skills_queries: SkillsQueryService
    skills_mutations: SkillsMutationService
    settings_queries: SettingsQueryService
    settings_mutations: SettingsMutationService
    slash_command_store: SlashCommandStore
    slash_command_sync_state: SlashCommandSyncStateStore
    slash_command_read_models: SlashCommandReadModelService
    slash_command_queries: SlashCommandQueryService
    slash_command_mutations: SlashCommandMutationService
    skills_marketplace_catalog: MarketplaceCatalog
    skills_marketplace_documents: MarketplaceDocumentService
    skills_marketplace_queries: MarketplaceQueryService
    skills_marketplace_installs: MarketplaceInstallService
    cli_marketplace_catalog: CliMarketplaceCatalog
    mcp_marketplace_catalog: McpMarketplaceCatalog
    mcp_store: McpServerStore
    mcp_read_models: McpReadModelService
    mcp_queries: McpQueryService
    mcp_mutations: McpMutationService
    hooks_store: HookStore
    hooks_read_models: HooksReadModelService
    hooks_queries: HooksQueryService
    hooks_mutations: HooksMutationService
    permissions_store: PermissionStore
    permissions_read_models: PermissionsReadModelService
    permissions_queries: PermissionsQueryService
    permissions_mutations: PermissionsMutationService
    scaffold_service: ScaffoldService
    agents_store: AgentStore
    agents_inventory: AgentInventoryService
    agents_mutations: AgentMutationService
    agents_audit: AgentAuditLog
    agents_reconcile: AgentReconcileService
    config_snapshots: ConfigSnapshotService
    mutation_audit: MutationAuditJournal
    app_home: Path


def _migrate_legacy_layouts(data_dir: Path, skills_store_root: Path, agents_root: Path) -> None:
    """Migrate old storage layouts into the new flat layout.

    Handles two old shapes:
      - pre-package: ``data_dir/shared`` → ``data_dir/skills``
      - package-layout: ``data_dir/packages/local/skills`` → ``data_dir/skills``
    and similarly for agents: ``data_dir/packages/local/agents`` → ``data_dir/agents``.
    Also moves legacy manifest files.
    """
    skills_store_root.mkdir(parents=True, exist_ok=True)
    agents_root.mkdir(parents=True, exist_ok=True)

    lock_path = data_dir / ".migration.lock"
    with file_lock(lock_path):
        # Skills migration
        legacy_shared = data_dir / "shared"
        legacy_pkg_skills = data_dir / "packages" / "local" / "skills"
        legacy_manifest = data_dir / "manifest.json"
        legacy_pkg_manifest = data_dir / "packages" / "local" / "manifest.json"

        # Migrate skills from old shapes if the new directory looks empty
        skills_populated = any(skills_store_root.iterdir()) if skills_store_root.is_dir() else False
        if not skills_populated:
            for legacy_dir in (legacy_pkg_skills, legacy_shared):
                if legacy_dir.is_dir():
                    for item in legacy_dir.iterdir():
                        target = skills_store_root / item.name
                        if not target.exists():
                            shutil.move(str(item), str(target))
                    break  # Only migrate the first-populated legacy shape

            # Manifest migration
            if not (data_dir / "skills-manifest.json").exists():
                if legacy_pkg_manifest.is_file():
                    shutil.copy2(str(legacy_pkg_manifest), str(data_dir / "skills-manifest.json"))
                elif legacy_manifest.is_file():
                    shutil.copy2(str(legacy_manifest), str(data_dir / "skills-manifest.json"))

        # Agents migration
        agents_populated = any(agents_root.iterdir()) if agents_root.is_dir() else False
        if not agents_populated:
            legacy_agents_dir = data_dir / "packages" / "local" / "agents"
            if legacy_agents_dir.is_dir():
                for item in legacy_agents_dir.iterdir():
                    target = agents_root / item.name
                    if not target.exists():
                        shutil.move(str(item), str(target))


def build_backend_container(
    env: dict[str, str] | None = None,
    *,
    marketplace_catalog: MarketplaceCatalog | None = None,
    mcp_marketplace_catalog: McpMarketplaceCatalog | None = None,
    cli_marketplace_catalog: CliMarketplaceCatalog | None = None,
    source_fetcher: SourceFetchService | None = None,
    mcp_availability_probe: McpAvailabilityProbe | None = None,
) -> BackendContainer:
    active_env = dict(os.environ)
    if env is not None:
        active_env.update(env)

    paths = resolve_app_paths(active_env)
    app_home = resolve_context(active_env).home
    
    _migrate_legacy_layouts(paths.data_dir, paths.skills_store_root, paths.agents_root)

    support_store = HarnessSupportStore(paths.settings_path)
    harness_kernel = HarnessKernelService.from_environment(active_env, support_store=support_store)
    invalidation = InvalidationFanout()
    mutation_audit = MutationAuditJournal(paths.mutation_audit_path)

    skills_store = SkillStore(
        paths.skills_store_root,
        manifest_path=paths.skills_store_manifest,
    )
    skills_read_models = SkillsReadModelService.from_kernel(store=skills_store, kernel=harness_kernel, data_dir=paths.data_dir)
    invalidation.register(skills_read_models)

    active_source_fetcher = source_fetcher or SourceFetchService()
    skills_queries = SkillsQueryService(skills_read_models, active_source_fetcher)
    skills_mutations = SkillsMutationService(skills_read_models, skills_queries, active_source_fetcher)
    auto_adopt_store = AutoAdoptStore(paths.settings_path)
    settings_queries = SettingsQueryService(harness_kernel, paths, auto_adopt_store)

    def auto_adopt_defaults(family: str) -> tuple[str, ...]:
        return auto_adopt_store.default_harnesses().get(family, ())
    slash_targets = resolve_slash_targets(harness_kernel)
    slash_command_store = SlashCommandStore(
        SlashCommandStorePaths(
            root=paths.slash_command_store_root,
            commands_dir=paths.slash_command_commands_dir,
        )
    )
    slash_command_sync_state = SlashCommandSyncStateStore(paths.slash_command_sync_state_path)
    slash_command_path_policy = SlashCommandPathPolicy()
    migrate_legacy_slash_commands(
        command_store=slash_command_store,
        sync_state_store=slash_command_sync_state,
        context=harness_kernel.context,
        targets=slash_targets,
        path_policy=slash_command_path_policy,
    )

    def resolve_slash_snapshot():
        # Re-resolved per call so toggling a harness in Settings takes effect at once.
        return resolve_slash_targets(harness_kernel)

    slash_command_read_models = SlashCommandReadModelService(
        slash_command_store,
        slash_command_sync_state,
        resolve_slash_snapshot,
        slash_command_path_policy,
    )
    slash_command_queries = SlashCommandQueryService(slash_command_read_models)
    slash_command_mutations = SlashCommandMutationService(
        slash_command_store,
        slash_command_sync_state,
        slash_command_queries,
        slash_command_read_models,
        SlashCommandPlanner(slash_command_path_policy),
        resolve_slash_snapshot,
    )
    slash_auto_adopt = SlashCommandsAutoAdoptService(
        read_models=slash_command_read_models,
        mutations=slash_command_mutations,
        is_enabled=lambda: auto_adopt_store.is_enabled("slash_commands"),
        journal=mutation_audit,
        default_harnesses=lambda: auto_adopt_defaults("slash_commands"),
    )
    slash_command_queries.set_reconcile(slash_auto_adopt.reconcile)

    cache = MarketplaceCache.from_environment(active_env)
    skills_catalog = marketplace_catalog or MarketplaceCatalog.from_environment(
        active_env,
        cache=cache,
        warm_on_init=False,
    )
    skills_documents = MarketplaceDocumentService(active_source_fetcher, cache=cache)
    skills_marketplace_queries = MarketplaceQueryService(skills_read_models, skills_catalog, skills_documents)
    skills_marketplace_installs = MarketplaceInstallService(skills_catalog, skills_mutations)
    cli_catalog = cli_marketplace_catalog or CliMarketplaceCatalog.from_environment(
        active_env,
        cache=cache,
    )

    mcp_store = McpServerStore(paths.mcp_store_manifest)
    mcp_read_models = McpReadModelService.from_kernel(store=mcp_store, kernel=harness_kernel)
    invalidation.register(mcp_read_models)
    settings_mutations = SettingsMutationService(
        harness_kernel, support_store, invalidation, auto_adopt_store
    )

    mcp_catalog = mcp_marketplace_catalog or McpMarketplaceCatalog.from_environment(
        active_env,
        cache=cache,
    )
    mcp_enrichment = McpEnrichmentService(mcp_catalog)
    mcp_planner = McpAdoptionPlanner(mcp_read_models)
    mcp_availability_probe = mcp_availability_probe or McpAvailabilityProbe()
    mcp_availability_cache = {}
    mcp_queries = McpQueryService(
        mcp_read_models,
        planner=mcp_planner,
        enrichment=mcp_enrichment,
        marketplace_catalog=mcp_catalog,
        availability_probe=mcp_availability_probe,
        availability_cache=mcp_availability_cache,
    )
    mcp_mutations = McpMutationService(
        store=mcp_store,
        read_models=mcp_read_models,
        planner=mcp_planner,
        marketplace_catalog=mcp_catalog,
        enrichment=mcp_enrichment,
        availability_probe=mcp_availability_probe,
        availability_cache=mcp_availability_cache,
    )
    mcp_auto_adopt = McpAutoAdoptService(
        planner=mcp_planner,
        mutations=mcp_mutations,
        is_enabled=lambda: auto_adopt_store.is_enabled("mcp"),
        journal=mutation_audit,
        default_harnesses=lambda: auto_adopt_defaults("mcp"),
    )
    mcp_queries.set_reconcile(mcp_auto_adopt.reconcile)

    hooks_store = HookStore(paths.hooks_store_manifest)
    hooks_read_models = HooksReadModelService.from_kernel(store=hooks_store, kernel=harness_kernel)
    invalidation.register(hooks_read_models)
    hooks_queries = HooksQueryService(hooks_read_models)
    hooks_mutations = HooksMutationService(
        store=hooks_store,
        read_models=hooks_read_models,
    )
    hooks_auto_adopt = ObservedConfigAutoAdoptService(
        read_models=hooks_read_models,
        store=hooks_store,
        promote=hooks_mutations.promote_hook,
        family="hooks",
        is_enabled=lambda: auto_adopt_store.is_enabled("hooks"),
        journal=mutation_audit,
        default_harnesses=lambda: auto_adopt_defaults("hooks"),
        enable_default=lambda ref, harness: hooks_mutations.enable_hook(ref, harness),
    )
    hooks_queries.set_reconcile(hooks_auto_adopt.reconcile)

    permissions_store = PermissionStore(paths.permissions_store_manifest)
    permissions_read_models = PermissionsReadModelService.from_kernel(store=permissions_store, kernel=harness_kernel)
    invalidation.register(permissions_read_models)
    permissions_queries = PermissionsQueryService(permissions_read_models)
    permissions_mutations = PermissionsMutationService(
        store=permissions_store,
        read_models=permissions_read_models,
    )
    permissions_auto_adopt = ObservedConfigAutoAdoptService(
        read_models=permissions_read_models,
        store=permissions_store,
        promote=permissions_mutations.promote_permission,
        family="permissions",
        is_enabled=lambda: auto_adopt_store.is_enabled("permissions"),
        journal=mutation_audit,
        default_harnesses=lambda: auto_adopt_defaults("permissions"),
        enable_default=lambda ref, harness: permissions_mutations.enable_permission(ref, harness),
    )
    permissions_queries.set_reconcile(permissions_auto_adopt.reconcile)

    scaffold_service = ScaffoldService(paths)
    agent_bindings = AgentBindingLedger(paths.bindings_ledger_path)

    def resolve_agents_snapshot():
        # Re-resolved per call so toggling a harness in Settings takes effect at once.
        targets = resolve_agent_targets(harness_kernel)
        return targets, {
            target.id: AgentHarnessAdapter(target, paths.agents_root) for target in targets
        }

    def rebaseline_agent_bindings(slug: str) -> None:
        """After we write a store file, re-record the baseline for **live** bindings.

        A live binding is a symlink, so the harness is already reading what we just
        wrote; re-baselining keeps a later clobber classifiable as one-sided. Bindings
        that are already broken are deliberately left alone — re-baselining one would
        make an independent store edit look like "the store never moved" and turn a
        genuine two-sided conflict into an automatic adopt that discards this edit.

        Rendered harnesses (Codex) are excluded for the same reason inverted: a store
        write does not reach them at all, so their copy is now stale, not current.
        """
        store_path = agents_store.path_for(slug)
        if not store_path.is_file():
            return
        _targets, adapters = resolve_agents_snapshot()
        live = tuple(
            harness
            for harness, adapter in adapters.items()
            if not adapter.renders and adapter.is_enabled(slug)
        )
        agent_bindings.rebaseline(slug, live, hash_file(store_path))

    agents_store = AgentStore(paths.agents_root, rebaseline_agent_bindings)
    agents_audit = AgentAuditLog(paths.agents_audit_path)
    agents_reconcile = AgentReconcileService(
        store=agents_store,
        resolve=resolve_agents_snapshot,
        ledger=agent_bindings,
        audit=agents_audit,
        conflicts_root=paths.agents_conflicts_root,
        # Read per call, not captured: switching auto-adopt off in Settings must stop
        # the next reconcile, not the next restart.
        is_enabled=lambda: auto_adopt_store.is_enabled("agents"),
        lock_path=paths.agents_reconcile_lock_path,
        default_harnesses=lambda: auto_adopt_defaults("agents"),
    )
    agents_mutations = AgentMutationService(
        agents_store, resolve_agents_snapshot, agent_bindings
    )

    config_snapshots = ConfigSnapshotService(paths)
    config_snapshots.capture_all_external_changes()

    skills_auto_adopt = SkillsAutoAdoptService(
        read_models=skills_read_models,
        mutations=skills_mutations,
        is_enabled=lambda: auto_adopt_store.is_enabled("skills"),
        journal=mutation_audit,
        lock_path=paths.data_dir / "auto-adopt.lock",
        default_harnesses=lambda: auto_adopt_defaults("skills"),
    )
    skills_queries.set_reconcile(skills_auto_adopt.reconcile)

    skills_tracker = MutationPathTracker(
        lambda: (
            (paths.skills_store_manifest, False),
            (paths.skills_store_root, False),
            *((adapter.managed_root, False) for adapter in skills_read_models.adapters),
        )
    )
    settings_tracker = MutationPathTracker(lambda: ((paths.settings_path, False),))
    slash_tracker = MutationPathTracker(
        lambda: (
            (paths.slash_command_store_root, True),
            *((target.output_dir, False) for target in resolve_slash_snapshot()),
        )
    )
    mcp_tracker = MutationPathTracker(
        lambda: (
            (paths.mcp_store_manifest, False),
            *(
                (config_path, False)
                for adapter in mcp_read_models.adapters
                for config_path in getattr(adapter, "_discovery_config_paths", (adapter.config_path,))
            ),
        )
    )
    hooks_tracker = MutationPathTracker(
        lambda: (
            (paths.hooks_store_manifest, False),
            *((adapter.config_path, False) for adapter in hooks_read_models.adapters),
        )
    )
    permissions_tracker = MutationPathTracker(
        lambda: (
            (paths.permissions_store_manifest, False),
            *((adapter.config_path, False) for adapter in permissions_read_models.adapters),
        )
    )
    agents_tracker = MutationPathTracker(
        lambda: (
            (paths.agents_root, True),
            (paths.bindings_ledger_path, False),
            *((target.output_dir, False) for target in resolve_agents_snapshot()[0]),
        )
    )
    snapshots_tracker = MutationPathTracker(lambda: ((paths.configs_dir, True),))
    scaffold_tracker = MutationPathTracker(
        lambda: (
            (paths.skills_store_root, True),
            (paths.agents_root, False),
            (paths.data_dir / "mcp" / "scaffolded", True),
            (paths.data_dir / "hooks" / "scaffolded", True),
        )
    )

    audited_skills_mutations = AuditedMutationService(
        skills_mutations,
        family="skills",
        journal=mutation_audit,
        path_tracker=skills_tracker,
    )
    audited_skills_marketplace_installs = AuditedMutationService(
        skills_marketplace_installs,
        family="skills",
        methods={"install_skill"},
        journal=mutation_audit,
        path_tracker=skills_tracker,
    )
    audited_settings_mutations = AuditedMutationService(
        settings_mutations,
        family="settings",
        journal=mutation_audit,
        path_tracker=settings_tracker,
    )
    audited_slash_mutations = AuditedMutationService(
        slash_command_mutations,
        family="slash_commands",
        journal=mutation_audit,
        path_tracker=slash_tracker,
    )
    audited_mcp_mutations = AuditedMutationService(
        mcp_mutations,
        family="mcp",
        journal=mutation_audit,
        path_tracker=mcp_tracker,
    )
    audited_hooks_mutations = AuditedMutationService(
        hooks_mutations,
        family="hooks",
        journal=mutation_audit,
        path_tracker=hooks_tracker,
    )
    audited_permissions_mutations = AuditedMutationService(
        permissions_mutations,
        family="permissions",
        journal=mutation_audit,
        path_tracker=permissions_tracker,
    )
    audited_agents_store = AuditedMutationService(
        agents_store,
        family="agents",
        methods={"create", "update"},
        journal=mutation_audit,
        path_tracker=agents_tracker,
    )
    audited_agents_mutations = AuditedMutationService(
        agents_mutations,
        family="agents",
        journal=mutation_audit,
        path_tracker=agents_tracker,
    )
    audited_agents_reconcile = AuditedMutationService(
        agents_reconcile,
        family="agents",
        methods={"reconcile"},
        journal=mutation_audit,
        path_tracker=agents_tracker,
        record_noop=False,
    )
    agents_inventory = AgentInventoryService(
        agents_store,
        resolve_agents_snapshot,
        agent_bindings,
        audited_agents_reconcile.reconcile,
    )
    audited_config_snapshots = AuditedMutationService(
        config_snapshots,
        family="config_snapshots",
        methods={"capture_snapshot"},
        journal=mutation_audit,
        path_tracker=snapshots_tracker,
        record_noop=False,
    )
    audited_scaffold = AuditedMutationService(
        scaffold_service,
        family="scaffold",
        methods={"scaffold_asset"},
        journal=mutation_audit,
        path_tracker=scaffold_tracker,
    )

    return BackendContainer(
        paths=paths,
        harness_kernel=harness_kernel,
        support_store=support_store,
        invalidation=invalidation,
        skills_source_fetcher=active_source_fetcher,
        skills_store=skills_store,
        skills_read_models=skills_read_models,
        skills_queries=skills_queries,
        skills_mutations=audited_skills_mutations,
        settings_queries=settings_queries,
        settings_mutations=audited_settings_mutations,
        slash_command_store=slash_command_store,
        slash_command_sync_state=slash_command_sync_state,
        slash_command_read_models=slash_command_read_models,
        slash_command_queries=slash_command_queries,
        slash_command_mutations=audited_slash_mutations,
        skills_marketplace_catalog=skills_catalog,
        skills_marketplace_documents=skills_documents,
        skills_marketplace_queries=skills_marketplace_queries,
        skills_marketplace_installs=audited_skills_marketplace_installs,
        cli_marketplace_catalog=cli_catalog,
        mcp_marketplace_catalog=mcp_catalog,
        mcp_store=mcp_store,
        mcp_read_models=mcp_read_models,
        mcp_queries=mcp_queries,
        mcp_mutations=audited_mcp_mutations,
        hooks_store=hooks_store,
        hooks_read_models=hooks_read_models,
        hooks_queries=hooks_queries,
        hooks_mutations=audited_hooks_mutations,
        permissions_store=permissions_store,
        permissions_read_models=permissions_read_models,
        permissions_queries=permissions_queries,
        permissions_mutations=audited_permissions_mutations,
        scaffold_service=audited_scaffold,
        agents_store=audited_agents_store,
        agents_inventory=agents_inventory,
        agents_mutations=audited_agents_mutations,
        agents_audit=agents_audit,
        agents_reconcile=audited_agents_reconcile,
        config_snapshots=audited_config_snapshots,
        mutation_audit=mutation_audit,
        app_home=app_home,
    )
