$ErrorActionPreference = "Stop"

# Milestone 11 bootstrap: install the locked environment. This does not publish.
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is required: https://docs.astral.sh/uv/"
    exit 127
}

uv sync --frozen
uv run qa-mcp doctor
