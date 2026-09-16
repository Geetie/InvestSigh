"""算子层单测（`Ch9 §3.4.4` 单测策略：每函数 ≥3 已知值 + 边界：0 / 负值 / 跨期 / 除零）。

覆盖：core / margin / fx / shares / growth（`Ch4 §D.3` 分档）+ AC-06 边界。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from scripts.compute import core, fx, growth, margin, shares
from scripts.compute.contract import ComputeGap, MissingInput, UndefinedComputation, safe_compute
from schema.models import Period

PERIOD = Period(
    reported_label="FY2026 Q2",
    normalized_start=date(2026, 4, 1),
    normalized_end=date(2026, 6, 30),
    fiscal_year_start_month=1,
)


# ─────────────────────────── core ───────────────────────────


def test_compute_yoy_known_value_350_vs_180() -> None:
    """源稿示例：收入 350 vs 基期 180 → 同比 +94.44%（`Ch9 §2.4.2`）。"""
    value = core.compute_yoy(
        Decimal("350"), Decimal("180"), "亿", PERIOD, subject="sec_nvda-FY2026Q2", operands=["claim-current", "claim-base"]
    )
    assert value.value.quantize(Decimal("0.01")) == Decimal("94.44")
    assert "FY2026 Q2" in value.formula
    assert value.operands == ["claim-current", "claim-base"]


def test_compute_yoy_negative_growth_allowed() -> None:
    value = core.compute_yoy(Decimal("90"), Decimal("100"), "亿", PERIOD, subject="s", operands=["a", "b"])
    assert value.value == Decimal("-10")


def test_compute_yoy_zero_base_is_gap_not_zero() -> None:
    with pytest.raises(UndefinedComputation):
        core.compute_yoy(Decimal("100"), Decimal("0"), "亿", PERIOD, subject="s", operands=["a", "b"])


def test_compute_cagr_known_value() -> None:
    value = core.compute_cagr(Decimal("100"), Decimal("121"), Decimal("2"), subject="s", operands=["a"])
    assert value.value.quantize(Decimal("0.0001")) == Decimal("0.1000")


def test_compute_cagr_rejects_nonpositive_base() -> None:
    with pytest.raises(UndefinedComputation):
        core.compute_cagr(Decimal("0"), Decimal("121"), Decimal("2"), subject="s", operands=["a"])
    with pytest.raises(UndefinedComputation):
        core.compute_cagr(Decimal("100"), Decimal("121"), Decimal("0"), subject="s", operands=["a"])


def test_compute_change_ratio_sign_preserved() -> None:
    value = core.compute_change_ratio(Decimal("100"), Decimal("80"), subject="s", operands=["a"])
    assert value.value == Decimal("-0.2")


def test_compute_huge_values_do_not_overflow() -> None:
    """AC-06 超大：1e18 量级仍可算（Decimal，无浮点溢出）。"""
    value = core.compute_diff_ratio(
        Decimal("1e18"), Decimal("1e17"), subject="s", operands=["a"]
    )
    assert value.value == Decimal("10")


# ─────────────────────────── margin ───────────────────────────


def test_margins_known_values() -> None:
    assert margin.compute_gross_margin(Decimal("60"), Decimal("100"), subject="s", operands=["a"]).value == Decimal("0.6")
    assert margin.compute_operating_margin(Decimal("30"), Decimal("100"), subject="s", operands=["a"]).value == Decimal("0.3")
    assert margin.compute_net_margin(Decimal("20"), Decimal("100"), subject="s", operands=["a"]).value == Decimal("0.2")


def test_margin_zero_revenue_is_gap() -> None:
    with pytest.raises(UndefinedComputation):
        margin.compute_gross_margin(Decimal("60"), Decimal("0"), subject="s", operands=["a"])


# ─────────────────────────── fx ───────────────────────────


def test_fx_convert_known_value() -> None:
    value = fx.convert_amount(
        Decimal("100"), Decimal("7.2"), subject="s", from_currency="USD", to_currency="CNY", operands=["fx-claim"]
    )
    assert value.value == Decimal("720.0")


def test_fx_same_currency_is_not_conversion() -> None:
    """同币种**不是**"已换算"——静默返回原值会制造双口径假象。"""
    with pytest.raises(UndefinedComputation):
        fx.convert_amount(Decimal("100"), Decimal("1"), subject="s", from_currency="USD", to_currency="USD", operands=["a"])


def test_fx_zero_rate_is_gap() -> None:
    with pytest.raises(UndefinedComputation):
        fx.convert_amount(Decimal("100"), Decimal("0"), subject="s", from_currency="USD", to_currency="JPY", operands=["a"])


def test_fx_adjusted_return_combines_local_and_fx() -> None:
    # (1 + 0.10) * (7.5 / 7.2) - 1 = 0.14583...
    value = fx.compute_fx_adjusted_return(Decimal("0.10"), Decimal("7.2"), Decimal("7.5"), subject="s", operands=["a"])
    assert value.value.quantize(Decimal("0.0001")) == Decimal("0.1458")


def test_fx_zero_begin_rate_is_gap() -> None:
    with pytest.raises(UndefinedComputation):
        fx.compute_fx_adjusted_return(Decimal("0.10"), Decimal("0"), Decimal("7.5"), subject="s", operands=["a"])


# ─────────────────────────── shares ───────────────────────────


def test_shares_known_values() -> None:
    assert shares.compute_eps(Decimal("10"), Decimal("100"), subject="s", operands=["a"]).value == Decimal("0.1")
    assert shares.compute_value_per_share(Decimal("800"), Decimal("100"), subject="s", operands=["a"]).value == Decimal("8")
    assert shares.compute_share_change_ratio(Decimal("100"), Decimal("110"), subject="s", operands=["a"]).value == Decimal("0.1")


def test_shares_zero_and_negative_are_gaps() -> None:
    with pytest.raises(UndefinedComputation):
        shares.compute_eps(Decimal("10"), Decimal("0"), subject="s", operands=["a"])
    with pytest.raises(UndefinedComputation):
        shares.compute_eps(Decimal("10"), Decimal("-1"), subject="s", operands=["a"])


# ─────────────────────────── growth（Ch4 §D.3） ───────────────────────────


def test_roiic_known_value() -> None:
    value = growth.compute_roiic(Decimal("50"), Decimal("500"), subject="s", operands=["a"])
    assert value.value == Decimal("0.1")


def test_roiic_zero_invested_capital_is_gap() -> None:
    with pytest.raises(UndefinedComputation):
        growth.compute_roiic(Decimal("50"), Decimal("0"), subject="s", operands=["a"])


def test_growth_quality_is_graded_not_single_score() -> None:
    """`Ch4 §D.3`：分档 high/medium/low（**不压成单一分数**）+ 分项明细。"""
    high = growth.assess_growth_quality(
        roiic=Decimal("0.20"), wacc=Decimal("0.10"),
        cash_conversion=Decimal("0.95"), working_capital_change=Decimal("-2"),
        financing_dependence="none", subject="s",
    )
    assert high.grade == "high"
    assert high.flags == []
    assert len(high.detail) == 4

    low = growth.assess_growth_quality(
        roiic=Decimal("0.05"), wacc=Decimal("0.10"),
        cash_conversion=Decimal("0.5"), working_capital_change=Decimal("10"),
        financing_dependence="high", subject="s",
    )
    assert low.grade == "low"
    assert growth.VALUE_DESTRUCTIVE_FLAG in low.flags


def test_growth_quality_roiic_below_wacc_forces_low() -> None:
    """`Ch4 §D.3` 伪码：`if roiic < wacc: return GrowthQuality("low", flag=…)`。

    ROIIC < WACC（毁灭价值）→ **唯一下档 `low`**（曾误判 `medium` + 仅打标志）。
    反向对照见 `test_growth_quality_is_graded_not_single_score` 的 `high` 分支
    （roiic≥wacc 且四项无负 → `high`）。
    """
    result = growth.assess_growth_quality(
        roiic=Decimal("0.05"), wacc=Decimal("0.10"),
        cash_conversion=Decimal("0.9"), working_capital_change=Decimal("0"),
        financing_dependence="none", subject="s",
    )
    assert result.grade == "low"
    assert growth.VALUE_DESTRUCTIVE_FLAG in result.flags


def test_growth_quality_rejects_unknown_financing_dependence() -> None:
    with pytest.raises(UndefinedComputation):
        growth.assess_growth_quality(
            roiic=Decimal("0.20"), wacc=Decimal("0.10"),
            cash_conversion=Decimal("0.95"), working_capital_change=Decimal("0"),
            financing_dependence="unknown-value", subject="s",
        )


# ─────────────────────── C-01：`None`（缺失）→ 缺口对象，不冒泡裸 TypeError ───────────────────────


def test_none_inputs_are_missing_not_typeerror() -> None:
    """★ C-01：`None`（缺失）型数值输入 → `MissingInput`（缺口类异常），**不得**裸 `TypeError`。

    覆盖 AC-05 明列的"缺汇率"等四个调用点（`fx` ×2 / `margin` / `growth`）+ `shares`（同型守卫）。
    """
    with pytest.raises(MissingInput):
        fx.convert_amount(
            Decimal("100"), None, subject="s", from_currency="USD", to_currency="CNY", operands=["a"]
        )
    with pytest.raises(MissingInput):
        fx.compute_fx_adjusted_return(Decimal("0.10"), None, Decimal("7.5"), subject="s", operands=["a"])
    with pytest.raises(MissingInput):
        margin.compute_gross_margin(Decimal("60"), None, subject="s", operands=["a"])
    with pytest.raises(MissingInput):
        growth.compute_roiic(Decimal("50"), None, subject="s", operands=["a"])
    with pytest.raises(MissingInput):
        shares.compute_eps(Decimal("10"), None, subject="s", operands=["a"])
    with pytest.raises(MissingInput):
        core.compute_cagr(None, Decimal("121"), Decimal("2"), subject="s", operands=["a"])


def test_none_inputs_fold_to_compute_gap_via_safe_compute() -> None:
    """★ C-01：`safe_compute` 把 `None` 折叠成 **`ComputeGap`**（含 `missing[]`），不冒泡 `TypeError`。"""
    outcome = safe_compute(
        lambda: fx.convert_amount(
            Decimal("100"), None, subject="p01", from_currency="USD", to_currency="CNY", operands=["a"]
        ),
        kind="fx_convert",
        subject="p01",
    )
    assert isinstance(outcome, ComputeGap)
    assert outcome.missing == ["rate（汇率）"]


def test_none_reverse_control_valid_numbers_still_compute() -> None:
    """反向对照：正常数值照常算出结果（`None` 守卫不误伤）。"""
    assert fx.convert_amount(
        Decimal("100"), Decimal("7.2"), subject="s", from_currency="USD", to_currency="CNY", operands=["a"]
    ).value == Decimal("720.0")
    assert margin.compute_gross_margin(Decimal("60"), Decimal("100"), subject="s", operands=["a"]).value == Decimal("0.6")
    assert growth.compute_roiic(Decimal("50"), Decimal("500"), subject="s", operands=["a"]).value == Decimal("0.1")
    assert shares.compute_eps(Decimal("10"), Decimal("100"), subject="s", operands=["a"]).value == Decimal("0.1")
