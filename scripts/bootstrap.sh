#!/usr/bin/env sh
set -eu

# Milestone 00 bootstrap: install exactly the locked project environment.
command -v uv >/dev/null 2>&1 || {
  echo "uv is required: https://docs.astral.sh/uv/" >&2
  exit 127
}
uv sync --locked
uv run qa-mcp doctor
