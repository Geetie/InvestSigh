"""`adjacency.py` —— 边加载 + **可重建邻接表缓存**（`Ch7 §C.8` / `Ch9 §3.3.2`）。

职责（逐字对齐设计）：

- **边表就是真源**：依赖图边 = `facts/dependency_edges.jsonl`（`{from,to,kind}`，
  模型 `DependencyEdge{edge_id,from_ref,to_ref,kind}`，`Ch9 §3.4.3`）；
  传导图的边 = `facts/relations.jsonl`（有向 `subject_id → object_id`，`Ch7 §B.1`）。
  **不引入图数据库**（`Ch9 §3.2`：不用 Neo4j；边表足够）。
- **邻接表缓存 = 可重建索引层**：落 `index/adjacency.sqlite`，**删掉可从 `facts/` 全量重建**，
  **永不作为事实源**（`Ch9 §3.3.2` 三层存储 / `Ch7 §C.8`）。正确性以 `facts/` **现算**为准，
  缓存只用于性能。

★ 本模块**不**去重边：`load_edges` 忠实返回真源里的每一行（含重复边），
  使「缓存 vs 真源」的一致性可逐行核对；重复边的幂等由 `closure` 的邻接 dict 天然承担。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from sqlite3 import connect as _sqlite_connect
from typing import Any, Iterable, Sequence

INDEX_DIRNAME = "index"
ADJACENCY_FILENAME = "adjacency.sqlite"

# 合法边源（= 两张真源边表）
EDGE_SOURCES: tuple[str, ...] = ("dependency_edges", "relations")

# 各 JSONL 的单主键字段名（用于把任意 ref 解析回它所属的对象类型）。
# 来源 = `schema/models.py` 各模型的主键（`Ch9 §2.1.1` 主键设计）。
PRIMARY_KEY_FIELD: dict[str, str] = {
    "industry_nodes": "node_id",
    "companies": "company_id",
    "securities": "security_id",
    "products": "product_id",
    "relations": "relation_id",
    "sources": "source_id",
    "claims": "claim_id",
    "claim_propagation": "propagation_id",
    "events": "event_id",
    "impacts": "impact_id",
    "baselines": "baseline_id",
    "prices": "snapshot_id",
    "expectations": "sample_id",
    "benchmarks": "benchmark_id",
    "recommendations": "recommendation_id",
    "tasks": "task_id",
    "dependency_edges": "edge_id",
}


@dataclass(frozen=True)
class Edge:
    """一条有向边。`source` ∈ `EDGE_SOURCES`，标明它来自哪张真源边表。"""

    from_ref: str
    to_ref: str
    kind: str
    source: str
    edge_id: str = ""


def adjacency_index_path(code_root: str | Path) -> Path:
    """邻接表缓存路径：`<code_root>/index/adjacency.sqlite`（**可重建，非真源**）。"""
    return Path(code_root) / INDEX_DIRNAME / ADJACENCY_FILENAME


def _parse_dt(value: Any) -> datetime | None:
    """把 ISO 字符串解析为 `datetime`；`None` 原样返回。

    非 `None` 但不可解析 → **响亮失败**（`ValueError`）：不静默置 `None` ——
    否则"时间字段损坏"会被错当成"该时间字段缺席"（`CONVENTIONS.md §二 G-01` 不静默）。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"时间字段不是合法 ISO 字符串: {text!r}") from exc


def load_edges(
    code_root: str | Path,
    source: str = "dependency_edges",
    *,
    valid_asof: datetime | None = None,
) -> tuple[Edge, ...]:
    """从 `facts/` **现算**读边（正确性口径，`Ch7 §C.8`）。

    - `source="dependency_edges"`：读 `{from_ref,to_ref,kind}`。
    - `source="relations"`：读有向 `subject_id → object_id`（`kind=relation_type`）；
      给 `valid_asof` 时按有效期过滤（`Ch9 §N9.1-08`：已结束的历史合作不参与当前传导）。

    返回**忠实于真源**的边序列（不去重），按 `(from_ref,to_ref,kind,source,edge_id)` 升序，
    保证可复现。未知 `source` → `ValueError`（不静默返回空）。
    """
    # 延迟导入：只在真正读盘时拉起 store（P-03 惰性精神）
    from schema.store import read_records

    if source not in EDGE_SOURCES:
        raise ValueError(f"未知边源: {source!r}；合法值 {EDGE_SOURCES}")

    rows = read_records(code_root, source)
    edges: list[Edge] = []
    if source == "dependency_edges":
        for row in rows:
            edges.append(
                Edge(
                    from_ref=str(row.get("from_ref", "")),
                    to_ref=str(row.get("to_ref", "")),
                    kind=str(row.get("kind", "")),
                    source="dependency_edges",
                    edge_id=str(row.get("edge_id", "")),
                )
            )
    else:  # relations
        for row in rows:
            if valid_asof is not None:
                valid_from = _parse_dt(row.get("valid_from"))
                valid_to = _parse_dt(row.get("valid_to"))
                if valid_from is not None and valid_from > valid_asof:
                    continue
                if valid_to is not None and valid_to <= valid_asof:
                    continue
            edges.append(
                Edge(
                    from_ref=str(row.get("subject_id", "")),
                    to_ref=str(row.get("object_id", "")),
                    kind=str(row.get("relation_type", "")),
                    source="relations",
                    edge_id=str(row.get("relation_id", "")),
                )
            )
    edges.sort(key=lambda e: (e.from_ref, e.to_ref, e.kind, e.source, e.edge_id))
    return tuple(edges)


