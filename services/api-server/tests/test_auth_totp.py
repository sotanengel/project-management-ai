"""TOTP検証のテスト(pyotp)。"""

from __future__ import annotations


def test_generate_secret_returns_base32_string() -> None:
    from api_server.auth.totp import generate_totp_secret

    secret = generate_totp_secret()
    assert isinstance(secret, str)
    assert len(secret) >= 16


def test_verify_totp_code_accepts_valid_current_code() -> None:
    import pyotp
    from api_server.auth.totp import generate_totp_secret, verify_totp_code

    secret = generate_totp_secret()
    current_code = pyotp.TOTP(secret).now()

    assert verify_totp_code(secret, current_code) is True


def test_verify_totp_code_rejects_invalid_code() -> None:
    from api_server.auth.totp import generate_totp_secret, verify_totp_code

    secret = generate_totp_secret()

    assert verify_totp_code(secret, "000000") is False
