#!/usr/bin/env bash
# Prove that a HAM-bound Skill is indistinguishable from a native Hermes Skill.
#
# Read-only with respect to HAM state. The one write (an edit through Hermes'
# editor path) is made to a scratch package this script creates and removes, so
# no Skill you own is ever touched.
#
# Exits non-zero on the first failed check.
set -uo pipefail

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
pass() { printf 'PASS: %s\n' "$1"; }

command -v hermes >/dev/null || fail "hermes is not on PATH"
command -v harnessam >/dev/null || fail "harnessam is not on PATH"

# Resolve Hermes' own interpreter from its launcher rather than guessing a
# layout — the launcher is the only thing that knows where the venv lives.
HERMES_PY=$(sed -n 's|^exec "\([^"]*python[^"]*\)".*|\1|p' "$(command -v hermes)" | head -1)
[ -x "${HERMES_PY:-}" ] || fail "could not resolve the Hermes interpreter from $(command -v hermes)"

# The sidecar must be installed, or every check below is meaningless.
status=$(harnessam hermes compat status)
[ "$status" = "current" ] || fail "sidecar status is '$status', expected 'current' (run: harnessam hermes compat install)"
pass "compatibility sidecar is current"

# Pick a real HAM binding rather than hardcoding a Skill name. Emits
# "<package-dir> <declared-name>" per binding: Hermes indexes a Skill by its
# frontmatter `name`, which need not match the package directory, and a Skill
# whose name collides with a native one loses and never appears in the list.
mapfile -t BINDINGS < <("$HERMES_PY" - <<'PY'
from hermes_constants import get_skills_dir
from tools.skill_usage import _read_skill_name

category = get_skills_dir() / "harnessam"
if category.is_dir():
    for package in sorted(p for p in category.iterdir() if p.is_symlink()):
        index = package / "SKILL.md"
        if index.is_file():
            print(package.name, _read_skill_name(index, fallback=package.name))
PY
)
[ "${#BINDINGS[@]}" -gt 0 ] || fail "no HAM binding found under the Hermes 'harnessam' category; enable one first"

LISTED=$(hermes skills list)
SKILL=""
for row in "${BINDINGS[@]}"; do
    declared=${row#* }
    if grep -qF -- "${declared:0:18}" <<<"$LISTED"; then
        SKILL=${row%% *}
        DECLARED=$declared
        break
    fi
done
[ -n "$SKILL" ] || fail "none of the ${#BINDINGS[@]} HAM bindings appear in 'hermes skills list'"
printf 'Using HAM-bound skill: %s (declared name: %s)\n\n' "$SKILL" "$DECLARED"
pass "discovered by 'hermes skills list'"

if ! hermes curator list-unmanaged 2>/dev/null | grep -qF -- "$DECLARED"; then
    "$HERMES_PY" -c "
import sys
from tools import skill_usage
sys.exit(0 if skill_usage.is_curator_managed('$DECLARED') else 1)
" || fail "$DECLARED is neither curator-adoptable nor curator-managed"
fi
pass "visible to the curator (adoptable or already managed)"

"$HERMES_PY" - "$SKILL" <<'PY' || exit 1
import json
import sys
import tempfile
from pathlib import Path

from tools.skill_manager_guards import _validate_delete_target
from tools.skill_manager_tool import _find_skill, _skills_dir, skill_manage
from tools.skills_tool import skill_view

name = sys.argv[1]
ok = True


def check(label, condition):
    global ok
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    ok = ok and bool(condition)


bare = _find_skill(name)
categorised = _find_skill(f"harnessam/{name}")
check("_find_skill resolves the bare name", bare is not None)
check("_find_skill resolves the categorised name", categorised is not None)
if bare is None or categorised is None:
    sys.exit(1)

link = bare["path"]
check("both forms return the same path", link == categorised["path"])
check("the returned path is the lexical Hermes path", link == _skills_dir() / "harnessam" / name)
check("the binding is a directory symlink", link.is_symlink())
check("reading SKILL.md through the link reaches the canonical package",
      (link / "SKILL.md").read_text() == link.resolve().joinpath("SKILL.md").read_text())

check("skill_view loads the skill", json.loads(skill_view(name)).get("success") is True)

support = next(
    (p for sub in ("references", "templates", "assets", "scripts")
     for p in sorted((link / sub).glob("*")) if p.is_file()),
    None,
)
if support is None:
    print("SKIP: no supporting file in this package to load")
else:
    rel = support.relative_to(link).as_posix()
    check(f"skill_view loads the supporting file {rel}",
          json.loads(skill_view(name, file_path=rel)).get("success") is True)

check("deleting through the symlink is refused", _validate_delete_target(link) is not None)

# The only write: round-trip a scratch package through Hermes' editor path.
with tempfile.TemporaryDirectory() as tmp:
    canonical = Path(tmp) / "ham-parity-probe"
    canonical.mkdir()
    (canonical / "SKILL.md").write_text(
        "---\nname: ham-parity-probe\ndescription: scratch package for parity verification\n---\nbody\n"
    )
    probe = _skills_dir() / "harnessam" / "ham-parity-probe"
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.symlink_to(canonical, target_is_directory=True)
    try:
        updated = (canonical / "SKILL.md").read_text() + "\nedited through Hermes\n"
        result = json.loads(skill_manage(action="patch", name="ham-parity-probe", content=updated))
        check("an edit through Hermes' editor path succeeds", result.get("success") is True)
        check("the edit reaches the canonical package",
              "edited through Hermes" in (canonical / "SKILL.md").read_text())
        check("the binding is still a symlink, not a real directory", probe.is_symlink())
    finally:
        if probe.is_symlink():
            probe.unlink()

sys.exit(0 if ok else 1)
PY

printf '\nAll parity checks passed.\n'
