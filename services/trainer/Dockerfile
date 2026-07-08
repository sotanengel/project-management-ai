# trainer: E8 自己学習ループ QLoRA SFT/DPO バッチ(train profile、常時稼働しない)
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/pmdf packages/pmdf
COPY services/agent-core services/agent-core
COPY services/eval-runner services/eval-runner
COPY services/trainer services/trainer
COPY services/scheduler services/scheduler

RUN uv sync --frozen --package trainer --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# バッチジョブのためコンテナ自体のHTTPヘルスチェックは持たない。
# uvが仮想環境を作成できていること(=依存解決成功)を軽量に確認する。
HEALTHCHECK --interval=30s --timeout=5s --retries=5 --start-period=10s \
    CMD python -c "import trainer" || exit 1

# 既定はCLIヘルプ表示(バッチ用途のためデフォルトでは学習を開始しない)。
# 実行時は `docker compose --profile train run trainer trainer-sft <dataset>` 等で上書きする。
CMD ["trainer-sft", "--help"]
