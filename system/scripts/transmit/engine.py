"""`engine.py` —— **传导编排**（`Ch7 §C.1`；`Ch9 §3.4.3`）。

## 引擎契约（`Ch7 §C.1`，逐字对齐）

| 项 | 内容 |
|---|---|
| **输入** | ① 事件或主张（`events`/`claims`）② 起点（公司 / ref）③ `facts/relations` + 边表 ④ `rules/transmission.yaml`（阈值） |
| **输出** | `facts/impacts.jsonl`（每跳**六要素**）+ 路径记录（`impacts.path_ref`）+ 待核验线索（依据不足跳） |
| **幂等键** | `(event_id, hop_from, hop_to, relation_id, direction)` |
| **失败处理** | 关系/证据缺失 → 该跳标 `evidence_insufficient`（**保留不丢弃**）；计算超限 → 收敛衰减并记录；**不静默丢弃** |
| **依赖** | 第六章 `claims`/`claim_propagation`；第九章 `relations`/`graph`/`compute` |

本模块提供两条编排路径：

1. `retraction_downstream(...)` —— **撤回传导**：一次上游撤回 → **逐层可达的下游集合**
   （`Ch9 §3.4.3` 正向可达）+ **复用** `propagate_retraction` 落 `recheck` 任务（**不新建第二套键**）。
2. `transmit(...)` —— **事件/主张 → 逐跳影响**：按 `Ch7 §C.2` 的停止判定逐跳产出六要素
   （`variable / direction / magnitude / conditions / counter_forces / time_lag`），
   并归集**待核验线索**（依据不足跳，保留不丢弃，`§C.6`）。

★ **只编排、不重造**（`纪律 11` / `G-06`）：可达性 / 深度 / 环取自
`scripts.graph.closure.forward_closure`；停止判定调 `scripts.graph.stop.should_stop`；
跳级等同调 `scripts.graph.stage_order.assert_not_equivalent`；入队调
`scripts.graph.propagate.propagate_retraction`。本模块**不复制**上述任何逻辑。

★ **参数不进决策函数**（`施工图 §8 纪律 1` / `P-09`）：阈值由调用方显式传入 `TransmitParams`
或读 `rules/transmission.yaml`（唯一真源，值待冻结）；**本模块不内置任何数值门槛**。

★ **错误路径一律响亮失败**（不静默返回空集 / 默认值）：边表**缺失** → `FileNotFoundError`；
起点 ref **不可解析** → `ValueError`；阈值**未传**且无配置文件 → `FileNotFoundError`；
出现**跳级等同** → `StageEquivalenceError`。空边表（存在但 0 行）→ 返回空结果并**显式记 `note`**
（`CONVENTIONS §二 G-03`：不得当「已验证」）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from schema.store import TRUTH_EMPTY, TRUTH_MISSING, truth_source_status
from scripts.graph.adjacency import (
    EDGE_SOURCES,
    Edge,
    adjacency_from_edges,
    load_edges,
    object_index,
)
from scripts.graph.closure import DEFAULT_MAX_DEPTH, forward_closure
from scripts.graph.propagate import PropagationResult, propagate_retraction
from scripts.graph.stage_order import assert_not_equivalent
from scripts.graph.stop import (
    GAIN_KEY_UNDISCLOSED,
    Hop,
    PathState,
    StopDecision,
    TransmitParams,
    cumulative_amplification,
    load_transmit_params,
    should_stop,
)
from scripts.transmit.demand import (
    DemandAttribution,
    DemandPath,
    attribute_terminal_demand,
)

#: 未披露幅度的**保守值**（`Ch7 §J5`：未披露用保守值，**不点估计**）。
MAGNITUDE_UNDISCLOSED = "undisclosed"

#: 未知时滞的**保守值**（`Ch7 §C.1` 六要素之一；未披露不臆测）。
LAG_UNDISCLOSED = "undisclosed"

#: 空边表的显式 note 前缀（`CONVENTIONS §二 G-03`）。
EMPTY_EDGE_TABLE_NOTE = "EMPTY_EDGE_TABLE"

#: 无下游 / 无传导路径的显式 note 前缀（不得当「已验证无影响」）。
NO_DOWNSTREAM_NOTE = "NO_DOWNSTREAM"
NO_PATH_NOTE = "NO_TRANSMISSION_PATH"

#: 证据不足线索的标记（`Ch7 §C.6`：该跳不成立并进待核验线索队列，**保留不丢弃**）。
EVIDENCE_INSUFFICIENT = "evidence_insufficient"


# ───────────────────────── 输出对象 ─────────────────────────


@dataclass(frozen=True)
class HopFields:
    """**模型抽取**的每跳结构化字段（`Ch7 §C.2`：模型只抽字段，程序判定）。

    - `hop` 承载停止判定（`should_stop`）所需的全部结构化字段；
    - 其余为 `impacts` **六要素**的补充（`Ch7 §C.1` 输出：`magnitude` / `time_lag` / `counter_forces`）；
    - `from_progress_stage` / `to_progress_stage` / `stage_skip_evidence` 用于 `Ch7 §B.4`
      的**禁跳级等同**守卫（`stage_order.assert_not_equivalent`）。
    """

    hop: Hop
    magnitude: str = MAGNITUDE_UNDISCLOSED
    time_lag: str = LAG_UNDISCLOSED
    counter_forces: tuple[str, ...] = ()
    from_progress_stage: str | None = None
    to_progress_stage: str | None = None
    stage_skip_evidence: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class HopImpact:
    """一跳的**影响**（`Ch7 §C.1` 六要素 + 停止判定 + 路径记录）。

    六要素（`Ch7 §C.1` / `§C.6`）：`variable` / `direction` / `magnitude` /
    `conditions` / `counter_forces` / `time_lag`；**缺条件则不成立**（由 `stop.evidence_gate` 判）。
    """

    hop_from: str
    hop_to: str
    relation_id: str | None
    variable: str | None
    direction: str
    magnitude: str
    conditions: tuple[str, ...]
    counter_forces: tuple[str, ...]
    time_lag: str
    evidence_claim_ids: tuple[str, ...]
    action: str                              # "continue" | "stop"
    reason: str | None = None                # 命中停止判定的原因（`Ch7 §C.2`）
    mark: str | None = None                  # 如 evidence_insufficient / direction_doubtful
    effect: str | None = None                # decay / allocate / record_cycle
    depth: int = 0
    path: tuple[str, ...] = ()               # 路径记录（`impacts.path_ref`）
    progress_stage: str | None = None        # `relation_progress_stage`（`Ch7 §B.4`）
    terminal_demand_id: str | None = None
    gain_key: str = GAIN_KEY_UNDISCLOSED

    @property
    def idempotency_key(self) -> tuple[str, str, str | None, str]:
        """幂等键 `(hop_from, hop_to, relation_id, direction)`（`Ch7 §C.1`；
        `event_id` 维度由调用方附加）。"""
        return (self.hop_from, self.hop_to, self.relation_id, self.direction)


@dataclass(frozen=True)
class TransmissionResult:
    """一次传导编排的结果（确定性、可复现）。"""

    start: str
    source: str
    impacts: tuple[HopImpact, ...] = ()
    evidence_insufficient_clues: tuple[HopImpact, ...] = ()
    terminal_demand_attribution: DemandAttribution | None = None
    cycle_detected: bool = False
    cycle_nodes: tuple[str, ...] = ()
    truncated: bool = False
    dangling: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def impacts_by_depth(self) -> dict[int, tuple[str, ...]]:
        """按深度分层的下游目标集合（**逐层可达的下游集合**）。"""
        by_depth: dict[int, list[str]] = {}
        for imp in self.impacts:
            by_depth.setdefault(imp.depth, []).append(imp.hop_to)
        return {d: tuple(sorted(v)) for d, v in sorted(by_depth.items())}


@dataclass(frozen=True)
class LayeredPropagation:
    """**撤回传导**的结果：逐层可达下游集合 + `recheck` 入队（`Ch9 §3.4.3`）。"""

    retracted_ref: str
    source: str
    reached_by_depth: dict[int, tuple[str, ...]] = field(default_factory=dict)
    depth_of: dict[str, int] = field(default_factory=dict)
    downstream: tuple[str, ...] = ()
    recheck_targets: tuple[str, ...] = ()
    created_task_ids: tuple[str, ...] = ()
    skipped_task_ids: tuple[str, ...] = ()
    rolled_back_companies: tuple[str, ...] = ()
    cycle_detected: bool = False
    cycle_nodes: tuple[str, ...] = ()
    dangling: tuple[str, ...] = ()
    truncated: bool = False
    notes: tuple[str, ...] = ()

    @property
    def max_depth(self) -> int:
        """可达下游的**最大深度**（逐层集合的层数）。"""
        return max(self.reached_by_depth, default=0)


# ───────────────────────── 边 / 字段解析（辅助） ─────────────────────────


def _validate_source(source: str) -> None:
    if source not in EDGE_SOURCES:
        raise ValueError(f"未知边源: {source!r}；合法值 {EDGE_SOURCES}")


def _resolve_edges(
    root: str | Path,
    source: str,
    edges: Sequence[Edge] | None,
    *,
    valid_asof: datetime | None,
) -> tuple[tuple[Edge, ...], bool]:
    """解析边序列，返回 `(edges, 是否空边表)`。

    ★ **响亮失败**：边表文件**缺失**（结构性违例）→ `FileNotFoundError`；
      **存在但 0 行** → 返回 `()` 且空标记 `True`（由调用方显式记 `note`，`G-03`）。
    """
    _validate_source(source)
    if edges is not None:
        seq = tuple(edges)
        return seq, len(seq) == 0
    status = truth_source_status(root, source)
    if status == TRUTH_MISSING:
        raise FileNotFoundError(
            f"缺少边表真源: {Path(root) / 'facts' / (source + '.jsonl')}"
            "（结构性违例 → 响亮失败，不静默返回空图）"
        )
    if status == TRUTH_EMPTY:
        return (), True
    return load_edges(root, source, valid_asof=valid_asof), False


def _known_refs(root: str | Path, provided: set[str] | None) -> set[str] | None:
    """对象索引（ref → 存在性）。调用方显式提供优先；否则现算；空索引 → `None`（不作悬空判定）。"""
    if provided is not None:
        return set(provided)
    index = object_index(root)
    return set(index) if index else None


def _edge_field_map(
    edges: Sequence[Edge],
    hop_fields: Mapping[str, HopFields] | None,
) -> dict[tuple[str, str], HopFields]:
    """把 `edge_id → HopFields` 的映射落到 `(from, to) → HopFields`。

    键优先取 `edge_id`；`edge_id` 为空时退化为 `"{from}->{to}"`（文档化的确定性回退）。
    """
    if not hop_fields:
        return {}
    out: dict[tuple[str, str], HopFields] = {}
    for edge in edges:
        if edge.edge_id and edge.edge_id in hop_fields:
            out[(edge.from_ref, edge.to_ref)] = hop_fields[edge.edge_id]
        else:
            fallback = f"{edge.from_ref}->{edge.to_ref}"
            if fallback in hop_fields:
                out[(edge.from_ref, edge.to_ref)] = hop_fields[fallback]
    return out


def _default_hop(node_key: str, edge: Edge) -> Hop:
    """无抽取字段时的**兜底 hop**：证据缺失 → `evidence_gate` 不满足 → 标依据不足（保留）。"""
    return Hop(
        node_key=node_key,
        relation_id=edge.edge_id or None,
        evidence_claim_ids=(),
    )


def _hop_for(
    node_key: str,
    edge: Edge,
    fields: HopFields | None,
) -> Hop:
    """取该跳的 `Hop`；无字段或 `node_key` 不一致 → 兜底（依据不足，而非静默跳过）。"""
    if fields is None:
        return _default_hop(node_key, edge)
    if fields.hop.node_key != node_key:
        raise ValueError(
            f"hop.node_key 与边目标不一致: hop.node_key={fields.hop.node_key!r} "
            f"但边 {edge.from_ref!r}->{edge.to_ref!r}（响亮失败，不静默改写）"
        )
    return fields.hop


def _assert_hop_stage(fields: HopFields | None) -> None:
    """禁跳级等同（`Ch7 §B.4`）：调用**复用**的 `assert_not_equivalent`，违例即抛。"""
    if fields is None:
        return
    if fields.from_progress_stage and fields.to_progress_stage:
        assert_not_equivalent(
            fields.from_progress_stage,
            fields.to_progress_stage,
            evidence=fields.stage_skip_evidence,
        )


def _to_impact(
    hop_from: str,
    hop_to: str,
    hop: Hop,
    fields: HopFields | None,
    decision: StopDecision,
    *,
    depth: int,
    path: tuple[str, ...],
) -> HopImpact:
    magnitude = fields.magnitude if fields is not None else MAGNITUDE_UNDISCLOSED
    time_lag = fields.time_lag if fields is not None else LAG_UNDISCLOSED
    counter_forces = fields.counter_forces if fields is not None else ()
    stage = fields.to_progress_stage if fields is not None else None
    return HopImpact(
        hop_from=hop_from,
        hop_to=hop_to,
        relation_id=hop.relation_id,
        variable=hop.variable,
        direction=hop.direction,
        magnitude=magnitude,
        conditions=tuple(hop.conditions),
        counter_forces=tuple(counter_forces),
        time_lag=time_lag,
        evidence_claim_ids=tuple(hop.evidence_claim_ids),
        action=decision.action,
        reason=decision.reason,
        mark=decision.mark,
        effect=decision.effect,
        depth=depth,
        path=path,
        progress_stage=stage,
        terminal_demand_id=hop.terminal_demand_id,
        gain_key=hop.gain_key,
    )


def _demand_paths(impacts: Sequence[HopImpact]) -> tuple[DemandPath, ...]:
    """从传导结果抽取终端需求路径段，供 `demand.attribute_terminal_demand` 归因。"""
    out: list[DemandPath] = []
    for idx, imp in enumerate(impacts):
        if imp.terminal_demand_id is None:
            continue
        out.append(
            DemandPath(
                path_id=f"p{idx}",
                node_key=imp.hop_to,
                terminal_demand_id=imp.terminal_demand_id,
            )
        )
    return tuple(out)


# ───────────────────────── 编排 ①：撤回传导 ─────────────────────────


def retraction_downstream(
    root: str | Path,
    retracted_ref: str,
    *,
    source: str = "dependency_edges",
    max_depth: int = DEFAULT_MAX_DEPTH,
    run_date: date | None = None,
    apply: bool = False,
) -> LayeredPropagation:
    """一次上游撤回 → **逐层可达下游** + `recheck` 入队（`Ch9 §3.4.3` / `Ch7 §C.1`）。

    - **逐层可达下游**：取 `forward_closure` 的 `reached_by_depth` / `depth_of`（**方向 / 深度正确**）；
    - **入队**：**复用** `propagate_retraction`（`apply=True` 时追加 `recheck` 任务与深度回退行，
      幂等键 `recheck::{retracted_ref}::{target}` —— **不新建第二套键**）。

    ★ 既调用 `forward_closure` 又调用 `propagate_retraction`：后者内部亦算一次闭包，
      但 `PropagationResult` 只暴露**扁平** `downstream`，**逐层集合**须由闭包显式取得。
      这是"复用既有出口 + 补逐层视图"，**非重复实现**。

    `max_depth` 默认取 `scripts.graph.closure.DEFAULT_MAX_DEPTH`（沿用 graph 层文档化默认，
    非本模块自造阈值；调用方可覆盖）。
    """
    if not retracted_ref:
        raise ValueError("retracted_ref 必填且非空")
    _validate_source(source)
    status = truth_source_status(root, source)
    if status == TRUTH_MISSING:
        raise FileNotFoundError(
            f"缺少边表真源: {Path(root) / 'facts' / (source + '.jsonl')}"
            "（结构性违例 → 响亮失败，不静默返回空图）"
        )
    known = _known_refs(root, None)

    closure = forward_closure(
        root, retracted_ref, max_depth=max_depth, source=source, known_refs=known
    )
    propagation: PropagationResult = propagate_retraction(
        root,
        retracted_ref,
        source=source,
        max_depth=max_depth,
        run_date=run_date,
        apply=apply,
    )

    notes: list[str] = []
    if not closure.reached and not closure.cycle_detected:
        notes.append(
            f"{NO_DOWNSTREAM_NOTE}: {retracted_ref!r} 无下游（结果为空；"
            "不得当「已验证无影响」，G-03）"
        )

    return LayeredPropagation(
        retracted_ref=retracted_ref,
        source=source,
        reached_by_depth=dict(closure.reached_by_depth),
        depth_of=dict(closure.depth_of),
        downstream=tuple(closure.reached),
        recheck_targets=tuple(propagation.recheck_targets),
        created_task_ids=tuple(propagation.created_task_ids),
        skipped_task_ids=tuple(propagation.skipped_task_ids),
        rolled_back_companies=tuple(propagation.rolled_back_companies),
        cycle_detected=closure.cycle_detected,
        cycle_nodes=tuple(closure.cycle_nodes),
        dangling=tuple(closure.dangling),
        truncated=closure.truncated,
        notes=tuple(notes),
    )


# ───────────────────────── 编排 ②：事件 / 主张 → 逐跳影响 ─────────────────────────


def transmit(
    root: str | Path,
    start: str,
    *,
    params: TransmitParams | None = None,
    source: str = "relations",
    hop_fields: Mapping[str, HopFields] | None = None,
    edges: Sequence[Edge] | None = None,
    valid_asof: datetime | None = None,
    known_refs: set[str] | None = None,
) -> TransmissionResult:
    """从 `start` 沿边表做**逐跳影响**传导（`Ch7 §C.1 / §C.2 / §C.6`）。

    - **可达性 / 深度 / 环**取自 `forward_closure`（复用）；本函数的遍历只在
      `closure.depth_of` 的**可达集合**内进行、且以 `visited` 保证**不重入**（单遍 `O(V+E)`）；
    - 每跳调 `should_stop`（复用）产出 `continue` / `stop`；`stop` 且 `mark=evidence_insufficient`
      的跳进入**待核验线索**（保留不丢弃）；
    - 每跳的 `variable / direction / magnitude / conditions / counter_forces / time_lag`
      即 `Ch7 §C.1` 的六要素；缺抽取字段的跳走兜底（依据不足），**不静默丢弃**。

    `params=None` → `load_transmit_params(root)` 读 `rules/transmission.yaml`（唯一真源）；
    文件缺失 → **`FileNotFoundError`**（响亮失败，不静默兜底）。
    """
    if not start:
        raise ValueError("start 必填且非空")
    if params is None:
        params = load_transmit_params(root)

    edge_seq, edge_empty = _resolve_edges(root, source, edges, valid_asof=valid_asof)
    explicit_refs = known_refs is not None
    known = _known_refs(root, known_refs)
    if explicit_refs and start not in (known or set()):
        raise ValueError(
            f"起点 ref 不可解析: {start!r}（不在**调用方提供的**对象索引中；"
            "响亮失败，不静默返回空集）"
        )

    if edge_empty:
        return TransmissionResult(
            start=start,
            source=source,
            notes=(
                f"{EMPTY_EDGE_TABLE_NOTE}: 边表 {source}.jsonl 存在但 0 行 —— "
                "空样本，无结论（不得当「已验证」，G-03）",
            ),
        )

    fields_by_edge = _edge_field_map(edge_seq, hop_fields)
    closure = forward_closure(
        root,
        start,
        max_depth=params.max_depth,
        source=source,
        edges=edge_seq,
        known_refs=known,
    )
    adjacency = adjacency_from_edges(edge_seq)              # 复用（重复边天然幂等）
    reachable = set(closure.depth_of)                       # 可达集合（含 start）
    edge_by_pair = {(e.from_ref, e.to_ref): e for e in edge_seq}

    impacts: list[HopImpact] = []
    clues: list[HopImpact] = []

    visited: set[str] = {start}
    path_of: dict[str, tuple[str, ...]] = {start: (start,)}
    evidence_of: dict[str, frozenset[str]] = {start: frozenset()}
    terminals_of: dict[str, frozenset[str]] = {start: frozenset()}
    amp_of: dict[str, float] = {start: 1.0}
    frontier: list[str] = [start]
    depth = 0

    while frontier and depth < params.max_depth:
        next_frontier: list[str] = []
        for node in sorted(frontier):
            for nxt in adjacency.get(node, ()):             # 邻接值已排序
                if nxt not in reachable:                    # 与闭包一致：可达性取自 closure
                    continue
                if nxt in visited:                          # 环安全：不重入（复用闭包语义）
                    continue
                edge = edge_by_pair.get((node, nxt))
                if edge is None:
                    continue
                fields = fields_by_edge.get((node, nxt))
                _assert_hop_stage(fields)                   # 跳级等同守卫（可能抛）
                hop = _hop_for(nxt, edge, fields)
                state = PathState(
                    visited=path_of[node],
                    upstream_evidence=evidence_of[node],
                    counted_terminals=terminals_of[node],
                    cumulative_amplification=amp_of[node],
                )
                decision = should_stop(hop, state, params)  # 复用停止判定（7 条件）
                path = path_of[node] + (nxt,)
                impact = _to_impact(
                    node, nxt, hop, fields, decision, depth=depth + 1, path=path
                )
                impacts.append(impact)
                visited.add(nxt)                            # 单遍：每个节点只判一次
                if decision.action == "continue":
                    path_of[nxt] = path
                    evidence_of[nxt] = evidence_of[node] | frozenset(hop.evidence)
                    if hop.terminal_demand_id is not None:
                        terminals_of[nxt] = terminals_of[node] | frozenset(
                            {hop.terminal_demand_id}
                        )
                    else:
                        terminals_of[nxt] = terminals_of[node]
                    amp_of[nxt] = cumulative_amplification(amp_of[node], hop, params)
                    next_frontier.append(nxt)
                elif decision.mark == EVIDENCE_INSUFFICIENT:
                    clues.append(impact)                    # 依据不足：保留不丢弃（Ch7 §C.6）
        frontier = next_frontier
        depth += 1

    demand_paths = _demand_paths(impacts)
    attribution = attribute_terminal_demand(demand_paths) if demand_paths else None

    notes: list[str] = []
    if not impacts:
        notes.append(
            f"{NO_PATH_NOTE}: 从 {start!r} 出发无可用传导路径"
            "（边表非空但该起点无出边；不得当「已验证无影响」，G-03）"
        )

    return TransmissionResult(
        start=start,
        source=source,
        impacts=tuple(impacts),
        evidence_insufficient_clues=tuple(clues),
        terminal_demand_attribution=attribution,
        cycle_detected=closure.cycle_detected,
        cycle_nodes=tuple(closure.cycle_nodes),
        truncated=closure.truncated,
        dangling=tuple(closure.dangling),
        notes=tuple(notes),
    )


__all__ = [
    "EVIDENCE_INSUFFICIENT",
    "EMPTY_EDGE_TABLE_NOTE",
    "HopFields",
    "HopImpact",
    "LAG_UNDISCLOSED",
    "LayeredPropagation",
    "MAGNITUDE_UNDISCLOSED",
    "NO_DOWNSTREAM_NOTE",
    "NO_PATH_NOTE",
    "TransmissionResult",
    "retraction_downstream",
    "transmit",
]
