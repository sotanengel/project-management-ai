"""E8-8: ベンチ問題スキーマ(DR-04)。"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class BenchCategory(str, Enum):
    PDM_KNOWLEDGE = "pdm_knowledge"
    PRIORITY_JUDGMENT = "priority_judgment"
    ARTIFACT_GENERATION = "artifact_generation"
    PMDF_ACCURACY = "pmdf_accuracy"
    PRODUCT_PROJECT_DISTINCTION = "product_project_distinction"
    GENERAL_REGRESSION = "general_regression"


PDM_CATEGORIES = {
    BenchCategory.PDM_KNOWLEDGE,
    BenchCategory.PRIORITY_JUDGMENT,
    BenchCategory.ARTIFACT_GENERATION,
    BenchCategory.PMDF_ACCURACY,
    BenchCategory.PRODUCT_PROJECT_DISTINCTION,
}


class BenchQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: BenchCategory
    question: str
    expected_answer_criteria: str
    scoring_method: str = Field(default="rubric_1_5")


def load_bench_dir(bench_dir: Path) -> list[BenchQuestion]:
    """bench/ 配下の YAML/JSON を全読込・検証。"""
    questions: list[BenchQuestion] = []
    for path in sorted(bench_dir.rglob("*")):
        if path.suffix not in {".yaml", ".yml", ".json"}:
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            for item in raw:
                questions.append(BenchQuestion.model_validate(item))
        else:
            questions.append(BenchQuestion.model_validate(raw))
    return questions
