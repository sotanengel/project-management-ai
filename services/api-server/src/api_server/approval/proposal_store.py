"""承認プロポーザルのファイルベース(JSON)ストア。

`Approval`(PMDF)エンティティは`decision`(approved/rejected)を必須項目
として持つため、決定前の「起案(proposed)」状態はPMDFエンティティとして
表現できない。そこで、決定前の状態はapi-server側の軽量なJSONストアで
管理し、決定(`decide`)が下された時点で`PmdfStore`に`Approval`エンティティ
として永続化する(監査証跡としてGit履歴に残す)。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from api_server.approval.state_machine import ProposalState


class Proposal(BaseModel):
    """承認プロポーザル1件分の情報。"""

    id: str
    target: str
    proposer: str
    status: ProposalState
    approver: str | None = None
    reason: str | None = None
    #: 決定が下された際に作成された`Approval`(PMDF)エンティティのid。
    approval_entity_id: str | None = None
    #: 起案内容(変更前後diff表示用、E7-4)。agent-core側で生成された変更案
    #: (対象エンティティに適用予定のフィールド値)を任意で保持する。
    draft: dict[str, Any] | None = None


def load_proposals(path: Path) -> list[Proposal]:
    """JSONファイルからプロポーザル一覧を読み込む。ファイルが存在しない場合は空リスト。"""
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Proposal.model_validate(item) for item in raw]


def save_proposals(path: Path, proposals: list[Proposal]) -> None:
    """プロポーザル一覧をJSONファイルへ書き込む。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [proposal.model_dump(mode="json") for proposal in proposals]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def add_proposal(path: Path, proposal: Proposal) -> Proposal:
    """新規プロポーザルを追加して永続化する。"""
    proposals = load_proposals(path)
    proposals.append(proposal)
    save_proposals(path, proposals)
    return proposal


def find_proposal_by_id(path: Path, proposal_id: str) -> Proposal | None:
    """idに一致するプロポーザルを返す(存在しない場合はNone)。"""
    for proposal in load_proposals(path):
        if proposal.id == proposal_id:
            return proposal
    return None


def update_proposal(path: Path, updated: Proposal) -> Proposal:
    """既存プロポーザルを更新して永続化する。

    Raises:
        KeyError: 対象プロポーザルが存在しない場合。
    """
    proposals = load_proposals(path)
    for index, existing in enumerate(proposals):
        if existing.id == updated.id:
            proposals[index] = updated
            save_proposals(path, proposals)
            return updated
    raise KeyError(f"プロポーザル {updated.id!r} が見つかりません")


__all__ = [
    "Proposal",
    "add_proposal",
    "find_proposal_by_id",
    "load_proposals",
    "save_proposals",
    "update_proposal",
]
