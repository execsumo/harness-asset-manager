export {
  invalidateSettingsQueries,
  settingsKeys,
  useDisplayPreferences,
  useHarnessSupportMutation,
  useSettingsQuery,
} from "./queries";

export const settingsRoutes = {
  settings: "/settings",
} as const;
