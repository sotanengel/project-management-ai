"""agent-core コンテナ起動エントリポイント。

healthcheck用HTTPサーバ(E4-4)をバックグラウンドスレッドで起動しつつ、
同一プロセス内で常駐ランナー(`agent_core.runner`、E9系)を実行する。
`RUNNER_ENABLED=false`の場合はランナーを起動せずhealthcheckのみで待機する
(healthcheck自体は常駐ランナーの有効/無効に関わらず提供する)。
"""

from __future__ import annotations

import asyncio
import os
import threading

from agent_core.health_server import run_health_server
from agent_core.logging import configure_logging, get_logger
from agent_core.runner import load_runner_config_from_env, run_runner_with_graceful_shutdown


def _start_health_server_thread(port: int) -> threading.Thread:
    thread = threading.Thread(
        target=run_health_server,
        kwargs={"port": port},
        daemon=True,
    )
    thread.start()
    return thread


def main() -> None:
    configure_logging()
    logger = get_logger(__name__)
    port = int(os.environ.get("AGENT_CORE_HEALTH_PORT", "8081"))
    logger.info("agent-core health server starting", port=port)
    health_thread = _start_health_server_thread(port)

    runner_config = load_runner_config_from_env()
    if not runner_config.enabled:
        logger.info("runner.disabled_health_only")
        health_thread.join()
        return

    logger.info(
        "agent-core runner starting",
        poll_interval_sec=runner_config.poll_interval_sec,
        api_server_url=runner_config.api_server_url,
    )
    try:
        asyncio.run(run_runner_with_graceful_shutdown(runner_config))
    finally:
        logger.info("agent-core runner stopped")


if __name__ == "__main__":
    main()
