import { useState } from "react";

import { usePendingRegistry } from "../../../lib/async/pending-registry";
import {
  useAutoAdoptMutation,
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
  const pendingRegistry = usePendingRegistry<string>();

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

  async function handleAutoAdoptToggle(family: string, nextEnabled: boolean) {
    setErrorMessage("");
    try {
      await pendingRegistry.run(
        `auto-adopt-${family}`,
        () => autoAdoptMutation.mutateAsync({ family, enabled: nextEnabled }),
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to update auto-adopt settings.");
    }
  }

  return {
    data: settingsQuery.data ?? null,
    errorMessage: errorMessage || (settingsQuery.error instanceof Error ? settingsQuery.error.message : ""),
    isPending: settingsQuery.isPending,
    isHarnessPending: (harness: string) => pendingRegistry.isPending(settingsSupportActionKey(harness)),
    isAutoAdoptPending: (family: string) => pendingRegistry.isPending(`auto-adopt-${family}`),
    setErrorMessage,
    handleSupportToggle,
    handleAutoAdoptToggle,
  };
}
