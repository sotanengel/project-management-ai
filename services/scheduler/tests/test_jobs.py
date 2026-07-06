"""E9-1: scheduler ジョブ登録・学習ループ連結のテスト。"""

from __future__ import annotations

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from scheduler.config import SchedulerConfig, load_scheduler_config
from scheduler.jobs import (
    LearningLoopDeps,
    register_scheduled_jobs,
    trigger_kpi_monitoring,
    trigger_learning_loop,
    trigger_weekly_review,
)


def test_load_scheduler_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEDULER_KPI_CRON", "15 * * * *")
    monkeypatch.setenv("SCHEDULER_WEEKLY_REVIEW_CRON", "30 10 * * 2")
    monkeypatch.setenv("SCHEDULER_LEARNING_LOOP_CRON", "0 3 * * 0")
    monkeypatch.setenv("API_BASE_URL", "http://api.test:8000")

    config = load_scheduler_config()

    assert config.kpi_cron == "15 * * * *"
    assert config.weekly_review_cron == "30 10 * * 2"
    assert config.learning_loop_cron == "0 3 * * 0"
    assert config.api_base_url == "http://api.test:8000"


def test_register_scheduled_jobs_uses_cron_from_config() -> None:
    scheduler = BackgroundScheduler()
    config = SchedulerConfig(
        api_base_url="http://api.test:8000",
        model_gateway_url="http://gateway.test:4000",
        auth_token="token",
        product_id="product-01",
        metric_id="metric-01",
        proposer="admin@example.com",
        kpi_cron="5 * * * *",
        weekly_review_cron="10 9 * * 1",
        learning_loop_cron="0 2 * * 0",
        weekly_review_period="2026-W01",
    )

    register_scheduled_jobs(scheduler, config)

    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert set(jobs) == {"kpi_monitoring", "weekly_review", "learning_loop"}
    assert "5" in str(jobs["kpi_monitoring"].trigger)
    assert "10" in str(jobs["weekly_review"].trigger)
    assert "hour='2'" in str(jobs["learning_loop"].trigger)
    assert "minute='0'" in str(jobs["learning_loop"].trigger)


def test_trigger_kpi_monitoring_invokes_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    async def _runner(**_kwargs: object) -> dict[str, object]:
        called.append("kpi")
        return {"breached": False}

    monkeypatch.setattr("scheduler.jobs._default_kpi_runner", _runner)
    trigger_kpi_monitoring()
    assert called == ["kpi"]


def test_trigger_weekly_review_invokes_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    async def _runner(**_kwargs: object) -> dict[str, object]:
        called.append("weekly")
        return {"report": {}}

    monkeypatch.setattr("scheduler.jobs._default_weekly_review_runner", _runner)
    trigger_weekly_review()
    assert called == ["weekly"]


def test_trigger_learning_loop_runs_stages_in_order() -> None:
    order: list[str] = []

    deps = LearningLoopDeps(
        synthesize=lambda: order.append("synthesize") or [{"id": "s1"}],
        execute=lambda _scenario: order.append("execute") or {"ok": True},
        evaluate=lambda _trajectory: order.append("evaluate") or {"passed": True},
        build_datasets=lambda _evaluations: order.append("build_datasets") or "/tmp/data.jsonl",
        run_training=lambda _path: order.append("run_training") or {"adapter": "/tmp/adapter"},
        compare_models=lambda: order.append("compare_models") or {"decision": "promote"},
    )

    result = trigger_learning_loop(deps=deps)

    assert order == [
        "synthesize",
        "execute",
        "evaluate",
        "build_datasets",
        "run_training",
        "compare_models",
    ]
    assert result.status == "completed"
    assert result.failed_stage is None


def test_trigger_learning_loop_stops_on_stage_failure() -> None:
    order: list[str] = []

    deps = LearningLoopDeps(
        synthesize=lambda: order.append("synthesize") or [{"id": "s1"}],
        execute=lambda _scenario: (_ for _ in ()).throw(RuntimeError("execute failed")),
        evaluate=lambda _trajectory: order.append("evaluate"),
        build_datasets=lambda _evaluations: order.append("build_datasets"),
        run_training=lambda _path: order.append("run_training"),
        compare_models=lambda: order.append("compare_models"),
    )

    result = trigger_learning_loop(deps=deps)

    assert order == ["synthesize"]
    assert result.status == "failed"
    assert result.failed_stage == "execute"
    assert "execute failed" in (result.error or "")


def test_trigger_learning_loop_skips_when_budget_blocked() -> None:
    order: list[str] = []
    deps = LearningLoopDeps(
        synthesize=lambda: order.append("synthesize") or [],
        execute=lambda _scenario: order.append("execute"),
        evaluate=lambda _trajectory: order.append("evaluate"),
        build_datasets=lambda _evaluations: order.append("build_datasets"),
        run_training=lambda _path: order.append("run_training"),
        compare_models=lambda: order.append("compare_models"),
    )

    result = trigger_learning_loop(deps=deps, is_learning_blocked=lambda: True)

    assert order == []
    assert result.status == "skipped"
    assert result.failed_stage == "budget_check"


def test_cron_trigger_parses_five_field_expression() -> None:
    trigger = CronTrigger.from_crontab("0 9 * * 1")
    assert "0" in str(trigger)
    assert "9" in str(trigger)
