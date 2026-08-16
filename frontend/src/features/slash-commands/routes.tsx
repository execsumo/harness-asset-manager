import { lazy, Suspense } from "react";
import { Navigate, Route } from "react-router-dom";

import RouteLoadingPanel from "../../components/RouteLoadingPanel";

const SlashCommandsPage = lazy(() => import("./screens/SlashCommandsPage"));

/** The canonical Slash Commands route declarations, shared by App and routing tests. */
export function getSlashCommandsRouteElements() {
  return [
    <Route
      key="slash-commands"
      path="slash-commands"
      element={
        <Suspense fallback={<RouteLoadingPanel label="Loading slash commands..." />}>
          <SlashCommandsPage />
        </Suspense>
      }
    />,
    <Route key="slash-commands-use" path="slash-commands/use" element={<Navigate to="/slash-commands" replace />} />,
    <Route
      key="slash-commands-review"
      path="slash-commands/review"
      element={<Navigate to="/slash-commands?status=untracked" replace />}
    />,
  ];
}
