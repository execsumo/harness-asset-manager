import { lazy, Suspense } from "react";
import { Navigate, Route } from "react-router-dom";

import RouteLoadingPanel from "../../components/RouteLoadingPanel";

const HooksPage = lazy(() => import("./screens/HooksInUsePage"));

/** The canonical Hooks route declarations, shared by App and routing tests. */
export function getHooksRouteElements() {
  return [
    <Route
      key="hooks"
      path="hooks"
      element={
        <Suspense fallback={<RouteLoadingPanel label="Loading hooks..." />}>
          <HooksPage />
        </Suspense>
      }
    />,
    <Route key="hooks-use" path="hooks/use" element={<Navigate to="/hooks" replace />} />,
    <Route
      key="hooks-review"
      path="hooks/review"
      element={<Navigate to="/hooks?status=untracked" replace />}
    />,
    <Route
      key="hooks-unmanaged"
      path="hooks/unmanaged"
      element={<Navigate to="/hooks?status=untracked" replace />}
    />,
  ];
}
