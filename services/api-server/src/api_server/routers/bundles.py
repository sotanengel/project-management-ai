"""PMDFバンドルのimport/export API(FR-DF-03, AC-07)。

E2バンドル機能(`pmdf.bundle.export`/`pmdf.bundle.import_`)をHTTP API化する。
バンドルのアップロードから適用までを1コミットとして扱う
(`PmdfStore.save_all`によるE3-2のpmdf-store層との統合)。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pmdf.bundle.export import ExportScope, export_bundle
from pmdf.bundle.import_ import Resolution, apply_bundle, diff_preview, validate_bundle
from pmdf.models import KIND_TO_MODEL
from pmdf.models.common import PmdfBase
from pydantic import BaseModel

from api_server.audit.log import AuditRecord, append_record, latest_hash
from api_server.auth.dependencies import get_current_user, require_role
from api_server.auth.models import User
from api_server.config import Settings, get_settings
from api_server.deps import get_pmdf_store_dependency
from api_server.pmdf_store.store import PmdfStore

router = APIRouter(prefix="/bundles", tags=["bundles"])


class ExportRequest(BaseModel):
    product_ids: list[str] | None = None
    kinds: list[str] | None = None


def _all_entities(store: PmdfStore) -> list[PmdfBase]:
    entities: list[PmdfBase] = []
    for kind in KIND_TO_MODEL:
        entities.extend(store.list_all(kind))
    return entities


@router.post("/export")
def export_entities(
    request: ExportRequest,
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
    _user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """スコープに合致するエンティティを`*.pmdf.tar.gz`としてエクスポートする。"""
    scope = ExportScope(product_ids=request.product_ids, kinds=request.kinds)
    entities = _all_entities(store)

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "bundle.pmdf.tar.gz"
        export_bundle(entities, scope, output_path, generated_env="api-server")
        content = output_path.read_bytes()

    return Response(
        content=content,
        media_type="application/gzip",
        headers={"Content-Disposition": 'attachment; filename="bundle.pmdf.tar.gz"'},
    )


def _bundle_validation_error_response(validation) -> None:  # type: ignore[no-untyped-def]
    detail = [{"relpath": e.relpath, "message": e.message} for e in validation.errors]
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


@router.post("/import/validate")
async def import_validate(
    file: UploadFile,
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
    _user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """バンドルのスキーマ検証+差分プレビューを行う(この時点では未適用)。"""
    content = await file.read()
    with tempfile.TemporaryDirectory() as tmp_dir:
        bundle_path = Path(tmp_dir) / "bundle.pmdf.tar.gz"
        bundle_path.write_bytes(content)

        validation = validate_bundle(bundle_path)
        if not validation.is_valid:
            _bundle_validation_error_response(validation)

        existing_entities = _all_entities(store)
        diffs = diff_preview(bundle_path, existing_entities)

    return {
        "is_valid": validation.is_valid,
        "manifest": validation.manifest,
        "diffs": [
            {
                "id": d.id,
                "kind": d.kind,
                "diff_type": d.diff_type,
                "field_diffs": d.field_diffs,
                "reference_errors": [str(e) for e in d.reference_errors],
            }
            for d in diffs
        ],
    }


class _BatchSaveAdapter:
    """`pmdf.bundle.import_.PmdfStore` Protocol(`save(entity) -> None`)を満たすアダプタ。

    `apply_bundle`はエンティティ毎に`save`を呼び出すが、バンドル適用は
    1コミットとして扱いたい(E3-9要件)ため、`save`呼び出し中はエンティティを
    バッファリングし、`flush()`でまとめて`PmdfStore.save_all`へ委譲する。
    """

    def __init__(self, store: PmdfStore, actor: str, message: str) -> None:
        self._store = store
        self._actor = actor
        self._message = message
        self._buffer: list[PmdfBase] = []

    def save(self, entity: PmdfBase) -> None:
        self._buffer.append(entity)

    def flush(self) -> list[PmdfBase]:
        return self._store.save_all(self._buffer, actor=self._actor, message=self._message)


@router.post("/import/apply")
async def import_apply(
    file: UploadFile,
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_role("admin", "editor"))],
    resolutions: Annotated[str, Form()] = "{}",
) -> dict[str, Any]:
    """バンドルを検証のうえストアへ適用する(1コミット、監査ログに1エントリ記録)。"""
    try:
        parsed_resolutions: dict[str, Resolution] = json.loads(resolutions)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"resolutionsのJSON解析に失敗しました: {exc}",
        ) from exc

    content = await file.read()
    with tempfile.TemporaryDirectory() as tmp_dir:
        bundle_path = Path(tmp_dir) / "bundle.pmdf.tar.gz"
        bundle_path.write_bytes(content)

        validation = validate_bundle(bundle_path)
        if not validation.is_valid:
            _bundle_validation_error_response(validation)

        actor = f"user:{user.id}"
        adapter = _BatchSaveAdapter(store, actor=actor, message=f"bundle apply by {actor}")
        result = apply_bundle(bundle_path, parsed_resolutions, adapter, dry_run=False)
        adapter.flush()

    audit_record = AuditRecord.create(
        actor=actor,
        action="pmdf.bundle.apply",
        target_kind="bundle",
        target_id=file.filename or "bundle.pmdf.tar.gz",
        detail={"applied_ids": result.applied_ids, "skipped_ids": result.skipped_ids},
        prev_hash=latest_hash(settings.audit_log_path),
    )
    append_record(audit_record, settings.audit_log_path)

    return {
        "applied_ids": result.applied_ids,
        "skipped_ids": result.skipped_ids,
        "dry_run": result.dry_run,
    }


__all__ = ["router"]
