import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { invalidateCapabilityQueries } from "../../app/capability-registry";
import { applyBootstrap, dismissBootstrap, fetchBootstrapPlan } from "./api";
import type { BootstrapActionDto, BootstrapPlanDto } from "./types";

export const BOOTSTRAP_PLAN_QUERY_KEY = ["bootstrap", "plan"] as const;

export function useBootstrapPlanQuery() {
  return useQuery({
    queryKey: BOOTSTRAP_PLAN_QUERY_KEY,
    queryFn: fetchBootstrapPlan,
    staleTime: 10_000,
  });
}

export function useDismissBootstrapMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: dismissBootstrap,
    onSuccess: () => {
      queryClient.setQueryData<BootstrapPlanDto | undefined>(
        BOOTSTRAP_PLAN_QUERY_KEY,
        (prev) => (prev ? { ...prev, dismissed: true } : prev),
      );
    },
  });
}

export function useApplyBootstrapMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      actions,
      allowConflicts,
    }: {
      actions: BootstrapActionDto[];
      allowConflicts?: boolean;
    }) => applyBootstrap(actions, allowConflicts),
    onSuccess: async () => {
      await invalidateCapabilityQueries(queryClient);
      await queryClient.invalidateQueries({ queryKey: BOOTSTRAP_PLAN_QUERY_KEY });
    },
  });
}
