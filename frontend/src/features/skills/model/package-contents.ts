export interface PackageContentGroup {
  name: string;
  isDirectory: boolean;
  /** `scripts/` is code the skill expects to run — worth saying so plainly. */
  executable: boolean;
  /** Paths inside the directory, relative to it. Empty for a root-level file. */
  files: string[];
}

const EXECUTABLE_DIRECTORY = "scripts";

/**
 * Group a package's relative paths by their top-level entry.
 *
 * Adoption copies the whole skill folder, so the detail view has to be able to
 * show what came with `SKILL.md`. Directories sort first so supporting material
 * — and `scripts/` above all — reads as structure rather than as a flat list of
 * anonymous filenames.
 */
export function groupPackageFiles(paths: string[]): PackageContentGroup[] {
  const groups = new Map<string, PackageContentGroup>();

  for (const path of paths) {
    const separator = path.indexOf("/");
    const name = separator === -1 ? path : path.slice(0, separator);
    let group = groups.get(name);
    if (!group) {
      group = {
        name,
        isDirectory: separator !== -1,
        executable: separator !== -1 && name === EXECUTABLE_DIRECTORY,
        files: [],
      };
      groups.set(name, group);
    }
    if (separator !== -1) {
      group.files.push(path.slice(separator + 1));
    }
  }

  return [...groups.values()].sort((left, right) => {
    if (left.isDirectory !== right.isDirectory) return left.isDirectory ? -1 : 1;
    return left.name.localeCompare(right.name);
  });
}
