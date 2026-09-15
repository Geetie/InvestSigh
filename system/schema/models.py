"""facts/ 18 个追加式 JSONL 的 8 类对象模型（唯一真源定义）。

权威出处（逐字对齐，不得偏离）：
- `Ch9 §3.3.3`   目录布局 / 18 JSONL → 8 类对象 / 版本表达方式
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
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator


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
    """驱动的兑现阶段（`Ch4 §D`）。与 `relation_progress_stage` **不得互用**（`Ch2 §C.2 R-15 ②`）。"""

    tbd = TBD
    not_started = "not_started"
    ramping = "ramping"
    ramped = "ramped"
    declining = "declining"


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
    supersedes: str | None = None                     # 版本链：新版本指向被取代的旧版本
    version_kind: VersionKind | None = None           # 三类版本事件语义（若为本行是修订版）
    locator: str = ""                                 # 定位（页码/段落/表格/视频时间点）
    status: str = "active"
    full_text_read: bool = False                      # 由 `scripts/validators/locator_check.py` 程序校验
    impact_capability: dict[str, Any] = Field(default_factory=dict)


class ClaimPropagation(TimeMixin):
    """传播记录（`Ch9 §N9.1-13` / `§3.4.7`）。

    十篇转述同一匿名订单 = **1 个 event + N 条 propagation**（T01）；
    转述者**不计独立证据**（`Ch6 §N6.2-11`）。
    """

    propagation_id: str
    root_claim_id: str                # 根来源主张
    propagated_claim_id: str          # 转述主张
    publisher_entity: str = ""
    carrier_platform: str = ""
    independent_evidence: bool = False  # 转述默认 False，不得提升为独立佐证


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


# ─────────────────────────── ⑤ 研究基线 ───────────────────────────

class ValueStateRefs(_Base):
    """价值状态（`Ch9 §N9.1-18`）。三组状态**可同时并存且不同向**（`Ch2 §C.2` N2.2-04）。"""

    growth_momentum_state: DirectionState = DirectionState.tbd
    certainty_state: DirectionState = DirectionState.tbd
    moat_level: MoatLevel = MoatLevel.tbd      # 护城河**水平**（新增，A-02/N2.2-02）
    moat_state: DirectionState = DirectionState.tbd   # 护城河**趋势**（既有）


class DriverModel(_Base):
    """驱动模型（`Ch9 §N9.1-17` / `Ch4 §D`）。驱动 → 科目 → 每股指标三层映射。"""

    driver_id: str
    driver_name: str
    realization_stage: DriverRealizationStage = DriverRealizationStage.tbd
    is_primary: bool = False
    linked_accounts: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class Baseline(TimeMixin):
    """研究基线（`Ch9 §N9.1-17` / `§N9.1-18`）。主键 = (`company_id`, `version`)，**版本化**。"""

    baseline_id: str
    company_id: str
    version: int
    business_mechanism: str                                        # 经营机制（"谁付费 + 转换链路各段"）
    historical_numeric_claims: list[str] = Field(default_factory=list)   # 历史基线数据（引用 NumericClaim）
    driver_model: list[DriverModel] = Field(default_factory=list)
    value_state_refs: ValueStateRefs = Field(default_factory=ValueStateRefs)
    conclusion_version: int = 1
    evidence_claim_ids: list[str] = Field(default_factory=list)
    falsifiers: list[str] = Field(default_factory=list)            # 与结论**同版本写入**（`Ch1 §C.1` G1-01）
    unmet_conditions: list[str] = Field(default_factory=list)
    verification_conditions: list[str] = Field(default_factory=list)
    falsifier_written_seq: int | None = None
    expiry_review: date | None = None


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
    source_id: str = ""


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
    #      （不新增第 19 个 JSONL：`Ch9 §3.3.3` 的 18 个**不得增删改名**）
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


# ─────────────────────────── 18 JSONL → 模型映射（唯一真源） ───────────────────────────
# `Ch9 §3.3.3` 表逐字对应；**不得增删改名**。

JSONL_MODELS: dict[str, type[BaseModel]] = {
    # 公司与证券
    "industry_nodes": IndustryNode,
    "companies": Company,
    "securities": Security,
    "business_positions": BusinessPosition,
    # 产品与关系
    "products": Product,
    "relations": Relation,
    # 来源与主张
    "sources": Source,
    "claims": Claim,
    "claim_propagation": ClaimPropagation,
    # 事件与影响
    "events": Event,
    "impacts": Impact,
    # 研究基线
    "baselines": Baseline,
    # 价格与预期
    "prices": PriceSnapshot,
    "expectations": ExpectationSample,
    # 基准与建议
    "benchmarks": Benchmark,
    "recommendations": Recommendation,
    # 任务与复盘
    "tasks": Task,
    # 依赖图边
    "dependency_edges": DependencyEdge,
}

assert len(JSONL_MODELS) == 18, f"facts/ 必须恰好 18 个 JSONL（Ch9 §3.3.3），实为 {len(JSONL_MODELS)}"


def model_for(jsonl_stem: str) -> type[BaseModel]:
    """取某 JSONL 对应的对象模型；未知 stem **响亮失败**（不返回兜底值）。"""
    if jsonl_stem not in JSONL_MODELS:
        raise KeyError(
            f"未知 JSONL: {jsonl_stem!r}；合法值见 Ch9 §3.3.3：" f"{sorted(JSONL_MODELS)}"
        )
    return JSONL_MODELS[jsonl_stem]
