"""`budget_gate.py` —— **第 6 步预算闸门**（`Ch6 §D.5` / `N6.3-08` / `N6.3-09`）。

## 一句话

第 6 步（核验）在**预算到限时停止深挖**，并把主张**转待核验 + 保留可重入任务** ——
`Ch6 §D.5` 称这是设计里"**可验收的行为定义**"：到限后任务状态 = 待核验 **且** 已入队
**且** 有日志 **且** 可重跑；**绝不静默丢弃、绝不把未完成结论标为已验证**。

## 三类预算取先到者（`Ch6 §D.5` 逐条）

| 预算类 | 字段 | 说明 |
|---|---|---|
| **时间** | `deadline` | 任务截止时刻 |
| **计算** | `max_model_calls` | 模型调用数上限；`research_cap(claim)`（`Ch6 §B.2`）给出**上限** |
| **检索** | `max_searches` | 检索次数上限 |

- **取先到者** = 三类里**最先触限**的那一类决定停止点（`Ch6 §D.5`：`research_cap` 给上限，三者取先到者）。
- **`research_cap` 仅由经济重要性决定**，与 `tier` / `quality` **无关**（`Ch6 §B.2` 明文禁令）：
  本模块**调用** `scripts/decision/triage.py::research_cap`（**唯一** `BUDGET_MAP` 真源，`G-06`），**不复制**字典表。
- 有效计算上限 = `min(配置的 max_model_calls, research_cap(claim))` —— 一手但低重要性也不深挖。

## 参数不内置（`00_开发Agent开工提示词 §6.1` / `Ch11 §D.2`）

预算值与运行时刻**一律**走 `system/config/freeze.py::get_param(...)`（**唯一参数读口**）：
`p09`（`public_data_and_budget`，`blocking_targets` 含 `Ch6 §D.5`）与 `p07`（`run_schedule_and_latency_target`）。
具体数值落在 `rules/budget.yaml`（`Ch6 §D.5`："实现方配置"）。

**缺文件不得静默兜底**（`§6.1`：缺值必须有**明确兜底或明确降级**）：本模块给出**两条确定路径** ——
① 调用方给**显式** `defaults`；② 否则**响亮失败** `BudgetConfigMissing`。绝不静默取 `0` / `None`。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

TIME_CLASS = "time"
"""时间预算（`deadline`）。"""

COMPUTE_CLASS = "compute"
"""计算预算（`max_model_calls`，受 `research_cap` 上界约束）。"""

RETRIEVAL_CLASS = "retrieval"
"""检索预算（`max_searches`）。"""

BUDGET_CLASSES: tuple[str, str, str] = (TIME_CLASS, COMPUTE_CLASS, RETRIEVAL_CLASS)
"""三类预算（`Ch6 §D.5`）。顺序即**确定性平手裁决**次序。"""

BUDGET_RULES_RELPATH = "rules/budget.yaml"
"""预算参数文件（`Ch6 §D.5`：实现方配置；`rules/` 0444，由主理人经 `lock_rules.py` 落）。"""

BUDGET_PARAM_ID = "p09"
"""`freeze.yaml` 的"公开数据与预算"参数（`blocking_targets` 含 `Ch6 §D.5`）。"""

RUN_SCHEDULE_PARAM_ID = "p07"
"""`freeze.yaml` 的"运行时刻与延迟目标"参数（`Ch6 §D.5` 的"运行时刻"）。"""

_PENDING = "pending_verification"
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_LIMIT_KEYS = ("deadline", "max_model_calls", "max_searches")


class BudgetConfigMissing(RuntimeError):
    """缺 `rules/budget.yaml` **且**未给显式缺省 —— **响亮失败**（不静默兜底，`§6.1`）。"""


class BudgetStateError(RuntimeError):
    """预算到限需把主张置 `pending_verification`，但状态机不允许 / 主张不存在 —— **响亮失败**。"""


@dataclass(frozen=True)
class BudgetLimits:
    """一次核验的**三类预算上限**（解析自配置 + `research_cap`）。"""

    deadline: datetime | None
    compute_limit: int | None
    search_limit: int | None
    research_cap: int
    source: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class BudgetUsage:
    """某次核验的**预算消耗**（观察值）。"""

    now: datetime
    model_calls_used: int = 0
    searches_used: int = 0
    started_at: datetime | None = None


@dataclass(frozen=True)
class BudgetDecision:
    """预算闸门判定（`Ch6 §D.5`：三类**取先到者**）。"""

    exhausted: bool
    binding: tuple[str, ...] = ()
    first_binding: str | None = None
    ratios: dict[str, float] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateOutcome:
    """`apply_budget_gate` 的结果（到限行为：待核验 + 可重入任务）。"""

    exhausted: bool
    decision: BudgetDecision
    claim_status_before: str | None = None
    status_written: bool = False
    task_id: str | None = None
    notes: tuple[str, ...] = ()


def research_cap_for(importance_class: str) -> int:
    """研究投入上限（**仅由经济重要性决定**）—— **调用** `triage.research_cap`，不重造（`G-06`）。

    `research_cap` 只读 `importance_class`，其余字段（tier / quality / 时间）**物理上不可影响**它；
    因此这里用一个**仅承载重要性**的 `DecisionView` 复用同一真源。
    """
    from scripts.decision.triage import DecisionView, research_cap

    view = DecisionView(
        claim_id="",
        tier="primary",
        importance_class=str(importance_class),
        first_seen_at=_EPOCH,
        direct_knowledge="unknown",
        method_reproducible=False,
        caliber_match=False,
        independent_evidence_count=0,
    )
    return int(research_cap(view))


def _parse_dt(value: Any) -> datetime | None:
    """把 `datetime` / ISO 串解析为 `datetime`；`None` 原样返回。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _as_mapping(node: Any) -> Mapping[str, Any] | None:
    return node if isinstance(node, Mapping) else None


