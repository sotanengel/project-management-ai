"""E2-8: 共有プロファイルサニタイズのテスト。"""

from __future__ import annotations

import tarfile
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pmdf.bundle.export import ExportScope, export_bundle
from pmdf.models import Provenance, Stakeholder, Story
from pmdf.models.stakeholder import ContactPolicy
from pmdf.models.story import Priority
from pmdf.sanitize import (
    REDACTED_VALUE,
    SanitizeProfile,
    load_sanitize_profile,
    sanitize_entity,
)

DEFAULT_PROFILE_PATH = (
    Path(__file__).parent.parent / "config" / "sanitize_profiles" / "default.yaml"
)


def _provenance() -> Provenance:
    return Provenance(created_by="user:tanaka-taro", updated_at=datetime(2026, 6, 1, tzinfo=UTC))


def _story() -> Story:
    return Story(
        pmdf_version="1.0.0",
        kind="story",
        id="story-01JZXSASSA01BBBBCCCCDDDDEE",
        provenance=_provenance(),
        title="タイトル",
        as_a="a",
        i_want="b",
        so_that="c",
        acceptance_criteria=["AC1"],
        priority=Priority(
            method="RICE", reach=4200, impact=2, confidence=0.8, effort=3, score=2240
        ),
        status="ready",
    )


def _stakeholder() -> Stakeholder:
    return Stakeholder(
        pmdf_version="1.0.0",
        kind="stakeholder",
        id="stakeholder-01JZX0SSSS01BBBBCCCCDDDDEF",
        provenance=_provenance(),
        name="山田太郎",
        role="営業部長",
        influence="high",
        contact_policy=ContactPolicy(personal_name="山田太郎", channel="email"),
    )


def test_load_default_profile() -> None:
    profile = load_sanitize_profile(DEFAULT_PROFILE_PATH)
    assert profile.profile == "partner-share-default"
    kinds = {rule.kind for rule in profile.mask_fields}
    assert {"story", "metric", "stakeholder"} <= kinds


def test_sanitize_entity_masks_specified_fields_only() -> None:
    profile = load_sanitize_profile(DEFAULT_PROFILE_PATH)
    story = _story()
    data = story.model_dump(mode="json")
    sanitized = sanitize_entity(data, profile)

    assert sanitized["priority"]["reach"] == REDACTED_VALUE
    assert sanitized["provenance"]["created_by"] == REDACTED_VALUE
    # マスク対象外のフィールドは変化しない
    assert sanitized["title"] == story.title
    assert sanitized["priority"]["impact"] == story.priority.impact
    assert sanitized["status"] == story.status


def test_sanitize_entity_does_not_mutate_original() -> None:
    profile = load_sanitize_profile(DEFAULT_PROFILE_PATH)
    story = _story()
    data = story.model_dump(mode="json")
    original_reach = data["priority"]["reach"]
    sanitize_entity(data, profile)
    assert data["priority"]["reach"] == original_reach


def test_sanitize_entity_masks_nested_stakeholder_field() -> None:
    profile = load_sanitize_profile(DEFAULT_PROFILE_PATH)
    stakeholder = _stakeholder()
    data = stakeholder.model_dump(mode="json")
    sanitized = sanitize_entity(data, profile)
    assert sanitized["name"] == REDACTED_VALUE
    assert sanitized["contact_policy"]["personal_name"] == REDACTED_VALUE
    assert sanitized["contact_policy"]["channel"] == "email"


def test_export_bundle_with_sanitize_profile_masks_before_writing(tmp_path: Path) -> None:
    profile = load_sanitize_profile(DEFAULT_PROFILE_PATH)
    story = _story()
    stakeholder = _stakeholder()
    output = tmp_path / "sanitized.pmdf.tar.gz"
    export_bundle(
        [story, stakeholder],
        ExportScope(),
        output,
        sanitize_profile=profile,
    )

    with tarfile.open(output, "r:gz") as tar:
        member = tar.extractfile(f"entities/story/{story.id}.yaml")
        assert member is not None
        story_yaml_text = member.read().decode("utf-8")
        stakeholder_member = tar.extractfile(f"entities/stakeholder/{stakeholder.id}.yaml")
        assert stakeholder_member is not None
        stakeholder_yaml_text = stakeholder_member.read().decode("utf-8")

    # AC-08相当: 個人名・内部コスト(reach)・作成者情報が平文で含まれない
    assert "tanaka-taro" not in story_yaml_text
    assert "4200" not in story_yaml_text
    assert "山田太郎" not in stakeholder_yaml_text

    story_data = yaml.safe_load(story_yaml_text)
    assert story_data["priority"]["reach"] == REDACTED_VALUE


def test_sanitize_profile_model_rejects_unknown_fields() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SanitizeProfile.model_validate({"profile": "x", "mask_fields": [], "unknown": 1})
