// ConfigsPage is deliberately not re-exported: the sidebar imports this module
// for configsRoutes/useConfigsListQuery, and a static re-export here would pull
// the whole screen into the main bundle and defeat its lazy route in App.tsx.
export { configsRoutes } from './routes';
export { useConfigsListQuery } from './api/queries';
