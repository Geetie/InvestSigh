#!/usr/bin/env python3
"""`transition.py` —— 主张**五态状态机** + `superseded` 传播（`Ch6 §E` · `Ch6 N6.3-10/11/18`）。

## 有限状态机（`Ch6 §E.1` 状态图的逐边实现）

```
[*] ──（②③④ 提取完成，初始态，Ch6 §E.1 首行）──► pending_verification
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
- **初始态由设计写死为 `pending_verification`**（`Ch6 §E` 状态机首行 `[*] --> pending_verification`）：
  采集层写出的 claim **直接**处于该态（`schema.models.ClaimStatus` 的默认值），
  **不存在任何五态之外的"入口别名"**——五态之外的取值一律 `UnknownClaimStatus` 响亮拒绝。

## 追加式写入（`Ch9 §3.4.2`）

状态迁移**不改历史行**：每次迁移**追加**一行带新 `status` 与递增 `recorded_seq` 的 claim 版本，
`as_of` 按业务键取 `recorded_seq` 最大者（`Ch9 §3.4.1`）。

## `superseded` 传播（**复用 `scripts/graph`，不重造**；`Ch6 §E.4`）

`Ch6 §E.4` 逐字要求「**直接调用第九章已有的** `forward_closure()` … **不新增一套传播**」。
本模块据此**整体委托** `scripts/graph/propagate.py::propagate_retraction` ——
该函数是"闭包遍历 → `baseline`/`recommendation` 入 `recheck` 队列 → 研究深度回退"的
**唯一实现与唯一写入者**（`Ch9 §3.4.3`）：

- 入口：`propagate_retraction(code_root, <claim 的 ref>, apply=...)`；
  本模块**不再**自建遍历 / ref 归一 / 入队（此前的自建版本与真签名不兼容，是缺陷 N-2 的根因）。
- "只对结论（`baseline` / `recommendation`）入复查"的语义由 `propagate_retraction` 的
  `RECHECK_STEM_TYPES` 过滤**表达**（≡ `Ch6 §E.4` 伪码的 `if obj.type in {baseline, recommendation}`）——
  本模块**不再**自造 `parent_context.requires_recheck` 布尔字段（设计中不存在该字段）。
- `recheck` 任务幂等键 = `recheck::<claim 的 ref>::<下游 ref>`（graph 口径，`Ch9 §N9.1-26`）——
  全库**唯一一套**键格式（`G-06` 唯一真源）。

### 写序（消灭"半数据窗口"）

旧版**先写库、后传播**：传播一旦失败，`facts/claims.jsonl` 会留下 `status=superseded` 而 `tasks` 为空。
现改为：

1. **解析 / 预飞**：解析 claim 的 ref 形式、并以 `apply=False` **干跑**一次传播 ——
   把"闭包遍历 / 对象索引 / ref 解析"这些**可能抛错**的动作**全部前移到写库之前**；
2. `_append_claim(...)` 追加 `superseded` 版本行；
3. `propagate_retraction(..., apply=True)` 落 `recheck` 任务与深度回退。

★ **诚实登记的残留窗口**（`R-04`，不称为"原子"）：第 3 步与第 2 步是**两次独立写盘**；
若第 3 步**在 I/O 层**失败（磁盘满 / 权限），仍会留下"claim 已 `superseded`、task 未落"的状态。
设计区无事务机制，本模块**无法**消除该窗口，只能把**解析类**失败（绝大多数失败形态）
挡在写库之前。

## 退出码（CLI，`CONVENTIONS.md::G-01`）

`0` 迁移完成 / 判定合法 · `1` **非法迁移 / 定位无效 / 传播不可用**（被检对象不合规）· `2` 输入异常。
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

CLAIM_STATES = ("pending_verification", "supported", "disputed", "refuted", "superseded")
"""`Ch6 §E.1` 五态（唯一权威取值域）。"""

INITIAL_STATE = "pending_verification"
"""提取（②③④）完成后的**初始态**（`Ch6 §E.1`）—— 采集层写出的 claim 即处于此态。"""

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

_LOCATOR_GATED_TARGETS = frozenset({"pending_verification", "supported", "disputed", "refuted"})
"""这些迁移目标受"定位前置门"约束（`Ch6 §D` 程序拦截）；retirement(`superseded`) 不受限。"""

_PROPAGATE_MODULE = "scripts.graph.propagate"
"""`superseded` 传播的唯一实现所在模块（`Ch6 §E.4` 复用第九章传播，`G-06` 不另建）。"""

_PROPAGATE_ATTR = "propagate_retraction"
"""`Ch9 §3.4.3` T12 传播入口（唯一写入者）。"""

_EDGE_SOURCE = "dependency_edges"
"""依赖图真源边表（`Ch9 §3.4.3`）。"""

_CLAIM_REF_PREFIXES = ("claim:", "claims:")
"""依赖图边端点里 claim 的**带前缀**写法（裸 id 之外的第二形式；判定见 `_resolve_claim_ref`）。"""


class ClaimTransitionError(RuntimeError):
    """主张状态迁移类错误的基类（一律**响亮拒绝**，不静默兜底）。"""


class UnknownClaimStatus(ClaimTransitionError):
    """出现 `Ch6 §E.1` 五态之外的取值 —— 未知状态。"""


class IllegalTransition(ClaimTransitionError):
    """合法状态之间的**非法迁移**（表外迁移 / 终态出边 / 序或时间倒挂 / 非法 `version_kind`）。"""


class ClaimNotFound(ClaimTransitionError):
    """`facts/claims.jsonl` 中不存在所请求的 `claim_id`（不得凭空重建）。"""


class ClaimLocatorInvalid(ClaimTransitionError):
    """迁移目标进入证据集，但主张定位无效（`locator_check` 命中违例，`Ch6 §D` 程序拦截）。"""


class PropagationUnavailable(ClaimTransitionError):
    """`superseded` 传播所需的 `scripts.graph.propagate::propagate_retraction` 不可解析
    （**写库前**抛出，不留半截数据）。"""


@dataclass
class TransitionResult:
    """一次状态迁移的结果（`superseded` 时含复用 `propagate_retraction` 的传播结果）。

    `downstream` / `recheck_tasks` / `rolled_back_companies` 直接来自
    `scripts.graph.propagate.PropagationResult`（graph 口径：下游为**裸 ref**）。
    """

    claim_id: str
    from_status: str
    to_status: str
    recorded_seq: int
    version_kind: str | None = None
    downstream: list[str] = field(default_factory=list)
    recheck_tasks: list[str] = field(default_factory=list)
    rolled_back_companies: list[str] = field(default_factory=list)
    reason: str = ""


def allowed_targets(from_status: str) -> frozenset[str] | None:
    """给定源状态，返回其**允许的目标集合**；源状态未知 → `None`。"""
    return ALLOWED_TRANSITIONS.get(from_status)


def can_transition(from_status: str, to_status: str) -> bool:
    """`from_status -> to_status` 是否在**允许迁移表**内（纯判定，无副作用）。"""
    targets = allowed_targets(from_status)
    if targets is None:
        return False
    return to_status in targets


def assert_transition(from_status: str, to_status: str) -> None:
    """断言迁移合法；否则抛 `UnknownClaimStatus` / `IllegalTransition`（**响亮拒绝**）。"""
    if from_status not in ALLOWED_TRANSITIONS:
        raise UnknownClaimStatus(
            f"未知主张状态 from={from_status!r}；合法状态见 Ch6 §E.1: {CLAIM_STATES}"
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


def _propagation_available() -> bool:
    """**纯可用性探测**：`scripts/graph.propagate` 是否可解析（`Ch6 §E.4` 复用的传播实现）。

    不可用 → 调用方折叠为 `PropagationUnavailable`（**写库前**）。本函数**不**返回可调用对象
    —— 实现由调用方按真签名（`code_root, ref, *, source, apply`）导入并委托，杜绝"猜接口"。
    """
    return _module_available(_PROPAGATE_MODULE)


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


def _resolve_claim_ref(root: Path, claim_id: str) -> str:
    """确定该 claim 在 `facts/dependency_edges.jsonl` 中的 **ref 形式**（**不猜测**）。

    `Ch9 §3.4.3` 的边端点在真实数据里存在两种写法（裸 id `"c1"` / 带前缀 `"claim:c1"`）。
    判定顺序：

    1. **先看真实边端点**：在候选形式（裸 id、`claim:<id>`、`claims:<id>`）中，
       恰有一种出现在端点集合里 → 采用它；
    2. 两种同时出现（图数据不规范）→ **响亮拒绝**（不猜）；
    3. 没有任何边引用该 claim → 回退 `object_index`：命中原语对象则用**裸 id**
       （该 claim 无下游，传播为空集，**合法**）；否则 → **响亮拒绝**（不把"未知对象"静默当"无下游"）。
    """
    from scripts.graph.adjacency import load_edges, object_index

    endpoints: set[str] = set()
    for edge in load_edges(root, _EDGE_SOURCE):
        if edge.from_ref:
            endpoints.add(edge.from_ref)
        if edge.to_ref:
            endpoints.add(edge.to_ref)

    candidates = [claim_id, *(f"{prefix}{claim_id}" for prefix in _CLAIM_REF_PREFIXES)]
    present = [c for c in candidates if c in endpoints]
    if len(present) > 1:
        raise ClaimTransitionError(
            f"claim {claim_id!r} 在 {_EDGE_SOURCE} 中出现多种 ref 形式 {present} —— 图数据不规范，拒绝猜测"
        )
    if len(present) == 1:
        return present[0]
    if claim_id in object_index(root):
        return claim_id
    raise ClaimTransitionError(
        f"无法解析 claim {claim_id!r} 的 ref 形式：{_EDGE_SOURCE} 无边引用、"
        "object_index 中亦无此对象 —— 不静默当'无下游'"
    )


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
    propagate_fn: Callable[..., Any] | None = None,
) -> TransitionResult:
    """执行一次**合法**状态迁移：校验迁移表 → （定位前置门）→ （`superseded`：解析/预飞）
    → 追加新版本行 → （`superseded`：`apply=True` 落地传播）。

    - 非法迁移 / 未知状态 / 未知 claim / 定位无效 / 传播不可用 → 抛 `ClaimTransitionError` 子类。
    - `reason` 仅供调用方 / CLI 记录，**不落库**（`Claim` 无该字段）。
    - `propagate_fn` 用于注入传播实现（测试 / 定制）；缺省惰性导入
      `scripts.graph.propagate::propagate_retraction`（真签名）。
    - **写序**：`superseded` 的解析/预飞在 `_append_claim` **之前**，故解析类失败**零写入**；
      `apply=True` 为独立写盘，其 I/O 失败仍可能留下残留（见模块 docstring）。
    """
    root = Path(code_root)
    prior_row, all_rows = _latest_claim(root, claim_id)
    prior_obj = _validate_prior(prior_row)
    # `prior_obj.status` 是新契约下的 `ClaimStatus`（`StrEnum`）—— 直接 `str()` 未必得五态值，
    # 故取 `.value`（对旧式纯 `str` 回退为原值）。
    from_status = str(getattr(prior_obj.status, "value", prior_obj.status))
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

    # ── `superseded`：先解析/预飞（全部可能抛错点前移到写库之前），再委托 propagate_retraction ──
    prop: Callable[..., Any] | None = None
    claim_ref: str | None = None
    if to_status == "superseded":
        if propagate_fn is not None:
            prop = propagate_fn
        elif _propagation_available():
            from scripts.graph.propagate import propagate_retraction as prop
        else:
            raise PropagationUnavailable(
                f"superseded 传播需 {_PROPAGATE_MODULE}::{_PROPAGATE_ATTR}"
                "（Ch6 §E.4 复用第九章传播），但当前不可解析 —— 写库前失败，不留半截数据"
            )
        claim_ref = _resolve_claim_ref(root, claim_id)
        # 干跑（apply=False）：真跑一遍闭包 + 对象索引 + 幂等键计算，但**不落库**。
        # 任何解析类错误在此抛出 → 下面的 `_append_claim` 永不执行 → 零写入。
        prop(root, claim_ref, source=_EDGE_SOURCE, apply=False)

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
    if to_status == "superseded" and prop is not None and claim_ref is not None:
        # 落地（apply=True）：`recheck` 任务与深度回退由 propagate_retraction 唯一写入。
        applied = prop(root, claim_ref, source=_EDGE_SOURCE, apply=True)
        result.downstream = list(applied.downstream)
        result.recheck_tasks = list(applied.created_task_ids)
        result.rolled_back_companies = list(applied.rolled_back_companies)
    return result


def on_superseded(
    code_root: str | Path,
    claim_id: str,
    version_kind: str,
    *,
    supersedes: str | None = None,
    recorded_at: datetime | None = None,
    propagate_fn: Callable[..., Any] | None = None,
) -> TransitionResult:
    """上游版本事件（预测修订 / 财务重述 / 原文撤回）→ 主张 `superseded` → 下游入复查（`Ch6 §E.4`）。"""
    return transition(
        code_root,
        claim_id,
        "superseded",
        version_kind=version_kind,
        supersedes=supersedes,
        recorded_at=recorded_at,
        propagate_fn=propagate_fn,
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
    for ref in result.downstream:
        print(f"  downstream: {ref}")
    for task_id in result.recheck_tasks:
        print(f"  recheck task: {task_id}")
    for company_id in result.rolled_back_companies:
        print(f"  depth rollback: {company_id}")
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
