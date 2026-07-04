"""フォールバック・リトライ・タイムアウトの動作検証(E4-2, AR-03)。

`litellm.config.yaml` の `router_settings`(fallbacks/num_retries/timeout/
cooldown_time)が実際に機能することを、respxでモックした主バックエンド・
フォールバックバックエンドに対して検証する。
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx
from model_gateway.config import DEFAULT_CONFIG_PATH, load_raw_config
from model_gateway.router import (
    AllBackendsFailedError,
    GatewayRouter,
    RequestTimeoutError,
)


@pytest.fixture
def env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDM_MAIN_MODEL", "anthropic/claude-sonnet-4-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
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


def test_config_defines_fallbacks_retries_timeout_and_cooldown() -> None:
    """litellm.config.yamlのrouter_settingsに必須キーが定義されていることを確認する。"""
    config = load_raw_config(DEFAULT_CONFIG_PATH)
    router_settings = config["router_settings"]

    assert router_settings["num_retries"] >= 1
    assert router_settings["timeout"] > 0
    assert router_settings["cooldown_time"] > 0

    fallbacks = router_settings["fallbacks"]
    assert isinstance(fallbacks, list)
    assert any("pdm-main" in mapping for mapping in fallbacks)
    for mapping in fallbacks:
        for _primary, fallback_list in mapping.items():
            assert isinstance(fallback_list, list)
            assert len(fallback_list) >= 1


def test_router_num_retries_matches_config(router: GatewayRouter) -> None:
    config = load_raw_config(DEFAULT_CONFIG_PATH)
    assert router.num_retries == config["router_settings"]["num_retries"]


@pytest.mark.asyncio
@respx.mock
async def test_primary_backend_is_retried_up_to_configured_count(router: GatewayRouter) -> None:
    """主バックエンドが失敗し続ける場合、`num_retries`回までリトライされることを確認する
    (初回1回 + リトライnum_retries回 = 呼び出し合計 1+num_retries回)。
    """
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(500, json={"error": "internal error"})
    )
    # pdm-mainのフォールバック先(pdm-main-fallback)はBedrock経由となるため、
    # 全経路を失敗させ切ってAllBackendsFailedErrorへ到達させるためにこちらもモックする。
    respx.post("https://bedrock-runtime.amazonaws.com/v1/messages").mock(
        return_value=httpx.Response(500, json={"error": "internal error"})
    )

    with pytest.raises(AllBackendsFailedError):
        await router.completion("pdm-main")

    # api.anthropic.comへの呼び出し回数を見ればpdm-main自体への試行回数
    # (1 + num_retries)を計測できる。
    assert route.call_count == 1 + router.num_retries


@pytest.mark.asyncio
@respx.mock
async def test_primary_failure_falls_back_to_configured_backend(router: GatewayRouter) -> None:
    """主バックエンドが継続的に失敗する場合、fallbacks設定に従い予備バックエンドへ
    リクエストが転送されることを確認する。
    """
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(500, json={"error": "internal error"})
    )
    fallback_route = respx.post("https://bedrock-runtime.amazonaws.com/v1/messages").mock(
        return_value=httpx.Response(200, json={"id": "msg_fallback", "model": "claude-3-5-sonnet"})
    )

    response = await router.completion("pdm-main")

    assert fallback_route.called
    assert response.status_code == 200


@pytest.mark.asyncio
@respx.mock
async def test_request_exceeding_timeout_is_aborted_and_error_propagates(
    router: GatewayRouter,
) -> None:
    """タイムアウト設定値を超えるとリクエストが打ち切られ、エラーが呼び出し元に伝播する。"""

    async def _slow_response(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(router.timeout + 1)
        return httpx.Response(200, json={"id": "too-late"})

    respx.post("https://api.anthropic.com/v1/messages").mock(side_effect=_slow_response)
    respx.post("https://bedrock-runtime.amazonaws.com/v1/messages").mock(side_effect=_slow_response)

    router.timeout = 0.05
    router.num_retries = 0

    with pytest.raises(AllBackendsFailedError) as exc_info:
        await router.completion("pdm-main")

    assert isinstance(exc_info.value.__cause__, RequestTimeoutError)


@pytest.mark.asyncio
@respx.mock
async def test_all_backends_failing_raises_all_backends_failed_error(
    router: GatewayRouter,
) -> None:
    """主バックエンド・フォールバック双方が失敗する場合はAllBackendsFailedErrorとなる。"""
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(500, json={"error": "internal error"})
    )
    respx.post("https://bedrock-runtime.amazonaws.com/v1/messages").mock(
        return_value=httpx.Response(503, json={"error": "unavailable"})
    )

    with pytest.raises(AllBackendsFailedError):
        await router.completion("pdm-main")
