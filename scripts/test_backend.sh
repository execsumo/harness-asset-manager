#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

"$ROOT_DIR/.venv/bin/coverage" erase
"$ROOT_DIR/.venv/bin/coverage" run \
  --branch \
  --source=harness_asset_manager \
  -m unittest discover tests/unit -p 'test_*.py'
"$ROOT_DIR/.venv/bin/coverage" run \
  --branch \
  --source=harness_asset_manager \
  -a \
  -m unittest discover tests/integration -p 'test_*.py'
"$ROOT_DIR/.venv/bin/coverage" report -m --fail-under=80
