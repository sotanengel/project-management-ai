"""認証・認可で用いるモデル群(`User`、ロール定義)。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

#: `admin`(管理者、全権限)、`editor`(編集者、PMDF CRUD可・承認不可)、
#: `viewer`(閲覧者、読み取りのみ)。
Role = Literal["admin", "editor", "viewer"]

#: 書込(作成・更新)が許可されるロール。
WRITE_ROLES: frozenset[Role] = frozenset({"admin", "editor"})


class User(BaseModel):
    """ファイルベースのユーザーストアに保存される1ユーザー分の情報。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    email: str
    password_hash: str
    role: Role
    totp_secret: str | None = None
    #: `None`は全プロダクトアクセス可(管理者/編集者向け)。viewerには通常
    #: 特定プロダクトIDのリストを設定する(E3-5)。
    product_scopes: list[str] | None = None


__all__ = ["WRITE_ROLES", "Role", "User"]
