"""E8-4: ハイブリッド評価のテスト。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from agent_core.learning.evaluate import (
    EvaluationResult,
    hybrid_evaluate,
    llm_judge_score,
    rule_based_checks,
)
from agent_core.llm_client import LogicalModelClient
from pmdf.learning.schemas import RecordProvenance, TrajectoryRecord

MODEL_GATEWAY_URL = "http://model-gateway.test:4000"
STORY_ID = "story-01JZX4T8G2K9V6R5N4M3P2Q1R0"
PRODUCT_ID = "prod-01JZX0AAAA01BBBBCCCCDDDDEE"

PROVENANCE = RecordProvenance(
    model="pdm-student",
    prompt_template_version="e8-3-v1",
    kb_version="corpus-v1",
    generated_at=datetime(2026, 7, 5, tzinfo=UTC),
)


def _trajectory(*, pmdf_diffs: list[dict], steps: list[dict] | None = None) -> TrajectoryRecord:
    return TrajectoryRecord(
        scenario_text="状況: test\n課題: test",
        steps=steps or [],
        tool_calls=[],
        pmdf_diffs=pmdf_diffs,
        model="pdm-student",
        provenance=PROVENANCE,
        scenario_hash="abc123",
    )


def _valid_story_entity(**overrides: Any) -> dict[str, Any]:
    entity = {
        "pmdf_version": "1.0.0",
        "kind": "story",
        "id": STORY_ID,
        "product": PRODUCT_ID,
        "provenance": {
            "created_by": "agent:learning@v1.0",
            "approved_by": None,
            "updated_at": "2026-07-05T00:00:00+00:00",
        },
        "attachments": [],
        "title": "検索改善",
        "as_a": "ユーザー",
        "i_want": "高速検索",
        "so_that": "待ち時間を減らす",
        "acceptance_criteria": ["3秒以内"],
        "priority": {
            "method": "RICE",
            "reach": 10,
            "impact": 2,
            "confidence": 0.8,
            "effort": 4,
            "score": 4.0,
        },
        "status": "ready",
    }
    entity.update(overrides)
    return entity


def test_rule_based_checks_passes_valid_rice_story() -> None:
    """正しい RICE スコアを持つ軌跡が rule_based_checks で合格する。"""
    trajectory = _trajectory(
        pmdf_diffs=[
            {
                "kind": "story",
                "id": STORY_ID,
                "verb": "create",
                "after": _valid_story_entity(),
            }
        ]
    )
    result = rule_based_checks(trajectory)
    assert result.passed is True
    assert result.failures == []


def test_rule_based_checks_fails_rice_mismatch() -> None:
    """検算不一致の score を持つ軌跡が不合格になる。"""
    trajectory = _trajectory(
        pmdf_diffs=[
            {
                "kind": "story",
                "id": STORY_ID,
                "verb": "create",
                "after": _valid_story_entity(
                    priority={
                        "method": "RICE",
                        "reach": 10,
                        "impact": 2,
                        "confidence": 0.8,
                        "effort": 4,
                        "score": 99.0,
                    }
                ),
            }
        ]
    )
    result = rule_based_checks(trajectory)
    assert result.passed is False
    assert any("RICE" in f for f in result.failures)


@pytest.mark.asyncio
async def test_llm_judge_score_parses_three_dimensions() -> None:
    """モックジャッジ応答から 3 観点のスコアをパースする。"""
    judge_json = json.dumps(
        {
            "value_for_whom": 4,
            "output_outcome_value_distinction": 3,
            "tradeoff_clarity": 5,
        }
    )
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant", "content": judge_json}}]},
            )
        )
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)
        score = await llm_judge_score(
            _trajectory(pmdf_diffs=[]),
            llm_client=llm_client,
        )

    assert score.value_for_whom == 4
    assert score.output_outcome_value_distinction == 3
    assert score.tradeoff_clarity == 5


@pytest.mark.asyncio
async def test_hybrid_evaluate_fails_when_rules_fail_despite_high_judge() -> None:
    """ルールベース不合格の軌跡はジャッジ呼び出し前に総合不合格。"""
    trajectory = _trajectory(
        pmdf_diffs=[
            {
                "kind": "story",
                "id": STORY_ID,
                "verb": "create",
                "after": _valid_story_entity(
                    acceptance_criteria=[],
                    priority={
                        "method": "RICE",
                        "reach": 1,
                        "impact": 1,
                        "confidence": 1,
                        "effort": 1,
                        "score": 999,
                    },
                ),
            }
        ]
    )
    llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)
    result = await hybrid_evaluate(trajectory, llm_client=llm_client)

    assert isinstance(result, EvaluationResult)
    assert result.passed is False
    assert result.rule_result.passed is False
    assert result.judge_score is None


def test_rubric_file_exists() -> None:
    rubric = (
        Path(__file__).resolve().parents[3]
        / "packages"
        / "pmdf"
        / "src"
        / "pmdf"
        / "learning"
        / "rubrics"
        / "value_centric.md"
    )
    assert rubric.is_file()
    assert "value_for_whom" in rubric.read_text(encoding="utf-8")
