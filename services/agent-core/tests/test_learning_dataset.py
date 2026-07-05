"""E8-5/E8-6: データパイプラインのテスト。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from agent_core.learning.anonymize import anonymize_text
from agent_core.learning.dataset_builder import (
    OptInStore,
    ProductOptIn,
    build_dpo_dataset,
    build_sft_dataset,
    exclude_shared_bundle_records,
    filter_by_opt_in,
    is_from_shared_bundle,
)
from agent_core.learning.evaluate import EvaluationResult, RuleCheckResult
from agent_core.learning.feedback_ingest import collect_preference_pairs_from_queue
from pmdf.learning.schemas import DpoRecord, RecordProvenance, TrajectoryRecord

FIXTURES = Path(__file__).parent / "fixtures"
PROVENANCE = RecordProvenance(
    model="pdm-student",
    prompt_template_version="e8-3-v1",
    kb_version="corpus-v1",
    generated_at=datetime(2026, 7, 5, tzinfo=UTC),
)
SHARED_PROVENANCE = RecordProvenance(
    model="import",
    prompt_template_version="e8-3-v1",
    kb_version="shared_bundle:external",
    generated_at=datetime(2026, 7, 5, tzinfo=UTC),
)


def _trajectory(**kwargs: object) -> TrajectoryRecord:
    data = {
        "scenario_text": "状況: t\n課題: t",
        "steps": [{"role": "assistant", "content": "回答"}],
        "tool_calls": [],
        "pmdf_diffs": [],
        "model": "pdm-student",
        "provenance": PROVENANCE,
        "scenario_hash": "hash1",
    }
    data.update(kwargs)
    return TrajectoryRecord.model_validate(data)


def test_collect_preference_pairs_from_queue(tmp_path: Path) -> None:
    sample = (FIXTURES / "feedback_queue_sample.jsonl").read_text(encoding="utf-8")
    (tmp_path / "2026-07-05.jsonl").write_text(sample, encoding="utf-8")
    records = collect_preference_pairs_from_queue(tmp_path)
    assert len(records) == 1
    assert records[0].origin == "human_feedback"
    assert records[0].prompt
    assert records[0].chosen
    assert records[0].rejected


def test_anonymize_text_masks_pii() -> None:
    text = "担当: 田中太郎 taro@example.com 株式会社サンプル 03-1234-5678"
    masked = anonymize_text(text)
    assert "taro@example.com" not in masked
    assert "株式会社サンプル" not in masked
    assert "03-1234-5678" not in masked
    assert "[REDACTED]" in masked


def test_human_feedback_records_are_anonymized(tmp_path: Path) -> None:
    raw = {
        "approval_id": "appr-01JZX4T8G2K9V6R5N4M3P2Q1R0",
        "target": "story-01JZX4T8G2K9V6R5N4M3P2Q1R0",
        "original_draft": {"note": "山田花子が作成"},
        "reason": "contact: hanako@corp.jp",
        "revised_draft": None,
    }
    (tmp_path / "2026-07-05.jsonl").write_text(json.dumps(raw) + "\n", encoding="utf-8")
    records = collect_preference_pairs_from_queue(tmp_path)
    assert "hanako@corp.jp" not in records[0].prompt
    assert "山田花子" not in records[0].rejected


def test_build_sft_dataset_includes_passed_only() -> None:
    passed = _trajectory(scenario_hash="pass1")
    failed = _trajectory(scenario_hash="fail1", steps=[])
    evaluations = [
        EvaluationResult(passed=True, rule_result=RuleCheckResult(passed=True)),
        EvaluationResult(passed=False, rule_result=RuleCheckResult(passed=False, failures=["x"])),
    ]
    sft = build_sft_dataset([passed, failed], evaluations)
    assert len(sft) == 1
    assert sft[0].trajectory_id == "pass1"


def test_build_dpo_dataset_merges_sources() -> None:
    rejected = _trajectory(scenario_hash="rej", steps=[{"role": "assistant", "content": "bad"}])
    corrected = _trajectory(scenario_hash="fix", steps=[{"role": "assistant", "content": "good"}])
    human = DpoRecord(
        prompt="p",
        chosen="c",
        rejected="r",
        origin="human_feedback",
        provenance=PROVENANCE,
    )
    dpo = build_dpo_dataset([rejected], [corrected], [human])
    assert len(dpo) == 2
    origins = {r.origin for r in dpo}
    assert origins == {"human_feedback", "rule_rejection"}


def test_filter_by_opt_in_excludes_non_opted_products() -> None:
    class Record:
        def __init__(self, product_id: str | None) -> None:
            self.product_id = product_id

    records = [Record("prod-a"), Record("prod-b"), Record(None)]
    filtered = filter_by_opt_in(records, {"prod-a": True, "prod-b": False})
    assert len(filtered) == 2
    assert filtered[0].product_id == "prod-a"
    assert filtered[1].product_id is None


def test_shared_bundle_records_excluded_by_default() -> None:
    normal = DpoRecord(
        prompt="p",
        chosen="c",
        rejected="r",
        origin="human_feedback",
        provenance=PROVENANCE,
    )
    shared = DpoRecord(
        prompt="p2",
        chosen="c2",
        rejected="r2",
        origin="human_feedback",
        provenance=SHARED_PROVENANCE,
    )
    assert is_from_shared_bundle(shared) is True
    result = exclude_shared_bundle_records([normal, shared])
    assert result == [normal]


def test_opt_in_store_persistence(tmp_path: Path) -> None:
    store = OptInStore(tmp_path / "opt_in.json")
    store.save_entry(
        ProductOptIn(
            product_id="prod-01JZX0AAAA01BBBBCCCCDDDDEE",
            opt_in=True,
            updated_at=datetime.now(UTC),
        )
    )
    assert store.load()["prod-01JZX0AAAA01BBBBCCCCDDDDEE"] is True
