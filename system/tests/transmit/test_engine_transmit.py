"""传导编排测试（`Ch7 §C.1 / §C.2 / §C.6`；AC-01 / AC-03 / AC-04）。

覆盖：撤回传导逐层可达 + `recheck` 入队；禁跳级等同真抛；放大上限门槛由调用方传入。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from scripts.graph.stage_order import StageEquivalenceError, assert_not_equivalent
from scripts.transmit.engine import retraction_downstream, transmit
from transmit_builders import (
    chain_edges,
    edge,
    fanout_edges,
    fields,
    fields_map,
    make_params,
    seed_retraction_chain,
)

RUN_DAY = date(2026, 9, 16)


# ───────────────────────── AC-01 撤回传导：逐层可达 + 真入队 ─────────────────────────


def test_retraction_layered_downstream_and_recheck(code_root: Path) -> None:
    seed_retraction_chain(code_root)

    result = retraction_downstream(code_root, "c1", run_date=RUN_DAY, apply=True)

    # 逐层可达的下游集合（方向 / 深度正确）
    assert result.reached_by_depth == {1: ("b1",), 2: ("r1",)}
    assert result.depth_of == {"c1": 0, "b1": 1, "r1": 2}
    assert result.downstream == ("b1", "r1")

    # 复用 propagate_retraction → recheck 入队（不新建第二套键）
    assert result.recheck_targets == ("b1", "r1")
    assert len(result.created_task_ids) == 2
    assert result.rolled_back_companies == ("CO1",)

    # 真源已追加（append-only）：recheck 任务 + 研究深度回退行；主张保留
    from schema.models import Task
    from schema.store import read_records

    tasks = [Task.model_validate(r) for r in read_records(code_root, "tasks")]
    rechecks = [t for t in tasks if t.task_type.value == "recheck"]
    assert len(rechecks) == 2
    assert all(t.status.value == "queued" for t in rechecks)
    assert all(t.parent_context.get("reason") == "dependency_stale" for t in rechecks)

    companies = read_records(code_root, "companies")
    latest = max(companies, key=lambda r: r.get("recorded_seq") or 0)
    assert latest["research_depth"] == "baseline_done"
    assert any(r["claim_id"] == "c1" for r in read_records(code_root, "claims"))


def test_retraction_is_idempotent(code_root: Path) -> None:
    seed_retraction_chain(code_root)
    first = retraction_downstream(code_root, "c1", run_date=RUN_DAY, apply=True)
    second = retraction_downstream(code_root, "c1", run_date=RUN_DAY, apply=True)

    assert len(first.created_task_ids) == 2
    assert second.created_task_ids == ()
    assert len(second.skipped_task_ids) == 2
    assert second.rolled_back_companies == ()


# ───────────────────────── AC-03 禁跳级等同：真抛 ─────────────────────────


def test_capex_is_not_revenue_actually_raises(code_root: Path) -> None:
    """★ `Ch7 §B.4`：`capex`（需求侧）≠ 供应商收入 —— 传导在落库前**真抛**。"""
    # ① 直接证明守卫本身真抛（复用 scripts.graph.stage_order）
    with pytest.raises(StageEquivalenceError):
        assert_not_equivalent("capex", "revenue")

    # ② 引擎在编排中调用它 → 违例即抛
    edges = [edge("a", "b", edge_id="e1")]
    fm = fields_map(
        ("e1", fields("b", "e1", from_progress_stage="capex", to_progress_stage="revenue"))
    )
    with pytest.raises(StageEquivalenceError):
        transmit(code_root, "a", params=make_params(), edges=edges, hop_fields=fm)


def test_adjacent_stage_transition_is_allowed(code_root: Path) -> None:
    edges = [edge("a", "b", edge_id="e1")]
    fm = fields_map(
        ("e1", fields("b", "e1", from_progress_stage="order", to_progress_stage="purchase_commitment"))
    )
    result = transmit(code_root, "a", params=make_params(), edges=edges, hop_fields=fm)
    assert len(result.impacts) == 1
    assert result.impacts[0].action == "continue"


# ───────────────────────── AC-04 停止判定与放大上限（门槛由调用方传入） ─────────────────────────


def test_amplification_cap_from_caller(code_root: Path) -> None:
    edges, fm = chain_edges(5)                     # start → n1 → … → n5
    params = make_params(amplification_cap=4.0)    # gain=2.0 → 第 3 跳 8 > 4 命中上限

    result = transmit(code_root, "start", params=params, edges=edges, hop_fields=fm)

    assert [i.action for i in result.impacts] == ["continue", "continue", "stop"]
    capped = result.impacts[-1]
    assert (capped.reason, capped.effect) == ("amplification_capped", "decay")
    assert capped.depth == 3
    # 逐层可达：第 3 跳命中即停，不再深挖
    assert result.impacts_by_depth == {1: ("n1",), 2: ("n2",), 3: ("n3",)}


def test_six_elements_are_emitted(code_root: Path) -> None:
    edges, fm = chain_edges(2)
    params = make_params(amplification_cap=100.0, max_depth=5)
    result = transmit(code_root, "start", params=params, edges=edges, hop_fields=fm)

    assert len(result.impacts) == 2
    imp = result.impacts[0]
    # 六要素（Ch7 §C.1）：variable / direction / magnitude / conditions / counter_forces / time_lag
    assert imp.variable == "demand"
    assert imp.direction == "+"
    assert imp.magnitude == "undisclosed"          # 未披露用保守值（§J5）
    assert imp.conditions == ("cond",)
    assert imp.time_lag == "undisclosed"
    assert isinstance(imp.counter_forces, tuple)
    assert imp.path == ("start", "n1")
    assert imp.idempotency_key == ("start", "n1", "e1", "+")


def test_terminal_demand_dedup_through_engine(code_root: Path) -> None:
    """高扇出共享同一终端需求 → 归因后**只计一次**（`Ch7 §C.4`）。"""
    edges, fm = fanout_edges(3, start="s")
    for eid in list(fm):
        f = fm[eid]
        fm[eid] = fields(f.hop.node_key, eid, relation_id=eid, terminal_demand_id="T")
    result = transmit(code_root, "s", params=make_params(), edges=edges, hop_fields=fm)

    assert len(result.impacts) == 3
    attribution = result.terminal_demand_attribution
    assert attribution is not None
    assert attribution.dedup_saved == 2               # 3 条路径 → 1 个根
    assert len(attribution.allocations) == 1
    shares = attribution.allocations[0].allocated_share
    assert all(abs(v - 1.0 / 3) < 1e-9 for v in shares.values())
