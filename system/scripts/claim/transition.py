#!/usr/bin/env python3
"""`transition.py` —— 主张**五态状态机** + `superseded` 传播（`Ch6 §E` · `Ch6 N6.3-10/11/18`）。

## 有限状态机（`Ch6 §E.1` 状态图的逐边实现）

```
[入口] active（采集层默认 status，schema/models.py::Claim.status）
        │ 仅此一条入边（强制显式进入状态机）
        ▼
pending_verification ──► supported ──► disputed ──► refuted ──► superseded(终态)
     │  ▲                    │            │            │
     │  └── refuted ─────────┼────────────┘            │
     │  （反证被撤回，重开）  │            │            │
     └──► disputed / refuted │            │            │
                            └────────────┴────────────┘
                            任意非终态 ──► superseded（上游版本事件）
```

- **允许迁移表**（`ALLOWED_TRANSITIONS`）逐条对齐 `Ch6 §E.1`；表的补集（含自环、逆回、终态出边）
  一律**非法**：`assert_transition` 抛 `IllegalTransition`，**不静默兜底、不自动纠正**（`Ch6 §E.2`）。
- `superseded` 为**终态**（`Ch6 §E.5`）；`refuted` **可重开**（`refuted → pending_verification`）。
- `active` 是采集层默认值，**不属于** `Ch6 §E.1` 五态；本模块把它当**状态机入口别名**，
  **只允许** `active → pending_verification`（强制显式进入；未核验不得直跳 `supported`）。

## 追加式写入（`Ch9 §3.4.2`）

状态迁移**不改历史行**：每次迁移**追加**一行带新 `status` 与递增 `recorded_seq` 的 claim 版本，
`as_of` 按业务键取 `recorded_seq` 最大者（`Ch9 §3.4.1`）。

## `superseded` 传播（复用，不重造；`Ch6 §E.4`）

调用 `scripts/graph/forward_closure(claim_id, max_depth=3, detect_cycle=True)`，对每个下游对象入一条
`recheck` 任务（`TaskType.recheck`，`Ch9 §2.1.6` 控制面对象）承载"标记 stale"，
幂等键 `recheck::<claim_id>::<type>::<id>`（重跑不重复建单，`Ch9 §N9.1-26`）；
`parent_context.requires_recheck = (type ∈ {baseline, recommendation})`（`Ch6 §E.4`）。
`forward_closure` 不可解析 → **写库前**抛 `PropagationUnavailable`（不留半截数据）。

## 退出码（CLI，`CONVENTIONS.md::G-01`）

`0` 迁移完成 / 判定合法 · `1` **非法迁移 / 定位无效 / 传播不可用**（被检对象不合规）· `2` 输入异常。
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

CLAIM_STATES = ("pending_verification", "supported", "disputed", "refuted", "superseded")
"""`Ch6 §E.1` 五态（唯一权威取值域）。"""

INITIAL_STATE = "pending_verification"
"""提取（②③④）完成后的**初始态**（`Ch6 §E.1`）。"""

INGEST_DEFAULT_STATUS = "active"
"""采集层默认 `status`（`schema/models.py::Claim.status`，真库实测行即 `"active"`）。"""

TERMINAL_STATES = frozenset({"superseded"})
"""终态（`Ch6 §E.5`）：无出边。"""

VERSION_KINDS = frozenset({"forecast_revision", "financial_restatement", "source_retraction"})
"""三类版本事件（`Ch6 §E.3` / `Ch9 §2.3.2`）。"""

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending_verification": frozenset({"supported", "disputed", "refuted", "superseded"}),
    "supported": frozenset({"disputed", "refuted", "superseded"}),
    "disputed": frozenset({"supported", "refuted", "superseded"}),
    "refuted": frozenset({"pending_verification", "disputed", "superseded"}),
    "superseded": frozenset(),
}
"""**允许迁移表**（`Ch6 §E.1` 逐边）。表外一律非法。"""

ENTRY_TRANSITIONS: dict[str, frozenset[str]] = {
    INGEST_DEFAULT_STATUS: frozenset({INITIAL_STATE}),
}
"""状态机入口别名：采集层默认 `active` **只允许**进入初始态（强制显式进入）。"""

_RECHECK_OBJECT_TYPES = frozenset({"baseline", "recommendation"})
"""`Ch6 §E.4`：仅对"依赖结论"（baseline / recommendation）入复查队列。"""

_LOCATOR_GATED_TARGETS = frozenset({"pending_verification", "supported", "disputed", "refuted"})
"""这些迁移目标受"定位前置门"约束（`Ch6 §D` 程序拦截）；retirement(`superseded`) 不受限。"""

_GRAPH_CANDIDATE_MODULES = ("scripts.graph", "scripts.graph.traversal", "scripts.graph.propagation")


class ClaimTransitionError(RuntimeError):
    """主张状态迁移类错误的基类（一律**响亮拒绝**，不静默兜底）。"""


class UnknownClaimStatus(ClaimTransitionError):
    """出现 `Ch6 §E.1` 五态（及入口别名）之外的取值 —— 未知状态。"""


class IllegalTransition(ClaimTransitionError):
    """合法状态之间的**非法迁移**（表外迁移 / 终态出边 / 序或时间倒挂 / 非法 `version_kind`）。"""


class ClaimNotFound(ClaimTransitionError):
    """`facts/claims.jsonl` 中不存在所请求的 `claim_id`（不得凭空重建）。"""


class ClaimLocatorInvalid(ClaimTransitionError):
    """迁移目标进入证据集，但主张定位无效（`locator_check` 命中违例，`Ch6 §D` 程序拦截）。"""


class PropagationUnavailable(ClaimTransitionError):
    """`superseded` 传播所需的 `scripts/graph/forward_closure` 不可解析（写库前失败，不留半截数据）。"""


@dataclass
class TransitionResult:
    """一次状态迁移的结果（含 `superseded` 传播的下游与新建 `recheck` 任务）。"""

    claim_id: str
    from_status: str
    to_status: str
    recorded_seq: int
    version_kind: str | None = None
    downstream: list[tuple[str, str]] = field(default_factory=list)
    recheck_tasks: list[str] = field(default_factory=list)
    reason: str = ""


def allowed_targets(from_status: str) -> frozenset[str] | None:
    """给定源状态，返回其**允许的目标集合**；源状态未知 → `None`。"""
    if from_status in ALLOWED_TRANSITIONS:
        return ALLOWED_TRANSITIONS[from_status]
    if from_status in ENTRY_TRANSITIONS:
        return ENTRY_TRANSITIONS[from_status]
    return None


def can_transition(from_status: str, to_status: str) -> bool:
    """`from_status -> to_status` 是否在**允许迁移表**内（纯判定，无副作用）。"""
    targets = allowed_targets(from_status)
    if targets is None:
        return False
    return to_status in targets


def assert_transition(from_status: str, to_status: str) -> None:
    """断言迁移合法；否则抛 `UnknownClaimStatus` / `IllegalTransition`（**响亮拒绝**）。"""
    if from_status not in ALLOWED_TRANSITIONS and from_status not in ENTRY_TRANSITIONS:
        raise UnknownClaimStatus(
            f"未知主张状态 from={from_status!r}；合法状态见 Ch6 §E.1: {CLAIM_STATES}"
            f"（入口别名: {sorted(ENTRY_TRANSITIONS)}）"
        )
    if to_status not in CLAIM_STATES:
        raise UnknownClaimStatus(
            f"未知目标状态 to={to_status!r}；合法状态见 Ch6 §E.1: {CLAIM_STATES}"
        )
    if not can_transition(from_status, to_status):
        raise IllegalTransition(
            f"非法迁移 {from_status!r} -> {to_status!r}（Ch6 §E.1 有限状态机；"
            f"允许目标: {sorted(allowed_targets(from_status))}）—— 本模块不静默兜底、不自动纠正"
        )


def _module_available(modname: str) -> bool:
    """模块是否可导入（已加载或 `find_spec` 命中）——不导模块本体，避免急切副作用。"""
    if modname in sys.modules:
        return True
    try:
        return importlib.util.find_spec(modname) is not None
    except (ImportError, ValueError):
        return False


def resolve_forward_closure() -> Callable[..., Iterable[Any]] | None:
    """**惰性**解析 `scripts/graph` 的 `forward_closure`（复用第九章传播，`G-06` 不另建）。

    候选模块逐个探测；全部不可用 → `None`（由调用方折叠为 `PropagationUnavailable`）。
    """
    for modname in _GRAPH_CANDIDATE_MODULES:
        if not _module_available(modname):
            continue
        module = importlib.import_module(modname)
        fn = getattr(module, "forward_closure", None)
        if fn is not None:
            return fn
    return None


def _validate_prior(row: Mapping[str, Any]) -> Any:
    """把最新历史行校验为 `schema.models.Claim`（三字段枚举域 / 必填项在此机械拦截）。"""
    from schema.models import Claim

    return Claim.model_validate(row)


def _latest_claim(root: Path, claim_id: str) -> tuple[Mapping[str, Any], list[Mapping[str, Any]]]:
    """取该 `claim_id` 的**最新版本**行（`recorded_seq` 最大者）与全部行。

    不存在 → `ClaimNotFound`（不得凭空重建）。
    """
    from schema.store import read_records

    rows = read_records(root, "claims")
    mine = [r for r in rows if r.get("claim_id") == claim_id]
    if not mine:
        raise ClaimNotFound(f"facts/claims.jsonl 中无 claim_id={claim_id!r}（不得凭空重建）")
    latest = max(mine, key=lambda r: int(r.get("recorded_seq") or 0))
    return latest, rows


def _source_index(root: Path) -> dict[str, Mapping[str, Any]]:
    """读 `facts/sources.jsonl` 建 `source_id -> 行` 索引（供定位前置门的来源侧交叉核对）。"""
    from schema.store import read_records

    return {str(r.get("source_id", "")): r for r in read_records(root, "sources")}


def _next_recorded_seq(rows: Sequence[Mapping[str, Any]], requested: int | None) -> int:
    """下一个版本序号：默认 = 全局现有最大 `recorded_seq` + 1；显式值**必须更大**（否则序倒挂 → 拒绝）。"""
    seqs = [int(r.get("recorded_seq") or 0) for r in rows]
    current_max = max(seqs) if seqs else 0
    if requested is None:
        return current_max + 1
    if int(requested) <= current_max:
        raise IllegalTransition(
            f"recorded_seq={requested} 不大于现有最大 {current_max} —— 版本序倒挂，拒绝"
        )
    return int(requested)


def _build_new_version(
    prior_obj: Any,
    to_status: str,
    recorded_seq: int,
    at: datetime,
    version_kind: str | None,
    supersedes: str | None,
) -> Any:
    """由原版本派生**新版本行**（仅改 `status` / 版本序号 / system_time / 版本链字段）。

    - 新版本 `first_seen_at` = `analyzed_at` = `at`（该版本进入系统的时刻）——使 `as_of`
      按"`first_seen_at ≤ as_of` 且 `recorded_seq` 最大"选取时，状态变化**在其发生后才可见**
      （`Ch9 §3.4.1`）。
    - `at` 早于原版本 `first_seen_at` → **时间倒挂**，拒绝。
    """
    from pydantic import ValidationError

    from schema.models import Claim

    if prior_obj.first_seen_at is not None and at < prior_obj.first_seen_at:
        raise IllegalTransition(
            f"新版本 first_seen_at={at.isoformat()} 早于原版本 "
            f"{prior_obj.first_seen_at.isoformat()} —— 时间倒挂，拒绝"
        )
    payload = prior_obj.model_dump(mode="json")
    payload["status"] = to_status
    payload["recorded_seq"] = recorded_seq
    payload["first_seen_at"] = at
    payload["analyzed_at"] = at
    if version_kind is not None:
        payload["version_kind"] = version_kind
    if supersedes is not None:
        payload["supersedes"] = supersedes
    try:
        return Claim.model_validate(payload)
    except ValidationError as exc:
        raise ClaimTransitionError(
            "新版本行未通过 Claim 校验（三字段 claim_nature / claim_form / official_claim_kind "
            f"维度不同，不得互换/合并）: {exc}"
        ) from exc


def _append_claim(root: Path, claim: Any) -> None:
    """**唯一写口**：追加一行 claim 版本（`schema.store.append_records`，追加式不可变）。"""
    from schema.store import append_records

    append_records(root, "claims", [claim])


def _normalize_ref(item: Any) -> tuple[str, str]:
    """把 `forward_closure` 的下游项归一化为 `(object_type, object_id)`。

    接受对象（`.object_type`/`.object_id`）或映射（`type`/`id`）；无法归一化 → **响亮拒绝**。
    """
    if isinstance(item, Mapping):
        obj_type = item.get("object_type") or item.get("type") or item.get("obj_type")
        obj_id = item.get("object_id") or item.get("id") or item.get("ref")
    else:
        obj_type = getattr(item, "object_type", None) or getattr(item, "type", None)
        obj_id = (
            getattr(item, "object_id", None)
            or getattr(item, "id", None)
            or getattr(item, "ref", None)
        )
    if not obj_type or not obj_id:
        raise ClaimTransitionError(
            "forward_closure 返回项无法归一化（需 .object_type/.object_id 或 dict type/id）: "
            f"{item!r}"
        )
    return (str(obj_type), str(obj_id))


def _existing_task_keys(root: Path) -> set[str]:
    """既有任务的幂等键集合（用于"重跑不重复建单"，`Ch9 §N9.1-26`）。"""
    from schema.store import read_records

    return {str(r.get("idempotency_key", "")) for r in read_records(root, "tasks")}


def _append_recheck_task(
    root: Path,
    key: str,
    claim_id: str,
    version_kind: str | None,
    obj_type: str,
    obj_id: str,
) -> None:
    """追加一条 `recheck` 任务（承载"标记 stale"与"入复查队列"，`Ch6 §E.4`）。"""
    from schema.models import Task, TaskStatus, TaskType
    from schema.store import append_records

    task = Task(
        task_id="task_{0}".format(key.replace("::", "_")),
        task_type=TaskType.recheck,
        status=TaskStatus.queued,
        idempotency_key=key,
        input_refs=[claim_id],
        parent_context={
            "invalidated_by": claim_id,
            "version_kind": version_kind,
            "stale_object_type": obj_type,
            "stale_object_id": obj_id,
            "requires_recheck": obj_type in _RECHECK_OBJECT_TYPES,
        },
    )
    append_records(root, "tasks", [task])


def _propagate(
    root: Path,
    claim_id: str,
    version_kind: str | None,
    forward_closure: Callable[..., Iterable[Any]],
) -> tuple[list[tuple[str, str]], list[str]]:
    """沿 `forward_closure` 把失效传播到下游：逐个入 `recheck` 任务（幂等）。"""
    downstream_raw = list(forward_closure(claim_id, max_depth=3, detect_cycle=True))
    refs = [_normalize_ref(item) for item in downstream_raw]
    existing = _existing_task_keys(root)
    created: list[str] = []
    for obj_type, obj_id in refs:
        key = f"recheck::{claim_id}::{obj_type}::{obj_id}"
        if key in existing:
            continue
        _append_recheck_task(root, key, claim_id, version_kind, obj_type, obj_id)
        existing.add(key)
        created.append(key)
    return refs, created


def transition(
    code_root: str | Path,
    claim_id: str,
    to_status: str,
    *,
    reason: str = "",
    version_kind: str | None = None,
    supersedes: str | None = None,
    recorded_at: datetime | None = None,
    recorded_seq: int | None = None,
    enforce_locator: bool = True,
    forward_closure_fn: Callable[..., Iterable[Any]] | None = None,
) -> TransitionResult:
    """执行一次**合法**状态迁移：校验迁移表 → （定位前置门）→ 追加新版本行 → （`superseded` 传播）。

    - 非法迁移 / 未知状态 / 未知 claim / 定位无效 / 传播不可用 → 抛 `ClaimTransitionError` 子类。
    - `reason` 仅供调用方 / CLI 记录，**不落库**（`Claim` 无该字段）。
    - `forward_closure_fn` 用于注入遍历实现（测试 / 定制）；缺省惰性复用 `scripts/graph`。
    """
    root = Path(code_root)
    prior_row, all_rows = _latest_claim(root, claim_id)
    prior_obj = _validate_prior(prior_row)
    from_status = str(prior_obj.status)
    assert_transition(from_status, to_status)

    if version_kind is not None and version_kind not in VERSION_KINDS:
        raise IllegalTransition(
            f"非法 version_kind={version_kind!r}；合法值见 Ch6 §E.3 / Ch9 §2.3.2: {sorted(VERSION_KINDS)}"
        )

    if enforce_locator and to_status in _LOCATOR_GATED_TARGETS:
        from scripts.validators.locator_check import claim_locator_problems

        problems = claim_locator_problems(prior_row, root, _source_index(root))
        if problems:
            detail = "; ".join(f"{code}: {text}" for code, text in problems)
            raise ClaimLocatorInvalid(
                f"claim {claim_id} 定位无效，拒绝迁移 {from_status} -> {to_status}: {detail}"
            )

    closure_fn: Callable[..., Iterable[Any]] | None = None
    if to_status == "superseded":
        closure_fn = forward_closure_fn or resolve_forward_closure()
        if closure_fn is None:
            raise PropagationUnavailable(
                "superseded 传播需 scripts/graph/forward_closure（Ch6 §E.4 复用第九章传播），"
                "但当前不可解析 —— 写库前失败，不留半截数据"
            )

    at = recorded_at or datetime.now(timezone.utc)
    seq = _next_recorded_seq(all_rows, recorded_seq)
    new_obj = _build_new_version(prior_obj, to_status, seq, at, version_kind, supersedes)
    _append_claim(root, new_obj)

    result = TransitionResult(
        claim_id=claim_id,
        from_status=from_status,
        to_status=to_status,
        recorded_seq=seq,
        version_kind=version_kind,
        reason=reason,
    )
    if to_status == "superseded" and closure_fn is not None:
        result.downstream, result.recheck_tasks = _propagate(
            root, claim_id, version_kind, closure_fn
        )
    return result


def on_superseded(
    code_root: str | Path,
    claim_id: str,
    version_kind: str,
    *,
    supersedes: str | None = None,
    recorded_at: datetime | None = None,
    forward_closure_fn: Callable[..., Iterable[Any]] | None = None,
) -> TransitionResult:
    """上游版本事件（预测修订 / 财务重述 / 原文撤回）→ 主张 `superseded` → 下游入复查（`Ch6 §E.4`）。"""
    return transition(
        code_root,
        claim_id,
        "superseded",
        version_kind=version_kind,
        supersedes=supersedes,
        recorded_at=recorded_at,
        forward_closure_fn=forward_closure_fn,
    )


def _run_check(args: Any) -> int:
    """`--check`：只做迁移表判定，不写库。"""
    if not args.from_status or not args.to:
        print("[INPUT-ERROR] --check 需同时给出 --from 与 --to", file=sys.stderr)
        return 2
    assert_transition(args.from_status, args.to)
    print(f"== transition.py ==\n  OK: {args.from_status!r} -> {args.to!r} 合法（Ch6 §E.1）")
    return 0


def _run_transition(args: Any) -> int:
    """`--claim-id --to ...`：执行真迁移（含 `superseded` 传播）。"""
    if not args.claim_id or not args.to:
        print("[INPUT-ERROR] 需 --claim-id 与 --to", file=sys.stderr)
        return 2
    recorded_at = _parse_dt(args.recorded_at)
    result = transition(
        args.code_root,
        args.claim_id,
        args.to,
        reason=args.reason,
        version_kind=args.version_kind,
        recorded_at=recorded_at,
    )
    print("== transition.py ==")
    print(
        f"  {result.claim_id}: {result.from_status!r} -> {result.to_status!r}"
        f"  recorded_seq={result.recorded_seq}"
        + (f"  version_kind={result.version_kind}" if result.version_kind else "")
    )
    for obj_type, obj_id in result.downstream:
        print(f"  downstream stale: {obj_type}:{obj_id}")
    for key in result.recheck_tasks:
        print(f"  recheck task: {key}")
    if result.reason:
        print(f"  reason: {result.reason}")
    return 0


def _parse_dt(text: str | None) -> datetime | None:
    """把 ISO 时间串解析为 `datetime`；缺省 → `None`（交由 `transition` 取当前 UTC）。"""
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。退出码：`0` 合法 / `1` 非法迁移或定位无效 / `2` 输入异常。"""
    import argparse

    from pydantic import ValidationError

    parser = argparse.ArgumentParser(
        prog="transition.py", description="主张五态状态机 + superseded 传播（Ch6 §E）"
    )
    parser.add_argument("code_root", nargs="?", default=".", help="代码工程根（system/）")
    parser.add_argument("--claim-id", default=None)
    parser.add_argument("--to", default=None, help="目标状态（五态之一）")
    parser.add_argument("--from", dest="from_status", default=None, help="仅 --check：源状态")
    parser.add_argument("--check", action="store_true", help="只做迁移表判定，不写库")
    parser.add_argument("--reason", default="")
    parser.add_argument("--version-kind", default=None)
    parser.add_argument("--recorded-at", default=None, help="ISO 时间（默认当前 UTC）")
    args = parser.parse_args(argv)

    try:
        if args.check:
            return _run_check(args)
        return _run_transition(args)
    except ClaimNotFound as exc:
        print(f"[INPUT-ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    except ClaimTransitionError as exc:
        print(f"[BLOCKED] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except ValidationError as exc:
        print(f"[BLOCKED] Claim 校验失败（三字段维度不同，不得互换/合并）: {exc}", file=sys.stderr)
        return 1
    except (FileNotFoundError, OSError) as exc:
        print(f"[INPUT-ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
