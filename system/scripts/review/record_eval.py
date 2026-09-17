"""`scripts/review/record_eval.py` —— **三层复盘记录器**（`Ch10 §C` · `Ch9 §3.3.5 R-29`）。

把一次**三层复盘**结果（研究质量 / 预测质量 / 投资结果）落成 `facts/tasks.jsonl` 上
的 `eval_result` —— **追加式**、可追溯、**禁合并**。

## 三条硬约束（`Ch10 §C`）

1. **三层不可合并**（`N10.3-01`）：**不产生**任何"综合评分 / 单一评分 / 置信度"。
   由 `assert_no_composite_score()` **负向断言**把关 —— **命中即 fail**（`G-01`），禁 warn-only。
2. **append-only**（`Ch9 §3.4.2`）：**只追加新行**；唯一写口 = `schema.store.append_records`
   （**不**自写文件 —— 那会绕过唯一写入口）。
3. **`error_axis` 越界即 fail**（`Ch10 §C.3` / `N10.3-12`）：`set(axis) ⊆ VALID_AXES`（七方向）。

## 字段对齐（`Ch10 §C.1`，与 `schema.models.EvalResult` 严格一致）

| `Ch10 §C.1` 字段 | 落位 | 说明 |
|---|---|---|
| `eval_layer` | `EvalResult.eval_layer` | **新**字段（三层分层） |
| `error_axis` | `EvalResult.error_axis` | **新**字段（七方向，可数组 = 一错跨方向） |
| `error_axis_note` | `EvalResult.error_axis_note` | **新**字段（定位说明） |
| `eval_target_ref` | `Task.parent_context.eval_target_ref` | **复用** Ch9 版本 id 机制 |
| `reason` / `version` | `Task.parent_context.reason` / `.version` | **复用** `Ch2 §E change_log` 口径 |

⇒ 本模块**不改 `schema/`**：`EvalResult` 上的三个新字段与 `Task.eval_result` 载体**均已存在**；
`eval_target_ref` / `reason` / `version` 按设计为**复用**，落在 `Task.parent_context`（不撞名）。

## 命名纪律（`Ch2 §B.2 P-09`）

`score` 属**被禁命名**（`decision_scope_only`）—— 它在本文件里**只**出现在模块级常量
`_COMPOSITE_FIELD_NAMES`（`scripts/review/` **非** `decision` / `graph` 作用域，模块级不触发），
**绝不**进入任何决策 / 排序 / 门槛逻辑。`assert_no_composite_score()` 是**检查器**（负向断言），
其函数体**不含**被禁词字面量。

## 版本更正（追加式，`Ch9 §3.4.2`）

复盘记录**一次写入即不可改**：要更正（例如补齐 `output_refs` 回写）**只能追加一版**，
而不是就地改写历史行。`record_eval(..., new_version=True)` 即该入口：

- **同一 `task_id` / 同一 `idempotency_key`**（同一逻辑复盘），`recorded_seq` **严格递增**
  ⇒ 版本序不倒挂（消费方按 `schema.store.as_of`，即"同业务键取 `recorded_seq` 最大者"取当前版本）；
- `recorded_seq` **必须显式给出且大于该 `task_id` 现有最大值**，否则拒绝
  （见 `_assert_version_monotonic`，与 `scripts/claim/transition.py::_next_recorded_seq` 同纪律）；
- 历史版本**不被删除**（供 as-of 回看）；两者同 `task_id` 共存于追加式真源。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from schema.models import (
    ErrorAxis,
    EvalLayer,
    EvalResult as PersistedEvalResult,
    Task,
    TaskStatus,
    TaskType,
)
from schema.store import append_records, read_records

__all__ = [
    "VALID_LAYERS",
    "VALID_AXES",
    "EvalResult",
    "record_eval",
    "assert_no_composite_score",
    "EvalLayerError",
    "ErrorAxisError",
    "CompositeScoreError",
    "TASK_TYPE",
]

_ROOT = Path(__file__).resolve().parents[2]
"""本模块所在 `system/` 根 —— `record_eval()` 的默认 `code_root`（含 `facts/`）。"""

VALID_LAYERS: frozenset[str] = frozenset(layer.value for layer in EvalLayer)
"""合法层 = `Ch10 §C.1` 三层。

