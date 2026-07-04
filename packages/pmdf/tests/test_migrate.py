"""E2-9: PMDFスキーマバージョン マイグレーション枠組のテスト。"""

from __future__ import annotations

import pytest
from pmdf.migrate import MIGRATIONS, MigrationNotFoundError, migrate_entity, register_migration


def test_dummy_migration_1_0_0_to_1_1_0_is_registered() -> None:
    assert ("1.0.0", "1.1.0") in MIGRATIONS


def test_migrate_entity_applies_dummy_migration_and_updates_version() -> None:
    data = {"pmdf_version": "1.0.0", "kind": "story", "id": "story-x"}
    migrated = migrate_entity(data, "1.1.0")
    assert migrated["pmdf_version"] == "1.1.0"
    assert migrated["x_migrated"] is True
    # 元データは変更されない
    assert data["pmdf_version"] == "1.0.0"
    assert "x_migrated" not in data


def test_migrate_entity_same_version_is_noop() -> None:
    data = {"pmdf_version": "1.1.0", "kind": "story", "id": "story-x"}
    migrated = migrate_entity(data, "1.1.0")
    assert migrated == data


def test_migrate_entity_raises_for_undefined_version_pair() -> None:
    data = {"pmdf_version": "1.0.0", "kind": "story", "id": "story-x"}
    with pytest.raises(MigrationNotFoundError):
        migrate_entity(data, "9.9.9")


def test_register_migration_enables_chained_migration() -> None:
    """複数ホップの変換関数チェーンが順に適用される(1.1.0→1.2.0を一時登録して検証)。"""

    def _bump(data: dict) -> dict:
        result = dict(data)
        result["x_bumped"] = True
        return result

    register_migration("1.1.0", "1.2.0", _bump)
    try:
        data = {"pmdf_version": "1.0.0", "kind": "story", "id": "story-x"}
        migrated = migrate_entity(data, "1.2.0")
        assert migrated["pmdf_version"] == "1.2.0"
        assert migrated["x_migrated"] is True
        assert migrated["x_bumped"] is True
    finally:
        del MIGRATIONS[("1.1.0", "1.2.0")]
