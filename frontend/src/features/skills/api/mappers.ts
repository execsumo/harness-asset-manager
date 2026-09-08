import type { SkillDetailDto, SkillTableRowDto, SkillsPageDto } from "./types";
import type { SkillDetail, SkillListRow, SkillsWorkspaceData } from "../model/types";

export function mapSkillsPage(dto: SkillsPageDto): SkillsWorkspaceData {
  return {
    summary: dto.summary,
    harnessColumns: dto.harnessColumns,
    rows: dto.rows.map(mapSkillRow),
  };
}

export function mapSkillDetail(dto: SkillDetailDto): SkillDetail {
  const linkedTargets = dto.linkedTargets ?? dto.locations
    .map((location) => location.harness)
    .filter((harness): harness is string => harness !== null);

  return {
    skillRef: dto.skillRef,
    name: dto.name,
    description: dto.description,
    displayStatus: dto.displayStatus,
    attentionMessage: dto.attentionMessage,
    tags: dto.tags ?? [],
    actions: {
      ...dto.actions,
      updateStatus: null,
    },
    harnessCells: dto.harnessCells,
    linkedTargets,
    locations: dto.locations,
    sourceLinks: dto.sourceLinks,
    documentMarkdown: dto.documentMarkdown,
    metadata: dto.metadata ?? [],
    packageFiles: dto.packageFiles ?? [],
    conformance: dto.conformance ?? [],
  };
}

function mapSkillRow(dto: SkillTableRowDto): SkillListRow {
  return {
    skillRef: dto.skillRef,
    name: dto.name,
    description: dto.description,
    displayStatus: dto.displayStatus,
    tags: dto.tags ?? [],
    actions: dto.actions,
    cells: dto.cells,
    linkedTargets: dto.linkedTargets,
    conformance: dto.conformance ?? [],
  };
}
