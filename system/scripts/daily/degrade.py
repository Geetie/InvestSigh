#!/usr/bin/env python3
"""`degrade.py` —— **故障降级：保留上次有效结果**（`Ch8 §E` / `Ch9 §3.6`）。

```
python system/scripts/daily/degrade.py [code_root] --scope full --run-date YYYY-MM-DD
```

## 设计口径（`Ch8 §E.1` 四类故障的共同红线）

> 故障时**保留上次有效结果并清楚显示日期 + 失效状态**；**不覆盖为无意义空值**；
> **不把旧数据标为最新**（`Ch8 §N8.4-05/06/07`）。

本模块**不重造**任何降级判定 —— 降级的**真信号**来自编排器产出的
`scripts.orchestrate.pipeline.RunResult`（字段 `degraded` / `blocked` / `gaps`）。
本模块只做三件事：

1. **保留上次有效结果**：`last_valid_result_ref` 指向**上一次成功**运行的 `check_id`
   （无 → `None`，**如实为空**，不臆造）；
2. **降级可见**（不得静默）：把降级落成一条**追加式** `Task` 行，带
   `parent_context.degraded=true` + `gaps`（来自 `RunResult.gaps`）；
3. **幂等**：同一 `(run_date, scope)` 只落一条（键 `degrade::<date>::<scope>`）。

★ **"上次有效结果"的判定只有一份**（`G-45` 收口）：原语 `is_valid_run_record()`
  + 由它派生的 `last_valid_result_ref()`（写路径据此填引用）与 `holds_valid_result()`
  （阶段④"首日豁免"据此判定，`scripts/delivery/stage_gate.py` **import 本模块**，
  不再自持一套）。此前两处口径相反 —— 同一批行一个说"有"、一个说"无"。

★ **追加式不可变**（`Ch9 §3.4.2` 纪律 4）：唯一写路径是 `schema.store.append_records`；
  本模块**不做** UPDATE / DELETE。
★ 写路径断言（`Ch8 §E.4`）：`assert_no_null_overwrite` / `assert_not_labeled_latest`
  由**调用方在写前调用**，命中即**抛**（`NullOverwriteError` / `StaleLabeledLatestError`），
  **不 warn-only**（纪律 2）。

★ 退出码：`0` 正常 / `2` 输入异常（复用 `_common.run_checker`）。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402

DEGRADE_REASON = "degraded_run"
ANCHOR = "Ch8 §E"

#: 被判定为"无意义空值"的取值（`Ch8 §N8.4-06`：故障不得把字段覆盖为这些）。
#:
#: ★ 刻意**不含** `0` / `False`：二者是**有意义**的取值（如 `position_listed=False`、
#:   计数 0）。用 `in (...)` 判等会把 `False == 0` 一并吞掉，制造两类误判 ——
#:   ① 把"本来就非空"的 `0`/`False` 当成空而放行；② 把"合法的 0/False"当成空而误报。
#:   故此处只列"未表达"的形态：`None` / 空串 / 空列表 / 空字典。
_NULLISH = (None, "", [], {})

#: 表示"最新 / 实时"的展示标签（`Ch8 §N8.4-07`：旧数据不得标为最新）。
LATEST_LABELS = ("latest", "realtime", "最新", "实时")


class NullOverwriteError(RuntimeError):
    """降级把既有非空字段覆盖成无意义空值（`Ch8 §N8.4-06`）。"""


class StaleLabeledLatestError(RuntimeError):
    """失效数据被标为"最新 / 实时"（`Ch8 §N8.4-07`）。"""


def is_degraded(result: Any) -> bool:
    """`RunResult`（或同构对象）是否处于降级 / 阻断态（**复用**编排器语义）。"""
    return bool(getattr(result, "degraded", False) or getattr(result, "blocked", False))


def run_gaps(result: Any) -> list[str]:
    """取编排器如实登记的缺口（`RunResult.gaps`）；无 → 空表（**不臆造**）。"""
    return [str(g) for g in (getattr(result, "gaps", None) or [])]


def is_valid_run_record(row: Mapping[str, Any]) -> bool:
    """该行是否**一条成功的运行记录** —— "上次有效结果"的**唯一原语**（`G-45` 收口）。

    判据（`Ch8 §E` / `§E.2`）：

    1. 带 `check_record`（只有运行记录才有可被引用的 `check_id`）；
    2. `status != "failed"`（本次运行没有失败）；
    3. `check_record.degraded` 为假（**降级运行的结果不是"有效结果"** —— 它本身就是在
       声明"本次结果不完整，请用上一次的"）。

    ★ **本函数是全仓库"上次有效结果"的唯一判定原语**：`last_valid_result_ref()`（定位该引用）
      与 `holds_valid_result()`（判定豁免）都建在它之上。此前 `stage_gate._holds_valid_result()`
      **另写了一套**（`output_refs` 口径）⇒ 同一批行两个模块给出**相反结论**（`G-45`）。
    """
    record = row.get("check_record")
    if not isinstance(record, Mapping):
        return False
    return row.get("status") != "failed" and not record.get("degraded")


def holds_valid_result(row: Mapping[str, Any]) -> bool:
    """该行是否**持有有效结果** —— 阶段④"首日豁免"判定的**唯一真源**（`G-43` / `G-45`）。

    三条载体取**并集**（相对 `stage_gate` 旧口径与 `degrade` 旧口径**只增不减**，不放松）：

    | 载体 | 判据 | 来源 |
    |---|---|---|
    | ① | `last_valid_result_ref` 非空 | `stage_gate` 旧口径 —— 降级链上的**显式引用**：前序行已经证明"引用是能保留的" |
    | ② | `is_valid_run_record(row)` | `degrade` 旧口径 —— **一次成功的运行**（这正是消掉 `G-45` 分歧的那一条） |
    | ③ | `status == "done"` 且 `output_refs` 非空 | `stage_gate` 旧口径 —— 正常完成且**真的产出了对象** |

    ★ **为什么必须有 ②**（本单的核心修复，`G-43`）：写入方 `pipeline._write_check_record()`
      原先**两个载体都不填**，于是 ①③ 在生产数据上**恒为假** ⇒ 本谓词**恒 False**
      ⇒ `any(prior)` 恒 False ⇒ **每一个失败行都被当成"首日"豁免** ⇒
      判据"降级保留上次有效结果"**空转、从不报任何真违规**。
      补上 ② 后，"此前有过一次成功运行"这件事**不再依赖任何未被填写的字段**。

    ★ **② 为什么不看 `output_refs`**：`Ch1 §D.3` 的反 KPI 明确"无变化日**不产信号**"，
      故无变化日的产出**合法为空**；但那次运行**仍是一次有效结果**（它完成了核查）。
      若把"产出为空"排除在有效结果之外，则"成功但无新增"的日子一过，
      下一次失败就会被误判成首日 —— 那正是 `G-43` 的同一形态（换个字段复发）。

    ★ **③ 为什么保留**：它是 `stage_gate` 的既有载体，删掉即**放松**判据（`R-06`：只增不减）。
      ③ 的生效条件 = `status == "done"` **且** `output_refs` 非空。**后半已经成立**：
      `pipeline._write_check_record()` **已**写 `output_refs`（`pipeline.py:415`）⇒
      原句"将来有别的写入方按旧口径填 `output_refs`"**已经发生**（不是将来）；眼下 ③ 仍不生效
      只是因为**前半**不成立（`T-18`：step 7/8 永不注册 ⇒ `blocked` 恒真 ⇒ 真仓库无 `done` 行）。
      ⇒ **保留的收益现在是真的**：`T-18` 一旦落地、`done` 行一出现，③ 立刻是活的。
      ★ 原句"它当前无生产写入点（`output_refs=` 零个生产赋值点）"是 `abbe7b3` **之前**的读数，
      **勿当现态** —— 否则就是"结论侥幸还对、理由已失效"（`G-50` 形态；清单见
      `reports/ws_degrade_contract_report.md` §④-7）。
    """
    if row.get("last_valid_result_ref"):
        return True
    if is_valid_run_record(row):
        return True
    return row.get("status") == "done" and bool(row.get("output_refs"))


def last_valid_result_ref(root: str | Path, *, scope: str = "full") -> str | None:
    """上一次**成功**运行的 `check_id`，作为"上次有效结果"的引用。

    判据（`Ch8 §E`）：取 `facts/tasks.jsonl` 内带 `check_record` 的行中，
    **满足 `is_valid_run_record()`**（= 降级为假且状态非 `failed`）的**最后一条**
    （`facts/tasks.jsonl` 追加式不可变 ⇒ **行序即时序**）。无 → `None`（**如实为空**，`G-03`）。

    ★ 这里**只**用 `is_valid_run_record()`，**不**用 `holds_valid_result()` 的并集：
      本函数的返回值是**可被引用的 `check_id`**，而并集的载体 ① 是一条**失败行自带的指针**
      （它自己的 `check_id` 不是有效结果）。二者分工：本函数答"**该指向谁**"，
      `holds_valid_result()` 答"**结构上是否可能存在可保留的结果**"，
      且后者 ⊇ 前者所用的原语（不会比前者更弱）。
    """
    from schema.store import read_records

    ref: str | None = None
    for row in read_records(root, "tasks"):
        record = row.get("check_record")
        if not isinstance(record, Mapping):
            continue
        if str(row.get("scope") or record.get("scope") or "") not in ("", scope):
            continue
        if not is_valid_run_record(row):
            continue
        check_id = record.get("check_id")
        if check_id:
            ref = str(check_id)
    return ref


def assert_no_null_overwrite(
    old_row: Mapping[str, Any],
    new_row: Mapping[str, Any],
    fields: Sequence[str] | None = None,
) -> None:
    """降级时**既有非空字段不得被覆盖为空值**（`Ch8 §E.4` / `N8.4-06`）。

    仅当 `old_row[f]` 非空而 `new_row[f]` 为空（`None` / `""` / `0` / `[]` / `{}`）时判违例；
    `old_row[f]` 本就为空 → **不**判违例（边界：不得把"本来就是空"判成置空）。
    """
    names = list(fields) if fields is not None else [k for k in old_row if k in new_row]
    for name in names:
        old_val = old_row.get(name)
        if old_val in _NULLISH:
            continue
        if new_row.get(name) in _NULLISH:
            raise NullOverwriteError(
                f"降级不得把非空字段置空: {name!r}（old={old_val!r} → new={new_row.get(name)!r}）"
            )


def assert_not_labeled_latest(row: Mapping[str, Any]) -> None:
    """失效数据不得标为"最新 / 实时"（`Ch8 §E.4` / `N8.4-07`）。

    判据：`stale` 为真时，`display_label` 不得是"最新 / 实时"类标签，
    且展示时间戳须为真实 `as_of_time`（存在 `stale_since`）。
    """
    if not row.get("stale"):
        return
    label = str(row.get("display_label") or "").strip().lower()
    if label in {x.lower() for x in LATEST_LABELS}:
        raise StaleLabeledLatestError(f"失效数据被标为最新/实时: display_label={label!r}")
    if not row.get("stale_since"):
        raise StaleLabeledLatestError(
            "失效数据缺 stale_since（无法显示'截至 X 日'；不得标为最新，Ch8 §E）"
        )


@dataclass
class DegradationMark:
    """一次降级标记的结果（确定性、可复现）。"""

    applied: bool
    visible: bool
    run_date: str
    scope: str
    reason: str
    last_valid_ref: str | None
    task_id: str | None
    gaps: tuple[str, ...] = field(default_factory=tuple)
    skipped_task_id: str | None = None

    @property
    def idempotency_key(self) -> str:
        return f"degrade::{self.run_date}::{self.scope}"


def mark_degraded(
    root: str | Path,
    result: Any,
    *,
    run_date: date,
    scope: str = "full",
    reason: str = DEGRADE_REASON,
    apply: bool = True,
) -> DegradationMark:
    """把一次降级落成**可见 + 幂等**的标记；非降级 → 原样返回"未应用"。

    返回 `DegradationMark`；`apply=False` → 只计算、不落库。
    """
    from schema.models import Task, TaskStatus, TaskType
    from schema.store import append_records, read_records

    day = run_date.isoformat()
    gaps = tuple(run_gaps(result))
    last_ref = last_valid_result_ref(root, scope=scope)
    key = f"degrade::{day}::{scope}"

    if not is_degraded(result):
        return DegradationMark(
            applied=False,
            visible=False,
            run_date=day,
            scope=scope,
            reason=reason,
            last_valid_ref=last_ref,
            task_id=None,
            gaps=gaps,
        )

    # 幂等：命中既有键 → 不重复建单（同日重跑不重复产事件/建议的同一纪律）
    for row in read_records(root, "tasks"):
        if str(row.get("idempotency_key") or "") == key:
            return DegradationMark(
                applied=False,
                visible=True,
                run_date=day,
                scope=scope,
                reason=reason,
                last_valid_ref=last_ref,
                task_id=None,
                gaps=gaps,
                skipped_task_id=str(row.get("task_id") or ""),
            )

    task = Task(
        task_id=f"task_{key}",
        task_type=TaskType.recheck,
        status=TaskStatus.failed,
        idempotency_key=key,
        input_refs=[last_ref] if last_ref else [],
        parent_context={
            "reason": reason,
            "degraded": True,
            "anchor": ANCHOR,
            "run_date": day,
            "gaps": list(gaps),
        },
        last_valid_result_ref=last_ref,
    )
    if apply:
        append_records(root, "tasks", [task])
    return DegradationMark(
        applied=apply,
        visible=True,
        run_date=day,
        scope=scope,
        reason=reason,
        last_valid_ref=last_ref,
        task_id=task.task_id,
        gaps=gaps,
    )


def check(root: Path) -> CheckReport:
    """守卫：降级标记**必须可见且可核**（`Ch8 §E`）。

    断言（**命中即 fail**）——对 `facts/tasks.jsonl` 内每条 `parent_context.degraded=true` 的行：

    - **E1 降级可核**：必须携带 `last_valid_result_ref`（保留上次有效结果）**或** 非空
      `parent_context.gaps`（降级原因可见）；两者皆无 → 违例（降级不可核、不可见）；
    - **E2 日期可见**：必须有 `parent_context.run_date`（`Ch8 §E`："清楚显示日期"），否则违例。

    `last_valid_result_ref` 为空的**合法**情形（首日降级、本无上次有效结果）→ **note**，不判违例
    （`G-03`：不得把"如实为空"判成缺陷）。空样本 → note（`NO_DEGRADE_MARK`）。
    """
    from schema.store import read_records

    report = CheckReport(checker="degrade_keeps_last_valid")
    rows = read_records(root, "tasks")
    report.scanned["tasks"] = len(rows)
    degraded_rows = [
        r
        for r in rows
        if isinstance(r.get("parent_context"), Mapping)
        and r["parent_context"].get("degraded") is True
    ]
    report.scanned["degraded_marks"] = len(degraded_rows)
    for row in degraded_rows:
        ctx = row.get("parent_context") or {}
        has_last = bool(row.get("last_valid_result_ref"))
        gaps = ctx.get("gaps") or []
        if not has_last and not gaps:
            report.violations.append(
                Violation(
                    "degrade_keeps_last_valid",
                    f"{row.get('task_id')} 为降级标记，却既无 last_valid_result_ref 又无 gaps —— "
                    f"降级不可核、不可见（{ANCHOR}）",
                    "facts/tasks.jsonl",
                )
            )
        if not ctx.get("run_date"):
            report.violations.append(
                Violation(
                    "degrade_keeps_last_valid",
                    f"{row.get('task_id')} 为降级标记，却缺 parent_context.run_date —— "
                    f"无法清楚显示日期（{ANCHOR}）",
                    "facts/tasks.jsonl",
                )
            )
        if not has_last:
            report.notes.append(
                f"DEGRADE_NO_LAST_VALID：{row.get('task_id')} 无上次有效结果可保留"
                "（如实为空，见 DoD AC-2）"
            )
    if not degraded_rows:
        report.notes.append("NO_DEGRADE_MARK：真源内无降级标记（阶段④ 起作用于真数据）")
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="degrade.py", description="降级保留上次有效结果（Ch8 §E）")
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.code_root) if args.code_root else _ROOT
    return run_checker(
        "degrade_keeps_last_valid", check, [str(root)] + (["--no-report"] if args.no_report else [])
    )


if __name__ == "__main__":
    sys.exit(main())
