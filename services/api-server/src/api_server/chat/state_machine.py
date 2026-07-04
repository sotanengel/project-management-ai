"""チャットタスクのステートマシン(`ChatTaskStatus`、E5-9)。

`pending`(受理) -> `running`(実行中) -> `done`(完了) / `failed`(失敗)
の一方向遷移のみを許可する(E5-1の`TaskQueue`の状態設計と揃える)。
"""

from __future__ import annotations

from enum import StrEnum


class ChatTaskStatus(StrEnum):
    """チャットタスクの状態。"""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class InvalidChatTaskTransitionError(Exception):
    """許可されていない状態遷移が試みられた場合に送出される例外。"""


#: 許可される遷移の集合(from -> 許可されるto の集合)。
_ALLOWED_TRANSITIONS: dict[ChatTaskStatus, frozenset[ChatTaskStatus]] = {
    ChatTaskStatus.PENDING: frozenset({ChatTaskStatus.RUNNING, ChatTaskStatus.FAILED}),
    ChatTaskStatus.RUNNING: frozenset({ChatTaskStatus.DONE, ChatTaskStatus.FAILED}),
    ChatTaskStatus.DONE: frozenset(),
    ChatTaskStatus.FAILED: frozenset(),
}


def transition(current: ChatTaskStatus, target: ChatTaskStatus) -> ChatTaskStatus:
    """`current`から`target`への遷移を検証し、許可されれば`target`を返す。

    Raises:
        InvalidChatTaskTransitionError: 許可されていない遷移の場合
            (`done`/`failed`からの再遷移等)。
    """
    allowed = _ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidChatTaskTransitionError(
            f"{current.value} から {target.value} への遷移は許可されません"
        )
    return target


__all__ = ["ChatTaskStatus", "InvalidChatTaskTransitionError", "transition"]
