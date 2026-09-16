"""facts/ 22 个追加式 JSONL 的对象模型（唯一真源定义）。

★ **表数由 18 扩至 22**（需求方 2026-09-16 裁定："如果扩表能更方便后续的开发，不留技术债…
  那扩表也没关系"；登记见 `system/reports/phase1_open_tensions.md::T-13` **备选②**）。
  新增 4 张表，**全部按各章 `02_实现方案.md` 的逐字声明**：

  | 新表 | 出处（逐字） | 为什么不能折叠进既有表 |
  |---|---|---|
  | `businesses` | `Ch4 §B.1`（含 schema 块）+ `Ch4 §0` 表第 19 行 | §B.1 方案比选**否决**"挂 `baselines` 下"：baseline 是版本化研究结论，business 是公司结构信息 |
  | `drivers` | `Ch4 §D.1`（schema 块）+ `§C.4`（三层映射）+ `Ch4 §0` 表第 20 行 | 驱动需 `financial_link`（`Ch5 §A.2`：估值经营假设 = `baseline.driver_refs[].financial_link`） |
  | `implied_requirements` | `Ch5 §B.2`（多组解结构）+ `§B.1/§B.3` | 价格反解**必然多解**，需 `solution_set_id` 聚合解集 |
  | `relation_flows` | `Ch7 §B.3`（三边字段表）+ `Ch7 §0` 表第 19 行 | §B.3 比选**否决**"同一 `relations` 表三行"：关系身份被复制三份；并以 MSFT↔NVDA 反例说明三方向无法压成一个 |

  ⚠️ 设计区（`00_*` / `01_`~`11_`）仍写"18 个 JSONL"，其回改由需求方在文档侧执行 —— 见 `stems.py` 脚注。
  ⚠️ `BusinessPosition`（既有 18 表之一）是「公司 × 产业节点的**多业务位置/覆盖维度**」，
     与 `Business`（业务单元 + `mechanism`）**不是一回事**，**不得合并**。

权威出处（逐字对齐，不得偏离）：
- `Ch9 §3.3.3`   目录布局 / JSONL → 对象 / 版本表达方式（表数经需求方裁定由 18 → 22）
- `Ch4 §B.1`     `business` schema（业务单元，`mechanism` 内嵌）
- `Ch4 §C.4`     `driver.financial_link`（指标 → 财务科目 → 每股指标三层映射）
- `Ch4 §D.1`     `driver` schema（`source_class` 7 类 + `mixed`；`duration` / `cost_of_growth` 五项）
- `Ch4 §F.1`     `moat`（六保护对象 / `origin_class` / 代际生存）
- `Ch4 §G.1/§G.4/§H.1/§H.3` `baselines` 六项深度 → 字段映射、未盈利/盈利必填分支、状态与增量
- `Ch5 §B.2`     `implied_requirements` 多组解输出结构
- `Ch5 §D.5/§D.6` 估值输入三类分开存（`input_source`）/ 区间宽度与 `probability` 默认空
- `Ch7 §B.1/§B.3` `relations` 增量 + 三条并行边（`relation_flows`）
- `Ch9 §2.1`     主键设计 / 公司-证券分离 / 多业务位置 / 8 类对象引用关系
- `Ch9 §2.2`     五类时间（time mixin，双时间轴基元）
- `Ch9 §2.3.2`   三类版本事件语义（version_kind）
- `Ch9 §3.3.4`   recommendations 固定字段（v1.1 R-07）
- `Ch9 §3.3.5`   eval_result 固定字段（v1.1 R-29）
- `Ch9 §3.4.5`   NumericClaim 9 字段
- `Ch9 §3.4.2`   version_kind ∈ {forecast_revision, financial_restatement, source_retraction}
- `Ch2 §C.2`     枚举 token 一律小写 + 下划线；"待定"统一 `tbd`
- `Ch2 §C.2 R-15` 同名不同域消歧：`tier` / `license_tier` / `param_tier`
- `Ch3 §C.2`     research_depth 四态 / position_listed / scan_frequency
- `Ch3 §C.3`     benchmark 对象化字段
- `Ch6 §C.1`     claim tier ∈ {primary, secondary_1_5, secondary_tertiary}
- `Ch6 §N6.2-03` official_claim_kind（仅 tier=primary）
- `Ch6 §N6.2-04` claim_form ∈ {original_investigation, citation, estimate, opinion}
- `Ch2 §D.1`     horizon ∈ [1Q, 1Y]（边界含）+ start_date 必填
- `Ch2 §D.2`     同上
- `Ch2 §B.2`     P-03/P-04/P-05/P-07 禁止字段与枚举

纪律约束（写在本文件的代码里，由检查器强制）：
- 纪律 7  `枚举 token 英文小写 + 下划线`；"待定" 统一 `tbd`
- 纪律 8  `同名不同域必须消歧`
- 不得凭"更合理的做法"改动设计（`00_开发Agent开工提示词.md §2.2 第 1 条`）
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum, StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from .stems import JSONL_STEMS


# ─────────────────────────── 待定 token 规范（Ch2 §C.2 R-14） ───────────────────────────
TBD = "tbd"
"""包内所有"待定 / 未确定"枚举值统一为小写 `tbd`。
历史拼写 `tdb` / `to_be_determined` 已废弃，不得再用（Ch2 §C.2 待定 token 规范）。"""


class _Base(BaseModel):
    """全对象基类：禁止未声明字段，保证"一个概念只允许一个字段名"（Ch2 §C.2 R-15 ③）。"""

    model_config = ConfigDict(extra="forbid", frozen=False, validate_assignment=True)


# ─────────────────────────── 枚举（全部小写 + 下划线） ───────────────────────────

class VersionKind(str, Enum):
    """三类版本事件语义不同，必须区分（`Ch9 §2.3.2` / `§3.4.2`）。"""

    forecast_revision = "forecast_revision"          # 预测修订：系统（我们）改，原版本仍为"当时有效判断"
    financial_restatement = "financial_restatement"  # 财务重述：公司（外部事实）改
    source_retraction = "source_retraction"          # 原文更正/撤回：来源改，证据效力转"被否定/被替代"


class ClaimNature(str, Enum):
    """认识论性质，普遍适用（`Ch9 §3.4.6` R-17 / `Ch2 §C.2`）。"""

    fact = "fact"
    plan = "plan"
    forecast = "forecast"
    interpretation = "interpretation"


class ClaimForm(str, Enum):
    """来源形成形式（`Ch6 §N6.2-04`，1.5 手材料拆型）。"""

    original_investigation = "original_investigation"
    citation = "citation"
    estimate = "estimate"
    opinion = "opinion"


class OfficialClaimKind(str, Enum):
    """官方一手披露性质，**仅适用 `tier=primary`**（`Ch6 §N6.2-03`）。"""

    occurred_fact = "occurred_fact"
    forward_guidance = "forward_guidance"
    marketing_claim = "marketing_claim"


class SourceTier(str, Enum):
    """来源分级 `tier`（**不得**与 `license_tier` / `param_tier` 混用，`Ch2 §C.2 R-18`）。

    权威取值：`Ch6 §C.1`。
    """

    primary = "primary"                      # 一手（含 company_official）
    secondary_1_5 = "secondary_1_5"          # 1.5 手
    secondary_tertiary = "secondary_tertiary"  # 二三手


class LicenseTier(str, Enum):
    """数据源许可档（`Ch9 §3.4.11` R-18 / D-01）。`tier` 保留给来源分级。"""

    free_quota = "free_quota"
    paid_subscription = "paid_subscription"


class ParamTier(str, Enum):
    """参数档位（`Ch11 §C`）。消歧 `tier` → `param_tier`。"""

    a = "a"
    b = "b"
    c = "c"


class ParamFreezeStatus(str, Enum):
    """`freeze_param.freeze_status`（`Ch11 §C` / `§F.1`）。

    域 = 待冻结参数。拍板前恒 `tbd`；`tbd → frozen` 单向。
    ⚠️ 与 `BenchmarkFreezeStatus` **同名不同域**（后者域 = 基准对象）。
    设计文档两处均逐字使用 `freeze_status`（`Ch11 §C` 与 `Ch3 §C.3`），
    故按"对象级作用域"实现，不擅自改名；该张力见 `system/reports/phase1_open_tensions.md`。
    """

    tbd = "tbd"
    frozen = "frozen"


class BenchmarkFreezeStatus(str, Enum):
    """`benchmark.freeze_status`（`Ch3 §C.3`）——域 = 基准对象。

    `unfrozen` 时**允许替换代码**（AGIX = 工作假设）；冻结前不得硬编码单一基准代码。
    """

    unfrozen = "unfrozen"
    frozen = "frozen"


class ResearchDepth(str, Enum):
    """研究深度四态（`Ch9 §N9.1-05` / `Ch3 §C.2`）。**可回退**，非单调递增。"""

    position_listed = "position_listed"
    relations_verified = "relations_verified"
    baseline_done = "baseline_done"
    tracking = "tracking"


class MoatLevel(str, Enum):
    """护城河**水平**（`Ch2 §C.2 A-02` / `N2.2-02`）。与 `moat_state` 独立、不得合并为 `moat`。"""

    weak = "weak"
    moderate = "moderate"
    strong = "strong"
    tbd = TBD


class DirectionState(str, Enum):
    """增长动力 / 确定性 / 护城河趋势三者的共用方向枚举（`Ch9 §N9.1-18`）。"""

    strengthening = "strengthening"
    weakening = "weakening"
    unchanged = "unchanged"
    tbd = TBD


class PriceGapState(str, Enum):
    """价格缺口态（`Ch2 §C.1` / `Ch5 §C.2`；历史中文取值已归一，`Ch2 §C.2 R-15 ①`）。"""

    fully_reflected = "fully_reflected"
    not_fully_reflected = "not_fully_reflected"
    attractive = "attractive"


class OpportunityType(str, Enum):
    """机会类型 A/B（`Ch2 §C.1` 规则 2）。**数组、不互斥、可为空**；**不进买入门**。

    ★ 登记在案的张力（`system/reports/phase1_open_tensions.md::T-02`）：
      `Ch2 §C.1` 逐字把枚举写作 "enum A/B"（源稿亦为"机会类型 A 类 / B 类"），
      而 `施工图 §8` 纪律 7 要求"枚举 token 英文小写 + 下划线"。二者在**表面形式**上冲突。
      本实现的取舍 —— **不擅自改动设计的数据契约，也不悄悄放松纪律**：

      - **wire 值 = 设计逐字** `"A"` / `"B"`（JSONL / schema 里出现的 token 不变）
      - **成员名 = 小写下划线** `type_a` / `type_b`（满足纪律 7 对**标识符**的要求）
      - 例外集合被单测 `test_enum_value_exceptions_are_exactly_the_documented_ones` **钉住**，
        任何新增的大写值都会 fail
    """

    type_a = "A"
    type_b = "B"


class RecommendationAction(str, Enum):
    """建议动作（`Ch2 §B.2 P-05`）。**不得含 short / short_sell**；**无 quantity / position**。"""

    buy = "buy"
    sell = "sell"
    pending = "pending"
    maintain = "maintain"


class RecommendationStatus(str, Enum):
    """建议状态（`Ch7 §D`：`boundary_unresolved` 与"跑不赢""无法判断"两端并列不并入，`Ch2 §C.3`）。"""

    active = "active"
    confident_underperform = "confident_underperform"
    uncertain = "uncertain"
    boundary_unresolved = "boundary_unresolved"
    superseded = "superseded"


class BenchmarkRole(str, Enum):
    """`Ch3 §C.3`。"""

    primary = "primary"
    secondary = "secondary"


class TaskStatus(str, Enum):
    """任务五态（`Ch1 §C.3` 状态机 / `Ch8 §C.2`）。"""

    queued = "queued"
    researching = "researching"
    pending_evidence = "pending_evidence"
    done = "done"
    failed = "failed"


class TaskType(str, Enum):
    """任务类型（`Ch1 §C.3`）。"""

    research = "research"
    verify = "verify"
    parse = "parse"
    recheck = "recheck"
    dedup_override = "dedup_override"


class CheckScope(str, Enum):
    """`check_record.scope`（`Ch1 §C.2`）。"""

    collect = "collect"
    verify = "verify"
    recheck = "recheck"
    full = "full"


class EvalLayer(str, Enum):
    """三层复盘分层（`Ch9 §3.3.5` R-29）。**标记字段，不进决策函数**。"""

    research_quality = "research_quality"
    forecast_quality = "forecast_quality"
    investment_result = "investment_result"


class ErrorAxis(str, Enum):
    """错误定位七方向（`Ch9 §3.3.5` R-29）。**标记字段，不进决策函数**。"""

    source = "source"
    business_mechanism = "business_mechanism"
    relation_transmission = "relation_transmission"
    financial_forecast = "financial_forecast"
    price_expectation = "price_expectation"
    benchmark_forecast = "benchmark_forecast"
    timing = "timing"


class RelationProgressStage(str, Enum):
    """合作阶段（`Ch9 §N9.1-07`）。**不得自动跨级推进**（T03）。

    ⚠️ 与 `driver.realization_stage` **分别命名、不得互用**（`Ch2 §C.2 R-15 ②`）。
    """

    tbd = TBD
    discussed = "discussed"
    validation_done = "validation_done"
    qualification_done = "qualification_done"
    design_win = "design_win"
    order_confirmed = "order_confirmed"
    revenue_recognized = "revenue_recognized"


class DriverRealizationStage(str, Enum):
    """驱动**三态**（`Ch4 §D.1` / `§E.2` / `N4.2-01`）。与 `relation_progress_stage` **不得互用**（`Ch2 §C.2 R-15 ②`）。

    ★ **取值域已按设计原文纠正**（本批次修正一处**自创枚举**，两个独立处一致）：
      - `Ch4 §D.1` 逐字：`realization_stage: occurred|planned_guidance_forecast|conditional`；
      - `Ch4 §E.2` 逐字："驱动三态（已发生/计划指引预测/依赖条件） | `driver.realization_stage`"；
      - `Ch4 §J.1`：`N4.2-01`「`drivers.realization_stage`（**三态**）+ `stage_derive.py`」。
      初版写的是 `not_started / ramping / ramped / declining` —— **设计里不存在这四个值**，
      且是**四态**而非三态（`stage_derive.py` 由 `claim_nature` 推导，不存在"爬坡中"这种阶段）。
      该错误值经全仓检索**无任何产出方/消费方**，真仓库 `facts/baselines.jsonl` 的
      `driver_model` 为空数组 ⇒ 纠正**零影响**（见 `tests/unit/test_schema_expand.py`）。
      `tbd` 保留为"尚未推导"的待定 token（`纪律 7` / `Ch2 §C.2`，与 `MoatLevel` / `DirectionState` 同例）。
    """

    tbd = TBD
    occurred = "occurred"                                  # 已发生
    planned_guidance_forecast = "planned_guidance_forecast"  # 计划 / 指引 / 预测
    conditional = "conditional"                            # 依赖条件


class EventType(str, Enum):
    """事件类型（`Ch9 §3.4.7` 指纹组成项之一）。"""

    tbd = TBD
    earnings = "earnings"
    guidance = "guidance"
    order = "order"
    product = "product"
    supply = "supply"
    policy = "policy"
    price_action = "price_action"
    personnel = "personnel"
    other = "other"


class CorporateActionType(str, Enum):
    """公司行动类型（`Ch9 §3.4.9`）。"""

    div = "div"
    split = "split"
    spinoff = "spinoff"


class DisclosureState(str, Enum):
    """披露状态——"不填入猜测数值"的显式表达（`Ch9 §N9.1-09` / `§N9.2-02`）。

    未披露时**必须**显式存 `undisclosed`，**不得**置 0、置 null 或写猜测值。
    """

    disclosed = "disclosed"
    undisclosed = "undisclosed"


# ─────────────────── 枚举 · 本批次新增（`Ch4 §B/§D/§F` · `Ch5 §B/§D` · `Ch7 §B`） ───────────────────
#
# 纪律（与既有枚举同）：成员名英文小写 + 下划线；"待定 / 未判定" 统一 `tbd`
# （`MoatLevel` / `DirectionState` / `EventType` / `RelationProgressStage` 同例）。
# ★ 取值域**只从设计逐字取**，除 `tbd` 外不新增；凡设计写成 `...` 或"注册表驱动"的，
#   一律**不用封闭枚举**（否则新增一类就要改代码，与各章声明的扩展机制冲突）。


class RevenueModel(str, Enum):
    """收入的实现方式（`Ch4 §B.1` yaml 块：`revenue_model: one_time|subscription|usage|license|hybrid`）。"""

    one_time = "one_time"
    subscription = "subscription"
    usage = "usage"
    license = "license"
    hybrid = "hybrid"


class FlowKind(str, Enum):
    """关系流的三条并行边（`Ch7 §B.3`：`flow_kind ∈ {product, capital, demand_signal}`）。

    ★ §B.3 的方案比选**否决**了"同一 `relations` 表三行"，理由：关系身份（证据/阶段/有效期）
      被复制三份、去重与版本追踪困难。三条边的方向**互不相同**，无法压成一个。
    """

    product = "product"                # 产品流：供应商 → 客户
    capital = "capital"                # 资金流：付款方 → 收款方（与产品流相反）
    demand_signal = "demand_signal"    # 需求信号：需求方 → 供应方（与产品流相反）


class PerShareMetric(str, Enum):
    """每股指标（`Ch4 §C.4`：`per_share_metric: eps | fcf_per_share | value_per_share`）。"""

    eps = "eps"
    fcf_per_share = "fcf_per_share"
    value_per_share = "value_per_share"


class DurationMode(str, Enum):
    """驱动可持续时长的表达（`Ch4 §D.1` / `§D.2`：`duration.mode ∈ {point, range}`）。

    §D.2 逐字："未披露用 `mode=range` + 定性标注（**不给伪精确点值**）"。
    """

    point = "point"
    range = "range"


class ConfidenceLevel(str, Enum):
    """判断置信度（`Ch4 §E.1`：`{high, medium, low}`，**不默认给数值概率**）。

    `tbd` = 尚未判定（一律显式存，**不得**用 0.5 / 50% 之类的伪概率顶上，`Ch5 §D.6` / `C45-2`）。
    """

    tbd = TBD
    high = "high"
    medium = "medium"
    low = "low"


class ImportanceClass(str, Enum):
    """驱动重要度分档（`Ch4 §D.1`：`importance_class: high|medium|low`）。

    §D.2 用它做"少量关键驱动"超限时的分级（`primary_drivers(≤5)` + `secondary_watchlist`）。
    """

    high = "high"
    medium = "medium"
    low = "low"


class MoatProtectedObjectKind(str, Enum):
    """**六种保护对象**（`Ch4 §F.1`：`object: share|pricing|cost|customer_retention|capital_return|innovation_efficiency`）。

    §F.1 逐字："多选"。故 `protected_objects` 是**数组**，一条护城河可同时保护多项。
    """

    share = "share"
    pricing = "pricing"
    cost = "cost"
    customer_retention = "customer_retention"
    capital_return = "capital_return"
    innovation_efficiency = "innovation_efficiency"


class MoatStrength(str, Enum):
    """单项保护对象的强度（`Ch4 §F.1`：`strength: high|medium|low`）。"""

    high = "high"
    medium = "medium"
    low = "low"


class MoatOriginClass(str, Enum):
    """护城河来源四类（`Ch4 §F.1` / `§F.2` 表：`origin_class`）。

    §F.2 的判据：`supply_demand_cycle` **不得**判为持久护城河（供给恢复即消失）。
    """

    durable_advantage = "durable_advantage"            # 跨周期、跨代际仍保持
    product_cycle = "product_cycle"                    # 单代领先，下一代可能丢失
    supply_demand_cycle = "supply_demand_cycle"        # 紧缺时高毛利，供给恢复即消失
    operational_efficiency = "operational_efficiency"  # 成本下降来自管理/规模


class MoatWriter(str, Enum):
    """`moat.writer` —— 写路径白名单（`Ch4 §F.3` 断言 A3，**可直接写单测**）。

    §F.3 逐字：`moat.writer ∈ {research_skill, human}`，**不含** `price_ingest` ——
    "股价上涨不自动证明护城河增强"在 **schema 层物理隔离**，而非靠自觉。
    """

    research_skill = "research_skill"
    human = "human"


class InputSource(str, Enum):
    """估值输入的三类来源（`Ch5 §D.5`：`input_source ∈ {fact, model_estimate, manual}`）。

    - `fact`         = 来自 `claim` 的原始数据；
    - `model_estimate` = 模型产出的假设；
    - `manual`       = 人工设定（**须留痕**：`author` + `modified_at`）。

    §D.5 的冲突处理：**不用加权**（承第六章禁加权）——分别保留并**并列展示**。
    """

    fact = "fact"
    model_estimate = "model_estimate"
    manual = "manual"


class SolvedVariable(str, Enum):
    """反解时被解出的那一类变量（`Ch5 §B.2`：`"solved_variable":"reinvestment"` + `§B.4` 五因素表）。

    §B.4 逐字："反解时固定 4 类、解第 5 类"，五类为
    增长 / 利润 / 再投资 / 风险 / 持续时间。故取值域 = 这五类（与 `ImpliedAssumptions` 的键一一对应）。
    """

    growth = "growth"
    margin = "margin"
    reinvestment = "reinvestment"
    risk = "risk"
    duration = "duration"



# ─────────────────────────── 时间 mixin（Ch9 §2.2 / §3.4.1） ───────────────────────────

class TimeMixin(_Base):
    """五类时间 + 补入时间。**双时间轴基元，而非 5 张表**（`Ch9 §2.2.3` / `§3.4.1`）。

    valid_time  { occurred_at, published_at, effective_from }
    system_time { first_seen_at, analyzed_at, recorded_seq }
    backfill    { backfilled_at }
    """

    # valid_time（业务/有效时间）
    occurred_at: datetime | None = None       # 发生时间 / 所属期间
    published_at: datetime | None = None      # 对公众可见时间
    effective_from: datetime | None = None    # 判断生效时间（参与收益计算的业务时间）

    # system_time（记录时间）
    first_seen_at: datetime | None = None     # 本系统第一次拿到的时间（补入时 = 补入日，不得回填为发生日）
    analyzed_at: datetime | None = None       # 分析时间（劳动时间，可变）
    recorded_seq: int | None = None           # 记录序号（同一业务键取最大者为当前版本）

    # backfill
    backfilled_at: datetime | None = None     # 事后补入时间（防"事后信息伪装成当时已知"）


# ─────────────────────────── 数值保真（Ch9 §3.4.5 / §N9.2-02） ───────────────────────────

class Derivation(_Base):
    """派生值的公式与操作数引用。**必须存公式 + 操作数，而非仅结果**（`Ch9 §3.4.5`）。

    基期被重述时可联动重算（T12 ②）。
    """

    formula: str
    operands: list[str] = Field(default_factory=list)   # 操作数引用（claim_id / derived_id / 原始值引用）
    method_version: str


class NumericClaim(TimeMixin):
    """数值保真结构：**9 个要素**（`Ch9 §3.4.5` / `§2.4.2`）。

    | # | 字段           | 说明 |
    |---|---|---|
    | 1 | raw_text       | 原始表文本（verbatim） |
    | 2 | value          | 数值（Decimal，字符串存储，避免浮点误差） |
    | 3 | unit_scale     | 单位/量级（亿 / billion / 百万） |
    | 4 | currency       | 币种 |
    | 5 | period         | 期间（as-reported 标签 + 归一化日期区间） |
    | 6 | metric + basis | 指标 + 口径 |
    | 7 | locator        | 来源定位（页码/段落/表格） |
    | 8 | is_derived     | 是否派生值 |
    | 9 | derivation     | { formula, operands[], method_version } |
    """

    raw_text: str
    value: Decimal
    unit_scale: str
    currency: str
    period_reported: str            # as-reported 期间标签（如 "FY2026 Q2"）
    period_normalized_start: date   # 归一化日期区间（起）
    period_normalized_end: date     # 归一化日期区间（止）
    metric: str
    basis: str                      # 口径（GAAP / non-GAAP 等）
    locator: str
    is_derived: bool = False
    derivation: Derivation | None = None

    @field_serializer("value")
    def _ser_value(self, v: Decimal) -> str:
        """Decimal 以字符串序列化落 JSONL，避免浮点误差（`Ch9 §3.4.5`）。"""
        return str(v)

    @model_validator(mode="after")
    def _check_derived_needs_derivation(self) -> "NumericClaim":
        if self.is_derived and self.derivation is None:
            raise ValueError("is_derived=True 必须携带 derivation（公式 + 操作数 + method_version）")
        return self


class DerivedValue(_Base):
    """确定性计算层的返回值（`Ch9 §3.4.4`）。**必须携带 formula + operands + method_version**。"""

    derived_id: str
    value: Decimal
    formula: str
    operands: list[str] = Field(default_factory=list)
    method_version: str
    computed_at: datetime

    @field_serializer("value")
    def _ser_value(self, v: Decimal) -> str:
        return str(v)


class Period(_Base):
    """可比期间（`Ch9 §N9.1-04`）。as-reported 与归一化**两套并存**，防串期。"""

    reported_label: str          # as-reported 期间标签
    normalized_start: date
    normalized_end: date
    fiscal_year_start_month: int = Field(ge=1, le=12)


# ─────────────────────────── ① 公司与证券 ───────────────────────────

class IndustryNode(TimeMixin):
    """产业节点（`Ch9 §N9.1-02`）。**节点 ≠ 可交易代码**。"""

    node_id: str
    node_name: str
    taxonomy_version: str
    parent_node_id: str | None = None


class Company(TimeMixin):
    """公司 = **研究判断对象**（`Ch9 §2.1.1` / `§2.1.2`）。

    主键 `company_id` 为内部稳定代理键，**永不改变**；
    外部权威 ID（LEI / ISIN）作**可复核映射**（可多对一、可变更、需版本化）。
    """

    company_id: str
    legal_name: str
    economic_group_name: str | None = None
    external_ids: dict[str, str] = Field(default_factory=dict)  # {"lei": ..., "isin": ...}
    fiscal_year_start_month: int = Field(default=1, ge=1, le=12)
    research_depth: ResearchDepth = ResearchDepth.position_listed   # 可回退（Ch3 §C.2 B-05）
    change_log: list[dict[str, Any]] = Field(default_factory=list)  # 状态对象：当前位置 + 独立变更日志


class Security(TimeMixin):
    """证券 = **可交易对象**（`Ch9 §N9.1-03`）。1 公司 → 0..N 证券。

    schema **显式允许 0 证券**：未上市实体（OpenAI / Anthropic）可建研究基线、
    **不产出股票建议**（`Ch9 §2.1.3` R-08）。
    """

    security_id: str
    company_id: str
    ticker: str
    listing_venue: str          # 上市地
    currency: str               # 币种
    trading_session: str        # 交易时段（与"生效价/行情时间"绑定，支撑 T11）
    verified: bool = False      # 未核实证券不得出建议（`Ch3 §C.1` / N3.2-09）


class BusinessPosition(TimeMixin):
    """公司 × 产业节点的**多对多**业务位置（`Ch9 §N9.1-02` / `§2.1.3`）。

    每条关系带"研究深度"与"收录依据"——否则无法满足 Ch3 的分级显示。
    ⚠️ `business_positions` 是合法同名词，**不得**被 P-04 裸词 `position` 扫描误报（`Ch2 §B.1 通则`）。
    """

    company_id: str
    node_id: str
    position_listed: bool = False          # 覆盖维度（`Ch3 §C.2` N3.2-04）
    research_depth: ResearchDepth = ResearchDepth.position_listed
    scan_frequency: str = TBD              # 扫描频率（逐节点不同，`Ch3 §C.2` N3.2-06）
    inclusion_reason: str = ""             # 收录依据（反凑数三字段之一）
    raw_source: str = ""                   # 出处（反凑数三字段之一）
    evidence_strength: str = ""            # 证据强度（反凑数三字段之一）


# ─────────────────────────── ② 产品与关系 ───────────────────────────

class Product(TimeMixin):
    """产品（`Ch9 §N9.1-07`）。代际为**显式枚举**。"""

    product_id: str
    company_id: str
    product_name: str
    generation: str = TBD          # 产品代际（硬件按产品代，服务按合同周期，`00_待拍板项清单` B8/B17）


class Relation(TimeMixin):
    """关系（`Ch9 §N9.1-06` / `§N9.1-08`）。

    业务键 = (主体, 客体, 产品, 关系类型, valid_from)；同对公司多关系可并存。
    """

    relation_id: str
    subject_id: str                 # 主体（公司或产品）
    subject_kind: Literal["company", "product"]
    object_id: str                  # 客体（公司或产品）
    object_kind: Literal["company", "product"]
    related_product_id: str | None = None
    relation_type: str
    relation_progress_stage: RelationProgressStage = RelationProgressStage.tbd
    valid_from: datetime
    valid_to: datetime | None = None            # None = 当前仍有效
    economic_exposure: str = TBD                # 金额/份额/方向；未披露则显式"unknown/undisclosed"
    economic_exposure_disclosure: DisclosureState = DisclosureState.undisclosed
    economic_exposure_caliber: str = TBD        # 口径（年/季）
    currency: str = TBD
    commitment_kind: str = TBD                  # 承诺 vs 实际
    evidence_claim_ids: list[str] = Field(default_factory=list)   # 证据 = 指向 claim_id 的外键，非独立实体


# ─────────── ②b 关系流（`Ch7 §B.3`；本批次新增 1 张表 `facts/relation_flows.jsonl`） ───────────
#
# ★ 落位取舍（`Ch7 §B.3` 的表逐字）：**`relations` 主表 + `relation_flows` 子表（1 关系 → 0..3 流）**，
#   而**不是**"同一张 `relations` 表三行"。否决理由逐字："关系身份（证据/阶段/有效期）被复制
#   三份，去重与版本追踪困难"。
# ★ 为什么不能合并（§B.3 用 **MSFT（云厂商）↔ NVDA** 的具体反例）：
#   ① 方向不一致：产品流 `NVDA→MSFT`、资金流 `MSFT→NVDA`、需求信号 `MSFT→NVDA`，三方向压不成一个；
#   ② 存在性解耦：可以有"MSFT capex 指引↑（需求信号↑）"但**尚无 GPU 订单**；
#   ③ 误把信号当收入：需求信号↑ ≠ NVDA 收入↑（有库存/时滞/验收）；
#   ④ 去重需要分开：同一终端需求可同时驱动多个供应商（`N7.2-09` 根终端需求归因）；
#   ⑤ 证据/阶段不同：订单阶段证据 vs 回款阶段证据不同，合并无法分别记录。


class ProductFlow(_Base):
    """产品流（`Ch7 §B.3` 表：方向**供应商 → 客户**；关键字段 `product_id`、`volume/value`、`stage`）。

    ★ `volume` 的命名取舍：§B.3 的关键字段列写作 "`volume/value`"（量**或**以值表达，二择一），
      **未给**两个独立字段名。依 `Ch2 §C.2 R-15 ③`（一个概念只允许一个字段名）取 **`volume`**
      一个字段承载该边的规模（单位与口径写在值里）；**对价支付**那一侧由 `CapitalFlow.amount`
      承载 —— 它是**另一个域**（对价支付 ≠ 产品交付量），故分名（`R-15 ②`）。
    ★ `stage` 是**自由字符串**：`Ch7 §B.3` 未给取值域；相邻的 `§B.4` 给的是 `relations` 侧
      `relation_progress_stage` 的五者语义层级，而**该名字在本仓库已被既有枚举占用**（见
      `RelationProgressStage` 的 docstring 与报告中的命名冲突登记）⇒ 本实现**不另造第二套枚举**
      （`G-06` 唯一真源），保持字符串。
    """

    product_id: str = TBD
    volume: str = TBD
    stage: str = TBD


class CapitalFlow(_Base):
    """资金流（`Ch7 §B.3` 表：方向**付款方 → 收款方**，与产品流**相反**；关键字段 `amount`、`currency`、`period`）。"""

    amount: str = TBD
    currency: str = TBD
    period: str = TBD


class DemandSignal(_Base):
    """需求信号（`Ch7 §B.3` 表：方向**需求方 → 供应方**；关键字段 `intensity`（定性/定量）、`basis`）。

    ★ §B.3 反例③：需求信号↑ **≠** 收入↑（有库存/时滞/验收）—— 故它与产品流是两条边。
    ★ `Ch7 §A.6`（回改 R-09）：环境层"**AI 投入与需求周期**"的承载方式就是
      "`demand_signal` 边（`relation_flows.flow_kind=demand_signal`）+ 终端需求归因"。
    """

    intensity: str = TBD
    basis: str = TBD


class RelationFlow(TimeMixin):
    """关系流（`Ch7 §B.3`，新表 `facts/relation_flows.jsonl`）。

    1 关系 → 0..3 流（产品流 / 资金流 / 需求信号），三者**各自带方向与字段**。

    ★ `flow_id` 与业务键：设计未给主键名；本实现沿用本项目对"边"对象的既有约定
      （`DependencyEdge.edge_id` + `from_ref`/`to_ref`）取 `flow_id`，**业务键 = (`relation_id`, `flow_kind`)**
      （§B.3："1 关系 → 0..3 流" ⇒ 一个关系的一种流至多一条）。
    ★ `from_ref` / `to_ref`：§B.3 的"方向"列（"供应商 → 客户" / "付款方 → 收款方" / "需求方 → 供应方"）
      **没有逐字字段名**。方向是**必须存**的（§B.3 反例①：三方向无法压成一个），故沿用
      `DependencyEdge` 的 `from_ref`/`to_ref` 命名承载方向的实体两端。
    ★ `flow_kind` 与对应子对象**必须一致在场**：与本项目 `ClaimPropagation.kind` / `alias_override`
      的一致性校验同构（不允许"标了产品流却带资金流字段"的半截行）。
    """

    flow_id: str
    relation_id: str
    flow_kind: FlowKind
    from_ref: str
    to_ref: str
    product_flow: ProductFlow | None = None
    capital_flow: CapitalFlow | None = None
    demand_signal: DemandSignal | None = None
    evidence_claim_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_payload_matches_flow_kind(self) -> "RelationFlow":
        expected = {
            FlowKind.product: "product_flow",
            FlowKind.capital: "capital_flow",
            FlowKind.demand_signal: "demand_signal",
        }[self.flow_kind]
        payloads = {
            "product_flow": self.product_flow,
            "capital_flow": self.capital_flow,
            "demand_signal": self.demand_signal,
        }
        if payloads[expected] is None:
            raise ValueError(f"flow_kind={self.flow_kind.value} 必须携带 {expected}（Ch7 §B.3）")
        extras = [name for name, val in payloads.items() if name != expected and val is not None]
        if extras:
            raise ValueError(
                f"flow_kind={self.flow_kind.value} 不得携带 {extras}（Ch7 §B.3：三条边各自独立，不得混载）"
            )
        return self


# ─────────────────────────── ③ 来源与主张 ───────────────────────────

class Source(TimeMixin):
    """来源（`Ch9 §N9.1-10~12` / `§3.4.8`）。

    登记 7 字段（`Ch9 §N9.3`）：公开入口 / 实际可获得内容 / 抓取方式 /
    可预期延迟 / 更新频率 / 访问限制 / 备选来源。
    """

    source_id: str
    # ── 登记 7 字段 ──
    public_entry: str                                 # 公开入口（URL / API / 渠道）
    obtainable_content_type: str                      # 实际可获得内容边界（full_text / summary / snippet）
    crawl_method: str                                 # 抓取方式（api / crawl / manual）
    expected_latency: str = TBD                       # 可预期延迟（决定"可承诺时效"）
    update_frequency: str = TBD                       # 更新频率
    access_restriction: str = TBD                     # 访问限制（login / paid / rate_limit / geo）
    fallback_source_ids: list[str] = Field(default_factory=list)   # 备选来源（≥1，保证持续）
    # ── 附加 ──
    tier: SourceTier                                  # 来源分级（必填，`Ch6 §N6.2-01`）
    author_id: str | None = None                      # 作者稳定身份 id（N9.1-12）
    source_version: str = "v1"
    content_hash: str = ""                            # 内容哈希：去重与完整性校验
    quality_label: str = TBD                          # **人工 ground truth**，模型自评不得替代（N9.3-11）
    observed_stats: dict[str, Any] = Field(default_factory=dict)   # 自动观测统计（仅辅助信号）
    health: str = TBD                                 # 健康状态（供降级判定）


class ClaimStatus(StrEnum):
    """主张五态（`Ch6 §E.1` 状态机，逐字）。

    ★ **初始态由设计写死为 `pending_verification`** —— `Ch6 §E` 状态机首行：
      `[*] --> pending_verification : ②③④ 提取完成（初始态）`。
      初版把它写成自由字符串 `"active"`，而 **`active` 根本不在五态内**，
      于是**真实链路写出的 claim 带着违约状态**（与我修过的"五类时间全为 None"
      同类：**只有真跑一次才暴露**）。

    ★ 基类必须是 **`StrEnum`**（而非 `(str, Enum)`）：
      后者下 `str(ClaimStatus.pending_verification)` 返回 **`'ClaimStatus.pending_verification'`**
      而不是五态值 —— 任何 `str(status)` 都会被误判（`ws/claim` 工作流实测踩到：
      状态机把每次合法迁移都判成 `UnknownClaimStatus`）。
      `StrEnum` 使 `str(member) == member.value`，**两种写法都对**，陷阱从类型层面消除。
    """

    pending_verification = "pending_verification"
    supported = "supported"
    disputed = "disputed"
    refuted = "refuted"
    superseded = "superseded"


class Claim(TimeMixin):
    """主张（`Ch9 §N9.1-13` / `§3.4.6`）。

    三字段维度不同，**不得互换、不得合并**（`Ch9 §3.4.6` R-17 / D-02）：
    `claim_nature` / `claim_form` / `official_claim_kind`。
    """

    claim_id: str
    source_id: str
    quote_hash: str                                   # 幂等键组成项（`Ch9 §3.5` 阶段②）
    claim_nature: ClaimNature                         # 认识论性质（必填）
    claim_form: ClaimForm                             # 来源形成形式
    official_claim_kind: OfficialClaimKind | None = None   # **仅 tier=primary 适用**
    tier: SourceTier
    tier_basis: str = ""
    publisher_entity: str = ""
    carrier_platform: str = ""                        # 仅辅助特征，**不参与 tier 判定**（`Ch6 §N6.2-09`）
    origin_claim_id: str | None = None                # 引用链：指向上游主张（T01/T12 基础）
    independent_evidence_count: int | None = None
    """**独立佐证基数** —— 该主张**所在内容组**内"独立根"的个数（T-12 契约变更，需求方 2026-09-16 裁定）。

    **口径（逐字对齐 `Ch6 §B.4` / `§C.2` 步骤⑤ / `§C.4`）**：
    - 它是**基数（count）不是权重（weight）**：`Ch6 §B.4` 明令"独立佐证数量（`independent_evidence_count`，
      是**基数**不是权重）"，且 **禁止**给来源设固定系数（`N6.3-13`）。
    - 计数主体 = **同一内容组（指纹相同）内的独立根主张数**；**转述不计**（`Ch6 §F.3`：
      有共同上游 → 只记 `claim_propagation`，计数不增）。
    - `Ch6 §C.4` 权威口径：10 篇转述同一匿名订单 ⇒ 根主张的该值 **== 1**。

    **它不包含什么（防止误用）**：
    - **不含**转述 / 转载 / 二次引用（`§F.3`：与根有共同上游者一律不增）；
    - **不含**权重、热度、情绪、粉丝量、模型自评分（`Ch6 §B.2` / `N6.3-14` 逐字禁令）；
    - **不代表"可信度总分"**，**不得**用于给来源排序加权（`Ch6 §B.2` 三轴职责边界）。

    **取值**：`None` = **未计算**（去重步骤尚未运行 / 旧行——`Ch9 §3.4.2` 追加式不可变，
    既有行不得因新字段报错）；整数 = 该主张作为**根**时的独立佐证基数（由 `scripts/evidence/independence.py`
    的去重步骤写入）。
    """
    supersedes: str | None = None                     # 版本链：新版本指向被取代的旧版本
    version_kind: VersionKind | None = None           # 三类版本事件语义（若为本行是修订版）
    locator: str = ""                                 # 定位（页码/段落/表格/视频时间点）
    status: ClaimStatus = ClaimStatus.pending_verification
    full_text_read: bool = False                      # 由 `scripts/validators/locator_check.py` 程序校验
    impact_capability: dict[str, Any] = Field(default_factory=dict)


class PropagationKind(StrEnum):
    """`claim_propagation.kind` —— 传播记录的**语义类别**（`Ch6 §C.2` 步骤④ / `§C.3`）。

    ★ 为什么需要它（T-11 契约变更，需求方 2026-09-16 裁定）：
      `Ch6 §C.3`（误判的纠正入口 / 人工 override）原设计把结果写独立的
      `facts/claim_alias.jsonl`（`{claim_id, is_independent, reason, operator, at}`）；
      但 `Ch9 §3.3.3` 把 `facts/` 的表集合锁死（**不得增删改名**）⇒ 「再开一张表」
      同样不是实现方能随手做的动作（扩表是**需求方裁定**项：2026-09-16 已由 18 扩至 22，
      见 `schema/stems.py` 脚注）⇒ `claim_alias.jsonl`
      **无落点**。裁定：**并入既有 `claim_propagation`**，以其 `kind` 取值
      `manual_alias_override` 承载"人工确认这两条其实是同一事件"。

    - `restatement`（**默认**）：自动去重判定的**转述**（`Ch6 §C.2` 步骤④）；
      ⚠️ **默认值必须使"旧行"合法**：既有 `claim_propagation` 行无 `kind` 字段
      （`Ch9 §3.4.2` 追加式不可变，不得让既有行失效），取默认即合法。
    - `manual_alias_override`：**人工别名覆盖**（`Ch6 §C.3`：`dedup_override` 任务结果，
      `is_independent` 由操作人强制设定，**追加不覆盖原判定**）。
    """

    restatement = "restatement"
    manual_alias_override = "manual_alias_override"


class AliasOverride(_Base):
    """人工别名覆盖的载荷（**逐字承载** `Ch6 §C.3` 的四要素）。

    `Ch6 §C.3` 原文：结果写 `{claim_id, is_independent, reason, operator, at}`（追加，不覆盖原判定）。
    并入 `claim_propagation` 后：`claim_id` → 行的 `propagated_claim_id`；
    其余四要素 → 本结构。`at` 用 `datetime`（系统时间轴，`Ch9 §2.2`）。
    """

    is_independent: bool              # 操作人强制设定的独立判定（`Ch6 §C.3`）
    reason: str                       # 变更理由（可复核）
    operator: str                     # 操作人
    at: datetime                      # 操作时刻


class ClaimPropagation(TimeMixin):
    """传播记录（`Ch9 §N9.1-13` / `§3.4.7`）。

    十篇转述同一匿名订单 = **1 个 event + N 条 propagation**（T01）；
    转述者**不计独立证据**（`Ch6 §N6.2-11`）。

    ★ `kind` / `alias_override`（T-11）：承载 `Ch6 §C.3` 的人工去重覆盖，
      同时**并入**既有表、**不为人工别名覆盖新开表**（`Ch9 §3.3.3`）。旧行无这两列 ⇒ 取默认（合法）。
    """

    propagation_id: str
    root_claim_id: str                # 根来源主张
    propagated_claim_id: str          # 转述主张
    publisher_entity: str = ""
    carrier_platform: str = ""
    independent_evidence: bool = False  # 转述默认 False，不得提升为独立佐证
    kind: PropagationKind = PropagationKind.restatement   # 语义类别（默认转述；旧行取默认即合法）
    alias_override: AliasOverride | None = None           # 仅 kind=manual_alias_override 时携带

    @model_validator(mode="after")
    def _check_alias_override_consistency(self) -> "ClaimPropagation":
        """`kind` 与 `alias_override` **必须一致**（不得有半截的人工覆盖，`Ch6 §C.3`）。

        - `kind=manual_alias_override` **必须**携带四要素载荷；
        - 其它 `kind` **不得**携带载荷（避免"标了转述却藏人工判定"）。
        旧行（无 `kind`、无载荷）走默认 ⇒ 通过。
        """
        if self.kind is PropagationKind.manual_alias_override and self.alias_override is None:
            raise ValueError(
                "kind=manual_alias_override 必须携带 alias_override（is_independent/reason/operator/at，Ch6 §C.3）"
            )
        if self.kind is not PropagationKind.manual_alias_override and self.alias_override is not None:
            raise ValueError("alias_override 仅在 kind=manual_alias_override 时允许（Ch6 §C.3）")
        return self


# ─────────────────────────── ④ 事件与影响 ───────────────────────────

class Event(TimeMixin):
    """事件（`Ch9 §N9.1-14` / `§3.4.7`）。

    去重身份 = 事件指纹（基于**根来源**而非标题）：
    `sha256(event_type ‖ sorted(company_ids) ‖ metric ‖ period_bucket ‖ bucket(occurred_at,1d) ‖ root_source_id)`
    """

    event_id: str                     # = 去重指纹
    event_type: EventType
    company_ids: list[str] = Field(default_factory=list)
    related_object_refs: list[str] = Field(default_factory=list)
    metric: str = TBD
    period_bucket: str = TBD
    root_source_id: str = ""
    version_kind: VersionKind | None = None    # 重述/撤回产生新行并带标记
    supersedes: str | None = None
    event_alias: list[str] = Field(default_factory=list)   # 误并/漏并的人工纠正入口


class Impact(TimeMixin):
    """影响（`Ch9 §N9.1-16`）。

    六要素：变量 / 方向 / 幅度或范围 / 成立条件 / 反向力量 / 时滞（+ 反证）。
    **缺条件则不成立**。
    """

    impact_id: str
    event_id: str
    affected_company_id: str
    affected_security_id: str | None = None     # 未上市实体可为空
    impact_variable: str
    direction: Literal["positive", "negative", "unclear"]
    magnitude: str = TBD
    magnitude_disclosure: DisclosureState = DisclosureState.undisclosed
    conditions: list[str] = Field(default_factory=list)        # 成立条件（缺则影响不成立）
    counter_forces: list[str] = Field(default_factory=list)    # 反向力量
    time_lag: str = TBD                                        # 体现时滞
    falsifiers: list[str] = Field(default_factory=list)        # 反证
    path_kind: Literal["direct_relation", "inferred_path"] = "direct_relation"
    evidence_claim_ids: list[str] = Field(default_factory=list)


# ─────────── ④b 业务单元与增长驱动（`Ch4 §B` / `§C.4` / `§D`；本批次新增 2 张表） ───────────
#
# ★ 为什么是**独立表**而不是挂 `baselines`（`Ch4 §B.1` 方案比选逐字）：
#   "baseline 是**版本化研究结论**（随研究更新换代），business 是**公司结构信息**
#    （相对稳定，状态对象）；混在一起会让'业务定义'随研究版本爆炸" ⇒ **否决**"挂 baselines"。
# ★ 为什么 `Business` ≠ `BusinessPosition`（既有 18 表之一）：
#   `business_positions` 是「公司 × 产业节点的**多业务位置/覆盖维度**」（`Ch9 §N9.1-02`，
#   带 `research_depth` / `scan_frequency` / 收录依据），而 `business` 是**业务单元 + 赚钱机制**
#   （谁付费 / 交付链路 / 成本与资本结构）。两者**不是一回事，不得合并**。


class Payer(_Base):
    """付费方（`Ch4 §B.1` yaml 块：`mechanism.payer: {party, segment, geographies}`）。

    §B.1 把"谁付费"列为赚钱机制的第一要素（`N4.1-01` 验收："可读'谁付费+链路各段+每段证据'"）。
    """

    party: str                              # 付费主体（谁掏钱）
    segment: str = TBD                      # 客户细分（未披露 → `tbd`，不猜）
    geographies: list[str] = Field(default_factory=list)


class ConversionSegment(_Base):
    """转化链路的**一段**（`Ch4 §B.1`：`{stage, input, output, evidence: [claim_id...]}`）。

    §B.1 的通用四段模型：**获取 → 交付 → 使用 → 变现**（按商业模式实例化：
    硬件 = 订单→排产/出货→验收→收入/回款；云 = 签约→通电/上线→利用率→收费；
    软件 = 使用→付费→续约/留存→增购）。

    ★ `stage` **刻意是自由字符串**（不是封闭枚举）：段名由**注册表驱动**
      （`Ch4 §C.1` `rules/metric-sets.yaml` 的 `stages:`；`§C.3` 明写"新增第 4 类**只改 yaml**、
      **不改代码**"）。把它写成枚举会让 §C.3 的扩展机制失效。

    ★ `pending_evidence` 与 `evidence` **必须一致**（§B.1 / §B.2 逐字）：
      每段必有 `evidence`（`claim_id[]`，接第六章），否则该段**必须**显式标
      `pending_evidence=true` —— 展示层据此呈现"证据未到位"，并**阻止该段进入财务连接**（§C）。
      故本类**拒绝**"证据为空却不标注"的半截行 ——
      这正是本项目最忌的"把没有证据包装成有证据"。
    """

    stage: str
    input: str = TBD
    output: str = TBD
    evidence: list[str] = Field(default_factory=list)   # claim_id[]
    pending_evidence: bool = False

    @model_validator(mode="after")
    def _check_pending_evidence_matches_evidence(self) -> "ConversionSegment":
        if not self.evidence and not self.pending_evidence:
            raise ValueError(
                "该段无证据 (evidence 为空) 时必须显式标 pending_evidence=true —— "
                "不得把'无证据'的段静默当作'有证据'（Ch4 §B.1/§B.2）"
            )
        if self.evidence and self.pending_evidence:
            raise ValueError(
                "evidence 非空时 pending_evidence 必须为 false —— 不得同时声称'有证据'与'证据未到位'"
                "（Ch4 §B.2）"
            )
        return self


class BusinessMechanism(_Base):
    """赚钱机制（`Ch4 §B.1` yaml 块的 `mechanism:` 子树）。

    ★ `cost_structure` / `capital_requirements` 用 `dict[str, Any]`：
      §B.1 原文写作 `cost_structure: {main_cogs[], fixed[], ...}` —— 那个 `...` 表示
      **科目集合开放**（随业务不同）。`extra="forbid"` 下无法表达"开放键"，故按本项目既有约定
      （`Task.cost` / `Benchmark.coverage_profile`）用开放 dict，并把设计的键名写进字段说明 ——
      **不伪造成封闭结构**。
    ★ 二者**不在阶段①骨架内**：`04_公司价值研究与深度标准/01_需求拆解.md §4` 的
      阶段①必填是"赚钱机制骨架（`payer`/`offering`/`conversion_chain`）"，
      而 `N4.1-02`（`cost_structure` + `capital_requirements`）标的是**阶段②**。
    """

    payer: Payer
    offering: list[str]                     # product_id / service_id 列表（§B.1）
    revenue_model: RevenueModel
    conversion_chain: list[ConversionSegment]
    cost_structure: dict[str, Any] = Field(default_factory=dict)
    """`{main_cogs[], fixed[], ...}`（`Ch4 §B.1`）——主要成本科目与固定成本，键集开放。"""

    capital_requirements: dict[str, Any] = Field(default_factory=dict)
    """`{capex, rnd, working_capital}`（`Ch4 §B.1`）——资本投入结构，键集开放。"""


class Business(TimeMixin):
    """业务单元 = **公司结构信息**（`Ch4 §B.1`，新表 `facts/businesses.jsonl`）。

    状态对象（与 `Company` 同例：当前位置 + 独立 `change_log`），**相对稳定**，
    故与版本化的 `baselines` 分表（§B.1 方案比选的否决理由）。

    ★ `business_type` 的命名取舍（本项目"一个概念只允许一个字段名"，`Ch2 §C.2 R-15 ③`）：
      设计里该概念有两个写法 —— `Ch4 §B.1` 的 **schema 块**写 `business_type: hardware`
      （注释指明"`model_class`：见 C"）；`§C.1`/`§C.2` 的**行文与示例代码**写
      `business.model_class`（路由键）。`04_.../01_需求拆解.md §4` 阶段①必填逐字写的是
      "`business` 对象、**`business_type`** 路由" ⇒ **数据契约取 schema 块 / 需求拆解的
      `business_type`**，`§C.2` 的 `business.model_class` 视为同一概念的行文漂移
      （已登记，见报告「剩余不确定性与缺口」）。
    ★ `business_type` **是自由字符串而非封闭枚举**：`§C.3` 明写扩展机制 ——
      "新增第 4 类（广告/代工/游戏内购…）| **只改 `rules/metric-sets.yaml`** | **否**（注册表驱动）"，
      并把未注册类型归入 `MS-GENERIC` 且**显式标注** `unregistered_model_class=true`。
      写成枚举会让"扩展不改代码"这条声明失效。
    """

    business_id: str
    company_id: str
    business_type: str                                  # 路由键（model_class，见 §C）
    metric_set_id: str                                  # → rules/metric-sets.yaml（§C.1）
    mechanism: BusinessMechanism
    unregistered_model_class: bool = False               # §C.3：未注册类型显式标注
    change_log: list[dict[str, Any]] = Field(default_factory=list)


class Duration(_Base):
    """驱动可持续时长（`Ch4 §D.1` / `§D.2`：`duration: {mode: point|range, value: "1-3Y"}`）。

    §D.2 逐字："未披露用 `mode=range` + 定性标注（**不给伪精确点值**）" ⇒
    `value` 是**自由字符串**（可写区间或定性描述），不强制数值 —— 强制数值会逼出伪精确。
    """

    mode: DurationMode
    value: str = TBD


class FinancialLink(_Base):
    """**驱动 → 科目 → 每股指标**的三层映射（`Ch4 §C.4`，落 `facts/drivers.jsonl`）。

    §C.4 原文块：

    ```
    driver.financial_link = {
      accounts: [revenue_segment, gross_margin, opex, capex, working_capital, ...],
      per_share_metric: eps | fcf_per_share | value_per_share,
      formula_ref: <DerivedValue ref>        # 走 scripts/compute/
    }
    ```

    ★ 为什么 `accounts` 是 `list[str]`：§C.4 的清单末位是 `...`（科目集合开放）。
    ★ 为什么单独一个类而不是三个散字段：`Ch5 §A.2` 逐字把
      "`baseline.driver_refs[].financial_link`" 当作**估值的经营假设来源** ——
      它是一级契约面，不是可选装饰。
    """

    accounts: list[str] = Field(default_factory=list)
    per_share_metric: PerShareMetric | None = None
    formula_ref: str = TBD                    # → derived/ 的 DerivedValue（算术走 scripts/compute/）


class CostOfGrowth(_Base):
    """五项"增长的代价"（`Ch4 §D.3` 表 + `§D.4` 环境层承载）。

    | 代价 | 财务科目 | 字段 |
    |---|---|---|
    | 降价 | 收入（单价↓）/ 毛利率 | `price_discount` |
    | 增加资本开支 | 现金流量表投资活动 / CapEx | `capex_requirement` |
    | 库存 | 资产负债表存货 | `inventory_buildup` |
    | 应收 | 资产负债表应收账款 | `receivables_buildup` |
    | 融资 | 筹资活动 / 净负债 | `financing_need` |

    ★ 每项用开放 dict：§D.1 的 schema 块把每一项都写作 `{...}`（内部结构由各业务自定）；
      **不伪造**一个设计未给的结构。
    ★ `financing_need` 同时是 `Ch4 §D.4`（回改 R-09）环境层"融资条件"的**唯一承载**：
      环境项**不得**独立成模块（`Ch3` 模块 denylist）。
    ★ `growth_quality ∈ {high, medium, low}` **不在此**：`§D.3` 明写它由
      `scripts/valuelayer/growth_quality.py` 的 "四项分项判定"（`ROIIC vs WACC` / 现金转化率 /
      营运资金变动 / 融资依赖）算出，是**派生输出**（走 `derived/`），且 `§D.1` 的
      driver schema 块**未**把它列为字段 ⇒ 不作为 `Driver` 的字段（`N4.1-14`
      "收入增速不得作投资回报代理"的替代指标集同属派生层）。
    """

    price_discount: dict[str, Any] = Field(default_factory=dict)
    capex_requirement: dict[str, Any] = Field(default_factory=dict)
    inventory_buildup: dict[str, Any] = Field(default_factory=dict)
    receivables_buildup: dict[str, Any] = Field(default_factory=dict)
    financing_need: dict[str, Any] = Field(default_factory=dict)


class Driver(TimeMixin):
    """增长驱动（`Ch4 §D.1`，新表 `facts/drivers.jsonl`）。

    ★ **本表是驱动对象的唯一真源**（`Ch4 §G.1②`：baseline 只持 `driver_refs[]`）；
      `baseline.driver_model` 收窄为**可由本表派生的估值假设投影**，见 `DriverModel` /
      `project_driver_model`。
    ★ `source_class` 取值域逐字（`Ch4 §D.1` + 回改 **R-21**）：**7 类 + `mixed` 兜底**
      （`N4.1-03` 验收："每驱动有来源标签，可统计分布"）。
    ★ `dependencies` ：`Ch4 §G.1③`（"③ 增长确定性 | `drivers[].realization_stage/timeline/confidence`
      + `dependencies[]`"）+ `N4.2-02`（"`drivers.dependencies[]`（条件类型枚举）"）。
      设计在 `04_.../01_需求拆解.md N4.2-02` 给出的是**中文语义**枚举
      （"依赖客户预算、供应认证、产能、能源、交付、商业化或竞争条件"），**未给 token**；
      且其"扩展"列写着"枚举扩展" ⇒ 本实现取**自由字符串**（token 化待需求方确认，见报告），
      以免"翻译出来的 token"被当成设计契约。
    """

    driver_id: str
    business_id: str
    source_class: Literal[
        "demand_expansion", "share", "price", "product_mix",
        "unit_usage", "penetration", "new_business", "mixed",
    ]
    duration: Duration
    financial_link: FinancialLink
    cost_of_growth: CostOfGrowth
    realization_stage: DriverRealizationStage = DriverRealizationStage.tbd
    timeline: str = TBD
    """兑现时间（`Ch4 §E.1`）。取值域 = **具体日期/期间，或分档** `{≤1Q, 1–4Q, 1–3Y, >3Y}`。

    ★ 分档 token 含 `≤` / `–` 等**非小写下划线**字符 ⇒ 若做成枚举会与
      `纪律 7`（`enum token 英文小写 + 下划线`）冲突（同 `OpportunityType` 的 T-02 形态）。
      故保持自由字符串并在此**逐字记下设计分档**，不擅自改写设计 token。
    """
    confidence: ConfidenceLevel = ConfidenceLevel.tbd
    importance_class: ImportanceClass
    dependencies: list[str] = Field(default_factory=list)
    """依赖条件类型（`Ch4 §G.1③` / `N4.2-02`），见类 docstring 末条的取舍说明。"""
    assumptions: list[str] = Field(default_factory=list)
    """该驱动支撑的**经营假设**（自由文本）。

    ★ 为什么这里需要它（`baseline.driver_model` 的收窄方案要求"可由对象派生"）：
      - `Ch5 §A.1` 逐字：`baseline.driver_model` / `drivers` = "估值的**经营假设**来源"；
      - `Ch4 §G.1②` 逐字：`driver_refs[]` "（含 `financial_link`、`duration`、`cost_of_growth`）"；
      - `01_产品目标与核心闭环/01_需求拆解.md §2.4` 把四要素之一的"**假设**"的承载写成
        `baseline.driver_model` / `valuation_inputs`；
      - `scripts/trace/traceback.py::TraceabilityResult.assumptions` 的注释逐字写着
        "`baseline.driver_model` / `valuation_inputs`(three-source)"，实现读的是
        `baseline.driver_model[].assumptions`。
      ⇒ 假设文本必须**在唯一真源（driver 对象）上**有位置，`driver_model` 才能是**投影**
        而不是"唯一持有者"（否则 `driver_model` 必然是第二个真源）。
      `Ch4 §D.1` 的 schema 块未列该字段 —— 此为本实现依上列四处设计的补齐，已登记。
    """


# ─────────────────────────── ⑤ 研究基线 ───────────────────────────

class ValueStateRefs(_Base):
    """价值状态（`Ch9 §N9.1-18`）。三组状态**可同时并存且不同向**（`Ch2 §C.2` N2.2-04）。"""

    growth_momentum_state: DirectionState = DirectionState.tbd
    certainty_state: DirectionState = DirectionState.tbd
    moat_level: MoatLevel = MoatLevel.tbd      # 护城河**水平**（新增，A-02/N2.2-02）
    moat_state: DirectionState = DirectionState.tbd   # 护城河**趋势**（既有）


class DriverModel(_Base):
    """**估值所需的假设投影**（`Ch9 §N9.1-17` / `Ch4 §A.1` / `Ch5 §A.1`；本批次**语义收窄**）。

    ★ 为什么收窄（本批次解决的**双真源**风险）：
      驱动对象的唯一真源是新的 `facts/drivers.jsonl`（`Driver`）；而 `Ch5 §A.2` 又说
      "估值经营假设 = `baseline.driver_refs[].financial_link`"。若 `baseline.driver_model`
      继续自带 `driver_name` / `realization_stage` / `is_primary` / `linked_accounts`，
      它就会与 `Driver` 的对应字段**各自演进** ⇒ 同一概念两个真源。
      ⇒ **保留但收窄为投影**：只承载 `{driver_id, assumptions[]}`，
      即**身份 + 可从 driver 对象取到的假设文本**（见 `project_driver_model`）。
    ★ `assumptions` 的出处与"为什么 driver 上也要有该字段"：见 `Driver.assumptions` 的 docstring
      （`Ch5 §A.1` / `01_产品目标与核心闭环/01_需求拆解.md §2.4` / `Ch4 §G.1②`）。
    ★ 被移除的四个字段**不是丢信息**：`driver_name` / `realization_stage` / `is_primary` /
      `linked_accounts` 全部可从 `drivers.jsonl` 的对象取到（`realization_stage` → `Driver.realization_stage`；
      `linked_accounts` → `Driver.financial_link.accounts`；`is_primary` → `Driver.importance_class == high` 的
      分类结果，由 §D.2 的"上限/分级"逻辑产出）。真仓库该字段为 `[]` ⇒ 零影响。
    """

    driver_id: str
    assumptions: list[str] = Field(default_factory=list)


def project_driver_model(
    baseline: "Baseline", drivers: dict[str, "Driver"]
) -> list[DriverModel]:
    """由 `baseline.driver_refs[]` + `drivers.jsonl` **派生** `baseline.driver_model`（估值假设投影）。

    ★ 为什么需要一个**代码里的**派生函数（而不是只在测试里比对）：
      存在一条真实的派生路径，`driver_model` 才**不可能**变成第二个真源 ——
      任何消费方想拿估值假设，都可以用本函数现算，无需相信落库的那份副本。
      本函数是**纯函数**（不做 I/O）：`drivers` 由调用方从 `schema.store.read_models(root, "drivers")` 取。

    ★ 缺失引用**响亮失败**（不静默跳过）：`driver_refs` 指向不存在的 driver ⇒ `KeyError`。
      这与 `schema.store::jsonl_path` 对未知 stem 的态度一致（本项目禁静默兜底）。
    """
    out: list[DriverModel] = []
    for ref in baseline.driver_refs:
        driver = drivers[ref]
        out.append(DriverModel(driver_id=driver.driver_id, assumptions=list(driver.assumptions)))
    return out


class MoatProtectedObject(_Base):
    """单项保护对象（`Ch4 §F.1`：`protected_objects` 的元素 `{object, strength, evidence}`）。"""

    object: MoatProtectedObjectKind          # 字段名逐字取 §F.1 的 `object`
    strength: MoatStrength
    evidence: list[str] = Field(default_factory=list)   # claim_id[]


class RealSubstitute(_Base):
    """**真实替代方案**（`Ch4 §J.1` 的 `N4.3-03` 实现载体逐字：
    `moat.real_substitutes[{switch_trigger, switching_cost, actual_switch_evidence}]`）。

    ★ `N4.3-03` 验收："替代方案含切换触发/成本/**真实实例**" —— 故
      `actual_switch_evidence` 是"真实发生过切换"的证据引用，不是推测。
    """

    switch_trigger: str = TBD
    switching_cost: str = TBD
    actual_switch_evidence: list[str] = Field(default_factory=list)


class Moat(_Base):
    """护城河条目（`Ch4 §F.1` yaml 块 + `§F.2` 反误判 + `§F.3` 硬隔离）。

    §F.1 原文块：

    ```yaml
    - moat_id: MOAT-NVDA-01
      mechanism: "..."                       # 优势机制说明（必填）
      protected_objects:                     # ⊆ 六类，多选
        - {object: share|pricing|..., strength: high|medium|low, evidence: [claim_id...]}
      origin_class: durable_advantage|product_cycle|supply_demand_cycle|operational_efficiency
      cross_generation_survival: true|false|unknown
      evidence_claims: [claim_id...]
    ```

    - `mechanism` **必填**（`N4.3-01` 验收："护城河条目含 mechanism"；`§F.2` 的
      `is_durable_moat()` 也要求 `moat.mechanism_explained`）。
    - `cross_generation_survival` 的 `unknown` 用 `None` 表达（三值：`True` / `False` / `None`）。
    - `cross_generation_competitiveness` 来自 `N4.3-05`（"承 `N9.1-07` 代际"，验收："有代际维度竞争评估"）；
      设计**未给**取值域 ⇒ 自由字符串 + `tbd`，不伪造枚举。
    - `writer` 是 `§F.3` 断言 A3 的落点："写路径断言 `moat.writer ∈ {research_skill, human}`，
      不含 `price_ingest`" —— **在 schema 层物理隔离**（对应 C45-5："股价上涨不自动证明护城河增强"）。
    """

    moat_id: str
    mechanism: str
    protected_objects: list[MoatProtectedObject] = Field(default_factory=list)
    origin_class: MoatOriginClass | None = None
    cross_generation_survival: bool | None = None       # None = `unknown`（§F.1 三值之一）
    cross_generation_competitiveness: str = TBD
    real_substitutes: list[RealSubstitute] = Field(default_factory=list)
    evidence_claims: list[str] = Field(default_factory=list)
    writer: MoatWriter = MoatWriter.research_skill


class ValuationRange(_Base):
    """区间表达（`Ch5 §D.6`："区间用 `range{low, high}` 表达宽度"）。"""

    low: Decimal | None = None
    high: Decimal | None = None

    @field_serializer("low", "high")
    def _ser_bounds(self, v: Decimal | None) -> str | None:
        """Decimal 以字符串序列化落 JSONL（`Ch9 §3.4.5`，避免浮点误差）。"""
        return None if v is None else str(v)


class Valuation(_Base):
    """估值对象（`Ch4 §A.1/§A.3/§G.1⑤` + `Ch5 §D.1/§D.2/§D.6`）。

    `Ch4 §A.1` 逐字：`baseline.valuation` 用于"与反向估值对照，形成独立判断"，
    并在建议里承载"收益比较"；`§G.1⑤` 把它与 `valuation_inputs` / `historicals` /
    `DerivedValue` 引用并列为"⑤ 财务与估值"。

    ★ **不重复 DerivedValue 的字段**（避免双真源）：`§D.2` 要求"每个 price range →
      `formula` + `operands` + `method_version` + `share_count` + `compute_date`（N5.3-02 / N9.2-02）"，
      而这些正是 `DerivedValue` 自身的字段 ⇒ 本对象只持 `formula_ref` 指向 `derived/` 的那条记录
      （沿用 `Ch4 §C.4` 对"DerivedValue 引用"的既有命名 `formula_ref: <DerivedValue ref>`），
      **不再落一份副本**。
    ★ `probability` 默认 `None`（`§D.6` + `N5.3-07` + `C45-2`）：**不默认 50/50**，
      "仅当有依据才填"；且 `§J` 的 `J9` 明写依据"须为 `DerivedValue` 且标注来源"。
    """

    method_class: str = TBD
    """估值方法（`Ch5 §D.1`：`rules/valuation-methods.yaml` 的 `method_class → business.model_class` 路由）。
    注册表驱动 ⇒ 自由字符串；未注册类型归入 `generic` 并标注（§D.1 末句）。"""
    range: ValuationRange = Field(default_factory=ValuationRange)
    probability: Decimal | None = None
    formula_ref: str = TBD
    forecast_assumptions: list[str] = Field(default_factory=list)
    """`Ch5 §D.2` 的 `inputs.forecast_assumptions` —— 来自第四章 `drivers`。"""
    valuation_params: list[str] = Field(default_factory=list)
    """`Ch5 §D.2` 的 `inputs.valuation_params` —— 方法参数（模型估计 / 人工设定）。"""

    @field_serializer("probability")
    def _ser_probability(self, v: Decimal | None) -> str | None:
        return None if v is None else str(v)


class AssumptionInput(_Base):
    """五因素之一的估值输入（`Ch5 §D.5`：**事实输入 / 模型估计 / 人工设定三类分开存**）。

    - `input_source` **必填**：不声明来源的假设不得入库（"三类分开存"是 `N5.3-04` 的验收面）；
    - `author` + `modified_at`：`§D.5` 逐字"谁有权写 `manual`：授权用户……须留痕（`author` + `modified_at`）"
      ⇒ 当 `input_source=manual` 时二者**必须非空**（下面的校验器强制）；
      同时这也是 `§D.4` "无历史假设"倒填检测的输入（`assumption_source=manual` 且无变更记录 → 标可疑）。
    - `conflict_status`：`§D.5` 逐字"冲突时标 `conflict_status=\"unresolved\"`"（**不用加权**，并列展示）。
    """

    value: str = TBD
    """点或区间（`Ch5 §B.4` 的"取值方式"列：收入 CAGR / 终值增长、利润率、capex/收入与 ROIIC、WACC、高增长年数）。"""
    input_source: InputSource
    author: str = ""
    modified_at: datetime | None = None
    conflict_status: str = ""

    @model_validator(mode="after")
    def _check_manual_needs_trace(self) -> "AssumptionInput":
        if self.input_source is InputSource.manual and not (self.author and self.modified_at):
            raise ValueError(
                "input_source=manual 必须留痕（author + modified_at）—— Ch5 §D.5："
                "人工设定须可复核；无留痕的 manual 亦是 §D.4 的倒填可疑项"
            )
        return self


class ValuationInputs(_Base):
    """估值假设的五因素（`Ch4 §A.3`："`valuation_inputs` | 三类输入（fact/model_estimate/manual）
    | `N5.3-04`（第五章写，第四章承载）"；`Ch4 §G.1⑤`："`valuation_inputs`（五因素→每股价值）"）。

    字段名逐字取 `Ch5 §B.4` 的假设组合表：
    `growth_assumption` / `margin_assumption` / `reinvestment_assumption` /
    `risk_assumption` / `duration_assumption`。
    ★ `risk_assumption`（WACC / 折现率）另有一处逐字来源：`Ch5 §D.5` 的 **R-09**——
      环境层"利率与折现要求"作为估值假设输入注入，且 `input_source ∈ {model_estimate, manual}`。
    """

    growth_assumption: AssumptionInput | None = None
    margin_assumption: AssumptionInput | None = None
    reinvestment_assumption: AssumptionInput | None = None
    risk_assumption: AssumptionInput | None = None
    duration_assumption: AssumptionInput | None = None


class Increment(_Base):
    """增量更新**六要素**（`Ch4 §H.3` / `N4.5-01`；`N4.5-04` 另有 `reason`）。

    `Ch4 §H.3` 逐字的 increment 块：

    ```json
    "increment":{"old_judgment":"...","new_info":["CLM-x"],"new_judgment":"...",
                 "affected_period":"FY2027Q1","supporting_evidence":["CLM-x"],
                 "counter_evidence":[]}
    ```

    ★ `new_info` **必须非空**（`min_length=1`）：`§H.2` 逐字 ——
      "状态变更函数**仅在 `new_info != ∅ AND affects_dimension` 时运行**；否则保持原值 + 记录核查"，
      `N4.5-05` 亦要求"无新信息日不改变状态、不产新信号"。
      ⇒ 一条 `new_info` 为空的 `increment` 就是"制造出来的变化"，**在 schema 层拒绝**。
    ★ `reason` 来自 `N4.5-04`（"`increment.reason`（引用新信息）| 每次状态变更含原因"）。
    """

    old_judgment: str
    new_info: list[str] = Field(min_length=1)
    new_judgment: str
    affected_period: str
    supporting_evidence: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    reason: str = ""


class Baseline(TimeMixin):
    """研究基线（`Ch9 §N9.1-17` / `§N9.1-18`）。主键 = (`company_id`, `version`)，**版本化**。

    本批次按 `Ch4 §G.1` 六项深度 → 字段映射、`§A.3`（第 22 行同一张表）"本章新增字段"、
    `§G.4` 盈利/未盈利必填分支、`§H.3` 增量行 逐条补齐。**新增字段一律可选且带默认值**
    （`Ch9 §3.4.2` 追加式不可变 ⇒ 契约变更不得让既有行失效）。

    | 六项深度（`Ch4 §G.1`） | 字段 |
    |---|---|
    | ① 业务与产业位置 | `business_refs[]` + `relations`（既有表） |
    | ② 增长驱动 | `driver_refs[]`（对象在 `drivers.jsonl`） |
    | ③ 增长确定性 | `drivers[].realization_stage/timeline/confidence` + `dependencies[]`（在 `drivers.jsonl`） |
    | ④ 护城河 | `moat[]` |
    | ⑤ 财务与估值 | `valuation_inputs` + `historicals`（= 既有 `historical_numeric_claims`）+ `valuation.formula_ref` |
    | ⑥ 价格与行动 | 引用第五章三份判断 + 第七章建议（**不落本表**，`Ch4 §A.1`） |
    """

    baseline_id: str
    company_id: str
    version: int
    business_mechanism: str                                        # 经营机制（"谁付费 + 转换链路各段"）
    historical_numeric_claims: list[str] = Field(default_factory=list)
    """历史基线数据（引用 `NumericClaim`）。★ 即 `Ch4 §G.1⑤` 逐字写的 `historicals`
    —— **沿用既有字段名**，不新增 `historicals` 造第二个名字（`R-15 ③` 一概念一字段名）。"""
    driver_model: list[DriverModel] = Field(default_factory=list)
    """驱动模型（**估值假设投影**，见 `DriverModel`）。真源 = `drivers.jsonl`。"""
    value_state_refs: ValueStateRefs = Field(default_factory=ValueStateRefs)
    """价值状态（`Ch4 §H.1` 的 `value_state`；`§H.4②` 的 `value_state_refs()` 输出四字段
    `growth_momentum_state` / `certainty_state` / `moat_level` / `moat_state` —— 与 `ValueStateRefs` 逐一对应）。"""
    conclusion_version: int = 1
    evidence_claim_ids: list[str] = Field(default_factory=list)
    falsifiers: list[str] = Field(default_factory=list)            # 与结论**同版本写入**（`Ch1 §C.1` G1-01）
    unmet_conditions: list[str] = Field(default_factory=list)
    verification_conditions: list[str] = Field(default_factory=list)
    falsifier_written_seq: int | None = None
    expiry_review: date | None = None

    # ── `Ch4 §A.3` / `§0` 表第 22 行：`baselines` 上的新增字段 ──
    business_refs: list[str] = Field(default_factory=list)         # business_id[]（§B.1 引用；N4.1-01）
    driver_refs: list[str] = Field(default_factory=list)           # driver_id[]（§D.1 引用；N4.1-03）
    moat: list[Moat] = Field(default_factory=list)                 # 护城河条目（§F；N4.3）
    valuation: Valuation = Field(default_factory=Valuation)        # 估值对象（§A.1；与反向估值对照）
    valuation_inputs: ValuationInputs = Field(default_factory=ValuationInputs)
    increment: Increment | None = None                             # 增量更新六要素（§H.3；N4.5-01）

    # ── `Ch4 §H.3` 追加行里的另两个字段（同一代码块逐字）──
    prev_version_id: int | None = None
    """上一版本（`Ch4 §H.3` 的 `"prev_version_id":7`；`01_产品目标与核心闭环/01_需求拆解.md §2.4`
    把"上一版本"列为结论可追溯四要素之一）。`None` = 首版（结构上不存在上一版本，与 `T-10` 同例）。"""
    changed_by: str = ""
    """`Ch4 §H.3` 的 `"changed_by":"research_skill"` —— 谁改的（供 `§H.2` "无新信息不产新版本"的复核）。"""

    # ── `Ch4 §G.4` 未盈利 / 盈利公司的**必填增量**（`N4.2-04` / `N4.2-05`；阶段② 必填）──
    #    ★ 设计把"按 `is_profitable` 分支要求非空"交给**校验器**（属阶段② 的
    #      `scripts/valuelayer/`，不在本批次）⇒ 本表只提供**字段载体**，字段本身可选，
    #      以免在 schema 层把"尚未研究"与"不适用"混为一谈。
    is_profitable: bool | None = None                              # None = 未判定（不猜）
    business_model_note: str = TBD                                 # 未盈利必填
    path_to_profitability: list[str] = Field(default_factory=list)  # 未盈利必填（里程碑）
    cash_runway: str = TBD                                         # 未盈利必填
    funding_need: str = TBD                                        # 未盈利必填
    unit_economics: str = TBD                                      # 未盈利必填
    margin_persistence: str = TBD                                  # 盈利必填
    fcf_persistence: str = TBD                                     # 盈利必填
    reinvestment_return: str = TBD                                 # 盈利必填
    share_dilution_impact: str = TBD                               # 盈利必填

    @model_validator(mode="after")
    def _check_driver_model_is_projection_of_driver_refs(self) -> "Baseline":
        """`driver_model` 只能是 `driver_refs` 的**投影** ⇒ 其 `driver_id` 必须全部被引用。

        ★ 这条断言就是"不留双真源"的**机器绑定**：任何"凭空写一条 driver_model 而
         没有对应 driver 对象"的行都会被拒 —— 那种行正是第二个真源。
        ★ 反向**不**强制（`driver_refs` 可以多于 `driver_model` 的条数）：估值只需要
         一部分驱动做经营假设；但**多出来的引用不能凭空生成投影**（由 `project_driver_model` 决定取哪些）。
          故这里只查"投影 ⊆ 引用"。
        ★ 旧行兼容：既有行的 `driver_model` 为 `[]` ⇒ 恒通过（真仓库实测 `[]`）。
        """
        orphan = sorted({d.driver_id for d in self.driver_model} - set(self.driver_refs))
        if orphan:
            raise ValueError(
                f"driver_model 引用了不在 driver_refs 中的 driver_id: {orphan} —— "
                "driver_model 只能是 driver_refs + drivers.jsonl 的投影（不得成为第二个真源）"
            )
        return self


# ─────────────────────────── ⑥ 价格与预期 ───────────────────────────

class PriceSnapshot(TimeMixin):
    """行情快照（`Ch9 §N9.1-19`）。**纯追加**；必须绑定公司行动口径版本。"""

    snapshot_id: str
    security_id: str
    price: Decimal
    currency: str
    trading_session: str
    delayed: bool = False                     # 延迟行情须显示"延迟"与行情时间，不得标实时
    adjustment_caliber_version: str = TBD     # 复权/公司行动口径版本（配合 N9.3-08）
    source_id: str = ""
    is_nav: bool = False                      # 净值仅作 diagnostic（`Ch3 §D.2`）

    @field_serializer("price")
    def _ser_price(self, v: Decimal) -> str:
        return str(v)


class ExpectationSample(TimeMixin):
    """外部预测**样本**（`Ch9 §N9.1-20`）。

    **命名不得升级为"一致预期 / 共识价"**；**三份判断不许合并**（`Ch9 §N9.1-20`；
    `Ch2 §B.2 P-07` 禁 `consensus` / `market_view` / `average_forecast`）。
    """

    sample_id: str                            # = (security_id, provider, metric, period)
    security_id: str
    provider_id: str
    provider_kind: Literal["company_guidance", "broker", "social"] = "broker"
    metric: str
    period: str
    sample_value: str = TBD
    sample_size: int | None = None
    # ★ `source_id` **必填且非空**（`Ch5 §C2`：「`expectations` 每条必须有 `source_id`
    #   + `provider` 身份（非空），**否则校验失败**」）。
    #   初版写成 `source_id: str = ""` —— 于是"无源的外部预期"能入库，
    #   而 P-07 禁的正是"无 source_id 的聚合预测"。由
    #   `tests/conflict/test_schema_no_aggregate.py` 抓出。
    source_id: str = Field(min_length=1)


# ─────────── ⑥b 价格隐含要求（`Ch5 §B.2`；本批次新增 1 张表 `facts/implied_requirements.jsonl`） ───────────
#
# ★ 为什么必须是**多组解**（`Ch5 §B.1` 逐字）：价格 `P = f(g, m, r, k, T)` 是**欠定方程** ——
#   一个 P 对应**无穷多组**解。"故**必须展示多组解**，否则会把某一解误当'市场的唯一真相'"。
# ★ 反解**不得**回灌 baseline（`Ch5 §B.5` 裁决 C45-1："反解 = 诊断（不产建议），正估 = 定价"；
#   禁令由 `FORBIDDEN_BASELINE_SOURCES = {"implied_solution", "implied_requirements"}` 承载，
#   属阶段② 的 `scripts/pricelayer/order_guard.py`，**不在本批次**）。
# ★ 时间语义：**不叠加 `TimeMixin`** —— `§B.2` 已逐字给出系统时间字段 `computed_at`；
#   再叠一套 `analyzed_at`/`first_seen_at` 会为同一概念造第二个字段名（`Ch2 §C.2 R-15 ③`）。


class ImpliedAssumptions(_Base):
    """反解时**固定不动**的四类假设（`Ch5 §B.2` 的 `assumptions{growth, margin, reinvestment, risk, duration}`）。

    键名逐字取 §B.2 的 JSON；每类的内部结构 §B.2 写作 `{...}`（由 §B.4 的"取值方式"决定：
    点或区间、收入 CAGR / 终值增长、capex/收入 与 ROIIC、WACC、高增长年数）⇒ 用开放 dict，
    **不伪造**一个设计未给的内层结构。
    被解出的那一类（`solved_variable`）在同一份 JSON 里也保留其区间解（`range`）。
    """

    growth: dict[str, Any] = Field(default_factory=dict)
    margin: dict[str, Any] = Field(default_factory=dict)
    reinvestment: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    duration: dict[str, Any] = Field(default_factory=dict)


class ImpliedRange(_Base):
    """区间表达（`Ch5 §B.2`：`"range":{"low":"...","high":"..."}`；`§D.6`："区间用 `range{low, high}`"）。

    ★ 用 `Decimal` + 字符串序列化（`Ch9 §3.4.5`）：区间值要参与算术与比较，
      用字符串会在下游被迫二次解析；`Ch9 §3.4.5` 明令"数值以字符串存储，避免浮点误差" ⇒
      存的是 `Decimal`，落盘时序列化为字符串。
    ★ 允许 `None`：反解在**参数不可行**时（`feasible=false`）可以只给出一侧边界；
      用 `None` 表达"该侧无解"，**不得**用 0 冒充。
    """

    low: Decimal | None = None
    high: Decimal | None = None

    @field_serializer("low", "high")
    def _ser_bounds(self, v: Decimal | None) -> str | None:
        return None if v is None else str(v)


class ImpliedRequirement(_Base):
    """价格隐含要求（`Ch5 §B.2`，新表 `facts/implied_requirements.jsonl`）。

    §B.2 的输出结构逐字（本类的字段与其一一对应）：

    ```json
    {"implied_id":"IMP-001","solution_set_id":"SET-nvda-2026-09-15",
     "security_id":"sec_nvda","price_snapshot_id":"SNP-...","current_price":"...",
     "assumptions":{"growth":{...},"margin":{...},"reinvestment":{...},
                    "risk":{...},"duration":{...}},
     "solved_variable":"reinvestment",                    // 固定其余 4 类，解第 5 类
     "range":{"low":"...","high":"..."},                  // 区间表达
     "alternative_explanations":["...","..."],            // 替代解释
     "feasible":true,"method_version":"v1","computed_at":"..."}
    ```

    ★ `solution_set_id` 聚合一组解（§B.2："展示层呈现'使当前价格成立的**解集**'
      （多组 + 每组区间 + 替代解释）"）⇒ 同一 `solution_set_id` 下会有多行。
    ★ `price_snapshot_id` 必填：反解是**针对某个行情快照**做的；缺了它，"使当前价格成立"
      这句话没有可核对的时点（`Ch9 §N9.1-19` 的行情必须绑定公司行动口径版本）。
    ★ **本类不叠加 `TimeMixin`**（见本节顶部第 3 条注）：`computed_at` 已是设计给的系统时间。
    """

    implied_id: str
    solution_set_id: str
    security_id: str
    price_snapshot_id: str
    current_price: Decimal
    assumptions: ImpliedAssumptions
    solved_variable: SolvedVariable
    range: ImpliedRange
    alternative_explanations: list[str]
    feasible: bool
    method_version: str
    computed_at: datetime

    @field_serializer("current_price")
    def _ser_current_price(self, v: Decimal) -> str:
        return str(v)


# ─────────────────────────── ⑦ 基准与建议 ───────────────────────────

class BenchmarkReturnBasis(_Base):
    """收益口径（`Ch9 §N9.1-23` / `Ch3 §C.3`）。

    **同起止时间 + 美元 + 含分红再投资的市场价格总回报**；净值仅诊断；费用不重复扣。
    """

    same_start_end: bool = True
    currency: str = "USD"
    dividends_reinvested: bool = True
    price_kind: Literal["market_price_total_return", "nav"] = "market_price_total_return"
    fee_deducted_again: bool = False          # 必须 False（`Ch3 §D.2`）
    version: str = "v1"


class Benchmark(TimeMixin):
    """基准（`Ch9 §N9.1-22` / `Ch3 §C.3`）。**对象化，非硬编码代码**。"""

    benchmark_id: str
    benchmark_role: BenchmarkRole = BenchmarkRole.primary
    coverage_profile: dict[str, Any] = Field(default_factory=dict)
    includes_non_listed_assets: bool = False
    non_listed_assets: dict[str, Any] = Field(default_factory=dict)
    sensitivity: dict[str, Any] = Field(default_factory=dict)
    freeze_status: BenchmarkFreezeStatus = BenchmarkFreezeStatus.unfrozen   # 域 = 基准对象
    return_basis: BenchmarkReturnBasis = Field(default_factory=BenchmarkReturnBasis)
    return_basis_version: str = "v1"
    benchmark_semantics: str = ""      # "选股相对继续持有该 AI 投资选项是否创造价值"，≠ 行业平均
    return_source: Literal["fund_market_price", "proxy_index"] = "fund_market_price"
    proxy_index_used: bool = False     # 必须 False（禁用替代指数，N3.4-05）
    change_records: list[dict[str, Any]] = Field(default_factory=list)   # 变更追加版本 + effective_date + reason + version + 人工审批


class OpportunityBasis(_Base):
    """机会类型依据（`Ch2 §C.1` / `Ch9 §3.3.4`）。每类一条依据。"""

    type: OpportunityType
    value_ref: str          # → Ch4 `value_state_refs`
    price_ref: str          # → Ch5 `price_gap_state`


class Recommendation(TimeMixin):
    """建议（`Ch9 §3.3.4` R-07 / `Ch2 §B.2` / `Ch7 §E`）。

    ⚠️ **本类的字段名集合即 Checker-2 的作用域边界**（`Ch2 §B.3`）：
    `assert_absent` **只对本类字段名生效**，**不得**扩展成全仓 token 遍历。
    合法同名词不得误报：`position_listed` / `business_positions`（"产业链位置"语义）。
    """

    recommendation_id: str
    security_id: str
    company_id: str
    action: RecommendationAction
    horizon: str                                  # ∈ [1Q, 1Y]（边界含），见 `assert_horizon`
    start_date: date                              # 必填（`Ch2 §D.2`）
    review_date: date | None = None               # 复查节点
    status: RecommendationStatus = RecommendationStatus.active

    # ── 规则版本与证据版本（T12：证据撤回后可查出当时哪些建议引用了该版本）──
    rule_version: str
    evidence_version_ids: list[str] = Field(default_factory=list)

    # ── `Ch2 §C.1` 机会类型（**不进买入门**，仅标注）──
    opportunity_types: list[OpportunityType] = Field(default_factory=list)
    opportunity_basis: list[OpportunityBasis] = Field(default_factory=list)

    # ── `Ch2 §D.1` 提前判断三要素（与非提前判断共用字段名，逐字一致）──
    assumptions: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    verification_conditions: list[str] = Field(default_factory=list)

    # ── `Ch1 §C.1` falsifiers 族 ──
    falsifiers: list[str] = Field(default_factory=list)
    unmet_conditions: list[str] = Field(default_factory=list)
    falsifier_written_at: int | None = None
    expiry_review: date | None = None

    # ── 反 KPI：新建议必须有变化理由（`Ch1 §F` G1-02）──
    change_reason: str = ""

    version: int = 1
    version_kind: VersionKind | None = None
    supersedes: str | None = None

    early_judgment: bool = False
    """是否为"提前判断"（结论依赖未兑现假设）。

    由 `Ch4 §H.1` + `Ch5` explainable forecast 判定；**非提前判断（已兑现）建议不强制三要素**
    （`Ch2 §D.1` 边界）。
    """

    @model_validator(mode="after")
    def _assert_early_judgment_trio_when_early(self) -> "Recommendation":
        """提前判断三要素：**任一为空即不得出建议**（`Ch2 §D.1` A-06 / 规则 6）。"""
        if self.early_judgment:
            missing = [
                name
                for name, val in (
                    ("assumptions", self.assumptions),
                    ("evidence_gaps", self.evidence_gaps),
                    ("verification_conditions", self.verification_conditions),
                )
                if not val
            ]
            if missing:
                raise ValueError(f"提前判断缺必填项: {missing}（记 gap，不出建议）")
        return self


# ─────────────────────────── ⑧ 任务与复盘 ───────────────────────────

class EvalResult(_Base):
    """三层复盘评估结果（`Ch9 §3.3.5` R-29）。

    ⚠️ 均为**标记字段**：**不进决策函数**、不参与任何门槛
    （对齐 `Ch2 §B.3` Checker-1 的 `is_decision_scope` 排除项）。
    """

    eval_layer: EvalLayer
    error_axis: list[ErrorAxis] = Field(default_factory=list)   # **允许数组**，一条错误可跨方向
    error_axis_note: str = ""


class CheckRecord(_Base):
    """核查记录（`Ch1 §C.2`）。**不是**第九章 8 大对象之一，属控制面子记录。

    每日运行**必写**（无论有无变化），使"无信号"成为正常态。
    """

    check_id: str
    run_date: date
    scope: CheckScope
    changed: bool
    judgment_change: dict[str, bool] = Field(default_factory=dict)
    signals_emitted: int
    degraded: bool = False


class Task(TimeMixin):
    """任务与复盘（`Ch9 §2.1.6`）——**元数据层 / 控制面**，唯一引用全部其它对象的对象。"""

    task_id: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.queued
    idempotency_key: str                       # 幂等键：防重复建单
    input_refs: list[str] = Field(default_factory=list)    # 输入引用
    output_refs: list[str] = Field(default_factory=list)   # 输出引用（可追溯回写）
    parent_context: dict[str, Any] = Field(default_factory=dict)

    # ── 运行成本（N9.1-27）──
    cost: dict[str, Any] = Field(default_factory=dict)     # {tokens, searches, storage}
    # ── 失败原因（N9.1-28）── 结构化分类，与运维错误分类对齐（N9.2-13）
    failure_stage: str = TBD
    failure_reason: str = TBD
    last_valid_result_ref: str | None = None    # 降级**保留上次有效结果**（N9.2-13 / Ch8 §E）
    # ── 复查节点（N9.1-29）──
    recheck_due: date | None = None
    # ── 评估结果（N9.1-30 / §3.3.5）──
    eval_result: EvalResult | None = None
    eval_result_history: list[EvalResult] = Field(default_factory=list)   # append-only
    # ── 核查记录（`Ch1 §C.2`）── 控制面**子记录**，落 `facts/tasks.jsonl`
    #      （不新增 JSONL：`facts/` 的表集合**不得增删改名**）
    check_record: "CheckRecord | None" = None
    # ── 模型规则修改记录（N9.1-30）──
    rule_change_records: list[dict[str, Any]] = Field(default_factory=list)
    change_log: list[dict[str, Any]] = Field(default_factory=list)


class DependencyEdge(_Base):
    """依赖图边（`Ch9 §3.4.3`），支撑 T12 传播。`{from, to, kind}`。"""

    edge_id: str
    from_ref: str
    to_ref: str
    kind: str


# ─────────────────────────── JSONL → 模型映射（唯一真源） ───────────────────────────
# `Ch9 §3.3.3` 表（**经需求方 2026-09-16 裁定由 18 扩至 22**，见文件头）逐字对应；
# **不得增删改名**。stem 清单的唯一真源是 `schema/stems.py::JSONL_STEMS`（见其 docstring）。

JSONL_MODELS: dict[str, type[BaseModel]] = {
    # 公司与证券
    "industry_nodes": IndustryNode,
    "companies": Company,
    "securities": Security,
    "business_positions": BusinessPosition,
    # 产品与关系
    "products": Product,
    "relations": Relation,
    "relation_flows": RelationFlow,
    # 来源与主张
    "sources": Source,
    "claims": Claim,
    "claim_propagation": ClaimPropagation,
    # 事件与影响
    "events": Event,
    "impacts": Impact,
    # 研究基线（业务单元 + 增长驱动 + 版本化结论）
    "businesses": Business,
    "drivers": Driver,
    "baselines": Baseline,
    # 价格与预期
    "prices": PriceSnapshot,
    "expectations": ExpectationSample,
    "implied_requirements": ImpliedRequirement,
    # 基准与建议
    "benchmarks": Benchmark,
    "recommendations": Recommendation,
    # 任务与复盘
    "tasks": Task,
    # 依赖图边
    "dependency_edges": DependencyEdge,
}

# ★★ 机器绑定：映射的**键集合**必须与 stem 注册表**逐一相等**。
#    在**导入时**断言 ⇒ 漂移即 `AssertionError`（响亮失败），不会退化成
#    "有人加了第 23 张表却忘了同步夹具清空清单"（那会让测试重新依赖"真仓库恰好有什么"）。
assert set(JSONL_MODELS) == set(JSONL_STEMS), (
    "JSONL_MODELS 与 stem 注册表不一致（唯一真源 = schema/stems.py::JSONL_STEMS）："
    f"仅在 JSONL_MODELS: {sorted(set(JSONL_MODELS) - set(JSONL_STEMS))}；"
    f"仅在 JSONL_STEMS: {sorted(set(JSONL_STEMS) - set(JSONL_MODELS))}"
)
assert len(JSONL_STEMS) == 22, (
    f"facts/ 必须恰好 22 个 JSONL（需求方 2026-09-16 裁定：18 → 22，见 `T-13` 备选②），"
    f"实为 {len(JSONL_STEMS)}"
)


def model_for(jsonl_stem: str) -> type[BaseModel]:
    """取某 JSONL 对应的对象模型；未知 stem **响亮失败**（不返回兜底值）。"""
    if jsonl_stem not in JSONL_MODELS:
        raise KeyError(
            f"未知 JSONL: {jsonl_stem!r}；合法值见 Ch9 §3.3.3：" f"{sorted(JSONL_MODELS)}"
        )
    return JSONL_MODELS[jsonl_stem]
