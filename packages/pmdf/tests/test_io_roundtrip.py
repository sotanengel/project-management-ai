"""E2-4: YAML⇄JSON無損失変換とファイルI/Oのプロパティベーステスト。

- `dict_to_yaml -> yaml_to_dict -> dict_to_yaml` の冪等性(2回目以降の
  YAML文字列が変化しないこと)
- `model_dump(mode="json") -> model_validate` の往復でデータが完全一致すること
- `save_entity` で書き出したファイルを `load_entity` で読み戻すと元の
  Pydanticモデルと等価(`==`)になること

をhypothesisのプロパティベーステストで検証する。
"""

from __future__ import annotations

from pathlib import Path

from helpers.strategies import ENTITY_STRATEGIES, any_entity_strategy
from hypothesis import HealthCheck, given, settings
from pmdf.io import dict_to_yaml, load_entity, save_entity, yaml_to_dict
from pmdf.models.common import PmdfBase

_SETTINGS = settings(max_examples=25, suppress_health_check=[HealthCheck.too_slow])


@given(entity=any_entity_strategy())
@_SETTINGS
def test_yaml_roundtrip_is_idempotent(entity: PmdfBase) -> None:
    data = entity.model_dump(mode="json")
    yaml_text_1 = dict_to_yaml(data)
    parsed = yaml_to_dict(yaml_text_1)
    yaml_text_2 = dict_to_yaml(parsed)
    assert yaml_text_1 == yaml_text_2


@given(entity=any_entity_strategy())
@_SETTINGS
def test_json_roundtrip_preserves_data(entity: PmdfBase) -> None:
    model_cls = type(entity)
    dumped = entity.model_dump(mode="json")
    restored = model_cls.model_validate(dumped)
    assert restored == entity
    assert restored.model_dump(mode="json") == dumped


@given(entity=any_entity_strategy())
@_SETTINGS
def test_save_then_load_entity_is_equivalent(entity: PmdfBase, tmp_path_factory) -> None:  # type: ignore[no-untyped-def]
    base_dir = Path(tmp_path_factory.mktemp("pmdf_store"))
    path = save_entity(entity, base_dir)
    assert path.exists()
    loaded = load_entity(path)
    assert loaded == entity


def test_key_order_places_common_fields_first() -> None:
    data = {
        "acceptance_criteria": ["a"],
        "kind": "story",
        "id": "story-01JZX4T8G2K9V6R5N4M3P2Q1R0",
        "pmdf_version": "1.0.0",
        "provenance": {"created_by": "user:x", "updated_at": "2026-01-01T00:00:00Z"},
    }
    text = dict_to_yaml(data)
    lines = [line for line in text.splitlines() if line and not line.startswith(" ")]
    keys_in_order = [line.split(":")[0] for line in lines]
    assert keys_in_order.index("pmdf_version") < keys_in_order.index("kind")
    assert keys_in_order.index("kind") < keys_in_order.index("id")
    assert keys_in_order.index("id") < keys_in_order.index("provenance")


@given(entity=ENTITY_STRATEGIES["story"])
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_save_entity_uses_kind_id_directory_convention(entity: PmdfBase, tmp_path: Path) -> None:
    path = save_entity(entity, tmp_path)
    assert path == tmp_path / "story" / f"{entity.id}.yaml"
