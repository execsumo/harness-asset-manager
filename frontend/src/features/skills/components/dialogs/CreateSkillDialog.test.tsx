import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CreateSkillDialog, slugifySkillName } from "./CreateSkillDialog";

const mockMutateAsync = vi.fn();
const mockToast = vi.fn();

interface MockSettings {
  autoAdoptHarnesses?: { skills?: string[] };
}

const settingsWithDefaults = (): MockSettings => ({
  autoAdoptHarnesses: { skills: ["claude", "codex"] },
});

// Hermes is deliberately uninstalled: it must render but stay unselectable.
const skillsPage = () => ({
  harnessColumns: [
    { harness: "claude", label: "Claude", logoKey: "claude", installed: true },
    { harness: "codex", label: "Codex", logoKey: "codex", installed: true },
    { harness: "hermes", label: "Hermes", logoKey: "hermes", installed: false },
  ],
  rows: [
    {
      skillRef: "shared:release-notes",
      name: "release-notes",
      description: "already in the store",
      displayStatus: "Managed",
    },
  ],
});

let mockSettingsData: MockSettings = settingsWithDefaults();
let mockSkillsData = skillsPage();

vi.mock("../../../../components/Toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

vi.mock("../../api/queries", () => ({
  useCreateSkillMutation: () => ({ mutateAsync: mockMutateAsync, isPending: false }),
  useSkillsListQuery: () => ({ data: mockSkillsData }),
}));

vi.mock("../../../settings/public", () => ({
  useSettingsQuery: () => ({ data: mockSettingsData }),
}));

function fillRequiredFields({ name, description }: { name: string; description: string }) {
  fireEvent.change(screen.getByRole("textbox", { name: "Name" }), { target: { value: name } });
  fireEvent.change(screen.getByRole("textbox", { name: "Description" }), {
    target: { value: description },
  });
}

describe("slugifySkillName", () => {
  it("mirrors the server's fold to the spec's name form", () => {
    expect(slugifySkillName("Release Notes Writer")).toBe("release-notes-writer");
    expect(slugifySkillName("  PDF   toolkit!  ")).toBe("pdf-toolkit");
    expect(slugifySkillName("already-fine")).toBe("already-fine");
    expect(slugifySkillName("---")).toBe("");
  });

  it("truncates a long name without leaving a trailing hyphen", () => {
    const slug = slugifySkillName(Array.from({ length: 40 }, () => "word").join(" "));
    expect(slug.length).toBeLessThanOrEqual(64);
    expect(slug.endsWith("-")).toBe(false);
  });
});

describe("CreateSkillDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSettingsData = settingsWithDefaults();
    mockSkillsData = skillsPage();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("edits the same frontmatter surface Skill Details does", () => {
    render(<CreateSkillDialog open={true} onOpenChange={vi.fn()} />);

    expect(screen.getByRole("textbox", { name: "Name" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Description" })).toBeInTheDocument();
    // The raw-YAML escape hatch and the free-form key adder come with that editor.
    expect(screen.getByRole("group", { name: "Frontmatter view mode" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add field/i })).toBeInTheDocument();
  });

  it("shows the package directory the typed name will be written to", () => {
    render(<CreateSkillDialog open={true} onOpenChange={vi.fn()} />);

    fillRequiredFields({ name: "Release Notes Writer", description: "Drafts notes." });

    expect(
      screen.getByText("Written as release-notes-writer/SKILL.md, with name: release-notes-writer."),
    ).toBeInTheDocument();
    expect(screen.getByText("release-notes-writer/SKILL.md")).toBeInTheDocument();
  });

  it("blocks a name that collides with a package already in the store", () => {
    render(<CreateSkillDialog open={true} onOpenChange={vi.fn()} />);

    fillRequiredFields({ name: "Release Notes", description: "Drafts notes." });

    expect(screen.getByText('A skill named "release-notes" already exists.')).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Skill" })).toBeDisabled();
    expect(mockMutateAsync).not.toHaveBeenCalled();
  });

  it("blocks a name that folds to nothing", () => {
    render(<CreateSkillDialog open={true} onOpenChange={vi.fn()} />);

    fillRequiredFields({ name: "---", description: "Drafts notes." });

    expect(
      screen.getByText("Cannot derive a valid package name from this skill name."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Skill" })).toBeDisabled();
  });

  it("keeps the submit disabled until a name and a description are both present", () => {
    render(<CreateSkillDialog open={true} onOpenChange={vi.fn()} />);

    const submit = screen.getByRole("button", { name: "Create Skill" });
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByRole("textbox", { name: "Name" }), {
      target: { value: "Quiet Skill" },
    });
    // A skill with no description is effectively undiscoverable, so it is not creatable.
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByRole("textbox", { name: "Description" }), {
      target: { value: "Says when it applies." },
    });
    expect(submit).not.toBeDisabled();
  });

  it("preselects harnesses from the configured auto-adopt defaults", () => {
    render(<CreateSkillDialog open={true} onOpenChange={vi.fn()} />);

    expect(screen.getByRole("button", { name: /disable claude/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: /disable codex/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: /hermes is not installed/i })).toBeDisabled();
    expect(screen.queryByText(/won't be linked into any harness yet/i)).not.toBeInTheDocument();
  });

  it("notes an unbound skill when nothing is preselected, and clears the note on a pick", () => {
    mockSettingsData = { autoAdoptHarnesses: { skills: [] } };

    render(<CreateSkillDialog open={true} onOpenChange={vi.fn()} />);

    expect(screen.getByText(/won't be linked into any harness yet/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /enable claude/i }));
    expect(screen.queryByText(/won't be linked into any harness yet/i)).not.toBeInTheDocument();
  });

  it("sends the frontmatter, the body and the picked harnesses", async () => {
    mockSettingsData = { autoAdoptHarnesses: { skills: ["claude"] } };
    mockMutateAsync.mockResolvedValueOnce({
      ok: true,
      skillRef: "shared:release-notes-writer",
      name: "release-notes-writer",
      packageDir: "release-notes-writer",
      boundHarnesses: ["claude"],
      harnessFailures: [],
    });
    const onOpenChange = vi.fn();

    render(<CreateSkillDialog open={true} onOpenChange={onOpenChange} />);

    fillRequiredFields({
      name: "Release Notes Writer",
      description: "Drafts release notes from a changelog.",
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Body" }), {
      target: { value: "# Release Notes Writer\n\nSummarise each merged PR." },
    });
    fireEvent.click(screen.getByRole("button", { name: /add field/i }));
    fireEvent.change(screen.getByRole("textbox", { name: "Key for entry 1" }), {
      target: { value: "license" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Value for entry 1" }), {
      target: { value: "MIT" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Create Skill" }));

    expect(mockMutateAsync).toHaveBeenCalledTimes(1);
    expect(mockMutateAsync.mock.calls[0][0]).toEqual({
      name: "Release Notes Writer",
      description: "Drafts release notes from a changelog.",
      body: "# Release Notes Writer\n\nSummarise each merged PR.",
      metadata: [{ key: "license", value: "MIT" }],
      harnesses: ["claude"],
    });

    await vi.waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith("Successfully created skill release-notes-writer");
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  it("names the harnesses a created skill could not be linked into", async () => {
    mockSettingsData = { autoAdoptHarnesses: { skills: ["claude"] } };
    mockMutateAsync.mockResolvedValueOnce({
      ok: false,
      skillRef: "shared:partial-skill",
      name: "partial-skill",
      packageDir: "partial-skill",
      boundHarnesses: [],
      harnessFailures: [{ harness: "claude", error: "harness support is disabled" }],
    });

    render(<CreateSkillDialog open={true} onOpenChange={vi.fn()} />);

    fillRequiredFields({ name: "Partial Skill", description: "One bad target." });
    fireEvent.click(screen.getByRole("button", { name: "Create Skill" }));

    await vi.waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        "Created skill partial-skill, but failed to link it into: claude",
      );
    });
  });

  it("surfaces a failed create without closing the dialog", async () => {
    mockMutateAsync.mockRejectedValueOnce(new Error("an agy-skill already exists"));
    const onOpenChange = vi.fn();

    render(<CreateSkillDialog open={true} onOpenChange={onOpenChange} />);

    fillRequiredFields({ name: "Agy Skill", description: "Collides server-side." });
    fireEvent.click(screen.getByRole("button", { name: "Create Skill" }));

    await screen.findByText("an agy-skill already exists");
    expect(onOpenChange).not.toHaveBeenCalled();
  });
});