def _configured_source(root: Path, defaults: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], str, list[str]]:
    """解析预算值来源：`rules/budget.yaml` > `freeze p09`（数值映射）> 显式 `defaults`；皆无 → 响亮失败。"""
    notes: list[str] = []
    rules_path = root / BUDGET_RULES_RELPATH
    if rules_path.exists():
        from config.rules import load_yaml

        return load_yaml(BUDGET_RULES_RELPATH, root), BUDGET_RULES_RELPATH, notes

    from config.freeze import get_param

    p09 = get_param(BUDGET_PARAM_ID, root)
    budget_cfg = _as_mapping(p09.effective_value)
    if budget_cfg is not None and any(k in budget_cfg for k in _LIMIT_KEYS):
        notes.append(
            f"budget source = freeze:{BUDGET_PARAM_ID}（value_source={p09.value_source}）"
        )
        return budget_cfg, f"freeze:{BUDGET_PARAM_ID}", notes

    if defaults is not None:
        notes.append("rules/budget.yaml 缺失且 freeze 预算值为 tbd：使用调用方**显式**缺省")
        return dict(defaults), "explicit_defaults", notes

    raise BudgetConfigMissing(
        f"缺 {BUDGET_RULES_RELPATH}，且 {BUDGET_PARAM_ID} 的 budget 值非数值映射、亦未提供显式缺省 —— "
        "拒绝静默兜底（Ch6 §D.5 / 00_开发Agent开工提示词 §6.1）；"
        f"请在 {BUDGET_RULES_RELPATH} 落预算值，或显式传入 defaults"
    )


def load_budget_limits(
    code_root: str | Path,
    *,
    importance_class: str,
    defaults: Mapping[str, Any] | None = None,
) -> BudgetLimits:
    """解析三类预算上限（`Ch6 §D.5`）。

    - 有效计算上限 = `min(配置 max_model_calls, research_cap(importance))`；
    - 缺配置且无显式缺省 → `BudgetConfigMissing`（**醒目失败**）。
    """
    root = Path(code_root)
    raw, source, notes = _configured_source(root, defaults)

    from config.freeze import get_param

    schedule = get_param(RUN_SCHEDULE_PARAM_ID, root)
    schedule_value = _as_mapping(schedule.effective_value)
    if schedule_value is not None:
        notes.append(
            f"run_time = freeze:{RUN_SCHEDULE_PARAM_ID}.time_value="
            f"{schedule_value.get('time_value')}（运行时刻，Ch6 §D.5）"
        )

    deadline = _parse_dt(raw.get("deadline"))
    cap = research_cap_for(importance_class)
    configured_calls = raw.get("max_model_calls")
    compute_limit: int | None
    if configured_calls is None:
        compute_limit = cap
        notes.append(f"未配置 max_model_calls ⇒ 计算上限 = research_cap = {cap}")
    else:
        compute_limit = min(int(configured_calls), cap)
        if int(configured_calls) > cap:
            notes.append(f"research_cap={cap} < 配置 max_model_calls={int(configured_calls)} ⇒ 取 cap")
    search_limit = None if raw.get("max_searches") is None else int(raw["max_searches"])

    return BudgetLimits(
        deadline=deadline,
        compute_limit=compute_limit,
        search_limit=search_limit,
        research_cap=cap,
        source=source,
        notes=tuple(notes),
    )


def _time_ratio(deadline: datetime | None, usage: BudgetUsage) -> float:
    """时间预算的**消耗比**（用于"取先到者"的确定性比较）。"""
    if deadline is None:
        return 0.0
    if usage.started_at is None or deadline <= usage.started_at:
        return 1.0 if usage.now >= deadline else 0.0
    span = (deadline - usage.started_at).total_seconds()
    used = (usage.now - usage.started_at).total_seconds()
    return used / span if span > 0 else 0.0


