import { optimisticTags } from "../../../components/tags/optimistic-tags";
import { useRef } from "react";
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { ScopedReconciliationTracker } from "../../../lib/async/scoped-reconciliation";
import { queryPolicy, settleInvalidate } from "../../../lib/query";
import { invalidateAgentsQueries } from "../../agents/public";
import {
  attachAgents,
  createSkill,
  deleteSkill,
  disableSkill,
  enableSkill,
  fetchSkillDetail,
  fetchSkillSourceStatus,
  fetchSkillsPage,
  manageAllSkills,
  manageSkill,
  setSkillHarnesses,
  setSkillTags,
  unmanageSkill,
  updateSkill,
  updateSkillDocument,
} from "./client";
import {
  getDetailCellState,
  getListCellState,
  patchSkillDetailToggle,
  patchSkillsListToggle,
  removeSkillFromList,
} from "./cache-patches";
import { invalidateSkillsQueries } from "./invalidation";
import { SKILLS_GC_TIME_MS, SKILLS_LIST_REFETCH_INTERVAL_MS, SKILLS_STALE_TIME_MS, skillsKeys } from "./keys";
import { mapSkillDetail, mapSkillsPage } from "./mappers";
import type { HarnessCellState } from "../model/types";
import type {
  AttachAgentsRequestDto,
  CreateSkillRequest,
  CreateSkillResponseDto,
  SetSkillHarnessesResultDto,
  SkillDetailDto,
  SkillsPageDto,
} from "./types";

export { invalidateSkillsQueries } from "./invalidation";
export { skillsKeys } from "./keys";

// Scoped on purpose (PR #154): a single-skill mutation refreshes the list plus that skill's
// own detail and source status, not every cached skill.
const settleSkillScope = (queryClient: QueryClient, skillRef: string) =>
  settleInvalidate(queryClient, skillsKeys.list(), skillsKeys.detail(skillRef), skillsKeys.sourceStatus(skillRef))();

// Agent payloads list their skills, so a skill that goes away or changes identity must also
// refresh agents.
const settleSkillsAndAgents = (queryClient: QueryClient) =>
  settleInvalidate(queryClient, invalidateSkillsQueries, invalidateAgentsQueries)();

export function useSkillsListQuery(includeArchived = false) {
  return useQuery({
    queryKey: includeArchived ? [...skillsKeys.list(), "with-archived"] : skillsKeys.list(),
    queryFn: () => fetchSkillsPage(includeArchived),
    select: mapSkillsPage,
    ...queryPolicy(SKILLS_STALE_TIME_MS, SKILLS_GC_TIME_MS),
    refetchInterval: SKILLS_LIST_REFETCH_INTERVAL_MS,
    refetchOnWindowFocus: true,
  });
}

export function useSkillDetailQuery(skillRef: string | null) {
  return useQuery({
    queryKey: skillsKeys.detail(skillRef ?? "__none__"),
    queryFn: () => fetchSkillDetail(skillRef!),
    select: mapSkillDetail,
    enabled: Boolean(skillRef),
    ...queryPolicy(SKILLS_STALE_TIME_MS, SKILLS_GC_TIME_MS),
  });
}

export function useSkillSourceStatusQuery(skillRef: string | null) {
  return useQuery({
    queryKey: skillsKeys.sourceStatus(skillRef ?? "__none__"),
    queryFn: () => fetchSkillSourceStatus(skillRef!),
    enabled: Boolean(skillRef),
    ...queryPolicy(SKILLS_STALE_TIME_MS, SKILLS_GC_TIME_MS),
  });
}

