"""PMDFバンドル(`*.pmdf.tar.gz`)のインポート検証・差分プレビュー・適用(FR-EX-04/05)。

手順: スキーマ検証(`validate_bundle`) → ID衝突・参照整合チェック →
差分プレビュー(`diff_preview`) → 適用(`apply_bundle`)。
適用はdry-run(プレビューのみ)と実適用を分離する。

モジュール名は`import`が予約語のため`import_`とする。
"""

from __future__ import annotations

import json
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import jsonschema
import yaml

from pmdf.bundle.export import compute_content_hash
from pmdf.models import KIND_TO_MODEL
from pmdf.models.common import PmdfBase
from pmdf.schema_registry import SchemaNotFoundError, validate_entity
from pmdf.validate import ReferenceError, validate_references

Resolution = Literal["incoming", "existing"]
DiffType = Literal["new", "conflict", "identical"]


@dataclass(frozen=True)
class BundleValidationError:
    """バンドル検証時の1件のエラー。"""

    relpath: str
    message: str


@dataclass(frozen=True)
class BundleValidationResult:
    """`validate_bundle`の結果。"""

    is_valid: bool
    entities: list[PmdfBase] = field(default_factory=list)
    errors: list[BundleValidationError] = field(default_factory=list)
    manifest: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EntityDiff:
    """1エンティティ分の差分プレビュー結果。"""

    id: str
    kind: str
    diff_type: DiffType
    field_diffs: dict[str, tuple[Any, Any]] | None = None
    reference_errors: list[ReferenceError] = field(default_factory=list)


@dataclass(frozen=True)
class ApplyResult:
    """`apply_bundle`の結果。"""

    applied_ids: list[str]
    skipped_ids: list[str]
    dry_run: bool


class PmdfStore(Protocol):
    """バンドル適用先のストア層が満たすべき最小プロトコル。

    本パッケージ(packages/pmdf)単体では具象実装を持たず、E3のpmdf-store層が
    このプロトコルを満たす実装を注入する。
    """

    def save(self, entity: PmdfBase) -> None: ...


