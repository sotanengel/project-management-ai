"""緊急停止照会(`agent_core.guards`)のテスト(E5-1、FR-AU-05)。"""

from __future__ import annotations

import httpx
import pytest
import respx
from agent_core.guards import EmergencyStopError, check_emergency_stop


@pytest.mark.asyncio
async def test_check_emergency_stop_passes_when_not_stopped() -> None:
    base_url = "http://api-server.test:8000"
    with respx.mock(base_url=base_url) as mock:
        mock.get("/autonomy/emergency-stop/status").mock(
            return_value=httpx.Response(200, json={"emergency_stopped": False})
        )
        # 例外が送出されなければ成功。
        await check_emergency_stop(api_server_url=base_url, auth_token="tok")


@pytest.mark.asyncio
async def test_check_emergency_stop_raises_when_stopped() -> None:
    base_url = "http://api-server.test:8000"
    with respx.mock(base_url=base_url) as mock:
        mock.get("/autonomy/emergency-stop/status").mock(
            return_value=httpx.Response(200, json={"emergency_stopped": True})
        )
        with pytest.raises(EmergencyStopError):
            await check_emergency_stop(api_server_url=base_url, auth_token="tok")


@pytest.mark.asyncio
async def test_check_emergency_stop_sends_auth_header() -> None:
    base_url = "http://api-server.test:8000"
    captured: dict[str, str] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={"emergency_stopped": False})

    with respx.mock(base_url=base_url) as mock:
        mock.get("/autonomy/emergency-stop/status").mock(side_effect=_handler)
        await check_emergency_stop(api_server_url=base_url, auth_token="secret-token")

    assert captured["authorization"] == "Bearer secret-token"


@pytest.mark.asyncio
async def test_run_node_with_guard_interrupts_graph_when_stopped() -> None:
    """グラフの各ノード実行前ラッパーが停止中に後続ノードを実行しないことを確認する統合テスト。"""
    from agent_core.guards import run_node_with_guard

    base_url = "http://api-server.test:8000"
    calls: list[str] = []

    async def llm_call_node(state: dict[str, object]) -> dict[str, object]:
        calls.append("llm_call")
        return {**state, "done": True}

    empty_state: dict[str, object] = {}

    with respx.mock(base_url=base_url) as mock:
        mock.get("/autonomy/emergency-stop/status").mock(
            return_value=httpx.Response(200, json={"emergency_stopped": True})
        )
        with pytest.raises(EmergencyStopError):
            await run_node_with_guard(
                llm_call_node,
                state=empty_state,
                api_server_url=base_url,
                auth_token="tok",
            )

    assert calls == []


@pytest.mark.asyncio
async def test_run_node_with_guard_executes_node_when_not_stopped() -> None:
    from agent_core.guards import run_node_with_guard

    base_url = "http://api-server.test:8000"

    async def node(state: dict[str, object]) -> dict[str, object]:
        return {**state, "executed": True}

    initial_state: dict[str, object] = {"a": 1}

    with respx.mock(base_url=base_url) as mock:
        mock.get("/autonomy/emergency-stop/status").mock(
            return_value=httpx.Response(200, json={"emergency_stopped": False})
        )
        result = await run_node_with_guard(
            node, state=initial_state, api_server_url=base_url, auth_token="tok"
        )

    assert result == {"a": 1, "executed": True}
