"""E2-2: JSON Schema v1 実行系エンティティの検証テスト。

roadmap_item/story/experiment/decision/release/risk/initiative/report/
approval の9種について、正常フィクスチャが検証を通り、異常フィクスチャが
ValidationError を送出することを確認する。要件定義書§6.2のstory記述例が
そのまま(必須フィールド補完の上)検証を通ることも確認する。
"""

from __future__ import annotations

from pathlib import Path

import jsonschema
import pytest
import yaml
from pmdf.schema_registry import validate_entity

FIXTURES_DIR = Path(__file__).parent / "fixtures"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"

EXECUTION_KINDS = [
    "roadmap_item",
    "story",
    "experiment",
    "decision",
    "release",
    "risk",
    "initiative",
    "report",
    "approval",
]


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("kind", EXECUTION_KINDS)
def test_valid_fixture_passes_schema_validation(kind: str) -> None:
    fixture_path = VALID_DIR / f"{kind}_example.yaml"
    assert fixture_path.exists(), f"フィクスチャが存在しません: {fixture_path}"
    data = _load_yaml(fixture_path)
    validate_entity(data)


def test_story_example_from_requirements_doc_section_6_2() -> None:
    """要件定義書§6.2のstory記述例(RICE優先度・statusを含む)が検証を通る。"""
    data = _load_yaml(VALID_DIR / "story_example.yaml")
    assert data["title"] == "ゲスト購入でも注文履歴をメールから参照できる"
    assert data["priority"] == {
        "method": "RICE",
        "reach": 4200,
        "impact": 2,
        "confidence": 0.8,
        "effort": 3,
        "score": 2240,
    }
    assert data["status"] == "ready"
    validate_entity(data)


@pytest.mark.parametrize(
    "fixture_name,target_kind",
    [
        ("roadmap_item_missing_objective.yaml", "roadmap_item"),
        ("story_missing_acceptance_criteria.yaml", "story"),
        ("experiment_bad_status.yaml", "experiment"),
        ("decision_missing_rejected_reasons.yaml", "decision"),
        ("release_bad_go_no_go.yaml", "release"),
        ("risk_score_out_of_range.yaml", "risk"),
        ("initiative_bad_approach.yaml", "initiative"),
        ("report_missing_decisions_needed.yaml", "report"),
        ("approval_missing_reason.yaml", "approval"),
    ],
)
def test_invalid_fixture_raises_validation_error(fixture_name: str, target_kind: str) -> None:
    fixture_path = INVALID_DIR / fixture_name
    assert fixture_path.exists(), f"フィクスチャが存在しません: {fixture_path}"
    data = _load_yaml(fixture_path)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        validate_entity(data, kind=target_kind)


def test_decision_schema_requires_background_options_rationale_rejected_reasons() -> None:
    """decisionスキーマは背景/選択肢/根拠/却下理由に対応するフィールドが必須。"""
    from pmdf.schema_registry import get_validator

    validator = get_validator("decision")
    required = set(validator.schema["required"])
    assert {"background", "options", "rationale", "rejected_reasons"} <= required
