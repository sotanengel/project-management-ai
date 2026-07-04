"""Windows環境でのファイルロック対策。

`filelock` ライブラリ(クロスプラットフォーム)を用い、書き込み系操作
(create/update)はリポジトリ単位の排他ロックを取得してから実行する。
同時書き込み要求は直列化され、待機タイムアウトを超えた場合は
`LockTimeoutError` を送出する(呼び出し側が503を返せるようにするため)。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

#: リポジトリ単位の排他ロック取得の既定タイムアウト秒数。
DEFAULT_LOCK_TIMEOUT_SECONDS = 10.0

#: ロックファイル名(リポジトリルート直下に置く)。
LOCK_FILE_NAME = ".pmdf.lock"


class LockTimeoutError(Exception):
    """ロック取得がタイムアウトした場合に送出される例外。"""


@contextmanager
def repo_write_lock(
    repo_path: Path, timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS
) -> Iterator[None]:
    """リポジトリ単位の排他ロックを取得するコンテキストマネージャ。

    Raises:
        LockTimeoutError: `timeout_seconds` 以内にロックを取得できなかった場合。
    """
    lock_path = repo_path / LOCK_FILE_NAME
    file_lock = FileLock(str(lock_path), timeout=timeout_seconds)
    try:
        with file_lock.acquire(timeout=timeout_seconds):
            yield
    except Timeout as exc:
        raise LockTimeoutError(
            f"リポジトリのロック取得がタイムアウトしました({timeout_seconds}秒): {repo_path}"
        ) from exc


__all__ = [
    "DEFAULT_LOCK_TIMEOUT_SECONDS",
    "LOCK_FILE_NAME",
    "FileLock",
    "LockTimeoutError",
    "repo_write_lock",
]
