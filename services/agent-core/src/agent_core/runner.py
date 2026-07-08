"""常駐ランナー(E9系: agent-coreの常駐ワーカー)。

api-server(`GET /chat/tasks?status=pending`)を一定間隔でポーリングし、
保留中のチャットタスクを`agent_core.chat.execute_chat_task`経由で実行する
(意図分類・業務グラフディスパッチのロジック自体はchat.py側に集約されており、
本モジュールはその呼び出しループ・緊急停止/学習ブロック照会・障害時の
`failed`遷移・グレースフルシャットダウンのみを担う)。

- 緊急停止中(`GET /autonomy/emergency-stop/status`)は、ポーリングは継続する
  ものの当該サイクルでのディスパッチをスキップする(FR-AU-05)。
- 予算超過による学習ブロック中(`GET /costs/learning-blocked`)も同様に
  ディスパッチをスキップする(FR-OP-01、schedulerの`budget_monitor`と
  同じ状態を参照する)。
- 個々のタスク実行(意図分類含む)で捕捉されなかった例外が発生した場合も
  ランナー自体はクラッシュさせず、当該タスクを`failed`へ遷移させて
  ループを継続する。
"""

from __future__ import annotations

import asyncio
import os
import signal
from dataclasses import dataclass
from typing import Any

import httpx

from agent_core.chat import DispatchFn, GraphKind, execute_chat_task
from agent_core.llm_client import LogicalModelClient
from agent_core.logging import get_logger
from agent_core.tools.pmdf_tools import PmdfToolClient

logger = get_logger(__name__)

#: ポーリング間隔の既定値(秒)。環境変数`RUNNER_POLL_INTERVAL_SEC`で上書き可能。
DEFAULT_POLL_INTERVAL_SEC = 5.0

_FALSY_ENV_VALUES = {"false", "0", "no", "off", ""}


@dataclass(frozen=True)
class RunnerConfig:
    """常駐ランナーの設定(環境変数から読込)。"""

    api_server_url: str
    auth_token: str
    agent_name: str = "resident-runner"
    agent_version: str = "1"
    poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC
    enabled: bool = True


def load_runner_config_from_env() -> RunnerConfig:
    """環境変数からランナー設定を読み込む。

    - `RUNNER_ENABLED`(既定`true`): `false`/`0`/`no`/`off`(大文字小文字無視)で
      無効化する。
    - `RUNNER_POLL_INTERVAL_SEC`(既定`5`): ポーリング間隔(秒)。
    - `API_SERVER_URL`(既定`http://api-server:8000`)。
    - `AGENT_CORE_AUTH_TOKEN`(既定空文字。実運用ではサービスアカウントの
      JWTを注入する想定)。
    """
    enabled_raw = os.environ.get("RUNNER_ENABLED", "true").strip().lower()
    return RunnerConfig(
        api_server_url=os.environ.get("API_SERVER_URL", "http://api-server:8000"),
        auth_token=os.environ.get("AGENT_CORE_AUTH_TOKEN", ""),
        poll_interval_sec=float(os.environ.get("RUNNER_POLL_INTERVAL_SEC", "5")),
        enabled=enabled_raw not in _FALSY_ENV_VALUES,
    )


