#!/usr/bin/env python3
"""`daily_explain.py` —— **每日价格解释**（`Ch5 §F.1~§F.5`）。

## 逐字依据

1. **先做行情口径校验**（`Ch5 §F.1` 逐字伪码）：

   ```python
   def validate_quote(snapshot):    # T11 / N5.5-01
       check(snapshot.quote_time, snapshot.trading_session,
             snapshot.currency, snapshot.adjusted_flag, snapshot.corporate_actions_ref)
   ```

   「校验未通过的行情**不用于**解释与收益计算（承 `N9.3-08` 公司行动口径）」。

2. **三分类**（`Ch5 §F.2` 逐字三档）：

   | 档 | 判定标准 | 字段 |
   |---|---|---|
   | 已确认解释 | 完整因果链 + 证据 | `explanation.confirmed[]` |
   | 合理推断 | 部分证据、因果未完全确认 | `explanation.inferred[]` |
   | 无法解释 | 无依据 | `explanation.unexplained` |

   `00_待拍板项清单` **B12（已确认）**："三档 = **已确认**（有事件且传导路径可达）/
   **合理推断**（有部分证据）/ **无法解释**"。

3. **归因必须有因果链而非时间接近**（`Ch5 §F.3` 逐字伪码）：

   ```python
   def attribute(move, factors):
       for f in candidate_factors(move):        # 基准/同行/公司事件/环境
           if f.event_id or f.claim_id:         # 必须引用事件/主张
               if reachable_via_transmission(f, move.security_id):   # 且经传导路径可达
                   return Confirmed(f)
       return Unexplained()                     # 仅时间接近 → 无法解释/待核验
   ```

   单测逐字要求：「构造一个'时间接近但因果链不可达'的消息 → 断言归为 `Unexplained`」（`N5.5-05`）。
   ★ **可达性复用** `scripts.graph.closure.forward_closure`（`Ch5 §J7`："因果链可达性深度 ——
   与 `max_depth` 一致 —— **复用**第七章 `forward_closure`"）⇒ 本模块**不重造**图遍历（`G-06`）。

4. **硬隔离**（`Ch5 §F.4`，承 `C45-5`）：价格涨跌**只触发复查**，**不写** `baselines.moat` / 基本面结论。
   单测逐字要求：「调用 `write_moat(...)` 传入 price 派生值 → 断言 `MoatPriceContamination`
   （与第四章 `§F.3` 共用断言）」。★ "共用断言"的载体 = schema 的写路径白名单
   `schema.models.MoatWriter`（`Ch4 §F.3` 断言 A3；`price_ingest` **不在**白名单内）——
   本模块**消费**该枚举，不另立第二套白名单。

5. **异常下跌触发强制复查 + 复查未完成显示**（`Ch5 §F.5`）：
   阈值取 `00_待拍板项清单` **B2（已确认）**："单日 ≤ −7% 或 3 日累计 ≤ −12% →
   **只触发复查，不是止损线**"；`recommendation.status=rechecking` + `original_judgment_time`。

## CLI

```
python system/scripts/pricelayer/daily_explain.py [code_root]
```

退出码 `0` 放行 / `1` 命中违例 / `2` 输入异常（复用 `_common.run_checker`）。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if __package__:
    from . import MoatPriceContamination, PriceLayerError, QuoteCaliberViolation
else:  # 直接以脚本方式运行（CLI 出口；仓库既有守卫都是这种调用方式）
    from scripts.pricelayer import MoatPriceContamination, PriceLayerError, QuoteCaliberViolation

REVIEW_YAML = "rules/review.yaml"
RULE_KEY_FORCED_RECHECK = "forced_recheck"
RULE_KEY_SINGLE_DAY_DROP_PCT = "single_day_drop_pct"
RULE_KEY_THREE_DAY_CUMULATIVE_PCT = "three_day_cumulative_pct"
RULE_KEY_ON_HIT = "on_hit"
RULE_KEY_KEEP_ORIGINAL_JUDGMENT_TIME = "keep_original_judgment_time"

ABNORMAL_DROP_1D = Decimal("-0.07")
ABNORMAL_DROP_3D = Decimal("-0.12")
"""异常下跌阈值的**设计逐字回落值**（`00_待拍板项清单` **B2 已确认**）。