export function useToggleSkillMutation() {
  const queryClient = useQueryClient();
  const reconciliationRef = useRef<ScopedReconciliationTracker<string> | null>(null);

  if (reconciliationRef.current === null) {
    reconciliationRef.current = new ScopedReconciliationTracker<string>();
  }

  return useMutation({
    mutationFn: async ({
      skillRef,
      harness,
      nextState,
    }: {
      skillRef: string;
      harness: string;
      nextState: HarnessCellState;
    }) => {
      if (nextState === "enabled") {
        return enableSkill(skillRef, harness);
      }
      return disableSkill(skillRef, harness);
    },
    onMutate: async ({ skillRef, harness, nextState }) => {
      reconciliationRef.current?.begin(skillRef);

      await Promise.all([
        queryClient.cancelQueries({ queryKey: skillsKeys.list() }),
        queryClient.cancelQueries({ queryKey: skillsKeys.detail(skillRef) }),
      ]);

      const previousList = queryClient.getQueryData<SkillsPageDto>([...skillsKeys.list(), "with-archived"])
        ?? queryClient.getQueryData<SkillsPageDto>(skillsKeys.list());
      const previousDetail = queryClient.getQueryData<SkillDetailDto>(skillsKeys.detail(skillRef));
      const previousListCellState = getListCellState(previousList, skillRef, harness);
      const previousDetailCellState = getDetailCellState(previousDetail, harness);

      if (previousList) {
        queryClient.setQueriesData<SkillsPageDto>(
          { queryKey: skillsKeys.list() },
          (current) => current ? patchSkillsListToggle(current, skillRef, harness, nextState) : current,
        );
      }
      if (previousDetail) {
        queryClient.setQueryData<SkillDetailDto>(
          skillsKeys.detail(skillRef),
          patchSkillDetailToggle(previousDetail, harness, nextState),
        );
      }

      return {
        skillRef,
        harness,
        previousListCellState,
        previousDetailCellState,
      };
    },
    onError: (_error, _variables, context) => {
      if (!context) {
        return;
      }

      if (context.previousListCellState !== null) {
        const previousListCellState = context.previousListCellState;
        queryClient.setQueriesData<SkillsPageDto>(
          { queryKey: skillsKeys.list() },
          (current) => current ? patchSkillsListToggle(
            current,
            context.skillRef,
            context.harness,
            previousListCellState,
          ) : current,
        );
      }
      if (context.previousDetailCellState !== null) {
        const previousDetailCellState = context.previousDetailCellState;
        queryClient.setQueryData<SkillDetailDto>(
          skillsKeys.detail(context.skillRef),
          (current) => current ? patchSkillDetailToggle(
            current,
            context.harness,
            previousDetailCellState,
          ) : current,
        );
      }
    },
    onSettled: async (_data, _error, variables) => {
      const decision = reconciliationRef.current?.finish(variables.skillRef) ?? {
        invalidateAll: true,
        invalidateScope: true,
      };
      await settleInvalidate(
        queryClient,
        ...(decision.invalidateScope ? [skillsKeys.detail(variables.skillRef), skillsKeys.sourceStatus(variables.skillRef)] : []),
        ...(decision.invalidateAll ? [skillsKeys.list()] : []),
      )();
    },
  });
}

export function useSetSkillHarnessesMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      skillRef,
      target,
    }: {
      skillRef: string;
      target: "enabled" | "disabled";
    }): Promise<SetSkillHarnessesResultDto> => {
      return setSkillHarnesses(skillRef, target);
    },
    onMutate: async ({ skillRef, target }) => {
      await Promise.all([
        queryClient.cancelQueries({ queryKey: skillsKeys.list() }),
        queryClient.cancelQueries({ queryKey: skillsKeys.detail(skillRef) }),
      ]);

      const previousList = queryClient.getQueryData<SkillsPageDto>(skillsKeys.list());
      const previousDetail = queryClient.getQueryData<SkillDetailDto>(skillsKeys.detail(skillRef));

      const row = previousList?.rows.find((candidate) => candidate.skillRef === skillRef);
      const flippingHarnesses = row
        ? row.cells
            .filter((cell) => cell.interactive && cell.state !== target)
            .map((cell) => cell.harness)
        : [];

      if (previousList && flippingHarnesses.length > 0) {
        let patched = previousList;
        for (const harness of flippingHarnesses) {
          patched = patchSkillsListToggle(patched, skillRef, harness, target);
        }
        queryClient.setQueryData<SkillsPageDto>(skillsKeys.list(), patched);
      }

      if (previousDetail && flippingHarnesses.length > 0) {
        let patched = previousDetail;
        for (const harness of flippingHarnesses) {
          patched = patchSkillDetailToggle(patched, harness, target);
        }
        queryClient.setQueryData<SkillDetailDto>(skillsKeys.detail(skillRef), patched);
      }

      return { skillRef, previousList, previousDetail };
    },
    onError: (_error, _variables, context) => {
      if (!context) return;
      if (context.previousList !== undefined) {
        queryClient.setQueryData<SkillsPageDto>(skillsKeys.list(), context.previousList);
      }
      if (context.previousDetail !== undefined) {
        queryClient.setQueryData<SkillDetailDto>(skillsKeys.detail(context.skillRef), context.previousDetail);
      }
    },
    onSettled: (_data, _error, variables) => settleSkillScope(queryClient, variables.skillRef),
  });
}

