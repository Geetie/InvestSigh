#!/usr/bin/env python3
"""`graph_integrity_guard.py` —— 依赖图**结构完整性守卫**（命中即 `exit 1`，`Ch2 §B.3`）。

```
python system/scripts/graph/graph_integrity_guard.py [code_root]
```

为什么需要它（设计锚点）：`Ch9 §3.4.3` 要求「从任一主张 / 版本可正向查出所有下游对象」，
`Ch7 §C.3` 要求「有环时冲击只计一次」。**自环 / 重复边 / 悬空端点 / 陈旧缓存**都会让
正向闭包失真或让"缓存"与真源漂移 —— 这是**可判定、可穷尽**的结构缺陷，故适合做守卫。

| 规则 | 判据（可判定） | 依据 |
|---|---|---|
| `GI-EMPTY-ENDPOINT` | `dependency_edges` 行的 `from_ref` / `to_ref` 有空串 | `Ch9 §3.4.3` 正向可达 |
| `GI-SELF-LOOP` | `from_ref == to_ref`（非空） | `Ch7 §C.3`（退化环） |
| `GI-DUP-EDGE` | 同 `(from_ref,to_ref,kind)` 出现多次 | `Ch9 §3.4.3`（幂等键唯一） |
| `GI-DUP-EDGE-ID` | 非空 `edge_id` 重复 | `Ch9 §3.4.3` |
| `GI-STALE-CACHE` | `index/adjacency.sqlite` 存在且与 `facts/` 逐边不一致 | `Ch9 §3.3.2`（索引可重建、非真源） |

退出码（`CONVENTIONS.md §二 G-01`）：`0` 放行 / `1` 阻断 / `2` 输入异常，**不静默**。
★ 空样本必须显式记 `note`（`G-03`：不得把"无被检对象"当"已验证"）。
★ 真源边表**缺失**（文件不存在）→ `FileNotFoundError` → `run_checker` 折算 `exit 2`：
  `Ch9 §3.3.3` 规定 `facts/` 的 JSONL 表集合不得增删改名（数量真源 = `schema/stems.py`），缺失即**结构性违例**，
  与「存在但为空」**不同**（后者记 `NO_EDGE_DATA` note + `exit 0`）。
"""

from __future__ import annotations

from pathlib import Path
from sys import exit as _sys_exit
from sys import path as _sys_path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in _sys_path:
    _sys_path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402
from scripts.graph.adjacency import (  # noqa: E402
    adjacency_index_path,
    adjacency_matches_facts,
    load_edges,
)

EDGE_FILE = "facts/dependency_edges.jsonl"


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="graph_integrity_guard")

    # ★ 真源**缺失**（文件不存在）→ 响亮失败：`Ch9 §3.3.3` 规定 `facts/` 的 JSONL
    #   不得增删改名，缺失即结构性违例，**不得**与「存在但为空」（`G-03` 真空成立）混同。
    from schema.store import TRUTH_MISSING, truth_source_status

    for stem in ("dependency_edges", "relations"):
        if truth_source_status(root, stem) == TRUTH_MISSING:
            raise FileNotFoundError(
                f"facts/{stem}.jsonl 缺失 —— Ch9 §3.3.3 规定 facts/ 下的 JSONL 不得增删改名，"
                "文件缺失即结构性违例（与'存在但 0 行'不同；G-03：不得把'无被检对象'当'已验证'）"
            )

    dep_edges = load_edges(root, "dependency_edges")
    rel_edges = load_edges(root, "relations")
    report.scanned["dependency_edges"] = len(dep_edges)
    report.scanned["relations"] = len(rel_edges)

    seen_pairs: dict[tuple[str, str, str], int] = {}
    seen_ids: dict[str, int] = {}
    for lineno, edge in enumerate(dep_edges, start=1):
        if not edge.from_ref or not edge.to_ref:
            report.violations.append(
                Violation(
                    "GI-EMPTY-ENDPOINT",
                    f"端点为空：from_ref={edge.from_ref!r} to_ref={edge.to_ref!r}",
                    EDGE_FILE,
                    lineno,
                )
            )
        if edge.from_ref and edge.from_ref == edge.to_ref:
            report.violations.append(
                Violation("GI-SELF-LOOP", f"自环边: {edge.from_ref}", EDGE_FILE, lineno)
            )
        pair = (edge.from_ref, edge.to_ref, edge.kind)
        if pair in seen_pairs:
            report.violations.append(
                Violation(
                    "GI-DUP-EDGE",
                    f"重复边 {pair}（首见 L{seen_pairs[pair]}）",
                    EDGE_FILE,
                    lineno,
                )
            )
        else:
            seen_pairs[pair] = lineno
        if edge.edge_id:
            if edge.edge_id in seen_ids:
                report.violations.append(
                    Violation(
                        "GI-DUP-EDGE-ID",
                        f"edge_id 重复: {edge.edge_id}（首见 L{seen_ids[edge.edge_id]}）",
                        EDGE_FILE,
                        lineno,
                    )
                )
            else:
                seen_ids[edge.edge_id] = lineno

    # 邻接表缓存：存在才做一致性核对（缓存非真源，允许缺失）
    cache_path = adjacency_index_path(root)
    report.scanned["cache_present"] = int(cache_path.exists())
    if cache_path.exists():
        ok, detail = adjacency_matches_facts(root)
        if not ok:
            report.violations.append(
                Violation(
                    "GI-STALE-CACHE",
                    f"邻接表缓存与真源不一致（可重建，须重建）: {detail}",
                    "index/adjacency.sqlite",
                )
            )
    else:
        report.notes.append("NO_CACHE：邻接表缓存不存在（可重建，非真源），本次不核一致性")

    if not dep_edges and not rel_edges:
        report.notes.append("NO_EDGE_DATA：两张真源边表均为空；断言已就绪，待真实边数据")
    return report


if __name__ == "__main__":
    _sys_exit(run_checker("graph_integrity_guard.py", check))
