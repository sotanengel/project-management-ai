"""FastAPI依存性注入: 認証済みユーザー取得・ロール/プロダクトスコープ認可。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from api_server.auth.jwt import InvalidTokenError, decode_access_token
from api_server.auth.models import Role, User
from api_server.auth.user_store import load_users
from api_server.config import Settings, get_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """JWTを検証し、対応する`User`を返す。未認証・無効トークンは401。"""
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(token, secret=settings.jwt_secret)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="トークンが無効です",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = payload.get("sub")
    users = load_users(settings.user_store_path)
    for user in users:
        if user.id == user_id:
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="ユーザーが見つかりません",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_role(*roles: Role) -> Callable[[User], User]:
    """指定ロールのいずれかを持つユーザーのみ許可する依存関数を生成する。"""

    def _dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"この操作には次のいずれかのロールが必要です: {', '.join(roles)}",
            )
        return user

    return _dependency


def require_product_scope(product_id: str | None) -> Callable[[User], User]:
    """ユーザーの`product_scopes`が対象プロダクトを含むか検証する依存関数を生成する。

    `product_scopes`が`None`のユーザー(既定: 管理者/編集者)は全プロダクトへ
    アクセス可能。`product_id`が`None`(プロダクト非依存のエンティティ)の
    場合はスコープチェックを行わない。
    """

    def _dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        check_product_scope(user, product_id)
        return user

    return _dependency


def check_product_scope(user: User, product_id: str | None) -> None:
    """`user`が`product_id`にアクセス可能か検証し、不可なら403を送出する。

    エンティティ取得後(store.getの後)など、ルートハンドラ内で対象の
    プロダクトIDが判明した時点で呼び出す用途を想定する
    (`require_product_scope`はパスパラメータから直接product_idが
    得られる場合向けの依存関数版)。

    - `product_id`が`None`(プロダクト非依存のエンティティ、または
      対象kindに`product`フィールドが無い場合)はチェックしない。
    - `user.product_scopes`が`None`(既定: 管理者/編集者)は全プロダクトへ
      アクセス可能。
    """
    if product_id is None:
        return
    if user.product_scopes is None:
        return
    if product_id not in user.product_scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"プロダクト {product_id!r} へのアクセス権がありません",
        )


__all__ = [
    "check_product_scope",
    "get_current_user",
    "oauth2_scheme",
    "require_product_scope",
    "require_role",
]
