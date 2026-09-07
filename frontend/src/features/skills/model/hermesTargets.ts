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

/** Bots a skill was *seen* in, including unmanaged copies a Bot created itself.
 *
 * Binding targets only name Bots HAM has bound. An adoption candidate has no
 * binding yet, so its originating Bot is only knowable from where it was found.
 */
export function hermesBotScopesFromLocations(
  locations: readonly { harness?: string | null }[] | undefined,
): string[] {
  return hermesBotScopes(
    (locations ?? [])
      .map((location) => location.harness)
      .filter((harness): harness is string => typeof harness === "string"),
  );
}
