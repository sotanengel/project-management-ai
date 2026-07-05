"""E8-2: KB+PMDF から PdM シナリオを教師モデルで合成(FR-SL-01)。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pmdf.learning.schemas import RecordProvenance
from pydantic import BaseModel, ConfigDict, Field

from agent_core.llm_client import LogicalModelClient, LogicalModelName

PROMPT_TEMPLATE_VERSION = "e8-2-v1"
DEFAULT_KB_VERSION = "corpus-v1"


class Scenario(BaseModel):
    """合成 PdM シナリオ(状況設定+課題+期待回答種別)。"""

    model_config = ConfigDict(extra="forbid")

    situation: str
    task: str
    expected_answer_type: str
    coverage_tags: list[str] = Field(min_length=1)
    provenance: RecordProvenance


def _build_context(kb_chunks: list[dict[str, Any]], pmdf_samples: list[dict[str, Any]]) -> str:
    kb_lines: list[str] = []
    for chunk in kb_chunks:
        domain = chunk.get("domain", "")
        framework = chunk.get("framework", "")
        title = chunk.get("title", "")
        text = chunk.get("text", chunk.get("body", ""))
        kb_lines.append(f"- [{domain}/{framework}] {title}: {text}")

    pmdf_lines = [
        f"- {sample.get('kind', 'unknown')}/{sample.get('id', '?')}: "
        f"{sample.get('title', sample.get('name', ''))}"
        for sample in pmdf_samples
    ]

    return (
        "KBコンテキスト:\n"
        + ("\n".join(kb_lines) if kb_lines else "(なし)")
        + "\n\nPMDFサンプル:\n"
        + ("\n".join(pmdf_lines) if pmdf_lines else "(なし)")
    )


def _extract_available_tags(kb_chunks: list[dict[str, Any]]) -> set[str]:
    tags: set[str] = set()
    for chunk in kb_chunks:
        if domain := chunk.get("domain"):
            tags.add(f"domain:{domain}")
        if framework := chunk.get("framework"):
            tags.add(f"framework:{framework}")
    return tags


def _parse_scenarios_payload(content: str) -> list[dict[str, Any]]:
    """教師モデルの JSON 応答をパースする。"""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(line for line in lines if not line.strip().startswith("```"))
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "scenarios" in data:
        scenarios = data["scenarios"]
        if isinstance(scenarios, list):
            return scenarios
    raise ValueError("教師モデル応答に scenarios 配列が含まれていません")


async def synthesize_scenarios(
    *,
    kb_chunks: list[dict[str, Any]],
    pmdf_samples: list[dict[str, Any]],
    count: int,
    llm_client: LogicalModelClient,
    teacher_model: str = "pdm-teacher",
    prompt_template_version: str = PROMPT_TEMPLATE_VERSION,
    kb_version: str = DEFAULT_KB_VERSION,
) -> list[Scenario]:
    """KB と匿名化済み PMDF から教師モデルで PdM シナリオを合成する。

    Args:
        kb_chunks: RAG 検索結果または KB メタデータ付きチャンク。
        pmdf_samples: 匿名化済み PMDF エンティティのサンプル。
        count: 生成するシナリオ件数。
        llm_client: model-gateway 経由の LLM クライアント。
        teacher_model: 教師モデル論理名(既定 `pdm-teacher`)。
        prompt_template_version: 来歴管理用プロンプト版。
        kb_version: 来歴管理用 KB 版。

    Returns:
        `coverage_tags` と `provenance` 付きのシナリオ一覧。
    """
    if count < 1:
        return []

    model: LogicalModelName = teacher_model  # type: ignore[assignment]
    context = _build_context(kb_chunks, pmdf_samples)
    available_tags = sorted(_extract_available_tags(kb_chunks))

    system_prompt = (
        "あなたはPdM教師モデルです。与えられたKB/PMDFコンテキストに基づき、"
        "プロダクトマネジメントの実践シナリオを合成してください。"
        "出力はJSONのみ。形式: "
        '{"scenarios": [{"situation": "...", "task": "...", '
        '"expected_answer_type": "priority_judgment|roadmap_tradeoff|'
        'experiment_interpretation|release_decision|...", '
        '"coverage_tags": ["domain:...", "framework:..."]}]}'
    )
    user_prompt = (
        f"{context}\n\n"
        f"上記コンテキストから {count} 件のシナリオを生成してください。\n"
        f"coverage_tags には次のいずれかを使用: {available_tags}\n"
        f"件数は厳密に {count} 件。"
    )

    result = await llm_client.complete(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw_scenarios = _parse_scenarios_payload(result.content)
    generated_at = datetime.now(UTC)
    provenance = RecordProvenance(
        model=teacher_model,
        prompt_template_version=prompt_template_version,
        kb_version=kb_version,
        generated_at=generated_at,
    )

    scenarios: list[Scenario] = []
    for item in raw_scenarios[:count]:
        scenarios.append(
            Scenario(
                situation=str(item["situation"]),
                task=str(item["task"]),
                expected_answer_type=str(item["expected_answer_type"]),
                coverage_tags=[str(t) for t in item["coverage_tags"]],
                provenance=provenance,
            )
        )

    return scenarios


__all__ = ["Scenario", "synthesize_scenarios"]
