"""`margin.py` —— 利润率类确定性算术（`Ch9 §3.4.4` 目录 `margin`；`Ch4 §D.3` 财务科目）。

三个算子（毛利率 / 营业利润率 / 净利率）共用同一形态：`分子 / 收入`。
收入为 0 → **缺口对象**（`Ch9 §3.5` 阶段④），不得返回 `0` 冒充。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Sequence

from schema.models import DerivedValue

from .contract import derived_id_for, make_derived, require_nonzero


def _margin(
    kind: str,
    numerator: Decimal,
    revenue: Decimal,
    numerator_label: str,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None,
) -> DerivedValue:
    """利润率公共实现：`numerator / revenue`（比例，分母 0 → 缺口）。"""
    require_nonzero(revenue, "revenue（收入）", subject=subject)
    value = numerator / revenue
    formula = f"{numerator_label} / {revenue}"
    return make_derived(
        derived_id_for(kind, subject),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )


def compute_gross_margin(
    gross_profit: Decimal,
    revenue: Decimal,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """毛利率 = 毛利 / 收入（`Ch4 §D.3` 降价 → 毛利率映射）。"""
    return _margin(
        "gross_margin", gross_profit, revenue, "gross_profit",
        subject=subject, operands=operands, computed_at=computed_at,
    )


def compute_operating_margin(
    operating_income: Decimal,
    revenue: Decimal,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """营业利润率 = 营业利润 / 收入（`Ch4 §C.4` opex 科目的比率化）。"""
    return _margin(
        "operating_margin", operating_income, revenue, "operating_income",
        subject=subject, operands=operands, computed_at=computed_at,
    )


def compute_net_margin(
    net_income: Decimal,
    revenue: Decimal,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """净利率 = 净利润 / 收入（`Ch4 §C.4` 净利 → EPS 链的中间量）。"""
    return _margin(
        "net_margin", net_income, revenue, "net_income",
        subject=subject, operands=operands, computed_at=computed_at,
    )
