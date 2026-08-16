export {
  useDeleteSkillMutation,
  useManageAllSkillsMutation,
  useManageSkillMutation,
  useSetSkillHarnessesMutation,
  useSkillDetailQuery,
  useSkillsListQuery,
  useSkillSourceStatusQuery,
  useToggleSkillMutation,
  useUnmanageSkillMutation,
  useUpdateSkillMutation,
} from "./api/queries";
export { invalidateSkillsQueries } from "./api/invalidation";
export { skillsKeys } from "./api/keys";
export type {
  HarnessCell,
  HarnessColumn,
  SkillListRow,
  SkillsWorkspaceData,
} from "./model/types";

export const skillsRoutes = {
  index: "/skills",
  // Keep the legacy values for overview/deep-link consumers; both routes
  // redirect through the shared fragment below.
  inUse: "/skills/use",
  needsReview: "/skills/review",
  needsReviewFilter: "/skills?status=untracked",
  marketplace: "/marketplace/skills",
} as const;
