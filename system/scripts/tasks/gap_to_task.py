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

★ G1-04 的另一半「终态必须有输出」有**两个**合法例外类（`G-64` 收口前只实现了一个）：

| # | 例外类 | 判据 | 谓词 |
|---|---|---|---|
| ① | **无变化日**（`C123-2` / `N7.3-04`：仅变化时产信号、无变化写 `check_record`；`02_实现方案.md:78`：必写 `check_record`） | `check_record.changed is False` | `is_no_change_day()` |
| ② | **本轮降级**（`Ch8 §E`：当日降级 ⇒ 保留上次有效结果、本轮不产新有效结果） | `check_record.degraded is True` | `is_degraded_empty_output()` |

⇒ `done` + 空 `output_refs` **合法当且仅当** `check_record` 存在且（`changed is False` **或**
`degraded is True`）；否则仍按 `G1-04` 判空执行。★★ 此前只认 ① ⇒ **降级轮被误报成空执行**
（`G-64`：假红；实测四态表见 `is_degraded_empty_output()`）。

★ **版本化真源口径**（`Ch9 §3.4.1` / `§3.4.2`）：本守卫逐条判据跑在每个 `task_id` 的
**当前版本**上（`recorded_seq` 最大者，经 `current_task_versions` → `schema.store.as_of` 选取）；
被跳过的历史版本**显式计数**（`scanned["tasks_historical_skipped"]` + `HISTORICAL_VERSIONS_SKIPPED`）。
这是**版本语义**，**不是放宽**：① 逐行判会把"同 `task_id` 的更正版"误判成"幂等键重复（同缺口建了两次单）"；
② 旧版缺 `output_refs` 会被误报空执行。真实重复（同幂等键、**异** `task_id`）去重后仍是两行，照常报警。
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402
from scripts._common import EXIT_INPUT_ERROR, EXIT_OK, EXIT_VIOLATION  # noqa: E402
from schema.store import as_of  # noqa: E402

# ★ 降级判定的**唯一真源**（`G-06`；`G-64` 的修复面）：本文件此前对该模块**零引用**，
#   于是"本轮是否降级"在 `scripts/daily/degrade.py` 与这里**各有一套局部口径**（同族第 3、4 个谓词）。
#   本层**不自己读** `check_record["degraded"]`，一律经此原语。
from scripts.daily.degrade import is_degraded_run_record  # noqa: E402

TASK_TYPES = ("research", "verify", "parse", "recheck", "dedup_override")
STATES = ("queued", "researching", "pending_evidence", "done", "failed")

