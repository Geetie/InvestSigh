"""注入防护执行器包（`Ch9 §3.2.1` / `§3.4.6`；落位 `Ch6 §0`）。

包内含四措施的代码落点（数据/指令物理分离 → 规则只读 → 工具白名单 → 主张性质强制）
与真实编排入口 `executor`。

★ **惰性导出（PEP 562）**：本 `__init__` **不在模块级急切导入**任何子模块 ——
  子模块（`claims` / `executor`）会经 `schema.models` 触发 **pydantic** 导入
  （≈0.3s/次，规避 `D-21`）。调用方**按需** `from scripts.guard import executor`，
  由 Python 在首次访问时加载对应子模块。

★ **无全局副作用**：不修改 `sys.path` / `sys.modules` / 不装审计钩子（规避 `D-23`）。

★ **不用 `importlib`**：数据路径不得出现工具原语（`checks/injection_guard.py` 断言 B）。
  故 `__getattr__` 用**显式子模块 import 语句**实现惰性加载，逐名分支、无动态导入。

子模块一览（`Ch9 §3.4.6` 四措施逐条对齐）：

| 措施 | 子模块 |
|---|---|
| ① 数据/指令物理分离（载体侧） | `rawsink` |
| ① 数据/指令物理分离（prompt 侧） | `annotate` |
| ② 规则只读（唯一写口） | `rulewrite` |
| ③ 工具白名单（唯一收口点） | `toolwatch` |
| ④ 主张性质强制（唯一构造口） | `claims` |
| 编排入口 | `executor` |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "annotate",
    "claims",
    "executor",
    "rawsink",
    "rulewrite",
    "toolwatch",
]

# 仅用于类型检查的导入（运行期不触发子模块加载 → 不牵出 pydantic）
if TYPE_CHECKING:  # pragma: no cover - 仅供静态检查
    from . import annotate, claims, executor, rawsink, rulewrite, toolwatch


def __getattr__(name: str) -> Any:
    """PEP 562 惰性加载：`scripts.guard.<submodule>` 首次访问时才导入。

    ★ 用**显式** `from . import <name>` 语句（非动态导入），使数据路径不含工具原语。
    """
    if name == "annotate":
        from . import annotate

        return annotate
    if name == "rawsink":
        from . import rawsink

        return rawsink
    if name == "rulewrite":
        from . import rulewrite

        return rulewrite
    if name == "toolwatch":
        from . import toolwatch

        return toolwatch
    if name == "claims":
        from . import claims

        return claims
    if name == "executor":
        from . import executor

        return executor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
