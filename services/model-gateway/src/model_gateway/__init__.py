"""model-gateway: LiteLLM Proxy設定(litellm.config.yaml)の検証・参照実装。

実運用のプロキシ処理は公式`ghcr.io/berriai/litellm`イメージ(コンテナ)が担う
(`services/model-gateway/Dockerfile`参照)。本パッケージはCIで
`litellm.config.yaml`の構造・ルーティング契約をPythonパッケージの依存関係
衝突(litellm 1.90.2 は typer<0.26系を要求し、`packages/pmdf`の
`typer>=0.26.8`要件と衝突する)なしに検証するための軽量テスト用実装を提供する。
"""

from __future__ import annotations

__all__: list[str] = []
