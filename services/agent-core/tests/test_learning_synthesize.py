"""E8-2: タスク合成(`synthesize_scenarios`)のテスト。"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from agent_core.learning.synthesize import Scenario, synthesize_scenarios
from agent_core.llm_client import LogicalModelClient

MODEL_GATEWAY_URL = "http://model-gateway.test:4000"

KB_CHUNKS = [
    {
        "domain": "discovery",
        "framework": "lean_startup",
        "title": "仮説検証",
        "text": "実験設計の基本",
    },
    {
        "domain": "backlog",
        "framework": "rice",
        "title": "優先順位",
        "text": "RICEスコアリング",
    },
]

PMDF_SAMPLES = [
    {"kind": "story", "id": "story-01", "title": "サンプルストーリー"},
]


def _teacher_response(scenarios: list[dict[str, Any]]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-synth",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({"scenarios": scenarios}, ensure_ascii=False),
                    },
                    "finish_reason": "stop",
                }
            ],
        },
    )


@pytest.mark.asyncio
async def test_synthesize_scenarios_generates_requested_count() -> None:
    """モック教師モデル応答から指定件数のシナリオが生成される。"""
    mock_scenarios = [
        {
            "situation": "新機能の優先順位を決める必要がある",
            "task": "RICEで3ストーリーを比較せよ",
            "expected_answer_type": "priority_judgment",
            "coverage_tags": ["domain:backlog", "framework:rice"],
        },
        {
            "situation": "実験結果を解釈する",
            "task": "A/Bテスト結果から次アクションを提案せよ",
            "expected_answer_type": "experiment_interpretation",
            "coverage_tags": ["domain:discovery", "framework:lean_startup"],
        },
    ]
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_teacher_response(mock_scenarios))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)
        result = await synthesize_scenarios(
            kb_chunks=KB_CHUNKS,
            pmdf_samples=PMDF_SAMPLES,
            count=2,
            llm_client=llm_client,
        )

    assert len(result) == 2
    assert all(isinstance(s, Scenario) for s in result)


@pytest.mark.asyncio
async def test_synthesize_scenarios_coverage_tags_match_kb_metadata() -> None:
    """各シナリオが coverage_tags を持ち KB メタデータと対応する。"""
    mock_scenarios = [
        {
            "situation": "バックログ整理",
            "task": "WSJFで順位付け",
            "expected_answer_type": "priority_judgment",
            "coverage_tags": ["domain:backlog", "framework:rice"],
        },
    ]
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_teacher_response(mock_scenarios))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)
        result = await synthesize_scenarios(
            kb_chunks=KB_CHUNKS,
            pmdf_samples=PMDF_SAMPLES,
            count=1,
            llm_client=llm_client,
        )

    assert result[0].coverage_tags == ["domain:backlog", "framework:rice"]
    assert "domain:backlog" in result[0].coverage_tags
    assert "framework:rice" in result[0].coverage_tags


@pytest.mark.asyncio
async def test_synthesize_scenarios_records_provenance() -> None:
    """provenance に教師モデル論理名・生成日時が記録される。"""
    mock_scenarios = [
        {
            "situation": "リリース判断",
            "task": "Go/No-Goを判断",
            "expected_answer_type": "release_decision",
            "coverage_tags": ["domain:release"],
        },
    ]
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_teacher_response(mock_scenarios))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)
        result = await synthesize_scenarios(
            kb_chunks=KB_CHUNKS,
            pmdf_samples=PMDF_SAMPLES,
            count=1,
            teacher_model="pdm-teacher",
            llm_client=llm_client,
        )

    prov = result[0].provenance
    assert prov.model == "pdm-teacher"
    assert prov.prompt_template_version
    assert prov.kb_version
    assert prov.generated_at is not None
