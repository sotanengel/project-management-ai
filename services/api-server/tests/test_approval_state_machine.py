"""承認ステートマシン(`ProposalState`)のテスト(E3-6)。"""

from __future__ import annotations

import pytest


def test_proposed_can_transition_to_approved() -> None:
    from api_server.approval.state_machine import ProposalState, transition

    assert transition(ProposalState.PROPOSED, ProposalState.APPROVED) == ProposalState.APPROVED


def test_proposed_can_transition_to_rejected() -> None:
    from api_server.approval.state_machine import ProposalState, transition

    assert transition(ProposalState.PROPOSED, ProposalState.REJECTED) == ProposalState.REJECTED


def test_approved_cannot_transition_again() -> None:
    from api_server.approval.state_machine import (
        InvalidTransitionError,
        ProposalState,
        transition,
    )

    with pytest.raises(InvalidTransitionError):
        transition(ProposalState.APPROVED, ProposalState.REJECTED)


def test_rejected_cannot_transition_again() -> None:
    from api_server.approval.state_machine import (
        InvalidTransitionError,
        ProposalState,
        transition,
    )

    with pytest.raises(InvalidTransitionError):
        transition(ProposalState.REJECTED, ProposalState.APPROVED)


def test_proposed_cannot_transition_to_itself() -> None:
    from api_server.approval.state_machine import (
        InvalidTransitionError,
        ProposalState,
        transition,
    )

    with pytest.raises(InvalidTransitionError):
        transition(ProposalState.PROPOSED, ProposalState.PROPOSED)
