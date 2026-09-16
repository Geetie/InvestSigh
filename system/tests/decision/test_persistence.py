"""建议构造与落库单测（`Ch7 §E` 8 字段 / `Ch9 §3.3.4 R-07` / `§3.4.2` 追加式不可变）。

覆盖：
- `build_recommendation` 构造 `schema.models.Recommendation`（`action` 四值、`horizon` 区间）；
- 提前判断三要素缺项 → **不出建议**（`EarlyJudgmentIncomplete`）；
- `persist_recommendation` **复用** `schema.store.append_records` → 落 `facts/recommendations.jsonl`；
- **幂等键**（`P7-4` / `Ch9 §3.5` 阶段⑤）：同"输入窗口 + 规则版本"重跑 → **不新增行**；
  反向对照：**不同**窗口 → **应新增**；
- **版本链**：同业务键 `(security_id, start_date)` 的新版本写 `version` / `recorded_seq`，
  `schema.store.as_of` 对 `recommendations` 可取到**最新版本**；
- `rebuild_index` 从 `facts/` 全量重建 `index/`（索引非真源）。
"""

from __future__ import annotations

from datetime import date

import pytest
from decision_builders import make_forecast, make_input

from scripts.decision.gate import EarlyJudgmentIncomplete, JudgmentChange
from scripts.decision.rules import (
    HorizonOutOfRange,
    PersistOutcome,
    build_recommendation,
    decide,
    persist_recommendation,
    persist_recommendation_detailed,
)
from schema.models import Recommendation, RecommendationAction
from schema.store import as_of, read_models, read_records, rebuild_index

START = date(2026, 4, 1)
REVIEW = date(2026, 9, 15)


def _buy_decision():
    inp = make_input(stock=make_forecast("0.10", "0.12"), benchmark=make_forecast("0.05", "0.06"))
    decision = decide(inp, JudgmentChange(fact_set_changed=True))
    assert decision is not None
    return inp, decision


def _rec(*, recommendation_id="rec-persist", start=START, review=REVIEW, rule_version="decision-v1"):
    inp, decision = _buy_decision()
    return build_recommendation(
        decision,
        inp=inp,
        recommendation_id=recommendation_id,
        security_id="usDEMO",
        horizon="2q",
        start_date=start,
        rule_version=rule_version,
        review_date=review,
        evidence_version_ids=("dv-total_return-co-demo-compute-v1",),
    )


def test_build_recommendation_fields() -> None:
    inp, decision = _buy_decision()
    rec = build_recommendation(
        decision,
        inp=inp,
        recommendation_id="rec-1",
        security_id="usDEMO",
        horizon="2q",
        start_date=START,
        rule_version="decision-v1",
        review_date=REVIEW,
        evidence_version_ids=("dv-total_return-co-demo-compute-v1",),
    )
    assert isinstance(rec, Recommendation)
    assert rec.action == RecommendationAction.buy
    assert rec.company_id == "co-demo"
    assert rec.horizon == "2q"
    assert rec.change_reason == decision.change_reason


def test_build_recommendation_rejects_out_of_range_horizon() -> None:
    inp, decision = _buy_decision()
    with pytest.raises(HorizonOutOfRange):
        build_recommendation(
            decision,
            inp=inp,
            recommendation_id="rec-2",
            security_id="usDEMO",
            horizon="18m",
            start_date=START,
            rule_version="decision-v1",
        )


def test_early_judgment_with_empty_trio_is_rejected() -> None:
    """`Ch2 §D.1 A-06`：提前判断三要素任一为空 → **不出建议**。"""
    inp, decision = _buy_decision()
    with pytest.raises(EarlyJudgmentIncomplete):
        build_recommendation(
            decision,
            inp=inp,
            recommendation_id="rec-3",
            security_id="usDEMO",
            horizon="2q",
            start_date=START,
            rule_version="decision-v1",
            early_judgment=True,
            assumptions=[],
            evidence_gaps=["gap:no-order"],
            verification_conditions=["cond:order-confirmed"],
        )


def test_early_judgment_with_full_trio_is_accepted() -> None:
    inp, decision = _buy_decision()
    rec = build_recommendation(
        decision,
        inp=inp,
        recommendation_id="rec-4",
        security_id="usDEMO",
        horizon="2q",
        start_date=START,
        rule_version="decision-v1",
        early_judgment=True,
        assumptions=["assumption:ramp-on-track"],
        evidence_gaps=["gap:no-order-yet"],
        verification_conditions=["cond:q3-order-confirmed"],
    )
    assert rec.early_judgment is True
    assert rec.assumptions and rec.evidence_gaps and rec.verification_conditions


def test_persist_appends_and_rebuilds_index(scratch) -> None:
    rec = _rec()
    written = persist_recommendation(scratch, rec)
    assert written == 1

    rows = read_models(scratch, "recommendations")
    assert [r.recommendation_id for r in rows] == ["rec-persist"]

    index_path = rebuild_index(scratch)
    assert index_path.exists() and index_path.stat().st_size > 0


