"""ベンチ問題(services/eval-runner/bench/*.yaml)の内容品質テスト。

DR-04: 300問(6カテゴリ×50)がダミー("[category] サンプル問題 N")のまま
置き換えられていないことを検出するための回帰テスト。
"""

from __future__ import annotations

from pathlib import Path

import yaml
from eval_runner.bench_schema import BenchCategory

BENCH_DIR = Path(__file__).resolve().parents[1] / "bench"

CATEGORY_FILES = {
    BenchCategory.PDM_KNOWLEDGE: "pdm_knowledge.yaml",
    BenchCategory.PRIORITY_JUDGMENT: "priority_judgment.yaml",
    BenchCategory.ARTIFACT_GENERATION: "artifact_generation.yaml",
    BenchCategory.PMDF_ACCURACY: "pmdf_accuracy.yaml",
    BenchCategory.PRODUCT_PROJECT_DISTINCTION: "product_project_distinction.yaml",
    BenchCategory.GENERAL_REGRESSION: "general_regression.yaml",
}

# 1ファイル50問中、最低これだけの種類の expected_answer_criteria が
# 存在すること(全問一色の定型句ダミーコンテンツを検出するための閾値)。
MIN_DISTINCT_CRITERIA_PER_FILE = 30


def _load_category(category: BenchCategory) -> list[dict]:
    path = BENCH_DIR / CATEGORY_FILES[category]
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    return raw


def test_each_category_file_has_exactly_50_questions() -> None:
    for category in BenchCategory:
        questions = _load_category(category)
        assert len(questions) == 50, f"{category.value} has {len(questions)}"


def test_total_question_count_is_300() -> None:
    total = sum(len(_load_category(c)) for c in BenchCategory)
    assert total == 300


def test_all_question_texts_are_globally_unique() -> None:
    all_questions: list[str] = []
    for category in BenchCategory:
        for item in _load_category(category):
            all_questions.append(item["question"])
    assert len(all_questions) == len(set(all_questions)), (
        "重複する question 文字列が見つかりました"
    )


def test_expected_answer_criteria_is_not_uniform_dummy() -> None:
    for category in BenchCategory:
        questions = _load_category(category)
        criteria = [q["expected_answer_criteria"] for q in questions]
        distinct = set(criteria)
        assert len(distinct) >= MIN_DISTINCT_CRITERIA_PER_FILE, (
            f"{category.value}: expected_answer_criteria の異なり数が"
            f"{len(distinct)}件しかありません"
            f"(閾値{MIN_DISTINCT_CRITERIA_PER_FILE}件)"
        )


def test_no_question_is_a_placeholder_dummy() -> None:
    for category in BenchCategory:
        for item in _load_category(category):
            assert "サンプル問題" not in item["question"]
            assert item["expected_answer_criteria"] != "価値中心・根拠明示・PMDF整合"
