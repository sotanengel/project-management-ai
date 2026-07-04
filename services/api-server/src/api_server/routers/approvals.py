"""承認ワークフローAPI(`POST /approvals`, `POST /approvals/{id}/decide`, `GET /approvals`)。

起案(`proposed`)→承認/差し戻し(`approved`/`rejected`)のステートマシンを
実装する。決定(`decide`)が下された時点で`Approval`(PMDF)エンティティを
`PmdfStore`へ永続化し(Git履歴として監査証跡を残す)、承認ゲート
(`api_server.approval.gate.require_approval`)はこのPMDFエンティティを
参照して判定する。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pmdf.models import Approval
from pmdf.models.common import Provenance
from pydantic import BaseModel, Field

from api_server.approval.proposal_store import (
    Proposal,
    add_proposal,
    find_proposal_by_id,
    load_proposals,
    update_proposal,
)
from api_server.approval.state_machine import InvalidTransitionError, ProposalState, transition
from api_server.auth.dependencies import get_current_user, require_role
from api_server.auth.models import User
from api_server.config import Settings, get_settings
from api_server.deps import get_pmdf_store_dependency
from api_server.pmdf_store.store import PmdfStore

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ProposeRequest(BaseModel):
    target: str
    proposer: str


class ProposalResponse(BaseModel):
    id: str
    target: str
    proposer: str
    status: ProposalState
    approver: str | None = None
    reason: str | None = None
    approval_entity_id: str | None = None


class DecideRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    approver: str
    reason: str = Field(min_length=1)


def _to_response(proposal: Proposal) -> ProposalResponse:
    return ProposalResponse(**proposal.model_dump())


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProposalResponse)
def propose(
    request: ProposeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[User, Depends(require_role("admin", "editor"))],
) -> ProposalResponse:
    proposal = Proposal(
        id=f"proposal-{uuid.uuid4()}",
        target=request.target,
        proposer=request.proposer,
        status=ProposalState.PROPOSED,
    )
    add_proposal(settings.proposal_store_path, proposal)
    return _to_response(proposal)


@router.get("", response_model=list[ProposalResponse])
def list_proposals(
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[User, Depends(get_current_user)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[ProposalResponse]:
    proposals = load_proposals(settings.proposal_store_path)
    if status_filter is not None:
        target_state = ProposalState.PROPOSED if status_filter == "pending" else status_filter
        proposals = [p for p in proposals if p.status == target_state]
    return [_to_response(p) for p in proposals]


@router.post("/{proposal_id}/decide", response_model=ProposalResponse)
def decide(
    proposal_id: str,
    request: DecideRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
    user: Annotated[User, Depends(require_role("admin", "editor"))],
) -> ProposalResponse:
    proposal = find_proposal_by_id(settings.proposal_store_path, proposal_id)
    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"プロポーザル {proposal_id!r} が見つかりません",
        )

    target_state = ProposalState(request.decision)
    try:
        transition(proposal.status, target_state)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    from pmdf.ids import generate_id

    approval_entity = Approval(
        pmdf_version="1.0.0",
        kind="approval",
        id=generate_id("approval"),
        provenance=Provenance(created_by=f"user:{user.id}", updated_at=datetime.now(UTC)),
        attachments=[],
        target=proposal.target,
        proposer=proposal.proposer,
        approver=request.approver,
        decision=request.decision,
        reason=request.reason,
    )
    store.create(approval_entity, actor=f"user:{user.id}")

    updated = proposal.model_copy(
        update={
            "status": target_state,
            "approver": request.approver,
            "reason": request.reason,
            "approval_entity_id": approval_entity.id,
        }
    )
    update_proposal(settings.proposal_store_path, updated)
    return _to_response(updated)


__all__ = ["router"]
