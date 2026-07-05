"""E8-3: 生徒モデル実行・軌跡記録のテスト。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx
from agent_core.learning.execute import IsolatedSandboxStore, execute_scenario
from agent_core.learning.synthesize import Scenario
from agent_core.llm_client import LogicalModelClient
from pmdf.learning.schemas import RecordProvenance, TrajectoryRecord

MODEL_GATEWAY_URL = "http://model-gateway.test:4000"


def _sample_scenario() -> Scenario:
    return Scenario(
        situation="バックログに未整理ストーリーが10件ある",
        task="RICEで優先順位を付けよ",
        expected_answer_type="priority_judgment",
        coverage_tags=["domain:backlog", "framework:rice"],
        provenance=RecordProvenance(
            model="pdm-teacher",
            prompt_template_version="e8-2-v1",
            kb_version="corpus-v1",
            generated_at=datetime(2026, 7, 5, tzinfo=UTC),
        ),
    )


@pytest.mark.asyncio
async def test_execute_scenario_records_trajectory_fields() -> None:
    """モック生徒モデル+モックツールで TrajectoryRecord に必要フィールドが記録される。"""
    sandbox = IsolatedSandboxStore()
    production = IsolatedSandboxStore()

    async def mock_dispatch(
        scenario: Scenario,
        student_model: str,
        sandbox_store: IsolatedSandboxStore,
    ) -> dict[str, Any]:
        sandbox_store.save("story", "story-abc123456789012345678901", {"title": "新ストーリー"})
        return {
            "steps": [{"role": "assistant", "content": "RICE分析を実施"}],
            "tool_calls": [
                {
                    "tool": "pmdf.create",
                    "args": {"kind": "story", "id": "story-abc123456789012345678901"},
                    "result": {"status": "ok"},
                }
            ],
            "pmdf_diffs": [
                {
                    "kind": "story",
                    "id": "story-abc123456789012345678901",
                    "verb": "create",
                    "after": {"title": "新ストーリー"},
                }
            ],
        }

    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "優先順位を分析します",
                            }
                        }
                    ]
                },
            )
        )
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)
        trajectory = await execute_scenario(
            _sample_scenario(),
            llm_client=llm_client,
            sandbox_store=sandbox,
            production_store=production,
            graph_dispatch=mock_dispatch,
        )

    assert isinstance(trajectory, TrajectoryRecord)
    assert trajectory.steps
    assert trajectory.tool_calls
    assert trajectory.pmdf_diffs
    assert trajectory.model == "pdm-student"
    assert trajectory.scenario_hash


@pytest.mark.asyncio
async def test_execute_scenario_uses_sandbox_only() -> None:
    """実行が隔離ストアのみに書込み、本番相当ストアに影響しない。"""
    sandbox = IsolatedSandboxStore()
    production = IsolatedSandboxStore()

    async def mock_dispatch(
        scenario: Scenario,
        student_model: str,
        sandbox_store: IsolatedSandboxStore,
    ) -> dict[str, Any]:
        sandbox_store.save("story", "story-def456789012345678901234", {"title": "sandbox only"})
        return {"steps": [], "tool_calls": [], "pmdf_diffs": []}

    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
            )
        )
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)
        await execute_scenario(
            _sample_scenario(),
            llm_client=llm_client,
            sandbox_store=sandbox,
            production_store=production,
            graph_dispatch=mock_dispatch,
        )

    assert len(sandbox.entities()) == 1
    assert len(production.entities()) == 0


@pytest.mark.asyncio
async def test_execute_scenario_validates_trajectory_record_schema() -> None:
    """生成 TrajectoryRecord が E8-1 Pydantic モデルでバリデーションを通過する。"""
    sandbox = IsolatedSandboxStore()
    production = IsolatedSandboxStore()

    async def mock_dispatch(
        scenario: Scenario,
        student_model: str,
        sandbox_store: IsolatedSandboxStore,
    ) -> dict[str, Any]:
        return {"steps": [], "tool_calls": [], "pmdf_diffs": []}

    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant", "content": "分析完了"}}]},
            )
        )
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)
        trajectory = await execute_scenario(
            _sample_scenario(),
            llm_client=llm_client,
            sandbox_store=sandbox,
            production_store=production,
            graph_dispatch=mock_dispatch,
        )

    validated = TrajectoryRecord.model_validate(trajectory.model_dump())
    assert validated.scenario_text
    assert validated.provenance.model == "pdm-student"
