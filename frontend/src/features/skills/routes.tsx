import { lazy, Suspense } from "react";
import { Navigate, Route } from "react-router-dom";

import RouteLoadingPanel from "../../components/RouteLoadingPanel";
import SkillsWorkspacePage from "./screens/SkillsWorkspacePage";

// Keep the route behind a lazy/Suspense boundary while the module is eagerly
// available to the shell's legacy-route heading checks.
export const preloadSkillsRoute = () => Promise.resolve({ default: SkillsWorkspacePage });

const SkillsPage = lazy(preloadSkillsRoute);

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
