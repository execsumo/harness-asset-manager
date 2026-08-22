import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Plus, X } from "lucide-react";

import { BulkActionBar } from "../../../components/BulkActionBar";
import { ConfirmActionDialog } from "../../../components/ConfirmActionDialog";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FilterBar } from "../../../components/FilterBar";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { PageHeader } from "../../../components/PageHeader";
import { McpServerDetailSheet } from "../components/detail/McpServerDetailSheet";
import { McpNeedsReviewDetailSheet } from "../components/detail/McpNeedsReviewDetailSheet";
import {
  McpConfigChoiceDialog,
  type McpConfigChoiceOption,
} from "../components/edit/McpConfigChoiceDialog";
import { McpInstallConfigDialog } from "../components/config/McpInstallConfigDialog";
import { McpFilterMenu } from "../components/McpFilterMenu";
import { McpServerMatrixView } from "../components/McpServerMatrixView";
import type {
  McpIdentityGroupDto,
  McpInventoryEntryDto,
} from "../api/management-types";
import { useCommonCopy } from "../../../i18n";
import { useMcpCopy } from "../i18n";
import type { McpInstallConfigValues } from "../model/install-config";
import {
  filterMcpServersInUse,
  pillCounts,
  type InUsePillValue,
} from "../model/selectors";
import { useMcpEnableWorkflow } from "../model/use-mcp-enable-workflow";
import { useMcpManagementController } from "../model/use-mcp-management-controller";

const DETAIL_PARAM = "server";
const STATUS_VALUES: InUsePillValue[] = [
  "all",
  "enabled",
  "all-harnesses",
  "unbound",
  "drifted",
  "untracked",
];

function isMcpStatusFilter(value: string | null): value is InUsePillValue {
  return value !== null && STATUS_VALUES.includes(value as InUsePillValue);
}

