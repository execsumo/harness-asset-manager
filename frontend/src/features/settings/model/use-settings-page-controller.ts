import { useState } from "react";

import { usePendingRegistry } from "../../../lib/async/pending-registry";
import {
  useAutoAdoptMutation,
  useAutoAdoptHarnessesMutation,
  useHarnessSupportMutation,
  useSettingsQuery,
} from "../queries";
import { settingsSupportActionKey } from "./pending";

interface SettingsPageControllerCopy {
  unableToUpdateHarnessSupport: string;
}

const defaultCopy: SettingsPageControllerCopy = {
  unableToUpdateHarnessSupport: "Unable to update harness support.",
};

export function useSettingsPageController(copy: SettingsPageControllerCopy = defaultCopy) {
  const [errorMessage, setErrorMessage] = useState("");
  const settingsQuery = useSettingsQuery();
  const supportMutation = useHarnessSupportMutation();
  const autoAdoptMutation = useAutoAdoptMutation();
  const autoAdoptHarnessesMutation = useAutoAdoptHarnessesMutation();
  const pendingRegistry = usePendingRegistry<string>();
  const data = settingsQuery.data ?? null;

  async function handleSupportToggle(harness: string, nextEnabled: boolean) {
    setErrorMessage("");
    try {
      await pendingRegistry.run(
        settingsSupportActionKey(harness),
        () => supportMutation.mutateAsync({ harness, enabled: nextEnabled }),
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : copy.unableToUpdateHarnessSupport);
    }
  }


  async function handleAutoAdoptHarnessToggle(family: string, harness: string, enabled: boolean) {
    setErrorMessage("");
    const currentHarnesses = data?.autoAdoptHarnesses?.[family] ?? [];
    const nextHarnesses = enabled
      ? Array.from(new Set([...currentHarnesses, harness]))
      : currentHarnesses.filter((item) => item !== harness);
    try {
      await pendingRegistry.run(
        `auto-adopt-defaults-${family}`,
        () => autoAdoptHarnessesMutation.mutateAsync({ family, harnesses: nextHarnesses }),
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to update auto-adopt defaults.");
    }
  }

  async function handleEnableAllAutoAdopt() {
    setErrorMessage("");
    const families = ["agents", "skills", "slash_commands", "mcp", "hooks", "permissions"];
    try {
      await Promise.all(
        families.map((family) =>
          pendingRegistry.run(`auto-adopt-${family}`, () =>
            autoAdoptMutation.mutateAsync({ family, enabled: true }),
          ),
        ),
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to enable auto-adopt across all families.");
    }
  }

  return {
    data,
    errorMessage: errorMessage || (settingsQuery.error instanceof Error ? settingsQuery.error.message : ""),
    isPending: settingsQuery.isPending,
    isHarnessPending: (harness: string) => pendingRegistry.isPending(settingsSupportActionKey(harness)),
    isAutoAdoptHarnessesPending: (family: string) => pendingRegistry.isPending(`auto-adopt-defaults-${family}`),
    setErrorMessage,
    handleSupportToggle,
    handleAutoAdoptHarnessToggle,
    handleEnableAllAutoAdopt,
  };
}
