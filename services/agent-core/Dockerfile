# agent-core: E4-4 暫定スケルトン(healthcheck サーバ。E9 で常駐ワーカーに置換)
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/pmdf packages/pmdf
COPY services/agent-core services/agent-core

RUN uv sync --frozen --package agent-core --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV AGENT_CORE_HEALTH_PORT=8081

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --retries=5 --start-period=10s \
    CMD curl -f http://localhost:8081/healthz || exit 1

CMD ["python", "-m", "agent_core"]
