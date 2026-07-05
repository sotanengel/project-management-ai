"""E8-8: 新旧モデル比較・昇格判定(AC-04)。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from eval_runner.bench_schema import BenchCategory, PDM_CATEGORIES

PDM_IMPROVEMENT_THRESHOLD = 10.0
GENERAL_REGRESSION_TOLERANCE = 5.0


class PromotionDecision(str, Enum):
    PROMOTE = "promote"
    REJECT = "reject"


class ComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: PromotionDecision
    pdm_baseline_avg: float
    pdm_new_avg: float
    pdm_delta: float
    general_baseline: float
    general_new: float
    general_delta: float
    reasons: list[str] = Field(default_factory=list)


def _category_avg(scores: dict[str, float], categories: set[BenchCategory]) -> float:
    values = [scores[c.value] for c in categories if c.value in scores]
    if not values:
        return 0.0
    return sum(values) / len(values)


def compare_models(
    baseline_scores: dict[str, float],
    new_scores: dict[str, float],
) -> ComparisonResult:
    """カテゴリ別スコアから昇格可否を判定する。"""
    pdm_baseline = _category_avg(baseline_scores, PDM_CATEGORIES)
    pdm_new = _category_avg(new_scores, PDM_CATEGORIES)
    pdm_delta = pdm_new - pdm_baseline

    general_baseline = baseline_scores.get(BenchCategory.GENERAL_REGRESSION.value, 0.0)
    general_new = new_scores.get(BenchCategory.GENERAL_REGRESSION.value, 0.0)
    general_delta = general_new - general_baseline

    reasons: list[str] = []
    promote = True

    if pdm_delta < PDM_IMPROVEMENT_THRESHOLD:
        promote = False
        reasons.append(
            f"PdMベンチ改善不足: {pdm_delta:.1f}pt < {PDM_IMPROVEMENT_THRESHOLD}pt"
        )

    if general_delta < -GENERAL_REGRESSION_TOLERANCE:
        promote = False
        reasons.append(
            f"一般能力回帰超過: {general_delta:.1f}pt < -{GENERAL_REGRESSION_TOLERANCE}pt"
        )

    if promote:
        reasons.append("閾値を満たしたため昇格")

    return ComparisonResult(
        decision=PromotionDecision.PROMOTE if promote else PromotionDecision.REJECT,
        pdm_baseline_avg=pdm_baseline,
        pdm_new_avg=pdm_new,
        pdm_delta=pdm_delta,
        general_baseline=general_baseline,
        general_new=general_new,
        general_delta=general_delta,
        reasons=reasons,
    )
