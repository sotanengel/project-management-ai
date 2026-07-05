"""E8-4: ルールベース+LLM-as-Judge ハイブリッド評価(FR-SL-03)。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pmdf.learning.schemas import TrajectoryRecord
from pmdf.models import Decision
from pmdf.schema_registry import validate_entity
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from agent_core.graphs.backlog import calc_rice_score, calc_wsjf_score
from agent_core.llm_client import LogicalModelClient, LogicalModelName

RUBRIC_PATH = (
    Path(__file__).resolve().parents[5]
    / "packages"
    / "pmdf"
    / "src"
    / "pmdf"
    / "learning"
    / "rubrics"
    / "value_centric.md"
)

DECISION_REQUIRED = (
    "background",
    "options",
    "chosen_option",
    "rationale",
    "rejected_reasons",
)


class RuleCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    failures: list[str] = Field(default_factory=list)


class JudgeScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value_for_whom: int = Field(ge=1, le=5)
    output_outcome_value_distinction: int = Field(ge=1, le=5)
    tradeoff_clarity: int = Field(ge=1, le=5)


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    rule_result: RuleCheckResult
    judge_score: JudgeScore | None = None


def _load_rubric() -> str:
    return RUBRIC_PATH.read_text(encoding="utf-8")


def _parse_judge_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(line for line in lines if not line.strip().startswith("```"))
    return json.loads(text)


def _check_priority_score(entity: dict[str, Any], failures: list[str]) -> None:
    priority = entity.get("priority")
    if not isinstance(priority, dict):
        return
    method = priority.get("method")
    score = priority.get("score")
    if score is None or method not in {"RICE", "WSJF"}:
        return
    try:
        if method == "RICE":
            expected = calc_rice_score(
                reach=float(priority["reach"]),
                impact=float(priority["impact"]),
                confidence=float(priority["confidence"]),
                effort=float(priority["effort"]),
            )
        else:
            expected = calc_wsjf_score(
                business_value=float(priority["business_value"]),
                time_criticality=float(priority["time_criticality"]),
                risk_reduction=float(priority["risk_reduction"]),
                job_size=float(priority["job_size"]),
            )
    except (KeyError, TypeError, ValueError) as exc:
        failures.append(f"priority 検算不能: {exc}")
        return
    if abs(float(score) - expected) > 1e-6:
        failures.append(f"{method} score 不一致: 提示={score}, 検算={expected}")


def _check_story(entity: dict[str, Any], failures: list[str]) -> None:
    criteria = entity.get("acceptance_criteria")
    if not criteria:
        failures.append("story の acceptance_criteria が空")
    elif isinstance(criteria, list) and len(criteria) < 1:
        failures.append("story の acceptance_criteria が不足")


def _check_decision(entity: dict[str, Any], failures: list[str]) -> None:
    for field in DECISION_REQUIRED:
        if not entity.get(field):
            failures.append(f"decision の必須項目 {field!r} が欠落")
    try:
        Decision.model_validate(entity)
    except PydanticValidationError as exc:
        failures.append(f"decision スキーマ不適合: {exc.errors()[0]['msg']}")


def rule_based_checks(trajectory: TrajectoryRecord) -> RuleCheckResult:
    """PMDF スキーマ・RICE/WSJF 検算・受入基準・DR 必須項目を検証する。"""
    failures: list[str] = []

    for diff in trajectory.pmdf_diffs:
        entity = diff.get("after") or diff.get("entity") or diff
        if not isinstance(entity, dict):
            continue
        kind = entity.get("kind") or diff.get("kind")
        if not kind:
            continue
        try:
            validate_entity(entity, kind=str(kind))
        except Exception as exc:  # noqa: BLE001 — jsonschema ValidationError 等
            failures.append(f"{kind} スキーマ不適合: {exc}")

        if kind == "story":
            _check_story(entity, failures)
            _check_priority_score(entity, failures)
        elif kind == "decision":
            _check_decision(entity, failures)

    return RuleCheckResult(passed=len(failures) == 0, failures=failures)


async def llm_judge_score(
    trajectory: TrajectoryRecord,
    *,
    llm_client: LogicalModelClient,
    judge_model: str = "pdm-judge",
    rubric: str | None = None,
) -> JudgeScore:
    """価値中心ルーブリックで LLM-as-Judge 採点。"""
    model: LogicalModelName = judge_model  # type: ignore[assignment]
    rubric_text = rubric or _load_rubric()
    prompt = (
        f"{rubric_text}\n\n"
        "以下の軌跡(JSON)を上記ルーブリックで採点し、JSONのみ返してください。\n"
        f"{json.dumps(trajectory.model_dump(mode='json'), ensure_ascii=False)}"
    )
    result = await llm_client.complete(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    parsed = _parse_judge_json(result.content)
    return JudgeScore.model_validate(parsed)


async def hybrid_evaluate(
    trajectory: TrajectoryRecord,
    *,
    llm_client: LogicalModelClient,
    judge_model: str = "pdm-judge",
) -> EvaluationResult:
    """ルールベース+ジャッジの統合評価。ルール不合格は最終不合格。"""
    rule_result = rule_based_checks(trajectory)
    if not rule_result.passed:
        return EvaluationResult(
            passed=False,
            rule_result=rule_result,
            judge_score=None,
        )

    judge_score = await llm_judge_score(
        trajectory,
        llm_client=llm_client,
        judge_model=judge_model,
    )
    min_score = min(
        judge_score.value_for_whom,
        judge_score.output_outcome_value_distinction,
        judge_score.tradeoff_clarity,
    )
    passed = min_score >= 3
    return EvaluationResult(
        passed=passed,
        rule_result=rule_result,
        judge_score=judge_score,
    )


__all__ = [
    "EvaluationResult",
    "JudgeScore",
    "RuleCheckResult",
    "hybrid_evaluate",
    "llm_judge_score",
    "rule_based_checks",
]
