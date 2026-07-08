"""学習状況API(E8-8関連)。

`GET /learning/status`(admin/editor/viewer): 自己学習ループ(SFT/DPO/評価ゲート)
の直近ジョブ状況と評価ゲート(promote/reject)履歴を返す。学習実績が無い場合は
`has_activity: false` の空状態を返す(trainer/eval-runnerが未実行の環境でも
UIが破綻しないようにするため)。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api_server.auth.dependencies import require_role
from api_server.auth.models import User
from api_server.config import Settings, get_settings
from api_server.learning.status_store import LearningStatusRecord, summarize_learning_status

router = APIRouter(prefix="/learning", tags=["learning"])


class LearningStatusResponse(BaseModel):
    has_activity: bool
    latest_job: LearningStatusRecord | None = None
    gate_history: list[LearningStatusRecord] = Field(default_factory=list)


@router.get("/status", response_model=LearningStatusResponse)
def get_learning_status(
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[User, Depends(require_role("admin", "editor", "viewer"))],
) -> LearningStatusResponse:
    """自己学習ループの直近ジョブ状況・評価ゲート履歴を返す(閲覧はviewer以上)。"""
    summary = summarize_learning_status(settings.learning_status_path)
    return LearningStatusResponse(
        has_activity=summary.latest_job is not None,
        latest_job=summary.latest_job,
        gate_history=summary.gate_history,
    )


__all__ = ["router"]
