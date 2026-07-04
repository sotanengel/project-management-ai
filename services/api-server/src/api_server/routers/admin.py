"""管理者専用API: ユーザー管理(`POST /admin/users`, `PUT /admin/users/{id}/scopes`)。

E3-5(プロダクトスコープ認可)の一部。`admin`ロールのみ利用可能。
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api_server.auth.dependencies import require_role
from api_server.auth.models import Role, User
from api_server.auth.password import hash_password
from api_server.auth.user_store import add_user, update_user_scopes
from api_server.config import Settings, get_settings

router = APIRouter(prefix="/admin", tags=["admin"])


class CreateUserRequest(BaseModel):
    email: str
    password: str
    role: Role
    totp_secret: str | None = None
    product_scopes: list[str] | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    role: Role
    product_scopes: list[str] | None = None


class UpdateScopesRequest(BaseModel):
    product_scopes: list[str] | None


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def create_user(
    request: CreateUserRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _admin: Annotated[User, Depends(require_role("admin"))],
) -> UserResponse:
    user = User(
        id=f"user-{uuid.uuid4()}",
        email=request.email,
        password_hash=hash_password(request.password),
        role=request.role,
        totp_secret=request.totp_secret,
        product_scopes=request.product_scopes,
    )
    try:
        add_user(settings.user_store_path, user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserResponse(
        id=user.id, email=user.email, role=user.role, product_scopes=user.product_scopes
    )


@router.put("/users/{user_id}/scopes", response_model=UserResponse)
def update_scopes(
    user_id: str,
    request: UpdateScopesRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _admin: Annotated[User, Depends(require_role("admin"))],
) -> UserResponse:
    try:
        updated = update_user_scopes(settings.user_store_path, user_id, request.product_scopes)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return UserResponse(
        id=updated.id,
        email=updated.email,
        role=updated.role,
        product_scopes=updated.product_scopes,
    )


__all__ = ["router"]
