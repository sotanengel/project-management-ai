"""E8-3: 生徒モデルがシナリオに回答し軌跡を記録(FR-SL-02)。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from pmdf.learning.contamination import scenario_hash
from pmdf.learning.schemas import RecordProvenance, TrajectoryRecord

from agent_core.learning.synthesize import Scenario
from agent_core.llm_client import LogicalModelClient, LogicalModelName

EXECUTE_PROMPT_VERSION = "e8-3-v1"
DEFAULT_KB_VERSION = "corpus-v1"


class IsolatedSandboxStore:
    """学習実行用の隔離 PMDF ストア(本番ストアを汚染しない)。"""

    def __init__(self) -> None:
        self._entities: dict[str, dict[str, Any]] = {}

    def save(self, kind: str, entity_id: str, entity: dict[str, Any]) -> None:
        self._entities[f"{kind}/{entity_id}"] = dict(entity)

    def entities(self) -> dict[str, dict[str, Any]]:
        return dict(self._entities)


GraphDispatch = Callable[
    [Scenario, str, IsolatedSandboxStore],
    Awaitable[dict[str, Any]],
]


def _scenario_text(scenario: Scenario) -> str:
    return f"状況: {scenario.situation}\n課題: {scenario.task}"


async def _default_graph_dispatch(
    scenario: Scenario,
    student_model: str,
    sandbox_store: IsolatedSandboxStore,
) -> dict[str, Any]:
    """シナリオ種別に応じた最小実行(テストでは注入して上書きする)。"""
    answer_type = scenario.expected_answer_type
    steps = [{"role": "system", "content": f"execute:{answer_type}"}]
    tool_calls: list[dict[str, Any]] = []
    pmdf_diffs: list[dict[str, Any]] = []

    if answer_type in {"priority_judgment", "backlog"}:
        entity_id = "story-learn000000000000000001"
        entity = {
            "id": entity_id,
            "kind": "story",
            "title": scenario.task,
            "acceptance_criteria": ["基準1"],
        }
        sandbox_store.save("story", entity_id, entity)
        tool_calls.append(
            {
                "tool": "pmdf.create",
                "args": {"kind": "story", "id": entity_id},
                "result": {"status": "ok"},
            }
        )
        pmdf_diffs.append({"kind": "story", "id": entity_id, "verb": "create", "after": entity})

    return {"steps": steps, "tool_calls": tool_calls, "pmdf_diffs": pmdf_diffs}


async def execute_scenario(
    scenario: Scenario,
    *,
    llm_client: LogicalModelClient,
    sandbox_store: IsolatedSandboxStore,
    production_store: IsolatedSandboxStore,
    student_model: str = "pdm-student",
    graph_dispatch: GraphDispatch | None = None,
    prompt_template_version: str = EXECUTE_PROMPT_VERSION,
    kb_version: str = DEFAULT_KB_VERSION,
) -> TrajectoryRecord:
    """合成シナリオを生徒モデルで実行し軌跡を記録する。

    本番相当ストア(`production_store`)への書込みは行わず、
    `sandbox_store` のみを対象とする。
    """
    model: LogicalModelName = student_model  # type: ignore[assignment]
    text = _scenario_text(scenario)

    llm_result = await llm_client.complete(
        model=model,
        messages=[
            {"role": "system", "content": "PdM生徒モデルとしてシナリオに回答してください。"},
            {"role": "user", "content": text},
        ],
    )

    reasoning_steps: list[dict[str, Any]] = [
        {"role": "assistant", "content": llm_result.content, "model": student_model}
    ]

    dispatch = graph_dispatch or _default_graph_dispatch
    dispatch_result = await dispatch(scenario, student_model, sandbox_store)

    reasoning_steps.extend(dispatch_result.get("steps", []))
    tool_calls = list(dispatch_result.get("tool_calls", []))
    pmdf_diffs = list(dispatch_result.get("pmdf_diffs", []))

    provenance = RecordProvenance(
        model=student_model,
        prompt_template_version=prompt_template_version,
        kb_version=kb_version,
        generated_at=datetime.now(UTC),
    )

    return TrajectoryRecord(
        scenario_text=text,
        steps=reasoning_steps,
        tool_calls=tool_calls,
        pmdf_diffs=pmdf_diffs,
        model=student_model,
        provenance=provenance,
        scenario_hash=scenario_hash(text),
    )


__all__ = ["GraphDispatch", "IsolatedSandboxStore", "execute_scenario"]
