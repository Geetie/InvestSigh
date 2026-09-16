"""`tests/transmit/` 夹具构造器（`Ch7 §C` 传导形态）。

非 `test_*.py`，不参与批次覆盖扫描；仅供本目录测试复用。

★ 一律在 `code_root` 的**副本**上写入（真仓库 `facts/` 保持为空，不污染真源）。
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

SYSTEM_ROOT = Path(__file__).resolve().parents[2]      # .../InvestSigh/system
if str(SYSTEM_ROOT) not in sys.path:
    sys.path.insert(0, str(SYSTEM_ROOT))

from schema.models import (  # noqa: E402
    Baseline,
    Claim,
    ClaimForm,
    ClaimNature,
    Company,
    DependencyEdge,
    Recommendation,
    RecommendationAction,
    ResearchDepth,
    SourceTier,
)
from schema.store import append_records  # noqa: E402
from scripts.graph.adjacency import Edge  # noqa: E402
from scripts.graph.stop import GAIN_KEY_UNDISCLOSED, Hop, TransmitParams  # noqa: E402
from scripts.transmit.engine import HopFields  # noqa: E402

NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)

#: 一条"全部条件满足"的 hop 的默认字段（供传导用例复用）。
DEFAULT_HOP_KWARGS: dict[str, object] = dict(
    relation_id="rel",
    evidence_claim_ids=("c_ev",),
    variable="demand",
    direction="+",
    conditions=("cond",),
    target_type="",
    importance=1.0,
    forward_forces=2.0,
    counter_forces=1.0,
    terminal_demand_id=None,
    evidence=("e_ev",),
    gain_key=GAIN_KEY_UNDISCLOSED,
)


def make_params(**over: object) -> TransmitParams:
    """构造**调用方显式传入**的传导参数（本模块绝不内置阈值）。"""
    base: dict[str, object] = dict(
        importance_threshold=0.5,
        amplification_cap=4.0,
        gain_map={GAIN_KEY_UNDISCLOSED: 2.0},
        max_depth=5,
    )
    base.update(over)
    return TransmitParams(**base)  # type: ignore[arg-type]


def make_hop(node_key: str, **over: object) -> Hop:
    base = dict(DEFAULT_HOP_KWARGS)
    base["node_key"] = node_key
    base.update(over)
    return Hop(**base)  # type: ignore[arg-type]


def edge(from_ref: str, to_ref: str, *, kind: str = "flow", edge_id: str = "") -> Edge:
    return Edge(from_ref=from_ref, to_ref=to_ref, kind=kind, source="relations", edge_id=edge_id)


def fields(node_key: str, edge_id: str, **over: object) -> HopFields:
    """构造某跳的抽取字段（键 = `edge_id`）。"""
    hop_over = {k: over.pop(k) for k in list(over) if k in DEFAULT_HOP_KWARGS or k == "node_key"}
    hop = make_hop(node_key, **hop_over)
    return HopFields(hop=hop, **over)  # type: ignore[arg-type]


def fields_map(*items: tuple[str, HopFields]) -> dict[str, HopFields]:
    return {edge_id: f for edge_id, f in items}


def dep_edges(triples: Iterable[tuple[str, str, str]]) -> list[DependencyEdge]:
    return [
        DependencyEdge(edge_id=f"e{i}", from_ref=f, to_ref=t, kind=k)
        for i, (f, t, k) in enumerate(triples)
    ]


def seed_retraction_chain(code_root: Path) -> None:
    """`claim:c1 → baseline:b1 → recommendation:r1`，公司 `CO1`（深度 `tracking`）。"""
    append_records(
        code_root,
        "claims",
        [
            Claim(
                claim_id="c1",
                source_id="s1",
                quote_hash="q1",
                claim_nature=ClaimNature.fact,
                claim_form=ClaimForm.original_investigation,
                tier=SourceTier.primary,
                first_seen_at=NOW,
                recorded_seq=1,
            )
        ],
    )
    append_records(
        code_root,
        "baselines",
        [Baseline(baseline_id="b1", company_id="CO1", version=1, business_mechanism="hw")],
    )
    append_records(
        code_root,
        "recommendations",
        [
            Recommendation(
                recommendation_id="r1",
                security_id="SEC1",
                company_id="CO1",
                action=RecommendationAction.buy,
                horizon="2Q",
                start_date=date(2026, 9, 1),
                rule_version="v1",
            )
        ],
    )
    append_records(
        code_root,
        "companies",
        [
            Company(
                company_id="CO1",
                legal_name="Co One",
                research_depth=ResearchDepth.tracking,
                recorded_seq=1,
                first_seen_at=NOW,
            )
        ],
    )
    append_records(
        code_root,
        "dependency_edges",
        dep_edges([("c1", "b1", "evidence"), ("b1", "r1", "supports")]),
    )


def chain_edges(length: int, *, prefix: str = "n") -> tuple[list[Edge], dict[str, HopFields]]:
    """构造 `start → n1 → n2 → … → n{length}` 的边 + 抽取字段（每跳证据唯一）。"""
    edges: list[Edge] = []
    fm: dict[str, HopFields] = {}
    prev = "start"
    for i in range(1, length + 1):
        node = f"{prefix}{i}"
        eid = f"e{i}"
        edges.append(edge(prev, node, edge_id=eid))
        fm[eid] = fields(
            node,
            eid,
            relation_id=eid,
            evidence_claim_ids=(f"c{i}",),
            evidence=(f"e{i}",),
        )
        prev = node
    return edges, fm


def fanout_edges(count: int, *, start: str = "s", prefix: str = "n") -> tuple[list[Edge], dict[str, HopFields]]:
    """构造 1 起点 + `count` 条出边的**高扇出**（单遍、线性）。"""
    edges: list[Edge] = []
    fm: dict[str, HopFields] = {}
    for i in range(count):
        node = f"{prefix}{i}"
        eid = f"e{i}"
        edges.append(edge(start, node, edge_id=eid))
        fm[eid] = fields(node, eid, relation_id=eid, evidence_claim_ids=(f"c{i}",), evidence=(f"e{i}",))
    return edges, fm


def unused_imports_guard() -> None:  # pragma: no cover - 保留占位以避免未用导入告警
    """占位保留：无实际逻辑（避免 `Path` 的未用导入告警）。"""
    return None


__all__ = [
    "DEFAULT_HOP_KWARGS",
    "NOW",
    "chain_edges",
    "dep_edges",
    "edge",
    "fanout_edges",
    "fields",
    "fields_map",
    "make_hop",
    "make_params",
    "seed_retraction_chain",
]
