"""argon2-cffiによるパスワードハッシュ化・検証。"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """平文パスワードをargon2ハッシュへ変換する。"""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """平文パスワードがハッシュと一致するか検証する(例外を握りつぶしbool化)。"""
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


__all__ = ["hash_password", "verify_password"]
