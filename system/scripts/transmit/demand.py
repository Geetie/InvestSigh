"""`demand.py` —— **终端需求归因**（`Ch7 §C.4` / `§A.6` / `J6`）。

## 口径锚点（逐字对齐 `Ch7 §C.4`）

> 为每条路径段维护 `terminal_demand_id`；不同中间环节沿依赖链回溯到**同一
> `root_demand_entity`** 即判为同一终端需求 → **只计一次**；若两个下游共享同一终端需求，
> 按**分摊比例**分配（**不各自全额计入**）。

反例与期望行为（`Ch7 §C.4` 表）：同一份「AI 训练需求」经由
① 云厂商→GPU→代工 与 ② 云厂商→内存→设备 两条中间链路被分别计入终端需求 →
**终端需求计 2 份 → 冲击放大 2 倍（错误）**；正确行为是**回溯到同一 `root_demand_entity` → 只计 1 份**，
若干环节**按分摊比例分配**。

## 分摊比例算法（`Ch7 §J6`）

> **按已知经济暴露份额；未知则均分。**

因此：某 root 下若**所有**路径都带**已知**经济暴露份额（`economic_exposure_share`）→ 按份额**归一化**分配；
只要**任一条未披露**（`None`）→ 该 root 下**均分**（保守，不对未披露值点估计，承 `Ch7 §J5`）。

## 归并（`Ch7 §C.4` 的 union-find）

`Ch7 §C.4` 的算法逐字：**用 union-find 归并同根需求**。故本模块导出
`UnionFind` 与 `merge_roots()`：把「沿 `demand_signal` 边 / `claim.impact.affected_node` 回溯」得到的
**同根关系对**归并成 `terminal_demand_id → 代表根` 映射，再交由 `attribute_terminal_demand()` 分摊。

★ 本模块**不读配置、不碰阈值**（不属决策作用域输入）；`scripts/transmit/**` 亦**不出现**
`P-09` 命中词（无加权 / 打分 / 投票 / 情绪 / 粉丝数）—— 分摊一律用「**份额（share）**」语义。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

#: 每个 root 的分摊份额之和（归一化目标）。**不是判定门槛**，仅用于归一定义。
FULL_SHARE = 1.0


@dataclass(frozen=True)
class DemandPath:
    """一条**终端需求路径段**（`Ch7 §C.4`）。

    `root_demand_entity` 为**回溯结果**（沿 `demand_signal` 边 / `claim.impact.affected_node`
    逆推得到的根需求实体）；若调用方未提供，则由 `attribute_terminal_demand(root_of=...)`
    的映射或 `terminal_demand_id` 自身充当根。
    """

    path_id: str
    node_key: str
    terminal_demand_id: str
    root_demand_entity: str | None = None
    economic_exposure_share: float | None = None
    """已知经济暴露份额；`None` = **未披露** → 该 root 走**均分**（`Ch7 §J6`）。"""


@dataclass(frozen=True)
class DemandAllocation:
    """某 `root_demand_entity` 下的一次归因结果（`Ch7 §C.4`）。"""

    root_demand_entity: str
    path_ids: tuple[str, ...]
    allocated_share: dict[str, float] = field(default_factory=dict)
    """`path_id → 份额`；**和恒为 `FULL_SHARE`**（该 root **只计一次**）。"""

    counted_once: bool = True
    basis: str = ""
    """分摊依据：`known_exposure`（已知份额按比例）或 `equal_split`（未披露 → 均分）。"""


@dataclass(frozen=True)
class DemandAttribution:
    """一次终端需求归因的完整结果（确定性、可复现）。"""

    allocations: tuple[DemandAllocation, ...] = ()
    merged_roots: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """`root_demand_entity → 归入该根的全部 path_id`（升序）。"""

    dedup_saved: int = 0
    """若不归并、按路径各自全额计入，会**多计**的份数 = `路径数 - 根数`（≥0）。"""

    notes: tuple[str, ...] = ()


class UnionFind:
    """确定性 union-find（按字典序取代表，保证可复现）。

    `Ch7 §C.4` 逐字要求「用 union-find 归并同根需求」。
    """

    def __init__(self, members: Iterable[str]) -> None:
        self._parent: dict[str, str] = {m: m for m in members}

    def find(self, x: str) -> str:
        """取 `x` 所属分量的**代表**（路径压缩，代表 = 分量内字典序最小成员）。"""
        if x not in self._parent:
            self._parent[x] = x
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:      # 路径压缩（迭代，不用递归）
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: str, b: str) -> str:
        """归并两个分量，返回新的代表（取字典序较小者为代表）。"""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        keep, drop = (ra, rb) if ra <= rb else (rb, ra)
        self._parent[drop] = keep
        return keep

    def groups(self) -> dict[str, tuple[str, ...]]:
        """`代表 → 该分量全部成员`（成员升序，键升序）。"""
        out: dict[str, list[str]] = {}
        for member in self._parent:
            out.setdefault(self.find(member), []).append(member)
        return {rep: tuple(sorted(members)) for rep, members in sorted(out.items())}


def merge_roots(
    terminal_demand_ids: Iterable[str],
    same_root_pairs: Iterable[tuple[str, str]] = (),
) -> dict[str, str]:
    """把**同根关系对**归并成 `terminal_demand_id → 代表根`（`Ch7 §C.4` union-find）。"""
    union = UnionFind(terminal_demand_ids)
    for a, b in same_root_pairs:
        union.union(a, b)
    return {member: rep for rep, members in union.groups().items() for member in members}


def _allocate_shares(members: Sequence[DemandPath]) -> tuple[dict[str, float], str]:
    """该 root 下的分摊：已知份额按比例，任一无则均分（`Ch7 §J6`）。"""
    if members and all(p.economic_exposure_share is not None for p in members):
        total = sum(float(p.economic_exposure_share) for p in members)  # type: ignore[arg-type]
        shares = {p.path_id: float(p.economic_exposure_share) / total for p in members}  # type: ignore[arg-type]
        return shares, "known_exposure"
    even = FULL_SHARE / len(members) if members else 0.0
    return {p.path_id: even for p in members}, "equal_split"


def attribute_terminal_demand(
    paths: Sequence[DemandPath],
    *,
    root_of: Mapping[str, str] | None = None,
) -> DemandAttribution:
    """把终端需求归因到 `root_demand_entity`，**同根只计一次**（`Ch7 §C.4`）。

    根解析优先级：`DemandPath.root_demand_entity` → `root_of[terminal_demand_id]` → `terminal_demand_id`。

    错误路径（**响亮失败**，不静默兜底）：
    - `path_id` 重复 → `ValueError`；
    - 已知 `economic_exposure_share <= 0` → `ValueError`（份额非正无意义）。

    空样本：返回空归因并**显式记 `note`**（`CONVENTIONS §二 G-03`：不得当「已验证」）。
    """
    items = tuple(paths)
    if not items:
        return DemandAttribution(
            notes=("NO_DEMAND_PATHS: 无终端需求路径（空样本，不得当「已验证」；G-03）",)
        )

    seen: set[str] = set()
    for p in items:
        if p.path_id in seen:
            raise ValueError(f"重复的 path_id: {p.path_id!r}（归因要求路径身份唯一）")
        seen.add(p.path_id)
        if p.economic_exposure_share is not None and float(p.economic_exposure_share) <= 0:
            raise ValueError(
                f"economic_exposure_share 必须 > 0（path_id={p.path_id!r}，"
                f"实为 {p.economic_exposure_share}）—— 未披露请用 None（走均分）"
            )

    mapping = dict(root_of or {})
    grouped: dict[str, list[DemandPath]] = {}
    for p in sorted(items, key=lambda x: (x.path_id,)):
        root = p.root_demand_entity or mapping.get(p.terminal_demand_id) or p.terminal_demand_id
        grouped.setdefault(root, []).append(p)

    allocations: list[DemandAllocation] = []
    merged_roots: dict[str, tuple[str, ...]] = {}
    for root in sorted(grouped):
        members = tuple(grouped[root])
        shares, basis = _allocate_shares(members)
        path_ids = tuple(p.path_id for p in members)
        allocations.append(
            DemandAllocation(
                root_demand_entity=root,
                path_ids=path_ids,
                allocated_share=dict(shares),
                counted_once=True,
                basis=basis,
            )
        )
        merged_roots[root] = path_ids

    notes: tuple[str, ...] = ()
    if len(grouped) < len(items):
        notes = (
            "TERMINAL_DEMAND_DEDUP: 同一 root_demand_entity 的路径**只计一次**（Ch7 §C.4）；"
            f"归并后根数 {len(grouped)} < 路径数 {len(items)}",
        )
    return DemandAttribution(
        allocations=tuple(allocations),
        merged_roots=merged_roots,
        dedup_saved=len(items) - len(grouped),
        notes=notes,
    )
