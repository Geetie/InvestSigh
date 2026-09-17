"""`tests/unit/test_versioned_task_rows.py` —— 版本化真源口径的机器绑定（`Ch9 §3.4.1` / `§3.4.2`）。

本单引入的口径：`facts/tasks.jsonl` 是**追加式版本表**，两个守卫

- `scripts/graph/traceability.py` 的**提问任务追溯链**（`T14`）
- `scripts/tasks/gap_to_task.py` 的 **G1-04**（终态必须有输出 / 幂等键唯一）

都只判**每个 `task_id` 的当前版本**（`recorded_seq` 最大者，经 `schema.store.as_of` 选取），
被跳过的历史版本**显式计数**（`G-03`）。本文件把该口径钉住 —— 并给出**反向对照**（`G-05`）：
**真实重复**（同幂等键、**异** `task_id`）去重后仍是两行，照常报警 ⇒ **不是放宽**。

★ 只用 `tmp_path`（**不** `copytree`）：本文件必须**快**（`CONVENTIONS.md::V-05` 的时序纪律）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.graph.traceability import task_traceability_violations
from scripts.review.record_eval import record_eval
from scripts.tasks.gap_to_task import check
from schema.store import read_records


def _row(
    task_id: str,
    recorded_seq: int,
    *,
    status: str = "done",
    output_refs: list | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """与真实 `facts/tasks.jsonl` 行**同字段集**，只改被测的几处（版本 / 回写 / 幂等键）。"""
    return {
        "task_id": task_id,
        "task_type": "verify",
        "status": status,
        "idempotency_key": idempotency_key or f"review::{task_id}",
        "input_refs": [],
        "output_refs": output_refs or [],
        "recorded_seq": recorded_seq,
    }


def _write_tasks(root: Path, rows: list[dict]) -> None:
    path = root / "facts" / "tasks.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )


# ── 提问任务链（traceability）：只判当前版本（含两次反向对照） ────────────────


def test_traceability_judges_latest_version_only(tmp_path: Path) -> None:
    """**旧版缺回写、当前版本已回写** ⇒ **不报**（若无该口径，旧版会被当成独立被检对象而假红）。"""
    rows = [
        _row("t1", 1, output_refs=[]),          # 历史版本：缺 `output_refs`
        _row("t1", 2, output_refs=["obj-1"]),   # 当前版本：已回写
    ]
    violations, scanned = task_traceability_violations(tmp_path, tasks=rows)
    assert [v.rule for v in violations] == [], [v.reason for v in violations]
    assert scanned == {
        "tasks": 1,
        "tasks_all_versions": 2,
        "tasks_historical_skipped": 1,
    }, scanned


def test_traceability_flags_when_current_version_lacks_writeback(tmp_path: Path) -> None:
    """反向（`G-05`）：**当前版本**缺回写 ⇒ 照样报 `ASKTRACE-WRITEBACK`（口径不放宽）。"""
    rows = [
        _row("t1", 1, output_refs=["obj-1"]),   # 历史版本：曾有回写
        _row("t1", 2, output_refs=[]),          # 当前版本：缺回写（真违规）
    ]
    violations, _ = task_traceability_violations(tmp_path, tasks=rows)
    assert any(v.rule == "ASKTRACE-WRITEBACK" for v in violations), [v.reason for v in violations]


# ── G1-04（gap_to_task）：只判当前版本 + 历史版本显式计数 ────────────────────


def test_gap_to_task_judges_latest_version_and_counts_skipped(tmp_path: Path) -> None:
    """**更正版补齐回写** ⇒ 无空执行违例；`scanned` 显式记 `all_versions` / `historical_skipped`。"""
    _write_tasks(
        tmp_path,
        [
            _row("t1", 1, output_refs=[]),          # 历史版本：空产出（本不该再被计）
            _row("t1", 2, output_refs=["obj-1"]),   # 当前版本：已回写
        ],
    )
    report = check(tmp_path)
    assert report.passed, [v.reason for v in report.violations]
    assert report.scanned["tasks"] == 1, report.scanned
    assert report.scanned["tasks_all_versions"] == 2, report.scanned
    assert report.scanned["tasks_historical_skipped"] == 1, report.scanned
    assert report.scanned["done_empty_output_rows"] == 0, report.scanned
    assert report.scanned["empty_output_violations"] == 0, report.scanned


def test_gap_to_task_still_flags_real_duplicate_across_task_ids(tmp_path: Path) -> None:
    """反向（`G-05`）：同幂等键挂在**两个不同 `task_id`** 上 ⇒ **仍报警**（去重**不是放宽**）。"""
    _write_tasks(
        tmp_path,
        [
            _row("t1", 1, output_refs=["obj-1"], idempotency_key="dup::k"),
            _row("t2", 1, output_refs=["obj-2"], idempotency_key="dup::k"),
        ],
    )
    report = check(tmp_path)
    assert any("幂等键重复" in v.reason for v in report.violations), [
        v.reason for v in report.violations
    ]


# ── record_eval 的追加更正版（new_version）：版本序必须严格递增 ──────────────


def test_record_eval_new_version_appends_and_requires_monotonic_seq(tmp_path: Path) -> None:
    """`new_version=True` 追加一版（同 `task_id`、`recorded_seq` 递增、带非空 `output_refs`）；
    序号不大于现有最大 / 缺省 ⇒ 拒绝（`Ch9 §3.4.2`，不猜值、不倒挂）。"""
    (tmp_path / "facts").mkdir(parents=True, exist_ok=True)
    record_eval("research_quality", "baseline-x", code_root=tmp_path, recorded_seq=1)
    record_eval(
        "research_quality",
        "baseline-x",
        code_root=tmp_path,
        output_refs=["baseline-x"],
        recorded_seq=2,
        new_version=True,
    )

    rows = read_records(tmp_path, "tasks")
    assert len(rows) == 2, "更正版应为**追加**（同 task_id 两行），不得就地改历史行"
    assert all(r["task_id"] == "task_review::research_quality::baseline-x" for r in rows)
    latest = max(rows, key=lambda r: r["recorded_seq"])
    assert latest["recorded_seq"] == 2 and latest["output_refs"] == ["baseline-x"]

    with pytest.raises(ValueError):
        record_eval(
            "research_quality",
            "baseline-x",
            code_root=tmp_path,
            output_refs=["baseline-x"],
            recorded_seq=2,          # 不大于现有最大 → 版本序倒挂，拒绝
            new_version=True,
        )
    with pytest.raises(ValueError):
        record_eval(                 # 缺 recorded_seq → 拒绝
            "research_quality", "baseline-x", code_root=tmp_path, new_version=True
        )
    assert len(read_records(tmp_path, "tasks")) == 2, "两次拒绝都不得留下半截数据"
