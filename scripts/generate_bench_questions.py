#!/usr/bin/env python3
"""DR-04: ベンチ問題 300 問(6カテゴリ×50)を生成する。"""

from __future__ import annotations

from pathlib import Path

import yaml

CATEGORIES = [
    "pdm_knowledge",
    "priority_judgment",
    "artifact_generation",
    "pmdf_accuracy",
    "product_project_distinction",
    "general_regression",
]

BENCH_ROOT = Path(__file__).resolve().parents[1] / "services" / "eval-runner" / "bench"


def main() -> None:
    BENCH_ROOT.mkdir(parents=True, exist_ok=True)
    for category in CATEGORIES:
        questions = []
        for i in range(1, 51):
            qid = f"{category}-{i:03d}"
            questions.append(
                {
                    "id": qid,
                    "category": category,
                    "question": f"[{category}] サンプル問題 {i}: PdM判断を述べよ。",
                    "expected_answer_criteria": "価値中心・根拠明示・PMDF整合",
                    "scoring_method": "rubric_1_5",
                }
            )
        path = BENCH_ROOT / f"{category}.yaml"
        path.write_text(
            yaml.dump(questions, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        print(f"Wrote {path} ({len(questions)} questions)")


if __name__ == "__main__":
    main()
