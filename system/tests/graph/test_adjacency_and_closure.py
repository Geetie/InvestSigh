"""依赖图遍历 + 邻接表缓存（`Ch9 §3.4.3` / `§3.3.2`）测试。

覆盖 AC-02（可重建）/ AC-05（环 / 自环 / 悬空边）/ AC-06（空 / 超大 / 重复边）。
"""

from __future__ import annotations

import time
from pathlib import Path

from schema.models import DependencyEdge
from schema.store import append_records, read_records
from scripts.graph.adjacency import (
    Edge,
    adjacency_index_path,
    adjacency_matches_facts,
    build_adjacency_index,
    load_all_edges,
)
from scripts.graph.closure import forward_closure, reverse_closure


def _write_dep_edges(code_root: Path, triples: list[tuple[str, str, str]]) -> None:
    rows = [
        DependencyEdge(edge_id=f"e{i}", from_ref=f, to_ref=t, kind=k)
        for i, (f, t, k) in enumerate(triples)
    ]
    append_records(code_root, "dependency_edges", rows)


# ───────────────────────── AC-02 可重建 / 可复现 ─────────────────────────

def test_adjacency_rebuild_is_reproducible(code_root: Path) -> None:
    edges = [("claim:c1", "baseline:b1", "evidence"), ("baseline:b1", "recommendation:r1", "supports")]
    _write_dep_edges(code_root, edges)

    # 第一次：无缓存 → 从 facts 现算闭包
    before = forward_closure(code_root, "claim:c1")

    # 写缓存 → 与真源一致
    idx = build_adjacency_index(code_root)
    assert idx == adjacency_index_path(code_root)
    ok, _detail = adjacency_matches_facts(code_root)
    assert ok is True

    # 删整个 index/ → 重建 → 仍与真源一致；闭包结果逐字段相同
    idx.unlink()
    assert idx.exists() is False
    assert adjacency_matches_facts(code_root)[0] is False  # 缓存缺失 = 不一致（响亮）
    build_adjacency_index(code_root)
    assert adjacency_matches_facts(code_root)[0] is True

    after = forward_closure(code_root, "claim:c1")
    assert before == after
    assert after.reached == ("baseline:b1", "recommendation:r1")
    assert after.depth_of["baseline:b1"] == 1
    assert after.depth_of["recommendation:r1"] == 2


def test_load_all_edges_reads_both_sources(code_root: Path) -> None:
    _write_dep_edges(code_root, [("a", "b", "k")])
    sources = {e.source for e in load_all_edges(code_root)}
    assert sources == {"dependency_edges"}


# ───────────────────────── 遍历正确性（正 / 反向） ─────────────────────────

def test_forward_and_reverse_closure(code_root: Path) -> None:
    _write_dep_edges(
        code_root,
        [("c", "b", "evidence"), ("b", "r", "supports"), ("c", "r2", "evidence")],
    )
    fwd = forward_closure(code_root, "c")
    assert fwd.reached == ("b", "r", "r2")
    rev = reverse_closure(code_root, "r")
    assert rev.reached == ("b", "c")
    assert rev.depth_of["b"] == 1 and rev.depth_of["c"] == 2


def test_max_depth_truncates(code_root: Path) -> None:
    _write_dep_edges(code_root, [("n0", "n1", "k"), ("n1", "n2", "k"), ("n2", "n3", "k")])
    res = forward_closure(code_root, "n0", max_depth=2)
    assert res.reached == ("n1", "n2")
    assert res.truncated is True  # n2 仍有下游 n3 未展开
    res_deep = forward_closure(code_root, "n0", max_depth=10)
    assert res_deep.reached == ("n1", "n2", "n3")
    assert res_deep.truncated is False


# ───────────────────────── AC-05 环 / 自环 / 悬空边 ─────────────────────────

def test_cycle_and_self_loop_do_not_loop(code_root: Path) -> None:
    _write_dep_edges(code_root, [("a", "b", "k"), ("b", "a", "k"), ("b", "b", "k")])
    res = forward_closure(code_root, "a")
    assert res.reached == ("b",)  # start(=a) 不算 reached
    assert res.cycle_detected is True
    assert set(res.cycle_nodes) == {"a", "b"}


def test_dangling_edge_is_recorded_not_raised(code_root: Path) -> None:
    _write_dep_edges(code_root, [("c", "ghost", "k")])
    from scripts.graph.adjacency import object_index

    res = forward_closure(code_root, "c", known_refs=set(object_index(code_root)))
    assert res.reached == ("ghost",)
    assert res.dangling == ("ghost",)


# ───────────────────────── AC-06 边界 ─────────────────────────

def test_empty_graph(code_root: Path) -> None:
    res = forward_closure(code_root, "nothing")
    assert res.reached == ()
    assert res.truncated is False and res.cycle_detected is False


def test_duplicate_edges_are_idempotent(code_root: Path) -> None:
    _write_dep_edges(code_root, [("a", "b", "k"), ("a", "b", "k"), ("a", "b", "k")])
    assert len(load_all_edges(code_root)) == 3   # 真源忠实保留 3 行
    res = forward_closure(code_root, "a")
    assert res.reached == ("b",)                  # 邻接 dict 去重 → 幂等


def test_large_graph_is_linear_no_path_enumeration() -> None:
    # 在内存里造一条 5000 节点长链（不落盘），验证单遍遍历不枚举路径
    n = 5000
    edges = tuple(Edge(f"n{i}", f"n{i+1}", "k", "dependency_edges") for i in range(n))
    t0 = time.monotonic()
    res = forward_closure(Path("/unused"), "n0", edges=edges, max_depth=n + 1)
    elapsed = time.monotonic() - t0
    assert len(res.reached) == n
    assert elapsed < 5.0, f"闭包耗时 {elapsed:.2f}s，疑似非单遍（可能退化）"
