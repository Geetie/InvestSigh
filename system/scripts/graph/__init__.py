"""`scripts/graph/` —— 依赖图与传播层（`Ch9 §3.2.1` 的 **B 边表 schema + C 遍历/失效/入队**）。

本包把「边表（`facts/dependency_edges.jsonl` + `facts/relations.jsonl`）」变成
**可遍历、可失效、可入队**的图能力，是阶段③ `core_chain`（`施工图 §2 阶段③`）的前置。

| 模块 | 能力 | 设计锚点 |
|---|---|---|
| `adjacency` | 边加载 + 可重建邻接表缓存（`index/adjacency.sqlite`，**非真源**） | `Ch7 §C.8` · `Ch9 §3.3.2` |
| `closure`   | 正 / 反向闭包（深度上限 + 环安全，单遍遍历） | `Ch9 §3.4.3` |
| `cycles`    | 环检测 SCC（迭代式 Tarjan）+ 环折叠 | `Ch7 §C.3` |
| `fingerprint` | 事件去重指纹（根来源，非标题）+ `split`/`merge`/`event_alias` | `Ch9 §3.4.7` |
| `stage_order` | 禁跳级等同（`capex` ≠ 订单 / 收入） | `Ch7 §B.4` |
| `stop`      | 停止判定 7 条件 + 累计放大上限 | `Ch7 §C.2 / §C.5` |
| `propagate` | T12 传播（下游失效 → `recheck` 入队 → 研究深度回退） | `Ch9 §3.4.3` |
| `graph_integrity_guard` | 图结构完整性守卫（命中即 `exit 1`） | `Ch2 §B.3` |

★ **惰性导入**（`CONVENTIONS.md §三 P-03` / PEP 562）：包 `__init__` 不在导入期
急切拉起子模块与 pydantic，避免拖慢只读 `__name__` 的轻量调用方。
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "Edge",
    "adjacency_index_path",
    "build_adjacency_index",
    "load_edges",
    "read_adjacency_index",
    "adjacency_matches_facts",
    "object_index",
    "ClosureResult",
    "forward_closure",
    "reverse_closure",
    "DEFAULT_MAX_DEPTH",
    "sccs",
    "strongly_connected",
    "collapse_cycles",
    "has_cycle",
    "event_fingerprint",
    "fingerprint_of_event",
    "event_alias_map",
    "resolve_fingerprint",
    "STAGE_ORDER",
    "assert_not_equivalent",
    "StageEquivalenceError",
    "StopDecision",
    "Hop",
    "PathState",
    "TransmitParams",
    "evidence_gate",
    "should_stop",
    "cumulative_amplification",
    "PropagationResult",
    "propagate_retraction",
]

# 名字 → 定义它的子模块（`scripts.graph.<module>`）。PEP 562：按需导入。
_EXPORTS: dict[str, str] = {
    "Edge": "adjacency",
    "adjacency_index_path": "adjacency",
    "build_adjacency_index": "adjacency",
    "load_edges": "adjacency",
    "read_adjacency_index": "adjacency",
    "adjacency_matches_facts": "adjacency",
    "object_index": "adjacency",
    "ClosureResult": "closure",
    "forward_closure": "closure",
    "reverse_closure": "closure",
    "DEFAULT_MAX_DEPTH": "closure",
    "sccs": "cycles",
    "strongly_connected": "cycles",
    "collapse_cycles": "cycles",
    "has_cycle": "cycles",
    "event_fingerprint": "fingerprint",
    "fingerprint_of_event": "fingerprint",
    "event_alias_map": "fingerprint",
    "resolve_fingerprint": "fingerprint",
    "STAGE_ORDER": "stage_order",
    "assert_not_equivalent": "stage_order",
    "StageEquivalenceError": "stage_order",
    "StopDecision": "stop",
    "Hop": "stop",
    "PathState": "stop",
    "TransmitParams": "stop",
    "evidence_gate": "stop",
    "should_stop": "stop",
    "cumulative_amplification": "stop",
    "PropagationResult": "propagate",
    "propagate_retraction": "propagate",
}


def __getattr__(name: str) -> Any:
    """PEP 562 惰性导出：首次访问某名字时才导入其子模块。"""
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    return getattr(import_module(f"{__name__}.{module}"), name)


def __dir__() -> list[str]:
    return sorted(__all__)
