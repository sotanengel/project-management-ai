"""チャットタスクのファイルベース(JSON)ストア(E5-9)。

E3-6の`api_server.approval.proposal_store`と同様、軽量なJSONファイルストア
として実装する(agent-coreのタスクキュー(E5-1)はagent-coreプロセス内の
インメモリ実装のため、UI⇄api-server⇄agent-coreランナー間で共有する
チャットタスクの実行状況はapi-server側でこのストアとして永続化し、
agent-coreランナーは`POST /chat/tasks/{id}/transition`経由でHTTP越しに
状態遷移を報告する)。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from api_server.chat.state_machine import ChatTaskStatus


class ChatTask(BaseModel):
    """チャットタスク1件分の情報。"""

    id: str
    message: str
    product_id: str
    actor: str
    status: ChatTaskStatus = ChatTaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    intent: str | None = None


class ChatTaskRequest(BaseModel):
    """`POST /chat/instructions`のリクエストボディ。"""

    message: str = Field(min_length=1)
    product_id: str


class ChatTaskTransitionRequest(BaseModel):
    """`POST /chat/tasks/{id}/transition`のリクエストボディ。"""

    status: ChatTaskStatus
    result: dict[str, Any] | None = None
    error: str | None = None
    intent: str | None = None


def load_tasks(path: Path) -> list[ChatTask]:
    """JSONファイルからチャットタスク一覧を読み込む。ファイルが存在しない場合は空リスト。"""
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [ChatTask.model_validate(item) for item in raw]


def save_tasks(path: Path, tasks: list[ChatTask]) -> None:
    """チャットタスク一覧をJSONファイルへ書き込む。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [task.model_dump(mode="json") for task in tasks]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def add_task(path: Path, task: ChatTask) -> ChatTask:
    """新規チャットタスクを追加して永続化する。"""
    tasks = load_tasks(path)
    tasks.append(task)
    save_tasks(path, tasks)
    return task


def find_task_by_id(path: Path, task_id: str) -> ChatTask | None:
    """idに一致するチャットタスクを返す(存在しない場合はNone)。"""
    for task in load_tasks(path):
        if task.id == task_id:
            return task
    return None


def update_task(path: Path, updated: ChatTask) -> ChatTask:
    """既存チャットタスクを更新して永続化する。

    Raises:
        KeyError: 対象タスクが存在しない場合。
    """
    tasks = load_tasks(path)
    for index, existing in enumerate(tasks):
        if existing.id == updated.id:
            tasks[index] = updated
            save_tasks(path, tasks)
            return updated
    raise KeyError(f"チャットタスク {updated.id!r} が見つかりません")


__all__ = [
    "ChatTask",
    "ChatTaskRequest",
    "ChatTaskTransitionRequest",
    "add_task",
    "find_task_by_id",
    "load_tasks",
    "save_tasks",
    "update_task",
]
