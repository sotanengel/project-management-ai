"""動作確認用のダミーマイグレーション(1.0.0 → 1.1.0)。

マイグレーション機構(レジストリ+チェーン適用)が実際に動くことを示す
ためだけのダミー実装。将来追加想定の`x_migrated`フラグを付与するだけの
変換を行う(実際のフィールド追加・破壊的変更はまだ発生していないため)。
"""

from __future__ import annotations

from typing import Any


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    """1.0.0のエンティティデータに`x_migrated: true`を付与する。"""
    result = dict(data)
    result["x_migrated"] = True
    return result


__all__ = ["migrate"]
