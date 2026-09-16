"""图结构完整性守卫（`Ch2 §B.3`：命中即 `exit 1`）测试 —— AC-04。

`run_gate_inproc` 走的是**与命令行完全相同的 `__main__` 入口**（`tests/conftest.py`），
断言的是**进程退出码**，不是"函数返回了违例列表"。
"""

from __future__ import annotations

from pathlib import Path

from conftest import run_gate_inproc
from schema.models import DependencyEdge
from schema.store import append_records
from scripts.graph.adjacency import build_adjacency_index

GUARD = "scripts/graph/graph_integrity_guard.py"


def _dep(frm: str, to: str, kind: str, edge_id: str) -> DependencyEdge:
    return DependencyEdge(edge_id=edge_id, from_ref=frm, to_ref=to, kind=kind)


def test_clean_tree_exits_zero_with_scanned(code_root: Path) -> None:
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 0, out
    assert "scanned " in out, "守卫必须报 scanned 计数（区分「没扫」与「扫了没问题」）"


def test_self_loop_blocks(code_root: Path) -> None:
    append_records(code_root, "dependency_edges", [_dep("a", "a", "k", "e1")])
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 1, f"自环边应致 exit 1，实得 {code}\n{out}"
    assert "GI-SELF-LOOP" in out


def test_duplicate_edge_blocks(code_root: Path) -> None:
    append_records(
        code_root,
        "dependency_edges",
        [_dep("a", "b", "k", "e1"), _dep("a", "b", "k", "e2")],
    )
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 1, f"重复边应致 exit 1，实得 {code}\n{out}"
    assert "GI-DUP-EDGE" in out


def test_stale_cache_blocks(code_root: Path) -> None:
    build_adjacency_index(code_root)                       # 先建缓存（此时为空）
    append_records(code_root, "dependency_edges", [_dep("a", "b", "k", "e1")])  # 真源变了，缓存未刷新
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 1, f"陈旧缓存应致 exit 1，实得 {code}\n{out}"
    assert "GI-STALE-CACHE" in out


def test_missing_code_root_exits_two() -> None:
    code, out = run_gate_inproc(GUARD, Path("/nonexistent/code_root_for_graph_guard"))
    assert code == 2, f"缺失 code_root 应为输入异常 exit 2，实得 {code}\n{out}"
