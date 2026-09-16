"""阶段③ `core_chain` 验收判据测试（WS-C：`graph_and_ask_traceable` + `t01_t14_all_pass`）。

覆盖任务卡 `03_WS-C` 的 AC：

| AC | 用例 |
|---|---|
| AC-01b 前置产物不再缺失 | `test_core_chain_precondition_no_longer_missing` |
| AC-02 持久化（写→读回→重建 index/ 数据仍在） | `test_relations_persist_across_index_rebuild` |
| AC-03 真接线（每条新真源的消费者） | `test_new_truth_sources_are_consumed_by_criteria` |
| AC-04 判据真拦得住（反例 + 合规对照） | `test_core_chain_graph_and_ask_traceable_blocks_on_dangling_endpoint` · `test_core_chain_t01_t14_all_pass_blocks_on_ledger_drift` |
| AC-05/06 错误路径与边界 | `test_empty_truth_source_degrades_without_crash` · `test_flow_to_missing_relation_is_rejected` · `test_cycle_and_depth_limit_are_bounded_not_hang` |
| AC-08 设计对齐（权威锚点 + 机器绑定 + 14/14） | `test_t01_t14_ledger_authority_and_machine_binding` |

★ 判据反例（AC-04）两条的**函数名含判据 id**，并被登记进
`registry/criterion_counterexamples.yaml`（由 `criterion_effectiveness_guard` 的 AST 核对强制）。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from conftest import run_gate, run_gate_inproc

GATE = "scripts/delivery/stage_gate.py"
LEDGER = "registry/acceptance_input_set.yaml"

_NODES = (
    "node_manufacturing_and_memory__tsm",
    "node_compute_chip_and_system__nvda",
    "node_manufacturing_and_memory__mu",
)
_CLAIMS = ("claim-ws-c-a", "claim-ws-c-b")
_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


# ─────────────────────────── 夹具：最小一致的真源图 ───────────────────────────


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def _rel(rid: str, subj: str, obj: str, evidence: tuple[str, ...]) -> dict:
    """一条 `Relation` 的完整字段（模型 `extra="forbid"`，故字段集合必须精确）。"""
    return {
        "relation_id": rid,
        "subject_id": subj,
        "subject_kind": "company",
        "object_id": obj,
        "object_kind": "company",
        "related_product_id": None,
        "relation_type": "供应采购",
        "relation_progress_stage": "order_confirmed",
        "valid_from": _TS,
        "valid_to": None,
        "economic_exposure": "undisclosed",
        "economic_exposure_disclosure": "undisclosed",
        "economic_exposure_caliber": "tbd",
        "currency": "usd",
        "commitment_kind": "actual",
        "evidence_claim_ids": list(evidence),
    }


def _impact(iid: str, company: str, evidence: tuple[str, ...]) -> dict:
    return {
        "impact_id": iid,
        "event_id": "ev-ws-c",
        "affected_company_id": company,
        "impact_variable": "代工排产 / 出货",
        "direction": "positive",
        "magnitude": "undisclosed",
        "conditions": ["下游需求维持"],
        "counter_forces": ["产能瓶颈"],
        "time_lag": "1 季",
        "path_kind": "direct_relation",
        "evidence_claim_ids": list(evidence),
    }


def _write_relations(root: Path, rows: list[dict]) -> None:
    """走**真实写路径**（`schema.store.append_records`），并保证从空起步。"""
    from schema.models import Relation
    from schema.store import append_records

    (root / "facts" / "relations.jsonl").write_text("", encoding="utf-8")
    append_records(root, "relations", [Relation(**row) for row in rows])


def _seed(
    root: Path,
    *,
    dangling_object: str | None = None,
    flow_relation: str = "rel-ws-c-1",
) -> None:
    """写一份**最小一致**的真源图（多公司 + 有证据 + 端点可解析）。"""
    _write_jsonl(root / "facts" / "industry_nodes.jsonl", [{"node_id": n} for n in _NODES])
    _write_jsonl(root / "facts" / "claims.jsonl", [{"claim_id": c} for c in _CLAIMS])
    _write_relations(
        root,
        [
            _rel("rel-ws-c-1", _NODES[0], dangling_object or _NODES[1], _CLAIMS[:1]),
            _rel("rel-ws-c-2", _NODES[2], _NODES[1], _CLAIMS[1:]),
        ],
    )
    _write_jsonl(
        root / "facts" / "impacts.jsonl", [_impact("imp-ws-c-1", _NODES[0], _CLAIMS[:1])]
    )
    _write_jsonl(
        root / "facts" / "relation_flows.jsonl",
        [
            {
                "flow_id": "flow-ws-c-1",
                "relation_id": flow_relation,
                "flow_kind": "product",
                "from_ref": _NODES[0],
                "to_ref": _NODES[1],
                "product_flow": {"product_id": "tbd", "volume": "undisclosed", "stage": "revenue"},
                "capital_flow": None,
                "demand_signal": None,
                "evidence_claim_ids": _CLAIMS[:1],
            }
        ],
    )


# ─────────────────────────── AC-01b：前置产物不再缺失 ───────────────────────────


def test_core_chain_precondition_no_longer_missing(code_root: Path) -> None:
    """补上 `relations.jsonl` + `impacts.jsonl` 后，阶段③ **不再报前置产物缺失**，且可评估。"""
    _seed(code_root)
    code, out = run_gate_inproc(GATE, code_root, "--stage", "core_chain")
    assert "前置产物尚不存在" not in out, f"前置产物缺失的 FATAL 又出现了\n{out}"
    assert "scanned core_chain.relations: 2" in out, out
    assert "scanned core_chain.impacts: 1" in out, out
    assert code == 0, f"合规的最小一致图应让阶段③ PASS\n{out}"


# ─────────────────────────── AC-04：判据真拦得住（反例 + 对照） ───────────────────────────


def test_core_chain_graph_and_ask_traceable_blocks_on_dangling_endpoint(
    code_root: Path,
) -> None:
    """★ 反例（AC-04）：一条关系指向**不存在的节点** → `GRAPHTRACE-REL-ENDPOINT` → 阶段③ exit 1。

    前置产物齐备（故阶段③ 不因前置缺失而 BLOCKED），判别力来自本判据本身。
    """
    _seed(code_root, dangling_object="node_does_not_exist")
    proc = run_gate(GATE, code_root, "--stage", "core_chain")
    assert proc.returncode == 1, f"端点不可解析应致阶段③ exit 1\n{proc.stdout}"
    assert "GRAPHTRACE-REL-ENDPOINT" in proc.stdout, proc.stdout

    # 合规对照：端点均可解析 → 该 hint 不出现（判别力专属本判据，非别的判据顺带变红）
    _seed(code_root)
    code, out = run_gate_inproc(GATE, code_root, "--stage", "core_chain")
    assert "GRAPHTRACE-REL-ENDPOINT" not in out, out
    assert code == 0, out


def test_core_chain_t01_t14_all_pass_blocks_on_ledger_drift(code_root: Path) -> None:
    """★ 反例（AC-04）：T01–T14 台账权威锚点被篡改 → `ACC-AUTHORITY` → 阶段③ exit 1。

    钉住「T01–T14 的唯一权威表 = `10/01 §2.1`」（`N-01`：`10/02 §I.2` 的指向是错的）。
    """
    import yaml

    _seed(code_root)
    ledger = code_root / LEDGER
    doc = yaml.safe_load(ledger.read_text(encoding="utf-8"))
    doc["authority_anchor"] = "10/02 §I.2"          # ← 篡改成那个**错误**的指向
    ledger.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")

    proc = run_gate(GATE, code_root, "--stage", "core_chain")
    assert proc.returncode == 1, f"权威锚点漂移应致阶段③ exit 1\n{proc.stdout}"
    assert "ACC-AUTHORITY" in proc.stdout, proc.stdout

    # 合规对照：权威锚点正确 → 该 hint 不出现
    doc["authority_anchor"] = "10/01 §2.1"
    ledger.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    code, out = run_gate_inproc(GATE, code_root, "--stage", "core_chain")
    assert "ACC-AUTHORITY" not in out, out
    assert code == 0, out


# ─────────────────────────── AC-03：真接线（谁读它） ───────────────────────────


def test_new_truth_sources_are_consumed_by_criteria(code_root: Path) -> None:
    """三张新真源都有**真实消费者**：`traceability.check` 读它们，`stage_gate` 判据消费其结果。"""
    from scripts.graph.traceability import check as trace_check

    _seed(code_root)
    report = trace_check(code_root)
    assert report.scanned["relations"] == 2, report.scanned
    assert report.scanned["impacts"] == 1, report.scanned
    assert report.scanned["relation_flows"] == 1, report.scanned

    code, out = run_gate_inproc(GATE, code_root, "--stage", "core_chain")
    assert code == 0, out
    # 判据消费 traceability / acceptance 的输出（计数由它们给出）
    assert "scanned core_chain.graph_and_ask_traceable: 0" in out, out
    assert "scanned core_chain.t01_t14_all_pass: 14" in out, out


# ─────────────────────────── AC-02：持久化 ───────────────────────────


def test_relations_persist_across_index_rebuild(code_root: Path) -> None:
    """关系写入 → **读回**一致 → 删 `index/` 全量重建，数据仍在（index 非真源）。"""
    from scripts.graph.adjacency import (
        adjacency_index_path,
        adjacency_matches_facts,
        build_adjacency_index,
        read_adjacency_index,
    )
    from scripts.graph.traceability import read_jsonl

    _seed(code_root)
    written = read_jsonl(code_root, "relations")
    assert {r["relation_id"] for r in written} == {"rel-ws-c-1", "rel-ws-c-2"}

    index = build_adjacency_index(code_root)
    assert index.exists()
    ok, why = adjacency_matches_facts(code_root)
    assert ok, f"重建后缓存与真源不一致：{why}"
    edges = read_adjacency_index(adjacency_index_path(code_root), source="relations")
    assert {(e.from_ref, e.to_ref) for e in edges} == {
        (_NODES[0], _NODES[1]),
        (_NODES[2], _NODES[1]),
    }

    # 删掉整个 index/ 再重建 —— 真源不变、缓存可完整重建
    index.unlink()
    assert not index.exists()
    build_adjacency_index(code_root)
    ok2, why2 = adjacency_matches_facts(code_root)
    assert ok2, f"二次重建后仍应一致：{why2}"
    assert len(read_jsonl(code_root, "relations")) == 2, "index 重建不得触碰真源"


# ─────────────────────────── AC-05/06：错误路径与边界 ───────────────────────────


def test_empty_truth_source_degrades_without_crash(code_root: Path) -> None:
    """空真源 → **显式 note**（`G-03`：无被检对象不得当"已验证"），不崩溃、不冒充通过。"""
    from scripts.graph.traceability import check as trace_check

    report = trace_check(code_root)          # 夹具真源为空
    assert not report.violations, report.violations
    assert any("EMPTY_GRAPH_SOURCE" in n for n in report.notes), report.notes
    assert any("EMPTY_TASK_SOURCE" in n for n in report.notes), report.notes


def test_flow_to_missing_relation_is_rejected(code_root: Path) -> None:
    """`relation_flow.relation_id` 指向**不存在的关系** → 显式 `GRAPHTRACE-FLOW-RELATION`。"""
    from scripts.graph.traceability import check as trace_check

    _seed(code_root, flow_relation="rel-does-not-exist")
    report = trace_check(code_root)
    assert any(v.rule == "GRAPHTRACE-FLOW-RELATION" for v in report.violations), report.violations


def test_cycle_and_depth_limit_are_bounded_not_hang(code_root: Path) -> None:
    """环 / 跳数超上限 → **有界**返回（环检测 + 显式截断），不挂死、不伪造"完整"。"""
    from scripts.graph.adjacency import Edge
    from scripts.graph.closure import forward_closure

    # ① 环：a ⇄ b，max_depth=5 → 有界返回 + 显式报环（不无限遍历）
    cyc = (
        Edge("a", "b", "k", "dependency_edges", "e1"),
        Edge("b", "a", "k", "dependency_edges", "e2"),
    )
    r1 = forward_closure(
        code_root, "a", max_depth=5, source="dependency_edges", edges=cyc, known_refs={"a", "b"}
    )
    assert set(r1.reached) <= {"a", "b"}, r1.reached
    assert r1.cycle_detected and set(r1.cycle_nodes) == {"a", "b"}, r1.cycle_nodes

    # ② 跳数超上限：a→b→c→d→e→f→g，max_depth=5 → truncated 显式为 True（不静默假装到底）
    chain = tuple(
        Edge(n, f"n{i + 1}", "k", "dependency_edges", f"x{i}")
        for i, n in enumerate(["a", "b", "c", "d", "e", "f"])
    )
    r2 = forward_closure(
        code_root, "a", max_depth=5, source="dependency_edges", edges=chain,
        known_refs={f"n{i}" for i in range(7)} | {"a"},
    )
    assert r2.truncated is True, "跳数超硬上限必须显式截断（否则会伪造『完整』）"


# ─────────────────────────── AC-08：设计对齐 ───────────────────────────


def test_t01_t14_ledger_authority_and_machine_binding(code_root: Path) -> None:
    """台账权威锚点 = `10/01 §2.1`；14 条齐备；判定器**机器绑定**；逐条真跑 → 14/14 ✅。"""
    from scripts.graph import acceptance
    from scripts.graph import acceptance_checks as checks

    doc = acceptance.load_ledger(code_root)
    assert doc["authority_anchor"] == "10/01 §2.1", doc.get("authority_anchor")

    rows = acceptance.t_case_rows(code_root)
    assert [r["t_id"] for r in rows] == [f"T{i:02d}" for i in range(1, 15)], rows

    for row in rows:
        assert row["adjudication"] == "programmatic", row["t_id"]
        fn = checks.ADJUDICATORS[row["t_id"]]
        assert row["adjudicator"].endswith(f"::{fn.__name__}"), row["t_id"]
        assert set(checks.ADJUDICATORS) == {f"T{i:02d}" for i in range(1, 15)}

    report = acceptance.t01_t14_check(code_root)
    assert not report.violations, report.violations
    assert report.scanned["t_passed"] == 14, report.scanned
