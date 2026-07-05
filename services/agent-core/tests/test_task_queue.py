"""タスクキュー(`agent_core.task_queue`)の単体テスト(E5-1)。"""

from __future__ import annotations

import json

import pytest
from agent_core.task_queue import TaskQueue, TaskStatus


@pytest.mark.asyncio
async def test_submit_then_get_returns_pending_task() -> None:
    queue = TaskQueue()
    task = await queue.submit(kind="backlog", payload={"text": "新機能の要望"})
    assert task.status == TaskStatus.PENDING
    assert task.kind == "backlog"

    fetched = queue.get(task.id)
    assert fetched is not None
    assert fetched.id == task.id


@pytest.mark.asyncio
async def test_state_transitions_pending_running_done() -> None:
    queue = TaskQueue()
    task = await queue.submit(kind="backlog", payload={})

    queue.mark_running(task.id)
    running = queue.get(task.id)
    assert running is not None
    assert running.status == TaskStatus.RUNNING

    queue.mark_done(task.id, result={"story_id": "story-01"})
    updated = queue.get(task.id)
    assert updated is not None
    assert updated.status == TaskStatus.DONE
    assert updated.result == {"story_id": "story-01"}


@pytest.mark.asyncio
async def test_state_transition_to_failed_records_error() -> None:
    queue = TaskQueue()
    task = await queue.submit(kind="backlog", payload={})

    queue.mark_running(task.id)
    queue.mark_failed(task.id, error="LLM呼び出し失敗")

    updated = queue.get(task.id)
    assert updated is not None
    assert updated.status == TaskStatus.FAILED
    assert updated.error == "LLM呼び出し失敗"


@pytest.mark.asyncio
async def test_dequeue_returns_tasks_in_fifo_order() -> None:
    queue = TaskQueue()
    first = await queue.submit(kind="backlog", payload={"n": 1})
    second = await queue.submit(kind="backlog", payload={"n": 2})

    dequeued_first = await queue.dequeue()
    dequeued_second = await queue.dequeue()

    assert dequeued_first.id == first.id
    assert dequeued_second.id == second.id


def test_get_unknown_task_returns_none() -> None:
    queue = TaskQueue()
    assert queue.get("task-does-not-exist") is None


def test_mark_running_on_unknown_task_raises() -> None:
    queue = TaskQueue()
    with pytest.raises(KeyError):
        queue.mark_running("task-does-not-exist")


@pytest.mark.asyncio
async def test_persist_and_load_round_trips_tasks(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """ファイル永続化: 状態をJSON Linesへ書き出し、別インスタンスから復元できることを確認する。"""
    persist_path = tmp_path / "tasks.jsonl"
    queue = TaskQueue(persist_path=persist_path)
    task = await queue.submit(kind="backlog", payload={"text": "x"})
    queue.mark_running(task.id)
    queue.mark_done(task.id, result={"ok": True})

    assert persist_path.exists()
    lines = persist_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    last_record = json.loads(lines[-1])
    assert last_record["id"] == task.id

    reloaded = TaskQueue(persist_path=persist_path)
    reloaded_task = reloaded.get(task.id)
    assert reloaded_task is not None
    assert reloaded_task.status == TaskStatus.DONE
    assert reloaded_task.result == {"ok": True}
