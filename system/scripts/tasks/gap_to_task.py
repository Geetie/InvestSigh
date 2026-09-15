#!/usr/bin/env python3
"""`gap_to_task.py` —— **缺口→任务幂等入队**（`Ch1 §C.3` / `§D.2` / G1-04）。

```
python system/scripts/tasks/gap_to_task.py [code_root]
```

契约（与 `Ch1 §C.3` 完全一致）：

| 项 | 定义 |
|---|---|
| 触发条件 | ① `gap` 创建（`gap_type` / `blocking_step` 非空）② `claim.status=pending_verification`（预算到限）③ `research_depth` 未达标但被引用 ④ T12 传播依赖失效 |
| 任务类型 | `research / verify / parse / recheck / dedup_override` |
| **幂等键** | `(gap_id 或 claim_id)` + `task_type` |
| 入队 vs 执行 | **入队无限**（缺口不丢），**执行受预算 cap 约束** |
| 到限动作 | 转 `pending_verification` + 保留可重入任务；**不伪装完成** |
| 状态机 | `queued → researching → pending_evidence → done / failed` |

★ G1-04：同 `gap_id` 建两次同型任务 → **只落 1 条**。
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402
from scripts._common import EXIT_INPUT_ERROR, EXIT_OK, EXIT_VIOLATION  # noqa: E402

TASK_TYPES = ("research", "verify", "parse", "recheck", "dedup_override")
STATES = ("queued", "researching", "pending_evidence", "done", "failed")

# 终极态：`done` 是唯一**无出边**的状态（见 `ALLOWED_TRANSITIONS['done'] == []`）。
# 它不是"可以空着收尾"的许可 —— 终态必须有 `output_refs`，否则是空执行。
TERMINAL_STATES = ("done",)

BUDGET_EXHAUSTED_STATE = "pending_verification"


@dataclass(frozen=True)
class TaskRef:
    task_id: str
    idempotency_key: str
    created: bool          # True = 本次新建；False = 命中既有（幂等返回）
    state: str


def idempotency_key(gap_id: str | None, claim_id: str | None, task_type: str) -> str:
    """幂等键 = `(gap_id 或 claim_id)` + `task_type`（`Ch1 §E`）。"""
    subject = gap_id or claim_id
    if not subject:
        raise ValueError("gap_id 与 claim_id 不能同时为空（缺主体 → 无法建立幂等键）")
    if task_type not in TASK_TYPES:
        raise ValueError(f"未知 task_type: {task_type!r}；合法值 {TASK_TYPES}")
    return f"{task_type}::{subject}"


class IdempotentTaskQueue:
    """入队**永远成功**、执行**受预算 cap 约束**（`Ch1 §D.2` sequence diagram）。"""

    def __init__(self, tasks_path: Path, research_cap: int | None = None):
        self.tasks_path = tasks_path
        self.research_cap = research_cap
        self._existing: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self.tasks_path.parent.mkdir(parents=True, exist_ok=True)
        if self.tasks_path.exists():
            for lineno, raw in enumerate(self.tasks_path.read_text(encoding="utf-8").splitlines(), 1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{self.tasks_path}:{lineno} 非法 JSON: {exc}") from exc
                key = row.get("idempotency_key")
                if not key:
                    raise ValueError(f"{self.tasks_path}:{lineno} 缺 idempotency_key")
                self._existing[key] = row
        self._loaded = True

    def enqueue(self, gap: Mapping[str, Any] | None, claim: Mapping[str, Any] | None, task_type: str) -> TaskRef:
        """幂等入队。命中既有 → 直接返回，**不重复建单**（G1-04）。"""
        self._load()
        gap_id = (gap or {}).get("gap_id")
        claim_id = (claim or {}).get("claim_id")
        key = idempotency_key(gap_id, claim_id, task_type)

        if key in self._existing:
            row = self._existing[key]
            return TaskRef(row["task_id"], key, created=False, state=row.get("status", "queued"))

        task_id = f"task_{abs(hash(key)) % (10 ** 10):010d}"
        state = "queued"
        if self.research_cap is not None and self._running_count() >= self.research_cap:
            # 到限动作：转 pending_verification + 保留可重入任务；**不伪装完成**
            state = BUDGET_EXHAUSTED_STATE

        row = {
            "task_id": task_id,
            "task_type": task_type,
            "status": state if state != BUDGET_EXHAUSTED_STATE else "pending_evidence",
            "idempotency_key": key,
            "gap_id": gap_id,
            "claim_id": claim_id,
            "reentrant": state == BUDGET_EXHAUSTED_STATE,
            "budget_exhausted": state == BUDGET_EXHAUSTED_STATE,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "failure_stage": "tbd",
            "failure_reason": "tbd",
            "last_valid_result_ref": None,
        }
        with open(self.tasks_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        self._existing[key] = row
        return TaskRef(task_id, key, created=True, state=row["status"])

    def _running_count(self) -> int:
        return sum(
            1 for r in self._existing.values() if r.get("status") in ("queued", "researching")
        )


# ── 状态机迁移守卫（`Ch1 §C.3`：queued → researching → pending_evidence → done/failed） ──

ALLOWED_TRANSITIONS = {
    "queued": {"researching", "pending_evidence", "failed"},
    "researching": {"pending_evidence", "done", "failed"},
    "pending_evidence": {"researching", "done", "failed"},
    "done": set(),                 # 终态：不得再改（追加新任务而非改写旧任务）
    "failed": {"researching"},     # 允许重入重试
}


def assert_transition(current: str, target: str) -> None:
    if current not in ALLOWED_TRANSITIONS:
        raise ValueError(f"未知当前状态: {current!r}")
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(
            f"非法状态迁移 {current} → {target}（`Ch1 §C.3` 状态机；不得伪装完成）"
        )


def check(root: Path) -> CheckReport:
    """守卫：真源中每条任务的状态必须合法、幂等键唯一、**终态必须有输出**。

    ★ "终态有输出"此前**只写在 docstring 里、函数体没有实现** ——
      第二轮独立审计把它列为"docstring 声称 vs 代码事实"脱节。
      现在补上：`done` 是唯一终极态（`ALLOWED_TRANSITIONS['done'] == []`），
      它以"产出为空"收尾就是**空执行**（`§6.2 Empty Execution`）。
    """
    report = CheckReport(checker="gap_to_task")
    path = root / "facts" / "tasks.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"缺少真源: {path}")
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    report.scanned["tasks"] = len(rows)
    report.scanned["terminal_states"] = len(TERMINAL_STATES)

    seen: dict[str, str] = {}
    for row in rows:
        key = row.get("idempotency_key", "")
        if key in seen:
            report.violations.append(
                Violation("G1-04", f"幂等键重复（同缺口建了两次单）: {key}", "facts/tasks.jsonl")
            )
        seen[key] = row.get("task_id", "")
        status = row.get("status")
        if status not in STATES:
            report.violations.append(
                Violation("G1-04", f"任务状态非法: {status!r}（合法 {STATES}）", "facts/tasks.jsonl")
            )
        if row.get("budget_exhausted") and status == "done":
            report.violations.append(
                Violation("G1-04", "预算到限的任务不得标 done（**不伪装完成**）", "facts/tasks.jsonl")
            )
        # ★ 终态必须有输出（docstring 曾声称、代码曾缺失）
        if status in TERMINAL_STATES and not (row.get("output_refs") or []):
            report.violations.append(
                Violation(
                    "G1-04",
                    f"{row.get('task_id')} 状态为终态 {status!r} 但 output_refs 为空"
                    "（空执行：报了完成却没有产出）",
                    "facts/tasks.jsonl",
                )
            )
    if not rows:
        report.notes.append("NO_TASK_DATA：阶段① 真源为空；断言已就绪，阶段③/④ 起作用于真数据")
    return report


if __name__ == "__main__":
    sys.exit(run_checker("gap_to_task.py", check))
