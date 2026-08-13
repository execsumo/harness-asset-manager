#!/usr/bin/env bash
set -euo pipefail

# Remove reproducible local analysis/test caches without touching source or user data.
find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) \
  -prune -exec rm -rf {} +
