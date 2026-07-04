"""pyotpによるTOTP(ワンタイムパスワード)生成・検証。

`TOTP_ENABLED`(環境変数、`api_server.config.Settings.totp_enabled`)が
trueの場合のみログインフローに組み込む。
"""

from __future__ import annotations

import pyotp


def generate_totp_secret() -> str:
    """新規ユーザー登録時に用いるBase32シークレットを生成する。"""
    return pyotp.random_base32()


def verify_totp_code(secret: str, code: str) -> bool:
    """TOTPコードがシークレットに対して有効か検証する。"""
    totp = pyotp.TOTP(secret)
    return totp.verify(code)


__all__ = ["generate_totp_secret", "verify_totp_code"]
