"""WebSocketイベント配信(`WS /ws/events`、FR-UI-11)。

承認キュー件数変化・PMDFエンティティ変更・エージェント活動をリアルタイムに
配信する。認証は接続時のクエリパラメータ`token`(JWT)で行い、無効・
未提供の場合は接続を拒否する(WebSocketクローズコード1008: Policy
Violation)。
"""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from api_server.auth.jwt import InvalidTokenError, decode_access_token
from api_server.auth.user_store import find_user_by_id
from api_server.config import get_settings
from api_server.events.bus import get_event_bus

router = APIRouter(tags=["ws"])

#: 認証拒否時のWebSocketクローズコード(1008: Policy Violation)。
_POLICY_VIOLATION_CLOSE_CODE = 1008


def _authenticate(token: str | None) -> bool:
    """`token`が有効なJWTであり、対応するユーザーが存在するか検証する。"""
    if token is None:
        return False
    settings = get_settings()
    try:
        payload = decode_access_token(token, secret=settings.jwt_secret)
    except InvalidTokenError:
        return False
    user_id = payload.get("sub")
    if user_id is None:
        return False
    return find_user_by_id(settings.user_store_path, user_id) is not None


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    if not _authenticate(token):
        await websocket.close(code=_POLICY_VIOLATION_CLOSE_CODE)
        return

    await websocket.accept()
    bus = get_event_bus()
    subscription = bus.subscribe()
    try:
        while True:
            event = await subscription.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(subscription)


__all__ = ["router"]
