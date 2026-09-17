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
| **提问任务**（tasks） | ① 每条任务 `status` **在场**（失败/完成可见）；② `input_refs` 逐个**能解析**到已知对象；③ `status == "done"` 的任务必须有非空 `output_refs`（可追溯回写）。★ 判的是每个 `task_id` 的**当前版本**（`recorded_seq` 最大者，见 `current_task_versions`） | `T14`（真研究任务 + 来源回答 + 可追溯回写；失败状态可见）· `Ch8 §C.2` |

★ **不静默**（`G-03`）：空 `relations`/`impacts`/`tasks` **不得**当成"已验证"——
逐项进 `note`（`EMPTY_*`），`scanned` 里给出逐项计数。

★ **版本化真源**（`Ch9 §3.4.1` / `§3.4.2`）：`facts/tasks.jsonl` 是**追加式版本表**，
  同一 `task_id` 可有多行（历史版本 + 当前版本）。提问任务判据**只判当前版本**
  （`recorded_seq` 最大者，经 `schema.store.as_of` 选取）；被跳过的历史版本**显式记账 + 计数**
  （`scanned["tasks_historical_skipped"]` + `HISTORICAL_VERSIONS_SKIPPED` note）—— **不是放宽**
  （真实重复恰好仍逐行报警），见 `current_task_versions` 的说明。

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
from schema.store import as_of  # noqa: E402

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


def current_task_versions(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], int]:
    """把任务行**收敛到每个 `task_id` 的当前版本**，返回 `(当前版本行, 被跳过的历史版本数)`。

    版本选取的**唯一真源** = `schema.store.as_of`（`Ch9 §3.4.1`："按业务键分组，
    取 `recorded_seq` 最大者"）—— 本函数是它的**薄包装**（`G-06`：**不重造**选取算法、
    不引入第二套口径）。同族先例：`valuelayer/completeness.py::current_baselines()`、
    `delivery/stage_gate.py::_declared_eval_layers()`（皆以"追加式版本表取当前版本"为口径）。

    ★ 为什么必须按 `task_id` 取当前版本：`facts/tasks.jsonl` 是**追加式版本表**
      （`Ch9 §3.4.2`：一次写入即不可改，修正 = **追加**带更大 `recorded_seq` 的新行）。
      于是同一 `task_id` 可以有多行（历史版本 + 当前版本）。**逐行**判会把**历史版本**
      当成独立被检对象 —— 旧版缺 `output_refs` 就会被误报（这正是本次修复的成因）。
      口径与真源语义一致：判的是**当前版本**，历史版本供 as-of 回看。

    ★ **缺 `task_id` 的行不参与分组**（每个自成一个被检对象）—— `as_of` 会把所有缺键行
      并进同一个 `(None,)` 桶、只留一条（**静默丢弃**，违反 `G-03`）。故此处把它们原样放出，
      仍逐条判（不因缺键而漏判，也不因缺键而丢行）。

    ★ **不是放宽**（`R-06` ①）：真实重复仍会被抓到 —— 同一 `idempotency_key` 挂在**两个不同**
      `task_id` 上属**两条独立记录**，去重后两行都在，逐行判据照常报警（见 `gap_to_task.check`）。
    """
    keyed = [row for row in rows if str(row.get("task_id") or "")]
    unkeyed = [row for row in rows if not str(row.get("task_id") or "")]
    current = list(as_of(keyed, ["task_id"])) + unkeyed
    return current, len(rows) - len(current)


def task_traceability_violations(
    root: str | Path,
    *,
    tasks: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[list[Violation], dict[str, int]]:
    """提问/研究任务追溯链的违例（T14）。

    `tasks` 显式给出时用其为准（供单测构造 canonical 用例）；否则读 `facts/tasks.jsonl`。

    ★ 逐条判据跑在**当前版本**上（同 `task_id` 取 `recorded_seq` 最大者，见
      `current_task_versions`）；被跳过的历史版本在 `scanned` 里**显式计数**（`G-03`）。
    """
    rows: Sequence[Mapping[str, Any]] = (
        tasks if tasks is not None else read_jsonl(root, "tasks")
    )
    current, skipped = current_task_versions(rows)
    known = known_entities(root)
    v: list[Violation] = []
    file_tasks = "facts/tasks.jsonl"

    for row in current:
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

    return v, {
        "tasks": len(current),
        "tasks_all_versions": len(rows),
        "tasks_historical_skipped": skipped,
    }


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
    if tscanned.get("tasks_historical_skipped", 0) > 0:
        report.notes.append(
            f"HISTORICAL_VERSIONS_SKIPPED: facts/tasks.jsonl 共 {tscanned['tasks_all_versions']} 行，"
            f"其中 {tscanned['tasks_historical_skipped']} 行为同 `task_id` 的旧版本；"
            "本次只判各 `task_id` 的当前版本（追加式版本表，历史版本供 as-of 回看："
            "`Ch9 §3.4.1` / `§3.4.2`）"
        )
    return report


def main(argv: list[str] | None = None) -> int:
    return run_checker("traceability.py", check, argv)


if __name__ == "__main__":
    sys.exit(main())
