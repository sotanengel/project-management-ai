"""論理名→実バックエンドへのルーティング検証(E4-1)。

respxでAnthropic/OpenAI/Ollama互換バックエンドをモックし、`GatewayRouter`が
`litellm.config.yaml`の定義通りに各論理名(pdm-main/pdm-teacher/pdm-judge/
pdm-embed)を実バックエンドへルーティングすることを確認する。
"""

from __future__ import annotations

import httpx
import pytest
import respx
from model_gateway.config import DEFAULT_CONFIG_PATH
from model_gateway.router import GatewayRouter


@pytest.fixture
def env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDM_MAIN_MODEL", "anthropic/claude-sonnet-4-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("PDM_MAIN_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("PDM_MAIN_LOCAL_MODEL", "ollama/qwen2.5:7b-instruct-q4_K_M")
    monkeypatch.setenv("PDM_MAIN_LOCAL_API_BASE", "http://ollama:11434")
    monkeypatch.setenv("PDM_MAIN_FALLBACK_MODEL", "bedrock/anthropic.claude-3-5-sonnet")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-aws-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-aws-secret")
    monkeypatch.setenv("AWS_REGION", "ap-northeast-1")
    monkeypatch.setenv("PDM_TEACHER_MODEL", "anthropic/claude-opus-4")
    monkeypatch.setenv("PDM_JUDGE_MODEL", "openai/gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("PDM_EMBED_MODEL", "openai/text-embedding-3-large")


@pytest.fixture
def router(env_vars: None) -> GatewayRouter:
    return GatewayRouter.from_yaml(DEFAULT_CONFIG_PATH)


@pytest.mark.asyncio
@respx.mock
async def test_pdm_main_routes_to_anthropic_backend(router: GatewayRouter) -> None:
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json={"id": "msg_1", "model": "claude-sonnet-4-5"})
    )

    response = await router.completion("pdm-main")

    assert route.called
    assert response.status_code == 200
    sent_body = route.calls[0].request.content
    assert b"claude-sonnet-4-5" in sent_body
    assert route.calls[0].request.headers["x-api-key"] == "test-anthropic-key"


@pytest.mark.asyncio
@respx.mock
async def test_pdm_main_local_routes_to_ollama_backend(router: GatewayRouter) -> None:
    """.env切替のローカルOllamaエントリ(pdm-main-local)が正しいAPIベースへルーティングされる。"""
    route = respx.post("http://ollama:11434/v1/messages").mock(
        return_value=httpx.Response(200, json={"id": "msg_local", "model": "qwen2.5"})
    )

    response = await router.completion("pdm-main-local")

    assert route.called
    assert response.status_code == 200


@pytest.mark.asyncio
@respx.mock
async def test_pdm_teacher_routes_to_anthropic_backend(router: GatewayRouter) -> None:
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json={"id": "msg_2", "model": "claude-opus-4"})
    )

    response = await router.completion("pdm-teacher")

    assert route.called
    assert response.status_code == 200
    assert b"claude-opus-4" in route.calls[0].request.content


@pytest.mark.asyncio
@respx.mock
async def test_pdm_judge_routes_to_openai_backend(router: GatewayRouter) -> None:
    route = respx.post("https://api.openai.com/v1/messages").mock(
        return_value=httpx.Response(200, json={"id": "msg_3", "model": "gpt-4o"})
    )

    response = await router.completion("pdm-judge")

    assert route.called
    assert response.status_code == 200
    assert route.calls[0].request.headers["x-api-key"] == "test-openai-key"


@pytest.mark.asyncio
@respx.mock
async def test_pdm_embed_routes_to_openai_backend(router: GatewayRouter) -> None:
    route = respx.post("https://api.openai.com/v1/messages").mock(
        return_value=httpx.Response(200, json={"id": "msg_4", "model": "text-embedding-3-large"})
    )

    response = await router.completion("pdm-embed")

    assert route.called
    assert response.status_code == 200
    assert route.calls[0].request.headers["x-api-key"] == "test-openai-key"


@pytest.mark.asyncio
@respx.mock
async def test_unknown_logical_name_raises(router: GatewayRouter) -> None:
    from model_gateway.router import AllBackendsFailedError

    with pytest.raises(AllBackendsFailedError):
        await router.completion("pdm-not-defined")
