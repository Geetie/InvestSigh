"""`scripts/daily/` —— **阶段④ `daily_run`（每日持续研究）** 的薄实现层。

**一句话**：把阶段④的三件"承重不变量"——**覆盖可核**、**故障降级保留上次有效结果**、
**同日重跑幂等**——落成可单测的确定性断言，并把"运行时刻/频率"接到 `p07` 的唯一读口。

| 模块 | 职责 | 设计锚点 |
|---|---|---|
| `coverage` | 阶段④ 硬判据 **`coverage_verifiable`（覆盖可核）** | `Ch3 §N3.2-03/04` · `施工图 §2 阶段④` · `10/01 §N10.1-06` |
| `degrade` | 故障降级：**保留上次有效结果** + **降级可见**（复用 `RunResult.degraded/blocked/gaps`） | `Ch8 §E` |
| `idempotency` | 同日重跑幂等（**复用**事件指纹 / 建议键 / 任务键） | `Ch8 §F` · `Ch9 §3.3.4/§3.4.7` · `Ch1 §C.3` |
| `schedule` | `p07` 配置化 rrule（**走 `get_param`**；缺文件 / `tbd` 响亮失败） | `Ch8 §D` · `Ch9 §3.10 J3` · `Ch11 §D.2` |
| `run` | 每日运行**薄封装**（复用 `Pipeline.run_daily`，不重写状态机） | `Ch1 §D.1` · `Ch8 §D` |

★ **惰性导入**（`CONVENTIONS.md §三 P-03` / PEP 562）：包 `__init__` 不在导入期急切拉起
  子模块与 pydantic（`Company` / `Task` ≈0.3s/次）。取子模块用 `from scripts.daily import coverage`
  或 `scripts.daily.coverage`（首次触碰时才 `import`）。

★ **复用优先**（纪律 11 / `G-06` 唯一真源）：本包**不重造**状态机、幂等键、真源读写或参数读口，
  一律调用既有模块的公开入口。
"""

from __future__ import annotations

import importlib
from typing import Any

_SUBMODULES = (
    "coverage",
    "degrade",
    "idempotency",
    "schedule",
    "run",
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
