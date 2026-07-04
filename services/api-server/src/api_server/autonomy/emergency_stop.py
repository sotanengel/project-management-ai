"""緊急停止(エージェントの全自律動作の即時停止、FR-AU-05/AR-06)。

グローバルな`emergency_stopped`フラグをJSONファイルで永続化する。
エージェント実行系エンドポイント(L1業務実行APIを含む)には
`check_not_stopped`依存関数を付与し、停止中は409を返す。PMDF CRUDや
UI向け閲覧・手動編集APIには付与しない(AR-06: エージェント非依存で
UI・PMDFは稼働し続ける)。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, status

from api_server.config import Settings, get_settings


def is_stopped(state_path: Path) -> bool:
    """現在緊急停止中かどうかを返す。状態ファイルが存在しない場合は`False`(通常稼働)。"""
    if not state_path.exists():
        return False
    data = json.loads(state_path.read_text(encoding="utf-8"))
    return bool(data.get("emergency_stopped", False))


def stop(state_path: Path) -> None:
    """緊急停止を発動する(`emergency_stopped=True`を永続化する)。"""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"emergency_stopped": True}, ensure_ascii=False), encoding="utf-8"
    )


def release(state_path: Path) -> None:
    """緊急停止を解除する(`emergency_stopped=False`を永続化する)。"""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"emergency_stopped": False}, ensure_ascii=False), encoding="utf-8"
    )


def check_not_stopped(settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """FastAPI依存関数: 緊急停止中であれば409を送出する。

    エージェント実行系エンドポイント(L1業務実行API等)にのみ付与すること。
    PMDF CRUDやUI向け閲覧・手動編集APIには付与しない(AR-06)。
    """
    if is_stopped(settings.emergency_stop_path):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="緊急停止中のため、エージェントの自律動作は実行できません(FR-AU-05)。",
        )


__all__ = ["check_not_stopped", "is_stopped", "release", "stop"]