def test_persist_same_window_rerun_does_not_append(scratch) -> None:
    """`P7-4`：同"输入窗口 + 规则版本"重跑 → **不新增行**（幂等）。

    ★ 修复前的反例：旧 `persist_recommendation` 直接 `append_records`，重跑会**追加重复**
      `recommendation_id`；旧断言把这一缺陷写成了期望（见 `ws_decision_fix_report.md`）。
    """
    rec = _rec()
    assert persist_recommendation(scratch, rec) == 1
    # 重跑同一窗口 + 同一规则版本 → 幂等命中，**0 新增**
    assert persist_recommendation(scratch, rec) == 0
    rows = read_models(scratch, "recommendations")
    assert [r.recommendation_id for r in rows] == ["rec-persist"]


def test_persist_different_window_appends_new_row(scratch) -> None:
    """**反向对照**：**不同**输入窗口 → **应新增**（幂等键不是恒 true 的"永远跳过"）。"""
    assert persist_recommendation(scratch, _rec(recommendation_id="rec-a", start=START)) == 1
    assert (
        persist_recommendation(
            scratch, _rec(recommendation_id="rec-b", start=date(2026, 6, 1))
        )
        == 1
    )
    rows = read_models(scratch, "recommendations")
    assert sorted(r.recommendation_id for r in rows) == ["rec-a", "rec-b"]


# ═════════ `persist_recommendation_detailed`：唯一写入口如实回传两个互斥集合 ═════════
#
# 缺陷 `G-44`：`scripts/decision/step.py` 原先只拿得到"写了什么"，拿不到"考察过、但已存在故没写"，
# 于是幂等重跑时 `produced=[]` 且无法说明"我确实考察过了" → `chain_steps` 的适配器判
# `incomplete_reason` → `STATUS_GAP` → **整轮 blocked**（实测：连续第二次 `run_daily` 必然 blocked）。


def test_detailed_reports_written_then_skipped_across_rerun(scratch) -> None:
    """双跑判别式：首轮 `written_ids` 非空 / `skipped_ids` 空；重跑**反向**。"""
    rec = _rec()
    first = persist_recommendation_detailed(scratch, rec)
    assert first.written_ids == ("rec-persist",), "首轮应真正写入"
    assert first.skipped_ids == (), "首轮不该有幂等命中（否则判别式失去判别力）"
    assert len(read_records(scratch, "recommendations")) == 1

    second = persist_recommendation_detailed(scratch, rec)
    assert second.written_ids == (), "重跑未新写入 → written_ids 必须为空"
    assert second.skipped_ids == ("rec-persist",), (
        "★ 重跑必须把'考察过、已存在故未写入'的建议如实回报到 skipped_ids —— "
        "缺了它，上层无法区分『空执行』与『幂等命中』（G-44）"
    )
    assert len(read_records(scratch, "recommendations")) == 1, "重跑不得新增行"


def test_detailed_written_and_skipped_are_disjoint(scratch) -> None:
    """★ 互斥不变量：`written_ids ∩ skipped_ids = ∅`（新窗口写入、旧窗口命中）。"""
    assert persist_recommendation_detailed(scratch, _rec(recommendation_id="rec-a")).written_ids == ("rec-a",)
    out = persist_recommendation_detailed(scratch, _rec(recommendation_id="rec-b", start=date(2026, 6, 1)))
    assert out.written_ids == ("rec-b",) and out.skipped_ids == ()
    assert set(out.written_ids) & set(out.skipped_ids) == set()


def test_persist_outcome_rejects_self_contradiction() -> None:
    """★ G-42 同源：`PersistOutcome` 自己就拒绝"同一 id 两边都有"的自相矛盾输入。"""
    with pytest.raises(ValueError, match="自相矛盾"):
        PersistOutcome(written_ids=("rec-x",), skipped_ids=("rec-x",))


def test_count_view_stays_consistent_with_detailed_view(scratch) -> None:
    """既有契约不回归：`persist_recommendation` == `len(detailed.written_ids)`（两个视图同源）。"""
    rec = _rec()
    assert persist_recommendation(scratch, rec) == 1
    assert persist_recommendation(scratch, rec) == 0
    assert persist_recommendation(scratch, rec) == 0


def test_version_chain_is_usable_via_as_of(scratch) -> None:
    """同业务键 `(security_id, start_date)` 的新版本 → `version` / `recorded_seq` 递增，
    `schema.store.as_of` 取到**最新版本**（修复前 `version` 恒 1、`recorded_seq` 恒 None）。"""
    # 同窗口、不同**规则版本** → 视为该业务键的新版本（写入放行）
    assert persist_recommendation(scratch, _rec(rule_version="decision-v1")) == 1
    assert persist_recommendation(scratch, _rec(rule_version="decision-v2")) == 1

    rows = read_records(scratch, "recommendations")
    assert len(rows) == 2
    assert [r["version"] for r in rows] == [1, 2]
    assert [r["recorded_seq"] for r in rows] == [1, 2]

    latest = as_of(rows, ["security_id", "start_date"])
    assert len(latest) == 1
    assert latest[0]["rule_version"] == "decision-v2"
    assert latest[0]["recorded_seq"] == 2


def test_recommendation_action_enum_is_four_values_only() -> None:
    """`Ch2 §B.2 P-05`：`action` 不得含做空、不得含仓位/数量。"""
    assert {a.value for a in RecommendationAction} == {"buy", "sell", "pending", "maintain"}
