export {
  invalidateSlashCommandQueries,
  useCreateSlashCommandMutation,
  useDeleteSlashCommandMutation,
  useImportSlashCommandMutation,
  useResolveSlashCommandReviewMutation,
  useSlashCommandsQuery,
  useSyncSlashCommandMutation,
  useUpdateSlashCommandMutation,
} from "./api/queries";
export type {
  SlashCommandDto,
  SlashCommandListDto,
  SlashCommandReviewDto,
  SlashCommandResolveRequest,
  SlashSyncEntryDto,
  SlashTargetDto,
  SlashTargetId,
} from "./api/types";

export const slashCommandRoutes = {
  index: "/slash-commands",
  home: "/slash-commands/use",
  // Legacy consumer links remain valid and are redirected by routes.tsx.
  inUse: "/slash-commands/use",
  needsReview: "/slash-commands/review",
  untracked: "/slash-commands?status=untracked",
} as const;
