#!/usr/bin/env python3
"""`no_signal_day.py` —— **反 KPI 校验**（`Ch1 §F` G1-02 / `Ch1 §D.3`）。

```
python system/scripts/checks/no_signal_day.py [code_root]
```

三条断言（`Ch1 §F` G1-02，逐字）：
1. 无变化日 `signals_emitted == 0`
2. 新建议 `change_reason` 非空
3. `建议数 > 变化数` → **告警**（本节按"命中即 fail"实现：告警即 fail，禁 warn-only）

**核心口径**（源稿 `L344`）：
**不能把"生成了日报""页面能打开"或"问答听起来合理"作为研究完成的充分条件。**
每日维护 ≠ 每日产信号。

★ 命中即 fail，禁 warn-only（纪律 2）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402

# ── G1-02 ①：无变化日不得产信号 ─────────────────────────────────────────────

def check_no_signal_day(check_records: Sequence[Mapping[str, Any]]) -> list[Violation]:
    v: list[Violation] = []
    for rec in check_records:
        changed = bool(rec.get("changed"))
        emitted = int(rec.get("signals_emitted") or 0)
        if not changed and emitted != 0:
            v.append(
                Violation(
                    "G1-02①",
                    f"无变化日产了新信号: run_date={rec.get('run_date')} signals_emitted={emitted}",
                    "facts/tasks.jsonl",
                )
            )
        if not rec.get("run_date"):
            v.append(Violation("G1-02", f"check_record 缺 run_date: {rec!r}", "facts/tasks.jsonl"))
    return v


# ── G1-02 ②：新建议 change_reason 非空 ──────────────────────────────────────

def assert_new_signal_has_change_reason(rec: Mapping[str, Any]) -> None:
    """新建议必须给出**变化理由**；空 → fail。"""
    if not str(rec.get("change_reason") or "").strip():
        raise AssertionError(
            f"新建议缺 change_reason: recommendation_id={rec.get('recommendation_id')}"
        )


def check_change_reasons(recommendations: Sequence[Mapping[str, Any]]) -> list[Violation]:
    v: list[Violation] = []
    for rec in recommendations:
        if rec.get("action") in ("buy", "sell") and not str(rec.get("change_reason") or "").strip():
            v.append(
                Violation(
                    "G1-02②",
                    f"新建议缺 change_reason: {rec.get('recommendation_id')}",
                    "facts/recommendations.jsonl",
                )
            )
    return v


# ── G1-02 ③：建议数 > 变化数 → 告警 ────────────────────────────────────────

def check_signal_change_ratio(
    recommendations: Sequence[Mapping[str, Any]], check_records: Sequence[Mapping[str, Any]]
) -> list[Violation]:
    v: list[Violation] = []
    for rec in check_records:
        run_date = rec.get("run_date")
        changes = rec.get("judgment_change") or {}
        change_count = sum(1 for x in changes.values() if x) if isinstance(changes, Mapping) else 0
        same_day = [r for r in recommendations if str(r.get("start_date")) == str(run_date)]
        if len(same_day) > change_count:
            v.append(
                Violation(
                    "G1-02③",
                    f"建议数({len(same_day)}) > 变化数({change_count}) @ {run_date}"
                    "（每日维护 ≠ 每日产信号）",
                    "facts/recommendations.jsonl",
                )
            )
    return v


# ── 数据装载 ────────────────────────────────────────────────────────────────

def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"缺少真源文件: {path}")
    out: list[dict[str, Any]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = raw.strip()
        if raw:
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno} 非法 JSON: {exc}") from exc
    return out


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="no_signal_day")
    recs = _load_jsonl(root / "facts" / "recommendations.jsonl")
    # check_record 是控制面**子记录**，落 `facts/tasks.jsonl`（`Ch1 §C.2`；
    # 18 个 JSONL 不得增删改名，故不新开文件）
    tasks = _load_jsonl(root / "facts" / "tasks.jsonl")
    check_records = [
        t["check_record"] for t in tasks if isinstance(t.get("check_record"), Mapping)
    ]
    report.scanned["recommendations"] = len(recs)
    report.scanned["tasks"] = len(tasks)
    report.scanned["check_records"] = len(check_records)

    if not check_records:
        report.notes.append(
            "NO_CHECK_RECORD_DATA：真源为空（阶段① 尚未产生每日运行数据）——"
            "断言已就绪，阶段④ 起作用于真数据；本条**不构成** ‘已通过反 KPI 检查’"
        )
        return report

    report.violations += check_no_signal_day(check_records)
    report.violations += check_change_reasons(recs)
    report.violations += check_signal_change_ratio(recs, check_records)
    return report


if __name__ == "__main__":
    sys.exit(run_checker("no_signal_day.py", check))
