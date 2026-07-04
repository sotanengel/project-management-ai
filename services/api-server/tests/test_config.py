"""api_server.config: 環境変数のみから設定値を読むことを保証するテスト(SEC-01)。"""

from __future__ import annotations

import pytest


def test_settings_loads_from_env_vars(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from api_server.config import Settings

    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path))

    settings = Settings()  # type: ignore[call-arg]

    assert settings.jwt_secret == "test-secret"
    assert settings.pmdf_store_path == tmp_path


def test_settings_missing_required_env_var_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from api_server.config import Settings
    from pydantic import ValidationError

    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("PMDF_STORE_PATH", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_has_no_hardcoded_secret_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """秘密情報系フィールドにハードコードされたデフォルト値が無いことを確認する。"""
    from api_server.config import Settings

    monkeypatch.setenv("JWT_SECRET", "another-secret")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path))
    settings = Settings()  # type: ignore[call-arg]

    # フィールド定義上、デフォルト値が無い(=必須)ことを型情報から確認する。
    assert Settings.model_fields["jwt_secret"].is_required()
    assert settings.jwt_secret == "another-secret"


def test_settings_cors_origins_default(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from api_server.config import Settings

    monkeypatch.setenv("JWT_SECRET", "s")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path))
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    settings = Settings()  # type: ignore[call-arg]
    assert settings.cors_origins == []
