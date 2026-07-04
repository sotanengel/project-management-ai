"""E2-7: バンドルimport検証と差分プレビューのテスト。

スキーマ検証→ID衝突・参照整合チェック→差分プレビュー→適用、の手順を検証する。
"""

from __future__ import annotations

import tarfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from pmdf.bundle.export import ExportScope, export_bundle
from pmdf.bundle.import_ import (
    apply_bundle,
    diff_preview,
    validate_bundle,
)
from pmdf.models import Product, Provenance, Story
from pmdf.models.story import Priority

PROD_A = "prod-01JZXAAAAA01BBBBCCCCDDDDEE"
STORY_A1 = "story-01JZXSASSA01BBBBCCCCDDDDEE"


def _provenance(updated_at: datetime | None = None) -> Provenance:
    return Provenance(
        created_by="user:tester",
        updated_at=updated_at or datetime(2026, 6, 1, tzinfo=UTC),
    )


def _product(product_id: str = PROD_A) -> Product:
    return Product(
        pmdf_version="1.0.0",
        kind="product",
        id=product_id,
        provenance=_provenance(),
        name="Product A",
        vision="vision",
        lifecycle_stage="growth",
    )


def _story(story_id: str, title: str = "title") -> Story:
    return Story(
        pmdf_version="1.0.0",
        kind="story",
        id=story_id,
        provenance=_provenance(),
        product=PROD_A,
        title=title,
        as_a="a",
        i_want="b",
        so_that="c",
        acceptance_criteria=["AC1"],
        priority=Priority(method="RICE"),
        status="ready",
    )


def _make_bundle(tmp_path: Path, entities: list, name: str = "bundle.pmdf.tar.gz") -> Path:
    output = tmp_path / name
    export_bundle(entities, ExportScope(), output, generated_env="test")
    return output


class RecordingStore:
    """`apply_bundle`が受け取るストアProtocolのテスト用モック実装。"""

    def __init__(self) -> None:
        self.saved: list[Any] = []

    def save(self, entity: Any) -> None:
        self.saved.append(entity)


def test_validate_bundle_accepts_well_formed_bundle(tmp_path: Path) -> None:
    bundle_path = _make_bundle(tmp_path, [_product(), _story(STORY_A1)])
    result = validate_bundle(bundle_path)
    assert result.is_valid
    assert result.errors == []
    assert {e.id for e in result.entities} == {PROD_A, STORY_A1}


def test_validate_bundle_rejects_bundle_with_schema_violation(tmp_path: Path) -> None:
    bundle_path = _make_bundle(tmp_path, [_product(), _story(STORY_A1)])

    # tarball内のエンティティYAMLを不正な内容に書き換える(statusのenum違反)。
    _corrupt_entity_yaml(
        bundle_path,
        f"entities/story/{STORY_A1}.yaml",
        replace=("status: ready", "status: not_a_valid_status"),
    )

    result = validate_bundle(bundle_path)
    assert not result.is_valid
    assert len(result.errors) >= 1


def test_diff_preview_detects_new_entities(tmp_path: Path) -> None:
    bundle_path = _make_bundle(tmp_path, [_product(), _story(STORY_A1)])
    diffs = diff_preview(bundle_path, existing_entities=[])
    by_id = {d.id: d for d in diffs}
    assert by_id[STORY_A1].diff_type == "new"
    assert by_id[PROD_A].diff_type == "new"


def test_diff_preview_detects_identical_entities(tmp_path: Path) -> None:
    story = _story(STORY_A1)
    bundle_path = _make_bundle(tmp_path, [story])
    diffs = diff_preview(bundle_path, existing_entities=[story])
    assert diffs[0].diff_type == "identical"


def test_diff_preview_detects_conflict_with_field_level_diff(tmp_path: Path) -> None:
    incoming_story = _story(STORY_A1, title="新タイトル")
    existing_story = _story(STORY_A1, title="旧タイトル")
    bundle_path = _make_bundle(tmp_path, [incoming_story])
    diffs = diff_preview(bundle_path, existing_entities=[existing_story])
    assert diffs[0].diff_type == "conflict"
    assert diffs[0].field_diffs is not None
    assert diffs[0].field_diffs["title"] == ("新タイトル", "旧タイトル")


def test_diff_preview_reports_reference_errors_on_merged_set(tmp_path: Path) -> None:
    """既存+バンドルの合併集合に対しvalidate_referencesが実行される。"""
    from pmdf.models.roadmap_item import RoadmapItem

    roadmap_item = RoadmapItem(
        pmdf_version="1.0.0",
        kind="roadmap_item",
        id="roadmap-01JZXRARAR01BBBBCCCCDDDDEE",
        provenance=_provenance(),
        theme="theme",
        period="2026-Q3",
        status="planned",
        objective="obj-ZZZZZZZZZZZZZZZZZZZZZZZZZZ",  # 存在しない参照
    )
    bundle_path = _make_bundle(tmp_path, [roadmap_item])
    diffs = diff_preview(bundle_path, existing_entities=[])
    target = next(d for d in diffs if d.id == roadmap_item.id)
    assert len(target.reference_errors) == 1
    assert target.reference_errors[0].reason == "missing"


def test_apply_bundle_dry_run_does_not_call_store(tmp_path: Path) -> None:
    bundle_path = _make_bundle(tmp_path, [_story(STORY_A1)])
    store = RecordingStore()
    result = apply_bundle(bundle_path, resolutions={}, store=store, dry_run=True)
    assert result.dry_run is True
    assert store.saved == []
    assert STORY_A1 in result.applied_ids


def test_apply_bundle_real_run_calls_store_for_new_and_incoming(tmp_path: Path) -> None:
    bundle_path = _make_bundle(tmp_path, [_story(STORY_A1)])
    store = RecordingStore()
    result = apply_bundle(bundle_path, resolutions={}, store=store, dry_run=False)
    assert result.dry_run is False
    assert [e.id for e in store.saved] == [STORY_A1]
    assert STORY_A1 in result.applied_ids


def test_apply_bundle_existing_resolution_skips_store_write(tmp_path: Path) -> None:
    incoming_story = _story(STORY_A1, title="新タイトル")
    bundle_path = _make_bundle(tmp_path, [incoming_story])
    store = RecordingStore()
    result = apply_bundle(
        bundle_path,
        resolutions={STORY_A1: "existing"},
        store=store,
        dry_run=False,
    )
    assert store.saved == []
    assert STORY_A1 in result.skipped_ids
    assert STORY_A1 not in result.applied_ids


def _corrupt_entity_yaml(bundle_path: Path, member_name: str, replace: tuple[str, str]) -> None:
    """テスト用にtarball内の1エンティティYAMLの内容を書き換える。"""
    with tarfile.open(bundle_path, "r:gz") as tar:
        members: dict[str, bytes] = {}
        for m in tar.getmembers():
            if not m.isfile():
                continue
            extracted = tar.extractfile(m)
            assert extracted is not None
            members[m.name] = extracted.read()

    old, new = replace
    original = members[member_name].decode("utf-8")
    assert old in original, f"{old!r} が元のYAMLに見つかりません"
    members[member_name] = original.replace(old, new).encode("utf-8")

    with tarfile.open(bundle_path, "w:gz") as tar:
        for name, content in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(info, BytesIO(content))
