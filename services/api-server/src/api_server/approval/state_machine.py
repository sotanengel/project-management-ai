"""承認プロポーザルのステートマシン(`ProposalState`)。

`proposed`(起案) → `approved`(承認) / `rejected`(差し戻し) の一方向遷移
のみを許可する。一度 `approved`/`rejected` に遷移したプロポーザルは
再遷移できない(監査ログの追記専用性・改ざん防止(E3-7)の前提と整合させる)。
"""

from __future__ import annotations

from enum import StrEnum


class ProposalState(StrEnum):
    """承認プロポーザルの状態。"""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class InvalidTransitionError(Exception):
    """許可されていない状態遷移が試みられた場合に送出される例外。"""


#: 許可される遷移の集合(from -> 許可されるto の集合)。
_ALLOWED_TRANSITIONS: dict[ProposalState, frozenset[ProposalState]] = {
    ProposalState.PROPOSED: frozenset({ProposalState.APPROVED, ProposalState.REJECTED}),
    ProposalState.APPROVED: frozenset(),
    ProposalState.REJECTED: frozenset(),
}


def transition(current: ProposalState, target: ProposalState) -> ProposalState:
    """`current` から `target` への遷移を検証し、許可されれば `target` を返す。

    Raises:
        InvalidTransitionError: 許可されていない遷移の場合
            (`approved`/`rejected` からの再遷移、`proposed` への自己遷移等)。
    """
    allowed = _ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            f"{current.value} から {target.value} への遷移は許可されません"
        )
    return target


__all__ = ["InvalidTransitionError", "ProposalState", "transition"]
