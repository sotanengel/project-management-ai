# project-management-ai (PdM AI)

プロジェクトマネジメントを支援するAIエージェント基盤。Tier-S(ローカルGPU)/
Tier-L(API-only)を同一の Docker Compose 定義で切り替えて動作させることを
目標とする。

## ディレクトリ構成

```
.
├── packages/        # 共有Pythonパッケージ (uvワークスペースメンバー)
│   └── pmdf/        # 共通データ基盤パッケージ (プレースホルダ)
├── services/        # 各サービス (api-server, agent-core, model-gateway 等)
├── scripts/         # 運用・移行用スクリプト
│   └── bootstrap_issues/  # GitHub Issue 一括登録スクリプト
├── docs/            # 実装状況・設計ドキュメント
├── .github/workflows/  # CI (GitHub Actions)
├── pyproject.toml   # uv ワークスペースルート定義
└── docker-compose.yml  # 全サービス定義 (profiles で環境切替)
```

## セットアップ

### 前提

- [uv](https://docs.astral.sh/uv/) (Pythonパッケージ/ワークスペース管理)
- Python 3.12 以上 (`uv python install 3.12` で導入可能)
- Docker Compose v2 (サービスをコンテナで起動する場合)

### Python ワークスペースのセットアップ

```bash
uv sync
```

ワークスペースメンバー(`packages/*`, `services/*` のうちPythonパッケージ)
が一括でインストールされる。動作確認:

```bash
uv run python -c "import pmdf; print(pmdf.__version__)"
```

### pre-commit フックの有効化

```bash
uv tool run pre-commit install
uv tool run pre-commit run --all-files
```

### Docker Compose (任意)

```bash
docker compose --profile api-only config
```

利用可能な profile: `api-only`(APIのみ、GPU不要) / `local-gpu`(Ollama等
ローカルGPU推論) / `train`(学習・評価用ワーカー)。

**注意(GPU排他)**: `local-gpu` と `train` の profile は同時起動しないこと。
両者は同一GPUリソースを奪い合うため、片方を停止してからもう片方を起動する
運用とする。詳細は `docs/IMPLEMENTATION_STATE.md` を参照。

## 開発を再開する場合

実装の中断・再開手順は [`docs/IMPLEMENTATION_STATE.md`](docs/IMPLEMENTATION_STATE.md)
を参照。要約:

1. `gh issue list --repo sotanengel/project-management-ai --state open --label in-progress` で中断中のイシューを確認
2. 見つかればそのイシューのコメントで進捗・次の一手を確認して再開
3. なければ `docs/IMPLEMENTATION_STATE.md` のエピック対応表からphase順に次の未着手イシューに着手

実装規約は [`CLAUDE.md`](CLAUDE.md) を参照。

## ブランチ運用

すべての実装作業は `develop` ブランチ上で行う。`main` へのマージは
ユーザーが手動で行う方針のため、実装エージェントは `main` への切替や
PRマージを行わない。
