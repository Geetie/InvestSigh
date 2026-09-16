"""`scripts/evidence/` —— **第六章证据层**（`Ch6 §6.3` 第 3 步 + 第 6 步的代码落地）。

本包把「信息入口闸门」中两块**设计写明、此前未实现**的行为落成可测代码
（阶段③ `core_chain` 的两条并行流之一：`Ch6 证据层 ∥ Ch7 传导层`，`00_交付施工图 §5.2`）：

| 模块 | 能力 | 设计锚点 |
|---|---|---|
| `independence` | 追源去重 + 独立 / 转述判定（`T01`：10 转述 = 1 证据 + 10 传播） | `Ch6 §6.3` / `§C.1~§C.4` / `§F.2~§F.3` |
| `budget_gate` | 第 6 步预算闸门（时间 / 计算 / 检索三类取先到者） | `Ch6 §D.5` / `N6.3-08` / `N6.3-09` |

★ **不重造原语**（`G-06` 唯一真源）：本包**新增 0 条**指纹 / 定位 / 状态机 / 写库路径，
全部**调用**既有实现 —— `scripts/graph/fingerprint.py`（消息指纹）、
`scripts/validators/locator_check.py`（定位复查）、`scripts/claim/transition.py`（五态状态机）、
`schema/store.py`（唯一写入口）、`scripts/decision/triage.py`（`research_cap`）。

★ **惰性导入**（`CONVENTIONS.md §三 P-03` / PEP 562）：包 `__init__` 不在导入期急切拉起
子模块与 pydantic，避免拖慢只读 `__name__` 的轻量调用方。
"""

from __future__ import annotations

from typing import Any

__all__ = [
    # independence
    "IndependenceInputError",
    "IndependenceSummary",
    "claim_group_fingerprint",
    "classify_independence",
    "record_propagation",
    "classify_and_record",
    # budget_gate
    "BudgetConfigMissing",
    "BudgetStateError",
    "BudgetLimits",
    "BudgetUsage",
    "BudgetDecision",
    "GateOutcome",
    "TIME_CLASS",
    "COMPUTE_CLASS",
    "RETRIEVAL_CLASS",
    "BUDGET_CLASSES",
    "research_cap_for",
    "load_budget_limits",
    "evaluate_budget",
    "apply_budget_gate",
]

# 名字 → 定义它的子模块（`scripts.evidence.<module>`）。PEP 562：按需导入。
_EXPORTS: dict[str, str] = {
    "IndependenceInputError": "independence",
    "IndependenceSummary": "independence",
    "claim_group_fingerprint": "independence",
    "classify_independence": "independence",
    "record_propagation": "independence",
    "classify_and_record": "independence",
    "BudgetConfigMissing": "budget_gate",
    "BudgetStateError": "budget_gate",
    "BudgetLimits": "budget_gate",
    "BudgetUsage": "budget_gate",
    "BudgetDecision": "budget_gate",
    "GateOutcome": "budget_gate",
    "TIME_CLASS": "budget_gate",
    "COMPUTE_CLASS": "budget_gate",
    "RETRIEVAL_CLASS": "budget_gate",
    "BUDGET_CLASSES": "budget_gate",
    "research_cap_for": "budget_gate",
    "load_budget_limits": "budget_gate",
    "evaluate_budget": "budget_gate",
    "apply_budget_gate": "budget_gate",
}


def __getattr__(name: str) -> Any:
    """PEP 562 惰性导出：首次访问某名字时才导入其子模块。"""
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    return getattr(import_module(f"{__name__}.{module}"), name)


def __dir__() -> list[str]:
    return sorted(__all__)
