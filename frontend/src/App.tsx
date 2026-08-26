import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import RouteLoadingPanel from "./components/RouteLoadingPanel";
import { Shell } from "./components/Shell";
import { ToastProvider } from "./components/Toast";
import { UiTooltipProvider } from "./components/ui/UiTooltipProvider";
import { invalidateCapabilityQueries } from "./app/capability-registry";
import { SkillsWorkspaceSessionProvider } from "./features/skills/model/session";
import { getSkillsRouteElements } from "./features/skills/routes";
import { getHooksRouteElements } from "./features/hooks/routes";
import { getMcpRouteElements } from "./features/mcp/routes";
import { getAgentsRouteElements } from "./features/agents/routes";
import { getSlashCommandsRouteElements } from "./features/slash-commands/routes";
import { useCommonCopy } from "./i18n";

import { HomeDirProvider } from "./lib/paths";
import { ThemeProvider } from "./lib/theme";

const MarketplaceLayout = lazy(() => import("./features/marketplace/components/MarketplaceLayout"));
const OverviewPage = lazy(() => import("./features/overview/screens/OverviewPage"));
const SettingsPage = lazy(() => import("./features/settings/screens/SettingsPage"));
const PermissionsPage = lazy(() => import("./features/permissions/screens/PermissionsPage"));
const ConfigsPage = lazy(() => import("./features/configs/screens/ConfigsPage"));

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
          {getAgentsRouteElements()}

          {getSkillsRouteElements()}

          {getMcpRouteElements()}

          {getHooksRouteElements()}

          <Route
            path="configs"
            element={
              <Suspense fallback={<RouteLoadingPanel label="Loading configs..." />}>
                <ConfigsPage />
              </Suspense>
            }
          />

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

          {getSlashCommandsRouteElements()}

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
