import claudeLogo from "../../assets/harness-logos/claude-code-logo.svg";
import codexLogo from "../../assets/harness-logos/codex-logo.svg";
import cursorLogo from "../../assets/harness-logos/cursor-logo.svg";
import opencodeLogo from "../../assets/harness-logos/opencode-logo.svg";
import agyLogo from "../../assets/harness-logos/agy-logo.svg";
import droidLogo from "../../assets/harness-logos/droid-logo.png";
import hermesLogo from "../../assets/harness-logos/hermes-logo.png";
import piLogo from "../../assets/harness-logos/pi-logo.svg";

export type HarnessLogoKey = "claude" | "codex" | "cursor" | "hermes" | "opencode" | "agy" | "droid" | "pi";

interface HarnessPresentation {
  logoSrc: string;
  variant: HarnessLogoKey;
}

const HARNESS_LOGO_ASSETS: Record<HarnessLogoKey, HarnessPresentation> = {
  claude: {
    logoSrc: claudeLogo,
    variant: "claude",
  },
  codex: {
    logoSrc: codexLogo,
    variant: "codex",
  },
  cursor: {
    logoSrc: cursorLogo,
    variant: "cursor",
  },
  hermes: {
    logoSrc: hermesLogo,
    variant: "hermes",
  },
  opencode: {
    logoSrc: opencodeLogo,
    variant: "opencode",
  },
  agy: {
    logoSrc: agyLogo,
    variant: "agy",
  },
  droid: {
    logoSrc: droidLogo,
    variant: "droid",
  },
  pi: {
    logoSrc: piLogo,
    variant: "pi",
  },
};

export function getHarnessPresentation(logoKey: string | null | undefined): HarnessPresentation | null {
  if (!logoKey) {
    return null;
  }
  const family = logoKey.split(":", 1)[0] as HarnessLogoKey;
  return HARNESS_LOGO_ASSETS[family] ?? null;
}

export function harnessFamily(value: string): string {
  return value.split(":", 1)[0];
}
