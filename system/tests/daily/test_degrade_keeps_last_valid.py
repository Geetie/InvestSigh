"""AC-2：**故障降级保留上次有效结果**（`Ch8 §E` / `Ch9 N9.2-13`）的正反两向测试。

锚点：`Ch8 §E`（保留上次有效结果 + 清楚显示日期 + 不得置空 + 不得标为最新）/
`Ch9 §3.6`（降级不静默）/ `CONVENTIONS.md §二 G-03`（真空不得判过）。

★ 契约（对齐 `tests/conftest.py`）：`code_root` 夹具给**空真源**，测试自己声明数据。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from scripts.daily import degrade
from schema.models import CheckRecord, CheckScope, Task, TaskStatus, TaskType
from schema.store import append_records, read_records


class _Run:
    """最小 `RunResult` 替身：只暴露本模块真正消费的三个字段（degraded/blocked/gaps）。"""

    def __init__(self, *, degraded: bool, blocked: bool = False, gaps: tuple[str, ...] = ()) -> None:
        self.degraded = degraded
        self.blocked = blocked
        self.gaps = list(gaps)


def _append_raw_tasks(root: Path, rows: list[dict]) -> None:
    path = root / "facts" / "tasks.jsonl"
    with open(path, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _prior_valid_check(root: Path, check_id: str, run_day: date) -> None:
    """落一条**有效**核查记录（复现"上次成功运行"的痕迹，供降级引用）。"""
    record = CheckRecord(
        check_id=check_id,
        run_date=run_day,
        scope=CheckScope.full,
        changed=False,
        signals_emitted=0,
        degraded=False,
    )
    task = Task(
        task_id=f"task_{check_id}",
        task_type=TaskType.verify,
        status=TaskStatus.done,
        idempotency_key=f"check::{check_id}",
        check_record=record,
    )
    append_records(root, "tasks", [task])


def _degraded_marks(root: Path) -> list[dict]:
    return [
        r
        for r in read_records(root, "tasks")
        if isinstance(r.get("parent_context"), dict) and r["parent_context"].get("degraded") is True
    ]


# ── 正向：降级保留上次有效结果 + 可见 ────────────────────────────────────────

def test_keeps_last_valid_ref_and_is_visible(code_root: Path) -> None:
    _prior_valid_check(code_root, "check_2026-01-01_full", date(2026, 1, 1))

    mark = degrade.mark_degraded(
        code_root, _Run(degraded=True, gaps=("step 3 缺口",)), run_date=date(2026, 1, 2)
    )

    assert mark.applied is True
    assert mark.visible is True
    assert mark.last_valid_ref == "check_2026-01-01_full"
    assert mark.idempotency_key == "degrade::2026-01-02::full"

    marks = _degraded_marks(code_root)
    assert len(marks) == 1
    assert marks[0]["last_valid_result_ref"] == "check_2026-01-01_full"
    assert marks[0]["parent_context"]["run_date"] == "2026-01-02"
    assert marks[0]["parent_context"]["gaps"] == ["step 3 缺口"]


def test_non_degraded_result_is_not_marked(code_root: Path) -> None:
    mark = degrade.mark_degraded(code_root, _Run(degraded=False), run_date=date(2026, 1, 2))
    assert mark.applied is False
    assert mark.visible is False
    assert read_records(code_root, "tasks") == []


def test_first_day_degradation_last_valid_is_empty_not_a_violation(code_root: Path) -> None:
    """边界：首日降级、本无上次有效结果 → `last_valid_result_ref` 如实为空，**不判违例**。"""
    mark = degrade.mark_degraded(
        code_root, _Run(degraded=True, gaps=("首日无上次有效结果",)), run_date=date(2026, 1, 2)
    )
    assert mark.last_valid_ref is None

    report = degrade.check(code_root)
    assert report.passed, [v.reason for v in report.violations]
    assert any("DEGRADE_NO_LAST_VALID" in n for n in report.notes), report.notes


def test_guard_passes_on_wellformed_mark(code_root: Path) -> None:
    _prior_valid_check(code_root, "check_2026-01-01_full", date(2026, 1, 1))
    degrade.mark_degraded(
        code_root, _Run(degraded=True, gaps=("g",)), run_date=date(2026, 1, 2)
    )
    report = degrade.check(code_root)
    assert report.passed, [v.reason for v in report.violations]
    assert report.scanned["degraded_marks"] == 1


# ── 幂等：同日重跑只落一条降级标记 ──────────────────────────────────────────

def test_same_day_mark_is_idempotent(code_root: Path) -> None:
    _prior_valid_check(code_root, "check_2026-01-01_full", date(2026, 1, 1))
    run = _Run(degraded=True, gaps=("g",))

    first = degrade.mark_degraded(code_root, run, run_date=date(2026, 1, 2))
    before = len(read_records(code_root, "tasks"))
    second = degrade.mark_degraded(code_root, run, run_date=date(2026, 1, 2))
    after = len(read_records(code_root, "tasks"))

    assert first.applied is True
    assert second.applied is False
    assert second.visible is True
    assert second.skipped_task_id == first.task_id
    assert before == after
    assert len(_degraded_marks(code_root)) == 1


# ── 错误路径：置空 / 标为最新 一律响亮抛错 ──────────────────────────────────

def test_null_overwrite_error_path_and_boundaries() -> None:
    with pytest.raises(degrade.NullOverwriteError):
        degrade.assert_no_null_overwrite({"a": "x"}, {"a": ""})
    with pytest.raises(degrade.NullOverwriteError):
        degrade.assert_no_null_overwrite({"a": ["x"]}, {"a": []})

    # 边界：本来就为空 → 不判违例（不得把"本来就是空"判成置空）
    degrade.assert_no_null_overwrite({"a": ""}, {"a": ""})
    degrade.assert_no_null_overwrite({"a": None}, {"a": ""})

    # 边界：`0` / `False` 是**有意义**取值，不是"空"
    degrade.assert_no_null_overwrite({"n": 5, "flag": True}, {"n": 0, "flag": False})

    # 正常：非空 → 非空
    degrade.assert_no_null_overwrite({"a": "x"}, {"a": "y"})


def test_stale_labeled_latest_error_path() -> None:
    with pytest.raises(degrade.StaleLabeledLatestError):
        degrade.assert_not_labeled_latest(
            {"stale": True, "display_label": "最新", "stale_since": "2026-01-01"}
        )
    with pytest.raises(degrade.StaleLabeledLatestError):
        # 缺 stale_since → 无法显示"截至 X 日"
        degrade.assert_not_labeled_latest({"stale": True, "display_label": "截至 2026-01-01"})

    # 正常：失效但标签诚实 + 有时间戳
    degrade.assert_not_labeled_latest(
        {"stale": True, "display_label": "截至 2026-01-01", "stale_since": "2026-01-01"}
    )
    # 正常：未失效
    degrade.assert_not_labeled_latest({"stale": False, "display_label": "最新"})


# ── 反向：不可见的降级标记被守卫拦下 ────────────────────────────────────────

def test_guard_fails_on_invisible_mark(code_root: Path) -> None:
    """降级标记既无 `last_valid_result_ref` 又无 `gaps` → 不可核 → 违例。"""
    _append_raw_tasks(
        code_root,
        [
            {
                "task_id": "t_invisible",
                "task_type": "recheck",
                "status": "failed",
                "idempotency_key": "degrade::2026-01-02::full",
                "parent_context": {"degraded": True},
            }
        ],
    )
    report = degrade.check(code_root)
    assert not report.passed
    assert any("不可核" in v.reason for v in report.violations), [v.reason for v in report.violations]


def test_guard_fails_on_missing_run_date(code_root: Path) -> None:
    """降级标记缺 `parent_context.run_date` → 无法清楚显示日期 → 违例。"""
    _append_raw_tasks(
        code_root,
        [
            {
                "task_id": "t_nodate",
                "task_type": "recheck",
                "status": "failed",
                "idempotency_key": "degrade::2026-01-03::full",
                "last_valid_result_ref": "check_2026-01-01_full",
                "parent_context": {"degraded": True, "gaps": ["g"]},
            }
        ],
    )
    report = degrade.check(code_root)
    assert not report.passed
    assert any("run_date" in v.reason for v in report.violations), [v.reason for v in report.violations]
