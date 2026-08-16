import { lazy, Suspense } from "react";
import { Navigate, Route } from "react-router-dom";

import RouteLoadingPanel from "../../components/RouteLoadingPanel";

const AgentsPage = lazy(() => import("./screens/AgentsInUsePage"));

/** The canonical Agents route declarations, shared by App and routing tests. */
export function getAgentsRouteElements() {
  return [
    <Route
      key="agents"
      path="agents"
      element={
        <Suspense fallback={<RouteLoadingPanel label="Loading agents..." />}>
          <AgentsPage />
        </Suspense>
      }
    />,
    <Route key="agents-use" path="agents/use" element={<Navigate to="/agents" replace />} />,
    <Route
      key="agents-review"
      path="agents/review"
      element={<Navigate to="/agents?status=untracked" replace />}
    />,
  ];
}
