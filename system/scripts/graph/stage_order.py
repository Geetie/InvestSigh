"""`stage_order.py` —— 五者语义层级的**程序约束**（禁跳级等同，`Ch7 §B.4`）。

`Ch7 §B.4`（逐字）：五者语义层 = 订单 / 采购承诺 / 资本开支 / 排产 / 收入；
「实」的排序（从最实到最虚）：`revenue > production_schedule > capex > purchase_commitment > order`。

**程序约束（代码拒绝把 A 当作 B）**：

- **`capex` 属需求侧，不得作为供应商的供给证据** —— `capex` 不得直接等同 `order` / `revenue`
  （对齐 N7.2-05 电力那一跳与 C.7 的「不能从 GPU 需求直接推所有能源公司受益」）。
- **跳级**：实性排序中**相邻跨级**（差 ≤ 1）允许；**跨越一级以上**（差 > 1）必须携带
  **中间阶段证据**（`skip_evidence(evidence)` 为真），否则拒绝（对齐 T03：官方仅"验证完成"
  不得自动升级到订单 / 收入）。

★ 本模块只承载 `Ch7 §B.4` 的**语义层级 + 拒绝规则**；`relations.relation_progress_stage`
  （合作阶段枚举，`schema/models.py`）是**另一维度**，二者**不得互用**（`Ch2 §C.2 R-15 ②`）。
"""

from __future__ import annotations

from typing import Any, Mapping

# 逐字取自 `Ch7 §B.4` 的程序约束片段
STAGE_ORDER: dict[str, int] = {
    "order": 0,
    "purchase_commitment": 1,
    "capex": 2,
    "production_schedule": 3,
    "revenue": 4,
}

#: `capex` 的**需求侧**语义（`Ch7 §B.4`）：不得与供应商的供给结果同等看待。
CAPEX_STAGE = "capex"
SUPPLIER_SUPPLY_STAGES = frozenset({"order", "revenue"})


class StageEquivalenceError(ValueError):
    """把 A 当作 B（跳级等同 / 需求侧冒充供给）—— 落库前拦截（`Ch7 §B.4`）。"""


def stage_rank(stage: str) -> int:
    """取某阶段的「实」性排序位（越大越实）；未知阶段 → `ValueError`。"""
    if stage not in STAGE_ORDER:
        raise ValueError(f"未知阶段: {stage!r}；合法值 {sorted(STAGE_ORDER)}")
    return STAGE_ORDER[stage]


def skip_evidence(evidence: Mapping[str, Any] | None) -> bool:
    """`Ch7 §B.4` 程序片段引用的判据：**是否携带允许跳级的中间阶段证据**。

    具体化为：`evidence` 为映射且带显式 `skip_justification`（非空）时为真；
    缺省为假 —— **保守**（没有中间阶段证据就不放行跳级）。
    """
    if not isinstance(evidence, Mapping):
        return False
    return bool(evidence.get("skip_justification"))


def assert_not_equivalent(
    from_stage: str,
    to_stage: str,
    *,
    evidence: Mapping[str, Any] | None = None,
) -> None:
    """禁止跳级等同；`capex` 属需求侧，不得作为供应商的供给证据（`Ch7 §B.4`）。

    满足条件则返回 `None`；违反则抛 `StageEquivalenceError`。
    """
    rank_from = stage_rank(from_stage)
    rank_to = stage_rank(to_stage)

    if from_stage == CAPEX_STAGE and to_stage in SUPPLIER_SUPPLY_STAGES:
        raise StageEquivalenceError("capex(需求侧) ≠ 供应商订单/收入")
    if rank_to - rank_from > 1 and not skip_evidence(evidence):
        raise StageEquivalenceError(f"{from_stage} 不能直接等同 {to_stage}（缺中间阶段证据）")


def is_adjacent(from_stage: str, to_stage: str) -> bool:
    """两阶段在「实」性排序上是否相邻（差 == 1）。"""
    return abs(stage_rank(to_stage) - stage_rank(from_stage)) == 1
