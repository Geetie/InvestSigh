"""五者语义层级 + 停止判定（`Ch7 §B.4 / §C.2 / §C.5 / §C.6`）测试。

覆盖 AC-08（特别：`capex` ≠ 订单 / 收入）与 AC-05（条件不足 → 事件保留、不下结论）。
"""

from __future__ import annotations

import pytest

from scripts.graph.stage_order import (
    STAGE_ORDER,
    StageEquivalenceError,
    assert_not_equivalent,
)
from scripts.graph.stop import (
    GAIN_KEY_UNDISCLOSED,
    Hop,
    PathState,
    TransmitParams,
    cumulative_amplification,
    evidence_gate,
    should_stop,
)

PARAMS = TransmitParams(
    importance_threshold=0.5,
    amplification_cap=8.0,
    gain_map={GAIN_KEY_UNDISCLOSED: 1.5, "high": 2.0},
    max_depth=5,
)


# ───────────────────────── AC-08 禁跳级等同（capex ≠ 订单 / 收入） ─────────────────────────

def test_stage_order_matches_design_verbatim() -> None:
    assert STAGE_ORDER == {
        "order": 0,
        "purchase_commitment": 1,
        "capex": 2,
        "production_schedule": 3,
        "revenue": 4,
    }


def test_capex_is_not_order_or_revenue() -> None:
    """★ `Ch7 §C`：`capex`（需求侧）不得作为供应商的订单 / 收入证据。"""
    with pytest.raises(StageEquivalenceError):
        assert_not_equivalent("capex", "order")
    with pytest.raises(StageEquivalenceError):
        assert_not_equivalent("capex", "revenue")
    # 即便是"拿着跳级证据"也不放行需求侧冒充供给结果
    with pytest.raises(StageEquivalenceError):
        assert_not_equivalent("capex", "order", evidence={"skip_justification": "x"})


def test_adjacent_jump_allowed_far_jump_requires_evidence() -> None:
    assert_not_equivalent("order", "purchase_commitment")             # 相邻 → 放行
    assert_not_equivalent("revenue", "production_schedule")          # 降一档 → 放行
    with pytest.raises(StageEquivalenceError):
        assert_not_equivalent("order", "revenue")                    # 跨多级、无证据 → 拒绝
    assert_not_equivalent("order", "revenue", evidence={"skip_justification": "mid-stage claim"})
    with pytest.raises(ValueError):
        assert_not_equivalent("order", "not_a_stage")


# ───────────────────────── AC-05 依据门槛（条件不足 → 不下结论） ─────────────────────────

def _passing_hop(**over: object) -> Hop:
    base: dict[str, object] = dict(
        node_key="n1",
        relation_id="rel1",
        evidence_claim_ids=("c1",),
        variable="demand",
        direction="+",
        conditions=("cond",),
        target_type="",
        importance=1.0,
        forward_forces=2.0,
        counter_forces=1.0,
        terminal_demand_id="tX",
        evidence=("c2",),
        gain_key=GAIN_KEY_UNDISCLOSED,
    )
    base.update(over)
    return Hop(**base)  # type: ignore[arg-type]


def _passing_path() -> PathState:
    return PathState(
        visited=("n0",),
        upstream_evidence=frozenset({"c1"}),
        counted_terminals=frozenset({"tY"}),
        cumulative_amplification=1.0,
    )


def test_claim_passes_through_when_all_conditions_ok() -> None:
    assert evidence_gate(_passing_hop(), PARAMS) is True
    assert should_stop(_passing_hop(), _passing_path(), PARAMS).action == "continue"


def test_specific_entity_requires_location_supply_or_procurement() -> None:
    """`Ch7 §C.6`：目标=具体经营实体 → `location/supply_mode/procurement_link` 至少一项非空。"""
    hop = _passing_hop(target_type="specific_operating_entity")
    assert evidence_gate(hop, PARAMS) is False
    assert should_stop(hop, _passing_path(), PARAMS).mark == "evidence_insufficient"
    ok = _passing_hop(target_type="specific_operating_entity", location="Virginia")
    assert evidence_gate(ok, PARAMS) is True


# ───────────────────────── AC-05 7 个停止条件逐条 ─────────────────────────

def test_stop_condition_1_evidence_gate() -> None:
    d = should_stop(_passing_hop(relation_id=None), _passing_path(), PARAMS)
    assert (d.action, d.reason, d.mark) == ("stop", "evidence_insufficient", "evidence_insufficient")


def test_stop_condition_2_low_importance() -> None:
    d = should_stop(_passing_hop(importance=0.1), _passing_path(), PARAMS)
    assert d.reason == "low_importance"
    # unknown_but_important 例外 → 不因低重要性停
    d2 = should_stop(_passing_hop(importance=0.1, unknown_but_important=True), _passing_path(), PARAMS)
    assert d2.action == "continue"


def test_stop_condition_3_cycle() -> None:
    d = should_stop(_passing_hop(node_key="n0"), _passing_path(), PARAMS)
    assert d.reason == "cycle" and d.effect == "record_cycle"


def test_stop_condition_4_direction_doubtful() -> None:
    d = should_stop(_passing_hop(forward_forces=1.0, counter_forces=1.0), _passing_path(), PARAMS)
    assert d.reason == "direction_doubtful" and d.mark == "direction_doubtful"


def test_stop_condition_5_duplicate_evidence() -> None:
    d = should_stop(_passing_hop(evidence=("c1",)), _passing_path(), PARAMS)
    assert d.reason == "duplicate_evidence"


def test_stop_condition_6_terminal_demand_dup() -> None:
    d = should_stop(_passing_hop(terminal_demand_id="tY"), _passing_path(), PARAMS)
    assert d.reason == "terminal_demand_dup" and d.effect == "allocate"


def test_stop_condition_7_amplification_capped() -> None:
    path = _passing_path()
    path.cumulative_amplification = 10.0     # 10 * 1.5 = 15 > cap 8
    d = should_stop(_passing_hop(), path, PARAMS)
    assert d.reason == "amplification_capped" and d.effect == "decay"


def test_cumulative_amplification_multiplies_along_path() -> None:
    hop = _passing_hop(gain_key="high")       # gain 2.0
    assert cumulative_amplification(1.0, hop, PARAMS) == 2.0
    assert cumulative_amplification(2.0, hop, PARAMS) == 4.0
