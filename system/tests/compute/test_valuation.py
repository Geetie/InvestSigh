"""`valuation` 单测（`Ch5 §D.2` 可追溯链 / `§D.3` 顺序约束 / `§D.6` 区间宽度与概率默认 null）。

覆盖 AC-06（非法区间 / 负股数 / 倒填拒绝）+ AC-08（设计对齐：链字段齐备）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from scripts.compute import valuation
from scripts.compute.contract import (
    CaliberViolation,
    MissingInput,
    OrderViolation,
    UndefinedComputation,
)


def test_value_per_share_range_known_value() -> None:
    """EV=1000, 净负债=200, 股数=100 → 权益 800 → 每股 8；×[10,15] → [80,120]。"""
    rng = valuation.compute_value_per_share_range(
        Decimal("1000"), Decimal("200"), Decimal("100"), Decimal("10"), Decimal("15"),
        subject="sec_nvda", operands=["baseline-1", "shares-1"], method_version="val-v1",
    )
    assert rng.low.value == Decimal("80")
    assert rng.high.value == Decimal("120")
    assert rng.as_range() == {"low": "80", "high": "120"}
    # `Ch5 §D.2`：每股价区间必须带 formula + operands + method_version + share_count + compute_date
    for dv in (rng.low, rng.high):
        assert dv.formula and dv.operands and dv.method_version == "val-v1"
    assert rng.share_count == Decimal("100")
    assert rng.compute_date is not None


def test_range_probability_defaults_to_none() -> None:
    """`Ch5 §D.6`：情景概率**默认 null**（不默认 50/50）。"""
    rng = valuation.compute_value_per_share_range(
        Decimal("1000"), Decimal("0"), Decimal("100"), Decimal("10"), Decimal("12"),
        subject="s", operands=["a"], method_version="v1",
    )
    assert rng.probability is None


def test_net_cash_adds_back() -> None:
    """净负债为负（净现金）→ 加回：EV - (-100) = EV + 100。"""
    rng = valuation.compute_value_per_share_range(
        Decimal("1000"), Decimal("-100"), Decimal("100"), Decimal("1"), Decimal("1"),
        subject="s", operands=["a"], method_version="v1",
    )
    assert rng.low.value == Decimal("11")


def test_reversed_range_is_rejected() -> None:
    with pytest.raises(UndefinedComputation):
        valuation.compute_value_per_share_range(
            Decimal("1000"), Decimal("0"), Decimal("100"), Decimal("15"), Decimal("10"),
            subject="s", operands=["a"], method_version="v1",
        )


def test_zero_shares_is_gap() -> None:
    with pytest.raises(UndefinedComputation):
        valuation.compute_value_per_share_range(
            Decimal("1000"), Decimal("0"), Decimal("0"), Decimal("10"), Decimal("12"),
            subject="s", operands=["a"], method_version="v1",
        )


def test_negative_shares_is_undefined() -> None:
    with pytest.raises(UndefinedComputation):
        valuation.compute_value_per_share_range(
            Decimal("1000"), Decimal("0"), Decimal("-1"), Decimal("10"), Decimal("12"),
            subject="s", operands=["a"], method_version="v1",
        )


def test_order_violation_when_baseline_not_before_compute() -> None:
    """`Ch5 §D.3` 第四条规则：baseline 版本时间必须**早于**估值时间 → 否则**拒绝**。"""
    later_baseline = datetime(2026, 9, 20, tzinfo=timezone.utc)
    compute_time = datetime(2026, 9, 10, tzinfo=timezone.utc)
    with pytest.raises(OrderViolation):
        valuation.compute_value_per_share_range(
            Decimal("1000"), Decimal("0"), Decimal("100"), Decimal("10"), Decimal("12"),
            subject="s", operands=["a"], method_version="v1",
            baseline_analyzed_at=later_baseline, computed_at=compute_time,
        )


def test_order_check_requires_explicit_times() -> None:
    """时间契约必须显式（不得默认当前时间，否则倒填不可检）。"""
    with pytest.raises(MissingInput):
        valuation.require_baseline_before_compute(None, datetime(2026, 9, 10, tzinfo=timezone.utc), subject="s")


def test_order_check_passes_when_baseline_earlier() -> None:
    valuation.require_baseline_before_compute(
        datetime(2026, 8, 1, tzinfo=timezone.utc),
        datetime(2026, 9, 10, tzinfo=timezone.utc),
        subject="s",
    )  # 不抛即通过


def test_implied_growth_known_value() -> None:
    """价格隐含增长率 = r - CF/P = 0.10 - 5/100 = 0.05。"""
    value = valuation.compute_implied_growth_ratio(
        Decimal("0.10"), Decimal("5"), Decimal("100"), subject="s", operands=["price-1", "assumption-1"],
    )
    assert value.value == Decimal("0.05")


def test_implied_growth_zero_price_is_gap() -> None:
    with pytest.raises(UndefinedComputation):
        valuation.compute_implied_growth_ratio(Decimal("0.10"), Decimal("5"), Decimal("0"), subject="s", operands=["a"])


def test_enterprise_value_known_value() -> None:
    value = valuation.compute_enterprise_value(Decimal("1000"), Decimal("200"), subject="s", operands=["mktcap-1"])
    assert value.value == Decimal("1200")


def test_enterprise_value_negative_market_cap_is_caliber_violation() -> None:
    with pytest.raises(CaliberViolation):
        valuation.compute_enterprise_value(Decimal("-1"), Decimal("0"), subject="s", operands=["a"])
