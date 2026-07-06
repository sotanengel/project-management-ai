"""月次予算超過時の学習ジョブ自動停止フラグ(E9-2, FR-OP-01)。

`emergency_stop`と同様のJSONファイル永続化パターン。予算消化率100%到達時に
`learning_blocked=True`を設定し、schedulerの`trigger_learning_loop`が
実行前チェックでジョブをスキップする。
"""

from __future__ import annotations

import json
from pathlib import Path


def is_learning_blocked(state_path: Path) -> bool:
    if not state_path.exists():
        return False
    data = json.loads(state_path.read_text(encoding="utf-8"))
    return bool(data.get("learning_blocked", False))


def set_learning_blocked(state_path: Path, *, blocked: bool) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"learning_blocked": blocked}, ensure_ascii=False),
        encoding="utf-8",
    )


__all__ = ["is_learning_blocked", "set_learning_blocked"]
