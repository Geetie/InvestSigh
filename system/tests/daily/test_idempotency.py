"""AC-3：**同日重跑幂等**（`Ch8 §F` / `Ch9 §3.3.4` / `§3.4.7` / `Ch1 §C.3`）的正反两向测试。

锚点：`Ch8 §N8.4-08`（同日同输入重跑 N 次，`events` / `recommendations` 行数不变）/
`Ch9 §3.4.7`（事件指纹基于**根来源**）/ `Ch1 §C.3`（任务幂等键 `(gap_id 或 claim_id)+task_type`）。

★ 复用证据：本模块的键函数**全部委托**既有真源实现（`scripts.tasks.gap_to_task` /
`scripts.graph.fingerprint`），**不新造机制**（`G-06` 唯一真源）。
"""

from __future__ import annotations

import json
from pathlib import Path

from schema.models import Event, EventType
from schema.store import read_records
from scripts.daily import idempotency


def _append_raw(root: Path, stem: str, rows: list[dict]) -> None:
    path = root / "facts" / f"{stem}.jsonl"
    with open(path, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _count(root: Path, stem: str) -> int:
    return len(read_records(root, stem))


# ── 复用证据：键函数委托既有真源 ────────────────────────────────────────────

def test_task_key_delegates_to_gap_to_task() -> None:
    """任务幂等键 == `scripts.tasks.gap_to_task.idempotency_key`（逐字复用）。"""
    from scripts.tasks.gap_to_task import idempotency_key

    assert idempotency.task_key("g1", None, "research") == idempotency_key("g1", None, "research")
    assert idempotency.task_key(None, "c1", "recheck") == "recheck::c1"


def test_event_key_falls_back_to_root_source_fingerprint() -> None:
    """无 `event_id` 时现算指纹（基于根来源，非标题）→ 稳定且非空。"""
    row = {
        "event_type": "earnings",
        "company_ids": ["c1"],
        "metric": "revenue",
        "period_bucket": "2026Q1",
        "occurred_at": "2026-09-16T00:00:00+00:00",
        "root_source_id": "src1",
    }
    key_a = idempotency.event_key_of(row)
    key_b = idempotency.event_key_of(dict(row))
    assert key_a and key_a == key_b


# ── 正向：无重复 → 守卫通过 ─────────────────────────────────────────────────

def test_no_duplicates_passes(code_root: Path) -> None:
    _append_raw(code_root, "events", [{"event_id": "e1"}, {"event_id": "e2"}])
    _append_raw(
        code_root,
        "recommendations",
        [{"security_id": "s1", "start_date": "2026-09-16", "version": 1}],
    )
    report = idempotency.check(code_root)
    assert report.passed, [v.reason for v in report.violations]
    assert report.scanned["events"] == 2
    assert report.scanned["recommendations"] == 1


# ── 反向：重复幂等键被拦下 ──────────────────────────────────────────────────

def test_recommendation_duplicate_is_rejected(code_root: Path) -> None:
    _append_raw(
        code_root,
        "recommendations",
        [
            {"security_id": "s1", "start_date": "2026-09-16", "version": 1, "recommendation_id": "r1"},
            {"security_id": "s1", "start_date": "2026-09-16", "version": 1, "recommendation_id": "r2"},
            {"security_id": "s2", "start_date": "2026-09-16", "version": 1, "recommendation_id": "r3"},
        ],
    )
    dups = idempotency.duplicates(code_root, "recommendations", idempotency.recommendation_key_of)
    assert dups == ["s1::2026-09-16::1"]

    report = idempotency.check(code_root)
    assert not report.passed
    assert any("重复幂等键" in v.reason for v in report.violations)


def test_event_duplicate_is_rejected(code_root: Path) -> None:
    _append_raw(code_root, "events", [{"event_id": "e1"}, {"event_id": "e1"}])
    report = idempotency.check(code_root)
    assert not report.passed


# ── 正向：去重追加 → 行数不变（w/c 语义） ───────────────────────────────────

def test_append_deduped_keeps_line_count_stable(code_root: Path) -> None:
    events = [
        Event(event_id="e1", event_type=EventType.earnings),
        Event(event_id="e2", event_type=EventType.guidance),
    ]
    wrote = idempotency.append_deduped(code_root, "events", events, idempotency.event_key_of)
    assert wrote == 2
    before = _count(code_root, "events")

    rewrote = idempotency.append_deduped(code_root, "events", events, idempotency.event_key_of)
    after = _count(code_root, "events")

    assert rewrote == 0
    assert before == after == 2
    assert idempotency.duplicates(code_root, "events", idempotency.event_key_of) == []
