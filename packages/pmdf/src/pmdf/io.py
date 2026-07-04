"""YAML(リポジトリ内表現)⇄ JSON(API入出力表現)の無損失相互変換とファイルI/O。

- リポジトリ内はYAML、API入出力はJSONを既定とし、両者は無損失で相互変換可能
  であること(要件定義書§6.1)。
- 1エンティティ(1ストーリー、1決定記録など)を1ファイルとする規約
  (`<kind>/<id>.yaml`)を実装する。
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.scalarfloat import ScalarFloat
from ruamel.yaml.scalarint import ScalarInt

from pmdf.models import KIND_TO_MODEL
from pmdf.models.common import PmdfBase

#: diffの可読性を高めるため、この順序のキーを先頭に固定する。
#: 残りのキーは元の(挿入)順序を保つ(pydanticのmodel_dumpはフィールド宣言順で
#: 決定的に出力するため、安定した冪等な並び替えになる)。
KEY_ORDER: tuple[str, ...] = (
    "pmdf_version",
    "kind",
    "id",
    "product",
    "provenance",
    "attachments",
)

#: 1エンティティ1ファイル規約: `<base_dir>/<kind>/<id>.yaml`
ENTITY_FILE_SUFFIX = ".yaml"


def _make_yaml() -> YAML:
    """round-tripモード(コメント・キー順序・改行を保持)のYAMLインスタンスを生成する。"""
    yaml = YAML(typ="rt")
    yaml.default_flow_style = False
    yaml.preserve_quotes = True
    yaml.width = 4096  # 長い文字列の折り返しによる非決定的な差分を避ける
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def _reorder_keys(data: dict[str, Any]) -> dict[str, Any]:
    """diffの可読性を高めるため、KEY_ORDERのキーを先頭に並べ替えた新しいdictを返す。

    残りのキーは入力dictにおける相対順序を保つ。この並び替えは冪等
    (既に並び替え済みのdictに再適用しても同じ結果になる)。
    """
    ordered: dict[str, Any] = {}
    for key in KEY_ORDER:
        if key in data:
            ordered[key] = data[key]
    for key, value in data.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def yaml_to_dict(text: str) -> dict[str, Any]:
    """YAML文字列をdict(ruamelのCommentedMap)に変換する。"""
    yaml = _make_yaml()
    loaded = yaml.load(text)
    return dict(loaded) if loaded is not None else {}


def _normalize_scalars(value: Any) -> Any:
    """ruamelの`ScalarFloat`/`ScalarInt`(書式メタデータ付き数値)を素の型に戻す。

    一度YAMLから読み込んだ数値を再度dumpする際、保持された書式メタデータ
    (元の桁数・指数表記等)から文字列を再構築すると、値は同一でも
    最終桁が異なる文字列になることがある(浮動小数点の文字列化精度の問題)。
    再dump前に素の`float`/`int`へ変換し、常に同じ書式で出力されるようにする。
    """
    if isinstance(value, dict):
        return {key: _normalize_scalars(v) for key, v in value.items()}
    if isinstance(value, list):
        return [_normalize_scalars(v) for v in value]
    if isinstance(value, ScalarFloat):
        return float(value)
    if isinstance(value, ScalarInt):
        return int(value)
    return value


def dict_to_yaml(data: dict[str, Any]) -> str:
    """dictをYAML文字列に変換する(キー順序を`KEY_ORDER`規約で固定する)。"""
    normalized = _normalize_scalars(data)
    ordered = _reorder_keys(normalized)
    yaml = _make_yaml()
    stream = StringIO()
    yaml.dump(ordered, stream)
    return stream.getvalue()


def entity_relative_path(kind: str, entity_id: str) -> Path:
    """1エンティティ1ファイル規約に基づく相対パス(`<kind>/<id>.yaml`)。"""
    return Path(kind) / f"{entity_id}{ENTITY_FILE_SUFFIX}"


def entity_to_json_dict(entity: PmdfBase) -> dict[str, Any]:
    """エンティティをJSON互換dictへ変換する(`None`値のフィールドは省略する)。

    JSON Schema上、オプショナルなフィールドは「存在しない」ことを許容する
    設計であり、「存在するが値がnull」であることまでは許容していないものが
    多い(例: `story.priority.reach`は`{"type": "number"}`で`null`非許容)。
    Pydanticの`model_dump`は既定でNone値のフィールドも明示的に出力するため、
    ここで`exclude_none=True`を用いて「値が無いフィールドは省略する」という
    JSON Schema側の意味論に合わせる。これにより、YAML保存→スキーマ再検証
    (バンドルimport等)の往復でも型不一致が発生しない。
    """
    return entity.model_dump(mode="json", exclude_none=True)


def load_entity(path: Path) -> PmdfBase:
    """YAMLファイル1件を読み、`kind`に応じたPydanticモデルへ変換する。

    Raises:
        KeyError: `kind`が未知の値の場合。
        pydantic.ValidationError: データがモデルの制約を満たさない場合。
    """
    text = path.read_text(encoding="utf-8")
    data = yaml_to_dict(text)
    kind = data.get("kind")
    if kind not in KIND_TO_MODEL:
        raise KeyError(f"未知のkindです: {kind!r} ({path})")
    model = KIND_TO_MODEL[kind]
    return model.model_validate(data)


def save_entity(entity: PmdfBase, base_dir: Path) -> Path:
    """1エンティティ1ファイル規約(`<base_dir>/<kind>/<id>.yaml`)でYAML書き込みする。

    Returns:
        書き込んだファイルの絶対パス。
    """
    data = entity_to_json_dict(entity)
    text = dict_to_yaml(data)
    relative_path = entity_relative_path(entity.kind, entity.id)
    path = base_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


__all__ = [
    "ENTITY_FILE_SUFFIX",
    "KEY_ORDER",
    "dict_to_yaml",
    "entity_relative_path",
    "entity_to_json_dict",
    "load_entity",
    "save_entity",
    "yaml_to_dict",
]
