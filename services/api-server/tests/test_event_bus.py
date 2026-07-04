"""アプリ内イベントバス(`api_server.events.bus`)のテスト(E3-10)。"""

from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_subscriber_receives_published_event() -> None:
    from api_server.events.bus import InMemoryEventBus

    bus = InMemoryEventBus()
    subscription = bus.subscribe()

    await bus.publish("pmdf.entity_changed", {"kind": "story", "id": "story-1"})

    event = await asyncio.wait_for(subscription.get(), timeout=1.0)
    assert event["type"] == "pmdf.entity_changed"
    assert event["data"] == {"kind": "story", "id": "story-1"}


@pytest.mark.asyncio
async def test_multiple_subscribers_each_receive_event() -> None:
    from api_server.events.bus import InMemoryEventBus

    bus = InMemoryEventBus()
    sub1 = bus.subscribe()
    sub2 = bus.subscribe()

    await bus.publish("approval.count_changed", {"count": 3})

    event1 = await asyncio.wait_for(sub1.get(), timeout=1.0)
    event2 = await asyncio.wait_for(sub2.get(), timeout=1.0)
    assert event1["type"] == "approval.count_changed"
    assert event2["type"] == "approval.count_changed"


@pytest.mark.asyncio
async def test_unsubscribe_stops_receiving_events() -> None:
    from api_server.events.bus import InMemoryEventBus

    bus = InMemoryEventBus()
    subscription = bus.subscribe()
    bus.unsubscribe(subscription)

    await bus.publish("agent.activity", {"action": "noop"})

    assert subscription.empty()
