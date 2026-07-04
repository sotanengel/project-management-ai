"""model-gateway経由(論理名 `pdm-embed`)の埋め込み取得クライアント(E6-2)。

OpenAI互換の `/embeddings` エンドポイントへリクエストする薄いラッパー。
実モデル名は一切扱わず、論理名 `pdm-embed` のみをコード上で指定する
(AR-01)。model-gatewayが未起動の環境でもテストはrespxモックで完結する。
"""

from __future__ import annotations

import httpx

#: model-gatewayに指定する埋め込み用の論理名(実モデル名はコードに持たない)。
EMBEDDING_LOGICAL_NAME = "pdm-embed"


class GatewayEmbeddingClient:
    """model-gateway(OpenAI互換 `/embeddings`)経由の埋め込みクライアント。"""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """`texts` に対応する埋め込みベクトルのリストを返す。

        `texts` が空の場合は空リストを返す(HTTPリクエストは行わない)。
        """
        if not texts:
            return []

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/embeddings",
                json={"model": EMBEDDING_LOGICAL_NAME, "input": texts},
            )
            response.raise_for_status()
            body = response.json()

        # OpenAI互換レスポンスの `data` はindex順とは限らないため明示的にソートする。
        data = sorted(body["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in data]


__all__ = ["EMBEDDING_LOGICAL_NAME", "GatewayEmbeddingClient"]