def _read_tar_members(bundle_path: Path) -> dict[str, bytes]:
    members: dict[str, bytes] = {}
    with tarfile.open(bundle_path, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            members[member.name] = extracted.read()
    return members


def validate_bundle(bundle_path: Path) -> BundleValidationResult:
    """バンドルを展開し、各エンティティのJSON Schema検証とmanifest整合を確認する。

    manifest記載のエンティティ数・content_hashと実際の内容が一致するかも
    検証する。エラーが1件でもあれば`is_valid=False`となり、後続の
    差分プレビュー・適用処理には進めない。
    """
    members = _read_tar_members(bundle_path)
    errors: list[BundleValidationError] = []

    if "manifest.json" not in members:
        return BundleValidationResult(
            is_valid=False,
            errors=[BundleValidationError("manifest.json", "manifest.jsonが見つかりません")],
        )
    manifest = json.loads(members["manifest.json"])

    entity_relpaths = sorted(
        name for name in members if name.startswith("entities/") and name.endswith(".yaml")
    )

    entity_yaml_by_relpath: dict[str, bytes] = {}
    entities: list[PmdfBase] = []
    for full_relpath in entity_relpaths:
        relpath = full_relpath.removeprefix("entities/")
        entity_yaml_by_relpath[relpath] = members[full_relpath]
        try:
            data = yaml.safe_load(members[full_relpath].decode("utf-8"))
        except yaml.YAMLError as exc:
            errors.append(BundleValidationError(full_relpath, f"YAML解析エラー: {exc}"))
            continue

        kind = data.get("kind") if isinstance(data, dict) else None
        try:
            validate_entity(data, kind=kind)
        except jsonschema.exceptions.ValidationError as exc:
            errors.append(BundleValidationError(full_relpath, f"スキーマ検証エラー: {exc.message}"))
            continue
        except SchemaNotFoundError as exc:
            errors.append(BundleValidationError(full_relpath, str(exc)))
            continue

        assert isinstance(kind, str)
        model_cls = KIND_TO_MODEL[kind]
        entities.append(model_cls.model_validate(data))

    expected_total = manifest.get("entity_count", {}).get("total")
    if expected_total is not None and expected_total != len(entity_relpaths):
        errors.append(
            BundleValidationError(
                "manifest.json",
                f"manifestのentity_count.total({expected_total})と実際のエンティティ数"
                f"({len(entity_relpaths)})が一致しません",
            )
        )

    expected_hash = manifest.get("content_hash")
    actual_hash = compute_content_hash(entity_yaml_by_relpath)
    if expected_hash is not None and expected_hash != actual_hash:
        errors.append(
            BundleValidationError(
                "manifest.json",
                f"manifestのcontent_hash({expected_hash})と実際の内容から算出したハッシュ"
                f"({actual_hash})が一致しません",
            )
        )

    return BundleValidationResult(
        is_valid=len(errors) == 0, entities=entities, errors=errors, manifest=manifest
    )


def _field_level_diff(incoming: PmdfBase, existing: PmdfBase) -> dict[str, tuple[Any, Any]]:
    incoming_data = incoming.model_dump(mode="json")
    existing_data = existing.model_dump(mode="json")
    diffs: dict[str, tuple[Any, Any]] = {}
    keys = set(incoming_data) | set(existing_data)
    for key in keys:
        incoming_value = incoming_data.get(key)
        existing_value = existing_data.get(key)
        if incoming_value != existing_value:
            diffs[key] = (incoming_value, existing_value)
    return diffs


def diff_preview(bundle_path: Path, existing_entities: list[PmdfBase]) -> list[EntityDiff]:
    """バンドルと既存エンティティ集合を比較し、差分プレビューを生成する。

    Raises:
        ValueError: バンドルのスキーマ検証に失敗している場合。
    """
    validation = validate_bundle(bundle_path)
    if not validation.is_valid:
        raise ValueError(
            "バンドルのスキーマ検証に失敗しているため差分プレビューを生成できません: "
            f"{[e.message for e in validation.errors]}"
        )

    existing_by_id = {entity.id: entity for entity in existing_entities}

    # 参照整合チェックは既存+バンドルの合併集合に対して実行する。
    merged_by_id: dict[str, PmdfBase] = dict(existing_by_id)
    for entity in validation.entities:
        merged_by_id[entity.id] = entity
    reference_errors = validate_references(list(merged_by_id.values()))
    errors_by_entity_id: dict[str, list[ReferenceError]] = {}
    for ref_error in reference_errors:
        errors_by_entity_id.setdefault(ref_error.entity_id, []).append(ref_error)

    diffs: list[EntityDiff] = []
    for entity in validation.entities:
        existing = existing_by_id.get(entity.id)
        ref_errors_for_entity = errors_by_entity_id.get(entity.id, [])
        if existing is None:
            diffs.append(
                EntityDiff(
                    id=entity.id,
                    kind=entity.kind,
                    diff_type="new",
                    reference_errors=ref_errors_for_entity,
                )
            )
        elif existing == entity:
            diffs.append(
                EntityDiff(
                    id=entity.id,
                    kind=entity.kind,
                    diff_type="identical",
                    reference_errors=ref_errors_for_entity,
                )
            )
        else:
            diffs.append(
                EntityDiff(
                    id=entity.id,
                    kind=entity.kind,
                    diff_type="conflict",
                    field_diffs=_field_level_diff(entity, existing),
                    reference_errors=ref_errors_for_entity,
                )
            )
    return diffs


def apply_bundle(
    bundle_path: Path,
    resolutions: dict[str, Resolution],
    store: PmdfStore,
    dry_run: bool = False,
) -> ApplyResult:
    """バンドルをストアへ適用する。

    Args:
        bundle_path: 適用対象のバンドル。
        resolutions: `conflict`となったidに対する解決方針
            (`"incoming"`: 取込側採用 / `"existing"`: 既存側維持)。
            `new`エンティティや`resolutions`未指定のエンティティは
            既定で取込側(incoming)を採用する。
        store: 書き込み先ストア(`PmdfStore`プロトコルを満たす実装)。
        dry_run: Trueの場合、実際の書き込みを行わずシミュレーション結果のみ返す。

    Raises:
        ValueError: バンドルのスキーマ検証に失敗している場合。
    """
    validation = validate_bundle(bundle_path)
    if not validation.is_valid:
        raise ValueError(
            "バンドルのスキーマ検証に失敗しているため適用できません: "
            f"{[e.message for e in validation.errors]}"
        )

    applied_ids: list[str] = []
    skipped_ids: list[str] = []
    for entity in validation.entities:
        resolution = resolutions.get(entity.id, "incoming")
        if resolution == "existing":
            skipped_ids.append(entity.id)
            continue
        applied_ids.append(entity.id)
        if not dry_run:
            store.save(entity)

    return ApplyResult(applied_ids=applied_ids, skipped_ids=skipped_ids, dry_run=dry_run)


__all__ = [
    "ApplyResult",
    "BundleValidationError",
    "BundleValidationResult",
    "EntityDiff",
    "PmdfStore",
    "Resolution",
    "apply_bundle",
    "diff_preview",
    "validate_bundle",
]