# 终极态：`done` 是唯一**无出边**的状态（见 `ALLOWED_TRANSITIONS['done'] == []`）。
# 它不是"可以空着收尾"的许可 —— 终态必须有 `output_refs`，否则是空执行。
# ★ 合法例外**有两个**（`G-64` 收口）：① 设计允许的**无变化日**（`is_no_change_day()`）
#   ② **本轮降级**（`is_degraded_empty_output()`，派生自 `daily/degrade.py` 真源）。
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

    ★★ 本函数只承载**两个合法空产出类中的第 ① 类**。合法的 `done` + 空产出**不是只有无变化日**
    —— **本轮降级**同样合法（`Ch8 §E`：降级轮保留上次有效结果、本轮不产新有效结果），
    那一支见 `is_degraded_empty_output()`。
    ⚠️ 本 docstring 曾写"每条 `done` 行**穷尽**落入合法/违例两态、**无第三态**"，并把"合法"等同于
    `changed is False` 一支 —— 该断言**已被 `G-64` 证伪**（降级轮实测 `exit=1` 假红）。
    现行表述：**合法 = ① ∪ ②**（两支互斥性/穷尽性由 `check()` 的**分列计数**机器绑定，
    见 `empty_output_violations` 那一行的恒等式）。

    ★★ 这是**可判定的正向标记**，不是放宽判据（`R-06` ①）：

    - 只认 `check_record.changed is **False**`（**严格同一性**）——
      `changed` **缺失 / `None` / `True` 都不豁免**（缺字段不得被当成"无变化"，否则
      同族缺陷会从"缺字段"这一侧复发：这正是 `G-43` 的教训 —— 判据被一个恒假的谓词空转）。
    - **不依赖任何 id 名单**：只看字段，不看 `task_id`。
    - **判别力不放松**：`changed` 不是 `False`（或压根没有 `check_record`）**且**本轮未降级
      ⇒ **照样按 `G1-04` 红**。
    - **字段全部复用**：`check_record` 由 `pipeline._write_check_record()` 真实写出，
      **不新增真源**（`G-06`）。
    """
    record = row.get("check_record")
    if not isinstance(record, Mapping):
        return False
    return record.get("changed") is False


def is_degraded_empty_output(row: Mapping[str, Any]) -> bool:
    """`done` + 空 `output_refs` 的第 ② 类合法情形：**本轮降级**（`Ch8 §E`）。

    ★ **本函数不含任何字段读取** —— 它整条判据都**派生自唯一真源**
      `scripts/daily/degrade.py::is_degraded_run_record()`（`G-06`）：
      `check_record` 存在 且 `check_record.degraded is True`（严格同一性）。
      换言之它是真源的**薄派生**（"这条行是不是一次降级运行" ⇒ "它的空产出合法"），
      **不是**第 4 个同族局部谓词；两者一致由测试机器绑定
      （`tests/daily/test_no_change_day.py::test_degraded_predicate_is_derived_from_truth_source`）。

    ★ **为什么降级轮的空产出是合法的**：`pipeline._write_check_record()` 对
      `valid_run = not (blocked or degraded)` 为假的行**写空 `output_refs`**
      （`pipeline.py:391/415`），并把有效结果指向 `last_valid_result_ref` ——
      与设计正文一致：`Ch8 §E.1` 共同红线「故障时**保留上次有效结果**并清楚显示日期 + 失效状态；
      **不覆盖为无意义空值**」、`§E.2`「`degraded` | `check_record` | 当日降级运行 = true」、
      `N8.4-05`「故障时旧结果仍在且…`last_valid_result_ref` 指向旧结果」。
      ⚠️ **举证半径如实标出**：「降级轮 `output_refs` 必须为空」这一句**不是设计逐字规定**，
      而是本仓写路径的**语义取舍**（`system/reports/ws_degrade_contract_report.md §④-3`
      已明说"非设计逐字规定"）。本判据与那条取舍**同源**：它不新增要求，
      只是**承认已落地的写路径契约**，从而不再把合法行判成空执行。

    ★★ **为什么必须是这个谓词，而不是几个看起来等价的候选**（`G-64` 四态实测，
    每态一个全新 root，行全部由**真实写路径** `Pipeline._write_check_record` 产出）：

    | 态 | `changed` | `degraded` | `last_valid_result_ref` | 实义 | 修前 → 修后 |
    |---|---|---|---|---|---|
    | A  | False | False | `None`      | 无变化日（合法） | `exit 0` → `exit 0` |
    | B  | True  | True  | `check_…`   | 降级 + 有上次成功（合法） | `exit 1`**假红** → `exit 0` |
    | B2 | True  | True  | **`None`**  | 降级 + 此前无成功运行（合法） | `exit 1`**假红** → `exit 0` |
    | C  | True  | **False** | `None`  | 真违规（空执行） | `exit 1` → `exit 1` |

    - **B2 与 C 在行上字段逐一相同，只有 `degraded` 不同**（`status` / `output_refs` /
      `last_valid_result_ref` / `changed` 全同）⇒ 任何**不看 `degraded`** 的谓词都无法把两者分开。
      特别地，候选 `last_valid_result_ref is not None` **会漏掉 B2**（该字段为 `None`）
      ⇒ 假红只是从 B 挪到 B2（**换个字段复发**，正是 `G-43` 的形状）。故排除该候选。
    - 抗"缺字段复发"同理：只认 `is True`，`degraded` 缺失 / `None` / `1` 都**不**豁免
      （反例见测试 `test_degraded_field_missing_does_not_exempt` 等三条）。
    """
    return is_degraded_run_record(row)


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


def current_task_versions(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], int]:
    """把任务行**收敛到每个 `task_id` 的当前版本**，返回 `(当前版本行, 被跳过的历史版本数)`。

    版本选取的**唯一真源** = `schema.store.as_of`（`Ch9 §3.4.1`："按业务键分组，
    取 `recorded_seq` 最大者"）—— 本函数是它的**薄包装**（`G-06`：**不重造**选取算法、
    不引入第二套口径）。同族先例：`valuelayer/completeness.py::current_baselines()`、
    `delivery/stage_gate.py::_declared_eval_layers()`；
    同一口径的姊妹实现见 `scripts/graph/traceability.py::current_task_versions`
    （两处均为对 `as_of` 的薄包装，选取算法**只有一份**）。

    ★ 为什么必须按 `task_id` 取当前版本：`facts/tasks.jsonl` 是**追加式版本表**
      （`Ch9 §3.4.2`：一次写入即不可改，修正 = **追加**带更大 `recorded_seq` 的新行）。
      于是同一 `task_id` 可以有多行（历史版本 + 当前版本）。**逐行**判会把**历史版本**
      当成独立被检对象 —— 旧版缺 `output_refs` 就会被误报，也会把"同 `task_id` 的版本"
      误判成"幂等键重复（同缺口建了两次单）"（这正是本次修复的成因）。

    ★ **缺 `task_id` 的行不参与分组**（每个自成一个被检对象）—— `as_of` 会把所有缺键行
      并进同一个 `(None,)` 桶、只留一条（**静默丢弃**，违反 `G-03`）。故此处把它们原样放出，
      仍逐条判（不因缺键而漏判，也不因缺键而丢行）。

    ★ **不是放宽**（`R-06` ①）：真实重复仍会被抓到 —— 同一 `idempotency_key` 挂在**两个不同**
      `task_id` 上属**两条独立记录**，去重后两行都在，下面的幂等键去重检查照常报警。
    """
    keyed = [row for row in rows if str(row.get("task_id") or "")]
    unkeyed = [row for row in rows if not str(row.get("task_id") or "")]
    current = list(as_of(keyed, ["task_id"])) + unkeyed
    return current, len(rows) - len(current)


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

    ★★ **第二个**合法例外：**本轮降级**（`Ch8 §E`，`G-64` 补）
      —— `done` + 空产出**不只有无变化日这一支**：降级轮按写路径契约同样"如实为空"
      （有效结果在 `last_valid_result_ref`）。认定方式见 `is_degraded_empty_output()`
      （派生自 `scripts/daily/degrade.py::is_degraded_run_record()`，`G-06`）。
      ⚠️ 本 docstring 曾写"`changed` 不是 `False` ⇒ 照样红"作为**穷尽**表述 ——
      对降级轮**不成立**（实测假红：`G-64`）。每行的归类由 `scanned` 的**分列计数**可见，
      且满足恒等式 `done_empty_output_rows == no_change_day_exempt + degraded_empty_output
      + empty_output_violations`（无第三态、无静默丢弃）。
    """
    report = CheckReport(checker="gap_to_task")
    path = root / "facts" / "tasks.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"缺少真源: {path}")
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    # ★ 版本化真源（`Ch9 §3.4.1` / `§3.4.2`）：同 `task_id` 只判**当前版本**（`recorded_seq` 最大者）。
    #   历史版本**显式计数**（`G-03`），不作为独立被检对象 —— 否则旧版缺产出会假红，
    #   且同 `task_id` 的版本会被误判成"幂等键重复（同缺口建了两次单）"。
    current_rows, historical_skipped = current_task_versions(rows)
    report.scanned["tasks"] = len(current_rows)
    report.scanned["tasks_all_versions"] = len(rows)
    report.scanned["tasks_historical_skipped"] = historical_skipped
    report.scanned["terminal_states"] = len(TERMINAL_STATES)
    if historical_skipped > 0:
        report.notes.append(
            f"HISTORICAL_VERSIONS_SKIPPED: facts/tasks.jsonl 共 {len(rows)} 行，"
            f"其中 {historical_skipped} 行为同 `task_id` 的旧版本；"
            "本次只判各 `task_id` 的当前版本（追加式版本表，历史版本供 as-of 回看："
            "`Ch9 §3.4.1` / `§3.4.2`）"
        )

    seen: dict[str, str] = {}
    # ★ 配对计数（`G-43` 的教训）：只看"豁免 0 条"**无法区分**"没有这类行"与"判据恒假"。
    #   故把"落进该形状的行数"与"其中被豁免的行数"**成对**报出。
    # ★★ 并且**按例外类分列**（`G-64`）：单一豁免计数器下"合法降级"与"真违规"都记 0
    #   ⇒ 两个不同事实在同一观测通道上等价（`G-62`）。
    done_empty_output_rows = 0
    no_change_day_exempt = 0
    degraded_empty_output = 0
    empty_output_violations = 0
    for row in current_rows:
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
        #   **两个**合法例外（`G-64`：此前只实现了一个 ⇒ 降级轮被误报空执行）：
        #   ① 设计允许的**无变化日**（`C123-2` / `N7.3-04`："仅变化时产信号、无变化写 check_record"）；
        #   ② **本轮降级**（`Ch8 §E`：降级轮保留上次有效结果，本轮的 `output_refs` 如实为空）。
        #   ★ 这是把一刀切换成**可判定的正向标记**，**不是放松**：两支都不成立照样红。
        if status in TERMINAL_STATES and not (row.get("output_refs") or []):
            done_empty_output_rows += 1
            # ★ 顺序 = **降级优先**：`Ch8 §E` 的降级是"本轮结果不完整"的**更强**理由
            #   （它强制本轮产出为空，与 `changed` 无关）；两态同时成立时归入降级列。
            #   该优先级有测试钉住（`test_row_both_degraded_and_no_change_is_counted_as_degraded`）。
            if is_degraded_empty_output(row):
                degraded_empty_output += 1
            elif is_no_change_day(row):
                no_change_day_exempt += 1
            else:
                empty_output_violations += 1
                report.violations.append(
                    Violation(
                        "G1-04",
                        f"{row.get('task_id')} 状态为终态 {status!r} 但 output_refs 为空，"
                        "且不满足两个合法空产出例外（需 `check_record` 存在，且"
                        "`check_record.changed is False`（无变化日）"
                        "或 `check_record.degraded is True`（降级轮））"
                        "（空执行：报了完成却没有产出）",
                        "facts/tasks.jsonl",
                    )
                )
    # ★★ 分列计数（`G-64` 的第二个产物）：单一 `no_change_day_exempt` 计数器下，
    #   **B2（合法降级、无上次成功）与 C（真违规）都记 0** —— 一个合法态与一个违规态
    #   在读数上被完全合并（`G-62`：两个不同事实在同一观测通道上等价）。
    #   故按**例外类分列**，并另报违规数，使下面这条恒等式可判：
    #     done_empty_output_rows == no_change_day_exempt + degraded_empty_output + empty_output_violations
    #   （即"每一行都恰好落进一支"，由 `if/elif/else` 结构性保证 + 测试机器绑定）
    report.scanned["done_empty_output_rows"] = done_empty_output_rows
    report.scanned["no_change_day_exempt"] = no_change_day_exempt
    report.scanned["degraded_empty_output"] = degraded_empty_output
    report.scanned["empty_output_violations"] = empty_output_violations
    if not rows:
        report.notes.append("NO_TASK_DATA：阶段① 真源为空；断言已就绪，阶段③/④ 起作用于真数据")
    return report


if __name__ == "__main__":
    sys.exit(run_checker("gap_to_task.py", check))
