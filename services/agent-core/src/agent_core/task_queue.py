"""エージェントタスクの登録・取得・状態管理を行うタスクキュー(E5-1)。

初期実装はプロセス内(`asyncio.Queue`によるFIFOディスパッチ+
辞書によるインデックス)だが、状態遷移・永続化はインターフェースとして
独立させてあり、将来の複数ワーカー化(外部キューへの差し替え)に
備える。`persist_path`を指定した場合、状態変化のたびにJSON Lines形式で
追記し、次回起動時に最新状態を復元できる(単純な追記専用ログの
再生方式)。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Task:
    id: str
    kind: str
    payload: dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


class TaskQueue:
    """タスクの登録・状態管理・FIFOディスパッチを行うインメモリキュー。"""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._tasks: dict[str, Task] = {}
        self._queue: asyncio.Queue[Task] = asyncio.Queue()
        self._persist_path = persist_path
        if persist_path is not None and persist_path.exists():
            self._load()

    def _load(self) -> None:
        assert self._persist_path is not None
        for line in self._persist_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            task = Task(
                id=data["id"],
                kind=data["kind"],
                payload=data["payload"],
                status=TaskStatus(data["status"]),
                result=data.get("result"),
                error=data.get("error"),
            )
            # 最新状態のみ保持(同一idの複数行は最後の行が正)。
            self._tasks[task.id] = task

    def _persist(self, task: Task) -> None:
        if self._persist_path is None:
            return
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        with self._persist_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(task.to_dict(), ensure_ascii=False) + "\n")

    async def submit(self, *, kind: str, payload: dict[str, Any]) -> Task:
        """新規タスクを`pending`状態で登録し、ディスパッチキューへ投入する。"""
        task = Task(id=f"task-{uuid.uuid4()}", kind=kind, payload=payload)
        self._tasks[task.id] = task
        self._persist(task)
        await self._queue.put(task)
        return task

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    async def dequeue(self) -> Task:
        """FIFO順でタスクを取り出す(ワーカーループからの呼び出しを想定)。"""
        return await self._queue.get()

    def mark_running(self, task_id: str) -> Task:
        return self._transition(task_id, TaskStatus.RUNNING)

    def mark_done(self, task_id: str, *, result: dict[str, Any] | None = None) -> Task:
        return self._transition(task_id, TaskStatus.DONE, result=result)

    def mark_failed(self, task_id: str, *, error: str) -> Task:
        return self._transition(task_id, TaskStatus.FAILED, error=error)

    def _transition(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> Task:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"タスクが見つかりません: {task_id}")
        task.status = status
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error
        self._persist(task)
        return task


__all__ = ["Task", "TaskQueue", "TaskStatus"]
