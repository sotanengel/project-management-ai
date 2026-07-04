"""api_server.costs.budget: 月次予算消化率の閾値判定(E4-3, AR-04)。"""

from __future__ import annotations

import pytest


def test_ratio_below_80_percent_is_ok() -> None:
    from api_server.costs.budget import BudgetStatus, check_budget_threshold

    assert check_budget_threshold(0.0) is BudgetStatus.OK
    assert check_budget_threshold(0.5) is BudgetStatus.OK
    assert check_budget_threshold(0.79) is BudgetStatus.OK


def test_ratio_at_80_percent_is_warning() -> None:
    from api_server.costs.budget import BudgetStatus, check_budget_threshold

    assert check_budget_threshold(0.8) is BudgetStatus.WARNING


def test_ratio_between_80_and_100_percent_is_warning() -> None:
    from api_server.costs.budget import BudgetStatus, check_budget_threshold

    assert check_budget_threshold(0.85) is BudgetStatus.WARNING
    assert check_budget_threshold(0.999) is BudgetStatus.WARNING


def test_ratio_at_100_percent_is_exceeded() -> None:
    from api_server.costs.budget import BudgetStatus, check_budget_threshold

    assert check_budget_threshold(1.0) is BudgetStatus.EXCEEDED


def test_ratio_above_100_percent_is_exceeded() -> None:
    from api_server.costs.budget import BudgetStatus, check_budget_threshold

    assert check_budget_threshold(1.5) is BudgetStatus.EXCEEDED


def test_negative_ratio_raises_value_error() -> None:
    from api_server.costs.budget import check_budget_threshold

    with pytest.raises(ValueError, match="0以上"):
        check_budget_threshold(-0.1)


def test_compute_consumption_ratio_divides_spend_by_budget() -> None:
    from api_server.costs.budget import compute_consumption_ratio

    assert compute_consumption_ratio(spend=25_000, budget=50_000) == pytest.approx(0.5)
    assert compute_consumption_ratio(spend=50_000, budget=50_000) == pytest.approx(1.0)
    assert compute_consumption_ratio(spend=0, budget=50_000) == pytest.approx(0.0)


def test_compute_consumption_ratio_with_zero_budget_returns_zero_when_no_spend() -> None:
    from api_server.costs.budget import compute_consumption_ratio

    assert compute_consumption_ratio(spend=0, budget=0) == 0.0


def test_compute_consumption_ratio_with_zero_budget_and_positive_spend_is_exceeded() -> None:
    from api_server.costs.budget import compute_consumption_ratio

    # 予算0円で支出がある場合は「無限大に消化」= 予算超過を表す大きな値を返す。
    ratio = compute_consumption_ratio(spend=100, budget=0)
    assert ratio > 1.0
