#!/bin/bash
set -euo pipefail

export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
export HAM_DATA="${HAM_DATA:-$HOME/.local/share/harnessam}"

echo "Checking hermes skills list..."
if ! "$HERMES_HOME/hermes-agent/venv/bin/hermes" skills list | grep "tailnet-web-serving" > /dev/null; then
    echo "FAIL: hermes skills list does not show a HAM-bound skill"
    exit 1
fi
echo "PASS: hermes skills list"

echo "Checking hermes curator list-unmanaged..."
if ! "$HERMES_HOME/hermes-agent/venv/bin/hermes" curator list-unmanaged | grep "tailnet-web-serving" > /dev/null; then
    echo "FAIL: hermes curator list-unmanaged does not include HAM-bound skills"
    exit 1
fi
echo "PASS: hermes curator list-unmanaged"

echo "Testing _find_skill and skill_view..."
cat << 'PYEOF' > test_hermes.py
import sys
from pathlib import Path

from tools.skill_manager_tool import _find_skill
from tools.skills_tool import skill_view

res1 = _find_skill("tailnet-web-serving")
res2 = _find_skill("harnessam/tailnet-web-serving")

if not res1 or not res2:
    print("res1 or res2 missing", res1, res2)
    sys.exit(1)

p1 = res1["path"]
p2 = res2["path"]

if p1 != p2:
    print("p1 != p2", p1, p2)
    sys.exit(1)

if ".hermes/skills/harnessam" not in str(p1):
    print("not in str p1", p1)
    sys.exit(1)

skill_md = p1 / "SKILL.md"
if not skill_md.exists():
    print("skill_md missing")
    sys.exit(1)

resolved = str(skill_md.resolve())
if not (resolved.startswith(str(Path.home() / ".local/share/harnessam/skills")) or
        resolved.startswith(str(Path.home() / ".harnessam/skills")) or
        resolved.startswith(str(Path.home() / ".dotfiles/.harnessam/skills"))):
    print("skill_md resolve fail", resolved)
    sys.exit(1)

view = skill_view("harnessam/tailnet-web-serving")
if "tailnet-web-serving" not in view:
    print("view fail", view)
    sys.exit(1)

PYEOF

"$HERMES_HOME/hermes-agent/venv/bin/python" test_hermes.py
rm test_hermes.py
echo "PASS: _find_skill and skill_view"

echo "Testing write through Hermes editor path..."
cat << 'PYEOF' > test_write.py
import sys
from pathlib import Path

from tools.skill_manager_tool import _find_skill

p1 = _find_skill("harnessam/tailnet-web-serving")["path"]

old_symlink_target = p1.resolve()

with open(p1 / "test_file.txt", "w") as f:
    f.write("test")

if not p1.is_symlink():
    sys.exit(1)

if p1.resolve() != old_symlink_target:
    sys.exit(1)

test_file = p1 / "test_file.txt"
if test_file.exists():
    test_file.unlink()

PYEOF
"$HERMES_HOME/hermes-agent/venv/bin/python" test_write.py
rm test_write.py
echo "PASS: write through Hermes editor"

echo "Testing delete refused..."
cat << 'PYEOF' > test_delete.py
import sys
from pathlib import Path
from tools.skill_manager_guards import _validate_delete_target
from tools.skill_manager_tool import _find_skill

p1 = _find_skill("harnessam/tailnet-web-serving")["path"]

result = _validate_delete_target(p1)
if result is None:
    print("FAIL: delete was allowed!")
    sys.exit(1)

if "symlink" not in result.lower() and "redirect" not in result.lower():
    print("FAIL: unexpected refusal reason:", result)
    sys.exit(1)
PYEOF
"$HERMES_HOME/hermes-agent/venv/bin/python" test_delete.py
rm test_delete.py
echo "PASS: delete refused"

