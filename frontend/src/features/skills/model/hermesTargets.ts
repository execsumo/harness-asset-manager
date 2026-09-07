import { harnessFamily } from "../../../components/harness/harnessPresentation";

/** Return only scoped Hermes targets; the unscoped default profile stays implicit. */
export function hermesBotScopes(targets: readonly string[] | undefined): string[] {
  if (!targets) return [];
  return targets
    .filter((target) => harnessFamily(target) === "hermes")
    .map((target) => target.slice("hermes:".length))
    .filter(Boolean);
}

/** Profile ids are slugs; title-case them for a readable Bot label. */
export function hermesBotLabel(scope: string): string {
  return scope
    .split(/[-_]+/)
    .filter(Boolean)
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}
