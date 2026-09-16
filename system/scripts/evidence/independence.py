"""`independence.py` —— **追源去重与独立判定**（`Ch6 §6.3` 第 3 步 / `§C.1~§C.4` / `§F.2~§F.3`）。

## 一句话（`Ch6 §6.3` 第 3 步）

把「同一消息被多家转述」识别为 **一个原始证据来源 + 多条传播记录**，
**绝不**提升为多份独立佐证 —— 这正是 `Ch10 §2.1` 权威表 `T01` 的预期行为：

> 场景：**十篇文章转述同一匿名订单消息**
> 预期行为：**保留一个原始证据来源及传播记录，不提升为十份独立佐证**

## 判定算法（`Ch6 §C.2` 步骤，逐条实现）

1. **分组**：按**内容指纹**分组（`claim_group_fingerprint`）—— 指纹**基于根来源而非标题/措辞**
   （`Ch9 §3.4.7`），故"十篇转述同一消息"落在**同一组**。
2. **求根**：沿 `claim.origin_claim_id` 回溯到**最早主张**（union-find 求根，`Ch6 §C.1`）。
3. **独立 / 转述判定**（`Ch6 §F.3` 认定边界）：
   - `is_restatement` ⟺ **有上游**（`find_root(c) != c`）→ 只记 `claim_propagation`，**计数不增**；
   - `is_independent` ⟺ **无上游**（是根）**且** `direct_knowledge == "direct"`；
   - 其余（根但非直接知情）→ 存疑 → `review_candidates`（`Ch6 §C.2` 步骤⑥）。
4. **计数**：`independent_evidence_count[root] = 同一组内独立根数`（`Ch6 §B.4`：是**基数**不是权重）。

## 为什么"指纹同 + 共同上游 ⇒ 转述"而不是打分（`Ch6 §张力 C6-3`）

转述判定是**基于关系的等价判定**（去重），独立计数是**基数**，
**不是**给来源设固定系数（那是 `N6.3-13` 明令禁止的"固定分数加权"）。

## 复用（不重造，`G-06`）

- 指纹：`scripts/graph/fingerprint.py::event_fingerprint`（**唯一**指纹实现）；
- 最新版本：`schema/store.py::as_of`（同一业务键取 `recorded_seq` 最大者）；
- 写入：`schema/store.py::append_records`（**唯一**写入口，追加式不可变）。

## 人工 override 的承载（`Ch6 §C.3`；T-11 契约变更）

`Ch6 §C.3` 的人工去重覆盖（原设计写独立 `facts/claim_alias.jsonl`）**并入**既有
`claim_propagation`，以其 `kind=manual_alias_override` 承载（`Ch9 §3.3.3`：18 个 JSONL 不得增删改名，
**不新增第 19 个**）。本模块的自动判定仍只产出 `kind=restatement` 的转述行；人工覆盖由
`dedup_override` 任务写 `manual_alias_override` 行（`schema.models.ClaimPropagation`）。

## `origin_claim_id` 的产出方（`Ch6 §C.2` 步骤③；T01 系统层缺口）

判定层只**读** `origin_claim_id`。本模块另提供**产出**路径（`plan_origin_attribution` /
`classify_and_record` → `record_claim_updates`）：当**根来源主张在场**（组内存在
`source_id == root_source_id` 的自根主张）时，把同组中**声明指向该根来源、且自身不是根来源**的
无上游主张，链到**最早**的自根主张（`Ch6 §C.1`：回溯到最早主张）。落链 = **追加新版本行**（不改历史）。

**根来源主张不在场 → 不臆断**（`residual_groups` 如实登记）：此情形下"真独立"与
"未标链的转述"在 claim 字段上**同构**，不得强行并入（`R-04`：歧义不自行裁决）。

## 已知缺口（如实登记，`R-04`）

- 人工覆盖（`manual_alias_override`）的**写入方**是 `dedup_override` 任务（非本模块自动判定）；
  本模块提供承载契约与判定读取，**不自动生成**人工覆盖行。
- `origin_claim_id` 产出方**仅在根来源主张在场时**生效；根不在场 → 残留如实登记（见上节）。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 复用既有原语（**不重造**，`G-06`）：指纹 / 写库 / 版本选取。
from scripts.graph.fingerprint import event_fingerprint  # noqa: E402

_CLAIMS_STEM = "claims"
_PROPAGATION_STEM = "claim_propagation"

_DEFAULT_EVENT_TYPE = "other"
"""`event_fingerprint` 的 `event_type` 缺省（`EventType.other`，`Ch9 §3.4.7`）。"""

_DIRECT = "direct"
_UNKNOWN = "unknown"


class IndependenceInputError(RuntimeError):
    """输入不足以做**可判定**的独立判定（缺 `occurred_at` / 根来源，或 `origin_claim_id` 成环）。

    一律**响亮失败**，**不静默**取兜底值 —— 否则"无法判定"会被错当成"独立"（`Ch9 §3.4.6` 精神）。
    """


@dataclass(frozen=True)
class IndependenceSummary:
    """一次独立判定的**完整结果**（确定性、可复现）。"""

    groups: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """指纹 → 该组内的 `claim_id`（升序）。"""

    roots: dict[str, str] = field(default_factory=dict)
    """`claim_id` → 其沿 `origin_claim_id` 回溯到的**根** `claim_id`。"""

    restatements: dict[str, str] = field(default_factory=dict)
    """转述主张 `claim_id` → 根 `claim_id`（`is_restatement=True` 的那些）。"""

    independent_roots: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """指纹 → 该组内的**独立根** `claim_id`（升序）。"""

    independent_evidence_count: dict[str, int] = field(default_factory=dict)
    """**根主张** `claim_id` → 其所在组的独立佐证基数（`Ch6 §B.4`：基数，非权重）。"""

    propagation_rows: tuple[Any, ...] = ()
    """待落库的 `ClaimPropagation` 行（转述记录，**保留**不丢弃）。"""

    review_candidates: tuple[str, ...] = ()
    """存疑项（根但非直接知情）→ 人工兜底线索（`Ch6 §C.2` 步骤⑥；override 见模块 docstring）。"""

    notes: tuple[str, ...] = ()
    """非静默说明（空真源 / 缺字段走法）。"""

    @property
    def propagation_count(self) -> int:
        """传播记录行数（`T01` 断言：10 转述 ⇒ 10）。"""
        return len(self.propagation_rows)

    @property
    def root_count(self) -> int:
        """**根主张数**（`T01` 断言：十篇转述 ⇒ 唯一根 ⇒ 1）。"""
        return len(set(self.roots.values()))


def _occurred_at(rec: Mapping[str, Any]) -> Any:
    """取主张的**事件发生时间**（`Ch9 §2.2` valid_time）。

    缺 `occurred_at` 时依次退到 `published_at` / `first_seen_at`；**皆缺 → 响亮失败**
    （不臆造"今天"，否则不同日期的同一消息会被错并/错分）。
    """
    for key in ("occurred_at", "published_at", "first_seen_at"):
        value = rec.get(key)
        if value:
            return value
    raise IndependenceInputError(
        "主张缺 occurred_at / published_at / first_seen_at —— 无法做时间归桶的指纹分组"
    )


def _declared_root_source(rec: Mapping[str, Any]) -> str | None:
    """取主张**显式声明**的根来源标识（无则 `None`）。**单一取值口**（`G-06`），供指纹与自根判定共用。

    allowlist（`R-06` ⑤）：① 顶层 `root_source_id`；② `impact_capability.root_source_id`
    （当前 `Claim` 无顶层 `root_source_id` 字段 ⇒ 自由 dict 是其唯一合法载体，落位同 `direct_knowledge`）。
    """
    declared = rec.get("root_source_id")
    if declared:
        return str(declared)
    capability = rec.get("impact_capability")
    if isinstance(capability, Mapping):
        carried = capability.get("root_source_id")
        if carried:
            return str(carried)
    return None


def _root_source_id(rec: Mapping[str, Any], root_rec: Mapping[str, Any]) -> str:
    """取**根来源**标识（`Ch9 §3.4.7`：指纹基于根来源而非标题）。

    取值来源（**allowlist**，`R-06` ⑤；不重造第二套指纹）：
    1. 主张**显式声明**的根来源（`_declared_root_source`）；
    2. 否则用 origin 链解出的**根主张**的 `source_id`。

    二者都是"根来源"语义，**绝不按标题/措辞分组**。
    """
    declared = _declared_root_source(rec)
    if declared:
        return declared
    derived = root_rec.get("source_id")
    if not derived:
        raise IndependenceInputError("主张既无 root_source_id，其根主张也无 source_id —— 无根来源")
    return str(derived)


def claim_group_fingerprint(rec: Mapping[str, Any], root_rec: Mapping[str, Any]) -> str:
    """按 `Ch9 §3.4.7` 计算**内容分组指纹**（**调用** `event_fingerprint`，不重造）。

    `root_source_id` 取根来源（见 `_root_source_id`）；`event_type` / `company_ids` /
    `metric` / `period_bucket` 取记录上的可选字段（缺则用 `EventType.other` / 空）。
    """
    return event_fingerprint(
        event_type=str(rec.get("event_type") or _DEFAULT_EVENT_TYPE),
        company_ids=list(rec.get("company_ids") or []),
        metric=rec.get("metric"),
        period_bucket=rec.get("period_bucket"),
        occurred_at=_occurred_at(rec),
        root_source_id=_root_source_id(rec, root_rec),
    )


def _direct_knowledge(rec: Mapping[str, Any]) -> str:
    """取 `direct_knowledge`（`Ch6 §B.1` 质量维度①）。

    取值来源（allowlist，`R-06` ⑤）：顶层 `direct_knowledge` →
    `quality.direct_knowledge`（设计 §B.1 落位）→ `impact_capability.direct_knowledge`
    （**当前 schema** 的 `Claim` 无 `quality` 字段，`extra="forbid"`；`impact_capability` 是
    其唯一可承载该维度的自由 dict）。皆无 → `unknown`（**保守**：无法证明"直接知情"即不计独立）。
    """
    value = rec.get("direct_knowledge")
    if value is None:
        for container in ("quality", "impact_capability"):
            node = rec.get(container)
            if isinstance(node, Mapping) and node.get("direct_knowledge") is not None:
                value = node.get("direct_knowledge")
                break
    return str(value) if value is not None else _UNKNOWN


def _latest_by_claim_id(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """同一 `claim_id` 多版本 → 取 `recorded_seq` 最大者（**调用** `store.as_of`，`Ch9 §3.4.1`）。

    **不得**把同一主张的多个历史版本当成多份佐证 —— 故分类前先取最新版本。
    """
    from schema.store import as_of

    return list(as_of(list(rows), ["claim_id"]))


def _resolve_root(claim_id: str, by_id: Mapping[str, Mapping[str, Any]]) -> str:
    """沿 `origin_claim_id` 回溯到根（union-find 求根，`Ch6 §C.1`）。

    - 上游指向**不在集合内**的主张 → `IndependenceInputError`（无法解析，不静默当独立）；
    - `origin_claim_id` 自指或成环 → `IndependenceInputError`（**响亮拒绝**，不无限回溯）。
    """
    seen: list[str] = []
    current = claim_id
    while True:
        rec = by_id.get(current)
        if rec is None:
            raise IndependenceInputError(
                f"origin 链指向不在本次主张集内的 claim_id={current!r} —— 无法解析根"
            )
        parent = rec.get("origin_claim_id")
        if not parent:
            return current
        parent = str(parent)
        if parent == current or parent in seen:
            raise IndependenceInputError(f"origin_claim_id 成环：{seen + [current]} → {parent!r}")
        seen.append(current)
        current = parent


def classify_independence(
    claims: Sequence[Mapping[str, Any]],
    *,
    group_key_fn: Callable[[Mapping[str, Any], Mapping[str, Any]], str] | None = None,
) -> IndependenceSummary:
    """对一批主张做**追源去重与独立判定**（纯函数，无副作用；`Ch6 §C.2`）。

    - 输入：原始 claim 行（`Mapping`，允许同一 `claim_id` 多版本 —— 内部取最新）；
    - 输出：`IndependenceSummary`（分组 / 根 / 转述 / 独立基数 / 待落传播行 / 存疑项）。

    ★ 同名函数 `classify_*` 属**决策作用域**（`Ch2 §B.3` Checker-1）：本函数体**不出现**
      任何禁词（`weight` / `score` / `vote` / `sentiment` / `follower_count`），
      且**不读**任何冻结参数（`Ch6 §B.2` 三轴职责边界）。
    """
    key_fn = group_key_fn or claim_group_fingerprint
    latest = _latest_by_claim_id(claims)
    by_id: dict[str, Mapping[str, Any]] = {}
    for rec in latest:
        cid = rec.get("claim_id")
        if cid:
            by_id[str(cid)] = rec

    notes: list[str] = []
    if not by_id:
        notes.append("NO_CLAIMS: 无被检对象（真空成立，非'已验证'，G-03）")
        return IndependenceSummary(notes=tuple(notes))

    # ① 求根（union-find）＋ ② 分组（内容指纹）
    roots: dict[str, str] = {}
    group_members: dict[str, list[str]] = {}
    for cid, rec in by_id.items():
        root = _resolve_root(cid, by_id)
        roots[cid] = root
        group_key = key_fn(rec, by_id[root])
        group_members.setdefault(group_key, []).append(cid)

    # ③ 独立 / 转述判定（Ch6 §F.3）
    restatements: dict[str, str] = {}
    independent_ids: set[str] = set()
    review: list[str] = []
    for cid, rec in by_id.items():
        if roots[cid] != cid:
            restatements[cid] = roots[cid]           # 有上游 ⇒ 转述，只记传播
        elif _direct_knowledge(rec) == _DIRECT:
            independent_ids.add(cid)                 # 无上游 + 直接知情 ⇒ 独立佐证
        else:
            review.append(cid)                       # 根但非直接知情 ⇒ 存疑

    # ④ 计数：独立基数是"同组内独立根数"，只记在**根主张**上（`Ch6 §C.2` 步骤⑤）
    independent_roots: dict[str, tuple[str, ...]] = {}
    counts: dict[str, int] = {}
    for group_key, members in group_members.items():
        independent = tuple(sorted(m for m in members if m in independent_ids))
        independent_roots[group_key] = independent
        for member in members:
            if roots[member] == member:
                counts[member] = len(independent)

    propagation_rows = tuple(
        _propagation_row(cid, root, by_id[cid]) for cid, root in sorted(restatements.items())
    )
    groups = {k: tuple(sorted(v)) for k, v in group_members.items()}
    return IndependenceSummary(
        groups=groups,
        roots=dict(roots),
        restatements=dict(sorted(restatements.items())),
        independent_roots=independent_roots,
        independent_evidence_count=dict(sorted(counts.items())),
        propagation_rows=propagation_rows,
        review_candidates=tuple(sorted(review)),
        notes=tuple(notes),
    )


def _propagation_row(claim_id: str, root_claim_id: str, rec: Mapping[str, Any]) -> Any:
    """构造一行 `ClaimPropagation`（转述记录）—— **不改原主张、只追加传播边**（`Ch6 §C.2` 步骤④）。"""
    from schema.models import ClaimPropagation, PropagationKind

    return ClaimPropagation(
        propagation_id=f"prop-{claim_id}",
        root_claim_id=root_claim_id,
        propagated_claim_id=claim_id,
        publisher_entity=str(rec.get("publisher_entity") or ""),
        carrier_platform=str(rec.get("carrier_platform") or ""),
        independent_evidence=False,
        kind=PropagationKind.restatement,
    )


# ───────────────────── ⑥ `origin_claim_id` 产出方（`Ch6 §C.2` 步骤③） ─────────────────────


@dataclass(frozen=True)
class OriginAttribution:
    """一次 `origin_claim_id` 产出（去重步骤③）的**完整结果**（确定性、可复现）。

    `Ch6 §C.2` 步骤③要求把转述链到根主张；但判定层只**读**该字段 —— 本结构承载**产出**。
    """

    links: dict[str, str] = field(default_factory=dict)
    """本次应建立的 `转述 claim_id -> 根主张 claim_id` 上游链（**仅根来源主张在场时**）。"""

    residual_groups: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """**无法确定根**的指纹组（根来源主张不在场）→ 该组既有主张（**不臆断**，如实登记残余）。"""

    notes: tuple[str, ...] = ()

    @property
    def link_count(self) -> int:
        """本次可建立的**上游链**条数。"""
        return len(self.links)

    @property
    def residual_count(self) -> int:
        """**未闭合**的指纹组数（根来源不在场 → 判定层产物，残余）。"""
        return len(self.residual_groups)


def _is_self_root(rec: Mapping[str, Any]) -> bool:
    """是否**自称根**：无上游，且其（显式或隐含的）根来源就是自身 `source_id`（`Ch6 §C.1`）。

    ★ 必须与 `_root_source_id` 用**同一取值口**（`_declared_root_source`）——否则携带
      `impact_capability.root_source_id` 的转述会被误判为自根（实测踩到：根被反向链到转述）。
    """
    if rec.get("origin_claim_id"):
        return False
    declared = _declared_root_source(rec)
    if declared is None:
        return True
    return declared == str(rec.get("source_id") or "")


def _earliest_key(rec: Mapping[str, Any]) -> tuple[str, int, str]:
    """**最早主张**的确定性排序键（`Ch6 §C.1`：回溯到最早主张）：(时间, 记录序号, claim_id)。"""
    return (str(_occurred_at(rec)), int(rec.get("recorded_seq") or 0), str(rec.get("claim_id") or ""))


def plan_origin_attribution(claims: Sequence[Mapping[str, Any]]) -> OriginAttribution:
    """**纯函数**：规划 `origin_claim_id` 产出（不改输入、不写库；`Ch6 §C.2` 步骤③）。

    规则（**allowlist，不靠猜键名**；`R-06`）：

    1. 按**内容指纹**（`claim_group_fingerprint`，基于根来源）分组；
    2. 组内**根来源主张在场**（存在自称根者，其 `source_id == 该组的根来源`）时，取**最早**者为根；
    3. 把组内**声明指向该根来源（`root_source_id == 根来源`）、自身非根来源、且无上游**的主张，
       链到该根 —— 这些是**转述**（`Ch6 §F.3`：有共同上游 ⇒ 只记传播、不增计数）；
    4. 组内**无自称根者**（根来源主张不在场）⇒ **不臆断**，整组登记 `residual_groups`。

    ★ 为什么不把所有同组主张都并成一：`Ch6 §F.3` 的独立认定要求"**无共同上游**" ——
      "同指纹但无显式上游"既可能是**真独立**（各自直接知情，用例 b），也可能是**未标链的转述**（用例 c），
      二者在 claim 字段上**同构** ⇒ 无外部信息时**不裁决**（`R-04`），只登记残余。
    """
    latest = _latest_by_claim_id(claims)
    by_id: dict[str, Mapping[str, Any]] = {}
    for rec in latest:
        cid = rec.get("claim_id")
        if cid:
            by_id[str(cid)] = rec

    notes: list[str] = []
    if not by_id:
        notes.append("NO_CLAIMS: 无被检对象（真空成立，非'已验证'，G-03）")
        return OriginAttribution(notes=tuple(notes))

    group_members: dict[str, list[str]] = {}
    for cid, rec in by_id.items():
        root = _resolve_root(cid, by_id)
        group_members.setdefault(claim_group_fingerprint(rec, by_id[root]), []).append(cid)

    links: dict[str, str] = {}
    residual: dict[str, tuple[str, ...]] = {}
    for key, members in group_members.items():
        members_sorted = sorted(members)
        self_roots = [m for m in members_sorted if _is_self_root(by_id[m])]
        if not self_roots:
            if len(members_sorted) > 1:
                residual[key] = tuple(members_sorted)   # 根来源不在场 → 残留（不臆断）
            continue
        root_id = min(self_roots, key=lambda m: _earliest_key(by_id[m]))
        root_source = str(by_id[root_id].get("source_id") or "")
        for member in members_sorted:
            if member == root_id:
                continue
            rec = by_id[member]
            if rec.get("origin_claim_id"):
                continue                                # 已有上游 ⇒ 不覆盖
            if str(rec.get("source_id") or "") == root_source:
                continue                                # 与根同源 = 根来源本身，非转述
            if _root_source_id(rec, by_id[root_id]) != root_source:
                continue                                # 未声明指向该根来源 ⇒ 不臆断
            links[member] = root_id

    return OriginAttribution(
        links=dict(sorted(links.items())),
        residual_groups={k: residual[k] for k in sorted(residual)},
        notes=tuple(notes),
    )


def _max_seq_by_claim_id(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """每个 `claim_id` 的最大 `recorded_seq`（用于**只**给最新版本打补丁）。"""
    out: dict[str, int] = {}
    for row in rows:
        cid = str(row.get("claim_id") or "")
        if not cid:
            continue
        out[cid] = max(out.get(cid, -1), int(row.get("recorded_seq") or 0))
    return out


def _apply_links(
    rows: Sequence[Mapping[str, Any]], links: Mapping[str, str]
) -> list[Mapping[str, Any]]:
    """**在内存中**给最新版本主张补上 `origin_claim_id`（不写库，供随后分类使用）。"""
    max_seq = _max_seq_by_claim_id(rows)
    out: list[Mapping[str, Any]] = []
    for row in rows:
        cid = str(row.get("claim_id") or "")
        if (
            cid in links
            and int(row.get("recorded_seq") or 0) == max_seq.get(cid)
            and not row.get("origin_claim_id")
        ):
            patched = dict(row)
            patched["origin_claim_id"] = links[cid]
            out.append(patched)
        else:
            out.append(row)
    return out


def record_claim_updates(
    code_root: str | Path,
    plan: OriginAttribution,
    counts: Mapping[str, int],
) -> int:
    """把 `origin_claim_id`（`plan.links`）与 `independent_evidence_count`（`counts`）**追加**落库。

    - 写入方式 = **追加新版本行**（`recorded_seq` 递增），**不改历史行**（`Ch9 §3.4.2` 追加式不可变）；
    - **幂等**：最新版本已具备同值时**不**再追加（重复跑 0 新增）；
    - 只对**最新版本**打补丁，返回本次**新增**行数。
    """
    from schema.models import Claim
    from schema.store import append_records, read_records

    rows = read_records(code_root, _CLAIMS_STEM)
    if not rows:
        return 0
    latest = {str(r.get("claim_id")): r for r in _latest_by_claim_id(rows)}
    seq = max((int(r.get("recorded_seq") or 0) for r in rows), default=0)

    updates: list[Any] = []
    for cid in sorted(set(plan.links) | set(counts)):
        rec = latest.get(cid)
        if rec is None:
            continue
        patch: dict[str, Any] = {}
        if cid in plan.links and not rec.get("origin_claim_id"):
            patch["origin_claim_id"] = plan.links[cid]
        if cid in counts and rec.get("independent_evidence_count") != counts[cid]:
            patch["independent_evidence_count"] = counts[cid]
        if not patch:
            continue
        seq += 1
        new_row = dict(rec)
        new_row.update(patch)
        new_row["recorded_seq"] = seq
        updates.append(Claim.model_validate(new_row))
    if not updates:
        return 0
    return append_records(code_root, _CLAIMS_STEM, updates)


def record_propagation(code_root: str | Path, summary: IndependenceSummary) -> int:
    """把传播行**追加**落库（`schema.store.append_records`，**唯一**写入口）。

    **幂等**：已存在的 `propagated_claim_id` 不再重复追加（append-only 下防重复）。
    返回本次**新增**行数。
    """
    from schema.store import append_records, read_records

    if not summary.propagation_rows:
        return 0
    existing = {
        str(row.get("propagated_claim_id")) for row in read_records(code_root, _PROPAGATION_STEM)
    }
    fresh = [row for row in summary.propagation_rows if row.propagated_claim_id not in existing]
    if not fresh:
        return 0
    return append_records(code_root, _PROPAGATION_STEM, fresh)


def classify_and_record(code_root: str | Path) -> IndependenceSummary:
    """**真跑通入口**：读 `facts/claims.jsonl` → ⑥产出 `origin_claim_id` → 分类 → 传播行落库。

    步骤（`Ch6 §C.2` 第 3 步）：
    1. 读 `claims` → **规划并落** `origin_claim_id`（`plan_origin_attribution` + `record_claim_updates`）；
    2. 把 `independent_evidence_count`（**基数**，T-12）落回根主张（同一写入口，追加新版本）；
    3. 分类 → 转述行落 `facts/claim_propagation.jsonl`（**只追加、不丢**）。

    真源 `claims.jsonl` 的**既有行只读不改**（`Ch9 §3.4.2` 追加式不可变）—— 本函数只**追加新版本**；
    真源缺失 → `read_records` 返回空列表（`G-03`：空样本显式记 note，不冒充"已验证"）。
    """
    from schema.store import read_records

    rows = read_records(code_root, _CLAIMS_STEM)
    plan = plan_origin_attribution(rows)
    effective = _apply_links(rows, plan.links)
    summary = classify_independence(effective)
    record_claim_updates(code_root, plan, summary.independent_evidence_count)
    record_propagation(code_root, summary)
    return summary
