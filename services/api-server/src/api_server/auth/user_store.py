"""ファイルベース(JSON)のユーザーストア。

初期実装として、`Settings.user_store_path` が指すJSONファイルに
ユーザー一覧を保持する。将来的にDB等へ差し替え可能なよう、
読み込み専用の単純な関数群として実装する。
"""

from __future__ import annotations

import json
from pathlib import Path

from api_server.auth.models import User


def load_users(path: Path) -> list[User]:
    """JSONファイルからユーザー一覧を読み込む。ファイルが存在しない場合は空リスト。"""
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [User.model_validate(item) for item in raw]


def find_user_by_email(path: Path, email: str) -> User | None:
    """emailに一致するユーザーを返す(存在しない場合はNone)。"""
    for user in load_users(path):
        if user.email == email:
            return user
    return None


def save_users(path: Path, users: list[User]) -> None:
    """ユーザー一覧をJSONファイルへ書き込む(管理者API等から利用)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [user.model_dump(mode="json") for user in users]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = ["find_user_by_email", "load_users", "save_users"]
