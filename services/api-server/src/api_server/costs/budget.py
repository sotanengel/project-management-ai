"""月次予算に対する消化率算出・閾値判定(E4-3, AR-04)。

80%/100%の閾値判定そのものはE9-2(予算監視と自動停止)で利用されるため、
本モジュールでは判定関数`check_budget_threshold`のみを提供する
(実際の自動停止アクションはE9-2の責務)。
"""

from __future__ import annotations

from enum import StrEnum

#: 警告(warning)とみなす消化率の下限(80%)。
WARNING_THRESHOLD = 0.8

#: 予算超過(exceeded)とみなす消化率の下限(100%)。
EXCEEDED_THRESHOLD = 1.0


class BudgetStatus(StrEnum):
    """月次予算消化率の状態。"""

    OK = "ok"
    WARNING = "warning"
    EXCEEDED = "exceeded"


def check_budget_threshold(ratio: float) -> BudgetStatus:
    """消化率`ratio`(0.0〜、1.0=100%)から`BudgetStatus`を判定する。

    - `ratio < 0.8`: OK
    - `0.8 <= ratio < 1.0`: WARNING
    - `ratio >= 1.0`: EXCEEDED
    """
    if ratio < 0:
        raise ValueError(f"ratioは0以上である必要があります: {ratio!r}")
    if ratio >= EXCEEDED_THRESHOLD:
        return BudgetStatus.EXCEEDED
    if ratio >= WARNING_THRESHOLD:
        return BudgetStatus.WARNING
    return BudgetStatus.OK


def compute_consumption_ratio(*, spend: float, budget: float) -> float:
    """`spend`(実消化額)/`budget`(月次予算額)の消化率を算出する。

    `budget`が0以下の場合、`spend`が0なら消化率0.0(予算未設定・支出なし)、
    `spend`が正なら「予算に対して無限に超過している」ことを表す大きな値
    (`EXCEEDED_THRESHOLD`を確実に上回る値)を返す。
    """
    if budget <= 0:
        return 0.0 if spend <= 0 else EXCEEDED_THRESHOLD + 1.0
    return spend / budget


__all__ = [
    "EXCEEDED_THRESHOLD",
    "WARNING_THRESHOLD",
    "BudgetStatus",
    "check_budget_threshold",
    "compute_consumption_ratio",
]
