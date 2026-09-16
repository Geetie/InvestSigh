"""`shares.py` —— 股本与每股指标确定性算术（`Ch9 §3.4.4` 目录 `shares`；`Ch9 §2.4.3` 排除清单含股本变化）。

- `compute_eps`: 每股收益 = 归属普通股净利 / 加权平均股数。
- `compute_value_per_share`: 每股价值 = 权益价值 / 流通股数。
- `compute_share_change_ratio`: 股本变化率 = `(end - begin) / begin`（用于识别稀释）。

股本为 0 / 负 → **缺口对象**（`Ch9 §3.5` 阶段④），不得返回 `0` 或 `inf`。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Sequence

from schema.models import DerivedValue

from .contract import UndefinedComputation, derived_id_for, make_derived, require_nonzero


def _require_positive_shares(shares: Decimal, *, subject: str) -> None:
    """股数必须 > 0：== 0 → 除零类缺口；< 0 → 非法输入（同样拒绝，不静默取绝对值）。"""
    if shares == 0:
        raise UndefinedComputation(
            f"{subject}: 股数为 0，每股指标无定义",
            missing=["shares"],
            subject=subject,
        )
    if shares < 0:
        raise UndefinedComputation(
            f"{subject}: 股数为负（{shares}）属非法输入",
            missing=["shares"],
            subject=subject,
        )


def compute_eps(
    net_income_to_common: Decimal,
    weighted_average_shares: Decimal,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """每股收益（EPS）= 归属普通股净利 / 加权平均股数（`Ch4 §C.4` 三层映射的每股指标）。"""
    _require_positive_shares(weighted_average_shares, subject=subject)
    value = net_income_to_common / weighted_average_shares
    formula = f"{net_income_to_common} / {weighted_average_shares}"
    return make_derived(
        derived_id_for("eps", subject),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )


def compute_value_per_share(
    equity_value: Decimal,
    shares_outstanding: Decimal,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """每股价值 = 权益价值 / 流通股数（`Ch5 §D.2` 每股价区间的中间量）。"""
    _require_positive_shares(shares_outstanding, subject=subject)
    value = equity_value / shares_outstanding
    formula = f"{equity_value} / {shares_outstanding}"
    return make_derived(
        derived_id_for("value_per_share", subject),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )


def compute_share_change_ratio(
    begin_shares: Decimal,
    end_shares: Decimal,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """股本变化率 = `(end - begin) / begin`（识别增发稀释 / 回购缩股；期初为 0 → 缺口）。"""
    require_nonzero(begin_shares, "begin_shares（期初股数）", subject=subject)
    value = (end_shares - begin_shares) / begin_shares
    formula = f"({end_shares} - {begin_shares}) / {begin_shares}"
    return make_derived(
        derived_id_for("share_change_ratio", subject),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )
