"""自律レベル設定API(`GET /autonomy`, `PUT /autonomy/{product_id}/{business_function}`)と
緊急停止API(`POST /autonomy/emergency-stop`, `POST /autonomy/emergency-stop/release`)。

いずれも管理者(`admin`)のみ実行可能(E3-4の`require_role`を利用)。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api_server.audit.log import AuditRecord, append_record, latest_hash
from api_server.auth.dependencies import get_current_user, require_role
from api_server.auth.models import User
from api_server.autonomy.config import (
    AutonomyConfig,
    AutonomyLevel,
    list_all,
    set_level,
)
from api_server.autonomy.emergency_stop import is_stopped, release, stop
from api_server.config import Settings, get_settings

router = APIRouter(prefix="/autonomy", tags=["autonomy"])


class SetLevelRequest(BaseModel):
    level: AutonomyLevel


class EmergencyStopResponse(BaseModel):
    emergency_stopped: bool


@router.get("", response_model=list[AutonomyConfig])
def get_autonomy_levels(
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[User, Depends(require_role("admin", "editor", "viewer"))],
) -> list[AutonomyConfig]:
    return list_all(settings.autonomy_config_path)


@router.put("/{product_id}/{business_function}", response_model=AutonomyConfig)
def set_autonomy_level(
    product_id: str,
    business_function: str,
    request: SetLevelRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_role("admin"))],
) -> AutonomyConfig:
    try:
        updated = set_level(
            settings.autonomy_config_path,
            product_id=product_id,
            business_function=business_function,
            level=request.level,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    audit_record = AuditRecord.create(
        actor=f"user:{user.id}",
        action="autonomy.level.set",
        target_kind="autonomy_config",
        target_id=f"{product_id}:{business_function}",
        detail={"level": request.level},
        prev_hash=latest_hash(settings.audit_log_path),
    )
    append_record(audit_record, settings.audit_log_path)
    return updated


@router.get("/emergency-stop/status", response_model=EmergencyStopResponse)
def get_emergency_stop_status(
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[User, Depends(get_current_user)],
) -> EmergencyStopResponse:
    """緊急停止状態の照会(E5-1: agent-coreが毎ステップ照会する読み取り専用API)。

    トリガー・解除(admin専用)とは異なり、認証済みであればロールを
    問わず参照できる(agent-coreのサービスアカウントがeditor/admin
    いずれであっても照会できるようにするため)。
    """
    return EmergencyStopResponse(emergency_stopped=is_stopped(settings.emergency_stop_path))


@router.post("/emergency-stop", response_model=EmergencyStopResponse)
def trigger_emergency_stop(
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_role("admin"))],
) -> EmergencyStopResponse:
    stop(settings.emergency_stop_path)

    audit_record = AuditRecord.create(
        actor=f"user:{user.id}",
        action="autonomy.emergency_stop.trigger",
        target_kind="emergency_stop",
        target_id="global",
        detail={},
        prev_hash=latest_hash(settings.audit_log_path),
    )
    append_record(audit_record, settings.audit_log_path)
    return EmergencyStopResponse(emergency_stopped=True)


@router.post("/emergency-stop/release", response_model=EmergencyStopResponse)
def release_emergency_stop(
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_role("admin"))],
) -> EmergencyStopResponse:
    release(settings.emergency_stop_path)

    audit_record = AuditRecord.create(
        actor=f"user:{user.id}",
        action="autonomy.emergency_stop.release",
        target_kind="emergency_stop",
        target_id="global",
        detail={},
        prev_hash=latest_hash(settings.audit_log_path),
    )
    append_record(audit_record, settings.audit_log_path)
    return EmergencyStopResponse(emergency_stopped=is_stopped(settings.emergency_stop_path))


__all__ = ["router"]
