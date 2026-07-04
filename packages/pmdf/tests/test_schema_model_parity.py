"""E2-3: Pydanticモデルとスキーマ整合テスト。

`packages/pmdf/src/pmdf/models/` の各Pydanticモデルについて、
`model_json_schema()` が要求する必須フィールド集合と、
`schemas/pmdf/v1/*.schema.json` の必須フィールド集合が一致することを検証する。

方針(AC対応): 今回は全14エンティティで完全一致(集合として同一)を達成できる
ようモデル側のフィールドにdefaultの有無を対応させて設計したため、
`==` による完全一致を基本の検証方式とする。将来、両者が完全一致しない
エンティティが生じた場合は、モデル必須フィールド ⊆ スキーマ必須フィールド
の包含関係チェックに切り替えることを許容する(issue #20 AC参照)。

あわせて、E2-1/E2-2の全正常フィクスチャがPydanticモデルの`model_validate()`
でエラーなくパースできること、異常フィクスチャは`ValidationError`を
送出することを確認する。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pmdf.models import KIND_TO_MODEL
from pmdf.schema_registry import get_validator
from pydantic import ValidationError

FIXTURES_DIR = Path(__file__).parent / "fixtures"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"

ALL_KINDS = [
    "product",
    "stakeholder",
    "persona",
    "objective",
    "metric",
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


def test_kind_to_model_covers_all_14_kinds() -> None:
    assert set(KIND_TO_MODEL.keys()) == set(ALL_KINDS)


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_required_fields_match_between_model_and_schema(kind: str) -> None:
    model = KIND_TO_MODEL[kind]
    model_schema = model.model_json_schema()
    model_required = set(model_schema.get("required", []))

    json_schema_validator = get_validator(kind)
    json_schema_required = set(json_schema_validator.schema.get("required", []))

    assert model_required == json_schema_required, (
        f"[{kind}] モデル必須フィールド {model_required} と "
        f"JSON Schema必須フィールド {json_schema_required} が一致しません"
    )


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_valid_fixture_parses_with_pydantic_model(kind: str) -> None:
    fixture_path = VALID_DIR / f"{kind}_example.yaml"
    data = _load_yaml(fixture_path)
    model = KIND_TO_MODEL[kind]
    instance = model.model_validate(data)
    assert instance.kind == kind


@pytest.mark.parametrize(
    "fixture_name,target_kind",
    [
        ("product_missing_required.yaml", "product"),
        ("stakeholder_wrong_type.yaml", "stakeholder"),
        ("persona_missing_jobs.yaml", "persona"),
        ("objective_bad_period.yaml", "objective"),
        ("metric_bad_id.yaml", "metric"),
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
def test_invalid_fixture_raises_pydantic_validation_error(
    fixture_name: str, target_kind: str
) -> None:
    fixture_path = INVALID_DIR / fixture_name
    data = _load_yaml(fixture_path)
    model = KIND_TO_MODEL[target_kind]
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_x_prefixed_extension_field_is_allowed_on_model() -> None:
    data = _load_yaml(VALID_DIR / "product_example.yaml")
    model = KIND_TO_MODEL["product"]
    instance = model.model_validate(data)
    assert instance.model_extra is not None
    assert "x_notes" in instance.model_extra


def test_non_x_prefixed_unknown_field_is_rejected_on_model() -> None:
    data = _load_yaml(VALID_DIR / "product_example.yaml")
    data["totally_unknown_field"] = "should be rejected"
    model = KIND_TO_MODEL["product"]
    with pytest.raises(ValidationError):
        model.model_validate(data)
