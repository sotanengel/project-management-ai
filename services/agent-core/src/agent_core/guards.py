"""緊急停止照会(FR-AU-05)。

LangGraphの各ノード実行前に、api-serverの
`GET /autonomy/emergency-stop/status` を照会し、停止中であれば
`EmergencyStopError`を送出してグラフ実行を即座に中断する共通ノード
ラッパーを提供する。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx


class EmergencyStopError(RuntimeError):
    """緊急停止中に検出された場合に送出される例外。"""

    def __init__(self) -> None:
        super().__init__("緊急停止が発動中のため、エージェントの自律動作を中断しました(FR-AU-05)。")


async def check_emergency_stop(
    *, api_server_url: str, auth_token: str, timeout: float = 10.0
) -> None:
    """api-serverへ緊急停止状態を照会し、停止中なら`EmergencyStopError`を送出する。"""
    base_url = api_server_url.rstrip("/")
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(
            f"{base_url}/autonomy/emergency-stop/status",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        response.raise_for_status()
        body = response.json()

    if bool(body.get("emergency_stopped", False)):
        raise EmergencyStopError()


async def run_node_with_guard[StateT](
    node: Callable[[StateT], Awaitable[StateT]],
    state: StateT,
    *,
    api_server_url: str,
    auth_token: str,
) -> StateT:
    """`node`の実行前に緊急停止を照会し、停止中でなければ`node(state)`を実行する。

    LangGraphのノードをラップする共通関数。各業務グラフはノード登録時に
    `functools.partial(run_node_with_guard, actual_node, ...)`のような形で
    利用することを想定する。
    """
    await check_emergency_stop(api_server_url=api_server_url, auth_token=auth_token)
    return await node(state)


__all__ = ["EmergencyStopError", "check_emergency_stop", "run_node_with_guard"]
