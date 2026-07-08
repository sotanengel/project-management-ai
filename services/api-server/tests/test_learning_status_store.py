"""api_server.learning.status_store: 学習状況記録(JSONL追記)と集計(E8-8関連)。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest


def _record(**overrides):
    from api_server.learning.status_store import LearningStatusRecord

    defaults = dict(
        timestamp=datetime(2026, 7, 1, tzinfo=UTC),
        job_type="sft",
        status="completed",
        metrics={},
        decision=None,
    )
    defaults.update(overrides)
    return LearningStatusRecord(**defaults)


def test_append_status_creates_file_and_appends_jsonl(tmp_path) -> None:
    from api_server.learning.status_store import append_status, read_status_records

    log_path = tmp_path / "status.jsonl"
    append_status(_record(), log_path)
    append_status(_record(job_type="dpo"), log_path)

    records = read_status_records(log_path)
    assert len(records) == 2
    assert records[0].job_type == "sft"
    assert records[1].job_type == "dpo"


def test_read_status_records_returns_empty_list_when_file_missing(tmp_path) -> None:
    from api_server.learning.status_store import read_status_records

    assert read_status_records(tmp_path / "does-not-exist.jsonl") == []


def test_summarize_learning_status_empty_when_file_missing(tmp_path) -> None:
    from api_server.learning.status_store import summarize_learning_status

    summary = summarize_learning_status(tmp_path / "does-not-exist.jsonl")
    assert summary.latest_job is None
    assert summary.gate_history == []


def test_summarize_learning_status_returns_latest_job(tmp_path) -> None:
    from api_server.learning.status_store import append_status, summarize_learning_status

    log_path = tmp_path / "status.jsonl"
    append_status(
        _record(timestamp=datetime(2026, 7, 1, tzinfo=UTC), job_type="sft", status="completed"),
        log_path,
    )
    append_status(
        _record(timestamp=datetime(2026, 7, 2, tzinfo=UTC), job_type="dpo", status="completed"),
        log_path,
    )

    summary = summarize_learning_status(log_path)
    assert summary.latest_job is not None
    assert summary.latest_job.job_type == "dpo"


def test_summarize_learning_status_collects_eval_gate_history(tmp_path) -> None:
    from api_server.learning.status_store import append_status, summarize_learning_status

    log_path = tmp_path / "status.jsonl"
    append_status(_record(job_type="sft", status="completed"), log_path)
    append_status(
        _record(
            job_type="eval",
            status="completed",
            decision="promote",
            metrics={"pdm_delta": 12.0},
        ),
        log_path,
    )
    append_status(
        _record(
            job_type="eval",
            status="completed",
            decision="reject",
            metrics={"pdm_delta": 2.0},
        ),
        log_path,
    )

    summary = summarize_learning_status(log_path)
    assert len(summary.gate_history) == 2
    assert summary.gate_history[0].decision == "promote"
    assert summary.gate_history[1].decision == "reject"


@pytest.mark.parametrize("bad_job_type", ["training", ""])
def test_learning_status_record_rejects_invalid_job_type(bad_job_type) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _record(job_type=bad_job_type)
