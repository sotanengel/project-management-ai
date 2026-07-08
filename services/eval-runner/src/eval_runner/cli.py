"""E8-8: eval-runner CLI(FR-SL-09)。"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer

from eval_runner.bench_schema import load_bench_dir
from eval_runner.compare import PromotionDecision, compare_models
from eval_runner.deploy_hook import promote_model

app = typer.Typer(help="評価ゲート eval-runner (E8-8)")

DEFAULT_BENCH = Path(__file__).resolve().parents[2] / "bench"


def _write_learning_status(
    job_type: str,
    status: str,
    *,
    metrics: dict[str, Any] | None = None,
    decision: str | None = None,
) -> None:
    """`LEARNING_STATUS_PATH`が設定されている場合のみ、学習状況をJSONL追記する(E8-8関連)。

    api-server(`GET /learning/status`)が読み取る共通スキーマ(timestamp/job_type/
    status/metrics/decision)に合わせる。trainerとは別ワークスペースパッケージのため
    api_server.learning.status_storeを直接importせず、同一スキーマのJSONを自前で
    書き出す。未設定時は既存の評価ジョブ挙動に影響しないよう何もしない。
    """
    path = os.environ.get("LEARNING_STATUS_PATH")
    if not path:
        return
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "job_type": job_type,
        "status": status,
        "metrics": metrics or {},
        "decision": decision,
    }
    status_path = Path(path)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    with status_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


@app.command("run-bench")
def run_bench(
    bench_dir: Path = typer.Option(DEFAULT_BENCH, help="ベンチ問題ディレクトリ"),
    output: Path = typer.Option(..., help="スコア出力 JSON パス"),
) -> None:
    """ベンチ問題を読込み、プレースホルダスコア(カテゴリ平均70)を出力。"""
    questions = load_bench_dir(bench_dir)
    categories = {q.category.value for q in questions}
    scores = {cat: 70.0 for cat in categories}
    output.write_text(json.dumps(scores, indent=2), encoding="utf-8")
    typer.echo(f"Wrote placeholder scores for {len(categories)} categories -> {output}")


@app.command("compare")
def compare_cmd(
    baseline: Path = typer.Option(..., help="ベースラインスコア JSON"),
    candidate: Path = typer.Option(..., help="新モデルスコア JSON"),
) -> None:
    """新旧スコアを比較し昇格判定を表示。"""
    baseline_scores = json.loads(baseline.read_text(encoding="utf-8"))
    new_scores = json.loads(candidate.read_text(encoding="utf-8"))
    result = compare_models(baseline_scores, new_scores)
    typer.echo(result.model_dump_json(indent=2))
    _write_learning_status(
        "eval",
        "completed",
        metrics={
            "pdm_baseline_avg": result.pdm_baseline_avg,
            "pdm_new_avg": result.pdm_new_avg,
            "pdm_delta": result.pdm_delta,
            "general_baseline": result.general_baseline,
            "general_new": result.general_new,
            "general_delta": result.general_delta,
        },
        decision=result.decision.value,
    )
    raise typer.Exit(code=0 if result.decision == PromotionDecision.PROMOTE else 1)


@app.command("promote")
def promote_cmd(
    adapter_path: str = typer.Argument(..., help="LoRA アダプタパス"),
    ollama_url: str = typer.Option("http://localhost:11434", help="Ollama URL"),
) -> None:
    """Ollama へアダプタ差替リクエストを送る。"""
    import asyncio

    asyncio.run(promote_model(adapter_path, ollama_url))
    typer.echo(f"Promoted adapter {adapter_path}")
