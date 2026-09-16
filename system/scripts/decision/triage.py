"""`triage.py` —— **三维正交决策函数（序 / 信 / 深）**（`Ch6 §B.2` / `§B.3`）。

**一句话**（`Ch6 §B.2`）：把一条主张的三个**不可互相替代**的维度分别映射为
**处理优先级（序）** / **研究投入上限（深）** / **证据采纳（信）**，三者**互不影响**。

| 轴 | 函数 | 由谁决定 | **不允许**被谁影响 |
|---|---|---|---|
| **序**（order） | `priority_order()` | tier 为主、importance 调序 | 不得被 quality 影响 |
| **深**（investment） | `research_cap()` | **仅** importance | 不得被 tier / quality 影响 |
| **信**（trust） | `is_adoptable()` | **仅** quality | 不得突破 cap，不得影响顺序 |

★ **为什么是"字典序 + 字典表"而不是"加权和"**（`Ch6 §B.2` 四条理由）：
① 三轴语义**不可加**（"高重要性 + 低可信"的正确处理是"投入核验"，加权和会压成中间值）；
② 加权分可被"刷量"拉高，与"禁止数量/情绪投票"直接冲突；③ 字典序**可解释**（逐级回答"为什么先处理它"）；
④ 分数化即违规（`Ch2 §B.2 P-09`）。

★ **反加权在结构上成立**（`Ch6 §B.3`）：决策函数**只接受** `DecisionView`（frozen dataclass），
  该 dataclass **物理上不包含** 粉丝 / 点赞 / 播放量 / 情绪这类热度字段 —— 决策代码**无法**读到它们。
  对外部记录取值一律走 **allowlist**（`view_from_record()`，未列出的键**默认丢弃**），
  因此"给记录多加一个 `followers` 字段"**不改变任何输出**（`R-06`：白名单对未列出的形式默认拒绝）。

★ **参数不进决策函数**（`施工图 §8` 纪律 1 / `Ch11 §E.1`）：本模块只做**字典映射与布尔判定**，
  不读任何冻结参数、不设任何数值置信度阈值。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

# 分级字典表（`Ch6 §B.2` 逐字）：输出越小越先处理。
TIER_RANK: dict[str, int] = {
    "primary": 0,
    "secondary_1_5": 1,
    "secondary_tertiary": 2,
}

# 经济重要性字典表（`Ch6 §B.2` 逐字）：仅决定"研究投入上限"。
IMPORTANCE_RANK: dict[str, int] = {
    "high": 2,
    "medium": 1,
    "low": 0,
}

# 研究投入上限（单位：模型调用数），`Ch6 §B.2` 逐字。
BUDGET_MAP: dict[str, int] = {
    "high": 40,
    "medium": 15,
    "low": 4,
}


class UnknownTierError(ValueError):
    """非法 `tier` —— **响亮失败**（不静默按 0 处理，避免"非法值最优先"）。"""


class UnknownImportanceError(ValueError):
    """非法 `importance_class` —— **响亮失败**（不静默当 low / high）。"""


def _as_utc(moment: datetime) -> datetime:
    """把 `first_seen_at` 归一为 **aware UTC**（naive 视为 UTC）—— 保证排序是**全序**且跨时区可比。

    naive 与 aware 直接比较会抛 `TypeError`；显式归一后：同一 `(tier, importance)` 下
    按"更早见到者优先"，同一时刻以 `claim_id` 兜底（`Ch6 §B.2` 的"时间兜底"）。
    """
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


@dataclass(frozen=True)
class DecisionView:
    """决策函数的**唯一**输入视图（`Ch6 §B.3` 类型约束）。

    ★ 字段是**允许进入决策**的最小集合；被禁元数据（粉丝 / 点赞 / 播放量 / 情绪 / 数量投票）
      在此 dataclass 上**不存在** —— 决策代码无法读到它们，故"刷量"在结构上不可能影响输出。
    """

    claim_id: str
    tier: str                       # primary | secondary_1_5 | secondary_tertiary
    importance_class: str           # high | medium | low
    first_seen_at: datetime
    direct_knowledge: str           # direct | indirect | unknown
    method_reproducible: bool
    caliber_match: bool
    independent_evidence_count: int
    strong_counter_evidence: tuple[str, ...] = ()

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "DecisionView":
        """从外部记录取决策视图 —— **allowlist** 取值（未列出的键默认丢弃）。

        ★ 为什么必须 allowlist（`R-06`）：denylist（"排除若干热度键"）**不可穷尽**，
          换一个键名即可绕过。白名单**只取**决策真正需要的字段，未列出的键**默认拒绝**，
          因此"给记录多塞一个热度字段"在**任何命名**下都不改变输出。
        """
        return view_from_record(record)


def view_from_record(record: Mapping[str, Any]) -> DecisionView:
    """按 **allowlist** 从记录构造 `DecisionView`；缺必填键 → `KeyError`（**响亮失败**）。"""
    allowed = (
        "claim_id",
        "tier",
        "importance_class",
        "first_seen_at",
        "direct_knowledge",
        "method_reproducible",
        "caliber_match",
        "independent_evidence_count",
    )
    missing = [name for name in allowed if name not in record]
    if missing:
        raise KeyError(f"决策视图缺必填字段 {missing}（allowlist 取值，不做静默兜底）")
    raw_time = record["first_seen_at"]
    first_seen_at = raw_time if isinstance(raw_time, datetime) else datetime.fromisoformat(str(raw_time))
    return DecisionView(
        claim_id=str(record["claim_id"]),
        tier=str(record["tier"]),
        importance_class=str(record["importance_class"]),
        first_seen_at=first_seen_at,
        direct_knowledge=str(record["direct_knowledge"]),
        method_reproducible=bool(record["method_reproducible"]),
        caliber_match=bool(record["caliber_match"]),
        independent_evidence_count=int(record["independent_evidence_count"]),
        strong_counter_evidence=tuple(str(x) for x in record.get("strong_counter_evidence", ())),
    )


def priority_order(view: DecisionView) -> tuple[int, int, datetime, str]:
    """**处理优先级**（`Ch6 §B.2` 逐字）：`(tier 秩, -importance 秩, 时间, claim_id)` —— 输出越小越先处理。

    ★ 字典序而非加权和：`tier` 决定"先看什么"，`importance` 只在**同级内**调序，
      **质量（信）完全不参与**（`Ch6 §B.2` 三轴职责边界）。
    """
    if view.tier not in TIER_RANK:
        raise UnknownTierError(f"非法 tier {view.tier!r}；合法值 {sorted(TIER_RANK)}")
    if view.importance_class not in IMPORTANCE_RANK:
        raise UnknownImportanceError(
            f"非法 importance_class {view.importance_class!r}；合法值 {sorted(IMPORTANCE_RANK)}"
        )
    return (
        TIER_RANK[view.tier],
        -IMPORTANCE_RANK[view.importance_class],
        _as_utc(view.first_seen_at),
        view.claim_id,
    )


def research_cap(view: DecisionView) -> int:
    """**研究投入上限**（`Ch6 §B.2` 逐字）：**仅由经济重要性决定**，与 tier、quality 无关。"""
    if view.importance_class not in BUDGET_MAP:
        raise UnknownImportanceError(
            f"非法 importance_class {view.importance_class!r}；合法值 {sorted(BUDGET_MAP)}"
        )
    return BUDGET_MAP[view.importance_class]


def is_adoptable(view: DecisionView) -> bool:
    """**证据采纳**（`Ch6 §B.2` 逐字）：由 quality 决定（只影响采纳与置信）。

    判据 = 口径匹配 **且** （直接知识 ∨ 可复核方法 ∨ 有独立佐证）**且** 无强反证。
    采纳**不改变顺序**，也不**突破** `research_cap` —— 三轴职责边界（`Ch6 §B.2`）。
    """
    direct = view.direct_knowledge == "direct"
    reproducible = view.method_reproducible
    corroborated = view.independent_evidence_count >= 1
    return bool(view.caliber_match) and (direct or reproducible or corroborated) and not view.strong_counter_evidence


def sort_views(views: Sequence[DecisionView]) -> list[DecisionView]:
    """按 `priority_order` 字典序升序排序（**稳定、可复现、无分数**）。"""
    return sorted(views, key=priority_order)
