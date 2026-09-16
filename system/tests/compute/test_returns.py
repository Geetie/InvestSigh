"""`returns` 单测（`Ch9 §3.4.9` 先复权再总回报；`Ch3 §D.2` 基准三条硬口径）。

覆盖 AC-04（口径违例响亮失败）/ AC-05 / AC-06（分红 / 拆股 / 除零 / 净值混入）。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from scripts.benchmark.return_guard import BenchmarkCaliberError
from scripts.compute import returns
from scripts.compute.contract import CaliberViolation, MissingInput, UndefinedComputation
from scripts.compute.returns import CorporateActionPoint, PricePoint

D1 = date(2026, 1, 1)
D2 = date(2026, 1, 10)
D3 = date(2026, 1, 20)


def _prices(*pairs: tuple[date, str]) -> list[PricePoint]:
    return [PricePoint(day=d, price=Decimal(p)) for d, p in pairs]


def _valid_benchmark(**overrides: object) -> dict:
    """一个**合规**的基准口径对象（`Ch3 §C.3` / `rules/benchmark.yaml` 形态）。"""
    base = {
        "benchmark_id": "p01",
        "return_source": "fund_market_price",
        "proxy_index_used": False,
        "return_basis": {
            "same_start_end": True,
            "currency": "USD",
            "dividends_reinvested": True,
            "price_kind": "market_price_total_return",
            "fee_deducted_again": False,
            "version": "v1",
        },
    }
    base.update(overrides)
    return base


# ─────────────────────────── 总回报算术 ───────────────────────────


def test_price_only_total_return() -> None:
    value = returns.compute_total_return(
        _prices((D1, "100"), (D3, "121")), [], D1, D3,
        subject="sec_x", currency="USD", operands=["prices(sec_x)"],
    )
    assert value.value == Decimal("0.21")
    assert "dividends_reinvested" in value.formula


def test_dividend_reinvested_increases_total_return() -> None:
    """分红 10/股、当日价 100 → 再投资后 shares=1.1 → 总回报 +10%（价格未动）。"""
    value = returns.compute_total_return(
        _prices((D1, "100"), (D2, "100"), (D3, "100")),
        [CorporateActionPoint(effective_date=D2, action_type="div", amount=Decimal("10"))],
        D1, D3,
        subject="sec_x", currency="USD", dividends_reinvested=True, operands=["prices(sec_x)"],
    )
    assert value.value == Decimal("0.1")


def test_dividend_cash_variant_keeps_cash_not_shares() -> None:
    value = returns.compute_total_return(
        _prices((D1, "100"), (D2, "90"), (D3, "90")),
        [CorporateActionPoint(effective_date=D2, action_type="div", amount=Decimal("10"))],
        D1, D3,
        subject="sec_x", currency="USD", dividends_reinvested=False, operands=["prices(sec_x)"],
    )
    # shares=1；cash=10；终值=90+10=100 → 100/100-1 = 0
    assert value.value == Decimal("0")


def test_split_does_not_change_total_return() -> None:
    """2:1 拆股：价格 100→50，股数 ×2 → 总回报恰为 0（先复权再总回报，`Ch9 §3.4.9`）。"""
    value = returns.compute_total_return(
        _prices((D1, "100"), (D3, "50")),
        [CorporateActionPoint(effective_date=D3, action_type="split", ratio=Decimal("2"))],
        D1, D3,
        subject="sec_x", currency="USD", operands=["prices(sec_x)"],
    )
    assert value.value == Decimal("0")


def test_empty_window_is_gap() -> None:
    with pytest.raises(MissingInput):
        returns.compute_total_return(_prices((D3, "100")), [], D1, D2, subject="s", operands=["p"])


def test_single_point_window_is_undefined() -> None:
    with pytest.raises(UndefinedComputation):
        returns.compute_total_return(_prices((D1, "100")), [], D1, D3, subject="s", operands=["p"])


def test_nonpositive_begin_price_is_undefined() -> None:
    with pytest.raises(UndefinedComputation):
        returns.compute_total_return(_prices((D1, "0"), (D3, "121")), [], D1, D3, subject="s", operands=["p"])


def test_nav_point_mixing_is_caliber_violation() -> None:
    """`Ch3 §D.2` ③：净值点**不得**混入市场价总回报（否则静默口径错误）。"""
    points = [
        PricePoint(day=D1, price=Decimal("100")),
        PricePoint(day=D3, price=Decimal("121"), is_nav=True),
    ]
    with pytest.raises(CaliberViolation):
        returns.compute_total_return(points, [], D1, D3, subject="s", operands=["p"])


def test_split_without_ratio_is_gap() -> None:
    with pytest.raises(MissingInput):
        returns.compute_total_return(
            _prices((D1, "100"), (D3, "50")),
            [CorporateActionPoint(effective_date=D3, action_type="split", ratio=None)],
            D1, D3, subject="s", operands=["p"],
        )


def test_unknown_action_type_is_undefined() -> None:
    with pytest.raises(UndefinedComputation):
        returns.compute_total_return(
            _prices((D1, "100"), (D3, "101")),
            [CorporateActionPoint(effective_date=D2, action_type="mystery")],
            D1, D3, subject="s", operands=["p"],
        )


# ─────────────────────────── 基准口径（只经 return_guard） ───────────────────────────


def test_benchmark_return_happy_path_returns_derived_value() -> None:
    value = returns.compute_benchmark_return(
        _valid_benchmark(),
        _prices((D1, "100"), (D3, "121")),
        [], D1, D3,
        subject="p01", operands=["rules/benchmark.yaml#p01", "prices(usAGIX)"],
    )
    assert value.value == Decimal("0.21")
    assert "source=fund_market_price" in value.formula


def test_benchmark_proxy_index_is_rejected_by_return_guard() -> None:
    """① 基准收益必须取基金本身行情（`N3.4-05`）—— 违例由 return_guard 抛，**exit 1 的进程级证据**见 wiring 测试。"""
    with pytest.raises(BenchmarkCaliberError):
        returns.compute_benchmark_return(
            _valid_benchmark(return_source="proxy_index", proxy_index_used=True),
            _prices((D1, "100"), (D3, "121")),
            [], D1, D3, subject="p01", operands=["op"],
        )


def test_benchmark_double_fee_is_rejected_by_return_guard() -> None:
    """② 禁止二次扣费（`N3.4-07`）：`fee_deducted_again` 必须 False。"""
    bad = _valid_benchmark()
    bad["return_basis"] = {**bad["return_basis"], "fee_deducted_again": True}
    with pytest.raises(BenchmarkCaliberError):
        returns.compute_benchmark_return(
            bad, _prices((D1, "100"), (D3, "121")), [], D1, D3, subject="p01", operands=["op"],
        )


def test_nav_return_is_diagnostic_only() -> None:
    """③ `nav_return` 只能标 `diagnostic`（`Ch3 §D.2`）。"""
    result = returns.compute_nav_return_diagnostic(
        _prices((D1, "100"), (D3, "110")), D1, D3, subject="sec_agix"
    )
    assert result["role"] == "diagnostic"
    assert result["value"] == "0.1"
