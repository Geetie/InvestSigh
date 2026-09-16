"""`system/schema` —— facts 对象模型的唯一定义与读写层。

对外导出：
- `models`      对象模型 / 五类时间 mixin / NumericClaim / DerivedValue / 全部枚举
- `stems`       `facts/` 事实表的 stem 注册表（**不依赖 pydantic**，供夹具等轻量消费方使用）
- `assertions`  `assert_present` / `assert_absent` / `assert_gate_has_no_numeric_confidence`
- `store`       追加式真源的追加 / 读取 / as-of / 索引重建

★ **本 `__init__` 采用惰性导入（PEP 562）**：
  `models` 依赖 pydantic，导入一次约 0.3s。而检查器里
  `from schema.assertions import assert_absent` 这样的语句会先执行
  `schema/__init__.py` —— 于是**每个守卫启动都要白付一次 pydantic 导入成本**
  （`check_L1` 实测 0.449s，其中大头就是它）。
  惰性化之后 `import schema` 几乎零成本，只有真正访问 `schema.models` 时才加载。
"""

from __future__ import annotations

from typing import Any

_EXPORTS_BY_MODULE: dict[str, tuple[str, ...]] = {
    ".assertions": (
        "SchemaAssertionError",
        "assert_absent",
        "assert_gate_has_no_numeric_confidence",
        "assert_present",
        "enum_of",
        "load_object_properties",
    ),
    ".models": ("JSONL_MODELS", "TBD", "model_for"),
    ".store": (
        "AppendOnlyViolation",
        "UnknownJsonlError",
        "append_records",
        "as_of",
        "jsonl_path",
        "read_models",
        "read_records",
        "rebuild_index",
    ),
}
_OWNER: dict[str, str] = {
    name: module for module, names in _EXPORTS_BY_MODULE.items() for name in names
}

__all__ = sorted(_OWNER)


def __getattr__(name: str) -> Any:
    """PEP 562：按需从子模块取属性（首次访问才真正 import）。"""
    module = _OWNER.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(module, __name__), name)


def __dir__() -> list[str]:
    return __all__
