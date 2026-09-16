"""`scripts/decision/` —— **决策层**（`施工图 §3.2` 决策（C）：`gate` / `rules` / `triage`）。

**一句话**：把「证据（`Ch6 claims`）+ 确定性计算（`scripts/compute` 的 `DerivedValue`）」
转成**可解释、可追溯、无加权、无新增门槛**的股票建议 —— 是阶段③ `core_chain`
从"采集"走到"建议"的**最后一环**。

| 模块 | 职责 | 设计锚点 |
|---|---|---|
| `triage` | 三维正交决策函数（**序** `priority_order` / **信** `is_adoptable` / **深** `research_cap`）+ `DecisionView` | `Ch6 §B.2 / §B.3` |
| `gate` | 建议决策**前置门**（研究完成 / 可解释预测 / `DerivedValue` 强制 / 提前判断三要素） | `Ch7 §D.2 / §D.5 / §D.7` |
| `rules` | **5 规则**决策引擎（R1 买入 / R2 卖出 / R3 待判断 / R4 维持 / R5 强制复查）+ `boundary_unresolved` | `Ch7 §D.1 / §D.3 / §D.4 / §E` |
| `step` | 对编排器的**接线接缝**（`StepHandler` 签名一致；注册动作待主理人集成） | `Ch9 §3.5` 阶段④ |
| `run_decide` | **真实运行**入口（读行情点 → `compute` 出 `DerivedValue` → 决策 → 落 `facts/recommendations.jsonl`） | `Ch7 §F` 端到端时序 |

★ **惰性导入**（`CONVENTIONS.md §三 P-03` / PEP 562）：包 `__init__` 不在导入期
  急切拉起子模块与 pydantic（`DerivedValue` / `Recommendation` ≈0.3s/次），
  避免拖慢只读 `__name__` 的轻量调用方。取子模块用 `from scripts.decision import rules`
  或 `scripts.decision.rules`（首次触碰时才 `import`）。

★ **最严守卫集中于本包**（`Ch2 §B.2`）：P-09 禁词（无加权/打分/投票）、P-06 门输入结构、
  参数不进决策函数（`Ch11 §E.1`）。本包文件全部在 `decision_scope.include_paths` 内，
  `conflict_scan`（L2/L4）与 `freeze_guard` 会**真扫**本包。
"""

from __future__ import annotations

import importlib
from typing import Any

_SUBMODULES = (
    "triage",
    "gate",
    "rules",
    "step",
    "run_decide",
)

__all__ = list(_SUBMODULES)


def __getattr__(name: str) -> Any:
    """PEP 562：子模块按需导入（首次访问才付出 pydantic / yaml 的导入成本）。"""
    if name in _SUBMODULES:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals()) + list(_SUBMODULES))
