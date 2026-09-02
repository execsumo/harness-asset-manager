import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { invalidateCapabilityQueries } from "../../app/capability-registry";
import { applyAdoption, dismissAdoption, fetchAdoptionPlan } from "./api";
import type { AdoptionActionDto, AdoptionPlanDto } from "./types";

export const ADOPTION_PLAN_QUERY_KEY = ["adopt", "plan"] as const;

export function useAdoptionPlanQuery() {
  return useQuery({
    queryKey: ADOPTION_PLAN_QUERY_KEY,
    queryFn: fetchAdoptionPlan,
    staleTime: 10_000,
  });
}

export function useDismissAdoptionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: dismissAdoption,
    onSuccess: () => {
      queryClient.setQueryData<AdoptionPlanDto | undefined>(
        ADOPTION_PLAN_QUERY_KEY,
        (prev) => (prev ? { ...prev, dismissed: true } : prev),
      );
    },
  });
}

export function useApplyAdoptionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      actions,
      allowConflicts,
    }: {
      actions: AdoptionActionDto[];
      allowConflicts?: boolean;
    }) => applyAdoption(actions, allowConflicts),
    onSuccess: async () => {
      await invalidateCapabilityQueries(queryClient);
      await queryClient.invalidateQueries({ queryKey: ADOPTION_PLAN_QUERY_KEY });
    },
  });
}
