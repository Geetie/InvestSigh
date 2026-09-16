"""`gate.py` —— **建议决策的前置门**（`Ch7 §D.2` / `Ch2 §B.2 P-02/P-06` / `§D.1/§D.2`）。

前置门只做**结构完备性**校验，**不设任何数值置信度阈值**（`Ch2 §B.2 P-02` / A5 / C123-5）：

| 门 | 函数 | 判据 |
|---|---|---|
| 研究完成 | `research_complete()` | 研究深度 ≥ `baseline_done`（`Ch9 §N9.1-05`）**且** 基线齐备（`N9.1-17`） |
| 可解释预测 | `has_explainable_forecast()` | ① 驱动假设集合 ② 判断期限 ③ 收益（点或区间）④ 底稿（`DerivedValue`）缺一不可 |
| 底稿强制 | `require_derived_worksheet()` | `forecast.worksheet` **必须是** `DerivedValue`，裸数字**响亮拒绝**（`N7.3-07`） |
| 可应用收益比较 | `can_apply_return_comparison()` | 前两条同时成立 |
| 提前判断三要素 | `assert_early_judgment_complete()` | `assumptions` / `evidence_gaps` / `verification_conditions` 任一为空 → 拦截（`Ch2 §D.1` A-06） |

★ **防"随意填数字"**（`Ch7 §D.2` / `N7.3-07`）：收益值必须能追到底稿 `DerivedValue`
  （带 `formula` + `operands` + `method_version`）；无 `DerivedValue` 的收益值 → **不生成建议**。
  人工设定值必须显式留在假设层，不冒充测算结果。

★ **参数不进门的输入结构**（`Ch2 §B.2 P-06` / `§B.3` Checker-3）：门输入**不得含**
  `moat_required` / `catalyst_required` / `official_confirmation_required` / `profitability_required` /
  `realization_required` / 裸 `moat` / 裸 `catalyst`；门**只**做"收益相对基准"的结构判定。

★ **关系传染隔离**（`Ch7 §D.5` / `N7.4-11`）：`RecommendationInput` **不含 `relations`、
  不含关联公司结论**（配不变性单测）—— 关系只作**研究路径**，不作结论依据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping, Sequence

from schema.models import DerivedValue, ResearchDepth

# 研究深度序（`Ch9 §N9.1-05` 权威枚举）：>= baseline_done 视为"已完成相应研究"。
#
# ★ 口径对齐登记：`Ch7 §D.2` 的设计文本写作 `research_baseline_done`，
#   而 `Ch9 §N9.1-05` / `schema.models.ResearchDepth` 的**权威 token** 是 `baseline_done`。
#   本模块对齐 **schema 权威枚举**（避免自造 token 与对象模型漂移）。
RESEARCH_DEPTH_ORDER: dict[str, int] = {
    ResearchDepth.position_listed.value: 0,
    ResearchDepth.relations_verified.value: 1,
    ResearchDepth.baseline_done.value: 2,
    ResearchDepth.tracking.value: 3,
}
RESEARCH_BASELINE_DONE: str = ResearchDepth.baseline_done.value


class UnknownResearchDepthError(ValueError):
    """非法 / 空的研究深度 —— **响亮失败**（不静默当作"已完成"或"未完成"）。"""


class RawNumberRejected(TypeError):
    """收益值不是 `DerivedValue`（例如裸数字）—— **响亮拒绝**（`Ch7 §D.2` / `N7.3-07`）。"""


class ReturnRangeError(ValueError):
    """收益区间非法（`low > high`）—— **响亮失败**（不静默交换两端）。"""


class EarlyJudgmentIncomplete(ValueError):
    """提前判断三要素缺项 —— **不出建议、记 gap**（`Ch2 §D.1` A-06）。"""

    def __init__(self, missing: Sequence[str], *, action: str = "记 gap（不出建议）") -> None:
        self.missing = list(missing)
        self.action = action
        super().__init__(f"提前判断缺必填项: {self.missing}；{action}")


# ─────────────────────────── 门的输入结构（`Ch7 §D.5`） ───────────────────────────


@dataclass(frozen=True)
class ResearchBaseline:
    """该标的**自身**的研究基线（`Ch9 §N9.1-17`）：研究深度 + 基线是否齐备。"""

    company_id: str
    research_depth: str        # `ResearchDepth` token
    baseline_complete: bool


@dataclass(frozen=True)
class ReturnValue:
    """收益（**点估或区间**，`Ch7 §D.2` ③）。

    - 点估：`low == high`；
    - 区间：`low < high`；
    - `low > high` → `ReturnRangeError`（**响亮失败**，不静默交换）。
    """

    low: Decimal
    high: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.low, Decimal) or not isinstance(self.high, Decimal):
            raise TypeError("ReturnValue 的两端必须是 Decimal（不接收 float，避免二进制误差）")
        if self.low > self.high:
            raise ReturnRangeError(f"收益区间非法: low={self.low} > high={self.high}")

    @property
    def is_point(self) -> bool:
        """是否点估（两端相等）。"""
        return self.low == self.high


@dataclass(frozen=True)
class ExplainableForecast:
    """"可解释预测"最小形式化（`Ch7 §D.2`）：①驱动假设 ②判断期限 ③收益 ④底稿 —— **缺一不可**。"""

    drivers: tuple[str, ...]              # ① 驱动假设集合（假设层引用）
    horizon: str                          # ② 判断期限（∈ [1Q,1Y]，见 `rules.assert_horizon`）
    return_range: ReturnValue             # ③ 收益（点估或区间）
    worksheet: Any                        # ④ 底稿：**必须**是 `DerivedValue`
    method_version: str                   # 方法版本（可 as-of 复核）


@dataclass(frozen=True)
class JudgmentChange:
    """"判断是否改变"三要素（`Ch7 §D.4`）：事实集 / 假设 / 结论 —— 全 False → 维持（不产新信号）。"""

    fact_set_changed: bool = False
    assumption_changed: bool = False
    conclusion_changed: bool = False

    @property
    def any_changed(self) -> bool:
        """三者任一为真即"判断已变"（`Ch7 §D.4` 逐字）。"""
        return self.fact_set_changed or self.assumption_changed or self.conclusion_changed


@dataclass(frozen=True)
class RecommendationInput:
    """建议决策的输入（`Ch7 §D.5` 逐字结构）。

    ★ **不含 `relations`、不含关联公司结论** —— 供应商与 NVIDIA 有关系只能触发
      "对供应商**独立研究**"任务，**不触发买入**（`Ch7 §D.5` 断言 4 / 裁决 C7-7）。
    """

    company_id: str
    baseline: ResearchBaseline                     # 该标的**自身**研究基线
    stock_forecast: ExplainableForecast            # 该标的**自身**收益预测
    benchmark_forecast: ExplainableForecast        # 基准收益预测
    own_evidence: tuple[str, ...] = field(default_factory=tuple)  # 该标的**自身** claim_id[]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RecommendationInput":
        """从映射构造（**allowlist**，未列出的键默认丢弃 —— 防"顺手加个关联公司影响"）。"""
        return RecommendationInput(
            company_id=str(payload["company_id"]),
            baseline=ResearchBaseline(
                company_id=str(payload["baseline"]["company_id"]),
                research_depth=str(payload["baseline"]["research_depth"]),
                baseline_complete=bool(payload["baseline"]["baseline_complete"]),
            ),
            stock_forecast=_forecast_from_mapping(payload["stock_forecast"]),
            benchmark_forecast=_forecast_from_mapping(payload["benchmark_forecast"]),
            own_evidence=tuple(str(x) for x in payload.get("own_evidence", ())),
        )


def _forecast_from_mapping(node: Mapping[str, Any]) -> ExplainableForecast:
    """从映射构造 `ExplainableForecast`（`worksheet` 保持原样 —— 由门负责判定其类型）。"""
    rng = node["return_range"]
    return ExplainableForecast(
        drivers=tuple(str(x) for x in node.get("drivers", ())),
        horizon=str(node["horizon"]),
        return_range=ReturnValue(low=Decimal(str(rng["low"])), high=Decimal(str(rng["high"]))),
        worksheet=node.get("worksheet"),
        method_version=str(node.get("method_version", "")),
    )


# ─────────────────────────── 门（纯函数） ───────────────────────────


def research_complete(inp: RecommendationInput) -> bool:
    """`Ch7 §D.2`：研究深度 ≥ `baseline_done` **且** 基线齐备。"""
    depth = inp.baseline.research_depth
    if depth not in RESEARCH_DEPTH_ORDER:
        raise UnknownResearchDepthError(
            f"非法 / 空的研究深度 {depth!r}；合法值 {sorted(RESEARCH_DEPTH_ORDER)}"
        )
    return RESEARCH_DEPTH_ORDER[depth] >= RESEARCH_DEPTH_ORDER[RESEARCH_BASELINE_DONE] and bool(
        inp.baseline.baseline_complete
    )


def require_derived_worksheet(forecast: ExplainableForecast) -> DerivedValue:
    """`Ch7 §D.2` / `N7.3-07`：底稿**必须是** `DerivedValue`，否则**响亮拒绝**。

    返回 `DerivedValue` 以便调用方继续用其 `formula` / `operands` / `method_version`。
    """
    worksheet = forecast.worksheet
    if not isinstance(worksheet, DerivedValue):
        raise RawNumberRejected(
            f"收益底稿必须是 DerivedValue（带 formula + operands + method_version），"
            f"实得 {type(worksheet).__name__}（Ch7 §D.2 / N7.3-07：无 DerivedValue 拒绝生成建议）"
        )
    return worksheet


def _forecast_is_explainable(forecast: ExplainableForecast) -> bool:
    """单条预测是否"可解释"（`Ch7 §D.2` ①②③④ 齐备）。"""
    if not isinstance(forecast, ExplainableForecast):
        return False
    if not forecast.drivers or not forecast.horizon:
        return False
    if not isinstance(forecast.worksheet, DerivedValue):
        return False
    return bool(forecast.worksheet.formula and forecast.worksheet.operands)


def has_explainable_forecast(inp: RecommendationInput) -> bool:
    """`Ch7 §D.2`：个股与基准预测**均须**是可解释预测（同一期间/情景口径的前提）。"""
    return _forecast_is_explainable(inp.stock_forecast) and _forecast_is_explainable(
        inp.benchmark_forecast
    )


def can_apply_return_comparison(inp: RecommendationInput) -> bool:
    """`Ch7 §D.2` 逐字：研究完成 **且** 可解释预测 —— 缺任一 → **不可应用收益比较规则**。"""
    return research_complete(inp) and has_explainable_forecast(inp)


def is_early_judgment(rec: Any) -> bool:
    """是否"提前判断"（结论依赖未兑现假设，`Ch7 §D.7`）。

    优先读 `early_judgment`（`schema.models.Recommendation` 字段）；兼容
    `depends_on_unrealized_assumption`（`Ch7 §D.7` 伪代码里的名字）。
    """
    if hasattr(rec, "early_judgment"):
        return bool(rec.early_judgment)
    return bool(getattr(rec, "depends_on_unrealized_assumption", False))


def assert_early_judgment_complete(rec: Any) -> None:
    """`Ch2 §D.1` / `Ch7 §D.7`：提前判断建议**三要素任一为空** → `EarlyJudgmentIncomplete`。

    三要素字段名与 `Ch2 §C.1` / `Ch1 §C.1` **逐字一致**：`assumptions[]` / `evidence_gaps[]` /
    `verification_conditions[]`。

    ★ **`Ch7 §D.7`（约 `:418`）的"同版本写入"断言 = 生产不可满足（已登记，待设计侧裁定）**：

      设计原文逐字（`07_产业链传导与股票建议/02_实现方案.md §D.7`，约 `:418`）：
      `assert rec.trio_written_seq <= rec.version_seq   # 与第一章 G1-01 一致：同版本写入`

      该断言引用 **两个** 字段 `trio_written_seq` 与 `version_seq`。而冻结的
      `schema.models.Recommendation`（`Ch9 §3.3.4` R-07）**两者皆无** —— 它带 `version`（int）
      与 `TimeMixin.recorded_seq`，但**没有** `trio_written_seq`，也**没有** `version_seq`。
      依 `CONVENTIONS.md::R-04`（"设计未写的一律不新增"）本实现**不得**为其补造字段，故：

      - **有判别力的部分**：当对象**确实暴露** `trio_written_seq` / `version_seq` 时，
        `trio_written_seq > version_seq` → 抛 `EarlyJudgmentIncomplete`
        （由 `tests/decision/test_gate.py::test_early_judgment_same_version_assertion_is_conditional`
        钉住 —— 证明本断言**不是恒真**）；
      - **生产恒 no-op 的部分**：对 `Recommendation`（及其构造用的 `SimpleNamespace`）两字段
        皆缺 → 断言**不执行**（no-op）。

      ★ 该"生产不可满足"事实不因此自动满足设计意图：`Ch1 §C.1` G1-01 的**结构性**保证
        （三要素与结论**同一次写入**、同一行内）在本实现成立（三要素与 `version` 同在一条
        `Recommendation` 记录里生成），但设计写的是一条**运行时字段断言**，二者不等价。
        登记见 `system/reports/ws_decision_dod.md`（已知缺口）与
        `system/reports/ws_decision_fix_report.md`（`P7-5`：设计原文引用 + 推理）。
    """
    trio = {
        "assumptions": rec.assumptions,
        "evidence_gaps": rec.evidence_gaps,
        "verification_conditions": rec.verification_conditions,
    }
    missing = [name for name, val in trio.items() if not val]
    if missing:
        raise EarlyJudgmentIncomplete(missing)
    trio_seq = getattr(rec, "trio_written_seq", None)
    version_seq = getattr(rec, "version_seq", getattr(rec, "version", None))
    if trio_seq is not None and version_seq is not None and trio_seq > version_seq:
        raise EarlyJudgmentIncomplete(
            ["same_version_write"],
            action=f"三要素须与结论同版本写入（trio_written_seq={trio_seq} > version_seq={version_seq}）",
        )
