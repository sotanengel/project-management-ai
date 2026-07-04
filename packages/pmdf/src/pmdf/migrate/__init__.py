"""PMDFスキーマバージョン改訂に備えたマイグレーションツール枠組(NFR-09)。

`MIGRATIONS`は`(from_version, to_version) -> 変換関数`のレジストリであり、
`migrate_entity`は現在バージョンから目標バージョンまでの変換関数チェーンを
探索・適用する。
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Any

from pmdf.migrate import v1_0_0_to_v1_1_0

MigrationFunc = Callable[[dict[str, Any]], dict[str, Any]]

#: `(from_version, to_version)` をキーとする変換関数レジストリ。
MIGRATIONS: dict[tuple[str, str], MigrationFunc] = {}


class MigrationNotFoundError(Exception):
    """現在バージョンから目標バージョンへの変換経路が見つからない場合に送出。"""


def register_migration(from_version: str, to_version: str, func: MigrationFunc) -> None:
    """`from_version` → `to_version` の変換関数をレジストリに登録する。"""
    MIGRATIONS[(from_version, to_version)] = func


def _find_migration_path(current_version: str, target_version: str) -> list[str]:
    """登録済みマイグレーションのグラフを幅優先探索し、バージョン経路を求める。"""
    if current_version == target_version:
        return [current_version]

    graph: dict[str, list[str]] = {}
    for from_v, to_v in MIGRATIONS:
        graph.setdefault(from_v, []).append(to_v)

    queue: deque[list[str]] = deque([[current_version]])
    visited = {current_version}
    while queue:
        path = queue.popleft()
        last = path[-1]
        for next_version in graph.get(last, []):
            if next_version == target_version:
                return [*path, next_version]
            if next_version not in visited:
                visited.add(next_version)
                queue.append([*path, next_version])

    raise MigrationNotFoundError(
        f"{current_version!r} から {target_version!r} への変換経路が登録されていません"
    )


def migrate_entity(data: dict[str, Any], target_version: str) -> dict[str, Any]:
    """`data`(`pmdf_version`を含むエンティティdict)を`target_version`まで変換する。

    現在バージョンと目標バージョンが同一の場合は入力をそのまま返す
    (コピーもしない。呼び出し側で変更しないことが前提)。

    Raises:
        MigrationNotFoundError: 変換経路が登録されていない場合。
    """
    current_version = data.get("pmdf_version")
    if not isinstance(current_version, str):
        raise MigrationNotFoundError("dataに文字列型の'pmdf_version'がありません")

    if current_version == target_version:
        return data

    path = _find_migration_path(current_version, target_version)

    result = data
    for from_v, to_v in zip(path, path[1:], strict=False):
        func = MIGRATIONS[(from_v, to_v)]
        result = func(result)
        result = dict(result)
        result["pmdf_version"] = to_v
    return result


# 動作確認用のダミーマイグレーションを登録する。
register_migration("1.0.0", "1.1.0", v1_0_0_to_v1_1_0.migrate)


__all__ = [
    "MIGRATIONS",
    "MigrationFunc",
    "MigrationNotFoundError",
    "migrate_entity",
    "register_migration",
]
