#!/usr/bin/env python3
"""`traceability.py` —— **图谱 / 提问任务可追溯**判定（`Ch9 §N9.1-26` · `Ch7 §C.1` · `T14`）。

```
python system/scripts/graph/traceability.py [code_root] [--no-report]
```

## 判据（阶段③ `graph_and_ask_traceable`，`registry/delivery.yaml`）

「图谱/提问任务可追溯」= **两条可判定的追溯链**：

| 链 | 判据（可判定、穷尽） | 依据 |
|---|---|---|
| **图谱**（relations / impacts / relation_flows） | ① 每条关系有 ≥1 条 `evidence_claim_ids` **且**每个引用**能解析**到 `claims` 里的真实 `claim_id`；② 关系两端 `subject_id`/`object_id` 能解析到已知对象；③ 每条 `relation_flow` 的 `relation_id` 能解析到一条关系；④ 每条 `impact` 有 ≥1 条可解析的 `evidence_claim_ids` | `Ch7 §B.1`（无证据关系不进传导，`N7.1-08`）· `Ch7 §B.3`（1 关系 → 0..3 流） |
| **提问任务**（tasks） | ① 每条任务 `status` **在场**（失败/完成可见）；② `input_refs` 逐个**能解析**到已知对象；③ `status == "done"` 的任务必须有非空 `output_refs`（可追溯回写） | `T14`（真研究任务 + 来源回答 + 可追溯回写；失败状态可见）· `Ch8 §C.2` |

★ **不静默**（`G-03`）：空 `relations`/`impacts`/`tasks` **不得**当成"已验证"——
逐项进 `note`（`EMPTY_*`），`scanned` 里给出逐项计数。

★ **事件层不在本判据内**：`impacts.event_id` 指向的 `events` 真源由事件层交付；
本判据只要求 `impact` 的**证据**可解析（`evidence_claim_ids`），不要求 `events.jsonl` 已就绪——
否则"事件层未交付"会被误报成"影响不可追溯"。

退出码（`CONVENTIONS.md §二 G-01`）：`0` 放行 / `1` 命中违例 / `2` 输入异常。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402

FACTS_DIRNAME = "facts"

#: `ref -> 所属 JSONL stem` 的**已知对象主键**（判定"端点/引用能否解析"的唯一依据）。
#: 逐条对应 `schema/models.py` 各模型主键（`Ch9 §2.1.1`）。
KNOWN_KEY_FIELDS: tuple[tuple[str, str], ...] = (
    ("industry_nodes", "node_id"),
    ("companies", "company_id"),
    ("securities", "security_id"),
    ("products", "product_id"),
    ("relations", "relation_id"),
    ("events", "event_id"),
    ("impacts", "impact_id"),
    ("baselines", "baseline_id"),
    ("recommendations", "recommendation_id"),
    ("tasks", "task_id"),
    ("claims", "claim_id"),
    ("sources", "source_id"),
    ("dependency_edges", "edge_id"),
)

#: 图谱关系 / 影响 / 流 / 任务四类真源的显式 note 前缀（空样本，`G-03`）。
EMPTY_GRAPH_NOTE = "EMPTY_GRAPH_SOURCE"
EMPTY_TASK_NOTE = "EMPTY_TASK_SOURCE"

_RULES = {
    "relation_evidence_missing": "GRAPHTRACE-REL-EVID",
    "relation_evidence_unresolved": "GRAPHTRACE-REL-EVID-UNRESOLVED",
    "relation_endpoint_unresolved": "GRAPHTRACE-REL-ENDPOINT",
    "flow_relation_unresolved": "GRAPHTRACE-FLOW-RELATION",
    "impact_evidence_missing": "GRAPHTRACE-IMPACT-EVID",
    "impact_evidence_unresolved": "GRAPHTRACE-IMPACT-EVID-UNRESOLVED",
    "task_status_missing": "ASKTRACE-STATUS",
    "task_input_unresolved": "ASKTRACE-INPUT",
    "task_writeback_missing": "ASKTRACE-WRITEBACK",
}


def read_jsonl(root: str | Path, stem: str) -> list[dict[str, Any]]:
    """读 `facts/<stem>.jsonl`（**宽松 JSONL 读取**，不触发 pydantic 校验）。

    文件不存在 → 返回 `[]`（与 `G-03` 一致：无被检对象由调用方显式记 `note`，
    而不是在这里抛异常）。非法 JSON → **响亮失败**（不静默跳过整行）。
    """
    path = Path(root) / FACTS_DIRNAME / f"{stem}.jsonl"
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            node = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno} 非法 JSON: {exc}") from exc
        if isinstance(node, dict):
            out.append(node)
    return out


def known_entities(root: str | Path) -> set[str]:
    """全仓**可解析对象**的 ref 集合（公司 / 节点 / 产品 / 关系 / 主张 / 基线 / 建议 …）。"""
    known: set[str] = set()
    for stem, field in KNOWN_KEY_FIELDS:
        for row in read_jsonl(root, stem):
            value = row.get(field)
            if value:
                known.add(str(value))
    return known


def _missing_refs(refs: Iterable[Any], known: set[str]) -> list[str]:
    """返回引用里**解析不到**已知对象的项（升序、去重）。"""
    out: set[str] = set()
    for ref in refs:
        text = str(ref)
        if text and text not in known:
            out.add(text)
    return sorted(out)


def graph_traceability_violations(root: str | Path) -> tuple[list[Violation], dict[str, int]]:
    """图谱追溯链的违例（relations / impacts / relation_flows）。"""
    relations = read_jsonl(root, "relations")
    impacts = read_jsonl(root, "impacts")
    flows = read_jsonl(root, "relation_flows")
    claims = {str(r.get("claim_id")) for r in read_jsonl(root, "claims") if r.get("claim_id")}
    known = known_entities(root)
    rel_ids = {str(r.get("relation_id")) for r in relations if r.get("relation_id")}

    v: list[Violation] = []
    file_rel, file_imp, file_flow = (
        "facts/relations.jsonl",
        "facts/impacts.jsonl",
        "facts/relation_flows.jsonl",
    )

    for row in relations:
        rid = row.get("relation_id")
        evidence = list(row.get("evidence_claim_ids") or [])
        if not evidence:
            v.append(
                Violation(
                    _RULES["relation_evidence_missing"],
                    f"关系 {rid} 缺证据引用：无证据关系不进传导（`Ch7 §B.1` / `N7.1-08`）",
                    file_rel,
                )
            )
        else:
            unresolved = _missing_refs(evidence, claims)
            if unresolved:
                v.append(
                    Violation(
                        _RULES["relation_evidence_unresolved"],
                        f"关系 {rid} 的证据 claim_id 不可解析 → {unresolved}"
                        "（引用了不存在的 claim，追溯链断裂）",
                        file_rel,
                    )
                )
        for key in ("subject_id", "object_id"):
            ref = row.get(key)
            if not ref or str(ref) not in known:
                v.append(
                    Violation(
                        _RULES["relation_endpoint_unresolved"],
                        f"关系 {rid} 的端点 {key}={ref!r} 不可解析到已知对象"
                        "（端点粒度须可区分，`Ch7 §B.1` / `N7.1-04`）",
                        file_rel,
                    )
                )

    for row in flows:
        rel = row.get("relation_id")
        if not rel or str(rel) not in rel_ids:
            v.append(
                Violation(
                    _RULES["flow_relation_unresolved"],
                    f"关系流 {row.get('flow_id')} 的 relation_id={rel!r} 不可解析到一条关系"
                    "（1 关系 → 0..3 流，`Ch7 §B.3`）",
                    file_flow,
                )
            )

    for row in impacts:
        iid = row.get("impact_id")
        evidence = list(row.get("evidence_claim_ids") or [])
        if not evidence:
            v.append(
                Violation(
                    _RULES["impact_evidence_missing"],
                    f"影响 {iid} 缺证据引用：六要素须有证据支撑（`Ch7 §C.1`）",
                    file_imp,
                )
            )
        else:
            unresolved = _missing_refs(evidence, claims)
            if unresolved:
                v.append(
                    Violation(
                        _RULES["impact_evidence_unresolved"],
                        f"影响 {iid} 的证据 claim_id 不可解析 → {unresolved}",
                        file_imp,
                    )
                )

    scanned = {
        "relations": len(relations),
        "impacts": len(impacts),
        "relation_flows": len(flows),
        "claims": len(claims),
    }
    return v, scanned


def task_traceability_violations(
    root: str | Path,
    *,
    tasks: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[list[Violation], dict[str, int]]:
    """提问/研究任务追溯链的违例（T14）。

    `tasks` 显式给出时用其为准（供单测构造 canonical 用例）；否则读 `facts/tasks.jsonl`。
    """
    rows: Sequence[Mapping[str, Any]] = (
        tasks if tasks is not None else read_jsonl(root, "tasks")
    )
    known = known_entities(root)
    v: list[Violation] = []
    file_tasks = "facts/tasks.jsonl"

    for row in rows:
        tid = row.get("task_id")
        status = row.get("status")
        if not isinstance(status, str) or not status:
            v.append(
                Violation(
                    _RULES["task_status_missing"],
                    f"任务 {tid} 缺 status：完成/失败状态不可见（`T14`：失败状态可见）",
                    file_tasks,
                )
            )
        unresolved = _missing_refs(list(row.get("input_refs") or []), known)
        if unresolved:
            v.append(
                Violation(
                    _RULES["task_input_unresolved"],
                    f"任务 {tid} 的 input_refs 不可解析 → {unresolved}"
                    "（研究任务须可追溯到对象，`T14`）",
                    file_tasks,
                )
            )
        outputs = list(row.get("output_refs") or [])
        if status == "done" and not outputs:
            v.append(
                Violation(
                    _RULES["task_writeback_missing"],
                    f"任务 {tid} 状态为 done 但无 output_refs：可追溯回写缺失（`T14`）",
                    file_tasks,
                )
            )

    return v, {"tasks": len(rows)}


def check(root: Path) -> CheckReport:
    """`graph_and_ask_traceable` 判据的**唯一真源**（供 `stage_gate` 复用）。"""
    report = CheckReport(checker="traceability")
    gv, gscanned = graph_traceability_violations(root)
    tv, tscanned = task_traceability_violations(root)
    report.violations += gv + tv
    report.scanned.update(gscanned)
    report.scanned.update(tscanned)
    report.scanned["graph_violations"] = len(gv)
    report.scanned["task_violations"] = len(tv)
    if gscanned["relations"] == 0 and gscanned["impacts"] == 0:
        report.notes.append(
            f"{EMPTY_GRAPH_NOTE}: 图谱真源为空（无被检对象，**不计为已验证**，`G-03`）"
        )
    if tscanned["tasks"] == 0:
        report.notes.append(
            f"{EMPTY_TASK_NOTE}: 任务真源为空（无被检对象，**不计为已验证**，`G-03`）"
        )
    return report


def main(argv: list[str] | None = None) -> int:
    return run_checker("traceability.py", check, argv)


if __name__ == "__main__":
    sys.exit(main())
