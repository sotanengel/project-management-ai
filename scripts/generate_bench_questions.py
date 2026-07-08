#!/usr/bin/env python3
"""DR-04: ベンチ問題 300 問(6カテゴリ×50)の初期スキャフォールディング用スクリプト。

**警告: このスクリプトを再実行して `services/eval-runner/bench/*.yaml` を
再生成しないこと。**

このスクリプトが生成するのは、各カテゴリで機械的に同一の文言を繰り返す
プレースホルダー("[category] サンプル問題 N: PdM判断を述べよ。")に過ぎない。
`services/eval-runner/bench/*.yaml` は現在、人手/LLMによって作成された
実問題(300問、カテゴリごとに内容・数値・シナリオが異なる実質的な設問と
個別の採点基準)に置き換え済みであり、こちらが正となる唯一の情報源
(source of truth)である。

このスクリプトは「最初にディレクトリ構造とスキーマ形状を用意する」という
初期スキャフォールディングの記録としてのみ残されている。ベンチ問題の
追加・更新が必要な場合は、このスクリプトではなく
`services/eval-runner/bench/*.yaml` を直接編集すること。
"""

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
