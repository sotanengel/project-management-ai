"""根拠明示の共通機構(`agent_core.evidence`)のテスト(E5-8、FR-PD-13)。

全業務グラフの成果物ペイロード(PMDF書込ペイロード)に、KB出典または
PMDF参照エンティティのいずれかを最低1件`x_evidence`として付与することを
強制する共通ヘルパーの振る舞いを検証する。
"""

from __future__ import annotations

import pytest
from agent_core.evidence import (
    MissingEvidenceError,
    attach_evidence,
    data_evidence,
    evidence_guard,
)
from agent_core.tools.rag_tool import SearchResult


def test_attach_evidence_adds_x_evidence_field_from_search_results() -> None:
    payload = {"kind": "story", "title": "検索高速化"}
    kb_result = SearchResult(
        text="JTBDの説明本文", score=0.9, source="kb", domain="discovery", framework="jtbd"
    )

    result = attach_evidence(payload, [kb_result])

    assert result["x_evidence"] == [
        {"source": "kb", "domain": "discovery", "framework": "jtbd", "excerpt": "JTBDの説明本文"}
    ]
    # 元のpayloadは変更されない(非破壊)。
    assert "x_evidence" not in payload


def test_attach_evidence_accepts_raw_evidence_dicts() -> None:
    payload = {"kind": "story"}

    result = attach_evidence(payload, [{"source": "pmdf", "kind": "persona", "id": "persona-1"}])

    assert result["x_evidence"] == [{"source": "pmdf", "kind": "persona", "id": "persona-1"}]


def test_attach_evidence_merges_search_results_and_raw_dicts() -> None:
    payload = {"kind": "decision"}
    pmdf_result = SearchResult(
        text="", score=None, source="pmdf", pmdf_kind="metric", pmdf_id="metric-1"
    )

    result = attach_evidence(
        payload, [pmdf_result, {"source": "kb", "domain": "d", "framework": None, "excerpt": "x"}]
    )

    assert len(result["x_evidence"]) == 2


def test_data_evidence_builds_data_source_dict() -> None:
    evidence = data_evidence(
        description="RICEスコア計算の入力値",
        data={"reach": 100, "impact": 2, "confidence": 0.8, "effort": 4},
    )

    assert evidence == {
        "source": "data",
        "description": "RICEスコア計算の入力値",
        "data": {"reach": 100, "impact": 2, "confidence": 0.8, "effort": 4},
    }


def test_attach_evidence_accepts_data_evidence() -> None:
    payload = {"kind": "story"}

    result = attach_evidence(payload, [data_evidence(description="計算根拠", data={"reach": 1})])

    assert result["x_evidence"] == [
        {"source": "data", "description": "計算根拠", "data": {"reach": 1}}
    ]


def test_attach_evidence_raises_when_no_evidence_provided() -> None:
    payload = {"kind": "story"}

    with pytest.raises(MissingEvidenceError):
        attach_evidence(payload, [])


def test_attach_evidence_raises_when_evidence_is_none() -> None:
    payload = {"kind": "story"}

    with pytest.raises(MissingEvidenceError):
        attach_evidence(payload, None)


@pytest.mark.asyncio
async def test_evidence_guard_decorator_wraps_async_node_and_requires_evidence() -> None:
    """`evidence_guard`は成果物生成ノードに1行のデコレータ追加で適用できる想定。

    デコレートされた関数は`(payload, evidence)`のタプルを返し、
    `evidence_guard`が`x_evidence`付与済みのpayloadだけを返すようにする。
    """

    @evidence_guard
    async def produce() -> tuple[dict, list]:
        payload = {"kind": "story", "title": "t"}
        evidence = [{"source": "pmdf", "kind": "story", "id": "story-1"}]
        return payload, evidence

    result = await produce()

    assert result["x_evidence"] == [{"source": "pmdf", "kind": "story", "id": "story-1"}]


@pytest.mark.asyncio
async def test_evidence_guard_raises_when_wrapped_node_returns_no_evidence() -> None:
    @evidence_guard
    async def produce_without_evidence() -> tuple[dict, list]:
        return {"kind": "story"}, []

    with pytest.raises(MissingEvidenceError):
        await produce_without_evidence()
