"""JWT発行・検証のテスト。"""

from __future__ import annotations

import pytest


def test_create_and_decode_access_token_round_trip() -> None:
    from api_server.auth.jwt import create_access_token, decode_access_token

    token = create_access_token(
        subject="user-1", role="editor", secret="test-secret", expires_minutes=30
    )
    payload = decode_access_token(token, secret="test-secret")

    assert payload["sub"] == "user-1"
    assert payload["role"] == "editor"


def test_decode_access_token_with_wrong_secret_raises() -> None:
    from api_server.auth.jwt import InvalidTokenError, create_access_token, decode_access_token

    token = create_access_token(
        subject="user-1", role="editor", secret="correct-secret", expires_minutes=30
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, secret="wrong-secret")


def test_decode_expired_token_raises() -> None:
    from api_server.auth.jwt import InvalidTokenError, create_access_token, decode_access_token

    token = create_access_token(
        subject="user-1", role="editor", secret="test-secret", expires_minutes=-1
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, secret="test-secret")