**唯一真源 = `schema.models.EvalLayer`**（此处**派生**而非手抄 —— 防枚举与常量两处漂移，`G-06`）。
"""

VALID_AXES: frozenset[str] = frozenset(axis.value for axis in ErrorAxis)
"""合法错误方向 = `Ch10 §C.3` 七方向。

**唯一真源 = `schema.models.ErrorAxis`**（同样**派生**，不手抄）。
"""

_COMPOSITE_FIELD_NAMES: tuple[str, ...] = ("score", "confidence")
"""三层"合并为单一综合评分"的字段名（`Ch10 §N10.3-01`；`P-09` 禁词同族）。

★ **只**供负向断言 `assert_no_composite_score()` **检测**是否存在这些字段；
  **绝不**参与任何决策 / 排序 / 门槛（它们**只出现在负向断言里**）。
★ 置于**模块作用域**：`scripts/review/` **不是** `decision` / `graph` 决策作用域，
  且 P-09 的 scope 是 `decision_scope_only` ⇒ 模块级 token **不**被 `conflict_scan` 命中。
"""

TASK_TYPE: TaskType = TaskType.verify
"""复盘记录落在 `Task.task_type` 上的取值。

复盘 = 对既有产出的一次**核查**（`Ch1 §C.3` 五态中的 `verify`）；**不**新建 task_type（`G-06`）。
"""


class EvalLayerError(ValueError):
    """非法 `eval_layer` —— 三层**不得新增 / 合并**（`Ch10 §N10.3-01`）。"""


class ErrorAxisError(ValueError):
    """`error_axis` 越界 —— 只允许 `Ch10 §C.3` 七方向（`N10.3-12`）。"""


class CompositeScoreError(RuntimeError):
    """三层被压成单一综合评分 —— **命中即 fail**（`N10.3-01` / `G-01`）。"""


@dataclass(frozen=True)
class EvalResult:
    """三层复盘记录（`Ch10 §C.4`）。**标记对象**：不进决策函数、不参与任何门槛。

    `frozen=True` ⇒ 记录一经构造**不可就地改写** —— 与 append-only 语义一致
    （要改就**追加新版本**，承 `Ch9 §3.4.2`）。
    """

    eval_layer: str
    eval_target_ref: str
    error_axis: list[str]
    error_axis_note: str
    reason: str
    version: str


def assert_no_composite_score(evals: Sequence[object]) -> None:
    """三层不得合并为单一综合评分（`Ch10 §N10.3-01`）。**命中即 fail**（`G-01`），禁 warn-only。

    ★ 本函数是**负向断言**（检测 `score` / `confidence` 是否出现），属"检查器"而非决策函数。
    ★ **反向对照**（`G-05` 要求每条拦截判据都配反例）：空序列 / 合法 `EvalResult`
      **不**触发异常（见 `tests/unit/test_record_eval.py`）——否则合法对象被误伤就是噪声。

    参数 `evals`：任意对象序列；只做 `hasattr` 检测，不假设类型。
    命中 → 抛 `CompositeScoreError`（**不是**返回告警）。
    """
    for e in evals:
        merged = [name for name in _COMPOSITE_FIELD_NAMES if hasattr(e, name)]
        if merged:
            raise CompositeScoreError(
                "N10.3-01：三层被压成综合评分 —— 对象含被禁字段 "
                f"{merged}；三层不可合并（Ch10 §N10.3-01）"
            )


def record_eval(
    layer: str,
    target_ref: str,
    axis: Iterable[str] = (),
    note: str = "",
    reason: str = "",
    version: str = "",
    *,
    code_root: str | Path | None = None,
    task_id: str | None = None,
    task_status: TaskStatus = TaskStatus.done,
    recorded_at: datetime | None = None,
    recorded_seq: int | None = None,
    backfilled_at: datetime | None = None,
    output_refs: Iterable[str] = (),
    new_version: bool = False,
    apply: bool = True,
) -> EvalResult:
    """落一条三层复盘记录（`Ch10 §C.4`）—— **append-only** 追加到 `facts/tasks.jsonl`。

    ★ **事前是硬约束**（`Ch10 §N10.3-03`）：预测质量四项须**早于**判断生效位写入。
      调用方通过 `recorded_at` / `recorded_seq` 表达"事前"写入时点；**事后补入**的记录
      必须给 `backfilled_at`（承 `Ch9 §2.2` 双时间轴），消费方据此**排除**该期复盘。

    校验顺序（越界即抛，**不写半截数据**）：

    1. `layer ∈ VALID_LAYERS`（三层，`N10.3-01`）→ 否则 `EvalLayerError`；
    2. `set(axis) ⊆ VALID_AXES`（七方向，`N10.3-12`）；**空 axis 合法**（= 未定位到错误）、
       **一条错误跨多方向合法**（可数组）→ 否则 `ErrorAxisError`；
    3. 记录本身过 `assert_no_composite_score()`（不得被压成综合评分）→ 否则 `CompositeScoreError`。

    幂等（承 `Ch9` 幂等键、`scripts/daily/degrade.py` 同纪律）：同一
    `idempotency_key = review::{layer}::{target_ref}` 已存在 → **不重复追加**。

    参数 `output_refs`：该复盘任务的**可追溯回写**（`T14`：`done` 必须有非空 `output_refs`）。
      默认空（历史调用行为不变）；更正既有记录时用它补齐回写。

    参数 `new_version=True`（**追加更正版**，`Ch9 §3.4.2`）：**跳过**幂等去重，按同一
      `task_id` / 同一幂等键**追加一版新行**；此时 `recorded_seq` 必须显式给出且**严格大于**
      该 `task_id` 现有最大值（见 `_assert_version_monotonic`），否则抛 `ValueError`。
      历史版本**不改不删**。

    参数 `apply=False` → **只校验、不落库**（供预演 / 纯校验用例）。

    返回本地 `EvalResult`（与落库行内的 `eval_result` **逐字段一致**）。
    """
    if layer not in VALID_LAYERS:
        raise EvalLayerError(
            f"非法 eval_layer={layer!r}：三层不得新增 / 合并（Ch10 §N10.3-01）；"
            f"合法值 = {sorted(VALID_LAYERS)}"
        )
    axis_list = [str(a) for a in axis]
    illegal = sorted(set(axis_list) - VALID_AXES)
    if illegal:
        raise ErrorAxisError(
            f"error_axis 越界 {illegal}：只允许 Ch10 §C.3 七方向 {sorted(VALID_AXES)}"
        )

    record = EvalResult(
        eval_layer=layer,
        eval_target_ref=target_ref,
        error_axis=axis_list,
        error_axis_note=note,
        reason=reason,
        version=version,
    )
    # 负向断言：一条复盘记录**本身**不得携带综合评分字段（合法记录必过，见反向对照用例）。
    assert_no_composite_score([record])

    out_refs = [str(ref) for ref in output_refs]
    if apply:
        root = Path(code_root) if code_root is not None else _ROOT
        key = _idempotency_key(layer, target_ref)
        tid = task_id or f"task_review::{layer}::{target_ref}"
        if new_version:
            # ★ 追加**更正版**：同一逻辑复盘（同 task_id / 同幂等键）被追加了一版。
            #   版本序必须**严格递增**（`Ch9 §3.4.2`）—— 否则拒绝（不猜值、不倒挂）。
            _assert_version_monotonic(root, tid, recorded_seq)
            task = _build_task(
                record=record,
                task_id=tid,
                idempotency_key=key,
                status=task_status,
                recorded_at=recorded_at,
                recorded_seq=recorded_seq,
                backfilled_at=backfilled_at,
                output_refs=out_refs,
            )
            # 唯一写入口（`Ch9 §3.4.2`）：**不**自写文件、**不**就地改既有行。
            append_records(root, "tasks", [task])
        elif not _already_recorded(root, key):
            task = _build_task(
                record=record,
                task_id=tid,
                idempotency_key=key,
                status=task_status,
                recorded_at=recorded_at,
                recorded_seq=recorded_seq,
                backfilled_at=backfilled_at,
                output_refs=out_refs,
            )
            # 唯一写入口（`Ch9 §3.4.2`）：**不**自写文件、**不**就地改既有行。
            append_records(root, "tasks", [task])
    return record


def _idempotency_key(layer: str, target_ref: str) -> str:
    """复盘记录的幂等键（防同一层 × 同一对象被重复追加）。"""
    return f"review::{layer}::{target_ref}"


def _already_recorded(root: Path, idempotency_key: str) -> bool:
    """真源里是否已存在同一幂等键的行（存在 → 调用方应**跳过追加**）。"""
    for row in read_records(root, "tasks"):
        if str(row.get("idempotency_key") or "") == idempotency_key:
            return True
    return False


def _as_int(value: Any) -> int:
    """把 `recorded_seq` 之类取值归一为 `int`；非整数（含缺失 / `None` / 字符串）按 `0`。

    ★ 用 `isinstance` 判定而非 `try/except ... continue` —— 后者会**吞异常**
      （命中 `no_placeholder_guard` 的 `SWALLOW_EXCEPTION_CONTINUE`）。
    ★ 显式排除 `bool`：`bool` 是 `int` 子类，否则 `True` 会被当成版本号 `1`。
    """
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _max_recorded_seq(root: Path, task_id: str) -> int:
    """该 `task_id` 在真源里现有的最大 `recorded_seq`（缺 / 非整数按 `0` 处理，不猜值）。"""
    best = 0
    for row in read_records(root, "tasks"):
        if str(row.get("task_id") or "") != task_id:
            continue
        best = max(best, _as_int(row.get("recorded_seq")))
    return best


def _assert_version_monotonic(
    root: Path, task_id: str, recorded_seq: int | None
) -> None:
    """更正版（`new_version=True`）必须带**严格大于现有最大**的 `recorded_seq`。

    与 `scripts/claim/transition.py::_next_recorded_seq` 同纪律：**不猜值、不倒挂**
    （`Ch9 §3.4.2`：追加式版本表以 `recorded_seq` 区分版本；消费方按 `as_of` 取最大者）。
    缺值 / 不大于现有最大 → 抛 `ValueError`（**不写半截数据**）。
    """
    if recorded_seq is None:
        raise ValueError(
            f"更正版必须显式给出 recorded_seq（Ch9 §3.4.2）；task_id={task_id}"
        )
    current_max = _max_recorded_seq(root, task_id)
    if int(recorded_seq) <= current_max:
        raise ValueError(
            f"recorded_seq={recorded_seq} 不大于 task_id={task_id} 现有最大 {current_max} "
            "—— 版本序倒挂，拒绝（Ch9 §3.4.2）"
        )


def _build_task(
    *,
    record: EvalResult,
    task_id: str,
    idempotency_key: str,
    status: TaskStatus,
    recorded_at: datetime | None,
    recorded_seq: int | None,
    backfilled_at: datetime | None,
    output_refs: Sequence[str],
) -> Task:
    """把一条 `EvalResult` 包成可落库的 `Task`（`facts/tasks.jsonl` 的行模型 = `Task`）。

    `eval_target_ref`（Ch9 版本 id 机制）与 `reason` / `version`（`Ch2 §E change_log` 口径）
    为**复用**字段 —— 落 `parent_context`，**不**改 `EvalResult` schema（`Ch10 §C.1`）。

    `output_refs`（`T14` 可追溯回写）由调用方给出：复盘任务写成 `done` 即**必须有非空回写**，
    否则被 `G1-04` / `ASKTRACE-WRITEBACK` 判为空执行 —— 即本次更正修复的那条既有契约。

    `eval_result`（**当前那条**）与 `eval_result_history`（**追加式累积**）均写入本记录：
    首次写入时二者一致，正是"当前指针 + 追加式日志"的标准形态
    （`schema/models.py::Task.eval_result_history` 注明 append-only）。
    ★ 更正版（`new_version=True`）**另起一行**：跨版本的累积由**追加式行序列**承载
      （多行同 `task_id`，`recorded_seq` 递增），本行的 `eval_result_history` 仍是本行那条。
    """
    persisted = PersistedEvalResult(
        eval_layer=EvalLayer(record.eval_layer),
        error_axis=[ErrorAxis(a) for a in record.error_axis],
        error_axis_note=record.error_axis_note,
    )
    parent_context: dict[str, Any] = {
        "anchor": "Ch10 §C",
        "eval_target_ref": record.eval_target_ref,
        "reason": record.reason,
        "version": record.version,
    }
    return Task(
        task_id=task_id,
        task_type=TASK_TYPE,
        status=status,
        idempotency_key=idempotency_key,
        input_refs=[record.eval_target_ref],
        output_refs=list(output_refs),
        parent_context=parent_context,
        first_seen_at=recorded_at,
        analyzed_at=recorded_at,
        recorded_seq=recorded_seq,
        backfilled_at=backfilled_at,
        eval_result=persisted,
        eval_result_history=[persisted],
    )
