"""`rules.py` —— **建议决策引擎**（5 规则 + 前置门接线）（`Ch7 §D.1`~`§D.7` / `§E`）。

| 规则 | 判定 | 输出（`action` / `status`） |
|---|---|---|
| **R1 买入** | 研究完成 **且** 可解释预测 **且** 预期绝对收益 > 0 **且** 个股收益 > 同期基准 | `buy` / `active`（**无最低超额幅度门槛**） |
| **R2 卖出** | 有依据预计**无法跑赢基准**（相对跑输确定） | `sell` / `confident_underperform`（即便正收益） |
| **R3 待判断** | **暂时无法判断**是否跑赢（相对收益不确定） | `pending` / `uncertain`（**≠ 卖出**） |
| **R4 维持** | `judgment_change` 全 False（事实/假设/结论均未变） | `maintain` / `active`（`is_new_signal=False`，**不产新信号**） |
| **R5 强制复查** | 单纯价格明显下跌（阈值在**参数层**判定后以布尔传入） | `action` 不变，`recheck_required=True`（**不自动止损/抄底**） |
| **R8**（`N7.3-08`） | 负绝对收益 **禁新增买入** | 降为 `pending` + 记 gap |
| **`boundary_unresolved`**（`§D.3`） | 绝对收益**为负**却**仍可能跑赢基准**，且已有积极建议 | `pending` / `boundary_unresolved`（**挂起待决**，非卖出、非维持） |

★ **三种"消极"状态语义并列、互不并入**（`Ch2 §C.3` / `Ch7 §D.3`）：
  `confident_underperform`（跑不赢）· `uncertain`（无法判断）· `boundary_unresolved`（未决边界）。
  **"无法判断 → 待判断" ≠ 卖出**。

★ **零新增门槛**（`施工图 §8` 纪律 1）：本模块**不读任何参数**、**不设任何阈值**；
  "价格明显下跌"的**阈值判定在参数层完成**，此处只接受**已判定的布尔**。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

from schema.models import (
    OpportunityType,
    Recommendation,
    RecommendationAction,
    RecommendationStatus,
)
from schema.store import append_records

from .gate import (
    ExplainableForecast,
    JudgmentChange,
    RecommendationInput,
    ReturnValue,
    assert_early_judgment_complete,
    can_apply_return_comparison,
)

# 建议期限区间（`Ch2 §D.2` / `rules/freeze.yaml::p04`：范围 `[1Q,1Y]`，**边界含**）。
QUARTER: str = "1q"
YEAR: str = "1y"
HORIZON_ORDER: dict[str, int] = {QUARTER: 0, "2q": 1, "3q": 2, "4q": 3, YEAR: 4}

# 机会类型分类用的价值状态 token（`Ch4 §H.1` 的 `DirectionState`）。
_IMPROVING: frozenset[str] = frozenset({"strengthening"})
_DETERIORATING: frozenset[str] = frozenset({"weakening"})


class HorizonOutOfRange(ValueError):
    """`horizon` 越界 `[1Q,1Y]` —— **拒绝**（`Ch2 §D.2` 规则 1）。"""


# ─────────────────────────── 收益比较（相对 + 绝对） ───────────────────────────


@dataclass(frozen=True)
class ComparisonState:
    """一次收益比较的结果：**绝对方向** + **相对方向**（两者独立，`Ch7 §D.1/§D.3`）。

    - `absolute ∈ {positive, negative, uncertain}`：个股收益相对 0 的方向；
    - `relative ∈ {outperform, underperform, uncertain}`：个股收益相对同期基准的方向。
    """

    absolute: str
    relative: str


def absolute_sign(stock: ReturnValue) -> str:
    """个股收益**绝对方向**：区间全为正 → `positive`；全为负 → `negative`；跨越 0 → `uncertain`。

    ★ 不做任何"数值门槛"判断，只做**符号/区间**判定（`Ch2 §B.2 P-02`：门与决策无置信度阈值）。
    """
    if stock.low > 0:
        return "positive"
    if stock.high < 0:
        return "negative"
    return "uncertain"


def relative_state(stock: ReturnValue, benchmark: ReturnValue) -> str:
    """相对方向：区间**完全分离**才判"确定跑赢/跑不赢"，否则 `uncertain`（`Ch7 §D.1 R2/R3`）。"""
    if stock.low > benchmark.high:
        return "outperform"
    if stock.high < benchmark.low:
        return "underperform"
    return "uncertain"


def compare_returns(stock_forecast: ExplainableForecast, benchmark_forecast: ExplainableForecast) -> ComparisonState:
    """同时给出**绝对**与**相对**方向（`Ch7 §D.1`：R1 需绝对为正，R2/R3 依相对方向）。"""
    return ComparisonState(
        absolute=absolute_sign(stock_forecast.return_range),
        relative=relative_state(stock_forecast.return_range, benchmark_forecast.return_range),
    )


# ─────────────────────────── 决策结果 ───────────────────────────


@dataclass(frozen=True)
class Decision:
    """一次建议决策的结果（`Ch7 §E` 的 8 字段投影；本类是**决策层内部**值对象）。"""

    action: str                    # buy | sell | pending | maintain
    status: str                    # active | confident_underperform | uncertain | boundary_unresolved
    is_new_signal: bool            # 仅 buy / sell 为交易信号；maintain / pending 不产新信号
    recheck_required: bool
    change_reason: str             # 新建议必须有变化理由（`Ch1 §F` G1-02）
    comparison: ComparisonState | None = None
    opportunity_types: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()

    @property
    def is_sell(self) -> bool:
        return self.action == RecommendationAction.sell.value

    @property
    def is_pending(self) -> bool:
        return self.action == RecommendationAction.pending.value


def _decision(
    action: str,
    status: str,
    reason: str,
    *,
    comparison: ComparisonState | None = None,
    recheck_required: bool = False,
    gaps: Sequence[str] = (),
) -> Decision:
    """构造 `Decision`；`is_new_signal` 恒等于"是否为交易动作（buy / sell）"。"""
    trade = action in (RecommendationAction.buy.value, RecommendationAction.sell.value)
    return Decision(
        action=action,
        status=status,
        is_new_signal=trade,
        recheck_required=recheck_required,
        change_reason=reason,
        comparison=comparison,
        gaps=tuple(gaps),
    )


def decide(
    inp: RecommendationInput,
    judgment: JudgmentChange,
    *,
    has_active_positive_recommendation: bool = False,
    price_drop_triggered: bool = False,
) -> Decision | None:
    """建议决策入口（`Ch7 §D.1`）：返回 `Decision`；门不通过 → **`None`（不出建议，记 gap）**。

    - `has_active_positive_recommendation`：该标的是否**已有** `buy`/`maintain` 积极建议
      —— 仅供 `boundary_unresolved`（`§D.3`）判定；**不构成买入门槛**。
    - `price_drop_triggered`：价格明显下跌的**已判定布尔**（阈值在参数层，`§D.1 R5`）
      —— 本函数**不计算**阈值，只据此置 `recheck_required`。

    ★ 决策顺序（确定性、可复现）：**门 → R4 维持 → R2 卖出 → R3 待判断 → 负绝对收益/未决边界 → R1 买入**。
    """
    if not can_apply_return_comparison(inp):
        return None

    comparison = compare_returns(inp.stock_forecast, inp.benchmark_forecast)

    if not judgment.any_changed:
        # R4 维持：事实/假设/结论均未变 → 不产新信号（`Ch7 §D.4`）。
        return _decision(
            RecommendationAction.maintain.value,
            RecommendationStatus.active.value,
            "judgment_unchanged",
            comparison=comparison,
            recheck_required=bool(price_drop_triggered),
        )

    if comparison.relative == "underperform":
        # R2 卖出：有依据预计无法跑赢基准 —— **即便正收益**（`Ch7 §D.1 R2`）。
        return _decision(
            RecommendationAction.sell.value,
            RecommendationStatus.confident_underperform.value,
            "relative_underperformance",
            comparison=comparison,
            recheck_required=bool(price_drop_triggered),
        )

    # ── 以下均为"非确定跑输"（`relative ∈ {outperform, uncertain}` ⇔ 设计所说的"仍可能跑赢"） ──
    if comparison.absolute == "negative" and has_active_positive_recommendation:
        # `boundary_unresolved`：绝对收益为负但**仍可能跑赢**、且该标的**已有积极建议**
        # → 挂起待决（`Ch7 §D.3`）。★ 位置在 R2 与 R8 **之间**的显式未决分支：
        #   既非"卖出"（R2）、亦非"维持"（R4），亦**不产出任何买卖动作**，故不新增买卖条件。
        return _decision(
            RecommendationAction.pending.value,
            RecommendationStatus.boundary_unresolved.value,
            "boundary_unresolved",
            comparison=comparison,
            recheck_required=bool(price_drop_triggered),
            gaps=("boundary_unresolved_needs_calibration",),
        )

    if comparison.relative == "uncertain":
        # R3 待判断：暂时无法判断是否跑赢 → 挂起 + 缺口；**严格 ≠ 卖出**（`Ch7 §D.1 R3`）。
        return _decision(
            RecommendationAction.pending.value,
            RecommendationStatus.uncertain.value,
            "relative_unresolved",
            comparison=comparison,
            recheck_required=bool(price_drop_triggered),
            gaps=("relative_return_uncertain",),
        )

    # relative == outperform
    if comparison.absolute == "negative":
        # R8（`N7.3-08`）：负绝对收益 **禁新增买入** → 降为待判断 + 记 gap。
        return _decision(
            RecommendationAction.pending.value,
            RecommendationStatus.uncertain.value,
            "negative_absolute_return_blocks_new_buy",
            comparison=comparison,
            recheck_required=bool(price_drop_triggered),
            gaps=("negative_absolute_return",),
        )

    if comparison.absolute == "uncertain":
        # 相对跑赢但绝对方向不确定 → 不可确认"预期绝对收益 > 0" → 待判断（不冒充买入）。
        return _decision(
            RecommendationAction.pending.value,
            RecommendationStatus.uncertain.value,
            "absolute_return_unresolved",
            comparison=comparison,
            recheck_required=bool(price_drop_triggered),
            gaps=("absolute_return_uncertain",),
        )

    # R1 买入：绝对为正 **且** 相对跑赢 —— **无最低超额幅度门槛**（`Ch7 §D.1 R1` / T06）。
    return _decision(
        RecommendationAction.buy.value,
        RecommendationStatus.active.value,
        "meets_buy_conditions",
        comparison=comparison,
        recheck_required=bool(price_drop_triggered),
    )


# ─────────────────────────── 机会类型（标注，非准入） ───────────────────────────


def is_improving(value_state_refs: Mapping[str, str]) -> bool:
    """"增长机会扩大"：`growth_momentum_state == strengthening`（`Ch4 §H.1`）。"""
    return value_state_refs.get("growth_momentum_state") == "strengthening"


def is_deteriorating(value_state_refs: Mapping[str, str]) -> bool:
    """"基本面恶化"：增长动力**或**兑现确定性减弱（`Ch4 §H.1` 任一为 `weakening`）。"""
    return (
        value_state_refs.get("growth_momentum_state") in _DETERIORATING
        or value_state_refs.get("certainty_state") in _DETERIORATING
    )


def classify_opportunity(value_state_refs: Mapping[str, str], price_gap_state: str) -> list[str]:
    """机会类型分类（`Ch2 §C.1` / `Ch7 §E.3`）：A = 价值改善且价格未充分反映；B = 未恶化且价格有吸引力。

    ★ **标注，不是准入**（`Ch7 §D.6` / 规则 9）：返回值**不进买入门**，两类均不得被额外门槛拒绝；
      A/B 可同时出现，也可为空（空不影响"能否买入"）。
    """
    out: list[str] = []
    if is_improving(value_state_refs) and price_gap_state == "not_fully_reflected":
        out.append(OpportunityType.type_a.value)
    if not is_deteriorating(value_state_refs) and price_gap_state == "attractive":
        out.append(OpportunityType.type_b.value)
    return out


def annotate_opportunity(
    decision: Decision,
    value_state_refs: Mapping[str, str],
    price_gap_state: str,
) -> Decision:
    """在**门后**给建议**标注**机会类型（不改变 `action`；`Ch7 §D.6`）。"""
    types = tuple(classify_opportunity(value_state_refs, price_gap_state))
    return replace(decision, opportunity_types=types)


# ─────────────────────────── 期限 / schema 校验 ───────────────────────────


def assert_horizon(horizon: str, start_date: date | None) -> None:
    """`Ch2 §D.2` / 规则 1：`start_date` 必填；`horizon ∈ [1Q,1Y]`（**边界含**，越界拒绝）。"""
    if start_date is None:
        raise HorizonOutOfRange("start_date 必填（Ch2 §D.2）")
    if horizon not in HORIZON_ORDER:
        raise HorizonOutOfRange(
            f"horizon 越界: {horizon!r}；合法值（区间 [1Q,1Y]，含边界）{sorted(HORIZON_ORDER, key=HORIZON_ORDER.get)}"
        )


# ─────────────────────────── 建议构造与持久化 ───────────────────────────


def build_recommendation(
    decision: Decision,
    *,
    inp: RecommendationInput,
    recommendation_id: str,
    security_id: str,
    horizon: str,
    start_date: date,
    rule_version: str,
    review_date: date | None = None,
    early_judgment: bool = False,
    assumptions: Sequence[str] = (),
    evidence_gaps: Sequence[str] = (),
    verification_conditions: Sequence[str] = (),
    falsifiers: Sequence[str] = (),
    evidence_version_ids: Sequence[str] = (),
    change_reason: str | None = None,
) -> Recommendation:
    """把 `Decision` 构造为 `schema.models.Recommendation`（`Ch7 §E` 8 字段）。

    - **提前判断三要素**（`early_judgment=True`）：任一为空 → `EarlyJudgmentIncomplete`（**不出建议**）。
    - `action` 只有 `buy` / `sell` / `pending` / `maintain` 四值（**无做空、无仓位/数量字段**，P-04/P-05）。
    - `horizon` 走 `assert_horizon`（`[1Q,1Y]`）。
    """
    assert_horizon(horizon, start_date)
    if early_judgment:
        assert_early_judgment_complete(
            SimpleNamespace(
                assumptions=list(assumptions),
                evidence_gaps=list(evidence_gaps),
                verification_conditions=list(verification_conditions),
            )
        )
    return Recommendation(
        recommendation_id=recommendation_id,
        security_id=security_id,
        company_id=inp.company_id,
        action=RecommendationAction(decision.action),
        horizon=horizon,
        start_date=start_date,
        review_date=review_date,
        status=RecommendationStatus(decision.status),
        rule_version=rule_version,
        evidence_version_ids=list(evidence_version_ids),
        opportunity_types=[OpportunityType(t) for t in decision.opportunity_types],
        assumptions=list(assumptions),
        evidence_gaps=list(evidence_gaps),
        verification_conditions=list(verification_conditions),
        falsifiers=list(falsifiers),
        change_reason=change_reason or decision.change_reason,
        early_judgment=bool(early_judgment),
    )


def persist_recommendation(root: str | Any, rec: Recommendation) -> int:
    """把建议落 `facts/recommendations.jsonl`（**复用** `schema.store.append_records`）。

    返回实际写入行数（1）。追加式不可变 + 文件锁 + pydantic 校验由 `schema.store` 统一承担，
    本模块**不新增**第二条写路径（`G-06` 唯一真源）。
    """
    return append_records(root, "recommendations", [rec])


def compare_and_decide(
    inp: RecommendationInput,
    judgment: JudgmentChange,
    *,
    has_active_positive_recommendation: bool = False,
    price_drop_triggered: bool = False,
    value_state_refs: Mapping[str, str] | None = None,
    price_gap_state: str = "",
) -> Decision | None:
    """`decide` 的便捷封装：可选地在门后**标注**机会类型（不改变 `action`）。"""
    decision = decide(
        inp,
        judgment,
        has_active_positive_recommendation=has_active_positive_recommendation,
        price_drop_triggered=price_drop_triggered,
    )
    if decision is None or value_state_refs is None:
        return decision
    return annotate_opportunity(decision, value_state_refs, price_gap_state)
