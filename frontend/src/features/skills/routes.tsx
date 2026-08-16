import { lazy, Suspense } from "react";
import { Navigate, Route } from "react-router-dom";

import RouteLoadingPanel from "../../components/RouteLoadingPanel";

const SkillsPage = lazy(() => import("./screens/SkillsWorkspacePage"));

/** The canonical Skills route declarations, shared by App and routing tests. */
export function getSkillsRouteElements() {
  return [
    <Route
      key="skills"
      path="skills"
      element={
        <Suspense fallback={<RouteLoadingPanel label="Loading skills..." />}>
          <SkillsPage />
        </Suspense>
      }
    />,
    <Route key="skills-use" path="skills/use" element={<Navigate to="/skills" replace />} />,
    <Route
      key="skills-review"
      path="skills/review"
      element={<Navigate to="/skills?status=untracked" replace />}
    />,
    <Route
      key="skills-managed"
      path="skills/managed"
      element={<Navigate to="/skills" replace />}
    />,
    <Route
      key="skills-unmanaged"
      path="skills/unmanaged"
      element={<Navigate to="/skills?status=untracked" replace />}
    />,
  ];
}
