"""`scripts/valuelayer/` —— **第四章《公司价值研究与深度标准》** 的确定性实现层。

**一句话**（`Ch4 §I` 的"自建"清单逐字）：第四章把「赚钱机制 / 指标集路由 / 增长代价 /
护城河反误判 / 3×4 状态机 / 形式完备性校验器」这些**必须可单测的确定性判定**建成代码；
"内容由模型抽取/叙述"的部分（底稿生成、机制结构化）不在本层。

| 模块 | 职责 | 设计锚点 |
|---|---|---|
| `route_guard` | 多业务多指标集绑定**防串味**（`MetricSetMismatch`）+ `MS-GENERIC` 兜底 | `Ch4 §C` |
| `rollup` | **分部 → 公司层**加总（**不做跨业务语义混用**） | `Ch4 §C.2` 末句 |
| `growth_quality` | 增长质量 / ROIIC / **代价五类** + **收入增速 denylist 守卫** | `Ch4 §D` |
| `moat_guard` | **护城河反误判**（单点证据拒绝）+ 六保护对象 + 四类来源区分 + **价格硬隔离** | `Ch4 §F` |
| `state_machine` | 3×4 价值状态机 + 增量更新 + **无变化分支**（不产新版本） | `Ch4 §H` |
| `completeness` | **形式完备性校验器**（`form_complete` 五项逐项可判定）+ `gap` 衔接 | `Ch4 §G.2/§G.3/§G.4` |
| `_rules` | `rules/{baseline,metric-sets}.yaml` 的**唯一读口**（`G-06`） | `Ch11 §D.2` |

★ **惰性导入**（`CONVENTIONS.md §三 P-03` / PEP 562）：本包不在导入期急切拉起子模块与
  pydantic（`schema.models` ≈0.3s/次）——`scripts/delivery/stage_gate.py` 会 import 本包，
  而它属于 `pre-commit` 的路径。取子模块用 `from scripts.valuelayer import completeness`
  或 `scripts.valuelayer.completeness`（首次触碰时才 `import`）。

★ **复用优先**（纪律 11 / `G-06` 唯一真源）：本包**不重造**算术（一律走 `scripts/compute/`）、
  不重造 `gap` 对象（复用 `Ch9 N9.1-21`）、不重造真源读写（`schema.store`）。
"""

from __future__ import annotations

import importlib
from typing import Any

_SUBMODULES = (
    "route_guard",
    "rollup",
    "growth_quality",
    "moat_guard",
    "state_machine",
    "completeness",
)

__all__ = list(_SUBMODULES)


def __getattr__(name: str) -> Any:
    """PEP 562：子模块按需导入（首次访问才付出 yaml / pydantic 的导入成本）。"""
    if name in _SUBMODULES:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals()) + list(_SUBMODULES))