export default function McpInUsePage() {
  const {
    status,
    inventory,
    needsReviewByServer,
    isInitialLoading,
    isNeedsReviewByServerLoading,
    pendingServerKeys,
    pendingAdoptKeys,
    pendingPerHarnessKeys,
    queryErrorMessage,
    actionErrorMessage,
    dismissActionError,
    handleSetServerHarnesses,
    handleUninstallServer,
    handleEnableInHarness,
    handleDisableInHarness,
    handleResolveConfig,
    handleAdoptConfig,
    multiSelectedNames,
    multiSelectPending,
    handleToggleMultiSelect,
    handleClearMultiSelect,
    handleMultiSelectEnableAll,
    handleMultiSelectDisableAll,
    handleMultiSelectUninstall,
  } = useMcpManagementController();

  const [searchParams, setSearchParams] = useSearchParams();
  const selectedName = searchParams.get(DETAIL_PARAM);
  const [confirmUninstallName, setConfirmUninstallName] = useState<string | null>(null);
  const [pageActionErrorMessage, setPageActionErrorMessage] = useState("");
  const [search, setSearch] = useState("");
  const [selectedUntrackedNames, setSelectedUntrackedNames] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  const [adoptingSelected, setAdoptingSelected] = useState(false);
  const [chooseConfigName, setChooseConfigName] = useState<string | null>(null);

  const copy = useMcpCopy();
  const common = useCommonCopy();

  const statusParam = searchParams.get("status");
  const statusFilter: InUsePillValue = isMcpStatusFilter(statusParam) ? statusParam : "all";
  const setStatusFilter = useCallback(
    (next: InUsePillValue) => {
      const params = new URLSearchParams(searchParams);
      if (next === "all") params.delete("status");
      else params.set("status", next);
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const {
    requestEnable,
    requestBulkEnable,
    pendingConfig: pendingEnableConfig,
    cancelConfig: cancelEnableConfig,
    submitConfig: submitEnableConfig,
    configError: enableConfigError,
  } = useMcpEnableWorkflow({
    loadErrorMessage: copy.detail.unableToLoadInstallConfig,
    bulkRequiresSingleMessage: copy.detail.installConfig.bulkRequiresSingle,
  });

  const groupMap = useMemo(
    () => new Map((needsReviewByServer?.servers ?? []).map((g) => [g.name, g])),
    [needsReviewByServer],
  );

  const entries = useMemo(
    () => filterMcpServersInUse(inventory, { search, pill: statusFilter }),
    [inventory, search, statusFilter],
  );
  const counts = useMemo(() => pillCounts(inventory), [inventory]);
  const hasData = (inventory?.entries.length ?? 0) > 0;
  const isReady = status === "ready" && Boolean(inventory);
  const isReviewView = statusFilter === "untracked";
  const filtersActive = search !== "" || statusFilter !== "all";

  const inventoryIssueMessage = inventory?.issues?.length
    ? copy.inUse.inventoryIssue(inventory.issues.length)
    : "";
  const visibleActionErrorMessage =
    actionErrorMessage || enableConfigError || pageActionErrorMessage;

  // Keep only currently visible, identical unmanaged rows selected as filters or inventory change.
  useEffect(() => {
    setSelectedUntrackedNames((current) => {
      const visibleUntracked = new Set(
        entries
          .filter((entry) => {
            if (entry.kind !== "unmanaged") return false;
            const g = groupMap.get(entry.name);
            return g ? g.identical : true;
          })
          .map((entry) => entry.name),
      );
      let changed = false;
      const next = new Set<string>();
      for (const name of current) {
        if (visibleUntracked.has(name)) next.add(name);
        else changed = true;
      }
      return changed ? next : current;
    });
  }, [entries, groupMap]);

  const toggleUntrackedSelected = useCallback((name: string) => {
    setSelectedUntrackedNames((current) => {
      const next = new Set(current);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }, []);

  const handleAdoptSelected = useCallback(async () => {
    const names = entries
      .filter((entry) => entry.kind === "unmanaged" && selectedUntrackedNames.has(entry.name))
      .map((entry) => entry.name);
    if (names.length === 0) return;
    setAdoptingSelected(true);
    try {
      for (const name of names) {
        try {
          await handleAdoptConfig(name);
        } catch {
          // Handled by controller actionErrorMessage
        }
      }
      setSelectedUntrackedNames(new Set());
    } finally {
      setAdoptingSelected(false);
    }
  }, [entries, handleAdoptConfig, selectedUntrackedNames]);

  const identicalServers = useMemo(() => {
    return entries.filter((e) => {
      if (e.kind !== "unmanaged") return false;
      const g = groupMap.get(e.name);
      return g ? g.identical : true;
    });
  }, [entries, groupMap]);
  const identicalCount = identicalServers.length;

  const onAdoptIdenticalServers = useCallback(async () => {
    for (const server of identicalServers) {
      try {
        await handleAdoptConfig(server.name);
      } catch {
        // Handled by controller
      }
    }
  }, [handleAdoptConfig, identicalServers]);

  const findEntry = useCallback(
    (name: string): McpInventoryEntryDto | null =>
      inventory?.entries.find((entry) => entry.name === name) ?? null,
    [inventory],
  );

  const findHarnessLabel = useCallback(
    (harness: string): string =>
      inventory?.columns.find((column) => column.harness === harness)?.label ?? harness,
    [inventory],
  );

  const requestConfiguredEnable = useCallback(
    (
      name: string,
      targetLabel: string,
      onProceed: (config?: McpInstallConfigValues) => void,
    ): void => {
      const entry = findEntry(name);
      if (!entry) return;
      requestEnable(entry, targetLabel, onProceed);
    },
    [findEntry, requestEnable],
  );

  const handleCardSetHarnesses = useCallback(
    (
      name: string,
      target: "enabled" | "disabled",
      config?: McpInstallConfigValues,
    ): void => {
      if (target === "disabled") {
        void handleSetServerHarnesses(name, target, config);
        return;
      }
      requestConfiguredEnable(name, copy.detail.installConfig.allHarnesses, (nextConfig) => {
        void handleSetServerHarnesses(name, target, nextConfig);
      });
    },
    [copy.detail.installConfig.allHarnesses, handleSetServerHarnesses, requestConfiguredEnable],
  );

  const handleMatrixEnableHarness = useCallback(
    (name: string, harness: string): void => {
      requestConfiguredEnable(name, findHarnessLabel(harness), (config) => {
        void handleEnableInHarness(name, harness, config);
      });
    },
    [findHarnessLabel, handleEnableInHarness, requestConfiguredEnable],
  );

  const handleBulkEnableAll = useCallback(async (): Promise<void> => {
    const selectedNames = Array.from(multiSelectedNames);
    const selectedEntries = selectedNames
      .map((name) => findEntry(name))
      .filter((entry): entry is McpInventoryEntryDto => Boolean(entry));
    await requestBulkEnable(
      selectedEntries,
      (entry) => handleCardSetHarnesses(entry.name, "enabled"),
      async () => {
        setPageActionErrorMessage("");
        await handleMultiSelectEnableAll();
      },
      setPageActionErrorMessage,
    );
  }, [
    findEntry,
    handleCardSetHarnesses,
    handleMultiSelectEnableAll,
    multiSelectedNames,
    requestBulkEnable,
  ]);

  const dismissVisibleActionError = useCallback(() => {
    dismissActionError();
    setPageActionErrorMessage("");
  }, [dismissActionError]);

  const setDetailName = useCallback(
    (name: string | null) => {
      const next = new URLSearchParams(searchParams);
      if (name) {
        next.set(DETAIL_PARAM, name);
      } else {
        next.delete(DETAIL_PARAM);
      }
      setSearchParams(next, { replace: !name });
    },
    [searchParams, setSearchParams],
  );

  const pendingForSelected = useMemo(() => {
    if (!selectedName) return new Set<string>();
    const result = new Set<string>();
    for (const key of pendingPerHarnessKeys) {
      const [name, harness] = key.split(":", 2);
      if (name === selectedName) result.add(harness);
    }
    return result;
  }, [pendingPerHarnessKeys, selectedName]);

  const isUninstallingSelected =
    selectedName !== null && pendingServerKeys.has(selectedName);
  const isServerPendingSelected =
    selectedName !== null && pendingServerKeys.has(selectedName);

  const isAdoptPending = useCallback(
    (name: string) =>
      pendingAdoptKeys.has(name) ||
      Array.from(pendingAdoptKeys).some((key) => key.startsWith(`${name}:`)),
    [pendingAdoptKeys],
  );

  const confirmUninstall = useCallback(
    (name: string) => setConfirmUninstallName(name),
    [],
  );

  const executeUninstall = useCallback(async () => {
    const target = confirmUninstallName;
    if (!target) return;
    setConfirmUninstallName(null);
    await handleUninstallServer(target);
    if (selectedName === target) {
      setDetailName(null);
    }
  }, [confirmUninstallName, handleUninstallServer, selectedName, setDetailName]);

  const clearFilters = useCallback(() => {
    setSearch("");
    setStatusFilter("all");
  }, [setStatusFilter]);

  const selectedEntry = useMemo(
    () => (selectedName ? findEntry(selectedName) : null),
    [findEntry, selectedName],
  );
  const selectedGroup = useMemo(
    () => (selectedName ? groupMap.get(selectedName) ?? null : null),
    [groupMap, selectedName],
  );
  const isSelectedUntracked = Boolean(
    selectedEntry ? selectedEntry.kind === "unmanaged" : selectedGroup,
  );

  const chooseConfigGroup = useMemo(
    () => (chooseConfigName ? groupMap.get(chooseConfigName) ?? null : null),
    [chooseConfigName, groupMap],
  );

  const selectedUntrackedCount = selectedUntrackedNames.size;

  return (
    <>
      <div className="page-chrome">
        <PageHeader
          title={copy.inUse.title}
          subtitle={isReviewView ? copy.review.subtitle(counts.untracked) : copy.inUse.subtitle}
          actions={
            <>
              {isReviewView && identicalCount > 0 ? (
                <button
                  type="button"
                  className="action-pill action-pill--md action-pill--accent"
                  onClick={() => {
                    void onAdoptIdenticalServers();
                  }}
                >
                  {copy.review.adoptIdentical(identicalCount)}
                </button>
              ) : null}
              <Link
                to="/marketplace/mcp"
                className={`action-pill action-pill--md ${!isReviewView || identicalCount === 0 ? "action-pill--accent" : ""}`}
              >
                {common.actions.browseMarketplace}
              </Link>
            </>
          }
        />
        {hasData ? (
          <FilterBar
            searchValue={search}
            onSearchChange={setSearch}
            searchPlaceholder={copy.inUse.searchPlaceholder}
            searchLabel={copy.inUse.searchLabel}
            trailing={<McpFilterMenu pill={statusFilter} counts={counts} onChange={setStatusFilter} />}
          />
        ) : null}
      </div>

      {visibleActionErrorMessage ? (
        <ErrorBanner message={visibleActionErrorMessage} onDismiss={dismissVisibleActionError} />
      ) : null}
      {inventoryIssueMessage ? <ErrorBanner message={inventoryIssueMessage} /> : null}

      {isInitialLoading ? (
        <div className="panel-state">
          <LoadingSpinner size="md" label={copy.inUse.loading} />
        </div>
      ) : status === "error" ? (
        <div className="panel-state">{queryErrorMessage || copy.inUse.unableToLoad}</div>
      ) : isReady && inventory ? (
        entries.length > 0 ? (
          <McpServerMatrixView
            entries={entries}
            columns={inventory.columns}
            pendingServerKeys={pendingServerKeys}
            pendingAdoptKeys={pendingAdoptKeys}
            pendingPerHarnessKeys={pendingPerHarnessKeys}
            checkedNames={multiSelectedNames}
            checkedUntrackedNames={selectedUntrackedNames}
            groupsByName={groupMap}
            onOpenDetail={setDetailName}
            onToggleChecked={handleToggleMultiSelect}
            onToggleCheckedUntracked={toggleUntrackedSelected}
            onEnableHarness={handleMatrixEnableHarness}
            onDisableHarness={(name, harness) => {
              void handleDisableInHarness(name, harness);
            }}
            onAdopt={(name) => void handleAdoptConfig(name)}
            onChooseConfigToAdopt={setChooseConfigName}
          />
        ) : hasData ? (
          <div className="empty-panel">
            <h3 className="empty-panel__title">
              {isReviewView ? "No MCP configs need review" : common.status.noMatches}
            </h3>
            <p className="empty-panel__body">
              {isReviewView
                ? (search
                    ? copy.review.noMatchesBody
                    : "Your harness configs only reference MCP servers that harness-asset-manager already tracks.")
                : copy.inUse.noMatchesBody}
            </p>
            <div className="empty-panel__actions">
              <button
                type="button"
                className="action-pill action-pill--md"
                onClick={clearFilters}
                disabled={!filtersActive}
              >
                {common.actions.clearFilters}
              </button>
            </div>
          </div>
        ) : (
          <div className="empty-panel">
            <h3 className="empty-panel__title">
              {isReviewView ? "No MCP configs need review" : copy.inUse.emptyTitle}
            </h3>
            <p className="empty-panel__body">
              {isReviewView
                ? "Your harness configs only reference MCP servers that harness-asset-manager already tracks."
                : copy.inUse.emptyBody}
            </p>
            <div className="empty-panel__actions">
              <Link
                to="/marketplace/mcp"
                className="action-pill action-pill--md action-pill--accent"
              >
                {common.actions.openMarketplace}
              </Link>
            </div>
          </div>
        )
      ) : null}

      {selectedName && isSelectedUntracked ? (
        <McpNeedsReviewDetailSheet
          name={selectedName}
          group={selectedGroup}
          isLoading={isNeedsReviewByServerLoading && !selectedGroup}
          errorMessage=""
          pending={isAdoptPending(selectedName)}
          onClose={() => setDetailName(null)}
          onAdopt={() => {
            if (selectedName) {
              void handleAdoptConfig(selectedName).then(() => setDetailName(null));
            }
          }}
          onChooseConfigToAdopt={() => {
            if (selectedName) {
              setDetailName(null);
              setChooseConfigName(selectedName);
            }
          }}
        />
      ) : selectedName && inventory ? (
        <McpServerDetailSheet
          name={selectedName}
          columns={inventory.columns}
          pendingPerHarness={pendingForSelected}
          isServerPending={isServerPendingSelected}
          isUninstalling={isUninstallingSelected}
          onClose={() => setDetailName(null)}
          onEnableHarness={(harness, config) => {
            if (selectedName) void handleEnableInHarness(selectedName, harness, config);
          }}
          onDisableHarness={(harness) => {
            if (selectedName) void handleDisableInHarness(selectedName, harness);
          }}
          onResolveConfig={(args) => {
            if (!selectedName) return Promise.resolve();
            return handleResolveConfig(selectedName, args);
          }}
          onUninstall={() => {
            if (selectedName) confirmUninstall(selectedName);
          }}
        />
      ) : null}

      {chooseConfigGroup ? (
        <McpConfigChoiceDialog
          open
          mode="adopt"
          serverName={chooseConfigGroup.name}
          options={optionsForGroup(chooseConfigGroup)}
          pending={isAdoptPending(chooseConfigGroup.name)}
          onClose={() => setChooseConfigName(null)}
          onConfirm={async (option) => {
            await handleAdoptConfig(chooseConfigGroup.name, {
              observedHarness: option.observedHarness,
              harnesses: chooseConfigGroup.sightings.map((sighting) => sighting.harness),
            });
            setChooseConfigName(null);
          }}
        />
      ) : null}

      <BulkActionBar
        selectedCount={multiSelectedNames.size}
        pending={multiSelectPending}
        onClear={handleClearMultiSelect}
        onEnableAll={handleBulkEnableAll}
        onDisableAll={handleMultiSelectDisableAll}
        onDelete={handleMultiSelectUninstall}
        destructive={{
          actionLabel: copy.inUse.uninstall.action,
          confirmTitle: copy.inUse.uninstall.bulkTitle(multiSelectedNames.size),
          confirmDescription: copy.inUse.uninstall.description,
        }}
      />

      {selectedUntrackedCount > 0 ? (
        <div className="bulk-dock">
          <div className="bulk-dock__fade" />
          <div
            className="bulk-bar"
            data-state="open"
            role="toolbar"
            aria-label={common.bulk.ariaLabel}
          >
            <div className="bulk-bar__group">
              <span className="bulk-bar__count">{common.bulk.selected(selectedUntrackedCount)}</span>
              <button
                type="button"
                className="bulk-bar__clear"
                onClick={() => setSelectedUntrackedNames(new Set())}
                disabled={adoptingSelected}
                aria-label={common.actions.clearSelection}
              >
                <X size={14} />
              </button>
            </div>

            <span className="bulk-bar__divider" aria-hidden="true" />

            <button
              type="button"
              className="bulk-bar__action"
              onClick={() => void handleAdoptSelected()}
              disabled={adoptingSelected}
            >
              {adoptingSelected ? (
                <LoadingSpinner size="sm" label={copy.inUse.adoptingSelected || "Adopting selected servers..."} />
              ) : (
                <Plus size={15} />
              )}
              {copy.inUse.adoptSelected || "Adopt selected"}
            </button>
          </div>
        </div>
      ) : null}

      <ConfirmActionDialog
        open={confirmUninstallName !== null}
        title={copy.inUse.uninstall.title(uninstallDisplayName(inventory, confirmUninstallName, copy.inUse.uninstall.fallbackName))}
        description={copy.inUse.uninstall.singleDescription}
        confirmLabel={copy.inUse.uninstall.action}
        pendingLabel={copy.inUse.uninstall.pending}
        isPending={false}
        onOpenChange={(open) => {
          if (!open) setConfirmUninstallName(null);
        }}
        onConfirm={executeUninstall}
      />
      <McpInstallConfigDialog
        pending={pendingEnableConfig}
        installing={false}
        onClose={cancelEnableConfig}
        onSubmit={submitEnableConfig}
      />
    </>
  );
}

function optionsForGroup(group: McpIdentityGroupDto): McpConfigChoiceOption[] {
  return group.sightings.map((sighting) => ({
    id: `harness:${sighting.harness}`,
    sourceKind: "harness",
    observedHarness: sighting.harness,
    label: sighting.label,
    logoKey: sighting.logoKey,
    configPath: sighting.configPath,
    payloadPreview: sighting.payloadPreview,
    spec: sighting.spec,
    env: sighting.env ?? [],
    recommended: sighting.recommended,
  }));
}

function uninstallDisplayName(
  inventory: { entries: { name: string; displayName: string }[] } | null,
  name: string | null,
  fallbackName = "this server",
): string {
  if (!inventory || !name) return fallbackName;
  const entry = inventory.entries.find((e) => e.name === name);
  return entry?.displayName ?? name;
}
