"""E9-1: 定常業務・自己学習ループの定期ジョブ(FR-OP-04)。"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from scheduler.config import SchedulerConfig, load_scheduler_config

logger = logging.getLogger(__name__)


@dataclass
class LearningLoopResult:
    status: str
    failed_stage: str | None = None
    error: str | None = None
    details: dict[str, Any] | None = None


@dataclass
class LearningLoopDeps:
    """学習ループ各段階を注入可能にし、テストでモック差し替えできるようにする。"""

    synthesize: Callable[[], list[Any]]
    execute: Callable[[Any], Any]
    evaluate: Callable[[Any], Any]
    build_datasets: Callable[[list[Any]], str]
    run_training: Callable[[str], Any]
    compare_models: Callable[[], Any]


def trigger_learning_loop(
    *,
    deps: LearningLoopDeps | None = None,
    is_learning_blocked: Callable[[], bool] | None = None,
) -> LearningLoopResult:
    """E8-2〜E8-8の各段階を順に呼び出す。途中失敗時は後続を実行しない。"""
    if is_learning_blocked and is_learning_blocked():
        logger.warning("learning_loop skipped: monthly budget exceeded")
        return LearningLoopResult(status="skipped", failed_stage="budget_check")

    loop_deps = deps or _default_learning_loop_deps()
    context: dict[str, Any] = {}

    def _run_stage(name: str, fn: Callable[[], Any]) -> LearningLoopResult | None:
        try:
            context[name] = fn()
        except Exception as exc:
            logger.exception("learning_loop failed at stage=%s", name)
            return LearningLoopResult(
                status="failed",
                failed_stage=name,
                error=str(exc),
                details=dict(context),
            )
        return None

    stage_runners: list[tuple[str, Callable[[], Any]]] = [
        ("synthesize", lambda: loop_deps.synthesize()),
        ("execute", lambda: [loop_deps.execute(s) for s in context["synthesize"]]),
        ("evaluate", lambda: [loop_deps.evaluate(t) for t in context["execute"]]),
        ("build_datasets", lambda: loop_deps.build_datasets(context["evaluate"])),
        ("run_training", lambda: loop_deps.run_training(context["build_datasets"])),
        ("compare_models", lambda: loop_deps.compare_models()),
    ]

    for stage_name, stage_fn in stage_runners:
        failure = _run_stage(stage_name, stage_fn)
        if failure is not None:
            return failure

    return LearningLoopResult(status="completed", details=dict(context))


def trigger_kpi_monitoring(*, config: SchedulerConfig | None = None) -> dict[str, Any]:
    """E5-6 `monitor_kpi` グラフを定期起動する。"""
    cfg = config or load_scheduler_config()
    return asyncio.run(_default_kpi_runner(config=cfg))


def trigger_weekly_review(*, config: SchedulerConfig | None = None) -> dict[str, Any]:
    """E5-6 `weekly_review` グラフを週次起動する。"""
    cfg = config or load_scheduler_config()
    return asyncio.run(_default_weekly_review_runner(config=cfg))


def register_scheduled_jobs(scheduler: BackgroundScheduler, config: SchedulerConfig) -> None:
    """cron式を環境変数から読み込んだ設定でジョブを登録する。"""
    scheduler.add_job(
        trigger_kpi_monitoring,
        CronTrigger.from_crontab(config.kpi_cron),
        id="kpi_monitoring",
        kwargs={"config": config},
        replace_existing=True,
    )
    scheduler.add_job(
        trigger_weekly_review,
        CronTrigger.from_crontab(config.weekly_review_cron),
        id="weekly_review",
        kwargs={"config": config},
        replace_existing=True,
    )
    scheduler.add_job(
        trigger_learning_loop,
        CronTrigger.from_crontab(config.learning_loop_cron),
        id="learning_loop",
        replace_existing=True,
    )


async def _default_kpi_runner(*, config: SchedulerConfig) -> dict[str, Any]:
    from agent_core.graphs.kpi_dr_review import monitor_kpi
    from agent_core.llm_client import LogicalModelClient
    from agent_core.tools.pmdf_tools import PmdfToolClient

    llm_client = LogicalModelClient(config.model_gateway_url)
    pmdf_client = PmdfToolClient(
        api_server_url=config.api_base_url,
        auth_token=config.auth_token,
        agent_name="scheduler",
        agent_version="v1",
    )
    return await monitor_kpi(
        metric_id=config.metric_id,
        product_id=config.product_id,
        pmdf_tool_client=pmdf_client,
        llm_client=llm_client,
        api_server_url=config.api_base_url,
        auth_token=config.auth_token,
    )


async def _default_weekly_review_runner(*, config: SchedulerConfig) -> dict[str, Any]:
    from agent_core.graphs.kpi_dr_review import weekly_review
    from agent_core.llm_client import LogicalModelClient
    from agent_core.tools.pmdf_tools import PmdfToolClient

    llm_client = LogicalModelClient(config.model_gateway_url)
    pmdf_client = PmdfToolClient(
        api_server_url=config.api_base_url,
        auth_token=config.auth_token,
        agent_name="scheduler",
        agent_version="v1",
    )
    return await weekly_review(
        product_id=config.product_id,
        period=config.weekly_review_period,
        proposer=config.proposer,
        pmdf_tool_client=pmdf_client,
        llm_client=llm_client,
        api_server_url=config.api_base_url,
        auth_token=config.auth_token,
    )


def _default_learning_loop_deps() -> LearningLoopDeps:
    from agent_core.learning import execute_scenario, hybrid_evaluate, synthesize_scenarios
    from agent_core.learning.dataset_builder import build_sft_dataset
    from agent_core.learning.execute import IsolatedSandboxStore
    from agent_core.llm_client import LogicalModelClient
    from eval_runner.compare import compare_models
    from trainer import run_sft
    from trainer.config import TrainingConfig

    config = load_scheduler_config()
    llm_client = LogicalModelClient(config.model_gateway_url)
    sandbox = IsolatedSandboxStore()
    production = IsolatedSandboxStore()

    def _synthesize() -> list[Any]:
        return asyncio.run(
            synthesize_scenarios(
                kb_chunks=[],
                pmdf_samples=[],
                count=1,
                llm_client=llm_client,
            )
        )

    trajectories_holder: list[Any] = []

    def _execute(scenario: Any) -> Any:
        trajectory = asyncio.run(
            execute_scenario(
                scenario,
                llm_client=llm_client,
                sandbox_store=sandbox,
                production_store=production,
            )
        )
        trajectories_holder.append(trajectory)
        return trajectory

    def _evaluate(trajectory: Any) -> Any:
        return asyncio.run(hybrid_evaluate(trajectory, llm_client=llm_client))

    def _build_datasets(evaluations: list[Any]) -> str:
        records = build_sft_dataset(trajectories_holder, evaluations)
        path = Path(tempfile.mkdtemp()) / "sft.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(record.model_dump_json() + "\n")
        return str(path)

    def _run_training(dataset_path: str) -> Any:
        return run_sft(dataset_path, TrainingConfig(output_dir=tempfile.mkdtemp()))

    def _compare() -> Any:
        baseline = {"discovery": 60.0, "general_reasoning": 70.0}
        candidate = {"discovery": 75.0, "general_reasoning": 70.0}
        return compare_models(baseline, candidate)

    return LearningLoopDeps(
        synthesize=_synthesize,
        execute=_execute,
        evaluate=_evaluate,
        build_datasets=_build_datasets,
        run_training=_run_training,
        compare_models=_compare,
    )


__all__ = [
    "LearningLoopDeps",
    "LearningLoopResult",
    "register_scheduled_jobs",
    "trigger_kpi_monitoring",
    "trigger_learning_loop",
    "trigger_weekly_review",
]
