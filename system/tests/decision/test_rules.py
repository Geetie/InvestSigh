"""建议决策引擎单测（`Ch7 §D.1`~`§D.7` / `§E`）。

覆盖 R1~R5 + R8 + `boundary_unresolved`，并**钉住**几条硬约束：
- R1 **无最低超额幅度门槛**（仅略高于基准不被额外门槛拒绝）；
- R2 相对跑输 → 卖出（**即便正收益**）；
- R3 "无法判断" → 待判断，**严格 ≠ 卖出**；
- R4 判断未变 → 维持且**不产新信号**；
- R5 价格明显下跌 → 置强制复查位但**不自动止损/抄底**（`action` 不变）；
- 三种消极状态（跑不赢 / 无法判断 / 未决边界）**并列、互不并入**；
- 机会类型只作**标注**，不改变 `action`。
"""

from __future__ import annotations

from datetime import date

import pytest
from decision_builders import make_forecast, make_input

from scripts.decision.gate import JudgmentChange
from scripts.decision.rules import (
    HorizonOutOfRange,
    absolute_sign,
    annotate_opportunity,
    assert_horizon,
    classify_opportunity,
    compare_returns,
    decide,
    relative_state,
)
from schema.models import OpportunityType, RecommendationAction, RecommendationStatus

CHANGED = JudgmentChange(fact_set_changed=True)
UNCHANGED = JudgmentChange()


def _action(decision) -> str:
    return decision.action


# ───────────────────────── 绝对 / 相对方向判定 ─────────────────────────


def test_absolute_sign_three_way() -> None:
    from decision_builders import make_forecast as _f

    assert absolute_sign(_f("0.10").return_range) == "positive"
    assert absolute_sign(_f("-0.10").return_range) == "negative"
    assert absolute_sign(_f("-0.05", "0.05").return_range) == "uncertain"


def test_relative_state_requires_separation() -> None:
    from decision_builders import make_forecast as _f

    assert relative_state(_f("0.20").return_range, _f("0.05").return_range) == "outperform"
    assert relative_state(_f("0.02").return_range, _f("0.10").return_range) == "underperform"
    # 区间接触（stock.low == bench.high）→ **不**判跑赢（须分离）
    assert relative_state(_f("0.05", "0.20").return_range, _f("0.00", "0.05").return_range) == "uncertain"


def test_compare_returns_reports_both_axes() -> None:
    state = compare_returns(make_forecast("0.10"), make_forecast("0.05"))
    assert state.absolute == "positive"
    assert state.relative == "outperform"


# ───────────────────────── R1 买入 ─────────────────────────


def test_r1_buy_when_positive_and_outperform() -> None:
    inp = make_input(stock=make_forecast("0.10", "0.12"), benchmark=make_forecast("0.05", "0.06"))
    d = decide(inp, CHANGED)
    assert _action(d) == RecommendationAction.buy.value
    assert d.status == RecommendationStatus.active.value
    assert d.is_new_signal is True


def test_r1_has_no_minimum_excess_threshold() -> None:
    """T06：仅**略高于**基准也买入 —— 不得有最低超额幅度门槛（`N7.3-01`）。"""
    inp = make_input(stock=make_forecast("0.0501"), benchmark=make_forecast("0.0500"))
    d = decide(inp, CHANGED)
    assert _action(d) == RecommendationAction.buy.value


# ───────────────────────── R2 卖出 ─────────────────────────


def test_r2_sell_on_confident_underperformance_even_with_positive_return() -> None:
    """T07：正收益但跑不赢 → 卖出并解释（`N7.3-02`）。"""
    inp = make_input(stock=make_forecast("0.05", "0.06"), benchmark=make_forecast("0.10", "0.11"))
    d = decide(inp, CHANGED)
    assert _action(d) == RecommendationAction.sell.value
    assert d.status == RecommendationStatus.confident_underperform.value
    assert d.is_new_signal is True
    assert d.comparison is not None and d.comparison.absolute == "positive"