def evaluate_budget(limits: BudgetLimits, usage: BudgetUsage) -> BudgetDecision:
    """判定是否到限，并给出**取先到者**的结论（纯函数，无副作用；`Ch6 §D.5`）。"""
    ratios: dict[str, float] = {TIME_CLASS: _time_ratio(limits.deadline, usage)}
    binding: list[str] = []
    if limits.deadline is not None and usage.now >= limits.deadline:
        binding.append(TIME_CLASS)

    for name, used, limit in (
        (COMPUTE_CLASS, usage.model_calls_used, limits.compute_limit),
        (RETRIEVAL_CLASS, usage.searches_used, limits.search_limit),
    ):
        if limit is not None and limit > 0:
            ratios[name] = used / limit
            if used >= limit:
                binding.append(name)
        else:
            ratios[name] = 0.0

    first: str | None = None
    if binding:
        first = max(binding, key=lambda c: (ratios[c], -BUDGET_CLASSES.index(c)))
    return BudgetDecision(
        exhausted=bool(binding),
        binding=tuple(sorted(binding)),
        first_binding=first,
        ratios=dict(ratios),
    )


def _ensure_pending(code_root: Path, claim_id: str) -> tuple[str, bool]:
    """确保主张处于 `pending_verification`（到限行为②，`Ch6 §D.5`）。

    - 已是 `pending_verification` → **no-op**（返回 `(状态, False)`；状态机不允许自环）；
    - 否则**调用** `scripts.claim.transition.transition`（**唯一**状态写入者）——
      若设计状态机不允许该迁移 → `BudgetStateError`（**响亮**，**绝不静默造状态**）。
    """
    from schema.store import read_records

    rows = [r for r in read_records(code_root, "claims") if r.get("claim_id") == claim_id]
    if not rows:
        raise BudgetStateError(f"facts/claims.jsonl 无 claim_id={claim_id!r} —— 不凭空重建")
    latest = max(rows, key=lambda r: int(r.get("recorded_seq") or 0))
    status = str(latest.get("status") or "")
    if status == _PENDING:
        return status, False

    from scripts.claim.transition import ClaimTransitionError, transition

    try:
        transition(code_root, claim_id, _PENDING)
    except ClaimTransitionError as exc:
        raise BudgetStateError(
            f"预算到限要求置 {_PENDING}，但 {status} -> {_PENDING} 非法（Ch6 §E.1 状态机）: {exc}"
        ) from exc
    return status, True


def _enqueue_verification(
    code_root: Path,
    claim_id: str,
    limits: BudgetLimits,
    decision: BudgetDecision,
    usage: BudgetUsage,
    *,
    alt_explanation: str,
    public_entry: str,
) -> str:
    """生成**可重入** `VerificationTask` 并入队（到限行为③④，`Ch6 §D.5`）。

    幂等：同 `idempotency_key` 已存在 → 不再重复建单（返回既有 `task_id`）。
    """
    from schema.models import Task, TaskStatus, TaskType
    from schema.store import append_records, read_records

    key = f"verify_budget::{claim_id}::{decision.first_binding or 'unspecified'}"
    existing = {t.get("idempotency_key") for t in read_records(code_root, "tasks")}
    if key in existing:
        return f"task_{key}"

    task = Task(
        task_id=f"task_{key}",
        task_type=TaskType.verify,
        status=TaskStatus.queued,
        idempotency_key=key,
        input_refs=[claim_id],
        parent_context={
            "gate": "budget",
            "binding": sorted(decision.binding),
            "first_binding": decision.first_binding,
            "budget_used": {
                "model_calls": usage.model_calls_used,
                "searches": usage.searches_used,
            },
            "limits": {
                "compute_limit": limits.compute_limit,
                "search_limit": limits.search_limit,
                "research_cap": limits.research_cap,
            },
            "alt_explanation_hint": alt_explanation,
            "public_entry": public_entry,
        },
        cost={"tokens": None, "searches": usage.searches_used, "model_calls": usage.model_calls_used},
    )
    append_records(code_root, "tasks", [task])
    return task.task_id


def apply_budget_gate(
    code_root: str | Path,
    claim_id: str,
    *,
    importance_class: str,
    usage: BudgetUsage,
    defaults: Mapping[str, Any] | None = None,
    alt_explanation: str = "",
    public_entry: str = "",
) -> GateOutcome:
    """**闸门动作**：未到限 → 无副作用；到限 → 停深挖 + 转待核验 + 保留可重入任务（`Ch6 §D.5`）。

    ★ 到限时**绝不**把未完成结论标为已验证：只把主张置 `pending_verification` 并**入队**。
    """
    root = Path(code_root)
    limits = load_budget_limits(root, importance_class=importance_class, defaults=defaults)
    decision = evaluate_budget(limits, usage)
    if not decision.exhausted:
        return GateOutcome(exhausted=False, decision=decision)

    status_before, status_written = _ensure_pending(root, claim_id)
    task_id = _enqueue_verification(
        root,
        claim_id,
        limits,
        decision,
        usage,
        alt_explanation=alt_explanation,
        public_entry=public_entry,
    )
    notes = list(limits.notes)
    notes.append(
        "到限：停深挖 + 主张置 pending_verification + 生成可重入 VerificationTask"
        "（不丢弃、不伪装完成，Ch6 §D.5）"
    )
    if not status_written:
        notes.append(f"主张原已处于 {_PENDING}（状态机不允许自环）⇒ 未再写状态")
    return GateOutcome(
        exhausted=True,
        decision=decision,
        claim_status_before=status_before,
        status_written=status_written,
        task_id=task_id,
        notes=tuple(notes),
    )
