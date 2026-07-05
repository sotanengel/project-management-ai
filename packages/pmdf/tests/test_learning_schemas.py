"""E8-1: 学習データスキーマの検証テスト。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pmdf.learning.schemas import (
    ContaminationHit,
    DpoRecord,
    RecordProvenance,
    SftRecord,
    TrajectoryRecord,
)
from pydantic import ValidationError


def _provenance() -> RecordProvenance:
    return RecordProvenance(
        model="pdm-main",
        prompt_template_version="v1.0.0",
        kb_version="kb-2026-01-01",
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_trajectory_record_requires_provenance() -> None:
    with pytest.raises(ValidationError):
        TrajectoryRecord(
            scenario_text="Add login feature",
            steps=[{"role": "user", "content": "plan"}],
            tool_calls=[],
            pmdf_diffs=[],
            model="pdm-main",
            scenario_hash="abc123",
        )


def test_trajectory_record_accepts_valid_payload() -> None:
    record = TrajectoryRecord(
        scenario_text="Add login feature",
        steps=[{"role": "user", "content": "plan"}],
        tool_calls=[{"name": "search", "args": {}}],
        pmdf_diffs=[{"path": "stories/s-1.yaml", "op": "add"}],
        model="pdm-main",
        provenance=_provenance(),
        scenario_hash="abc123",
    )
    assert record.scenario_text == "Add login feature"
    assert record.provenance.model == "pdm-main"


def test_sft_record_requires_provenance() -> None:
    with pytest.raises(ValidationError):
        SftRecord(
            prompt="Write a story",
            completion="Story created",
            trajectory_id="traj-001",
        )


def test_dpo_record_origin_literal() -> None:
    record = DpoRecord(
        prompt="Write a story",
        chosen="Good completion",
        rejected="Bad completion",
        origin="human_feedback",
        provenance=_provenance(),
    )
    assert record.origin == "human_feedback"

    with pytest.raises(ValidationError):
        DpoRecord(
            prompt="Write a story",
            chosen="Good completion",
            rejected="Bad completion",
            origin="invalid_origin",  # type: ignore[arg-type]
            provenance=_provenance(),
        )


def test_contamination_hit_fields() -> None:
    hit = ContaminationHit(
        scenario_hash="deadbeef",
        train_record_id="tr-train-1",
        gate_record_id="tr-gate-1",
    )
    assert hit.scenario_hash == "deadbeef"