# ───────────────────────── R3 待判断（≠ 卖出） ─────────────────────────


def test_r3_pending_when_relative_uncertain_never_sell() -> None:
    """T10：无法判断 → 待判断 + 缺口；与卖出**严格分离**（`N7.3-03`）。"""
    inp = make_input(stock=make_forecast("0.05", "0.20"), benchmark=make_forecast("0.08", "0.12"))
    d = decide(inp, CHANGED)
    assert _action(d) == RecommendationAction.pending.value
    assert d.status == RecommendationStatus.uncertain.value
    assert d.is_sell is False
    assert d.is_pending is True
    assert "relative_return_uncertain" in d.gaps
    assert d.is_new_signal is False


# ───────────────────────── R4 维持（不产新信号） ─────────────────────────


def test_r4_maintain_when_judgment_unchanged() -> None:
    inp = make_input(stock=make_forecast("0.10"), benchmark=make_forecast("0.05"))
    d = decide(inp, UNCHANGED)
    assert _action(d) == RecommendationAction.maintain.value
    assert d.is_new_signal is False
    assert d.change_reason == "judgment_unchanged"


@pytest.mark.parametrize(
    "judgment",
    [
        JudgmentChange(fact_set_changed=True),
        JudgmentChange(assumption_changed=True),
        JudgmentChange(conclusion_changed=True),
    ],
)
def test_r4_any_change_breaks_maintain(judgment: JudgmentChange) -> None:
    inp = make_input(stock=make_forecast("0.10"), benchmark=make_forecast("0.05"))
    assert _action(decide(inp, judgment)) == RecommendationAction.buy.value


# ───────────────────────── R5 强制复查（不自动止损） ─────────────────────────


def test_r5_price_drop_sets_recheck_but_keeps_action() -> None:
    inp = make_input(stock=make_forecast("0.05", "0.06"), benchmark=make_forecast("0.10", "0.11"))
    without = decide(inp, CHANGED, price_drop_triggered=False)
    with_drop = decide(inp, CHANGED, price_drop_triggered=True)
    assert _action(without) == _action(with_drop) == RecommendationAction.sell.value
    assert without.recheck_required is False
    assert with_drop.recheck_required is True


def test_r5_price_drop_on_maintain_still_marks_recheck() -> None:
    inp = make_input(stock=make_forecast("0.10"), benchmark=make_forecast("0.05"))
    d = decide(inp, UNCHANGED, price_drop_triggered=True)
    assert _action(d) == RecommendationAction.maintain.value
    assert d.recheck_required is True


# ───────────────────────── R8 负绝对收益禁新增买入 ─────────────────────────


def test_r8_negative_absolute_blocks_new_buy() -> None:
    inp = make_input(stock=make_forecast("-0.10", "-0.05"), benchmark=make_forecast("-0.20", "-0.15"))
    d = decide(inp, CHANGED)
    assert _action(d) == RecommendationAction.pending.value
    assert d.status == RecommendationStatus.uncertain.value
    assert "negative_absolute_return" in d.gaps


# ───────────────────────── boundary_unresolved（未决边界） ─────────────────────────


def test_boundary_unresolved_requires_active_positive_recommendation() -> None:
    inp = make_input(stock=make_forecast("-0.10", "-0.05"), benchmark=make_forecast("-0.20", "-0.15"))
    d = decide(inp, CHANGED, has_active_positive_recommendation=True)
    assert _action(d) == RecommendationAction.pending.value
    assert d.status == RecommendationStatus.boundary_unresolved.value
    assert d.is_sell is False
    assert d.is_pending is True
    assert "boundary_unresolved_needs_calibration" in d.gaps


def test_boundary_unresolved_also_covers_uncertain_relative() -> None:
    """负绝对收益 + 相对**不确定**（仍"可能跑赢"）+ 已有积极建议 → 未决边界（`§D.3`）。"""
    inp = make_input(stock=make_forecast("-0.50", "-0.20"), benchmark=make_forecast("-0.35", "-0.30"))
    d = decide(inp, CHANGED, has_active_positive_recommendation=True)
    assert d.status == RecommendationStatus.boundary_unresolved.value


