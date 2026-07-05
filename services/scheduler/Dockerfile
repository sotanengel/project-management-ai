# scheduler: E4-4 暫定スケルトン(healthcheck + 空 APScheduler)
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY services/scheduler services/scheduler

RUN uv sync --frozen --package scheduler --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV SCHEDULER_HEALTH_PORT=8082

EXPOSE 8082

HEALTHCHECK --interval=30s --timeout=5s --retries=5 --start-period=10s \
    CMD curl -f http://localhost:8082/healthz || exit 1

CMD ["python", "-m", "scheduler.main"]
