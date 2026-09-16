"""`rollup.py` —— **分部 → 公司层**加总（`Ch4 §C.2` 末句逐字）。

## 设计锚点

> **汇总规则**：分部财务**在分部层完成后合并**，禁止跨业务直接引用指标
> （`scripts/valuelayer/rollup.py` 只做分部→公司层加总，**不做跨业务语义混用**）。

这句话里有**三条**可执行约束，逐条落成本模块的判定：

| # | 约束（原文） | 判据（可判定 + 穷尽） |
|---|---|---|
| 1 | **在分部层完成后**合并 | 每条贡献必须带 `chain_complete=True`；有任一条为 `False` ⇒ `IncompleteSegmentRollup`（**整次加总拒绝**，不给部分结果） |
| 2 | **禁止跨业务直接引用指标** | 每条贡献的 `metric_owner_business_id` 必须 `== business_id` ⇒ 否则 `CrossBusinessSemanticMismatch` |
| 3 | **不做跨业务语义混用** | 同一 `account` 的各贡献必须**同单位、同币种** ⇒ 否则 `CrossBusinessSemanticMismatch`（跨币种换算属 `scripts/compute/fx`，**不在这里顺手做** —— 那是算术，`G-06` 唯一真源） |

★ 为什么"不部分成功"（约束 1）：分部层没完成就先把完成的几个加出来，会产出一个
  **看起来像公司层数字**的东西，而它缺了几块 —— 正是 `Ch4 §G` 要拦的"形式上齐了、
  实质是空标题"的同族形态。故宁可整体拒绝。

★ 为什么不做跨币种换算：`Ch9 §3.4.4` 把 FX 明确划给 `scripts/compute/fx`。
  在这里顺手除一下，就出现了第二条汇率口径（`G-06`）。

★ 本模块**不排序、不打分、不加权**（`纪律 7` / `P-09`）：加总就是加总。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence


class RollupViolation(RuntimeError):
    """分部 → 公司层加总被拒（`Ch4 §C.2`）。**整次拒绝**，不给部分结果。"""


class IncompleteSegmentRollup(RollupViolation):
    """分部层未完成即试图合并（`Ch4 §C.2`："在分部层完成后合并"）。"""

    def __init__(self, offenders: Sequence[str]) -> None:
        self.offenders = tuple(offenders)
        super().__init__(
            f"IncompleteSegmentRollup: {len(self.offenders)} 个分部尚未完成 "
            f"（{list(self.offenders)}）—— Ch4 §C.2 要求'在分部层完成后合并'，"
            "不得先合并一个缺块的所谓公司层数字"
        )


class CrossBusinessSemanticMismatch(RollupViolation):
    """跨业务引用指标 / 同一科目跨业务语义不一致（`Ch4 §C.2`）。"""

    def __init__(self, detail: str) -> None:
        super().__init__(f"CrossBusinessSemanticMismatch: {detail}")


class DuplicateContribution(RollupViolation):
    """同一 (business_id, account) 出现多行 —— 会**重复计数**，必须拒。"""

    def __init__(self, keys: Sequence[tuple[str, str]]) -> None:
        super().__init__(
            f"DuplicateContribution: 同一 (business_id, account) 出现多行 {list(keys)} —— "
            "加总会重复计数；分部内应先自行加总（Ch4 §C.2 的分部层职责）"
        )


@dataclass(frozen=True)
class SegmentContribution:
    """一个分部对**一个**财务科目的贡献（`Ch4 §C.2` / `§C.4` 的三层映射末端）。

    字段名刻意保持在**分部层**口径：`business_id` 是"这条数字属于哪个分部"，
    `metric_owner_business_id` 是"这个指标是谁的"。两者必须相等 —— 这个区分
    就是约束 2 的**可判定**形式（只用 `business_id` 一个字段的话，
    "跨业务引用的指标"在数据上**不可见**，也就无法被拦）。
    """

    business_id: str
    metric_owner_business_id: str
    account: str
    value: Decimal
    unit: str = ""
    currency: str = ""
    chain_complete: bool = False


@dataclass(frozen=True)
class CompanyRollup:
    """公司层加总结果（**分部 → 公司**，`Ch4 §C.2`）。"""

    by_account: Mapping[str, Decimal]
    businesses: tuple[str, ...]
    contributions: int
    detail: Mapping[str, str] = field(default_factory=dict)


def _dec(value: Any) -> Decimal:
    """转 `Decimal`（`Ch9 §3.4.5`：落库数字用十进制，避免浮点误差）。"""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def rollup(contributions: Iterable[SegmentContribution]) -> CompanyRollup:
    """分部 → 公司层加总（`Ch4 §C.2`）。任一约束不满足 ⇒ **抛异常、不给部分结果**。

    检查顺序刻意是"先结构性、后数值性"：先证明"这份输入**允许**被合并"
    （约束 1/2），再证明"合并**结果**有意义"（约束 3）。
    """
    rows = list(contributions)
    if not rows:
        # G-03：无被检对象必须**显式**，不得返回一个空 dict 冒充"加总完成"。
        return CompanyRollup(
            by_account={},
            businesses=(),
            contributions=0,
            detail={"note": "NO_CONTRIBUTIONS: 无任何分部贡献可加总（真空成立，不是'已加总'，G-03）"},
        )

    incomplete = [f"{r.business_id}:{r.account}" for r in rows if not r.chain_complete]
    if incomplete:
        raise IncompleteSegmentRollup(incomplete)

    cross = [
        f"{r.business_id}:{r.account} 的指标归属为 {r.metric_owner_business_id!r}"
        for r in rows
        if r.metric_owner_business_id != r.business_id
    ]
    if cross:
        raise CrossBusinessSemanticMismatch(
            "禁止跨业务直接引用指标（Ch4 §C.2）：" + "；".join(cross)
        )

    seen: set[tuple[str, str]] = set()
    dups: list[tuple[str, str]] = []
    for r in rows:
        key = (r.business_id, r.account)
        if key in seen:
            dups.append(key)
        seen.add(key)
    if dups:
        raise DuplicateContribution(dups)

    # 约束 3：同一科目的单位/币种必须唯一（**跨业务语义混用**的判据）。
    units: dict[str, set[str]] = {}
    currencies: dict[str, set[str]] = {}
    for r in rows:
        units.setdefault(r.account, set()).add(r.unit)
        currencies.setdefault(r.account, set()).add(r.currency)
    mixed_units = {a: sorted(u) for a, u in units.items() if len(u) > 1}
    mixed_ccy = {a: sorted(c) for a, c in currencies.items() if len(c) > 1}
    if mixed_units:
        raise CrossBusinessSemanticMismatch(
            f"同一科目在不同分部使用了不同单位 {mixed_units} —— 跨业务语义混用；"
            "单位换算属 scripts/compute/，不在此处顺手做（G-06）"
        )
    if mixed_ccy:
        raise CrossBusinessSemanticMismatch(
            f"同一科目在不同分部使用了不同币种 {mixed_ccy} —— 跨币种换算属 "
            "scripts/compute/fx（Ch9 §3.4.4），不在此处顺手做（G-06）"
        )

    by_account: dict[str, Decimal] = {}
    for r in rows:
        by_account[r.account] = by_account.get(r.account, Decimal(0)) + _dec(r.value)
    detail = {a: f"{len([r for r in rows if r.account == a])} 个分部合并，单位={sorted(u)[0]}" for a, u in units.items()}
    return CompanyRollup(
        by_account=dict(sorted(by_account.items())),
        businesses=tuple(sorted({r.business_id for r in rows})),
        contributions=len(rows),
        detail=detail,
    )
