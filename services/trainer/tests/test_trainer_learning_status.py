"""trainer.sft / trainer.dpo の学習状況JSONL書き出し(`LEARNING_STATUS_PATH`)。

api-server(`GET /learning/status`)が読み取る共通スキーマ(timestamp/job_type/
status/metrics/decision)に合わせてJSON1行を追記する。環境変数未設定時は
既存の学習ジョブ挙動に影響しないよう何もしない(no-op)。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_sft_write_learning_status_noop_when_env_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from trainer.sft import _write_learning_status

    monkeypatch.delenv("LEARNING_STATUS_PATH", raising=False)
    _write_learning_status("sft", "started")
    # 環境変数未設定時はどこにも書き込まれない(tmp_path配下に何も作られない)
    assert list(tmp_path.iterdir()) == []


def test_sft_write_learning_status_appends_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from trainer.sft import _write_learning_status

    status_path = tmp_path / "learning" / "status.jsonl"
    monkeypatch.setenv("LEARNING_STATUS_PATH", str(status_path))

    _write_learning_status("sft", "started")
    _write_learning_status("sft", "completed", metrics={"train_steps": 10})

    lines = status_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["job_type"] == "sft"
    assert first["status"] == "started"
    assert second["status"] == "completed"
    assert second["metrics"] == {"train_steps": 10}
    assert second["decision"] is None


def test_dpo_write_learning_status_appends_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from trainer.dpo import _write_learning_status

    status_path = tmp_path / "status.jsonl"
    monkeypatch.setenv("LEARNING_STATUS_PATH", str(status_path))

    _write_learning_status("dpo", "completed", metrics={"train_steps": 5})

    lines = status_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["job_type"] == "dpo"
    assert record["status"] == "completed"
    assert record["metrics"] == {"train_steps": 5}


def test_dpo_write_learning_status_noop_when_env_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from trainer.dpo import _write_learning_status

    monkeypatch.delenv("LEARNING_STATUS_PATH", raising=False)
    _write_learning_status("dpo", "started")
    assert list(tmp_path.iterdir()) == []
