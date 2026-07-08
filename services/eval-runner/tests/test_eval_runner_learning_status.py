"""eval_runner.cli の学習状況JSONL書き出し(`LEARNING_STATUS_PATH`)。

`compare` コマンドで昇格/却下判定が確定したタイミングでapi-serverと共通の
スキーマ(timestamp/job_type/status/metrics/decision)でJSON1行を追記する。
環境変数未設定時はno-op。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from eval_runner.bench_schema import BenchCategory
from typer.testing import CliRunner

from eval_runner.cli import app

runner = CliRunner()


def test_write_learning_status_noop_when_env_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eval_runner.cli import _write_learning_status

    monkeypatch.delenv("LEARNING_STATUS_PATH", raising=False)
    _write_learning_status("eval", "completed", decision="promote")
    assert list(tmp_path.iterdir()) == []


def test_write_learning_status_appends_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eval_runner.cli import _write_learning_status

    status_path = tmp_path / "status.jsonl"
    monkeypatch.setenv("LEARNING_STATUS_PATH", str(status_path))

    _write_learning_status(
        "eval", "completed", metrics={"pdm_delta": 12.0}, decision="promote"
    )

    lines = status_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["job_type"] == "eval"
    assert record["decision"] == "promote"
    assert record["metrics"] == {"pdm_delta": 12.0}


def test_compare_cmd_writes_learning_status_on_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    status_path = tmp_path / "status.jsonl"
    monkeypatch.setenv("LEARNING_STATUS_PATH", str(status_path))

    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({c.value: 60.0 for c in BenchCategory}), encoding="utf-8"
    )
    candidate = tmp_path / "candidate.json"
    candidate.write_text(
        json.dumps({c.value: 80.0 for c in BenchCategory}), encoding="utf-8"
    )

    result = runner.invoke(
        app, ["compare", "--baseline", str(baseline), "--candidate", str(candidate)]
    )
    assert result.exit_code == 0

    lines = status_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["job_type"] == "eval"
    assert record["decision"] == "promote"
