"""E8-5: 人間フィードバック(DPO)取込(FR-SL-04)。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pmdf.learning.schemas import DpoRecord, RecordProvenance

from agent_core.feedback_loop import FeedbackRecord
from agent_core.learning.anonymize import anonymize_text

DEFAULT_PROMPT_VERSION = "e8-5-v1"
DEFAULT_KB_VERSION = "corpus-v1"


def _draft_to_text(draft: dict[str, Any] | None) -> str:
    if not draft:
        return ""
    return json.dumps(draft, ensure_ascii=False, sort_keys=True)


def _build_provenance(*, model: str = "human_feedback") -> RecordProvenance:
    return RecordProvenance(
        model=model,
        prompt_template_version=DEFAULT_PROMPT_VERSION,
        kb_version=DEFAULT_KB_VERSION,
        generated_at=datetime.now(UTC),
    )


def collect_preference_pairs_from_queue(
    queue_dir: Path,
    *,
    model: str = "human_feedback",
) -> list[DpoRecord]:
    """feedback_queue/ の JSONL から DpoRecord を構築する。"""
    records: list[DpoRecord] = []
    if not queue_dir.is_dir():
        return records

    for path in sorted(queue_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            feedback = FeedbackRecord(
                approval_id=raw["approval_id"],
                target=raw["target"],
                original_draft=raw["original_draft"],
                reason=raw["reason"],
                revised_draft=raw.get("revised_draft"),
            )
            records.extend(
                _feedback_to_dpo(feedback, model=model),
            )
    return records


def _feedback_to_dpo(feedback: FeedbackRecord, *, model: str) -> list[DpoRecord]:
    """差し戻しペアを DpoRecord に変換(必ず匿名化)。"""
    rejected = _draft_to_text(feedback.original_draft)
    chosen_source = feedback.revised_draft or feedback.original_draft
    chosen = _draft_to_text(chosen_source)
    prompt = anonymize_text(f"対象: {feedback.target}\n差し戻し理由: {feedback.reason}")
    chosen_anon = anonymize_text(chosen)
    rejected_anon = anonymize_text(rejected)

    record = DpoRecord(
        prompt=prompt,
        chosen=chosen_anon,
        rejected=rejected_anon,
        origin="human_feedback",
        provenance=_build_provenance(model=model),
    )
    return [record]


__all__ = ["collect_preference_pairs_from_queue"]
