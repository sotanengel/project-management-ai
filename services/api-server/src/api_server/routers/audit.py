"""監査ログ検索API(`GET /audit/records`、E7-6)。

`api_server.audit.log`(E3-7)が提供する追記専用JSONL永続化層を、
actor/action/対象kind/期間で検索できるようHTTP経由で公開する
(FR-UI-04: エージェント活動ログ画面からの監査ログ閲覧・検索)。
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api_server.audit.log import AuditRecord, read_records
from api_server.auth.dependencies import get_current_user
from api_server.auth.models import User
from api_server.config import Settings, get_settings

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/records", response_model=list[AuditRecord])
def list_records(
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[User, Depends(get_current_user)],
    actor: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    kind: Annotated[str | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
) -> list[AuditRecord]:
    """監査ログをフィルタ条件で絞り込み、新しい順に返す。"""
    records = read_records(settings.audit_log_path)

    if actor is not None:
        records = [r for r in records if r.actor == actor]
    if action is not None:
        records = [r for r in records if r.action == action]
    if kind is not None:
        records = [r for r in records if r.target_kind == kind]
    if date_from is not None:
        records = [r for r in records if r.timestamp >= date_from]
    if date_to is not None:
        records = [r for r in records if r.timestamp <= date_to]

    return list(reversed(records))


__all__ = ["router"]
