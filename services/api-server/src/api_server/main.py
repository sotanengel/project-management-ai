"""api-server FastAPIアプリケーションのエントリポイント。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_server.config import get_settings
from api_server.exceptions import register_exception_handlers
from api_server.logging import configure_logging
from api_server.routers import (
    admin,
    approvals,
    auth,
    autonomy,
    bundles,
    chat,
    costs,
    health,
    l1_execution,
    pmdf,
    ws,
)


def create_app() -> FastAPI:
    """FastAPIアプリを組み立てる(テストからは設定変更後に毎回呼び出す想定)。"""
    configure_logging()
    get_settings.cache_clear()
    settings = get_settings()

    app = FastAPI(
        title="project-management-ai api-server",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(approvals.router)
    app.include_router(autonomy.router)
    app.include_router(bundles.router)
    app.include_router(chat.router)
    app.include_router(costs.router)
    app.include_router(l1_execution.router)
    app.include_router(pmdf.router)
    app.include_router(ws.router)

    return app


def __getattr__(name: str) -> FastAPI:
    """`uvicorn api_server.main:app` 起動用に、初回アクセス時のみアプリを生成する。

    モジュールインポート時点(テスト収集時など、環境変数が未設定の場合を含む)
    には `create_app()` を呼び出さないための遅延初期化。
    """
    if name == "app":
        return create_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["create_app"]