def load_all_edges(code_root: str | Path) -> tuple[Edge, ...]:
    """两张真源边表的并集（用于缓存全量重建与一致性核对）。"""
    both = list(load_edges(code_root, "dependency_edges")) + list(load_edges(code_root, "relations"))
    both.sort(key=lambda e: (e.source, e.from_ref, e.to_ref, e.kind, e.edge_id))
    return tuple(both)


def build_adjacency_index(code_root: str | Path, out_path: str | Path | None = None) -> Path:
    """从 `facts/` **全量重建** `index/adjacency.sqlite`（`Ch9 §3.3.2`）。

    缓存**非真源**：删掉整个 `index/` 后调用本函数即可完整重建。
    返回写出的缓存路径。
    """
    target = Path(out_path) if out_path else adjacency_index_path(code_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    edges = load_all_edges(code_root)
    conn = _sqlite_connect(target)
    try:
        conn.execute(
            """
            CREATE TABLE edges (
                source    TEXT NOT NULL,
                from_ref  TEXT NOT NULL,
                to_ref    TEXT NOT NULL,
                kind      TEXT NOT NULL,
                edge_id   TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX ix_edges_from ON edges(source, from_ref)")
        conn.execute("CREATE INDEX ix_edges_to ON edges(source, to_ref)")
        conn.executemany(
            "INSERT INTO edges (source, from_ref, to_ref, kind, edge_id) VALUES (?,?,?,?,?)",
            [(e.source, e.from_ref, e.to_ref, e.kind, e.edge_id) for e in edges],
        )
        conn.commit()
    finally:
        conn.close()
    return target


def read_adjacency_index(
    path: str | Path,
    *,
    source: str | None = None,
) -> tuple[Edge, ...]:
    """从缓存 sqlite 读边（`source=None` 读全部）。

    缓存文件不存在 → **响亮失败**（`FileNotFoundError`），**不静默返回空** ——
    否则"缓存缺失"会被错当成"图里没有边"。
    """
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"邻接表缓存不存在（可重建）: {target}")
    conn = _sqlite_connect(target)
    try:
        if source is None:
            cur = conn.execute("SELECT source, from_ref, to_ref, kind, edge_id FROM edges")
        else:
            cur = conn.execute(
                "SELECT source, from_ref, to_ref, kind, edge_id FROM edges WHERE source = ?",
                (source,),
            )
        edges = [Edge(r[1], r[2], r[3], r[0], r[4]) for r in cur.fetchall()]
    finally:
        conn.close()
    edges.sort(key=lambda e: (e.source, e.from_ref, e.to_ref, e.kind, e.edge_id))
    return tuple(edges)


def _edge_signature(edges: Iterable[Edge]) -> list[tuple[str, str, str, str, str]]:
    return sorted((e.source, e.from_ref, e.to_ref, e.kind, e.edge_id) for e in edges)


def adjacency_matches_facts(code_root: str | Path, *, path: str | Path | None = None) -> tuple[bool, str]:
    """核对缓存与真源是否逐边一致。

    返回 `(是否一致, 说明)`。缓存缺失 → `(False, "缓存缺失…")`（调用方据此判定"陈旧/缺失"）。
    """
    target = Path(path) if path else adjacency_index_path(code_root)
    if not target.exists():
        return False, f"缓存缺失: {target}"
    facts = _edge_signature(load_all_edges(code_root))
    cache = _edge_signature(read_adjacency_index(target))
    if facts == cache:
        return True, f"一致（{len(facts)} 条边）"
    return False, f"不一致：真源 {len(facts)} 条，缓存 {len(cache)} 条"


def object_index(code_root: str | Path) -> dict[str, str]:
    """构建 `ref → JSONL 名` 的对象索引（供传播层判定下游对象类型）。

    只纳入**有单一主键字段**的对象（见 `PRIMARY_KEY_FIELD`）；复合键对象
    （如 `business_positions`）不纳入 —— 它们的成员字段各自可被独立索引。
    未知对象不计入，**不猜测**。
    """
    from schema.store import read_records

    index: dict[str, str] = {}
    for stem, field in PRIMARY_KEY_FIELD.items():
        for row in read_records(code_root, stem):
            ref = row.get(field)
            if ref:
                index[str(ref)] = stem
    return index


def adjacency_from_edges(edges: Sequence[Edge], *, reverse: bool = False) -> dict[str, list[str]]:
    """把边序列折叠成邻接 dict（**重复边天然幂等**，邻接值去重并排序）。

    `reverse=False` → `from → {to}`；`reverse=True` → `to → {from}`。
    空 ref 的边被忽略（不产生噪声节点）。
    """
    adj: dict[str, set[str]] = {}
    for e in edges:
        if not e.from_ref or not e.to_ref:
            continue
        src, dst = (e.to_ref, e.from_ref) if reverse else (e.from_ref, e.to_ref)
        adj.setdefault(src, set()).add(dst)
    return {k: sorted(v) for k, v in adj.items()}
