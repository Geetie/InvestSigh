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
| **P-08 门**（`Ch2 §B.2`） | 个股**或**基准的"预测"依据是**已实现收益**（`past_return` 等） | `pending` / `uncertain` + `gap=realized_return_not_a_forecast`（**拦 R1 与 R2 两侧**） |

★ **P-08 门是 2026-09-17 冷启动实测后新增**（本仓唯一一次把 `P-08` 从文档变成**运行时**判据）：
  详见 `REALIZED_RETURN_BASIS_IDS` 处的长注释。位置在 R4 **之后**、R2 **之前** —— 两处位置
  各有理由，改动前先读那段。

★ **三种"消极"状态语义并列、互不并入**（`Ch2 §C.3` / `Ch7 §D.3`）：
  `confident_underperform`（跑不赢）· `uncertain`（无法判断）· `boundary_unresolved`（未决边界）。
  **"无法判断 → 待判断" ≠ 卖出**。

★ **零新增门槛**（`施工图 §8` 纪律 1）：本模块**不读任何参数**、**不设任何阈值**；
  "价格明显下跌"的**阈值判定在参数层完成**，此处只接受**已判定的布尔**。
  （P-08 门**不是**新增门槛：它检的是**依据的性质**（前向 / 后向），不是某个数值阈值。）
"""

from __future__ import annotations

import re
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


class FalsifiersMissing(ValueError):
    """`buy` 建议的 `falsifiers` 为空 —— **拒绝**（`Ch2 §D.1` 买入前置必填）。

    承载依据（逐字）：`02_已确认的投资规则/02_实现方案.md:281`
    「`falsifiers`/`unmet_conditions` 字段虽存在，但**未列为买入前置必填**」——
    同一扫描表 `:371` 的 `R-03` 只补了**提前判断三要素**（`assert_early_judgment_complete`），
    `falsifiers` 这一半**仍是缺口**（`01_需求拆解.md:114` 同样标注 ⚠️）。

    ★★ 为什么它与 P-08 是同一件事的两半：`rec-sec-nvda-2026-08-03`（实测）**同时**
    具备「依据已实现收益」与「`falsifiers` 为空」两个特征 —— 前者让它**不该**出 `buy`，
    后者让它**出了也无人能证伪**。两半都必须在**产出侧**拦（验收 §G / `N7.4-08`：
    "缺则三层复盘的预测质量不可核验"）。
    """


# ─────────────────── P-08 前置门：已实现收益**不得**充当收益预测 ───────────────────
#
# `Ch2 §B.2` 反例 **P-08**（逐字）：「依据 `past_return` 的收益预测」——
#   承载 = **程序检查**（`Ch2 02 实现方案` 表：「落 `Ch5 history_guard`（引用）」）。
#   `rules/banned_tokens.yaml` 亦把 P-08 标为「不由本表承载」并指向程序检查。
#
# ★★ 为什么要在这里（决策层）也落一道门 —— 2026-09-17 冷启动端到端**实测**：
#   `scripts/decision/run_decide.py` 用 `_forecast()` 把 **`DerivedValue`（区间已实现
#   总回报）** 包成 `ExplainableForecast`（`drivers=("<subject>:market_price_total_return",)`）
#   送前置门。门只校验"四要素齐备"，**不校验依据是前向还是后向** ⇒ 门通过 ⇒
#   产出 `buy`（`rec-sec-nvda-2026-08-03`）且 `falsifiers` 为空 ⇒
#   ① `G1-02①` 判红（**无变化日**产了新信号）；
#   ② 该建议成为"当前结论"，把**已实现**的 +3.63% 当成"预期跑赢"的证据。
#   会话侧只能事后 `supersedes` 覆盖 —— **那是补丁，不是修复**：该函数仍能在
#   "无前向预测输入"时产出 `buy`。本段即把 P-08 从文档变成**运行时**判据。
#
# ★ 词元口径（`R-06` ①：**不**用子串匹配 —— 本仓已栽过 `unadjusted` ⊃ `adjusted`）：
#   把驱动标识**规范化**（小写 + 非字母数字段折叠为 `_`）后，判据只有两条：
#     ① 全等某个 basis id；② 以 `_<basis id>` 为**后缀**（前缀允许是 `subject:` 段）。
#   ⇒ 边界由 `_` 锚定，不是子串包含。

REALIZED_RETURN_BASIS_IDS: frozenset[str] = frozenset(
    {
        "past_return",          # `P-08` 逐字用词（`Ch2 §B.2`）
        "trailing_return",      # 同义：滚动/过去 N 期已实现
        "realized_return",      # 同义：已实现
        "historical_return",    # 同义：历史
        "market_price_total_return",  # ★ 本仓既有形态（`run_decide._forecast` 的 drivers）
    }
)
"""**已实现收益**的 basis 标识白名单（闭集 —— 判据穷尽、可判定，`R-06` ①）。

