export interface AgentLabelSource {
  name: string;
  role?: string | null;
}

/** `<role>:<name>` from the agent's frontmatter; just the name when it has no role. */
export function agentLabel({ name, role }: AgentLabelSource): string {
  const trimmedRole = role?.trim();
  return trimmedRole ? `${trimmedRole}:${name}` : name;
}
