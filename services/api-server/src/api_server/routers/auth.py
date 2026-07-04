"""`POST /auth/login`, `POST /auth/refresh`。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api_server.auth.jwt import InvalidTokenError, create_access_token, decode_access_token
from api_server.auth.password import verify_password
from api_server.auth.totp import verify_totp_code
from api_server.auth.user_store import find_user_by_email
from api_server.config import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str
    totp_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    access_token: str


@router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = find_user_by_email(settings.user_store_path, request.email)
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="認証に失敗しました")

    if settings.totp_enabled and user.totp_secret is not None:
        if request.totp_code is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="TOTPコードが必要です(totp_code)",
            )
        if not verify_totp_code(user.totp_secret, request.totp_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="TOTPコードが不正です"
            )

    token = create_access_token(
        subject=user.id,
        role=user.role,
        secret=settings.jwt_secret,
        expires_minutes=settings.jwt_expires_minutes,
    )
    return TokenResponse(access_token=token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: RefreshRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    try:
        payload = decode_access_token(request.access_token, secret=settings.jwt_secret)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="トークンが無効です"
        ) from exc

    new_token = create_access_token(
        subject=payload["sub"],
        role=payload["role"],
        secret=settings.jwt_secret,
        expires_minutes=settings.jwt_expires_minutes,
    )
    return TokenResponse(access_token=new_token)


__all__ = ["router"]
