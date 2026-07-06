"""agent-core コンテナ起動エントリポイント(E4-4 暫定: healthcheck のみ)。"""

from __future__ import annotations

import os

from agent_core.health_server import run_health_server
from agent_core.logging import configure_logging, get_logger


def main() -> None:
    configure_logging()
    logger = get_logger(__name__)
    port = int(os.environ.get("AGENT_CORE_HEALTH_PORT", "8081"))
    logger.info("agent-core health server starting", port=port)
    run_health_server(port=port)


if __name__ == "__main__":
    main()
