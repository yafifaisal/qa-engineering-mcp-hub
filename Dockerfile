# Community Edition image. It is not published from this repository.
FROM ghcr.io/astral-sh/uv:0.13.1 AS uv

FROM python:3.12-slim

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=uv /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 qa-mcp \
    && chown -R qa-mcp:qa-mcp /app
USER qa-mcp

ENTRYPOINT ["qa-mcp"]
CMD ["serve"]
