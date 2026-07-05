"""チャット指示インターフェースAPI(E5-9、FR-UI-07バックエンド)。

UIから自然文の指示を受け付け(`POST /chat/instructions`)、対応する業務
グラフの起動をagent-coreランナーへ委ねるためのタスクとして登録する。
実際のLLMによる意図分類・業務グラフディスパッチはagent-core
(`agent_core.chat.handle_chat_instruction`)側の責務であり、api-serverは
タスクの受付・状態永続化・状態遷移のWebSocket配信のみを担う
(agent-coreランナーは`POST /chat/tasks/{id}/transition`経由でHTTP越しに
実行状況を報告する)。
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api_server.auth.dependencies import get_current_user, require_role
from api_server.auth.models import User
from api_server.chat.state_machine import InvalidChatTaskTransitionError, transition
from api_server.chat.task_store import (
    ChatTask,
    ChatTaskRequest,
    ChatTaskTransitionRequest,
    add_task,
    find_task_by_id,
    load_tasks,
    update_task,
)
from api_server.config import Settings, get_settings
from api_server.events.bus import InMemoryEventBus, get_event_bus

router = APIRouter(prefix="/chat", tags=["chat"])


async def _publish_activity(bus: InMemoryEventBus, task: ChatTask) -> None:
    """チャットタスクの状態変化をWebSocket購読者へ配信する(FR-UI-11、`agent.activity`)。"""
    await bus.publish(
        "agent.activity",
        {
            "task_id": task.id,
            "status": task.status.value,
            "product_id": task.product_id,
            "intent": task.intent,
        },
    )


@router.post("/instructions", status_code=status.HTTP_201_CREATED, response_model=ChatTask)
async def post_instructions(
    request: ChatTaskRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_role("admin", "editor"))],
    bus: Annotated[InMemoryEventBus, Depends(get_event_bus)],
) -> ChatTask:
    """自然文の指示を受け付け、`pending`状態のチャットタスクとして登録する。"""
    task = ChatTask(
        id=f"chat-task-{uuid.uuid4()}",
        message=request.message,
        product_id=request.product_id,
        actor=f"user:{user.id}",
    )
    add_task(settings.chat_task_store_path, task)
    await _publish_activity(bus, task)
    return task


@router.get("/tasks", response_model=list[ChatTask])
def list_tasks(
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[User, Depends(get_current_user)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[ChatTask]:
    """チャットタスク一覧を新しい順に返す(E7-6のエージェント活動ログ画面向け)。"""
    tasks = load_tasks(settings.chat_task_store_path)
    if status_filter is not None:
        tasks = [t for t in tasks if t.status.value == status_filter]
    return list(reversed(tasks))


@router.get("/tasks/{task_id}", response_model=ChatTask)
def get_task(
    task_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[User, Depends(get_current_user)],
) -> ChatTask:
    """チャットタスクの現在の実行状況を返す。"""
    task = find_task_by_id(settings.chat_task_store_path, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"チャットタスク {task_id!r} が見つかりません",
        )
    return task


@router.post("/tasks/{task_id}/transition", response_model=ChatTask)
async def transition_task(
    task_id: str,
    request: ChatTaskTransitionRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[User, Depends(require_role("admin", "editor"))],
    bus: Annotated[InMemoryEventBus, Depends(get_event_bus)],
) -> ChatTask:
    """agent-coreランナーからのタスク状態遷移報告を受け付ける(受理/実行中/完了/失敗)。

    `running`/`done`/`failed`への遷移のみを許可し(`pending`は
    `post_instructions`でのみ設定される)、不正な遷移は409を返す。
    """
    task = find_task_by_id(settings.chat_task_store_path, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"チャットタスク {task_id!r} が見つかりません",
        )

    try:
        target_status = transition(task.status, request.status)
    except InvalidChatTaskTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    updated = task.model_copy(
        update={
            "status": target_status,
            "result": request.result if request.result is not None else task.result,
            "error": request.error if request.error is not None else task.error,
            "intent": request.intent if request.intent is not None else task.intent,
        }
    )
    update_task(settings.chat_task_store_path, updated)
    await _publish_activity(bus, updated)
    return updated


__all__ = ["router"]
