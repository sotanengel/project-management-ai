"""scheduler コンテナ起動エントリポイント(E4-4 暫定: APScheduler 空ループ + healthcheck)。"""

from __future__ import annotations

import os
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from scheduler.health import run_health_server


def main() -> None:
    port = int(os.environ.get("SCHEDULER_HEALTH_PORT", "8082"))
    scheduler = BackgroundScheduler()
    scheduler.start()

    health_thread = threading.Thread(
        target=run_health_server,
        kwargs={"port": port},
        daemon=True,
    )
    health_thread.start()

    try:
        health_thread.join()
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
