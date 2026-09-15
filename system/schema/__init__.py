"""`system/schema` —— facts 8 类对象模型的唯一定义与读写层。

对外导出：
- `models`      8 类对象 / 五类时间 mixin / NumericClaim / DerivedValue / 全部枚举
- `assertions`  `assert_present` / `assert_absent` / `assert_gate_has_no_numeric_confidence`
- `store`       追加式真源的追加 / 读取 / as-of / 索引重建
"""

from .assertions import (
    SchemaAssertionError,
    assert_absent,
    assert_gate_has_no_numeric_confidence,
    assert_present,
    enum_of,
    load_object_properties,
)
from .models import JSONL_MODELS, TBD, model_for
from .store import (
    AppendOnlyViolation,
    UnknownJsonlError,
    append_records,
    as_of,
    jsonl_path,
    read_models,
    read_records,
    rebuild_index,
)

__all__ = [
    "JSONL_MODELS",
    "TBD",
    "AppendOnlyViolation",
    "SchemaAssertionError",
    "UnknownJsonlError",
    "append_records",
    "as_of",
    "assert_absent",
    "assert_gate_has_no_numeric_confidence",
    "assert_present",
    "enum_of",
    "jsonl_path",
    "load_object_properties",
    "model_for",
    "read_models",
    "read_records",
    "rebuild_index",
]
