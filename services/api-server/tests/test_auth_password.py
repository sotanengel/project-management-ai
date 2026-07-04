"""パスワードハッシュ化・検証のテスト(argon2)。"""

from __future__ import annotations


def test_hash_password_does_not_return_plaintext() -> None:
    from api_server.auth.password import hash_password

    hashed = hash_password("correct horse battery staple")

    assert hashed != "correct horse battery staple"
    assert hashed.startswith("$argon2")


def test_verify_password_succeeds_for_correct_password() -> None:
    from api_server.auth.password import hash_password, verify_password

    hashed = hash_password("s3cret!")
    assert verify_password("s3cret!", hashed) is True


def test_verify_password_fails_for_incorrect_password() -> None:
    from api_server.auth.password import hash_password, verify_password

    hashed = hash_password("s3cret!")
    assert verify_password("wrong-password", hashed) is False
