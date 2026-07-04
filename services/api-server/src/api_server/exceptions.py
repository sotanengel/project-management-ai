"""共通例外ハンドラ。

統一エラー形式 `{"error": {"code": str, "message": str}}` でJSONを返す。
未捕捉例外は500として返し、スタックトレースはレスポンスボディへ含めず
構造化ログにのみ出力する。
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from api_server.logging import get_logger

logger = get_logger(__name__)


def _error_response(status_code: int, code: str, message: str, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if extra:
        body["error"].update(extra)
    return JSONResponse(status_code=status_code, content=body)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError | ValidationError
) -> JSONResponse:
    logger.info("request_validation_error", path=str(request.url), errors=exc.errors())
    return _error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_error",
        "リクエストの検証に失敗しました",
        details=exc.errors(),
    )


async def permission_error_handler(request: Request, exc: PermissionError) -> JSONResponse:
    logger.warning("permission_denied", path=str(request.url), detail=str(exc))
    return _error_response(status.HTTP_403_FORBIDDEN, "forbidden", str(exc) or "権限がありません")


async def http_exception_handler(
    request: Request, exc: HTTPException | StarletteHTTPException
) -> JSONResponse:
    code = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "validation_error",
        503: "service_unavailable",
    }.get(exc.status_code, "http_error")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": str(exc.detail)}},
        headers=exc.headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # スタックトレースは構造化ログにのみ出力し、レスポンスボディへは含めない。
    logger.error(
        "unhandled_exception",
        path=str(request.url),
        exc_info=exc,
    )
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "内部エラーが発生しました",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """FastAPIアプリへ共通例外ハンドラ群を登録する。

    各ハンドラは対応する例外型に特化した引数型を持つが、Starletteの
    `add_exception_handler` シグネチャは汎用的な`Exception`基底型を要求する
    ため、mypy上は型不一致となる(実行時には例外型ディスパッチにより
    正しいハンドラが呼ばれるため安全)。
    """
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(PermissionError, permission_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)


__all__ = ["register_exception_handlers"]
