"""scheduler コンテナ起動エントリポイント(E9-1: cronジョブ登録 + healthcheck)。"""

from __future__ import annotations

import logging
import os
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from scheduler.config import load_scheduler_config
from scheduler.health import run_health_server
from scheduler.jobs import register_scheduled_jobs

logger = logging.getLogger(__name__)


def main() -> None:
    port = int(os.environ.get("SCHEDULER_HEALTH_PORT", "8082"))
    config = load_scheduler_config()

    scheduler = BackgroundScheduler()
    register_scheduled_jobs(scheduler, config)
    scheduler.start()
    logger.info(
        "scheduler started kpi_cron=%s weekly_cron=%s learning_cron=%s",
        config.kpi_cron,
        config.weekly_review_cron,
        config.learning_loop_cron,
    )

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
