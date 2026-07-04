"""api_server.costs.usage_store: usage記録(JSONL追記)と集計(E4-3, AR-04)。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest


def _record(**overrides):
    from api_server.costs.usage_store import UsageRecord

    defaults = dict(
        timestamp=datetime(2026, 7, 1, tzinfo=UTC),
        logical_name="pdm-main",
        model="claude-sonnet-4-5",
        prompt_tokens=100,
        completion_tokens=50,
        latency_ms=250.0,
        cost_jpy=15.0,
        actor="agent-core",
    )
    defaults.update(overrides)
    return UsageRecord(**defaults)


def test_append_usage_creates_file_and_appends_jsonl(tmp_path) -> None:
    from api_server.costs.usage_store import append_usage, read_usage_records

    log_path = tmp_path / "usage.jsonl"
    append_usage(_record(), log_path)
    append_usage(_record(cost_jpy=20.0), log_path)

    records = read_usage_records(log_path)
    assert len(records) == 2
    assert records[0].cost_jpy == 15.0
    assert records[1].cost_jpy == 20.0


def test_read_usage_records_returns_empty_list_when_file_missing(tmp_path) -> None:
    from api_server.costs.usage_store import read_usage_records

    assert read_usage_records(tmp_path / "does-not-exist.jsonl") == []


def test_total_spend_sums_cost_jpy(tmp_path) -> None:
    from api_server.costs.usage_store import append_usage, total_spend

    log_path = tmp_path / "usage.jsonl"
    append_usage(_record(cost_jpy=10.0), log_path)
    append_usage(_record(cost_jpy=25.5), log_path)

    assert total_spend(read_records_path=log_path) == pytest.approx(35.5)


def test_summarize_by_model_aggregates_tokens_and_cost(tmp_path) -> None:
    from api_server.costs.usage_store import append_usage, summarize_by_model

    log_path = tmp_path / "usage.jsonl"
    append_usage(
        _record(model="claude-sonnet-4-5", prompt_tokens=100, completion_tokens=50, cost_jpy=10.0),
        log_path,
    )
    append_usage(
        _record(model="claude-sonnet-4-5", prompt_tokens=200, completion_tokens=100, cost_jpy=20.0),
        log_path,
    )
    append_usage(
        _record(model="gpt-4o", prompt_tokens=50, completion_tokens=25, cost_jpy=5.0), log_path
    )

    summary = summarize_by_model(log_path)

    assert summary["claude-sonnet-4-5"].total_tokens == 450
    assert summary["claude-sonnet-4-5"].total_cost_jpy == pytest.approx(30.0)
    assert summary["claude-sonnet-4-5"].call_count == 2
    assert summary["gpt-4o"].total_tokens == 75
    assert summary["gpt-4o"].total_cost_jpy == pytest.approx(5.0)
    assert summary["gpt-4o"].call_count == 1


def test_summarize_by_logical_name_aggregates(tmp_path) -> None:
    from api_server.costs.usage_store import append_usage, summarize_by_logical_name

    log_path = tmp_path / "usage.jsonl"
    append_usage(_record(logical_name="pdm-main", cost_jpy=10.0), log_path)
    append_usage(_record(logical_name="pdm-judge", cost_jpy=3.0), log_path)
    append_usage(_record(logical_name="pdm-main", cost_jpy=7.0), log_path)

    summary = summarize_by_logical_name(log_path)

    assert summary["pdm-main"].total_cost_jpy == pytest.approx(17.0)
    assert summary["pdm-main"].call_count == 2
    assert summary["pdm-judge"].total_cost_jpy == pytest.approx(3.0)


def test_summarize_by_day_aggregates_by_date(tmp_path) -> None:
    from api_server.costs.usage_store import append_usage, summarize_by_day

    log_path = tmp_path / "usage.jsonl"
    append_usage(_record(timestamp=datetime(2026, 7, 1, 9, tzinfo=UTC), cost_jpy=10.0), log_path)
    append_usage(_record(timestamp=datetime(2026, 7, 1, 18, tzinfo=UTC), cost_jpy=5.0), log_path)
    append_usage(_record(timestamp=datetime(2026, 7, 2, 9, tzinfo=UTC), cost_jpy=8.0), log_path)

    summary = summarize_by_day(log_path)

    assert summary["2026-07-01"].total_cost_jpy == pytest.approx(15.0)
    assert summary["2026-07-02"].total_cost_jpy == pytest.approx(8.0)


def test_total_spend_filters_by_month(tmp_path) -> None:
    from api_server.costs.usage_store import append_usage, total_spend

    log_path = tmp_path / "usage.jsonl"
    append_usage(_record(timestamp=datetime(2026, 6, 30, tzinfo=UTC), cost_jpy=100.0), log_path)
    append_usage(_record(timestamp=datetime(2026, 7, 1, tzinfo=UTC), cost_jpy=10.0), log_path)
    append_usage(_record(timestamp=datetime(2026, 7, 15, tzinfo=UTC), cost_jpy=20.0), log_path)

    assert total_spend(read_records_path=log_path, year=2026, month=7) == pytest.approx(30.0)
