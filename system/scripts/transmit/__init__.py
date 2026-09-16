"""`scripts/transmit/` —— **传导引擎**（`Ch7 §C.1`：`engine.py` 编排 + `demand.py` 终端需求归因）。

**一句话**：把「依赖图原语（`scripts/graph/**`）」**编排**成 `Ch7 §C` 的传导能力 ——
给定一次上游撤回或一次事件冲击，产出**逐层可达的下游集合**与**逐跳影响（六要素）**，
并**复用**既有入队出口落 `recheck` 任务。**只编排、不重造**（`纪律 11` / `G-06`）。

| 模块 | 职责 | 设计锚点 |
|---|---|---|
| `engine` | 传导编排：撤回传导（逐层下游 + `recheck` 入队）/ 事件 → 逐跳影响（六要素 + 路径 + 待核验线索） | `Ch7 §C.1 / §C.2 / §C.6` · `Ch9 §3.4.3` |
| `demand` | 终端需求归因：union-find 同根归并 + 分摊（只计一次） | `Ch7 §C.4 / §A.6` · `J6` |

★ **本包只调用不重造**：可达性 / 环检测 / 深度取自 `scripts.graph.closure.forward_closure`；
停止判定调 `scripts.graph.stop.should_stop`；跳级等同调 `scripts.graph.stage_order.assert_not_equivalent`；
入队调 `scripts.graph.propagate.propagate_retraction`。**不复制**上述任何逻辑。

★ **参数不进决策函数**（`施工图 §8 纪律 1` / `P-09`）：一切阈值由调用方显式传入
（`scripts.graph.stop.TransmitParams`）或读 `rules/transmission.yaml`（唯一真源，值待冻结）；
本包**不内置任何数值门槛**。缺文件 / 缺参数 → **响亮失败**（不静默兜底）。

★ **惰性导入**（`CONVENTIONS.md §三 P-03` / PEP 562）：包 `__init__` 不在导入期急切拉起子模块。

★ **决策作用域禁词**（`Ch2 §B.2` P-09）：本包代码 / docstring / 字符串**不出现**命中词。
"""

from __future__ import annotations

import importlib
from typing import Any

_SUBMODULES = (
    "engine",
    "demand",
)

__all__ = list(_SUBMODULES)


def __getattr__(name: str) -> Any:
    """PEP 562：子模块按需导入（首次触碰才付出 pydantic / yaml 的导入成本）。"""
    if name in _SUBMODULES:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals()) + list(_SUBMODULES))
