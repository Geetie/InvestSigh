"""`core.py` —— 通用确定性算术（`Ch9 §3.4.4` 目录 `core`）。

只放**与行业无关**的基础算子（同比 / 复合增长率 / 差分比率 / 变化率）；行业算子按层拆到
`growth` / `margin` / `returns` / `fx` / `shares` / `valuation`。

接口与 `Ch9 §3.4.4` 的示例签名一致：

```
compute_yoy(current: Decimal, base: Decimal, unit: str, period: Period) -> DerivedValue
```

★ 边界（`Ch9 §3.4.4` 单测策略）：0 / 负值 / 跨期 / 除零 —— 除零与无定义 → **缺口对象**，
  不抛裸 `ZeroDivisionError`，不返回 `0` 冒充。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Sequence

from schema.models import DerivedValue, Period

from .contract import (
    UndefinedComputation,
    derived_id_for,
    make_derived,
    require_nonzero,
    require_present,
)


def compute_yoy(
    current: Decimal,
    base: Decimal,
    unit: str,
    period: Period,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """同比（YoY）：`(current - base) / base * 100`（比例，单位 `%`）。

    `unit` 只作**标注**（源稿 9 要素之一），不参与算术 —— 算术在**同口径同币种**下成立，
    跨口径须由调用方先经 `fx` 层换算。
    """
    require_nonzero(base, "base（基期）", subject=subject)
    value = (current - base) / base * Decimal(100)
    formula = f"({current} - {base}) / {base} * 100 [{period.reported_label}]"
    return make_derived(
        derived_id_for("yoy", subject),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )


def compute_cagr(
    begin: Decimal,
    end: Decimal,
    years: Decimal,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """复合年均增长率：`(end / begin) ** (1 / years) - 1`（比例，单位 `倍`）。

    - `begin <= 0` → `UndefinedComputation`（零/负基数下**实**CAGR 无定义，不得给近似值）。
    - `end <= 0` → `UndefinedComputation`。
    - `years <= 0` → `UndefinedComputation`。
    - 任一为 `None`（缺失）→ `MissingInput`（缺口对象，**不得**冒泡成裸 `TypeError`）。
    """
    require_present(
        {"begin": begin, "end": end, "years": years}, ("begin", "end", "years"), subject=subject
    )
    if begin <= 0 or end <= 0:
        raise UndefinedComputation(
            f"{subject}: CAGR 要求 begin>0 且 end>0（实得 begin={begin}, end={end}）",
            missing=["begin", "end"],
            subject=subject,
        )
    if years <= 0:
        raise UndefinedComputation(
            f"{subject}: CAGR 的年数必须 > 0（实得 {years}）",
            missing=["years"],
            subject=subject,
        )
    ratio = (end / begin) ** (Decimal(1) / years)
    value = ratio - Decimal(1)
    formula = f"({end} / {begin}) ** (1 / {years}) - 1"
    return make_derived(
        derived_id_for("cagr", subject),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )


def compute_diff_ratio(
    numerator: Decimal,
    denominator: Decimal,
    *,
    subject: str,
    operands: Sequence[str],
    unit: str = "倍",
    computed_at: datetime | None = None,
) -> DerivedValue:
    """差分比率：`numerator / denominator`（通用比率算子；分母为 0 → 缺口）。"""
    require_nonzero(denominator, "denominator（分母）", subject=subject)
    value = numerator / denominator
    formula = f"{numerator} / {denominator} [{unit}]"
    return make_derived(
        derived_id_for("diff_ratio", subject),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )


def compute_change_ratio(
    begin: Decimal,
    end: Decimal,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """变化率：`(end - begin) / abs(begin)`（带符号；`begin == 0` → 缺口）。"""
    require_nonzero(begin, "begin（基期）", subject=subject)
    value = (end - begin) / abs(begin)
    formula = f"({end} - {begin}) / abs({begin})"
    return make_derived(
        derived_id_for("change_ratio", subject),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )
