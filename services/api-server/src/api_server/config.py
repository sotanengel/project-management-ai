"""api-serverの設定値。すべて環境変数のみから読み込む(SEC-01準拠)。

秘密情報(JWT_SECRET等)をコードやデフォルト値にハードコードしないため、
`pydantic-settings` の `BaseSettings` を用いる。必須項目は未設定時に
`pydantic.ValidationError` を送出する(デフォルト値を持たない)。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """環境変数から読み込む設定値。

    `.env` ファイルからの読み込みにも対応するが、CI・本番環境では
    環境変数を直接使うことを想定する(`.env` はローカル開発用途)。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    #: JWT署名用シークレット。秘密情報のためデフォルト値を持たない(必須)。
    jwt_secret: str

    #: pmdf-store(Gitリポジトリ)のルートパス。
    pmdf_store_path: Path

    #: CORS許可オリジン(カンマ区切りの環境変数を想定)。既定は空リスト。
    cors_origins: list[str] = []

    #: JWTアクセストークンの有効期限(分)。
    jwt_expires_minutes: int = 30

    #: TOTP(ワンタイムパスワード)によるログイン追加認証を有効化するか。
    totp_enabled: bool = False

    #: ファイルベースのユーザーストア(JSON/YAML)のパス。
    user_store_path: Path = Path("data/users.json")

    #: 承認プロポーザル(決定前状態)のファイルベースストアのパス。
    proposal_store_path: Path = Path("data/proposals.json")

    #: 監査ログ(JSONL)のパス。
    audit_log_path: Path = Path("data/audit/audit.log.jsonl")

    #: 自律レベル設定ファイルのパス。
    autonomy_config_path: Path = Path("data/autonomy.json")

    #: 緊急停止フラグの状態ファイルのパス。
    emergency_stop_path: Path = Path("data/emergency_stop.json")


@lru_cache
def get_settings() -> Settings:
    """設定値のシングルトンを返す(FastAPIの依存性注入から利用)。"""
    return Settings()  # type: ignore[call-arg]


__all__ = ["Settings", "get_settings"]
