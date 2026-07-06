"""E9-2: 月次予算監視と学習ジョブ自動停止(FR-OP-01)。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from scheduler.config import SchedulerConfig

logger = logging.getLogger(__name__)


@dataclass
class BudgetMonitorResult:
    status: str
    consumption_ratio: float = 0.0


def _auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


def run_budget_monitor(*, api_base_url: str, auth_token: str) -> BudgetMonitorResult:
    """`GET /costs/summary`をポーリングし、閾値に応じてイベント発行・学習停止フラグを更新する。"""
    base = api_base_url.rstrip("/")
    headers = _auth_headers(auth_token)

    with httpx.Client(timeout=30.0) as client:
        summary_resp = client.get(f"{base}/costs/summary", headers=headers)
        summary_resp.raise_for_status()
        summary = summary_resp.json()

        status = summary.get("budget_status", "ok")
        ratio = float(summary.get("consumption_ratio", 0.0))

        if status == "warning":
            client.post(
                f"{base}/costs/budget-events",
                headers=headers,
                json={
                    "event_type": "budget.warning",
                    "consumption_ratio": ratio,
                    "total_spend_jpy": summary.get("total_spend_jpy"),
                    "budget_monthly_jpy": summary.get("budget_monthly_jpy"),
                },
            ).raise_for_status()
            client.put(
                f"{base}/costs/learning-blocked",
                headers=headers,
                json={"learning_blocked": False},
            ).raise_for_status()
        elif status == "exceeded":
            client.post(
                f"{base}/costs/budget-events",
                headers=headers,
                json={
                    "event_type": "budget.exceeded",
                    "consumption_ratio": ratio,
                    "total_spend_jpy": summary.get("total_spend_jpy"),
                    "budget_monthly_jpy": summary.get("budget_monthly_jpy"),
                },
            ).raise_for_status()
            client.put(
                f"{base}/costs/learning-blocked",
                headers=headers,
                json={"learning_blocked": True},
            ).raise_for_status()
            logger.warning("monthly budget exceeded; learning jobs blocked")
        else:
            client.put(
                f"{base}/costs/learning-blocked",
                headers=headers,
                json={"learning_blocked": False},
            ).raise_for_status()

    return BudgetMonitorResult(status=status, consumption_ratio=ratio)


def check_learning_blocked(*, api_base_url: str, auth_token: str) -> bool:
    """学習ジョブ停止フラグをapi-serverから取得する。"""
    base = api_base_url.rstrip("/")
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{base}/costs/learning-blocked",
            headers=_auth_headers(auth_token),
        )
        response.raise_for_status()
        return bool(response.json().get("learning_blocked", False))


def register_budget_monitor_job(
    scheduler: BackgroundScheduler,
    config: SchedulerConfig,
    *,
    cron: str | None = None,
) -> None:
    cron_expr = cron or config.budget_monitor_cron
    scheduler.add_job(
        lambda: run_budget_monitor(
            api_base_url=config.api_base_url,
            auth_token=config.auth_token,
        ),
        CronTrigger.from_crontab(cron_expr),
        id="budget_monitor",
        replace_existing=True,
    )


__all__ = [
    "BudgetMonitorResult",
    "check_learning_blocked",
    "register_budget_monitor_job",
    "run_budget_monitor",
]
