"""agent-core コンテナ起動エントリポイント(E4-4 暫定: healthcheck のみ)。"""

from __future__ import annotations

import os

from agent_core.health_server import run_health_server


def main() -> None:
    port = int(os.environ.get("AGENT_CORE_HEALTH_PORT", "8081"))
    run_health_server(port=port)


if __name__ == "__main__":
    main()
