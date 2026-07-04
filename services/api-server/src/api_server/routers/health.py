"""GET /healthz: 依存先(pmdf-store読み書き可否)の簡易ヘルスチェック。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api_server.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """pmdf-storeのルートディレクトリへアクセス可能かを簡易チェックする。"""
    store_path = settings.pmdf_store_path
    store_path.mkdir(parents=True, exist_ok=True)
    return {"status": "ok"}


__all__ = ["router"]
