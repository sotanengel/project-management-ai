#!/usr/bin/env bash
# 埋め込みモデル切替検証スクリプト(E6-4)。
#
# `pdm-embed`論理名の設定変更のみ(kb-ingestのコード変更なし)で、
# 異なる次元(モデルA: 1536、モデルB: 768)の埋め込みモデルへ切り替え
# られること、次元不一致時にコレクション再作成が必要な旨の明確な
# エラーが出ること、再作成後は新次元で投入・検索が通ることを検証する。
#
# 実体はPython実装(scripts/switch_embedding_model_check.py)に委譲する。
# 実model-gatewayは使用せず、ローカルにモデルA/B相当のモック埋め込み
# HTTPサーバを一時起動して代替する(litellm.config.yamlのpdm-embed
# エントリの変更のみで実モデルを切り替える運用と等価な検証)。
#
# 参照: docs/kb-embedding-switch.md
#
# exit code:
#   0: 検証成功
#   1: 検証失敗
#   2: 前提コマンド(uv)が見つからない

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "[NG] uv コマンドが見つかりません。https://docs.astral.sh/uv/ を参照してインストールしてください。" >&2
  exit 2
fi

cd "${REPO_ROOT}"
uv run python scripts/switch_embedding_model_check.py
