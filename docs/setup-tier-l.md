# Tier-L セットアップ手順 (Windows / WSL2)

Tier-L はローカル開発・検証用の構成です。GPU 推論を使う場合は `local-gpu`
プロファイルを追加します。

## 前提

- Windows 11 + WSL2 (Ubuntu 22.04 推奨)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (WSL2 バックエンド有効)
- [uv](https://docs.astral.sh/uv/) (Python 3.12+)
- Node.js 20+ / [pnpm](https://pnpm.io/) 9+ (web-ui)
- (GPU 推論時) NVIDIA ドライバ + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

## 1. リポジトリ取得

```bash
git clone https://github.com/sotanengel/project-management-ai.git
cd project-management-ai
git switch main && git pull
uv sync --all-packages
```

## 2. 環境変数

```bash
cp .env.example .env
# JWT_SECRET, MODEL_GATEWAY_URL, ACTIVE_BACKEND 等を編集
```

メール認証を使う本番相当の検証では、Cognito 等のメール OTP 設定を
`.env` 経由で参照すること(シークレットの直書き禁止)。

## 3. API スタック起動 (CPU / クラウド API)

```bash
docker compose --profile api-only up -d --build
docker compose ps   # 9 サービスが healthy になること (AC-01)
```

常時稼働: web-ui, api-server, agent-core, pmdf-store, model-gateway,
qdrant, minio, mlflow, scheduler

## 4. GPU 推論 (local-gpu)

WSL2 内で `nvidia-smi` が動作することを確認後:

```bash
docker compose --profile api-only --profile local-gpu up -d --build
```

`ACTIVE_BACKEND=ollama` にし、Ollama コンテナが GPU を認識していることを
`docker compose logs ollama` で確認する。

## 5. 学習バッチ (train profile)

```bash
docker compose --profile train run --rm trainer --help
docker compose --profile train run --rm eval-runner --help
```

scheduler の `trigger_learning_loop()` は compose 上の trainer /
eval-runner を HTTP/CLI 経由で起動する想定です。

## 6. Web UI

```bash
cd services/web-ui
pnpm install
pnpm dev   # http://localhost:5173
```

## 7. サンプルデータ投入

```bash
uv run python scripts/seed_sample_product/seed.py
```

## 8. 検証コマンド

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run pytest
cd services/web-ui && pnpm lint && pnpm test && pnpm test:e2e
```

## トラブルシューティング

| 症状                      | 対処                                                                          |
| ------------------------- | ----------------------------------------------------------------------------- |
| compose healthcheck 失敗  | `docker compose logs <service>` で起動エラー確認。ポート競合(8000/5173)を解消 |
| WSL2 で GPU 未認識        | Windows 側ドライバ更新、Docker Desktop → Resources → WSL integration 有効化   |
| pmdf-store 書き込みエラー | `data/pmdf-store` の権限・ロックファイルを確認                                |
| 予算超過で学習停止        | `data/budget_exceeded.json` と api-server `/costs/learning-blocked` を確認    |
