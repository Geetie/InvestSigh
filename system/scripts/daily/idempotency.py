#!/usr/bin/env python3
"""`idempotency.py` —— **同日重跑幂等**（`Ch8 §F` / `Ch9 §3.3.4 / §3.4.7` / `Ch1 §C.3`）。

```
python system/scripts/daily/idempotency.py [code_root]
```

## 三类幂等键（**全部复用既有真源，不新建机制**，`Ch8 §F.1`）

| 产出 | 幂等键 | 复用点 |
|---|---|---|
| 事件 | `event_fingerprint`（基于**根来源**，非标题） | `scripts.graph.fingerprint.fingerprint_of_event`（`Ch9 §3.4.7`） |
| 建议 | `(security_id, issued_at, version)` | 本模块表达；`Ch9 §3.3.4` |
| 任务 | `(gap_id 或 claim_id) + task_type` | `scripts.tasks.gap_to_task.idempotency_key`（`Ch1 §C.3`） |

## 判据（`Ch8 §N8.4-08`）

> **同日同输入重跑 N 次，`events` / `recommendations` 行数不变** —— 幂等键命中即跳过。

实现：`append_deduped` 在追加前按幂等键去重；`check_daily_idempotency` 对真源内
**已存在的重复键**报违例（命中即 fail，纪律 2）。

★ **口径映射**（如实登记，见 DoD §4 G-5）：模型 `Recommendation` 无 `issued_at`
  字段，其落点为 `start_date`；本模块以 `(security_id, start_date, version)` 表达设计键。

★ 退出码：`0` 通过 / `1` 命中违例 / `2` 输入异常。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402

ANCHOR_EVENT = "Ch9 §3.4.7"
ANCHOR_REC = "Ch9 §3.3.4"
ANCHOR_TASK = "Ch1 §C.3"
CRITERION = "G1-04"

#: 幂等键字段名（`schema.models`：`Task.idempotency_key`）。
KEY_FIELD = "idempotency_key"

KeyFn = Callable[[Mapping[str, Any]], str]


def task_key(gap_id: str | None, claim_id: str | None, task_type: str) -> str:
    """任务幂等键 = `(gap_id 或 claim_id) + task_type`（**复用**既有实现，`Ch1 §C.3`）。"""
    from scripts.tasks.gap_to_task import idempotency_key

    return idempotency_key(gap_id, claim_id, task_type)


def recommendation_idempotency_key(
    security_id: str, issued_at: str, version: Any
) -> str:
    """建议幂等键 `(security_id, issued_at, version)`（`Ch9 §3.3.4`）。"""
    if not security_id or not str(issued_at).strip():
        raise ValueError("建议幂等键需要非空 security_id 与 issued_at")
    return f"{security_id}::{issued_at}::{version}"


def recommendation_key_of(row: Mapping[str, Any]) -> str:
    """从一条建议行取幂等键（`issued_at` ← 模型 `start_date`，见模块 docstring 口径映射）。"""
    return recommendation_idempotency_key(
        str(row.get("security_id") or ""),
        str(row.get("start_date") or ""),
        row.get("version"),
    )


def event_key_of(row: Mapping[str, Any]) -> str:
    """从一条事件行取幂等键：优先 `event_id`（即指纹），否则**现算**指纹（`Ch9 §3.4.7`）。"""
    event_id = str(row.get("event_id") or "")
    if event_id:
        return event_id
    from scripts.graph.fingerprint import fingerprint_of_event

    return fingerprint_of_event(row)


def _read(root: str | Path, stem: str) -> list[dict[str, Any]]:
    from schema.store import read_records

    return read_records(root, stem)


def existing_keys(root: str | Path, stem: str, key_of: KeyFn) -> set[str]:
    """真源内已存在的幂等键集合。"""
    return {key_of(row) for row in _read(root, stem)}


def duplicates(
    root: str | Path, stem: str, key_of: KeyFn = recommendation_key_of
) -> list[str]:
    """真源内**重复出现**的幂等键（升序）——空表表示无重复。"""
    seen: dict[str, int] = {}
    for row in _read(root, stem):
        key = key_of(row)
        seen[key] = seen.get(key, 0) + 1
    return sorted(k for k, n in seen.items() if n > 1)


def append_deduped(
    root: str | Path, stem: str, records: Sequence[Any], key_of: KeyFn
) -> int:
    """按幂等键**去重后追加**：命中既有键的记录跳过（`Ch8 §N8.4-08`）。

    返回**实际追加**的行数。唯一写路径是 `schema.store.append_records`（追加式不可变）。
    """
    from schema.store import append_records

    known = existing_keys(root, stem, key_of)
    fresh: list[Any] = []
    for record in records:
        node = record.model_dump(mode="json") if hasattr(record, "model_dump") else dict(record)
        key = key_of(node)
        if key in known:
            continue
        known.add(key)
        fresh.append(record)
    if not fresh:
        return 0
    return append_records(root, stem, fresh)


def check_daily_idempotency(
    root: str | Path, *, stem: str, key_of: KeyFn
) -> list[Violation]:
    """真源内出现重复幂等键 → 违例（同日重跑重复产事件/建议，`Ch8 §N8.4-08`）。"""
    anchor = ANCHOR_EVENT if stem == "events" else ANCHOR_REC
    return [
        Violation(
            CRITERION,
            f"{stem} 存在重复幂等键 {key!r}（同日重跑不得重复产事件/建议，{anchor}）",
            f"facts/{stem}.jsonl",
        )
        for key in duplicates(root, stem, key_of)
    ]


def check(root: Path) -> CheckReport:
    """守卫：对 `events` 与 `recommendations` 跑幂等唯一性断言（命中即 fail）。"""
    report = CheckReport(checker="daily_idempotency")
    events = _read(root, "events")
    recs = _read(root, "recommendations")
    report.scanned["events"] = len(events)
    report.scanned["recommendations"] = len(recs)
    report.violations += check_daily_idempotency(root, stem="events", key_of=event_key_of)
    report.violations += check_daily_idempotency(
        root, stem="recommendations", key_of=recommendation_key_of
    )
    if not events and not recs:
        report.notes.append(
            "NO_IDEMPOTENCY_SAMPLE：events 与 recommendations 均为空（阶段④ 起作用于真数据）"
        )
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="idempotency.py", description="同日重跑幂等（Ch8 §F）")
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.code_root) if args.code_root else _ROOT
    return run_checker(
        "daily_idempotency", check, [str(root)] + (["--no-report"] if args.no_report else [])
    )


if __name__ == "__main__":
    sys.exit(main())
