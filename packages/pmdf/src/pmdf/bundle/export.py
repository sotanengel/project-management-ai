"""PMDFエンティティ群を `*.pmdf.tar.gz` バンドルとしてエクスポートする(FR-EX-01/02)。

tarball構造:
    manifest.json
    entities/<kind>/<id>.yaml
    attachments/<entity_id>/<path>  (include_attachments=Trueかつ実体がある場合のみ)
"""

from __future__ import annotations

import hashlib
import json
import tarfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from pmdf.io import dict_to_yaml, entity_relative_path, entity_to_json_dict
from pmdf.models.common import PmdfBase

#: 現時点のPMDFスキーマバージョン(マニフェストに記録する)。
SCHEMA_VERSION = "1.0.0"


class ExportScope(BaseModel):
    """エクスポート対象を絞り込むスコープ指定(FR-EX-02)。

    いずれのフィールドも`None`の場合は絞り込みなし(全件対象)を意味する。
    """

    model_config = ConfigDict(extra="forbid")

    product_ids: list[str] | None = None
    kinds: list[str] | None = None
    since: datetime | None = None
    until: datetime | None = None

    def matches(self, entity: PmdfBase) -> bool:
        """このスコープに`entity`が含まれるかどうかを判定する。"""
        if self.kinds is not None and entity.kind not in self.kinds:
            return False
        if self.product_ids is not None:
            owning_product = (
                entity.id if entity.kind == "product" else getattr(entity, "product", None)
            )
            if owning_product not in self.product_ids:
                return False
        updated_at = entity.provenance.updated_at
        if self.since is not None and updated_at < self.since:
            return False
        if self.until is not None and updated_at > self.until:
            return False
        return True


def _select_entities(entities: list[PmdfBase], scope: ExportScope) -> list[PmdfBase]:
    selected = [entity for entity in entities if scope.matches(entity)]
    # (kind, id)でソートし、content_hash・tar内順序を決定的にする。
    return sorted(selected, key=lambda e: (e.kind, e.id))


def compute_content_hash(entity_yaml_by_relpath: dict[str, bytes]) -> str:
    """全エンティティYAMLの内容から決定的なSHA-256ハッシュを算出する。"""
    hasher = hashlib.sha256()
    for relpath in sorted(entity_yaml_by_relpath):
        hasher.update(relpath.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(entity_yaml_by_relpath[relpath])
        hasher.update(b"\0")
    return hasher.hexdigest()


def _build_manifest(
    selected: list[PmdfBase],
    entity_yaml_by_relpath: dict[str, bytes],
    generated_env: str,
) -> dict:
    by_kind: dict[str, int] = {}
    for entity in selected:
        by_kind[entity.kind] = by_kind.get(entity.kind, 0) + 1
    owning_product_ids = {
        entity.id if entity.kind == "product" else getattr(entity, "product", None)
        for entity in selected
    }
    product_ids: list[str] = sorted(pid for pid in owning_product_ids if pid is not None)
    return {
        "schema_version": SCHEMA_VERSION,
        "product_ids": product_ids,
        "entity_count": {"total": len(selected), "by_kind": by_kind},
        "generated_env": generated_env,
        "generated_at": datetime.now().astimezone().isoformat(),
        "content_hash": compute_content_hash(entity_yaml_by_relpath),
    }


def export_bundle(
    entities: list[PmdfBase],
    scope: ExportScope,
    output_path: Path,
    include_attachments: bool = True,
    attachments_dir: Path | None = None,
    generated_env: str = "unknown",
) -> Path:
    """PMDFエンティティ群を`output_path`(`*.pmdf.tar.gz`)にエクスポートする。

    Args:
        entities: エクスポート候補となる全エンティティ。
        scope: 絞り込み条件(プロダクト/種別/期間)。
        output_path: 出力先の`.pmdf.tar.gz`パス。
        include_attachments: Trueの場合、`attachments_dir`配下の実体ファイルを
            バンドルに同梱する。Falseの場合、エンティティ側の`attachments`
            フィールド(path+sha256の参照)は保持したままバイナリ本体は含めない。
        attachments_dir: 添付ファイルの実体を探索するベースディレクトリ。
        generated_env: 生成環境を表す文字列(呼び出し側から注入)。

    Returns:
        書き込んだ`output_path`。
    """
    selected = _select_entities(entities, scope)

    entity_yaml_by_relpath: dict[str, bytes] = {}
    for entity in selected:
        # tar内のパスはOS非依存にPOSIX形式(`/`区切り)で統一する。
        relpath = entity_relative_path(entity.kind, entity.id).as_posix()
        data = entity_to_json_dict(entity)
        entity_yaml_by_relpath[relpath] = dict_to_yaml(data).encode("utf-8")

    manifest = _build_manifest(selected, entity_yaml_by_relpath, generated_env)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output_path, "w:gz") as tar:
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        _add_bytes(tar, "manifest.json", manifest_bytes)

        for relpath, content in entity_yaml_by_relpath.items():
            _add_bytes(tar, f"entities/{relpath}", content)

        if include_attachments and attachments_dir is not None:
            for entity in selected:
                for attachment in entity.attachments:
                    source_path = attachments_dir / attachment.path
                    if not source_path.exists():
                        continue
                    tar.add(
                        source_path,
                        arcname=f"attachments/{entity.id}/{attachment.path}",
                    )

    return output_path


def _add_bytes(tar: tarfile.TarFile, arcname: str, content: bytes) -> None:
    info = tarfile.TarInfo(name=arcname)
    info.size = len(content)
    tar.addfile(info, BytesIO(content))


__all__ = ["SCHEMA_VERSION", "ExportScope", "compute_content_hash", "export_bundle"]
