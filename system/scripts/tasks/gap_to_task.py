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

★ G1-04 的另一半「终态必须有输出」有一个**设计规定的例外**：**无变化日**
（`C123-2` / `N7.3-04`：仅变化时产信号、无变化写 `check_record`；`02_实现方案.md:78`：必写 `check_record`）
—— `done` + 空 `output_refs` 当且仅当 `check_record.changed is False` 时合法。
详见 `is_no_change_day()`。
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
# ★ 唯一例外：**设计允许的无变化日**（见 `is_no_change_day()`）。
TERMINAL_STATES = ("done",)

BUDGET_EXHAUSTED_STATE = "pending_verification"


def is_no_change_day(row: Mapping[str, Any]) -> bool:
    """`done` + 空 `output_refs` 是否属于**设计允许的无变化日**（`C123-2` / `N7.3-04`）。

    设计正文（逐字）：

    | 出处 | 原文 |
    |---|---|
    | `02_已确认的投资规则/01_需求拆解.md:149`（`C123-2`） | 「**更新 ≠ 信号**：每日维护（采集/核验/复查），仅变化时产信号，**无变化写 `check_record`**」 |
    | `07_产业链传导与股票建议/01_需求拆解.md:51`（`N7.3-04`） | 「**无变化日不产生新信号，仅生成核查记录**」 |
    | `08_产品入口与每日运行/02_实现方案.md:78` | 「每日运行**必写** `check_record`（**无论有无变化**）」 |

    ⇒ 无变化日"报了完成、却没有新产出"是**设计规定的正确行为**：那一轮的产出就是
    **一份核查记录**（`check_record`），不是空执行。

    ★★ 这是**可判定的正向标记**，不是放宽判据（`R-06` ①）：

    - 只认 `check_record.changed is **False**`（**严格同一性**）——
      `changed` **缺失 / `None` / `True` 都不豁免**（缺字段不得被当成"无变化"，否则
      同族缺陷会从"缺字段"这一侧复发：这正是 `G-43` 的教训 —— 判据被一个恒假的谓词空转）。
    - **不依赖任何 id 名单**：每条 `done` 行**穷尽**落入"合法 / 违例"两态，无第三态。
    - **判别力不放松**：`changed` 不是 `False`（或压根没有 `check_record`）⇒ **照样按 `G1-04` 红**。
    - **字段全部复用**：`check_record` 由 `pipeline._write_check_record()` 真实写出，
      **不新增真源**（`G-06`）。
    """
    record = row.get("check_record")
    if not isinstance(record, Mapping):
        return False
    return record.get("changed") is False


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

    ★★ 无变化日例外（`C123-2` / `N7.3-04` / `08_产品入口与每日运行/02_实现方案.md:78`）：
      设计规定"每日运行**必写** `check_record`（无论有无变化）"、"**无变化日不产生新信号**"，
      ⇒ `done` + `output_refs=[]` 在**无变化日**是**正确行为**，不是空执行。
      认定方式见 `is_no_change_day()`：**可判定的正向标记**（`check_record.changed is False`），
      **不是放宽** —— `changed` 不是 `False` 或缺 `check_record` ⇒ **照样红**。
    """
    report = CheckReport(checker="gap_to_task")
    path = root / "facts" / "tasks.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"缺少真源: {path}")
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    report.scanned["tasks"] = len(rows)
    report.scanned["terminal_states"] = len(TERMINAL_STATES)

    seen: dict[str, str] = {}
    # ★ 配对计数（`G-43` 的教训）：只看"豁免 0 条"**无法区分**"没有这类行"与"判据恒假"。
    #   故把"落进该形状的行数"与"其中被豁免的行数"**成对**报出。
    done_empty_output_rows = 0
    no_change_day_exempt = 0
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
        #   唯一合法例外：**设计允许的无变化日**（`C123-2` / `N7.3-04`：
        #   "仅变化时产信号、无变化写 check_record"）⇒ 该日 `done` + 空产出是**正确行为**。
        #   ★ 这是把一刀切换成**可判定的正向标记**，**不是放松**：`changed` 不是 `False`
        #     （或没有 `check_record`）照样红。
        if status in TERMINAL_STATES and not (row.get("output_refs") or []):
            done_empty_output_rows += 1
            if is_no_change_day(row):
                no_change_day_exempt += 1
            else:
                report.violations.append(
                    Violation(
                        "G1-04",
                        f"{row.get('task_id')} 状态为终态 {status!r} 但 output_refs 为空，"
                        "且不满足无变化日豁免"
                        "（需 `check_record` 存在且 `check_record.changed is False`）"
                        "（空执行：报了完成却没有产出）",
                        "facts/tasks.jsonl",
                    )
                )
    report.scanned["done_empty_output_rows"] = done_empty_output_rows
    report.scanned["no_change_day_exempt"] = no_change_day_exempt
    if not rows:
        report.notes.append("NO_TASK_DATA：阶段① 真源为空；断言已就绪，阶段③/④ 起作用于真数据")
    return report


if __name__ == "__main__":
    sys.exit(run_checker("gap_to_task.py", check))
