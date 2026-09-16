"""终端需求归因测试（`Ch7 §C.4 / §A.6 / J6`；AC-02）。

覆盖：同根归并只计一次；分摊（已知份额按比例 / 未披露均分）；union-find；错误路径；空样本。
"""

from __future__ import annotations

import pytest

from scripts.transmit.demand import (
    DemandPath,
    UnionFind,
    attribute_terminal_demand,
    merge_roots,
)


def _path(pid: str, node: str, terminal: str, *, root: str | None = None, share: float | None = None):
    return DemandPath(
        path_id=pid,
        node_key=node,
        terminal_demand_id=terminal,
        root_demand_entity=root,
        economic_exposure_share=share,
    )


# ───────────────────────── AC-02 同根 → 只计一次（分摊） ─────────────────────────


def test_same_root_counted_once_equal_split() -> None:
    """同一份"AI 训练需求"经三条中间链路 → **只计 1 份**（`Ch7 §C.4` 反例的期望行为）。"""
    paths = [
        _path("p1", "foundry", "t_train"),
        _path("p2", "memory", "t_train"),
        _path("p3", "equipment", "t_train"),
    ]
    attribution = attribute_terminal_demand(paths)

    assert len(attribution.allocations) == 1
    alloc = attribution.allocations[0]
    assert alloc.root_demand_entity == "t_train"
    assert alloc.counted_once is True
    assert alloc.basis == "equal_split"                     # 未披露份额 → 均分（J6）
    assert sum(alloc.allocated_share.values()) == pytest.approx(1.0)
    assert alloc.allocated_share == pytest.approx({"p1": 1 / 3, "p2": 1 / 3, "p3": 1 / 3})
    assert attribution.dedup_saved == 2                     # 3 路径 − 1 根


def test_known_exposure_shares_are_proportional() -> None:
    """已知经济暴露份额 → 按比例（`Ch7 §J6`）。"""
    paths = [
        _path("p1", "a", "t", root="root_x", share=3.0),
        _path("p2", "b", "t", root="root_x", share=1.0),
    ]
    attribution = attribute_terminal_demand(paths)
    alloc = attribution.allocations[0]
    assert alloc.basis == "known_exposure"
    assert alloc.allocated_share == pytest.approx({"p1": 0.75, "p2": 0.25})


def test_mixed_disclosure_falls_back_to_equal_split() -> None:
    """任一条未披露 → 该 root 走均分（保守，不点估计，`Ch7 §J5`）。"""
    paths = [
        _path("p1", "a", "t", root="root_x", share=3.0),
        _path("p2", "b", "t", root="root_x", share=None),
    ]
    allocation = attribute_terminal_demand(paths).allocations[0]
    assert allocation.basis == "equal_split"
    assert allocation.allocated_share == pytest.approx({"p1": 0.5, "p2": 0.5})


def test_distinct_roots_are_not_merged() -> None:
    paths = [
        _path("p1", "a", "t_a", root="root_a"),
        _path("p2", "b", "t_b", root="root_b"),
    ]
    attribution = attribute_terminal_demand(paths)
    assert len(attribution.allocations) == 2
    assert attribution.dedup_saved == 0


# ───────────────────────── union-find 归并（Ch7 §C.4 算法） ─────────────────────────


def test_union_find_merges_same_root_pairs() -> None:
    groups = merge_roots(["t1", "t2", "t3"], [("t1", "t2")])
    assert groups["t1"] == groups["t2"]
    assert groups["t3"] == "t3"
    assert groups["t1"] != groups["t3"]


def test_union_find_is_deterministic() -> None:
    uf = UnionFind(["b", "a", "c"])
    uf.union("c", "b")
    uf.union("b", "a")
    assert uf.find("c") == "a"
    assert uf.groups() == {"a": ("a", "b", "c")}


def test_root_of_mapping_is_used() -> None:
    paths = [_path("p1", "a", "t1"), _path("p2", "b", "t2")]
    attribution = attribute_terminal_demand(paths, root_of={"t1": "ROOT", "t2": "ROOT"})
    assert len(attribution.allocations) == 1
    assert attribution.allocations[0].root_demand_entity == "ROOT"
    assert attribution.dedup_saved == 1


# ───────────────────────── 错误路径 / 边界 ─────────────────────────


def test_duplicate_path_id_raises() -> None:
    paths = [_path("p1", "a", "t"), _path("p1", "b", "t")]
    with pytest.raises(ValueError):
        attribute_terminal_demand(paths)


def test_non_positive_share_raises() -> None:
    with pytest.raises(ValueError):
        attribute_terminal_demand([_path("p1", "a", "t", share=0.0)])


def test_empty_sample_records_note() -> None:
    """空样本必须显式记 note，**不得**当「已验证」（`G-03`）。"""
    attribution = attribute_terminal_demand([])
    assert attribution.allocations == ()
    assert attribution.notes and attribution.notes[0].startswith("NO_DEMAND_PATHS")
