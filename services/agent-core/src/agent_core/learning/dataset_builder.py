"""E8-6: 学習データセット組み立て(FR-SL-05, FR-SL-10)。"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pmdf.learning.schemas import DpoRecord, RecordProvenance, SftRecord, TrajectoryRecord
from pydantic import BaseModel, ConfigDict

from agent_core.learning.evaluate import EvaluationResult

DEFAULT_PROMPT_VERSION = "e8-6-v1"
DEFAULT_KB_VERSION = "corpus-v1"
SHARED_BUNDLE_MARKER = "x_imported_from_bundle"


class HasProvenance(Protocol):
    provenance: RecordProvenance


class HasProductId(Protocol):
    product_id: str


class ProductOptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    opt_in: bool
    updated_at: datetime


def _trajectory_to_prompt_completion(trajectory: TrajectoryRecord) -> tuple[str, str]:
    prompt = trajectory.scenario_text
    parts: list[str] = []
    for step in trajectory.steps:
        role = step.get("role", "unknown")
        content = step.get("content", "")
        parts.append(f"{role}: {content}")
    for diff in trajectory.pmdf_diffs:
        parts.append(json.dumps(diff, ensure_ascii=False))
    completion = "\n".join(parts) if parts else "(empty)"
    return prompt, completion


def build_sft_dataset(
    trajectories: list[TrajectoryRecord],
    evaluations: list[EvaluationResult],
) -> list[SftRecord]:
    """合格軌跡のみ SFT レコード化。"""
    if len(trajectories) != len(evaluations):
        raise ValueError("trajectories と evaluations の件数が一致しません")

    records: list[SftRecord] = []
    for trajectory, evaluation in zip(trajectories, evaluations, strict=True):
        if not evaluation.passed:
            continue
        prompt, completion = _trajectory_to_prompt_completion(trajectory)
        records.append(
            SftRecord(
                prompt=prompt,
                completion=completion,
                trajectory_id=trajectory.scenario_hash,
                provenance=trajectory.provenance,
            )
        )
    return records


def build_dpo_dataset(
    rejected_trajectories: list[TrajectoryRecord],
    corrections: list[TrajectoryRecord],
    human_feedback: list[DpoRecord],
) -> list[DpoRecord]:
    """不合格+修正ペアと人間 FB を統合。"""
    if len(rejected_trajectories) != len(corrections):
        raise ValueError("rejected_trajectories と corrections の件数が一致しません")

    records: list[DpoRecord] = list(human_feedback)
    for rejected, corrected in zip(rejected_trajectories, corrections, strict=True):
        rej_prompt, rej_completion = _trajectory_to_prompt_completion(rejected)
        _, chosen_completion = _trajectory_to_prompt_completion(corrected)
        records.append(
            DpoRecord(
                prompt=rej_prompt,
                chosen=chosen_completion,
                rejected=rej_completion,
                origin="rule_rejection",
                provenance=rejected.provenance,
            )
        )
    return records


def is_from_shared_bundle(record: HasProvenance) -> bool:
    """共有バンドル import 由来なら True(既定除外対象)。"""
    prov = record.provenance
    kb = prov.kb_version or ""
    if kb.startswith("shared_bundle:"):
        return True
    if SHARED_BUNDLE_MARKER in kb:
        return True
    return False


def filter_by_opt_in(
    records: list[Any],
    opt_ins: dict[str, bool],
    *,
    get_product_id: Callable[[Any], str | None] | None = None,
) -> list[Any]:
    """オプトインされていないプロダクト由来レコードを除外。"""
    getter = get_product_id or (lambda r: getattr(r, "product_id", None))
    filtered: list[Any] = []
    for record in records:
        product_id = getter(record)
        if product_id is None:
            filtered.append(record)
            continue
        if opt_ins.get(product_id, False):
            filtered.append(record)
    return filtered


def exclude_shared_bundle_records(records: list[Any]) -> list[Any]:
    """共有バンドル由来を除外(明示オプトインなしでは学習対象外)。"""
    return [r for r in records if not is_from_shared_bundle(r)]


class OptInStore:
    """プロダクト単位オプトイン設定(JSON 永続化)。"""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> dict[str, bool]:
        if not self._path.is_file():
            return {}
        data = json.loads(self._path.read_text(encoding="utf-8"))
        return {item["product_id"]: item["opt_in"] for item in data.get("products", [])}

    def save_entry(self, entry: ProductOptIn) -> None:
        current = self.load()
        current[entry.product_id] = entry.opt_in
        payload = {
            "products": [
                {
                    "product_id": pid,
                    "opt_in": opted,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
                for pid, opted in sorted(current.items())
            ]
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


__all__ = [
    "ProductOptIn",
    "OptInStore",
    "build_dpo_dataset",
    "build_sft_dataset",
    "exclude_shared_bundle_records",
    "filter_by_opt_in",
    "is_from_shared_bundle",
]
