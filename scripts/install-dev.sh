#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m venv .venv
"$ROOT_DIR/.venv/bin/pip" install -r requirements.txt
# The dev toolchain (ruff, pyright, coverage) is what `npm run validate` and the
# backend-compat CI job run. Without it a fresh checkout cannot reproduce CI locally.
"$ROOT_DIR/.venv/bin/pip" install -r requirements-dev.txt
npm install
