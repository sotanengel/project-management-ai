"""E9-2: 予算監視と学習ジョブ自動停止のテスト。"""

from __future__ import annotations

import httpx
import pytest
import respx
from scheduler.budget_monitor import check_learning_blocked, run_budget_monitor
from scheduler.config import SchedulerConfig
from scheduler.jobs import LearningLoopDeps, trigger_learning_loop


@pytest.fixture
def api_base() -> str:
    return "http://api.test:8000"


@respx.mock
def test_run_budget_monitor_emits_warning_event(api_base: str) -> None:
    respx.get(f"{api_base}/costs/summary").mock(
        return_value=httpx.Response(
            200,
            json={
                "budget_status": "warning",
                "consumption_ratio": 0.85,
                "total_spend_jpy": 42500,
                "budget_monthly_jpy": 50000,
            },
        )
    )
    publish = respx.post(f"{api_base}/costs/budget-events").mock(
        return_value=httpx.Response(200, json={"published": True})
    )
    respx.put(f"{api_base}/costs/learning-blocked").mock(
        return_value=httpx.Response(200, json={"learning_blocked": False})
    )

    result = run_budget_monitor(api_base_url=api_base, auth_token="token")

    assert result.status == "warning"
    assert publish.called
    assert publish.calls.last.request.content
    assert b"budget.warning" in publish.calls.last.request.content


@respx.mock
def test_run_budget_monitor_blocks_learning_at_exceeded(api_base: str) -> None:
    respx.get(f"{api_base}/costs/summary").mock(
        return_value=httpx.Response(
            200,
            json={
                "budget_status": "exceeded",
                "consumption_ratio": 1.1,
                "total_spend_jpy": 55000,
                "budget_monthly_jpy": 50000,
            },
        )
    )
    respx.post(f"{api_base}/costs/budget-events").mock(
        return_value=httpx.Response(200, json={"published": True})
    )
    blocked = respx.put(f"{api_base}/costs/learning-blocked").mock(
        return_value=httpx.Response(200, json={"learning_blocked": True})
    )

    result = run_budget_monitor(api_base_url=api_base, auth_token="token")

    assert result.status == "exceeded"
    assert blocked.called
    body = blocked.calls.last.request.content.decode()
    assert "true" in body.lower()


@respx.mock
def test_run_budget_monitor_ok_does_not_publish(api_base: str) -> None:
    respx.get(f"{api_base}/costs/summary").mock(
        return_value=httpx.Response(
            200,
            json={
                "budget_status": "ok",
                "consumption_ratio": 0.5,
                "total_spend_jpy": 25000,
                "budget_monthly_jpy": 50000,
            },
        )
    )
    publish = respx.post(f"{api_base}/costs/budget-events").mock(
        return_value=httpx.Response(200, json={"published": True})
    )
    respx.put(f"{api_base}/costs/learning-blocked").mock(
        return_value=httpx.Response(200, json={"learning_blocked": False})
    )

    result = run_budget_monitor(api_base_url=api_base, auth_token="token")

    assert result.status == "ok"
    assert not publish.called


@respx.mock
def test_check_learning_blocked(api_base: str) -> None:
    respx.get(f"{api_base}/costs/learning-blocked").mock(
        return_value=httpx.Response(200, json={"learning_blocked": True})
    )
    assert check_learning_blocked(api_base_url=api_base, auth_token="token") is True


def test_trigger_learning_loop_skips_when_remote_blocked(
    monkeypatch: pytest.MonkeyPatch,
    api_base: str,
) -> None:
    monkeypatch.setattr(
        "scheduler.budget_monitor.check_learning_blocked",
        lambda **_kwargs: True,
    )

    called: list[str] = []

    def _synthesize() -> list[object]:
        called.append("synthesize")
        return []

    def _execute(_: object) -> object:
        called.append("execute")
        return {}

    def _evaluate(_: object) -> object:
        called.append("evaluate")
        return {}

    def _build(_: list[object]) -> str:
        called.append("build")
        return ""

    def _train(_: str) -> object:
        called.append("train")
        return {}

    def _compare() -> object:
        called.append("compare")
        return {}

    deps = LearningLoopDeps(
        synthesize=_synthesize,
        execute=_execute,
        evaluate=_evaluate,
        build_datasets=_build,
        run_training=_train,
        compare_models=_compare,
    )

    result = trigger_learning_loop(
        deps=deps,
        config=SchedulerConfig(
            api_base_url=api_base,
            model_gateway_url="http://gateway.test:4000",
            auth_token="token",
            product_id="p",
            metric_id="m",
            proposer="p",
            kpi_cron="0 * * * *",
            weekly_review_cron="0 9 * * 1",
            learning_loop_cron="0 2 * * 0",
            weekly_review_period="2026-W01",
            budget_monitor_cron="0 * * * *",
        ),
    )

    assert result.status == "skipped"
    assert called == []
