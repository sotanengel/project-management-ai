"""E2-1: JSON Schema v1 共通+基本エンティティの検証テスト。

`packages/pmdf/schemas/pmdf/v1/` 配下の共通定義(common.schema.json)と
基本エンティティ(product/stakeholder/persona/objective/metric)について、
正常フィクスチャが検証を通り、異常フィクスチャが ValidationError を
送出することを確認する。
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

BASIC_KINDS = ["product", "stakeholder", "persona", "objective", "metric"]


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("kind", BASIC_KINDS)
def test_valid_fixture_passes_schema_validation(kind: str) -> None:
    fixture_path = VALID_DIR / f"{kind}_example.yaml"
    assert fixture_path.exists(), f"フィクスチャが存在しません: {fixture_path}"
    data = _load_yaml(fixture_path)
    validate_entity(data)  # ValidationErrorが出なければ成功


@pytest.mark.parametrize(
    "fixture_name,target_kind",
    [
        ("product_missing_required.yaml", "product"),
        ("product_bad_kind.yaml", "product"),
        ("product_unknown_property.yaml", "product"),
        ("stakeholder_wrong_type.yaml", "stakeholder"),
        ("persona_missing_jobs.yaml", "persona"),
        ("objective_bad_period.yaml", "objective"),
        ("metric_bad_id.yaml", "metric"),
    ],
)
def test_invalid_fixture_raises_validation_error(fixture_name: str, target_kind: str) -> None:
    """異常フィクスチャは、意図した種別のスキーマに対して検証エラーとなる。

    `product_bad_kind.yaml` のように `kind` フィールド自体が不正な値である
    ケースも含むため、検証に用いるスキーマは意図した種別を明示的に指定する
    (`kind`フィールドの値からの自動推定はしない)。
    """
    fixture_path = INVALID_DIR / fixture_name
    assert fixture_path.exists(), f"フィクスチャが存在しません: {fixture_path}"
    data = _load_yaml(fixture_path)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        validate_entity(data, kind=target_kind)


def test_unknown_property_without_x_prefix_is_rejected() -> None:
    """additionalProperties:false により `x_` 以外の未知プロパティは拒否される。"""
    data = _load_yaml(VALID_DIR / "product_example.yaml")
    data["totally_unknown_field"] = "should be rejected"
    with pytest.raises(jsonschema.exceptions.ValidationError):
        validate_entity(data)


def test_x_prefixed_extension_field_is_allowed() -> None:
    """`x_` 接頭辞の拡張フィールドはスキーマ制約なしで許可される。"""
    data = _load_yaml(VALID_DIR / "product_example.yaml")
    data["x_arbitrary_extension"] = {"anything": [1, 2, 3]}
    validate_entity(data)  # 例外が出なければ成功


def test_id_pattern_matches_prefixed_ulid() -> None:
    data = _load_yaml(VALID_DIR / "metric_example.yaml")
    import re

    assert re.match(r"^[a-z]+-[0-9A-HJKMNP-TV-Z]{26}$", data["id"])
