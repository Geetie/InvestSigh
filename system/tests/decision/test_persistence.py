"""建议构造与落库单测（`Ch7 §E` 8 字段 / `Ch9 §3.3.4 R-07` / `§3.4.2` 追加式不可变）。

覆盖：
- `build_recommendation` 构造 `schema.models.Recommendation`（`action` 四值、`horizon` 区间）；
- 提前判断三要素缺项 → **不出建议**（`EarlyJudgmentIncomplete`）；
- `persist_recommendation` **复用** `schema.store.append_records` → 落 `facts/recommendations.jsonl`；
- `rebuild_index` 从 `facts/` 全量重建 `index/`（索引非真源）。
"""

from __future__ import annotations

from datetime import date

import pytest
from decision_builders import make_forecast, make_input

from scripts.decision.gate import EarlyJudgmentIncomplete, JudgmentChange
from scripts.decision.rules import (
    HorizonOutOfRange,
    build_recommendation,
    decide,
    persist_recommendation,
)
from schema.models import Recommendation, RecommendationAction
from schema.store import read_models, rebuild_index

START = date(2026, 4, 1)


def _buy_decision():
    inp = make_input(stock=make_forecast("0.10", "0.12"), benchmark=make_forecast("0.05", "0.06"))
    decision = decide(inp, JudgmentChange(fact_set_changed=True))
    assert decision is not None
    return inp, decision


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
        review_date=date(2026, 9, 15),
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
    inp, decision = _buy_decision()
    rec = build_recommendation(
        decision,
        inp=inp,
        recommendation_id="rec-persist",
        security_id="usDEMO",
        horizon="2q",
        start_date=START,
        rule_version="decision-v1",
        evidence_version_ids=("dv-total_return-co-demo-compute-v1",),
    )
    written = persist_recommendation(scratch, rec)
    assert written == 1

    rows = read_models(scratch, "recommendations")
    assert [r.recommendation_id for r in rows] == ["rec-persist"]

    index_path = rebuild_index(scratch)
    assert index_path.exists() and index_path.stat().st_size > 0


def test_persist_is_append_only(scratch) -> None:
    inp, decision = _buy_decision()
    for rid in ("rec-a", "rec-b"):
        rec = build_recommendation(
            decision,
            inp=inp,
            recommendation_id=rid,
            security_id="usDEMO",
            horizon="2q",
            start_date=START,
            rule_version="decision-v1",
        )
        persist_recommendation(scratch, rec)
    rows = read_models(scratch, "recommendations")
    assert [r.recommendation_id for r in rows] == ["rec-a", "rec-b"]


def test_recommendation_action_enum_is_four_values_only() -> None:
    """`Ch2 §B.2 P-05`：`action` 不得含做空、不得含仓位/数量。"""
    assert {a.value for a in RecommendationAction} == {"buy", "sell", "pending", "maintain"}
