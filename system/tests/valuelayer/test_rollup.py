"""`Ch4 §C.2` 末句 —— **分部 → 公司层加总**的三条约束（逐条正反用例）。

设计原句（逐字）：

> **汇总规则**：分部财务**在分部层完成后合并**，禁止跨业务直接引用指标
> （`scripts/valuelayer/rollup.py` 只做分部→公司层加总，**不做跨业务语义混用**）。

本文件把这一句拆成三条**可判定**的约束各配一对正反用例（`G-05`）：

| 用例组 | 约束 | 反例的形态 |
|---|---|---|
| `test_rollup_sums_*` / `test_rollup_refuses_*` | ① "在分部层完成后合并" | 任一分部 `chain_complete=False` |
| … | ② "禁止跨业务直接引用指标" | `metric_owner_business_id ≠ business_id` |
| … | ③ "不做跨业务语义混用" | 同一科目**混单位 / 混币种** |

★ 本模块**无 CLI**（设计把它归为"脚本"，`00_交付施工图.md` 的类别是 C 而非"检查器"），
  故这里不写退出码用例；退出码契约由 `tests/valuelayer/test_completeness.py` 等同批检查器覆盖。
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from scripts.valuelayer.rollup import (
    CompanyRollup,
    CrossBusinessSemanticMismatch,
    DuplicateContribution,
    IncompleteSegmentRollup,
    SegmentContribution,
    rollup,
)


def _c(
    business_id: str = "BIZ-1",
    account: str = "revenue",
    value: str = "100",
    *,
    owner: str | None = None,
    unit: str = "usd",
    currency: str = "usd",
    chain_complete: bool = True,
) -> SegmentContribution:
    """一条分部贡献（默认**合规**：完成、指标归属本分部、同单位同币种）。"""
    return SegmentContribution(
        business_id=business_id,
        metric_owner_business_id=owner if owner is not None else business_id,
        account=account,
        value=Decimal(value),
        unit=unit,
        currency=currency,
        chain_complete=chain_complete,
    )


# ───────────────────────── 正向：加总本身 ─────────────────────────


def test_rollup_sums_two_segments_per_account() -> None:
    """两个分部各报 `revenue` ⇒ 公司层是**按科目**的加总（不是按分部罗列）。"""
    result = rollup([_c("BIZ-1", "revenue", "100"), _c("BIZ-2", "revenue", "50")])
    assert isinstance(result, CompanyRollup)
    assert result.by_account == {"revenue": Decimal("150")}
    assert result.businesses == ("BIZ-1", "BIZ-2")
    assert result.contributions == 2


def test_rollup_keeps_accounts_separate() -> None:
    """不同科目各加各的 —— 加总**不跨科目**（跨科目是语义混用）。"""
    result = rollup([_c("BIZ-1", "revenue", "100"), _c("BIZ-2", "cogs", "40")])
    assert result.by_account == {"cogs": Decimal("40"), "revenue": Decimal("100")}


def test_rollup_uses_decimal_not_float() -> None:
    """`Ch9 §3.4.5`：落库数字用十进制 —— 浮点加总会给出 `0.30000000000000004`。"""
    result = rollup([_c("BIZ-1", "revenue", "0.1"), _c("BIZ-2", "revenue", "0.2")])
    assert result.by_account["revenue"] == Decimal("0.3")
    assert str(result.by_account["revenue"]) == "0.3"


def test_rollup_with_no_contributions_is_vacuous_not_done() -> None:
    """★ `G-03`：**没有**任何贡献 ≠ "加总完成" ⇒ 必须显式记 `NO_CONTRIBUTIONS`。

    ★ 为什么不能返回一个空 dict 了事：空 dict 与"两个分部各为 0 的加总"
      在结构上**逐字相同**，而后者是一个（可疑的）结论。
    """
    result = rollup([])
    assert result.by_account == {}
    assert result.contributions == 0
    assert "NO_CONTRIBUTIONS" in result.detail["note"]


# ─────────────────── 反向 ①：未完成的分部不得先合并 ───────────────────


def test_rollup_refuses_when_any_segment_is_incomplete() -> None:
    """约束 ①：任一分部 `chain_complete=False` ⇒ **整次加总拒绝**，且点出是哪几个。"""
    with pytest.raises(IncompleteSegmentRollup) as excinfo:
        rollup([_c("BIZ-1", "revenue", "100"), _c("BIZ-2", "revenue", "50", chain_complete=False)])
    assert "BIZ-2:revenue" in excinfo.value.offenders


def test_rollup_gives_no_partial_result_when_incomplete() -> None:
    """★ 拒绝时**不得**顺手返回"已完成的那几个"的和 —— 那会产出缺块的假公司层数字。

    ★ 这条是约束 ① 的**判别力**所在：一个"先过滤掉未完成、再加总"的实现
      在 `test_rollup_refuses_when_any_segment_is_incomplete` 上会红，
      但如果只把异常收窄成 warn，本用例仍能红（`produced` 与"是否拒绝"是两件事）。
    """
    try:
        rollup([_c("BIZ-1", "revenue", "100"), _c("BIZ-2", "revenue", "50", chain_complete=False)])
    except IncompleteSegmentRollup:
        return
    raise AssertionError("未完成分部被静默跳过 —— 加总必须整体拒绝，不得给部分结果")


# ─────────────────── 反向 ②：禁止跨业务直接引用指标 ───────────────────


def test_rollup_refuses_cross_business_metric_reference() -> None:
    """约束 ②：贡献里引用的指标归属**别的**业务 ⇒ 拒（`Ch4 §C.2`）。"""
    with pytest.raises(CrossBusinessSemanticMismatch) as excinfo:
        rollup([_c("BIZ-1", "revenue", "100", owner="BIZ-2")])
    assert "BIZ-2" in str(excinfo.value)


def test_cross_business_field_is_what_makes_the_violation_visible() -> None:
    """★ 判据为何要**两个**字段：只留 `business_id` 时"跨业务引用的指标"在数据上不可见。

    同一条数值，`owner` 与 `business_id` 一致 ⇒ 通过；把 `owner` 换成别人 ⇒ 拒。
    两行只差 `metric_owner_business_id` **一个字段** ⇒ 判别力可归因到该字段（`C-03` 同族思路）。
    """
    assert rollup([_c("BIZ-1", "revenue", "100")]).contributions == 1
    with pytest.raises(CrossBusinessSemanticMismatch):
        rollup([_c("BIZ-1", "revenue", "100", owner="BIZ-9")])


# ─────────────────── 反向 ③：不做跨业务语义混用（单位/币种） ───────────────────


def test_rollup_refuses_mixed_units_on_the_same_account() -> None:
    """约束 ③：同一科目在不同分部用了不同单位 ⇒ 拒（换算属 `scripts/compute/`，不在此处顺手做）。"""
    with pytest.raises(CrossBusinessSemanticMismatch) as excinfo:
        rollup([_c("BIZ-1", "revenue", "100", unit="usd"), _c("BIZ-2", "revenue", "50", unit="cny")])
    assert "不同单位" in str(excinfo.value)


def test_rollup_refuses_mixed_currencies_on_the_same_account() -> None:
    """约束 ③：同一科目混币种 ⇒ 拒（跨币种换算属 `scripts/compute/fx`，`Ch9 §3.4.4`）。"""
    with pytest.raises(CrossBusinessSemanticMismatch) as excinfo:
        rollup([_c("BIZ-1", "revenue", "100", currency="usd"), _c("BIZ-2", "revenue", "50", currency="cny")])
    assert "不同币种" in str(excinfo.value)


def test_rollup_allows_same_unit_across_segments() -> None:
    """**反向对照**（`G-05`）：同单位同币种 ⇒ 正常加总，证明上面两条不是"见多分部就拒"。"""
    result = rollup([_c("BIZ-1", "revenue", "100", unit="usd"), _c("BIZ-2", "revenue", "50", unit="usd")])
    assert result.by_account == {"revenue": Decimal("150")}


# ─────────────────── 反向 ④：重复贡献会重复计数 ───────────────────


def test_rollup_refuses_duplicate_contributions() -> None:
    """同一 `(business_id, account)` 出现多行 ⇒ 拒（会在公司层**重复计数**）。"""
    with pytest.raises(DuplicateContribution):
        rollup([_c("BIZ-1", "revenue", "100"), _c("BIZ-1", "revenue", "100")])


def test_duplicate_check_is_per_business_not_global() -> None:
    """**反向对照**：不同分部的同科目**不是**重复（那正是加总要合并的东西）。"""
    assert rollup([_c("BIZ-1", "revenue", "100"), _c("BIZ-2", "revenue", "100")]).contributions == 2


# ─────────────────── 不排序、不打分（`纪律 7` / `P-09`） ───────────────────


def test_rollup_result_exposes_no_score_or_rank_field() -> None:
    """加总就是加总：结果对象里**不得**出现打分 / 排序 / 加权字段（`纪律 7` / `P-09`）。

    ★ 为什么用结构性断言：这类字段一旦加进来，下游就会开始"按分数选公司"，
      而那已被 `Ch2 §B.2 P-01` 明确禁止。断言字段集能让这件事在**加进来那一刻**变红。
    """
    names = {f.name for f in dataclasses.fields(CompanyRollup)}
    assert names == {"by_account", "businesses", "contributions", "detail"}
    assert not {n for n in names if n in {"score", "rank", "weight", "rating"}}
