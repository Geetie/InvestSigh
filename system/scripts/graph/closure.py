"""`closure.py` —— 依赖图**遍历**（正 / 反向闭包，`Ch9 §3.4.3`）。

设计锚点（逐字）：

- **存储**：`facts/dependency_edges.jsonl`，字段 `{from, to, kind}`。
- **遍历**：
  - `forward_closure(claim_id)` → 该主张的所有**下游对象**（T12 ①：正向可达）；
  - `reverse_closure(recommendation_id)` → 该建议依赖的**全部主张**（T12 ④ 反查）。
- **防护**：设 `max_depth`（硬性安全上限，防无限遍历 / 成本爆炸）+ **环检测**
  （`Ch9 §3.4.3` / `Ch7 §C.3`）。

★ **复杂度 = `O(V + E)` 单遍 BFS**，`visited` 集合同时承担「防环重入」与「去重」，
  **绝不枚举路径**（不做指数级的 `O(b^D)` 枚举；`Ch7 §I.3` 的 Worst-case 评估要求剪枝）。

★ **深度不固定**：`max_depth` 仅作**防御性上限**（`Ch7 §C.3`：深度由重要性动态决定），
  默认 `3`。

  张力登记（`R-04`：不自行裁决设计冲突）：`Ch7 §C.3` 写「`max_depth` … 默认 3」，
  而 `Ch7 §J` 的待明确项 `J3` 建议「硬上限 5」。本模块取 `§C.3` 的逐字默认值 `3`，
  并把 `max_depth` 作为**显式参数**（调用方可覆盖），不把任何阈值固化进逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from .adjacency import Edge, adjacency_from_edges, load_edges
from .cycles import strongly_connected

DEFAULT_MAX_DEPTH = 3


@dataclass(frozen=True)
class ClosureResult:
    """一次闭包遍历的结果（确定性、可复现）。"""

    start: str
    direction: str                                   # "forward" | "reverse"
    depth_of: dict[str, int] = field(default_factory=dict)
    reached: tuple[str, ...] = ()                    # 升序；**不含** start
    reached_by_depth: dict[int, tuple[str, ...]] = field(default_factory=dict)
    truncated: bool = False                          # 命中 max_depth 且仍有未展开的下游
    cycle_detected: bool = False
    cycle_nodes: tuple[str, ...] = ()                # 处于环中的节点（升序）
    dangling: tuple[str, ...] = ()                   # 无法解析到已知对象的远端（升序）

    @property
    def max_reached_depth(self) -> int:
        return max(self.depth_of.values(), default=0)


def _traverse(
    start: str,
    adjacency: dict[str, list[str]],
    *,
    max_depth: int,
    direction: str,
) -> ClosureResult:
    """单遍 BFS。返回不含 `start` 的可达集合与按深度分层。"""
    depth_of: dict[str, int] = {start: 0}
    frontier: list[str] = [start]
    depth = 0
    truncated = False
    while frontier and depth < max_depth:
        next_frontier: list[str] = []
        for node in frontier:
            for nxt in adjacency.get(node, ()):        # 邻接值已排序
                if nxt in depth_of:
                    continue                            # 去重 + 防环重入
                depth_of[nxt] = depth + 1
                next_frontier.append(nxt)
        if depth + 1 == max_depth and any(adjacency.get(n) for n in next_frontier):
            truncated = True                            # 已到上限且仍有下游未展开
        frontier = next_frontier
        depth += 1

    reached = sorted(k for k in depth_of if k != start)
    by_depth: dict[int, list[str]] = {}
    for node in reached:
        by_depth.setdefault(depth_of[node], []).append(node)
    reached_by_depth = {d: tuple(sorted(v)) for d, v in sorted(by_depth.items())}

    # 环检测：只在对**可达子图**上跑 SCC（O(V+E)），不枚举路径
    visited = set(depth_of)
    sub_adj = {n: [s for s in adjacency.get(n, ()) if s in visited] for n in visited}
    cycles = strongly_connected(visited, sub_adj)
    cycle_nodes = tuple(sorted({n for comp in cycles for n in comp}))

    return ClosureResult(
        start=start,
        direction=direction,
        depth_of=dict(depth_of),
        reached=tuple(reached),
        reached_by_depth=reached_by_depth,
        truncated=truncated,
        cycle_detected=bool(cycles),
        cycle_nodes=cycle_nodes,
    )


def _resolve_edges(
    code_root: str | Path,
    source: str,
    edges: Sequence[Edge] | None,
    *,
    valid_asof: datetime | None,
) -> tuple[Edge, ...]:
    if edges is not None:
        return tuple(edges)
    return load_edges(code_root, source, valid_asof=valid_asof)


def _collect_dangling(
    known_refs: set[str] | None,
    edges: Iterable[Edge],
    *,
    reverse: bool,
) -> tuple[str, ...]:
    """收集**悬空**远端：指向 / 来自**无法解析到已知对象**的 ref。

    `known_refs is None`（调用方未提供对象索引）→ 不做此判定，返回空元组 ——
    避免"没有索引"被错当成"全部悬空"（降噪即有效性，`CONVENTIONS.md §二 G-05`）。
    """
    if known_refs is None:
        return ()
    dangling: set[str] = set()
    for e in edges:
        remote = e.from_ref if reverse else e.to_ref
        if remote and remote not in known_refs:
            dangling.add(remote)
    return tuple(sorted(dangling))


def forward_closure(
    code_root: str | Path,
    start: str,
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    source: str = "dependency_edges",
    edges: Sequence[Edge] | None = None,
    known_refs: set[str] | None = None,
    valid_asof: datetime | None = None,
) -> ClosureResult:
    """正向闭包：`start` 的所有下游对象（`Ch9 §3.4.3`）。"""
    if max_depth < 0:
        raise ValueError(f"max_depth 必须 >= 0，实为 {max_depth}")
    edge_seq = _resolve_edges(code_root, source, edges, valid_asof=valid_asof)
    adjacency = adjacency_from_edges(edge_seq, reverse=False)
    result = _traverse(start, adjacency, max_depth=max_depth, direction="forward")
    return _with_dangling(result, known_refs, edge_seq, reverse=False)


def reverse_closure(
    code_root: str | Path,
    start: str,
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    source: str = "dependency_edges",
    edges: Sequence[Edge] | None = None,
    known_refs: set[str] | None = None,
    valid_asof: datetime | None = None,
) -> ClosureResult:
    """反向闭包：`start` 依赖的全部上游对象（`Ch9 §3.4.3` T12 ④ 反查）。"""
    if max_depth < 0:
        raise ValueError(f"max_depth 必须 >= 0，实为 {max_depth}")
    edge_seq = _resolve_edges(code_root, source, edges, valid_asof=valid_asof)
    adjacency = adjacency_from_edges(edge_seq, reverse=True)
    result = _traverse(start, adjacency, max_depth=max_depth, direction="reverse")
    return _with_dangling(result, known_refs, edge_seq, reverse=True)


def _with_dangling(
    result: ClosureResult,
    known_refs: set[str] | None,
    edges: Sequence[Edge],
    *,
    reverse: bool,
) -> ClosureResult:
    dangling = _collect_dangling(known_refs, edges, reverse=reverse)
    if not dangling:
        return result
    return ClosureResult(
        start=result.start,
        direction=result.direction,
        depth_of=result.depth_of,
        reached=result.reached,
        reached_by_depth=result.reached_by_depth,
        truncated=result.truncated,
        cycle_detected=result.cycle_detected,
        cycle_nodes=result.cycle_nodes,
        dangling=dangling,
    )
