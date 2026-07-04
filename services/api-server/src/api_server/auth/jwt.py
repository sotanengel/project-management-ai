"""PyJWTによるアクセストークンの発行・検証。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt as _pyjwt

ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    """トークンの署名不正・期限切れ等、検証に失敗した場合に送出される例外。"""


def create_access_token(*, subject: str, role: str, secret: str, expires_minutes: int) -> str:
    """アクセストークン(JWT)を発行する。"""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return _pyjwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, *, secret: str) -> dict[str, Any]:
    """アクセストークンを検証・デコードする。

    Raises:
        InvalidTokenError: 署名不正・期限切れ等、検証に失敗した場合。
    """
    try:
        return _pyjwt.decode(token, secret, algorithms=[ALGORITHM])
    except _pyjwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc


__all__ = ["ALGORITHM", "InvalidTokenError", "create_access_token", "decode_access_token"]
