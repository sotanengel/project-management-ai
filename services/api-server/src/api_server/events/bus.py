"""アプリ内pub/subイベントバス(FR-UI-11)。

承認キュー件数変化(`approval.count_changed`)、PMDFエンティティ変更
(`pmdf.entity_changed`)、エージェント活動(`agent.activity`)を
WebSocket経由でUIへリアルタイム配信するための配信基盤。

単一プロセス構成を前提とした`asyncio.Queue`ベースのシンプルな実装
(`InMemoryEventBus`)を提供する。将来的な複数レプリカ構成では
Redis pub/sub等の実装に差し替え可能なよう、`EventBus` Protocolとして
インターフェースを定義する。
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, TypedDict


class Event(TypedDict):
    """バス上を流れるイベント1件の形式。"""

    type: str
    data: dict[str, Any]


#: 1購読者分のイベントキュー。
Subscription = "asyncio.Queue[Event]"


class EventBus(Protocol):
    """イベントバスが満たすべきプロトコル(将来のRedis実装差し替え等に備える)。"""

    def subscribe(self) -> asyncio.Queue[Event]: ...

    def unsubscribe(self, subscription: asyncio.Queue[Event]) -> None: ...

    async def publish(self, event_type: str, data: dict[str, Any]) -> None: ...


class InMemoryEventBus:
    """単一プロセス構成向けの`asyncio.Queue`ベースイベントバス実装。"""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Event]] = []

    def subscribe(self) -> asyncio.Queue[Event]:
        """新規購読者用のキューを作成し、配信対象に登録する。"""
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, subscription: asyncio.Queue[Event]) -> None:
        """購読を解除する(WebSocket切断時等に呼び出す)。"""
        if subscription in self._subscribers:
            self._subscribers.remove(subscription)

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """全購読者のキューへイベントを配信する。"""
        event: Event = {"type": event_type, "data": data}
        for queue in list(self._subscribers):
            await queue.put(event)


#: プロセス全体で共有する既定のイベントバスインスタンス。
_default_bus = InMemoryEventBus()


def get_event_bus() -> InMemoryEventBus:
    """FastAPIの依存性注入・書込系エンドポイントから利用する共有イベントバスを返す。"""
    return _default_bus


__all__ = ["Event", "EventBus", "InMemoryEventBus", "get_event_bus"]
