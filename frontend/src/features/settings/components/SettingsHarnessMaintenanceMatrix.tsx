import { Fragment } from "react";

import { HarnessAvatar } from "../../../components/harness/HarnessAvatar";
import { ToggleSwitch } from "../../../components/ToggleSwitch";
import { useFormatPath } from "../../../lib/paths";
import type { SettingsHarness } from "../api/types";
import type { SettingsCopy } from "../i18n";

export const autoAdoptFamilies = ["agents", "skills", "slash_commands", "mcp", "hooks", "permissions"] as const;
export type AutoAdoptFamily = (typeof autoAdoptFamilies)[number];

type AutoAdoptCopy = SettingsCopy["autoAdopt"];

interface SettingsHarnessMaintenanceMatrixProps {
  harnesses: SettingsHarness[];
  autoAdoptHarnesses: Record<string, string[]>;
  autoAdoptHarnessOptions: Record<string, string[]>;
  harnessCopy: SettingsCopy["harnesses"];
  copy: AutoAdoptCopy;
  isAutoAdoptHarnessesPending: (family: string) => boolean;
  isHarnessPending: (harness: string) => boolean;
  onAutoAdoptHarnessToggle: (family: string, harness: string, enabled: boolean) => void;
  onHarnessSupportToggle: (harness: string, enabled: boolean) => void;
  onEnableAllAutoAdopt: () => void;
}

export function SettingsHarnessMaintenanceMatrix({
  harnesses,
  autoAdoptHarnesses,
  autoAdoptHarnessOptions,
  harnessCopy,
  copy,
  isAutoAdoptHarnessesPending,
  isHarnessPending,
  onAutoAdoptHarnessToggle,
  onHarnessSupportToggle,
  onEnableAllAutoAdopt,
}: SettingsHarnessMaintenanceMatrixProps) {
  const formatPath = useFormatPath();

  return (
    <div className="settings-maintenance">
      <div className="settings-maintenance__header">
        <h3 className="settings-harness-group__heading">{copy.heading}</h3>
        <button type="button" className="action-pill" onClick={onEnableAllAutoAdopt}>
          {copy.enableAll}
        </button>
      </div>
      <div className="settings-maintenance__scroll">
        <table className="settings-maintenance__table">
          <caption className="sr-only">{copy.heading}</caption>
          <thead>
            <tr>
              <th scope="col">Harness</th>
              {autoAdoptFamilies.map((family) => {
                const option = copy[family];
                return (
                  <th scope="col" id={`settings-maintenance-${family}`} key={family}>
                    <span className="settings-maintenance__family-label" title={option.sub}>
                      {option.short}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {harnesses.map((harness, index) => (
              <Fragment key={harness.harness}>
                {index === 0 || harness.installed !== harnesses[index - 1]?.installed ? (
                  <tr className="settings-maintenance__group-heading">
                    <th colSpan={autoAdoptFamilies.length + 1} scope="rowgroup">
                      {harness.installed ? harnessCopy.detectedHeading : harnessCopy.notDetectedHeading}
                    </th>
                  </tr>
                ) : null}
                <HarnessMaintenanceRow
                  harness={harness}
                  autoAdoptHarnesses={autoAdoptHarnesses}
                  autoAdoptHarnessOptions={autoAdoptHarnessOptions}
                  harnessCopy={harnessCopy}
                  copy={copy}
                  formatPath={formatPath}
                  isAutoAdoptHarnessesPending={isAutoAdoptHarnessesPending}
                  isHarnessPending={isHarnessPending}
                  onAutoAdoptHarnessToggle={onAutoAdoptHarnessToggle}
                  onHarnessSupportToggle={onHarnessSupportToggle}
                />
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface HarnessMaintenanceRowProps {
  harness: SettingsHarness;
  autoAdoptHarnesses: Record<string, string[]>;
  autoAdoptHarnessOptions: Record<string, string[]>;
  harnessCopy: SettingsCopy["harnesses"];
  copy: AutoAdoptCopy;
  formatPath: (path: string) => string;
  isAutoAdoptHarnessesPending: (family: string) => boolean;
  isHarnessPending: (harness: string) => boolean;
  onAutoAdoptHarnessToggle: (family: string, harness: string, enabled: boolean) => void;
  onHarnessSupportToggle: (harness: string, enabled: boolean) => void;
}

function HarnessMaintenanceRow({
  harness,
  autoAdoptHarnesses,
  autoAdoptHarnessOptions,
  harnessCopy,
  copy,
  formatPath,
  isAutoAdoptHarnessesPending,
  isHarnessPending,
  onAutoAdoptHarnessToggle,
  onHarnessSupportToggle,
}: HarnessMaintenanceRowProps) {
  const supportEnabled = harness.installed && harness.supportEnabled;

  return (
    <tr>
      <th scope="row" className="settings-maintenance__harness">
        <HarnessAvatar harness={harness.harness} label={harness.label} logoKey={harness.logoKey} />
        <div className="settings-maintenance__harness-info">
          <span className="settings-maintenance__harness-name">{harness.label}</span>
          {harness.managedLocation ? (
            <span className="settings-maintenance__harness-path">{formatPath(harness.managedLocation)}</span>
          ) : null}
        </div>
        <ToggleSwitch
          checked={supportEnabled}
          disabled={isHarnessPending(harness.harness) || !harness.installed}
          label=""
          ariaLabel={harnessCopy.enableSupport(harness.label)}
          pendingLabel={harnessCopy.saving}
          onCheckedChange={(checked) => onHarnessSupportToggle(harness.harness, checked)}
        />
      </th>
      {autoAdoptFamilies.map((family) => {
        const option = copy[family];
        const supported = autoAdoptHarnessOptions[family]?.includes(harness.harness) ?? false;
        const selected = autoAdoptHarnesses[family]?.includes(harness.harness) ?? false;
        const disabled =
          !supported ||
          !harness.installed ||
          !harness.supportEnabled ||
          isAutoAdoptHarnessesPending(family) ||
          isHarnessPending(harness.harness);
        return (
          <td
            className="settings-maintenance__cell"
            key={`${harness.harness}-${family}`}
            headers={`settings-maintenance-${family}`}
          >
            {supported ? (
              <input
                type="checkbox"
                checked={selected}
                disabled={disabled || isHarnessPending(harness.harness)}
                aria-label={`${option.label} for ${harness.label}`}
                onChange={(event) => onAutoAdoptHarnessToggle(family, harness.harness, event.currentTarget.checked)}
              />
            ) : (
              <span className="settings-maintenance__unsupported" aria-label={`${option.label} not supported for ${harness.label}`}>
                —
              </span>
            )}
          </td>
        );
      })}
    </tr>
  );
}
