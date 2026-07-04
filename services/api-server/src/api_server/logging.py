"""structlogによるJSON構造化ログ設定。

未捕捉例外のスタックトレースは、レスポンスボディへは一切含めず、
本モジュールで設定した構造化ログにのみ出力する(E3-1受け入れ条件)。
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: int = logging.INFO) -> None:
    """アプリ起動時に一度だけ呼び出し、JSON形式の構造化ログを設定する。"""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """構造化ロガーを取得する。"""
    return structlog.get_logger(name)


__all__ = ["configure_logging", "get_logger"]