export function useCreateSkillMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: CreateSkillRequest): Promise<CreateSkillResponseDto> => createSkill(request),
    // A new package changes the list and nothing else yet, but it can land bound to
    // harnesses, so the whole skills scope is refreshed rather than the list alone.
    onSettled: settleInvalidate(queryClient, invalidateSkillsQueries),
  });
}

export function useManageSkillMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ skillRef }: { skillRef: string }) => manageSkill(skillRef),
    onSettled: (_data, _error, variables) => settleSkillScope(queryClient, variables.skillRef),
  });
}

export function useManageAllSkillsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: manageAllSkills,
    onSettled: settleInvalidate(queryClient, invalidateSkillsQueries),
  });
}

export function useUpdateSkillMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ skillRef }: { skillRef: string }) => updateSkill(skillRef),
    onSettled: (_data, _error, variables) => settleSkillScope(queryClient, variables.skillRef),
  });
}

export function useUnmanageSkillMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ skillRef }: { skillRef: string }) => unmanageSkill(skillRef),
    onSuccess: (_data, variables) => {
      queryClient.removeQueries({ queryKey: skillsKeys.detail(variables.skillRef), exact: true });
      queryClient.removeQueries({ queryKey: skillsKeys.sourceStatus(variables.skillRef), exact: true });
    },
    onSettled: () => settleSkillsAndAgents(queryClient),
  });
}

export function useDeleteSkillMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ skillRef }: { skillRef: string }) => deleteSkill(skillRef),
    onMutate: async ({ skillRef }) => {
      await Promise.all([
        queryClient.cancelQueries({ queryKey: skillsKeys.list() }),
        queryClient.cancelQueries({ queryKey: skillsKeys.detail(skillRef) }),
        queryClient.cancelQueries({ queryKey: skillsKeys.sourceStatus(skillRef) }),
      ]);

      const previousList = queryClient.getQueryData<SkillsPageDto>(skillsKeys.list());
      const previousDetail = queryClient.getQueryData(skillsKeys.detail(skillRef));

      if (previousList) {
        queryClient.setQueryData<SkillsPageDto>(skillsKeys.list(), removeSkillFromList(previousList, skillRef));
      }
      queryClient.removeQueries({ queryKey: skillsKeys.detail(skillRef), exact: true });
      queryClient.removeQueries({ queryKey: skillsKeys.sourceStatus(skillRef), exact: true });

      return { previousList, previousDetail, skillRef };
    },
    onError: (_error, _variables, context) => {
      if (context?.previousList) {
        queryClient.setQueryData(skillsKeys.list(), context.previousList);
      }
      if (context?.previousDetail) {
        queryClient.setQueryData(skillsKeys.detail(context.skillRef), context.previousDetail);
      }
    },
    onSuccess: (_data, variables) => {
      queryClient.removeQueries({ queryKey: skillsKeys.detail(variables.skillRef), exact: true });
      queryClient.removeQueries({ queryKey: skillsKeys.sourceStatus(variables.skillRef), exact: true });
    },
    onSettled: () => settleSkillsAndAgents(queryClient),
  });
}

export function useUpdateSkillDocumentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ skillRef, body }: { skillRef: string; body: Parameters<typeof updateSkillDocument>[1] }) =>
      updateSkillDocument(skillRef, body),
    onSettled: (_data, _error, variables) => settleSkillScope(queryClient, variables.skillRef),
  });
}

export function useSetSkillTagsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: [...skillsKeys.all, "tags"],
    mutationFn: ({ skillRef, tags }: { skillRef: string; tags: string[] }) =>
      setSkillTags(skillRef, tags),
    onMutate: ({ skillRef, tags }) => optimisticTags(queryClient, {
      prefix: skillsKeys.all, collectionKey: "list", collections: ["rows"], identity: "skillRef", detail: skillsKeys.detail(skillRef),
    }, skillRef, tags),
    onError: (_error, _variables, rollback) => rollback?.(),
    onSettled: () => {
      if (queryClient.isMutating({ mutationKey: [...skillsKeys.all, "tags"] }) === 1) {
        return queryClient.invalidateQueries({ queryKey: skillsKeys.all });
      }
    },
  });
}


export function useAttachAgentsMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (req: AttachAgentsRequestDto) => attachAgents(req),
    // A dry run changes nothing, so it needs no refetch.
    onSettled: (_res, _error, req) => (req.dryRun ? undefined : settleSkillsAndAgents(client)),
  });
}
