"""差戻フィードバック取込(`agent_core.feedback_loop`)のテスト(E5-8、FR-AU-03)。

approvalが差し戻された(`decision == "rejected"`)場合、(1)次回起案時に
差し戻し理由をLLMコンテキストへ注入するためのメッセージを組み立てられる
こと、(2)選好ペア候補として`feedback_queue/`へJSONL形式で記録されること
を検証する。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agent_core.feedback_loop import (
    FeedbackRecord,
    build_rejection_context_message,
    enqueue_feedback,
    on_rejection,
)


def _approval(**overrides: object) -> dict:
    approval: dict = {
        "id": "approval-01HFEEDBACKAAAAAAAAAAAAAAA",
        "target": "roadmap_item-01HTARGETAAAAAAAAAAAAAAAAA",
        "proposer": "stakeholder-01HPROPOSERAAAAAAAAAAAAAAA",
        "approver": "stakeholder-01HAPPROVERAAAAAAAAAAAAAAA",
        "decision": "rejected",
        "reason": "優先度の根拠が不十分です",
    }
    approval.update(overrides)
    return approval


def test_build_rejection_context_message_includes_reason() -> None:
    message = build_rejection_context_message(_approval())

    assert message["role"] == "user"
    assert "優先度の根拠が不十分です" in message["content"]
    assert "roadmap_item-01HTARGETAAAAAAAAAAAAAAAAA" in message["content"]


def test_enqueue_feedback_appends_jsonl_record(tmp_path: Path) -> None:
    queue_dir = tmp_path / "feedback_queue"
    record = FeedbackRecord(
        approval_id="approval-1",
        target="roadmap_item-1",
        original_draft={"theme": "旧テーマ"},
        reason="根拠不足",
        revised_draft=None,
    )

    enqueue_feedback(record, queue_dir=queue_dir)

    files = list(queue_dir.glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["approval_id"] == "approval-1"
    assert data["reason"] == "根拠不足"
    assert data["original_draft"] == {"theme": "旧テーマ"}
    assert data["revised_draft"] is None


def test_enqueue_feedback_appends_multiple_records_to_same_file(tmp_path: Path) -> None:
    queue_dir = tmp_path / "feedback_queue"
    record1 = FeedbackRecord(
        approval_id="approval-1", target="t-1", original_draft={}, reason="r1", revised_draft=None
    )
    record2 = FeedbackRecord(
        approval_id="approval-2", target="t-2", original_draft={}, reason="r2", revised_draft=None
    )

    enqueue_feedback(record1, queue_dir=queue_dir)
    enqueue_feedback(record2, queue_dir=queue_dir)

    files = list(queue_dir.glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


@pytest.mark.asyncio
async def test_on_rejection_ignores_non_rejected_approvals(tmp_path: Path) -> None:
    queue_dir = tmp_path / "feedback_queue"
    approved = _approval(decision="approved")

    injected = await on_rejection(approved, queue_dir=queue_dir)

    assert injected is None
    assert not queue_dir.exists() or not list(queue_dir.glob("*.jsonl"))


@pytest.mark.asyncio
async def test_on_rejection_enqueues_and_returns_context_message(tmp_path: Path) -> None:
    queue_dir = tmp_path / "feedback_queue"
    rejected = _approval()

    injected = await on_rejection(
        rejected, queue_dir=queue_dir, original_draft={"theme": "旧テーマ"}
    )

    assert injected is not None
    assert "優先度の根拠が不十分です" in injected["content"]

    files = list(queue_dir.glob("*.jsonl"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8").strip().splitlines()[0])
    assert data["approval_id"] == rejected["id"]
    assert data["target"] == rejected["target"]
    assert data["original_draft"] == {"theme": "旧テーマ"}
