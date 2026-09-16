"""`propagate.py` —— **T12 传播**：下游失效 → `recheck` 入队 → 研究深度回退（`Ch9 §3.4.3`）。

撤回传播流程（`Ch9 §3.4.3` 逐字）：

> 遍历下游 → **追加 stale 标记（不覆盖）** → `baseline` / `recommendation` 入队 `recheck` 任务
> → 研究深度回退

T12 四项验收逐一对齐（`Ch9 §2.3.3`）：

1. 正向可达 —— `forward_closure(claim_id)` 给出所有下游；
2. 自动失效入队 —— 命中下游 `baseline` / `recommendation` 建 `recheck` 任务（`queued`）；
3. 前后版本可重建 —— stale 标记与深度回退均走**追加式真源**（不 UPDATE / DELETE）；
4. 列出依赖建议 —— 结果里带 `downstream_by_kind`，建议/基线可逐条反查。

★ **追加式不可变**（`Ch9 §3.4.2` 纪律 4）：本模块的唯一写路径是 `schema.store.append_records`；
  stale 标记 = 任务行的 `parent_context.reason`（**新行**，不覆盖任何既有行）。
★ 幂等：`recheck` 任务以 `(cause, target)` 建幂等键；命中既有 → 跳过，不重复建单（G1-04）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .adjacency import object_index
from .closure import DEFAULT_MAX_DEPTH, forward_closure

#: 触发 `recheck` 的目标对象类型（`Ch9 §3.4.3`：`baseline` / `recommendation` 入队）。
RECHECK_STEM_TYPES: tuple[str, ...] = ("baselines", "recommendations")

#: 研究深度阶梯（`Ch3 §C.2`；**可回退**，非单调递增，`schema/models.py::ResearchDepth`）。
RESEARCH_DEPTH_LADDER: tuple[str, ...] = (
    "position_listed",
    "relations_verified",
    "baseline_done",
    "tracking",
)

STALE_REASON = "dependency_stale"


@dataclass(frozen=True)
class PropagationResult:
    """一次撤回传播的结果（确定性、可复现）。"""

    retracted_ref: str
    source: str
    apply: bool
    downstream: tuple[str, ...] = ()
    downstream_by_kind: dict[str, tuple[str, ...]] = field(default_factory=dict)
    recheck_targets: tuple[str, ...] = ()
    created_task_ids: tuple[str, ...] = ()
    skipped_task_ids: tuple[str, ...] = ()
    rolled_back_companies: tuple[str, ...] = ()
    truncated: bool = False
    cycle_detected: bool = False
    dangling: tuple[str, ...] = ()
    stale_marks: int = 0


def _idempotency_keys(root: str | Path) -> set[str]:
    from schema.store import read_records

    return {
        str(row.get("idempotency_key"))
        for row in read_records(root, "tasks")
        if row.get("idempotency_key")
    }


def _company_company_id_by_ref(root: str | Path) -> dict[str, str]:
    """把 `baseline_id` / `recommendation_id` 映射到其 `company_id`（受影响公司）。"""
    from schema.store import read_records

    mapping: dict[str, str] = {}
    for stem, id_field in (("baselines", "baseline_id"), ("recommendations", "recommendation_id")):
        for row in read_records(root, stem):
            ref = row.get(id_field)
            company = row.get("company_id")
            if ref and company:
                mapping[str(ref)] = str(company)
    return mapping


def _latest_company_rows(root: str | Path) -> dict[str, dict[str, Any]]:
    """取每个公司的**当前版本**（同 `company_id` 取 `recorded_seq` 最大者）。"""
    from schema.store import read_records

    latest: dict[str, dict[str, Any]] = {}
    for row in read_records(root, "companies"):
        cid = str(row.get("company_id", ""))
        if not cid:
            continue
        prev = latest.get(cid)
        if prev is None or (row.get("recorded_seq") or 0) >= (prev.get("recorded_seq") or 0):
            latest[cid] = row
    return latest


def _rollback_depth_row(row: dict[str, Any], *, cause: str, now: datetime) -> dict[str, Any] | None:
    """生成一条**研究深度回退**的新公司行（append-only）；不需回退 → `None`。

    - 已在最低档（`position_listed`）→ `None`（不无意义降级）。
    - 已因同一 `cause` 回退过 → `None`（幂等，不重复追加）。
    """
    current = str(row.get("research_depth", RESEARCH_DEPTH_LADDER[0]))
    if current not in RESEARCH_DEPTH_LADDER:
        current = RESEARCH_DEPTH_LADDER[0]
    idx = RESEARCH_DEPTH_LADDER.index(current)
    change_log = list(row.get("change_log") or [])
    if any(str(entry.get("cause")) == cause for entry in change_log if isinstance(entry, dict)):
        return None
    if idx == 0:
        return None
    new_row = dict(row)
    new_row["research_depth"] = RESEARCH_DEPTH_LADDER[idx - 1]
    new_row["recorded_seq"] = int(row.get("recorded_seq") or 0) + 1
    new_row["analyzed_at"] = now.isoformat()
    new_row["change_log"] = change_log + [
        {
            "cause": cause,
            "field": "research_depth",
            "from": current,
            "to": RESEARCH_DEPTH_LADDER[idx - 1],
            "anchor": "Ch9 §3.4.3",
            "at": now.isoformat(),
        }
    ]
    return new_row


def propagate_retraction(
    code_root: str | Path,
    retracted_ref: str,
    *,
    source: str = "dependency_edges",
    max_depth: int = DEFAULT_MAX_DEPTH,
    run_date: date | None = None,
    apply: bool = False,
) -> PropagationResult:
    """对一条被撤回 / 被重述的对象做 T12 传播（`Ch9 §3.4.3`）。

    `apply=False`（默认）→ **只计算、不落库**（干跑）；`apply=True` → 追加 `recheck` 任务
    与深度回退行（均走 `append_records`）。
    """
    if not retracted_ref:
        raise ValueError("retracted_ref 必填且非空")

    index = object_index(code_root)
    closure = forward_closure(
        code_root,
        retracted_ref,
        max_depth=max_depth,
        source=source,
        known_refs=set(index) if index else None,
    )

    downstream_by_kind: dict[str, list[str]] = {}
    for ref in closure.reached:
        downstream_by_kind.setdefault(index.get(ref, "unknown"), []).append(ref)

    targets = sorted(
        ref for ref in closure.reached if index.get(ref) in RECHECK_STEM_TYPES
    )

    now = datetime.now(timezone.utc)
    run_day = run_date or now.date()
    existing = _idempotency_keys(code_root)

    from schema.models import Task, TaskStatus, TaskType

    new_tasks: list[Any] = []
    created: list[str] = []
    skipped: list[str] = []
    for target in targets:
        key = f"recheck::{retracted_ref}::{target}"
        if key in existing:
            skipped.append(key)
            continue
        task = Task(
            task_id=f"task_{key}",
            task_type=TaskType.recheck,
            status=TaskStatus.queued,
            idempotency_key=key,
            input_refs=[target, retracted_ref],
            parent_context={
                "reason": STALE_REASON,
                "cause": retracted_ref,
                "anchor": "Ch9 §3.4.3",
                "run_date": run_day.isoformat(),
            },
        )
        new_tasks.append(task)
        created.append(task.task_id)
        existing.add(key)

    # 受影响公司 = 依赖失效基线 / 建议的主体（`Ch9 §3.4.3` T12 ④）
    ref_to_company = _company_company_id_by_ref(code_root)
    affected = sorted({ref_to_company[t] for t in targets if t in ref_to_company})

    rolled: list[str] = []
    rollback_rows: list[dict[str, Any]] = []
    if apply and affected:
        latest = _latest_company_rows(code_root)
        for company_id in affected:
            row = latest.get(company_id)
            if row is None:
                continue
            new_row = _rollback_depth_row(row, cause=retracted_ref, now=now)
            if new_row is None:
                continue
            rollback_rows.append(new_row)
            rolled.append(company_id)

    if apply:
        from schema.store import append_records

        if new_tasks:
            append_records(code_root, "tasks", new_tasks)
        if rollback_rows:
            append_records(code_root, "companies", rollback_rows)

    return PropagationResult(
        retracted_ref=retracted_ref,
        source=source,
        apply=apply,
        downstream=closure.reached,
        downstream_by_kind={k: tuple(sorted(v)) for k, v in sorted(downstream_by_kind.items())},
        recheck_targets=tuple(targets),
        created_task_ids=tuple(created),
        skipped_task_ids=tuple(skipped),
        rolled_back_companies=tuple(rolled),
        truncated=closure.truncated,
        cycle_detected=closure.cycle_detected,
        dangling=closure.dangling,
        stale_marks=len(created),
    )
