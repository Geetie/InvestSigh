"""事件指纹与去重身份（`Ch9 §3.4.7` / `N9.1-14`）测试。

覆盖：根来源口径（十篇转述 = 1 事件）、时区归一（AC-06）、`split`/`merge`/`event_alias`。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts.graph.fingerprint import (
    event_alias_map,
    event_fingerprint,
    override_task,
    plan_merge,
    plan_split,
    resolve_fingerprint,
)


def _fp(**over: object) -> str:
    base: dict[str, object] = dict(
        event_type="order",
        company_ids=["NVDA"],
        metric="order_value",
        period_bucket="FY2026Q2",
        occurred_at=datetime(2026, 1, 2, 16, 0, tzinfo=timezone.utc),
        root_source_id="src_root_1",
    )
    base.update(over)
    return event_fingerprint(**base)  # type: ignore[arg-type]


def test_same_root_source_same_fingerprint_ten_reports() -> None:
    """十篇转述**同一根来源** → **同一指纹**（T01：1 event + N propagation）。"""
    assert _fp() == _fp(metric="order_value")


def test_different_root_source_differs() -> None:
    assert _fp(root_source_id="src_root_1") != _fp(root_source_id="src_root_2")


def test_company_ids_order_independent() -> None:
    assert _fp(company_ids=["b", "a"]) == _fp(company_ids=["a", "b"])


def test_timezone_normalized_to_utc_day_bucket() -> None:
    """★ AC-06：不同时区书面表示、同一 UTC 时刻 → 同一指纹。"""
    jst = datetime(2026, 1, 3, 1, 0, tzinfo=timezone(timedelta(hours=9)))
    utc = datetime(2026, 1, 2, 16, 0, tzinfo=timezone.utc)
    assert _fp(occurred_at=jst) == _fp(occurred_at=utc)
    # 字符串 ISO 表示同样归一
    assert _fp(occurred_at="2026-01-03T01:00:00+09:00") == _fp(occurred_at=utc)
    # 相差一日（UTC）→ 指纹不同
    assert _fp(occurred_at=jst) != _fp(occurred_at=datetime(2026, 1, 3, 16, 0, tzinfo=timezone.utc))


def test_alias_resolution_and_override_tasks() -> None:
    events = [{"event_id": "E1", "event_alias": ["E1old", "E1legacy"]}]
    aliases = event_alias_map(events)
    assert aliases == {"E1old": "E1", "E1legacy": "E1"}
    assert resolve_fingerprint("E1old", aliases) == "E1"
    assert resolve_fingerprint("E9", aliases) == "E9"

    split_plan = plan_split("E1", reason="wrong_merge")
    assert split_plan.action == "split" and split_plan.event_refs == ("E1",)
    split_task = override_task(split_plan)
    assert split_task.task_type.value == "dedup_override"
    assert split_task.idempotency_key.startswith("dedup_override::split::")

    merge_plan = plan_merge(["E2", "E1", "E2"], reason="missed_merge")
    assert merge_plan.event_refs == ("E1", "E2")
    assert override_task(merge_plan).input_refs == ["E1", "E2"]
