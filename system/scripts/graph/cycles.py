"""`cycles.py` —— 环检测 SCC（**迭代式 Tarjan**）与环折叠。

设计（逐字对齐）：

- **算法**：对本事件的传导边集建有向图，跑 **Tarjan SCC**（`Ch7 §C.3`）；
  同 SCC 内的强连通分量视为环。
- **检测到后的动作**：把环**折叠为一个代表节点**，冲击按**代表值（max，非求和）**计入一次，
  回边记 `cycle_collapsed=true` 并丢弃（`Ch7 §C.3` / 裁定 J7）。
- **同 `(node, terminal_demand)` 在一次传导中至多贡献一次**（同节）。
- **复杂度**：`O(V + E)`；**迭代实现**（显式栈）—— 不用递归，避免大图触顶 Python 递归上限
  （`Ch9 §3.4.3` 防护：`max_depth` 兜底成本，SCC 保证符号与计数正确）。**绝不做路径枚举。**

★ 本模块**只**做图算法的确定性判定，不读配置、不碰阈值（不属决策作用域输入）。
"""

from __future__ import annotations

from typing import Iterable, Mapping


def sccs(nodes: Iterable[str], adjacency: Mapping[str, Iterable[str]]) -> list[list[str]]:
    """迭代式 Tarjan：返回全部强连通分量（每个分量内部按字典序排序）。

    `adjacency` 为 `节点 → 后继` 映射；未出现在映射里的节点视为无出边。
    分量顺序按「其最小成员」字典序稳定排序，保证可复现。
    """
    node_set = set(nodes) | set(adjacency.keys())
    for succ in adjacency.values():
        node_set.update(succ)

    order_index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    result: list[list[str]] = []
    counter = 0

    def _succ(node: str) -> list[str]:
        return sorted(set(adjacency.get(node, ())))

    for root in sorted(node_set):
        if root in order_index:
            continue
        # 显式调用栈：每帧 = (节点, 其后继迭代器)
        work: list[tuple[str, list[str], int]] = [(root, _succ(root), 0)]
        order_index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)

        while work:
            node, children, child_ptr = work[-1]
            if child_ptr < len(children):
                child = children[child_ptr]
                work[-1] = (node, children, child_ptr + 1)
                if child not in order_index:
                    order_index[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, _succ(child), 0))
                elif child in on_stack:
                    low[node] = min(low[node], order_index[child])
                continue

            # 该节点的所有后继处理完 → 结算
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == order_index[node]:
                comp: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    comp.append(member)
                    if member == node:
                        break
                result.append(sorted(comp))

    result.sort(key=lambda comp: comp[0])
    return result


def strongly_connected(
    nodes: Iterable[str], adjacency: Mapping[str, Iterable[str]]
) -> list[list[str]]:
    """只返回**真正的环**：分量大小 > 1，或大小为 1 但存在自环（`n → n`）。"""
    out: list[list[str]] = []
    for comp in sccs(nodes, adjacency):
        if len(comp) > 1:
            out.append(comp)
        elif comp and comp[0] in set(adjacency.get(comp[0], ())):
            out.append(comp)  # 自环
    return out


def has_cycle(nodes: Iterable[str], adjacency: Mapping[str, Iterable[str]]) -> bool:
    """图是否含环（含自环）。"""
    return bool(strongly_connected(nodes, adjacency))


def collapse_cycles(adjacency: Mapping[str, Iterable[str]]) -> dict[str, str]:
    """把每个环折叠为一个**代表节点**，返回 `成员 → 代表` 映射。

    代表值取分量内**字典序最大**成员（`Ch7 §C.3` / 裁定 J7：取 max、非求和），
    确定且可复现。非环节点映射到自身（便于调用方统一改写端点）。
    """
    mapping: dict[str, str] = {}
    nodes = set(adjacency.keys())
    for succ in adjacency.values():
        nodes.update(succ)
    for comp in strongly_connected(nodes, adjacency):
        representative = max(comp)
        for member in comp:
            mapping[member] = representative
    for node in nodes:
        mapping.setdefault(node, node)
    return mapping
