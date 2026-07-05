"""eval-runner テスト。"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from eval_runner.bench_schema import BenchCategory, load_bench_dir
from eval_runner.compare import PromotionDecision, compare_models
from eval_runner.deploy_hook import promote_model
from typer.testing import CliRunner

from eval_runner.cli import app

BENCH_DIR = Path(__file__).resolve().parents[1] / "bench"
runner = CliRunner()


def test_bench_dir_has_300_valid_questions() -> None:
    questions = load_bench_dir(BENCH_DIR)
    assert len(questions) >= 300
    by_cat: dict[str, int] = {}
    for q in questions:
        by_cat[q.category.value] = by_cat.get(q.category.value, 0) + 1
    for cat in BenchCategory:
        assert by_cat.get(cat.value, 0) >= 50, (
            f"{cat.value} has {by_cat.get(cat.value, 0)}"
        )


def test_compare_models_promote_on_threshold() -> None:
    baseline = {
        "pdm_knowledge": 60.0,
        "priority_judgment": 60.0,
        "artifact_generation": 60.0,
        "pmdf_accuracy": 60.0,
        "product_project_distinction": 60.0,
        "general_regression": 80.0,
    }
    new = {
        "pdm_knowledge": 75.0,
        "priority_judgment": 75.0,
        "artifact_generation": 75.0,
        "pmdf_accuracy": 75.0,
        "product_project_distinction": 75.0,
        "general_regression": 78.0,
    }
    result = compare_models(baseline, new)
    assert result.decision == PromotionDecision.PROMOTE
    assert result.pdm_delta >= 10.0


def test_compare_models_reject_on_insufficient_pdm_gain() -> None:
    baseline = {c.value: 70.0 for c in BenchCategory}
    new = dict(baseline)
    new["pdm_knowledge"] = 79.0  # avg +1.8 only
    result = compare_models(baseline, new)
    assert result.decision == PromotionDecision.REJECT


def test_compare_models_reject_on_general_regression() -> None:
    baseline = {c.value: 60.0 for c in BenchCategory}
    new = {c.value: 80.0 for c in BenchCategory}
    new["general_regression"] = 50.0  # -10pt regression
    result = compare_models(baseline, new)
    assert result.decision == PromotionDecision.REJECT


@pytest.mark.asyncio
async def test_promote_model_calls_ollama() -> None:
    with respx.mock(base_url="http://ollama.test:11434") as mock:
        mock.post("/api/adapters/load").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await promote_model("/adapters/lora.safetensors", "http://ollama.test:11434")
        assert mock.calls.call_count == 1


def test_cli_run_bench_and_compare(tmp_path: Path) -> None:
    out = tmp_path / "scores.json"
    result = runner.invoke(
        app, ["run-bench", "--output", str(out), "--bench-dir", str(BENCH_DIR)]
    )
    assert result.exit_code == 0
    assert out.is_file()

    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({c.value: 60.0 for c in BenchCategory}),
        encoding="utf-8",
    )
    candidate = tmp_path / "candidate.json"
    candidate.write_text(
        json.dumps({c.value: 80.0 for c in BenchCategory}),
        encoding="utf-8",
    )
    cmp_result = runner.invoke(
        app,
        ["compare", "--baseline", str(baseline), "--candidate", str(candidate)],
    )
    assert cmp_result.exit_code == 0


def test_cli_promote_mock(tmp_path: Path) -> None:
    with respx.mock(base_url="http://127.0.0.1:11434") as mock:
        mock.post("/api/adapters/load").mock(return_value=httpx.Response(200, json={}))
        result = runner.invoke(
            app,
            [
                "promote",
                str(tmp_path / "adapter.bin"),
                "--ollama-url",
                "http://127.0.0.1:11434",
            ],
        )
    assert result.exit_code == 0
