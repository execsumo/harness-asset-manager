import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import RouteLoadingPanel from "./components/RouteLoadingPanel";
import { Shell } from "./components/Shell";
import { ToastProvider } from "./components/Toast";
import { UiTooltipProvider } from "./components/ui/UiTooltipProvider";
import { invalidateCapabilityQueries } from "./app/capability-registry";
import { SkillsWorkspaceSessionProvider } from "./features/skills/model/session";
import { getSkillsRouteElements, preloadSkillsRoute } from "./features/skills/routes";
import { getHooksRouteElements } from "./features/hooks/routes";
import { useCommonCopy } from "./i18n";

import { HomeDirProvider } from "./lib/paths";
import { ThemeProvider } from "./lib/theme";

// Keep the legacy route heading responsive while the shared route fragment
// retains its Suspense boundary and lazy declaration.
void preloadSkillsRoute();

const MarketplaceLayout = lazy(() => import("./features/marketplace/components/MarketplaceLayout"));
const OverviewPage = lazy(() => import("./features/overview/screens/OverviewPage"));
const SettingsPage = lazy(() => import("./features/settings/screens/SettingsPage"));
const SlashCommandsPage = lazy(() => import("./features/slash-commands/screens/SlashCommandsPage"));
const SlashCommandsReviewPage = lazy(() => import("./features/slash-commands/screens/SlashCommandsReviewPage"));
const McpNeedsReviewPage = lazy(() => import("./features/mcp/screens/McpNeedsReviewPage"));
const McpInUsePage = lazy(() => import("./features/mcp/screens/McpInUsePage"));
const AgentsInUsePage = lazy(() => import("./features/agents/screens/AgentsInUsePage"));
const AgentsNeedsReviewPage = lazy(() => import("./features/agents/screens/AgentsNeedsReviewPage"));
const PermissionsPage = lazy(() => import("./features/permissions/screens/PermissionsPage"));
const ActivityPage = lazy(() => import("./features/activity/screens/ActivityPage"));

export function App() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <UiTooltipProvider>
            <HomeDirProvider>
              <AppContent />
            </HomeDirProvider>
          </UiTooltipProvider>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

function AppContent() {
  const queryClient = useQueryClient();
  const [refreshPending, setRefreshPending] = useState(false);
  const common = useCommonCopy();

  async function handleRefreshData() {
    setRefreshPending(true);
    try {
      await invalidateCapabilityQueries(queryClient);
    } finally {
      setRefreshPending(false);
    }
  }

  return (
    <SkillsWorkspaceSessionProvider>
      <Shell onRefresh={handleRefreshData} refreshPending={refreshPending}>
        <Routes>
          <Route index element={<Navigate to="/overview" replace />} />

          <Route
            path="overview"
            element={
              <Suspense fallback={<RouteLoadingPanel label={common.loading.overview} />}>
                <OverviewPage />
              </Suspense>
            }
          />
          <Route path="agents" element={<Navigate to="/agents/use" replace />} />
          <Route
            path="agents/use"
            element={
              <Suspense fallback={<RouteLoadingPanel label="Loading agents..." />}>
                <AgentsInUsePage />
              </Suspense>
            }
          />
          <Route
            path="agents/review"
            element={
              <Suspense fallback={<RouteLoadingPanel label="Loading agents..." />}>
                <AgentsNeedsReviewPage />
              </Suspense>
            }
          />

          {getSkillsRouteElements()}

          <Route path="mcp" element={<Navigate to="/mcp/use" replace />} />
          <Route
            path="mcp/use"
            element={
              <Suspense fallback={<RouteLoadingPanel label={common.loading.mcp} />}>
                <McpInUsePage />
              </Suspense>
            }
          />
          <Route
            path="mcp/review"
            element={
              <Suspense fallback={<RouteLoadingPanel label={common.loading.mcp} />}>
                <McpNeedsReviewPage />
              </Suspense>
            }
          />
          <Route path="mcp/managed" element={<Navigate to="/mcp/use" replace />} />
          <Route path="mcp/unmanaged" element={<Navigate to="/mcp/review" replace />} />

          {getHooksRouteElements()}

          <Route
            path="permissions"
            element={
              <Suspense fallback={<RouteLoadingPanel label="Loading permissions..." />}>
                <PermissionsPage />
              </Suspense>
            }
          />
          {/* Legacy split routes now resolve to the unified inventory. */}
          <Route path="permissions/use" element={<Navigate to="/permissions" replace />} />
          <Route path="permissions/review" element={<Navigate to="/permissions" replace />} />

          <Route
            path="marketplace"
            element={
              <Suspense fallback={<RouteLoadingPanel label={common.loading.marketplace} />}>
                <MarketplaceLayout />
              </Suspense>
            }
          >
            <Route index element={<Navigate to="skills" replace />} />
            {/* Child routes exist only so /marketplace/skills, /marketplace/mcp,
                and /marketplace/clis
                are valid URLs and NavLink active matching works.
                MarketplaceLayout renders the panes itself — no Outlet. */}
            <Route path="skills" element={null} />
            <Route path="mcp" element={null} />
            <Route path="clis" element={null} />
          </Route>

          <Route path="slash-commands" element={<Navigate to="/slash-commands/use" replace />} />
          <Route
            path="slash-commands/use"
            element={
              <Suspense fallback={<RouteLoadingPanel label={common.loading.slashCommands} />}>
                <SlashCommandsPage />
              </Suspense>
            }
          />
          <Route
            path="slash-commands/review"
            element={
              <Suspense fallback={<RouteLoadingPanel label={common.loading.slashCommands} />}>
                <SlashCommandsReviewPage />
              </Suspense>
            }
          />

          <Route
            path="activity"
            element={
              <Suspense fallback={<RouteLoadingPanel label={common.loading.activity} />}>
                <ActivityPage />
              </Suspense>
            }
          />

          <Route
            path="settings"
            element={
              <Suspense fallback={<RouteLoadingPanel label={common.loading.settings} />}>
                <SettingsPage />
              </Suspense>
            }
          />

          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
      </Shell>
    </SkillsWorkspaceSessionProvider>
  );
}
