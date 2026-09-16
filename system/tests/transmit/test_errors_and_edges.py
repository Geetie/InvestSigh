"""错误路径与边界测试（`Ch7 §C.2 / §C.3 / §C.6`；AC-05 / AC-06 / AC-07）。

覆盖：环安全（不重入 / 不指数枚举）；四类响亮失败；空边表 note / 单点链 / 高扇出线性 / 重复边幂等。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.graph.stage_order import StageEquivalenceError
from scripts.transmit.engine import retraction_downstream, transmit
from transmit_builders import (
    chain_edges,
    edge,
    fanout_edges,
    fields,
    fields_map,
    make_params,
)


# ───────────────────────── AC-05 环安全 ─────────────────────────


def test_cycle_does_not_reenter_or_enumerate(code_root: Path) -> None:
    edges = [edge("a", "b", edge_id="e1"), edge("b", "a", edge_id="e2")]
    fm = fields_map(("e1", fields("b", "e1", relation_id="e1")), ("e2", fields("a", "e2", relation_id="e2")))
    result = transmit(code_root, "a", params=make_params(), edges=edges, hop_fields=fm)

    # 环不重入：a→b 走一次后，b→a 命中 visited → 不展开；不指数枚举
    assert [i.hop_to for i in result.impacts] == ["b"]
    assert result.cycle_detected is True
    assert result.cycle_nodes == ("a", "b")


def test_self_loop_is_safe(code_root: Path) -> None:
    edges = [edge("a", "a", edge_id="e1")]
    fm = fields_map(("e1", fields("a", "e1", relation_id="e1")))
    result = transmit(code_root, "a", params=make_params(), edges=edges, hop_fields=fm)
    assert result.impacts == ()                 # 自环不重入、不死循环
    assert result.cycle_detected is True


# ───────────────────────── AC-06 四类响亮失败 ─────────────────────────


def test_missing_edge_table_raises(code_root: Path) -> None:
    (code_root / "facts" / "dependency_edges.jsonl").unlink()
    with pytest.raises(FileNotFoundError):
        retraction_downstream(code_root, "c1")


def test_unresolvable_start_ref_raises(code_root: Path) -> None:
    edges = [edge("a", "b", edge_id="e1")]
    fm = fields_map(("e1", fields("b", "e1")))
    with pytest.raises(ValueError):
        transmit(
            code_root,
            "ghost",
            params=make_params(),
            known_refs={"a"},
            edges=edges,
            hop_fields=fm,
        )


def test_params_missing_raises(code_root: Path) -> None:
    """阈值未传且无 `rules/transmission.yaml` → 响亮失败（不静默兜底）。"""
    edges = [edge("a", "b", edge_id="e1")]
    fm = fields_map(("e1", fields("b", "e1")))
    assert not (code_root / "rules" / "transmission.yaml").exists()
    with pytest.raises(FileNotFoundError):
        transmit(code_root, "a", params=None, edges=edges, hop_fields=fm)


def test_stage_equivalence_failure_is_loud(code_root: Path) -> None:
    edges = [edge("a", "b", edge_id="e1")]
    fm = fields_map(
        ("e1", fields("b", "e1", from_progress_stage="capex", to_progress_stage="order"))
    )
    with pytest.raises(StageEquivalenceError):
        transmit(code_root, "a", params=make_params(), edges=edges, hop_fields=fm)


def test_unknown_edge_source_raises(code_root: Path) -> None:
    with pytest.raises(ValueError):
        transmit(code_root, "a", params=make_params(), source="no_such_table")


# ───────────────────────── AC-07 边界 ─────────────────────────


def test_empty_edge_table_records_note(code_root: Path) -> None:
    """`facts/relations.jsonl` 存在但 0 行 → 空样本必须显式记 note（`G-03`）。"""
    result = transmit(code_root, "start", params=make_params(), source="relations")
    assert result.impacts == ()
    assert result.notes and result.notes[0].startswith("EMPTY_EDGE_TABLE")


def test_single_hop_chain(code_root: Path) -> None:
    edges, fm = chain_edges(1)
    result = transmit(code_root, "start", params=make_params(), edges=edges, hop_fields=fm)
    assert len(result.impacts) == 1
    assert result.impacts[0].depth == 1
    assert result.impacts_by_depth == {1: ("n1",)}


def test_high_fanout_is_single_pass_linear(code_root: Path) -> None:
    """高扇出 → **单遍、线性**（N 条出边 → N 条 impact；**不做路径枚举**）。"""
    count = 2000
    edges, fm = fanout_edges(count)
    result = transmit(code_root, "s", params=make_params(), edges=edges, hop_fields=fm)
    assert len(result.impacts) == count
    assert all(i.depth == 1 for i in result.impacts)


def test_duplicate_edges_are_idempotent(code_root: Path) -> None:
    single = [edge("a", "b", edge_id="e1")]
    duplicated = [edge("a", "b", edge_id="e1"), edge("a", "b", edge_id="e2")]
    fm = fields_map(("e1", fields("b", "e1", relation_id="e1")))

    r1 = transmit(code_root, "a", params=make_params(), edges=single, hop_fields=fm)
    r2 = transmit(code_root, "a", params=make_params(), edges=duplicated, hop_fields=fm)
    assert [i.hop_to for i in r1.impacts] == ["b"]
    assert [i.hop_to for i in r2.impacts] == ["b"]


def test_dependency_source_missing_after_unlink(code_root: Path) -> None:
    """边界：`source` 合法但真源缺失 → 响亮失败（区别于「存在但为空」）。"""
    (code_root / "facts" / "dependency_edges.jsonl").unlink()
    with pytest.raises(FileNotFoundError):
        transmit(code_root, "a", params=make_params(), source="dependency_edges")
