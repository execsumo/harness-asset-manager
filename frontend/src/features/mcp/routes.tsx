import { lazy, Suspense } from "react";
import { Navigate, Route } from "react-router-dom";

import RouteLoadingPanel from "../../components/RouteLoadingPanel";

const McpPage = lazy(() => import("./screens/McpInUsePage"));

/** The canonical MCP route declarations, shared by App and routing tests. */
export function getMcpRouteElements() {
  return [
    <Route
      key="mcp"
      path="mcp"
      element={
        <Suspense fallback={<RouteLoadingPanel label="Loading MCP..." />}>
          <McpPage />
        </Suspense>
      }
    />,
    <Route key="mcp-use" path="mcp/use" element={<Navigate to="/mcp" replace />} />,
    <Route
      key="mcp-review"
      path="mcp/review"
      element={<Navigate to="/mcp?status=untracked" replace />}
    />,
    <Route key="mcp-managed" path="mcp/managed" element={<Navigate to="/mcp" replace />} />,
    <Route
      key="mcp-unmanaged"
      path="mcp/unmanaged"
      element={<Navigate to="/mcp?status=untracked" replace />}
    />,
  ];
}
