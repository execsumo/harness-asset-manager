import { UiTooltip } from "../../../components/ui/UiTooltip";
import { getHarnessPresentation } from "../../../components/harness/harnessPresentation";
import type { AgentInventoryDto, AgentInventoryEntryDto } from "../api/types";

interface AgentsHarnessLogoStackProps {
  bindings: AgentInventoryEntryDto["bindings"];
  columns: AgentInventoryDto["columns"];
}

export function AgentsHarnessLogoStack({ bindings, columns }: AgentsHarnessLogoStackProps) {
  const labelByHarness = new Map(columns.map((c) => [c.harness, c.label]));
  const logoByHarness = new Map(columns.map((c) => [c.harness, c.logoKey ?? c.harness]));
  const enabledBindings = bindings.filter((b) => b.state === "enabled");
  const enabledCount = enabledBindings.length;
  const totalCount = columns.length;
  const ariaLabel = `Enabled on ${enabledCount} of ${totalCount} harnesses`;

  return (
    <div className="skill-card__harness-row">
      <div className="harness-stack" aria-label={ariaLabel}>
        {enabledBindings.map((binding, index) => {
          const presentation = getHarnessPresentation(logoByHarness.get(binding.harness) ?? null);
          const label = labelByHarness.get(binding.harness) ?? binding.harness;
          return (
            <UiTooltip key={binding.harness} content={label}>
              <span
                className="harness-stack__item"
                style={{ zIndex: enabledBindings.length - index }}
              >
                {presentation ? (
                  <img src={presentation.logoSrc} alt="" aria-hidden="true" />
                ) : (
                  <span className="harness-stack__fallback">{label.slice(0, 1)}</span>
                )}
              </span>
            </UiTooltip>
          );
        })}
      </div>
      <span className="skill-card__harness-count">
        {enabledCount}/{totalCount}
      </span>
    </div>
  );
}