★ 真值取自 `rules/review.yaml::forced_recheck.single_day_drop_pct`（`-7`）与
  `three_day_cumulative_pct`（`-12`）—— **参数只住 `rules/`**（`Ch11 §D.2`）。
  本常量仅作规则文件/该键缺失时的回落；`check` 另做"代码默认值 == 文件真值"的绑定断言。
★ `Ch5 §F.5` 逐字："**不自动止损/抄底**"（`N5.5-06` / `T08`）—— 本阈值**只触发复查**。
"""

DESIGN_KEEP_ORIGINAL_JUDGMENT_TIME = True
"""`Ch5 §F.5` / `T08` 逐字："价格涨跌**只触发复查**，**保留原判断时间**" —— `True`。

★ 真值取自 `rules/review.yaml::forced_recheck.on_hit.keep_original_judgment_time`（现为 `true`）；
  本常量仅作规则文件/该键缺失时的**设计逐字回落**，并由 `_rule_binding_violations`
  核"代码回落值 == 文件真值"（否则"规则改了、回落没改"不会被发现）。
"""


@dataclass(frozen=True)
class RecheckTrigger:
    """`rules/review.yaml::forced_recheck` 的解析结果（**带来源标注**）。

    - `value_source`：`"rules"` = 取自规则文件；`"design_default"` = 文件/键缺失，取
      **设计逐字值**（B2 的 `-7%`/`-12%` + `Ch5 §F.5`/`T08` 的"保留原判断时间"）。
    - `notes`：**`value_source == "design_default"` 时必非空** —— 逐条写明缺的是什么
      （主理人裁定 ③-2：`design_default` 必须打 note，否则单独特调本函数就看不出"缺键"）。
    """

    single_day_drop: Decimal
    three_day_cumulative: Decimal
    keep_original_judgment_time: bool = True
    value_source: str = "design_default"
    notes: tuple[str, ...] = ()


def load_recheck_trigger(root: str | Path | None = None) -> RecheckTrigger:
    """读 `rules/review.yaml::forced_recheck` 的阈值（`Ch5 §F.5` / B2 / `T08`）—— **唯一读口**。

    ★ 比例口径归正：规则文件写的是**百分点**（`-7` / `-12`），本层内部用**小数**
      （`-0.07` / `-0.12`）。换算在**这一处**完成，避免两套口径并存。
    - 文件缺失 / **节**缺失 → 回落**设计逐字值**（B2 + `Ch5 §F.5`）并标 `value_source="design_default"`
      **且记一条写明缺失对象的 note**（主理人裁定 ③-1/③-2）。
    - `on_hit.keep_original_judgment_time` 缺键 → 同上（回落 + `NO_ON_HIT_KEY` note；`T08`）。
    - **阈值键缺失 / 非数值 → `DailyExplainError`（响亮失败，`不静默兜底`）**：
      ★ 实测（删 `single_day_drop_pct` ⇒ `阈值非数值（None / -12）—— 不静默兜底`）确认
      **不走回落**。旧实现在此还留了一段 `NO_FORCED_RECHECK_KEY` note，声称"该阈值取设计
      逐字回落值"，与真实行为**不符**且**永不可达**（上面先抛了）；第四轮已删
      （声明与实现脱节 / 死代码）。
    - 取值非负 → `DailyExplainError`（**响亮失败**；阈值必须是负的下跌阈值）。
    """
    from scripts._common import _cached_yaml  # `P-02`

    def _fallback(reason: str) -> RecheckTrigger:
        return RecheckTrigger(
            single_day_drop=ABNORMAL_DROP_1D,
            three_day_cumulative=ABNORMAL_DROP_3D,
            keep_original_judgment_time=DESIGN_KEEP_ORIGINAL_JUDGMENT_TIME,
            value_source="design_default",
            notes=(
                f"NO_FORCED_RECHECK: {reason} —— 回落设计逐字值 "
                f"单日 {ABNORMAL_DROP_1D} / 三日累计 {ABNORMAL_DROP_3D}（B2）、"
                f"保留原判断时间 {DESIGN_KEEP_ORIGINAL_JUDGMENT_TIME}（Ch5 §F.5 / T08）（非'已核'）",
            ),
        )

    if root is None:
        return _fallback("未给 code_root")
    path = Path(root) / REVIEW_YAML
    if not path.exists():
        return _fallback(f"{REVIEW_YAML} 不存在")
    doc = _cached_yaml(path) or {}
    node = doc.get(RULE_KEY_FORCED_RECHECK)
    if not isinstance(node, Mapping):
        return _fallback(f"{REVIEW_YAML} 缺/非法键 {RULE_KEY_FORCED_RECHECK!r}")
    try:
        one_day = Decimal(str(node.get(RULE_KEY_SINGLE_DAY_DROP_PCT))) / Decimal(100)
        three_day = Decimal(str(node.get(RULE_KEY_THREE_DAY_CUMULATIVE_PCT))) / Decimal(100)
    except (InvalidOperation, TypeError) as exc:
        raise DailyExplainError(
            f"{REVIEW_YAML}:: {RULE_KEY_FORCED_RECHECK} 阈值非数值"
            f"（{node.get(RULE_KEY_SINGLE_DAY_DROP_PCT)!r} / "
            f"{node.get(RULE_KEY_THREE_DAY_CUMULATIVE_PCT)!r}）—— 不静默兜底"
        ) from exc
    if one_day > 0 or three_day > 0:
        raise DailyExplainError(
            f"{REVIEW_YAML}:: {RULE_KEY_FORCED_RECHECK} 阈值必须为负（下跌口径）："
            f"{one_day} / {three_day}（B2：单日 ≤ −7% / 3 日累计 ≤ −12%）"
        )
    on_hit = node.get(RULE_KEY_ON_HIT)
    keep = DESIGN_KEEP_ORIGINAL_JUDGMENT_TIME
    notes: list[str] = []
    if isinstance(on_hit, Mapping) and RULE_KEY_KEEP_ORIGINAL_JUDGMENT_TIME in on_hit:
        keep = bool(on_hit.get(RULE_KEY_KEEP_ORIGINAL_JUDGMENT_TIME))
    else:
        notes.append(
            f"NO_ON_HIT_KEY: {REVIEW_YAML}:: {RULE_KEY_FORCED_RECHECK}.{RULE_KEY_ON_HIT}."
            f"{RULE_KEY_KEEP_ORIGINAL_JUDGMENT_TIME} 缺失 —— 取设计逐字回落值 "
            f"{DESIGN_KEEP_ORIGINAL_JUDGMENT_TIME}（Ch5 §F.5 / T08：涨跌只触发复查，保留原判断时间）"
            "（非'已核'）"
        )
    return RecheckTrigger(
        single_day_drop=one_day,
        three_day_cumulative=three_day,
        keep_original_judgment_time=keep,
        value_source="rules",
        notes=tuple(notes),
    )

FACTOR_KINDS: tuple[str, ...] = ("benchmark", "peer", "company_event", "environment")
"""`Ch5 §F.3` 逐字的四类候选因素（基准/同行/公司事件/环境）；`N5.5-02` 要求覆盖四类。"""

TBD = "tbd"
"""设计约定的"待定"token（与 `schema.models.TBD` 同值；此处不导入 schema 以保持守卫轻量）。"""


class DailyExplainError(PriceLayerError):
    """每日解释层的**输入结构**错误。"""


# ───────────────────────── §F.1 行情口径校验 ─────────────────────────


@dataclass(frozen=True)
class QuoteCaliber:
    """行情**口径五要素**（`Ch5 §F.1` 逐字五个字段名）。

    ★ **命名登记（待裁定）**：`Ch5 §F.1` 的字段名是 `quote_time` / `adjusted_flag` /
      `corporate_actions_ref`，而 `schema.models.PriceSnapshot` 上的名字是
      `published_at`|`occurred_at` / `adjustment_caliber_version`（其后两者**合并**为一个字段）。
      映射由 `quote_caliber_from_snapshot()` 承载（**唯一**映射点），设计两处命名差异已登记。
    """

    quote_time: datetime | None
    trading_session: str
    currency: str
    adjusted_flag: bool | None
    corporate_actions_ref: str
    delayed: bool = False


def quote_caliber_from_snapshot(snapshot: Any) -> QuoteCaliber:
    """把 `PriceSnapshot`（schema 真源）投影成 `Ch5 §F.1` 的五要素。

    - `quote_time` ← `published_at` ?? `occurred_at`（**两者都缺 → `None`** ⇒ 校验拒绝）；
    - `adjusted_flag` ← `adjustment_caliber_version` 是否已给出（非空且非 `tbd`）；
    - `corporate_actions_ref` ← 同一个 `adjustment_caliber_version`（`N9.3-08` 公司行动口径）。
    """
    quote_time = getattr(snapshot, "published_at", None) or getattr(snapshot, "occurred_at", None)
    caliber_version = str(getattr(snapshot, "adjustment_caliber_version", "") or "")
    adjusted = bool(caliber_version) and caliber_version != TBD
    return QuoteCaliber(
        quote_time=quote_time,
        trading_session=str(getattr(snapshot, "trading_session", "") or ""),
        currency=str(getattr(snapshot, "currency", "") or ""),
        adjusted_flag=adjusted,
        corporate_actions_ref=caliber_version if adjusted else "",
        delayed=bool(getattr(snapshot, "delayed", False)),
    )


def validate_quote(caliber: QuoteCaliber) -> None:
    """行情口径校验（`Ch5 §F.1` / `N5.5-01`）：五项任一不成立 → `QuoteCaliberViolation`。

    未通过的行情**不用于**解释与收益计算（`Ch5 §F.1` 逐字）。
    """
    missing: list[str] = []
    if caliber.quote_time is None:
        missing.append("quote_time")
    if not caliber.trading_session or caliber.trading_session == TBD:
        missing.append("trading_session")
    if not caliber.currency or caliber.currency == TBD:
        missing.append("currency")
    if caliber.adjusted_flag is not True:
        missing.append("adjusted_flag")
    if not caliber.corporate_actions_ref or caliber.corporate_actions_ref == TBD:
        missing.append("corporate_actions_ref")
    if missing:
        raise QuoteCaliberViolation(
            f"行情口径校验失败：缺 {missing} —— 该行情不得用于解释与收益计算"
            "（Ch5 §F.1 / T11 / N5.5-01）"
        )


# ───────────────────────── §F.3 因果链归因 ─────────────────────────


@dataclass(frozen=True)
class PriceMove:
    """一次价格变动（`Ch5 §F.3` 的 `move`）。"""

    security_id: str
    move_date: datetime
    change_pct: Decimal | None = None


@dataclass(frozen=True)
class Factor:
    """一个候选解释因素（`Ch5 §F.3` 的 `f`；四类之一）。

    `event_id` / `claim_id` 是"引用事件或主张"的**外键**（`§F.3` 逐字 `if f.event_id or f.claim_id`）；
    两者皆空 ⇒ 该因素**只有时间接近**，不足以归因。
    """

    kind: str
    label: str
    event_id: str = ""
    claim_id: str = ""
    observed_at: datetime | None = None


@dataclass
class Explanation:
    """三分类解释（`Ch5 §F.2` 的 `explanation.{confirmed,inferred,unexplained}`）。"""

    confirmed: list[Factor] = field(default_factory=list)
    inferred: list[Factor] = field(default_factory=list)
    unexplained: bool = False

    @property
    def has_confirmed(self) -> bool:
        return bool(self.confirmed)


def candidate_factors(
    move: PriceMove,
    factors: Sequence[Factor],
) -> list[Factor]:
    """筛出与 `move` **同期同标的**的候选因素（`Ch5 §F.3` 的 `candidate_factors(move)`）。

    - 只保留 `kind ∈ FACTOR_KINDS` 的因素（四类穷尽；未知类 → 丢弃并不可归因）；
    - 未给出 `observed_at` 的因素**仍可**入选（归因由"因果链可达"决定，不由时间决定）——
      这正是 `§F.3`"归因必须有因果链而**非时间接近**"的落点。
    """
    out: list[Factor] = []
    for factor in factors:
        if factor.kind not in FACTOR_KINDS:
            continue
        out.append(factor)
    return out


def reachable_via_transmission(
    factor_ref: str,
    security_id: str,
    *,
    root: str | Path | None = None,
    edges: Sequence[Any] | None = None,
    max_depth: int | None = None,
) -> bool:
    """`factor_ref` 是否**经传导路径可达** `security_id`（`Ch5 §F.3` 逐字判据）。

    ★ **复用** `scripts.graph.closure.forward_closure`（`Ch5 §J7` 逐字："复用第七章
      `forward_closure`"）—— 本模块不重造图遍历（`G-06`）；`max_depth` 缺省取该模块的
      `DEFAULT_MAX_DEPTH`（与第七章一致）。
    """
    from scripts.graph.closure import DEFAULT_MAX_DEPTH, forward_closure

    if not factor_ref or not security_id:
        return False
    result = forward_closure(
        Path(root) if root is not None else Path("."),
        factor_ref,
        max_depth=DEFAULT_MAX_DEPTH if max_depth is None else max_depth,
        edges=list(edges) if edges is not None else None,
    )
    return security_id in set(result.reached)


def attribute(
    move: PriceMove,
    factors: Sequence[Factor],
    *,
    root: str | Path | None = None,
    edges: Sequence[Any] | None = None,
    max_depth: int | None = None,
) -> Explanation:
    """把价格变动归到三档（`Ch5 §F.3` 逐字算法 + `§F.2` 三分类）。

    - **已确认**：因素引用了 `event_id` 或 `claim_id` **且**经传导路径可达该证券；
    - **合理推断**：因素有引用但**因果链不可达**（"部分证据、因果未完全确认"）；
    - **无法解释**：无任何"已确认 / 合理推断"的依据 ⇒ `unexplained=True`（`§F.3` 的
      `return Unexplained()`；单测逐字："仅时间接近 → 无法解释"）。
    """
    explanation = Explanation()
    for factor in candidate_factors(move, factors):
        reference = factor.event_id or factor.claim_id
        if not reference:
            continue
        if reachable_via_transmission(
            reference, move.security_id, root=root, edges=edges, max_depth=max_depth
        ):
            explanation.confirmed.append(factor)
        else:
            explanation.inferred.append(factor)
    if not explanation.confirmed and not explanation.inferred:
        explanation.unexplained = True
    return explanation


# ───────────────────────── §F.4 硬隔离（价格不写护城河） ─────────────────────────


def assert_no_price_contamination(writer: str) -> None:
    """价格派生值**不得**写入护城河/基本面（`Ch5 §F.4`，承 `C45-5`）。

    ★ "**共用断言**"的载体是 schema 的写路径白名单 `schema.models.MoatWriter`
      （`Ch4 §F.3` 断言 A3：`moat.writer ∈ {research_skill, human}`，**不含** `price_ingest`）。
      本函数**消费**该枚举做 allowlist 判定（未列入即拒，`R-06 ⑤`），
      **不新立第二套白名单**（`G-06`）。
    """
    from schema.models import MoatWriter

    allowed = {member.value for member in MoatWriter}
    if writer not in allowed:
        raise MoatPriceContamination(
            f"写路径 {writer!r} 不在护城河写白名单 {sorted(allowed)} 内 —— "
            "价格涨跌只触发复查，不写 baselines.moat / 基本面结论（Ch5 §F.4 / C45-5 / Ch4 §F.3 A3）"
        )


# ───────────────────────── §F.5 异常下跌 → 强制复查 ─────────────────────────


@dataclass(frozen=True)
class ReviewTicket:
    """复查工单（`Ch5 §F.5`：`recommendation.status=rechecking` + `original_judgment_time`）。

    ★ `status` 取 `Ch5 §F.5` 逐字值 `"rechecking"`；schema 的 `RecommendationStatus`
      目前**没有**该取值 ⇒ 本对象独立承载，schema 缺口已登记待裁定（不改共享 schema）。
    """

    recommendation_id: str
    status: str
    original_judgment_time: datetime
    trigger: str


def is_abnormal_decline(
    daily_change_pct: Decimal,
    *,
    three_day_change_pct: Decimal | None = None,
    trigger: RecheckTrigger | None = None,
    drop_1d: Decimal | None = None,
    drop_3d: Decimal | None = None,
) -> bool:
    """异常下跌判定（`Ch5 §F.5` + B2）：单日 ≤ 阈值 **或** 3 日累计 ≤ 阈值。

    ★ 阈值**读** `rules/review.yaml::forced_recheck`（`trigger` = `load_recheck_trigger(root)`）
      —— **不硬编码**（`Ch11 §D.2`）。`drop_1d` / `drop_3d` 只是**显式覆盖**（测试用）。
    ★ 命中**只触发复查**：`Ch5 §F.5` 逐字"**不自动止损/抄底**"（`N5.5-06`）。
    """
    trigger = trigger or RecheckTrigger(
        single_day_drop=ABNORMAL_DROP_1D, three_day_cumulative=ABNORMAL_DROP_3D
    )
    one_day = trigger.single_day_drop if drop_1d is None else drop_1d
    three_day = trigger.three_day_cumulative if drop_3d is None else drop_3d
    if daily_change_pct <= one_day:
        return True
    return three_day_change_pct is not None and three_day_change_pct <= three_day


def enqueue_review(
    *,
    recommendation_id: str,
    original_judgment_time: datetime,
    daily_change_pct: Decimal,
    three_day_change_pct: Decimal | None = None,
    trigger: RecheckTrigger | None = None,
) -> ReviewTicket | None:
    """异常下跌 → `enqueue_review`（`Ch5 §F.5` / `T08`）；未触发 → `None`（**不产工单**）。

    ★ 返回值是**复查工单**，不是买卖动作 —— `Ch5 §F.5` 明令"不自动止损/抄底"。
    ★ 阈值取 `rules/review.yaml::forced_recheck`（`trigger`）；**不硬编码**。
    """
    trigger = trigger or RecheckTrigger(
        single_day_drop=ABNORMAL_DROP_1D, three_day_cumulative=ABNORMAL_DROP_3D
    )
    if not is_abnormal_decline(
        daily_change_pct, three_day_change_pct=three_day_change_pct, trigger=trigger
    ):
        return None
    reason = (
        f"单日 {daily_change_pct} ≤ {trigger.single_day_drop}"
        if daily_change_pct <= trigger.single_day_drop
        else f"3 日累计 {three_day_change_pct} ≤ {trigger.three_day_cumulative}"
    )
    return ReviewTicket(
        recommendation_id=recommendation_id,
        status="rechecking",
        original_judgment_time=original_judgment_time,
        trigger=reason,
    )


# ───────────────────────── 守卫：真源扫描（CLI 承载面） ─────────────────────────

NOTE_NO_PRICES = "NO_PRICES"
_PRICE_CALIBER_FIELDS = ("currency", "trading_session", "adjustment_caliber_version")

RULE_BOUND_ENTRIES: tuple[tuple[str, str], ...] = (
    (REVIEW_YAML, RULE_KEY_FORCED_RECHECK),
)
"""``(规则文件, 本模块实际读取的顶层键)`` 的机器绑定对照集合（`Ch11 §D.2`）。"""


def _rule_binding_violations(root: Path, trigger: RecheckTrigger) -> list[str]:
    """**规则↔代码机器绑定**：`rules/review.yaml` 的强制复查口径必须与实现一致。

    | # | 判据 | 依据 |
    |---|---|---|
    | ① | `forced_recheck` 键**真实存在** | `Ch11 §D.2`（参数只住 `rules/`） |
    | ② | 阈值与代码回落值（B2）**一致** | B2 / `Ch5 §F.5` |
    | ③ | `on_hit.keep_original_judgment_time` 为真 | `T08`（复查未完成显示原判断时间） |

    ★ **"缺键"本身即违例**：①由键清单承担；③额外**单独判存在性** —— 该键缺失时加载器回落
      设计值，而"设计值"恰好等于"应该有的值"，按值比较**判不出缺键**（`G-03`：跳过不是通过）。
    ★ 规则文件不存在 → 返回空（调用方另有 note 面，**不**当已核）。
    """
    from scripts._common import _cached_yaml

    path = root / REVIEW_YAML
    if not path.exists():
        return []
    doc = _cached_yaml(path) or {}
    violations: list[str] = []
    for relpath, key in RULE_BOUND_ENTRIES:
        if key not in doc:
            violations.append(
                f"{relpath} 缺本模块实际读取的键 {key!r} —— 声明与实现脱节（Ch11 §D.2）"
            )
    if trigger.value_source != "rules":
        # 规则文件在（上面已 `path.exists()` 过）却读不到值 ⇒ 键缺失/非法；此时**不得**拿
        # 回落值去和代码常量比 —— 那会把"文件里根本没写"判成"一致"（静默通过）。
        violations.append(
            f"{REVIEW_YAML}:: {RULE_KEY_FORCED_RECHECK} 读不到值"
            f"（{trigger.notes[0] if trigger.notes else '原因未标注'}）—— "
            "**不**按回落值判'一致'（Ch11 §D.2；缺键本身即违例）"
        )
        return violations
    if trigger.single_day_drop != ABNORMAL_DROP_1D:
        violations.append(
            f"{REVIEW_YAML}:: {RULE_KEY_FORCED_RECHECK}.{RULE_KEY_SINGLE_DAY_DROP_PCT} "
            f"= {trigger.single_day_drop} 与代码回落值 {ABNORMAL_DROP_1D} 不一致（B2）"
        )
    if trigger.three_day_cumulative != ABNORMAL_DROP_3D:
        violations.append(
            f"{REVIEW_YAML}:: {RULE_KEY_FORCED_RECHECK}.{RULE_KEY_THREE_DAY_CUMULATIVE_PCT} "
            f"= {trigger.three_day_cumulative} 与代码回落值 {ABNORMAL_DROP_3D} 不一致（B2）"
        )
    if trigger.keep_original_judgment_time != DESIGN_KEEP_ORIGINAL_JUDGMENT_TIME:
        violations.append(
            f"{REVIEW_YAML}:: {RULE_KEY_FORCED_RECHECK}.{RULE_KEY_ON_HIT}."
            f"{RULE_KEY_KEEP_ORIGINAL_JUDGMENT_TIME}={trigger.keep_original_judgment_time} "
            f"与代码回落值 {DESIGN_KEEP_ORIGINAL_JUDGMENT_TIME} 不一致 —— `T08`：复查未完成时"
            "必须显示原判断时间（Ch5 §F.5）"
        )
    # ★ **`on_hit.keep_original_judgment_time` 缺键本身即违例**（第四轮补）：该键在真文件里
    #   **存在**。缺它时加载器回落设计值 ⇒ 值与回落值恰好相等 ⇒ 上面那条比较**判不出来**
    #   （`rules` 与"设计值"撞成同一个数），门禁就成了"缺键也不红"。故必须按**文档原文**
    #   单独判存在性（`G-03`："跳过不是通过"）。
    forced = doc.get(RULE_KEY_FORCED_RECHECK)
    on_hit = forced.get(RULE_KEY_ON_HIT) if isinstance(forced, Mapping) else None
    if not isinstance(on_hit, Mapping) or RULE_KEY_KEEP_ORIGINAL_JUDGMENT_TIME not in on_hit:
        violations.append(
            f"{REVIEW_YAML}:: {RULE_KEY_FORCED_RECHECK}.{RULE_KEY_ON_HIT}."
            f"{RULE_KEY_KEEP_ORIGINAL_JUDGMENT_TIME} 缺失 —— 缺键本身即违例（Ch11 §D.2）："
            f"回落值 {DESIGN_KEEP_ORIGINAL_JUDGMENT_TIME} 与设计值撞成同一个数，"
            "按值比较判不出缺键（故按文档原文判存在性）"
        )
    return violations


def check(root: str | Path) -> Any:
    """扫描 `facts/prices.jsonl`：每条行情必须过**口径五要素**（`Ch5 §F.1`）。

    ★ 判据是**运行时效果**：某条快照的口径要素缺失 ⇒ 它**不得**被用于解释与收益计算，
      故在此拦下（`N5.5-01` / `T11`）。空样本 → 显式 note（`G-03`）。
    ★ 另含**规则↔代码机器绑定**（与 `facts/` 数据无关，故空样本也照跑）：本模块读取的
      `rules/review.yaml::forced_recheck` 键必须真实存在，且阈值与代码回落值一致。
    """
    from scripts._common import CheckReport, Violation
    from schema.store import read_records

    root_path = Path(root)
    report = CheckReport(checker="pricelayer_daily_explain")
    report.scanned["rule_binding_checks"] = len(RULE_BOUND_ENTRIES)
    trigger = load_recheck_trigger(root_path)
    report.scanned["recheck_value_source"] = 1 if trigger.value_source == "rules" else 0
    # `design_default` 的 note 必须**真的上报**（主理人裁定 ③-2）。
    report.notes.extend(trigger.notes)
    for text in _rule_binding_violations(root_path, trigger):
        report.violations.append(Violation("DAILY-RULE-BINDING", text))

    rows = read_records(root_path, "prices")
    report.scanned["prices"] = len(rows)
    report.scanned["caliber_fields"] = len(_PRICE_CALIBER_FIELDS)
    if not rows:
        report.notes.append(f"{NOTE_NO_PRICES}: facts/prices.jsonl 无行（非'已验证'）")
        return report

    for row in rows:
        snapshot_id = str(row.get("snapshot_id") or "<no-snapshot_id>")
        quote_time = row.get("published_at") or row.get("occurred_at")
        caliber = QuoteCaliber(
            quote_time=(
                datetime.fromisoformat(str(quote_time)) if quote_time else None
            ),
            trading_session=str(row.get("trading_session") or ""),
            currency=str(row.get("currency") or ""),
            adjusted_flag=bool(str(row.get("adjustment_caliber_version") or "")) or None,
            corporate_actions_ref=str(row.get("adjustment_caliber_version") or ""),
            delayed=bool(row.get("delayed")),
        )
        try:
            validate_quote(caliber)
        except QuoteCaliberViolation as exc:
            report.violations.append(
                Violation("QUOTE-CALIBER", f"snapshot {snapshot_id}: {exc}")
            )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """CLI：`python system/scripts/pricelayer/daily_explain.py [code_root]`。"""
    from scripts._common import run_checker

    return run_checker("pricelayer_daily_explain", check, argv)


if __name__ == "__main__":  # pragma: no cover - CLI 出口
    raise SystemExit(main())
