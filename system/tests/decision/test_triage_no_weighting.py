"""三维正交决策函数的**反加权**单测（`Ch6 §B.2` / `§B.3` / `Ch2 §B.2 P-09`）。

三条互补证据（缺一不足以证明"无加权"）：

1. **签名无 weight/score**：`priority_order` / `research_cap` / `is_adoptable` 的参数只有视图对象。
2. **类型约束**：`DecisionView` **物理上不包含**热度字段 → 决策代码读不到热度。
3. **不变性 fuzz**：给记录注入被禁元数据（粉丝 / 点赞 / 播放量 / 情绪 / 数量投票…），
   断言三个决策函数的输出**完全不变**（allowlist 取值，未列出的键默认丢弃）。
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest

from scripts.decision import triage
from scripts.decision.triage import (
    BUDGET_MAP,
    DecisionView,
    UnknownImportanceError,
    UnknownTierError,
    is_adoptable,
    priority_order,
    research_cap,
    sort_views,
    view_from_record,
)

# 被禁元数据（`Ch6 §B.3`）：粉丝 / 点赞 / 播放量 / 转发量 / 情绪 / 数量 / 加权分 / 打分 / 投票。
# 它们**不得**出现在决策函数的签名或 `DecisionView` 的字段里。
BANNED_METADATA_KEYS: tuple[str, ...] = (
    "followers",
    "follower_count",
    "likes",
    "view_count",
    "play_count",
    "article_count",
    "repost_count",
    "sentiment",
    "sentiment_score",
    "popularity",
    "vote",
    "weight",
    "score",
)

BASE_RECORD: dict[str, object] = {
    "claim_id": "cl-1",
    "tier": "primary",
    "importance_class": "high",
    "first_seen_at": "2026-05-01T00:00:00",
    "direct_knowledge": "direct",
    "method_reproducible": True,
    "caliber_match": True,
    "independent_evidence_count": 0,
}


def _view(
    *,
    claim_id: str = "cl-1",
    tier: str = "primary",
    importance_class: str = "high",
    first_seen_at: datetime | None = None,
    direct_knowledge: str = "direct",
    method_reproducible: bool = True,
    caliber_match: bool = True,
    independent_evidence_count: int = 0,
    strong_counter_evidence: tuple[str, ...] = (),
) -> DecisionView:
    return DecisionView(
        claim_id=claim_id,
        tier=tier,
        importance_class=importance_class,
        first_seen_at=first_seen_at or datetime(2026, 5, 1, tzinfo=timezone.utc),
        direct_knowledge=direct_knowledge,
        method_reproducible=method_reproducible,
        caliber_match=caliber_match,
        independent_evidence_count=independent_evidence_count,
        strong_counter_evidence=strong_counter_evidence,
    )


# ───────────────────────── ① 签名无 weight / score ─────────────────────────


def test_decision_functions_take_only_the_view() -> None:
    """三个决策函数的参数**只有**视图对象（不得有 weight / score 参数）。"""
    for fn in (priority_order, research_cap, is_adoptable):
        params = list(inspect.signature(fn).parameters)
        assert params == ["view"], f"{fn.__name__} 的参数应为 ['view']，实为 {params}"


def test_decision_function_parameter_names_contain_no_banned_token() -> None:
    """参数名不得命中被禁 token（含 weight / score / vote / sentiment / follower_count）。"""
    banned = set(BANNED_METADATA_KEYS)
    for fn in (priority_order, research_cap, is_adoptable):
        for name in inspect.signature(fn).parameters:
            assert name.lower() not in banned, f"{fn.__name__} 参数名 {name!r} 命中被禁 token"


# ───────────────────────── ② 类型约束（物理上读不到热度） ─────────────────────────


def test_decision_view_has_no_hotness_fields() -> None:
    """`DecisionView` **物理上不包含**任何被禁元数据字段。"""
    fields = set(DecisionView.__dataclass_fields__)
    leaked = fields & set(BANNED_METADATA_KEYS)
    assert not leaked, f"DecisionView 泄露了热度字段: {sorted(leaked)}"


# ───────────────────────── ③ 不变性 fuzz ─────────────────────────


def test_view_from_record_is_allowlist_and_drops_unknown_keys() -> None:
    """`view_from_record` 只取白名单字段；多塞的键被丢弃。"""
    pristine = view_from_record(dict(BASE_RECORD))
    trashed = dict(BASE_RECORD)
    trashed.update({key: 1_000_000_000 for key in BANNED_METADATA_KEYS})
    assert view_from_record(trashed) == pristine


def test_priority_order_invariant_under_injected_metadata() -> None:
    """注入热度元数据后 `priority_order` **完全不变**。"""
    pristine = priority_order(view_from_record(dict(BASE_RECORD)))
    for key in BANNED_METADATA_KEYS:
        trashed = dict(BASE_RECORD)
        trashed[key] = 1_000_000_000
        assert priority_order(view_from_record(trashed)) == pristine, f"注入 {key!r} 改变了处理顺序"


def test_research_cap_invariant_under_injected_metadata() -> None:
    """注入热度元数据后 `research_cap` **完全不变**。"""
    pristine = research_cap(view_from_record(dict(BASE_RECORD)))
    for key in BANNED_METADATA_KEYS:
        trashed = dict(BASE_RECORD)
        trashed[key] = 1_000_000_000
        assert research_cap(view_from_record(trashed)) == pristine, f"注入 {key!r} 改变了研究投入上限"


def test_is_adoptable_invariant_under_injected_metadata() -> None:
    """注入热度元数据后 `is_adoptable` **完全不变**。"""
    pristine = is_adoptable(view_from_record(dict(BASE_RECORD)))
    for key in BANNED_METADATA_KEYS:
        trashed = dict(BASE_RECORD)
        trashed[key] = 1_000_000_000
        assert is_adoptable(view_from_record(trashed)) == pristine, f"注入 {key!r} 改变了采纳判定"


# ───────────────────────── 三轴职责边界（互不影响） ─────────────────────────


def test_priority_order_is_lexicographic_tier_then_importance() -> None:
    """`tier` 为主、`importance` 只同级调序（字典序，非加权和）。"""
    primary_low = _view(claim_id="a", tier="primary", importance_class="low")
    secondary_high = _view(claim_id="b", tier="secondary_1_5", importance_class="high")
    assert priority_order(primary_low) < priority_order(secondary_high)

    primary_high = _view(claim_id="c", tier="primary", importance_class="high")
    assert priority_order(primary_high) < priority_order(primary_low)


def test_priority_order_is_not_affected_by_quality() -> None:
    """质量（信）**不参与**顺序：同 tier/importance 下，低质量与高质量顺序一致。"""
    strong = _view(claim_id="x", direct_knowledge="direct", independent_evidence_count=9)
    weak = _view(claim_id="x", direct_knowledge="unknown", caliber_match=False)
    assert priority_order(strong) == priority_order(weak)


def test_research_cap_depends_only_on_importance() -> None:
    """研究投入上限**仅**由经济重要性决定（tier / quality 均不影响）。"""
    for tier in ("primary", "secondary_1_5", "secondary_tertiary"):
        for direct, repro, cal in ((True, True, True), (False, False, False)):
            view = _view(tier=tier, importance_class="high", direct_knowledge="direct" if direct else "unknown",
                         method_reproducible=repro, caliber_match=cal)
            assert research_cap(view) == BUDGET_MAP["high"]


def test_is_adoptable_depends_only_on_quality() -> None:
    """采纳判定**仅**由质量决定（tier / importance 均不影响），且不突破 cap。"""
    for tier in ("primary", "secondary_tertiary"):
        for importance in ("high", "low"):
            view = _view(tier=tier, importance_class=importance)
            assert is_adoptable(view) is True


def test_is_adoptable_requires_caliber_and_a_support_and_no_counter() -> None:
    """`is_adoptable` = 口径匹配 ∧（直接 ∨ 可复核 ∨ 独立佐证）∧ 无强反证。"""
    assert is_adoptable(_view()) is True
    assert is_adoptable(_view(caliber_match=False)) is False
    assert is_adoptable(
        _view(direct_knowledge="unknown", method_reproducible=False, independent_evidence_count=0)
    ) is False
    assert is_adoptable(
        _view(direct_knowledge="unknown", method_reproducible=False, independent_evidence_count=1)
    ) is True
    assert is_adoptable(_view(strong_counter_evidence=("cl-9",))) is False


def test_sort_views_is_deterministic_and_quality_free() -> None:
    """排序稳定可复现；结果与质量无关。"""
    views = [
        _view(claim_id="b", tier="primary", importance_class="low"),
        _view(claim_id="a", tier="primary", importance_class="high"),
        _view(claim_id="c", tier="secondary_tertiary", importance_class="high"),
    ]
    ordered = [v.claim_id for v in sort_views(views)]
    assert ordered == ["a", "b", "c"]
    assert [v.claim_id for v in sort_views(list(reversed(views)))] == ordered


# ───────────────────────── 响亮失败（不静默兜底） ─────────────────────────


def test_unknown_tier_raises() -> None:
    with pytest.raises(UnknownTierError):
        priority_order(_view(tier="god_tier"))


def test_unknown_importance_raises() -> None:
    with pytest.raises(UnknownImportanceError):
        research_cap(_view(importance_class="critical"))


def test_missing_required_field_raises_key_error() -> None:
    broken = dict(BASE_RECORD)
    del broken["claim_id"]
    with pytest.raises(KeyError):
        view_from_record(broken)


def test_naive_and_aware_timestamps_are_comparable() -> None:
    """naive 视为 UTC：两个时区表达的时间排序一致（不抛 `TypeError`）。"""
    naive = _view(claim_id="a", first_seen_at=datetime(2026, 5, 1, 0, 0, 0))
    aware = _view(claim_id="b", first_seen_at=datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc))
    assert priority_order(naive)[:3] == priority_order(aware)[:3]
    assert sort_views([naive, aware])


def test_triage_module_declares_rank_tables() -> None:
    """分级字典表逐字对齐设计（`Ch6 §B.2`）：改表即改语义，须留痕。"""
    assert triage.TIER_RANK == {"primary": 0, "secondary_1_5": 1, "secondary_tertiary": 2}
    assert triage.IMPORTANCE_RANK == {"high": 2, "medium": 1, "low": 0}
    assert BUDGET_MAP == {"high": 40, "medium": 15, "low": 4}