def test_boundary_unresolved_does_not_auto_sell_or_maintain() -> None:
    """未决边界**不产出任何买卖动作**、也不等于"维持"（`N7.3-09` / 裁决 C7-4）。"""
    inp = make_input(stock=make_forecast("-0.10", "-0.05"), benchmark=make_forecast("-0.20", "-0.15"))
    d = decide(inp, CHANGED, has_active_positive_recommendation=True)
    assert _action(d) not in (RecommendationAction.sell.value, RecommendationAction.buy.value)
    assert _action(d) != RecommendationAction.maintain.value
    assert d.is_new_signal is False


# ───────────────────────── 三种消极状态**并列不并入** ─────────────────────────


def test_three_negative_states_are_distinct_and_not_merged() -> None:
    """`Ch2 §C.3`：`confident_underperform` / `uncertain` / `boundary_unresolved` 三者互不相等。"""
    sell = decide(
        make_input(stock=make_forecast("0.05", "0.06"), benchmark=make_forecast("0.10", "0.11")), CHANGED
    )
    unclear = decide(
        make_input(stock=make_forecast("0.05", "0.20"), benchmark=make_forecast("0.08", "0.12")), CHANGED
    )
    boundary = decide(
        make_input(stock=make_forecast("-0.10", "-0.05"), benchmark=make_forecast("-0.20", "-0.15")),
        CHANGED,
        has_active_positive_recommendation=True,
    )
    statuses = {sell.status, unclear.status, boundary.status}
    assert statuses == {
        RecommendationStatus.confident_underperform.value,
        RecommendationStatus.uncertain.value,
        RecommendationStatus.boundary_unresolved.value,
    }


# ───────────────────────── 机会类型：标注而非准入 ─────────────────────────


def test_classify_opportunity_type_a_and_b() -> None:
    assert classify_opportunity({"growth_momentum_state": "strengthening"}, "not_fully_reflected") == [
        OpportunityType.type_a.value
    ]
    assert classify_opportunity({"growth_momentum_state": "unchanged"}, "attractive") == [
        OpportunityType.type_b.value
    ]
    assert classify_opportunity({"growth_momentum_state": "weakening"}, "attractive") == []


def test_opportunity_types_do_not_change_action() -> None:
    """`§D.6`：把同一标的分别标为 [A]/[B]/[A,B]/[] → `action` 完全不变。"""
    inp = make_input(stock=make_forecast("0.10", "0.12"), benchmark=make_forecast("0.05", "0.06"))
    base = decide(inp, CHANGED)
    variants = [
        annotate_opportunity(base, {"growth_momentum_state": "strengthening"}, "not_fully_reflected"),
        annotate_opportunity(base, {"growth_momentum_state": "unchanged"}, "attractive"),
        annotate_opportunity(base, {"growth_momentum_state": "strengthening"}, "attractive"),
        annotate_opportunity(base, {"growth_momentum_state": "weakening"}, "fully_reflected"),
    ]
    assert {v.action for v in variants} == {base.action}


# ───────────────────────── 期限区间 [1Q, 1Y]（边界含） ─────────────────────────


@pytest.mark.parametrize("horizon", ["1q", "2q", "3q", "4q", "1y"])
def test_assert_horizon_accepts_in_range(horizon: str) -> None:
    assert_horizon(horizon, date(2026, 4, 1))


@pytest.mark.parametrize("horizon", ["1m", "18m", ""])
def test_assert_horizon_rejects_out_of_range(horizon: str) -> None:
    with pytest.raises(HorizonOutOfRange):
        assert_horizon(horizon, date(2026, 4, 1))


def test_assert_horizon_requires_start_date() -> None:
    with pytest.raises(HorizonOutOfRange):
        assert_horizon("2q", None)
