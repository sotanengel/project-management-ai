"""`LogicalModelClient`(model-gateway経由のLLMクライアント)のテスト(E5-1)。"""

from __future__ import annotations

import httpx
import pytest
import respx
from agent_core.llm_client import LogicalModelClient


@pytest.mark.asyncio
async def test_complete_sends_request_to_gateway_chat_completions_endpoint() -> None:
    """`complete`がmodel-gatewayの`/chat/completions`へ論理名付きでリクエストすることを確認する。"""
    base_url = "http://model-gateway.test:4000"
    captured: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = __import__("json").loads(request.content)
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "こんにちは"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    with respx.mock(base_url=base_url) as mock:
        mock.post("/chat/completions").mock(side_effect=_handler)
        client = LogicalModelClient(model_gateway_url=base_url)
        result = await client.complete(
            model="pdm-main",
            messages=[{"role": "user", "content": "こんにちは"}],
        )

    assert captured["url"] == f"{base_url}/chat/completions"
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["model"] == "pdm-main"
    assert payload["messages"] == [{"role": "user", "content": "こんにちは"}]
    assert result.content == "こんにちは"
    assert result.raw["id"] == "chatcmpl-1"


@pytest.mark.asyncio
async def test_complete_with_each_logical_name() -> None:
    """4つの論理名すべてでリクエストが成功することを確認する。"""
    base_url = "http://model-gateway.test:4000"
    with respx.mock(base_url=base_url) as mock:
        mock.post("/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "chatcmpl-2",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "ok"},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )
        client = LogicalModelClient(model_gateway_url=base_url)
        for logical_name in (
            "pdm-main",
            "pdm-teacher",
            "pdm-judge",
            "pdm-embed",
            "pdm-student",
        ):
            result = await client.complete(model=logical_name, messages=[])
            assert result.content == "ok"


@pytest.mark.asyncio
async def test_complete_raises_on_http_error() -> None:
    """ゲートウェイがエラーを返した場合、httpxの例外が伝播することを確認する。"""
    base_url = "http://model-gateway.test:4000"
    with respx.mock(base_url=base_url) as mock:
        mock.post("/chat/completions").mock(return_value=httpx.Response(500))
        client = LogicalModelClient(model_gateway_url=base_url)
        with pytest.raises(httpx.HTTPStatusError):
            await client.complete(model="pdm-main", messages=[{"role": "user", "content": "x"}])


def test_logical_model_name_type_rejects_unknown_literal_at_typecheck() -> None:
    """型注釈`LogicalModelName`が定義済み論理名のみのLiteralであることを確認する(mypy検証は別途CIで担保)。"""
    from agent_core.llm_client import LOGICAL_MODEL_NAMES

    assert LOGICAL_MODEL_NAMES == (
        "pdm-main",
        "pdm-teacher",
        "pdm-judge",
        "pdm-embed",
        "pdm-student",
    )
