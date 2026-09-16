"""`growth.py` —— 增长驱动与"增长的代价"的确定性算术（`Ch4 §D.3`）。

`Ch4 §D.3` 的两条硬要求，逐条落成本层的可测函数：

1. **ROIIC**（增量资本回报率）= `incremental_nopat / incremental_invested_capital`
   → 走 `scripts/compute/`（`Ch4 §D.3` 的伪码 `compute_roiic(...)`）。
2. **增长质量 = 分档（不压成单一分数）**：`growth_quality ∈ {high, medium, low}`，
   由**四项分项**判定 —— `ROIIC vs WACC` / `现金转化率` / `营运资金变动` / `融资依赖`。

★ `assess_growth_quality()` **刻意不返回单一数值**：模型不得把四项压成一个分数再做门槛
  （对齐 `Ch2 §B.2 P-01`：不得增设最低超额收益门槛）。它返回**分档 + 分项明细**。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Sequence

from schema.models import DerivedValue

from .contract import UndefinedComputation, derived_id_for, make_derived, require_nonzero

VALUE_DESTRUCTIVE_FLAG = "value_destructive_growth"
"""`Ch4 §D.3`："收入高增长但毁灭股东价值"的识别标志（当 `ROIIC < WACC`）。"""


def compute_roiic(
    incremental_nopat: Decimal,
    incremental_invested_capital: Decimal,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """ROIIC：增量 NOPAT / 增量投入资本（`Ch4 §D.3`）。分母 0 → 缺口对象。"""
    require_nonzero(
        incremental_invested_capital, "incremental_invested_capital（增量投入资本）", subject=subject
    )
    value = incremental_nopat / incremental_invested_capital
    formula = f"{incremental_nopat} / {incremental_invested_capital}"
    return make_derived(
        derived_id_for("roiic", subject),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )


@dataclass(frozen=True)
class GrowthQuality:
    """增长质量**分档**结果（`Ch4 §D.3`）—— 分档 + 分项明细，**不是单一分数**。"""

    grade: str                                  # high | medium | low
    roiic: Decimal
    wacc: Decimal
    cash_conversion: Decimal
    working_capital_change: Decimal             # 正 = 营运资金占用增加（对增长质量为负向）
    financing_dependence: str                   # none | low | high
    flags: list[str] = field(default_factory=list)
    detail: dict[str, str] = field(default_factory=dict)


def assess_growth_quality(
    *,
    roiic: Decimal,
    wacc: Decimal,
    cash_conversion: Decimal,
    working_capital_change: Decimal,
    financing_dependence: str,
    subject: str = "",
) -> GrowthQuality:
    """四项分项 → 分档（`Ch4 §D.3`）。**不合并成单一分数**，按分项计负分再分档。

    ★ `Ch4 §D.3` 伪码**硬规则**：`if roiic < wacc: return GrowthQuality("low", flag=…)` ——
      ROIIC 低于资金成本（毁灭价值）时**唯一下档为 `low`**，其余三项只进 `detail`，不再改变档位。

    - 分项 ①：`roiic < wacc` → 负向，并打 `value_destructive_growth` 标志 →
      **档位直接判 `low`**（对齐 `Ch4 §D.3` 伪码）。
    - 分项 ②：现金转化率 `< 0.8`（经验下限，作为**分档依据**而非门槛）→ 负向。
    - 分项 ③：营运资金变动 `> 0`（占用增加）→ 负向。
    - 分项 ④：融资依赖 `high` → 负向。

    档位映射：`roiic < wacc` → `low`；否则负分计数 `0` → `high`；`1` → `medium`；`≥2` → `low`。
    分档**不阻断**任何结论，只供价值层与建议层参考（`Ch4 §D.3`）。
    """
    if financing_dependence not in {"none", "low", "high"}:
        raise UndefinedComputation(
            f"{subject}: financing_dependence 取值非法 {financing_dependence!r}"
            "（合法：none / low / high）",
            missing=["financing_dependence"],
            subject=subject,
        )

    flags: list[str] = []
    detail: dict[str, str] = {}
    negatives = 0

    if roiic < wacc:
        negatives += 1
        flags.append(VALUE_DESTRUCTIVE_FLAG)
        detail["roiic_vs_wacc"] = f"ROIIC({roiic}) < WACC({wacc}) → 负向"
    else:
        detail["roiic_vs_wacc"] = f"ROIIC({roiic}) >= WACC({wacc}) → 中性"

    cash_threshold = Decimal("0.8")
    if cash_conversion < cash_threshold:
        negatives += 1
        detail["cash_conversion"] = f"{cash_conversion} < {cash_threshold} → 负向"
    else:
        detail["cash_conversion"] = f"{cash_conversion} >= {cash_threshold} → 中性"

    if working_capital_change > 0:
        negatives += 1
        detail["working_capital_change"] = f"{working_capital_change} > 0（占用增加）→ 负向"
    else:
        detail["working_capital_change"] = f"{working_capital_change} <= 0 → 中性"

    if financing_dependence == "high":
        negatives += 1
        detail["financing_dependence"] = "high → 负向"
    else:
        detail["financing_dependence"] = f"{financing_dependence} → 中性"

    # ★ 分档（`Ch4 §D.3`）：`roiic < wacc`（毁灭价值）→ 直接 `low`（伪码硬规则）；
    #   否则按四项负分计数分档。此处**不把四项压成单一分数**（分项明细保留在 detail）。
    if roiic < wacc:
        grade = "low"
    else:
        grade = "high" if negatives == 0 else ("medium" if negatives == 1 else "low")
    return GrowthQuality(
        grade=grade,
        roiic=roiic,
        wacc=wacc,
        cash_conversion=cash_conversion,
        working_capital_change=working_capital_change,
        financing_dependence=financing_dependence,
        flags=flags,
        detail=detail,
    )
