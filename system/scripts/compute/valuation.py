"""`valuation.py` —— 估值确定性算术（`Ch9 §3.4.4` 目录 `valuation`；`Ch5 §D.2/§D.3/§D.6`）。

三条要求逐条落码：

1. **可追溯链**（`Ch5 §D.2`）：每个每股价区间 → `formula` + `operands` + `method_version`
   + `share_count` + `compute_date`。`ValuationRange` 显式携带这些字段。
2. **顺序约束 / 禁倒填**（`Ch5 §D.3` 第四条规则）：`baseline` 版本时间**必须早于**估值计算时间，
   否则 `OrderViolation`（**拒绝**，不是 warn）。
3. **区间宽度 + 概率默认 null**（`Ch5 §D.6`）：区间用 `range{low, high}` 表达；
   情景概率**默认 `null`**（不默认 50/50）。

★ 本层只做**算术与口径检查**；假设（增长率 / WACC / 倍数）由模型或人工给出并作为 operand 传入
  （`Ch5 §B.3`：**模型不做算术，程序不做假设**）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Sequence

from schema.models import DerivedValue

from .contract import (
    CaliberViolation,
    MissingInput,
    OrderViolation,
    UndefinedComputation,
    derived_id_for,
    make_derived,
    require_nonzero,
    require_present,
)


def require_baseline_before_compute(
    baseline_analyzed_at: datetime | None,
    compute_time: datetime | None,
    *,
    subject: str,
) -> None:
    """顺序约束（`Ch5 §D.3` 第四条规则）：`baseline.analyzed_at < compute_time`，否则**拒绝**。

    两者任一缺失（None）→ `MissingInput`（时间契约必须显式，**不得**用"当前时间"兜底，
    否则倒填不可检）。
    """
    if baseline_analyzed_at is None or compute_time is None:
        raise MissingInput(
            f"{subject}: 顺序校验需 baseline.analyzed_at 与 compute_time（不得默认当前时间）",
            missing=["baseline_analyzed_at", "compute_time"],
            subject=subject,
        )
    if baseline_analyzed_at >= compute_time:
        raise OrderViolation(
            f"{subject}: baseline 版本时间（{baseline_analyzed_at}）不早于估值计算时间"
            f"（{compute_time}）—— 禁止倒填（Ch5 §D.3）"
        )


@dataclass(frozen=True)
class ValuationRange:
    """每股价**区间**（`Ch5 §D.2` 可追溯链 + `§D.6` 区间宽度）。

    - `low` / `high`：两个 `DerivedValue`（各带 formula + operands + method_version）。
    - `share_count` / `compute_date`：`Ch5 §D.2` 要求的链字段。
    - `probability`：**默认 `None`**（`Ch5 §D.6`：不把宽泛区间包装成精确预测）。
    """

    low: DerivedValue
    high: DerivedValue
    share_count: Decimal
    compute_date: date
    probability: Decimal | None = None

    def as_range(self) -> dict[str, str]:
        """区间表达 `range{low, high}`（`Ch5 §D.6`），值以字符串存（避免浮点误差）。"""
        return {"low": str(self.low.value), "high": str(self.high.value)}


def compute_value_per_share_range(
    enterprise_value: Decimal,
    net_debt: Decimal,
    shares_outstanding: Decimal,
    low_multiple: Decimal,
    high_multiple: Decimal,
    *,
    subject: str,
    operands: Sequence[str],
    method_version: str,
    computed_at: datetime | None = None,
    baseline_analyzed_at: datetime | None = None,
    probability: Decimal | None = None,
) -> ValuationRange:
    """每股价区间：`(EV - net_debt) / shares * [low, high]_multiple`。

    - `net_debt` 可负（净现金）；净现金时**加回**（`EV - net_debt`）。
    - `shares <= 0` / `low > high` → 缺口或非法输入（明确拒绝，不静默）。
    - `baseline_analyzed_at` 与 `computed_at` **两者都必须给出**：顺序约束
      （`Ch5 §D.3`：baseline 版本时间必须早于计算时间）**始终执行**；任一缺失 → `MissingInput`
      （时间契约必须显式，**不得**用当前时间兜底，否则倒填不可检）。
    - `probability` **默认 `None`**（`Ch5 §D.6`）。
    """
    require_nonzero(shares_outstanding, "shares_outstanding（股数）", subject=subject)
    if shares_outstanding < 0:
        raise UndefinedComputation(
            f"{subject}: 股数为负（{shares_outstanding}）属非法输入",
            missing=["shares_outstanding"],
            subject=subject,
        )
    if low_multiple > high_multiple:
        raise UndefinedComputation(
            f"{subject}: 区间下界 {low_multiple} > 上界 {high_multiple}（非法区间）",
            missing=["low_multiple", "high_multiple"],
            subject=subject,
        )
    # ★ Ch5 §D.3 顺序约束**始终执行**：双 None 时曾静默跳过并以当前时间兜底（= 倒填不可检），
    #   与 require_baseline_before_compute 自身 docstring 相反。现无条件调用。
    require_baseline_before_compute(baseline_analyzed_at, computed_at, subject=subject)
    assert computed_at is not None  # require_baseline_before_compute 已拒绝 None（Ch5 §D.3）

    equity_value = enterprise_value - net_debt
    per_share_base = equity_value / shares_outstanding
    compute_moment = computed_at
    low_value = per_share_base * low_multiple
    high_value = per_share_base * high_multiple
    low = make_derived(
        derived_id_for("value_per_share_low", subject, method_version=method_version),
        low_value,
        f"(({enterprise_value} - {net_debt}) / {shares_outstanding}) * {low_multiple}",
        operands,
        method_version=method_version,
        computed_at=compute_moment,
    )
    high = make_derived(
        derived_id_for("value_per_share_high", subject, method_version=method_version),
        high_value,
        f"(({enterprise_value} - {net_debt}) / {shares_outstanding}) * {high_multiple}",
        operands,
        method_version=method_version,
        computed_at=compute_moment,
    )
    return ValuationRange(
        low=low,
        high=high,
        share_count=shares_outstanding,
        compute_date=compute_moment.date(),
        probability=probability,
    )


def compute_implied_growth_ratio(
    discount_rate: Decimal,
    cash_flow_per_share: Decimal,
    price: Decimal,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """价格**隐含**增长率（`Ch9 §2.4.3` 排除清单：价格隐含增长率由程序算）：`r - CF/P`。

    - `price <= 0` / `cash_flow_per_share` 缺失 → 缺口。
    - 任一输入为 `None`（缺失）→ `MissingInput`（缺口对象，**不得**裸 `TypeError`）。
    - 结果为**诊断**性质（价格隐含），不直接进出建议结论（`Ch5 §B.5`）。
    """
    require_present(
        {"discount_rate": discount_rate, "cash_flow_per_share": cash_flow_per_share, "price": price},
        ("discount_rate", "cash_flow_per_share", "price"),
        subject=subject,
    )
    if price <= 0:
        raise UndefinedComputation(
            f"{subject}: 价格非正（{price}），隐含增长率无定义",
            missing=["price"],
            subject=subject,
        )
    yield_ratio = cash_flow_per_share / price
    value = discount_rate - yield_ratio
    formula = f"{discount_rate} - ({cash_flow_per_share} / {price})"
    return make_derived(
        derived_id_for("implied_growth_ratio", subject),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )


def compute_enterprise_value(
    market_cap: Decimal,
    net_debt: Decimal,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """企业价值 EV = 市值 + 净负债（净现金则减）。`Ch5 §D.2` 链的前置量。

    - `market_cap < 0` → `CaliberViolation`（响亮失败）。
    - 任一输入为 `None`（缺失）→ `MissingInput`（缺口对象，**不得**裸 `TypeError`）。
    """
    require_present({"market_cap": market_cap, "net_debt": net_debt}, ("market_cap", "net_debt"), subject=subject)
    if market_cap < 0:
        raise CaliberViolation(f"{subject}: 市值不得为负（实得 {market_cap}）")
    value = market_cap + net_debt
    formula = f"{market_cap} + {net_debt}"
    return make_derived(
        derived_id_for("enterprise_value", subject),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )
