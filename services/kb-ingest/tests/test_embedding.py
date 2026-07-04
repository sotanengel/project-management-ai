"""kb_ingest.embedding のテスト(E6-2)。

model-gateway(論理名 pdm-embed)経由のOpenAI互換 /embeddings
エンドポイントをrespxでモックして検証する。
"""

from __future__ import annotations

import httpx
import pytest
import respx
from kb_ingest.embedding import GatewayEmbeddingClient


@pytest.mark.asyncio
@respx.mock
async def test_embed_calls_gateway_embeddings_endpoint() -> None:
    route = respx.post("http://model-gateway:4000/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"embedding": [0.1, 0.2, 0.3], "index": 0},
                    {"embedding": [0.4, 0.5, 0.6], "index": 1},
                ]
            },
        )
    )
    client = GatewayEmbeddingClient(base_url="http://model-gateway:4000")
    result = await client.embed(["テキスト1", "テキスト2"])

    assert route.called
    request_body = route.calls[0].request.content
    import json

    payload = json.loads(request_body)
    assert payload["model"] == "pdm-embed"
    assert payload["input"] == ["テキスト1", "テキスト2"]
    assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


@pytest.mark.asyncio
@respx.mock
async def test_embed_empty_input_returns_empty_list() -> None:
    client = GatewayEmbeddingClient(base_url="http://model-gateway:4000")
    result = await client.embed([])
    assert result == []


@pytest.mark.asyncio
@respx.mock
async def test_embed_raises_on_gateway_error() -> None:
    respx.post("http://model-gateway:4000/embeddings").mock(
        return_value=httpx.Response(500, json={"error": "internal"})
    )
    client = GatewayEmbeddingClient(base_url="http://model-gateway:4000")
    with pytest.raises(httpx.HTTPStatusError):
        await client.embed(["テキスト"])
