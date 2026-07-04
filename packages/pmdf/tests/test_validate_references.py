"""E2-5: エンティティ間参照整合チェック(`validate_references`)のテスト。

参照フィールドの定義は各Pydanticモデルのフィールドメタデータ
(`json_schema_extra={"ref_kind": ...}`)から動的に収集する設計であり、
ハードコードした参照リストを持たない。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pmdf.models import KeyResult, Objective, Provenance, RoadmapItem, Story
from pmdf.models.story import Priority, StoryLinks
from pmdf.validate import validate_references


def _provenance() -> Provenance:
    return Provenance(created_by="user:tester", updated_at=datetime.now(UTC))


OBJ_ID = "obj-01JZX0KKKK01BBBBCCCCDDDDEF"
ROADMAP_ID = "roadmap-01JZX1RRRR01BBBBCCCCDDDDEF"
STORY_ID = "story-01JZX4T8G2K9V6R5N4M3P2Q1R0"


def _objective(obj_id: str = OBJ_ID) -> Objective:
    return Objective(
        pmdf_version="1.0.0",
        kind="objective",
        id=obj_id,
        provenance=_provenance(),
        objective="目標",
        key_results=[KeyResult(description="KR1", target_value=1.0)],
        period="2026-Q3",
    )


def _roadmap_item(objective_ref: str) -> RoadmapItem:
    return RoadmapItem(
        pmdf_version="1.0.0",
        kind="roadmap_item",
        id=ROADMAP_ID,
        provenance=_provenance(),
        theme="テーマ",
        period="2026-Q3",
        status="planned",
        objective=objective_ref,
    )


def _story(objective_ref: str | None) -> Story:
    return Story(
        pmdf_version="1.0.0",
        kind="story",
        id=STORY_ID,
        provenance=_provenance(),
        title="タイトル",
        as_a="誰か",
        i_want="したい",
        so_that="ため",
        acceptance_criteria=["AC1"],
        priority=Priority(method="RICE"),
        status="ready",
        links=StoryLinks(objective=objective_ref) if objective_ref else None,
    )


def test_no_errors_when_all_references_resolve() -> None:
    objective = _objective()
    roadmap_item = _roadmap_item(objective.id)
    story = _story(objective.id)
    errors = validate_references([objective, roadmap_item, story])
    assert errors == []


def test_missing_reference_is_detected() -> None:
    roadmap_item = _roadmap_item("obj-ZZZZZZZZZZZZZZZZZZZZZZZZZZ")
    errors = validate_references([roadmap_item])
    assert len(errors) == 1
    assert errors[0].reason == "missing"
    assert errors[0].field_path == "objective"
    assert errors[0].entity_id == ROADMAP_ID


def test_kind_mismatch_is_detected_when_reference_points_to_wrong_kind() -> None:
    """objective参照にstory idを指定した場合、種別不一致として検出される。"""
    story = _story(None)
    roadmap_item = _roadmap_item(story.id)  # objectiveのはずがstoryを指している
    errors = validate_references([story, roadmap_item])
    assert len(errors) == 1
    assert errors[0].reason == "kind_mismatch"
    assert errors[0].expected_kind == "objective"
    assert errors[0].actual_kind == "story"


def test_nested_links_field_is_collected_dynamically() -> None:
    """Story.links.objective(ネストしたサブモデル内)の参照も動的に収集される。"""
    story = _story("obj-ZZZZZZZZZZZZZZZZZZZZZZZZZZ")
    errors = validate_references([story])
    assert len(errors) == 1
    assert errors[0].field_path == "links.objective"


def test_no_reference_fields_yields_no_errors_for_unrelated_entities() -> None:
    objective = _objective()
    errors = validate_references([objective])
    assert errors == []


@pytest.mark.parametrize("field_path_substr", ["objective"])
def test_error_repr_contains_useful_context(field_path_substr: str) -> None:
    roadmap_item = _roadmap_item("obj-ZZZZZZZZZZZZZZZZZZZZZZZZZZ")
    errors = validate_references([roadmap_item])
    message = str(errors[0])
    assert field_path_substr in message
    assert ROADMAP_ID in message