async def _get_json(
    client: httpx.AsyncClient,
    path: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
) -> Any:
    response = await client.get(path, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


async def _is_emergency_stopped(client: httpx.AsyncClient, headers: dict[str, str]) -> bool:
    data = await _get_json(client, "/autonomy/emergency-stop/status", headers=headers)
    return bool(data.get("emergency_stopped", False))


async def _is_learning_blocked(client: httpx.AsyncClient, headers: dict[str, str]) -> bool:
    data = await _get_json(client, "/costs/learning-blocked", headers=headers)
    return bool(data.get("learning_blocked", False))


async def poll_once(
    *,
    pmdf_tool_client: PmdfToolClient,
    llm_client: LogicalModelClient,
    api_server_url: str,
    auth_token: str,
    transport: httpx.AsyncBaseTransport | None = None,
    dispatch_overrides: dict[GraphKind, DispatchFn] | None = None,
) -> None:
    """1回分のポーリングサイクルを実行する。

    緊急停止中・学習ブロック中はディスパッチを行わずに戻る(ポーリング自体は
    正常終了する)。保留中タスクの取得・実行いずれかで例外が発生しても
    ここで捕捉し、対象タスクを可能な範囲で`failed`へ遷移させたうえで
    正常に戻る(呼び出し元のループをクラッシュさせない)。
    """
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with httpx.AsyncClient(
        base_url=api_server_url.rstrip("/"), transport=transport, timeout=30.0
    ) as client:
        try:
            if await _is_emergency_stopped(client, headers):
                logger.info("runner.emergency_stop_active_skip_dispatch")
                return
            if await _is_learning_blocked(client, headers):
                logger.info("runner.learning_blocked_skip_dispatch")
                return
            pending_tasks = await _get_json(
                client, "/chat/tasks", headers=headers, params={"status": "pending"}
            )
        except Exception as exc:  # noqa: BLE001 - ポーリングサイクル自体を落とさないため捕捉
            logger.error("runner.poll_cycle_failed", error=str(exc))
            return

    for task in pending_tasks:
        task_id = task["id"]
        try:
            await execute_chat_task(
                task_id=task_id,
                message=task["message"],
                product_id=task["product_id"],
                actor=task["actor"],
                llm_client=llm_client,
                pmdf_tool_client=pmdf_tool_client,
                api_server_url=api_server_url,
                auth_token=auth_token,
                dispatch_overrides=dispatch_overrides,
            )
        except Exception as exc:  # noqa: BLE001 - 1タスクの失敗でランナーを止めないため捕捉
            logger.error("runner.task_execution_failed", task_id=task_id, error=str(exc))
            try:
                await pmdf_tool_client.request(
                    "POST",
                    f"/chat/tasks/{task_id}/transition",
                    json={"status": "failed", "error": str(exc)},
                )
            except Exception as transition_exc:  # noqa: BLE001
                logger.error(
                    "runner.task_failed_transition_report_failed",
                    task_id=task_id,
                    error=str(transition_exc),
                )


async def run_forever(
    *,
    pmdf_tool_client: PmdfToolClient,
    llm_client: LogicalModelClient,
    api_server_url: str,
    auth_token: str,
    poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC,
    stop_event: asyncio.Event | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    dispatch_overrides: dict[GraphKind, DispatchFn] | None = None,
) -> None:
    """`stop_event`がセットされるまで`poll_once`を`poll_interval_sec`間隔で繰り返す。"""
    event = stop_event if stop_event is not None else asyncio.Event()
    while not event.is_set():
        await poll_once(
            pmdf_tool_client=pmdf_tool_client,
            llm_client=llm_client,
            api_server_url=api_server_url,
            auth_token=auth_token,
            transport=transport,
            dispatch_overrides=dispatch_overrides,
        )
        try:
            await asyncio.wait_for(event.wait(), timeout=poll_interval_sec)
        except TimeoutError:
            pass


def _install_signal_handlers(stop_event: asyncio.Event, loop: asyncio.AbstractEventLoop) -> None:
    """SIGTERM/SIGINTを`stop_event`のセットへ変換する(可能な環境でのみ有効化)。

    Windows等、シグナルの扱いが制限される環境や、メインスレッド以外から
    呼び出された場合は`signal.signal`が例外を送出しうるため、その場合は
    黙って無視する(コンテナ環境(Linux)での本来の対象を優先し、ローカル
    開発時の制約でクラッシュしないようにする)。
    """

    def _request_stop(*_args: object) -> None:
        loop.call_soon_threadsafe(stop_event.set)

    for sig_name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _request_stop)
        except (ValueError, OSError, RuntimeError):
            logger.info("runner.signal_handler_unavailable", signal=sig_name)


async def run_runner_with_graceful_shutdown(config: RunnerConfig) -> None:
    """`RunnerConfig`から常駐ワーカーを起動し、SIGTERM/SIGINTで停止するまで動作させる。"""
    pmdf_tool_client = PmdfToolClient(
        api_server_url=config.api_server_url,
        auth_token=config.auth_token,
        agent_name=config.agent_name,
        agent_version=config.agent_version,
    )
    llm_client = LogicalModelClient(
        model_gateway_url=os.environ.get("MODEL_GATEWAY_URL", "http://model-gateway:4000")
    )

    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event, asyncio.get_running_loop())

    await run_forever(
        pmdf_tool_client=pmdf_tool_client,
        llm_client=llm_client,
        api_server_url=config.api_server_url,
        auth_token=config.auth_token,
        poll_interval_sec=config.poll_interval_sec,
        stop_event=stop_event,
    )


__all__ = [
    "DEFAULT_POLL_INTERVAL_SEC",
    "RunnerConfig",
    "load_runner_config_from_env",
    "poll_once",
    "run_forever",
    "run_runner_with_graceful_shutdown",
]
