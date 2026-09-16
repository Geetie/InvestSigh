"""`fingerprint.py` —— 事件去重身份指纹（`Ch9 §3.4.7` / `N9.1-14`）。

指纹定义（逐字对齐 `Ch9 §3.4.7`）：

```
sha256( event_type ‖ sorted(company_ids) ‖ metric ‖ period_bucket
        ‖ bucket(occurred_at, 1d) ‖ root_source_id )
```

**关键：基于根来源而非标题** → 十篇转述 = **1 个 event + N 条 propagation**（T01）。

**误并 / 漏并纠正**（`Ch9 §3.4.7` / `N9.1-14`）：提供 `split` / `merge` 任务 +
`event_alias` 记录，**人工可干预**（对齐 `TaskType.dedup_override`，`schema/models.py`）。

★ `occurred_at` 一律归一到 **UTC 日桶**：同一时刻的不同时区书面表示 → **同一指纹**
  （`Ch9 §2.2`：时间语义五分开；桶粒度 = 1 日）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from typing import Any, Iterable, Mapping

# 分隔符（设计用 "‖"）。组件均为受控 token（枚举值 / 稳定 id / 日期），不含该分隔符。
_SEP = "\u2016"

DAY_BUCKET_FORMAT = "%Y-%m-%d"


def _utc_day_bucket(occurred_at: datetime | str) -> str:
    """把事件发生时间归一到 **UTC 日桶**（`YYYY-MM-DD`）。

    时区感知时间 → 转 UTC；naive 时间 → **按 UTC 解释**（不臆测本地时区）。
    不可解析 → `ValueError`（**不静默**取今天）。
    """
    if isinstance(occurred_at, str):
        try:
            moment = datetime.fromisoformat(occurred_at)
        except ValueError as exc:
            raise ValueError(f"occurred_at 不是合法 ISO 时间: {occurred_at!r}") from exc
    elif isinstance(occurred_at, datetime):
        moment = occurred_at
    else:
        raise TypeError(f"occurred_at 类型不支持: {type(occurred_at).__name__}")
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime(DAY_BUCKET_FORMAT)


def event_fingerprint(
    *,
    event_type: str,
    company_ids: Iterable[str],
    metric: str | None,
    period_bucket: str | None,
    occurred_at: datetime | str,
    root_source_id: str,
) -> str:
    """按 `Ch9 §3.4.7` 计算事件去重指纹（hex sha256）。

    组件归一：`event_type` / `root_source_id` 必填非空；`company_ids` **排序去重**后
    以逗号连接；`metric` / `period_bucket` 缺失记空串。缺失必填项 → `ValueError`。
    """
    if not event_type:
        raise ValueError("event_type 必填且非空（指纹组成项）")
    if not root_source_id:
        raise ValueError("root_source_id 必填且非空（指纹**基于根来源**，非标题）")
    companies = ",".join(sorted(set(company_ids)))
    bucket = _utc_day_bucket(occurred_at)
    canonical = _SEP.join(
        [
            str(event_type),
            companies,
            "" if metric is None else str(metric),
            "" if period_bucket is None else str(period_bucket),
            bucket,
            str(root_source_id),
        ]
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _get(obj: Any, key: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def fingerprint_of_event(event: Any) -> str:
    """对一条事件对象 / dict 计算指纹（字段名与 `Event` 模型逐字一致）。"""
    return event_fingerprint(
        event_type=str(_get(event, "event_type") or ""),
        company_ids=list(_get(event, "company_ids") or []),
        metric=_get(event, "metric"),
        period_bucket=_get(event, "period_bucket"),
        occurred_at=_get(event, "occurred_at"),
        root_source_id=str(_get(event, "root_source_id") or ""),
    )


def event_alias_map(events: Iterable[Any]) -> dict[str, str]:
    """由事件的 `event_alias` 字段构建 `别名指纹 → 规范 event_id` 映射。

    `Event.event_alias`（`schema/models.py`）= 误并 / 漏并的**人工纠正入口**：
    列表成员是被并入该事件的其它指纹。规范键取事件自身的 `event_id`。
    """
    mapping: dict[str, str] = {}
    for ev in events:
        canonical = str(_get(ev, "event_id") or "")
        if not canonical:
            continue
        for alias in _get(ev, "event_alias") or []:
            alias = str(alias)
            if alias and alias != canonical:
                mapping[alias] = canonical
    return mapping


def resolve_fingerprint(fingerprint: str, aliases: Mapping[str, str]) -> str:
    """把可能的别名指纹解析到规范 `event_id`（无别名 → 原样返回）。"""
    return aliases.get(fingerprint, fingerprint)


@dataclass(frozen=True)
class DedupOverridePlan:
    """一次人工去重纠正（`split` / `merge`）的计划，落成 `dedup_override` 任务。"""

    action: str                       # "split" | "merge"
    event_refs: tuple[str, ...]
    idempotency_key: str
    reason: str


def plan_split(event_id: str, *, reason: str = "") -> DedupOverridePlan:
    """计划把一个**误并**的事件拆开（人工纠正入口，`Ch9 §3.4.7`）。"""
    if not event_id:
        raise ValueError("split 需要非空 event_id")
    return DedupOverridePlan(
        action="split",
        event_refs=(event_id,),
        idempotency_key=f"dedup_override::split::{event_id}",
        reason=reason or "manual_split_over_merged_event",
    )


def plan_merge(event_ids: Iterable[str], *, reason: str = "") -> DedupOverridePlan:
    """计划把**漏并**的多个事件合并（人工纠正入口，`Ch9 §3.4.7`）。"""
    refs = tuple(sorted({e for e in event_ids if e}))
    if len(refs) < 2:
        raise ValueError("merge 需要至少两个不同的非空 event_id")
    return DedupOverridePlan(
        action="merge",
        event_refs=refs,
        idempotency_key="dedup_override::merge::" + ",".join(refs),
        reason=reason or "manual_merge_split_events",
    )


def override_task(plan: DedupOverridePlan) -> Any:
    """把纠正计划落成 `Task`（`task_type=dedup_override`，`Ch1 §C.3`）。

    返回 `Task` 对象；**写入由调用方经 `schema.store.append_records` 完成**
    （追加式不可变，唯一写入口）。
    """
    from schema.models import Task, TaskStatus, TaskType

    return Task(
        task_id=f"task_{plan.idempotency_key}",
        task_type=TaskType.dedup_override,
        status=TaskStatus.queued,
        idempotency_key=plan.idempotency_key,
        input_refs=list(plan.event_refs),
        parent_context={
            "action": plan.action,
            "reason": plan.reason,
            "anchor": "Ch9 §3.4.7",
        },
    )


def _bucket_of(value: date) -> str:
    """便利：把一个 `date` 直接格式化为日桶（与 `_utc_day_bucket` 同构）。"""
    return value.strftime(DAY_BUCKET_FORMAT)
