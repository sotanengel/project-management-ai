"""アプリ全体で共有する依存性注入ヘルパー(pmdf-storeインスタンス等)。"""

from __future__ import annotations

from functools import lru_cache

from api_server.config import Settings, get_settings
from api_server.pmdf_store.store import PmdfStore


@lru_cache
def _cached_store(repo_path: str) -> PmdfStore:
    return PmdfStore(repo_path)  # type: ignore[arg-type]


def get_pmdf_store(settings: Settings | None = None) -> PmdfStore:
    """設定値のpmdf_store_pathからPmdfStoreインスタンスを取得する(パス単位でキャッシュ)。

    リポジトリが未初期化の場合は`PmdfStore.init`で初期化してから返す。
    """
    settings = settings or get_settings()
    repo_path = settings.pmdf_store_path
    if not (repo_path / ".git").exists():
        PmdfStore.init(repo_path)
    return _cached_store(str(repo_path))


def get_pmdf_store_dependency() -> PmdfStore:
    """FastAPIの`Depends`から呼び出すためのラッパー。"""
    return get_pmdf_store()


def reset_store_cache() -> None:
    """テスト間でのキャッシュ汚染を避けるためのキャッシュクリア。"""
    _cached_store.cache_clear()


__all__ = ["get_pmdf_store", "get_pmdf_store_dependency", "reset_store_cache"]
