"""`scripts/compute/` —— 确定性计算层（`Ch9 §3.4.4`，C 档最重自建块）。

**一句话**（`Ch9 §N9.2-03`）：**算术由程序层承担，模型不口算**。
同比 / 复合增长率 / 毛利率 / CAGR / 超额收益 / 含分红再投资总回报 / FX / 股本变化 /
企业价值 / 价格隐含增长率 —— 一律由本层的确定性函数产出并单测，落库数字必须能追到 operand。

子模块（`Ch9 §3.4.4` 目录）：

| 模块 | 职责 |
|---|---|
| `contract` | 契约：异常族 / 缺口对象 `ComputeGap` / `DerivedValue` 唯一构造入口 |
| `core` | 通用算子：同比 / CAGR / 差分比率 / 变化率 |
| `growth` | ROIIC + **增长质量分档**（`Ch4 §D.3`，不压成单一分数） |
| `margin` | 毛利率 / 营业利润率 / 净利率 |
| `returns` | **先复权再总回报**（`Ch9 §3.4.9`）+ 基准口径（`Ch3 §D.2`，只调 `return_guard`） |
| `fx` | 汇率换算与含汇率变动的收益 |
| `shares` | EPS / 每股价值 / 股本变化率 |
| `valuation` | 每股价区间（`Ch5 §D.2/§D.6`）+ 顺序约束（`§D.3`） |
| `store` | `derived/` 追加式持久化（`Ch9 §3.3.3`） |
| `driver` | 真实运行编排（读事实 → 算 → 落盘） |
| `step` | 对编排器的接线接缝（`Ch9 §3.5` 阶段④/⑤/⑥） |

★ **惰性导入**（`CONVENTIONS.md P-03` / PEP 562）：`import scripts.compute` **不**急切导入
  pydantic（`DerivedValue` ≈0.3s/次）。取子模块用 `from scripts.compute import returns`
  或 `scripts.compute.returns`（首次触碰时才 `import`）。
"""

from __future__ import annotations

import importlib
from typing import Any

_SUBMODULES = (
    "contract",
    "core",
    "growth",
    "margin",
    "returns",
    "fx",
    "shares",
    "valuation",
    "store",
    "driver",
    "step",
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
