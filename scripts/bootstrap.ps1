$ErrorActionPreference = "Stop"

# Milestone 00 bootstrap: install exactly the locked project environment.
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is required: https://docs.astral.sh/uv/"
    exit 127
}

uv sync --locked
uv run qa-mcp doctor