★ 闭集而非"含 return 就算"：`Ch4 §H.2` 的前向驱动（如 `dc_revenue_growth`）不含这些 token，
  故**不会**被误伤；反之"任何含 `return` 的标识一律拦"会把合法的**预期**收益口径也拦掉。
"""


def _normalize_basis(token: str) -> str:
    """把驱动标识规范化为 `_` 连接的小写段序列（`NVDA:Market-Price_Total Return` → `nvda_market_price_total_return`）。"""
    segments = [s for s in re.split(r"[^a-z0-9]+", token.strip().lower()) if s]
    return "_".join(segments)


def realized_return_drivers(forecast: ExplainableForecast) -> tuple[str, ...]:
    """该预测的驱动里，**依据已实现收益**的那些（`P-08`）—— 空元组 = 依据是前向的。

    ★ 返回**原始串**（不是规范化后的）以便落进 `change_reason` / `gap`，让"为什么被拦"可复核。
    """
    hits: list[str] = []
    for raw in forecast.drivers or ():
        norm = _normalize_basis(str(raw))
        if not norm:
            continue
        if norm in REALIZED_RETURN_BASIS_IDS or any(
            norm.endswith("_" + basis) for basis in REALIZED_RETURN_BASIS_IDS
        ):
            hits.append(str(raw))
    return tuple(hits)


def realized_return_basis_offenders(inp: RecommendationInput) -> tuple[str, ...]:
    """个股 **与** 基准两侧中，"依据已实现收益"的驱动串（并集，去重保序）。

    ★ 为什么**两侧都要查**：R1/R2 的判定是**相对**比较 ⇒ 只要任一侧的"预测"其实是已实现值，
      这个比较就不成立（左侧是后视、右侧是前视的差是**无意义**的量）。
    """
    out: list[str] = []
    for forecast in (inp.stock_forecast, inp.benchmark_forecast):
        for hit in realized_return_drivers(forecast):
            if hit not in out:
                out.append(hit)
    return tuple(out)


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

    # ── ★ P-08 前置门（**必须早于 R2/R1**）────────────────────────────────────────
    #   「依据 `past_return` 的收益预测」—— 见本模块 `REALIZED_RETURN_BASIS_IDS` 处的长注释。
    #   位置在 R4 **之后**：`judgment_unchanged` 的 `maintain` 不是新信号、也不主张收益，
    #   与"预测依据是否前向"无关，不受本门约束（否则会把"维持原判断"也一并误拦）。
    #   位置在 R2 **之前**：R2 的"预计跑不赢基准"同样是**用比较结果当判断依据**，
    #   依据若是后视值，则该判断与 R1 一样不可成立 —— 只拦 `buy` 是**拦漏了右半边**。
    _realized = realized_return_basis_offenders(inp)
    if _realized:
        return _decision(
            RecommendationAction.pending.value,
            RecommendationStatus.uncertain.value,
            "realized_return_is_not_a_forecast:" + "|".join(_realized),
            comparison=comparison,
            recheck_required=bool(price_drop_triggered),
            gaps=("realized_return_not_a_forecast",),
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
    if decision.action == RecommendationAction.buy.value and not list(falsifiers):
        # ★ 买入前置必填（见 `FalsifiersMissing`）：**在产出侧**拦，而不只在校验侧。
        #   `assert_early_judgment_complete` 管的是"提前判断三要素"，**不管** `falsifiers`。
        raise FalsifiersMissing(
            "buy 建议必须写明证伪条件（`falsifiers`）："
            "`02_已确认的投资规则/02_实现方案.md:281` 明列其为买入前置必填项；"
            "缺则三层复盘的预测质量**不可核验**（`N7.4-08`）"
        )
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


# ── 幂等键 + 版本链（`P7-4`；`Ch9 §3.5` 阶段⑤） ──
#
# 设计口径（逐字）：`Ch9 §3.5` 阶段⑤ 决策的**幂等键** = `(security_id, issued_at, version)`，
# 输出 = `recommendations`（含规则版本 + 证据版本）。
#
# ★ 本实现的映射（**全部落在 `schema/models.py` 现有字段上，不新增冻结字段**，`R-04`）：
#   - `security_id` ↔ `recommendation.security_id`；
#   - `issued_at`   ↔ 判断**输入窗口** `[start_date, review_date]`（`Ch2 §D.2`：`start_date` 必填、
#                      `horizon` 决定复查节点）—— 即"同一输入窗口"；
#   - `version`     ↔ `recommendation.rule_version`（规则版本，`Ch7 §E`）。
#   由此"同一'输入窗口 + 规则版本'重跑 → 不追加"在 `recommendations` 上可判定。
#
# ★ 版本链（让 `schema.store.as_of` 对 `recommendations` 可用）：同一业务键
#   `(security_id, start_date)` 的每次**新增**写入取 `version = 既有同键行数 + 1`，并同步写
#   `recorded_seq`（`TimeMixin`，"同一业务键取最大者为当前版本"）→ `as_of(rows, ["security_id",
#   "start_date"])` 取到最新版本。`Recommendation` 已带 `version` 与 `recorded_seq`
#   （`TimeMixin`），**无需**新增字段。


def recommendation_business_key(row: Mapping[str, Any]) -> tuple[str, str]:
    """建议的**业务键** `(security_id, start_date)` —— 同一"结论"的**唯一分组键**。

    ★★ **公开名**（2026-09-17 由 `_row_recommendation_identity` 更名，原因如下）：

      "一条结论在多行里是同一件事"这个判断，**全仓只能有一处定义**。原先它是**私有**的，
      于是 `scripts/trace/traceback.py::check()` **另写了一套**：按 `recommendation_id` 去重。
      两者在真实数据上**给出不同答案** —— 实测：`rec-sec-nvda-2026-08-03`（v1，`buy`，
      已实现收益依据）与 `rec-sec-nvda-2026-08-03-session-review`（`pending`，明确
      `supersedes` 前者）**是同一个业务键下的前后两版**，但按 `recommendation_id` 去重时
      被当成**两条不同的结论** ⇒ 已被取代的 v1 仍被当"当前结论"评估 ⇒ `G1-03` 永久判红。

      ⇒ 与 `G-45`／`stage_gate` 同一处置：**让消费方 import 生产方的唯一真源**，
      而不是各写一份（本仓最高频的漂移源，症状恒为**假红**）。
    """
    return (str(row.get("security_id", "")), str(row.get("start_date", "")))


def latest_version_row(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    """**同一 `recommendation_id`** 的多条版本行里选**当前版本**（`Ch9 §3.4.2`）。

    排序键 = `(version, recorded_seq)`；同键取**文件中靠后**那条（`>=` 保证后者胜）。
    `version` 缺省视为 `1`、`recorded_seq` 缺省视为 `0`（与 `Recommendation` 的默认一致）。

    ★ 本函数**原在** `scripts.trace.traceback`（私有名 `_latest_version_row`）。
      2026-09-17 内化 `views/` 构建时**迁到本模块并公开**：它回答的是"**这条建议的当前版本是哪行**"
      —— 属决策域语义，且消费方已有三处（`traceback` / `review_return` / `views.build`）。
      三处各写一份正是本仓最高频的漂移源（`G-06`／`G-45`），故收敛到唯一真源。

    ★ 注意与 `current_recommendation_row()` 的**分工**：

    | 函数 | 回答的问题 | 分组 |
    |---|---|---|
    | 本函数 | "**同一条**建议有多版，哪版是当前" | 按 `recommendation_id` |
    | `current_recommendation_row()` | "**同一个业务键**下，哪条建议是当前"（可能换了 id） | 按业务键 + `supersedes` 链 |
    """
    best: Mapping[str, Any] | None = None
    best_key: tuple[int, int] | None = None
    for row in rows:
        key = (int(row.get("version") or 1), int(row.get("recorded_seq") or 0))
        if best_key is None or key >= best_key:
            best_key = key
            best = row
    if best is None:  # pragma: no cover - 调用方保证 rows 非空
        raise ValueError("latest_version_row() 需要非空 rows（不得对空集猜一个版本）")
    return best


def supersedes_map(rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """`{被取代的 recommendation_id → 取代它的 recommendation_id}`。

    ★ 一次修正**可能换 id**（本仓实测形态：`rec-sec-nvda-2026-08-03` →
      `rec-sec-nvda-2026-08-03-session-review`，后者 `supersedes` 前者）。
      此时"哪条是当前"**不能只看 `version`/`recorded_seq`** —— 实测这两行**都是** `version=1`
      且 `recorded_seq=1` ⇒ 任何按数值取最大的实现都退化成"取文件里第一条或最后一条"，
      即**取决于行的物理顺序**。`supersedes` 才是这个关系的**显式声明**。

    ★ 同一行被多条行取代（分叉）时保留**首个**声明者，并由 `current_recommendation_row()`
      的多头检测如实报出 —— 不在此处静默择一。
    """
    out: dict[str, str] = {}
    for row in rows:
        target = str(row.get("supersedes") or "").strip()
        if not target:
            continue
        rid = str(row.get("recommendation_id") or "")
        out.setdefault(target, rid)
    return out


def current_recommendation_row(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    """**同一业务键**的一组建议行 → 取"当前建议"（`supersedes` 链的**末节点**）。

    算法：① 由 `supersedes_map()` 得到"谁取代了谁"；② 末节点 = **没有**被任何行取代的那条；
    ③ 若末节点不唯一（链条分叉）或为空（链成环），**回退**到 `latest_version_row()` 并
    由 `current_recommendation_multihead()` 让调用方如实报出（**不静默**）。

    ★★ **为什么必须有这个函数**（`B-7`，2026-09-17 冷启动实测）：
      `views/company_pages.json` 的 `current_recommendation` 原先按 `recorded_seq` 取最大，
      而真实数据里全部 5 行的 `recorded_seq` **都是 1** ⇒ `>` 比较**从不成立** ⇒ 取到
      **文件中第一条** = `rec-sec-nvda-2026-08-03`（v1、`buy`、已实现收益依据）——
      即**已被评审明确推翻的旧建议**被当作"当前建议"渲染给读者；同一页的"反证"却取自
      取代它的那条（`pending`）⇒ **同页不同源、自相矛盾**。
      `traceback` 也踩同一形态（靠 `>=` 取到靠后那条纯属**巧合**，不是按语义选对）。

    ★ 结论：**"哪条是当前"必须由图关系决定，不能由行的物理顺序决定。**
    """
    if not rows:
        raise ValueError("current_recommendation_row() 需要非空 rows")
    superseded = supersedes_map(rows)
    heads = [r for r in rows if str(r.get("recommendation_id") or "") not in superseded]
    if len(heads) == 1:
        return heads[0]
    # 回退：链成环（heads 空）或分叉（heads >1）—— 一律按版本水位取一条，并让调用方报出。
    return latest_version_row(heads or rows)


def current_recommendation_multihead(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """该组里 `supersedes` 链的**末节点不唯一**时，返回全部末节点 id（唯一时返回空元组）。

    供消费方如实记 note（`R-03`：降级要**显式可见**）—— 判据不因数据分叉而静默择一。
    """
    if not rows:
        return ()
    superseded = supersedes_map(rows)
    heads = [str(r.get("recommendation_id") or "") for r in rows
             if str(r.get("recommendation_id") or "") not in superseded]
    return tuple(heads) if len(heads) > 1 else ()


def _recommendation_identity(rec: Recommendation) -> tuple[str, str]:
    """从 `Recommendation` 取业务键 `(security_id, start_date)`（版本链分组键）。"""
    return (rec.security_id, rec.start_date.isoformat())


def _row_idempotency_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    """从 JSONL 原始行取幂等键（与 `_recommendation_idempotency_key` **同口径**）。"""
    return (
        str(row.get("security_id", "")),
        str(row.get("start_date", "")),
        str(row.get("review_date") or ""),
        str(row.get("rule_version", "")),
    )


def _recommendation_idempotency_key(rec: Recommendation) -> tuple[str, str, str, str]:
    """建议的幂等键 = `Ch9 §3.5` 阶段⑤ `(security_id, issued_at, version)` 的现有字段表达。

    `(security_id, start_date, review_date, rule_version)` —— 见上方映射说明。
    """
    return (
        rec.security_id,
        rec.start_date.isoformat(),
        rec.review_date.isoformat() if rec.review_date else "",
        rec.rule_version,
    )


@dataclass(frozen=True)
class PersistOutcome:
    """一次建议落库的**如实结果**（`Ch9 §3.5` 阶段⑤）。

    | 字段 | 语义 |
    |---|---|
    | `written_ids` | **本轮真正新写入**的 `recommendation_id`（首次该幂等键） |
    | `skipped_ids` | 本轮**考察过、但幂等键已存在故未写入**的 `recommendation_id` |

    ★ **两者互斥**（`pipeline.assert_steps_complete` 的 G-42 互斥校验），由 `__post_init__`
      自己断言 —— 违反即**响亮失败**，不把自相矛盾的结果交给上层。

    ★ 为什么与 `scripts.compute.store.AppendOutcome` **分开定义**（而非共用一个类型）：
      两者是**不同层、不同对象**（`DerivedValue` vs `Recommendation`）的落库结果，
      各自随本人的幂等键演进；合并只会造出一条**假的**跨层耦合。此处模式相同是**同构**，
      不是第二套实现 —— 幂等判定各自只有一处（本模块的 `persist_recommendation_detailed`、
      计算层的 `store.append_derived_value_ids_detailed`）。
    """

    written_ids: tuple[str, ...] = ()
    skipped_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        overlap = sorted(set(self.written_ids) & set(self.skipped_ids))
        if overlap:
            raise ValueError(
                f"PersistOutcome 自相矛盾：{overlap} 同时出现在 written_ids 与 skipped_ids —— "
                "同一 recommendation_id 不可能既'本轮新写入'又'已存在故未写入'"
            )


def persist_recommendation_detailed(root: str | Any, rec: Recommendation) -> PersistOutcome:
    """把建议落 `facts/recommendations.jsonl`，返回 `(written_ids, skipped_ids)` **两个**互斥集合。

    ★ **这是"哪些算已存在"的唯一定义处**（`G-06` 唯一真源）：幂等判据 = 业务键
      `(security_id, start_date, review_date, rule_version)` 是否已在真源中出现
      （`Ch9 §3.5` 阶段⑤）。**任何**调用方（CLI / step 处理器 / 测试）都只能由此得到
      "已存在"这件事，**不得**在别处重算。

    - **幂等命中**（`P7-4`）→ `written_ids=()` + `skipped_ids=(rec.recommendation_id,)`；
    - **新增** → `written_ids=(rec.recommendation_id,)` + `skipped_ids=()`；
    - **版本链**：新增行取 `version = 既有 `(security_id, start_date)` 行数 + 1`，并写
      `recorded_seq = version`，使 `schema.store.as_of` 对该业务键可取到最新版本。
    - 追加式不可变 + 文件锁 + pydantic 校验由 `schema.store` 统一承担，本模块**不新增**
      第二条写路径（`G-06` 唯一真源）。

    ★ **诚实登记的残留**（`R-04`，**不称为"原子"**）：本函数"先读全量判键、再追加"是**两次**
      独立操作，`append_records` 的 `fcntl` 文件锁**只覆盖追加那一步**——并发写者仍可能
      在读写之间插入同键行（首版为单写者约定，`Ch9 §3.10 J6`；`scripts/compute.store`
      的 `append_derived_value_ids_detailed` 采用同一形态，本处与之保持一致，未额外引入第二条锁）。
    """
    from schema.store import read_records

    rows = read_records(root, "recommendations")
    key = _recommendation_idempotency_key(rec)
    if any(_row_idempotency_key(row) == key for row in rows):
        return PersistOutcome(skipped_ids=(rec.recommendation_id,))
    version = sum(1 for row in rows if recommendation_business_key(row) == _recommendation_identity(rec)) + 1
    stamped = rec.model_copy(update={"version": version, "recorded_seq": version})
    if not append_records(root, "recommendations", [stamped]):
        # 未写进任何行，且**不是**幂等命中（键此前不存在）→ 两个集合都为空，
        # **不得**把它记成"已存在故未写入"（那会是一句谎话）。调用方见 `written=[] skipped=[]`
        # 应如实判"本步未完成"。
        return PersistOutcome()
    return PersistOutcome(written_ids=(rec.recommendation_id,))


def persist_recommendation(root: str | Any, rec: Recommendation) -> int:
    """把建议落 `facts/recommendations.jsonl`（**复用** `schema.store.append_records`）。

    返回**实际写入行数**（新增 → `1`；**幂等命中 → `0`**）。

    本函数是 `persist_recommendation_detailed` 的**只取写入侧的计数视图**（既有契约不变：
    调用方只关心"写了几行"）。幂等判定**不在这里重复实现**，见后者的 docstring。
    """
    return len(persist_recommendation_detailed(root, rec).written_ids)


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
