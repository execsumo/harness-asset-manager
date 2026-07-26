#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

npm run build
"$ROOT_DIR/.venv/bin/python" -m harness_asset_manager start --state-dir "$ROOT_DIR/.artifacts/runtime"
