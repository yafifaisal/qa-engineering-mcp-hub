#!/usr/bin/env sh
set -eu

# Milestone 11 bootstrap: install the locked environment. This does not publish.
command -v uv >/dev/null 2>&1 || {
  echo "uv is required: https://docs.astral.sh/uv/" >&2
  exit 127
}
uv sync --frozen
uv run qa-mcp doctor
