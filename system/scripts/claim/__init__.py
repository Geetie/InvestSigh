"""`system/scripts/claim` —— 主张层**状态机**包（`Ch6 §E` · `00_交付施工图 §3.2`）。

首批交付 `transition`：主张五态状态机（`pending_verification` / `supported` / `disputed` /
`refuted` / `superseded`）+ `superseded` 传播（复用 `scripts/graph/forward_closure`，`Ch6 §E.4`）。

★ **惰性导出（PEP 562）**：本 `__init__` **不在模块级急切导入**子模块 —— 子模块经
  `schema.models` 触发 **pydantic** 导入（≈0.3s/次，规避 `D-21`）。调用方**按需**
  `from scripts.claim import transition`，由 Python 在首次访问时加载。

★ **无全局副作用**：不修改 `sys.path` / `sys.modules` / 不装审计钩子（规避 `D-23`）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["transition"]

if TYPE_CHECKING:  # pragma: no cover - 仅供静态检查，运行期不触发子模块加载
    from . import transition


def __getattr__(name: str) -> Any:
    """PEP 562 惰性加载：`scripts.claim.<submodule>` 首次访问时才导入。

    ★ 用 `importlib.import_module`（同 `schema/__init__.py`）而非 `from . import X` ——
      后者在该 `__getattr__` 内会经 `_handle_fromlist` → `hasattr(pkg, X)` 回到本函数，
      造成**无限递归**（实测 `RecursionError`）。
    """
    if name == "transition":
        import importlib

        return importlib.import_module(".transition", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
