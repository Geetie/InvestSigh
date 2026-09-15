"""schema 断言原语（`Ch2 §B.3` Checker-2 的公共实现）。

**作用域纪律（`Ch2 §B.1 ★禁词作用域通则` / `§B.3 Checker-2`）**：
`assert_absent(rec, ...)` 的断言对象 `rec` 是
`schema["defs"]["Recommendation"]["properties"]`——**仅该对象的字段名集合**。
**禁止**把它扩展成全仓 token 遍历：不得对 `scripts/**` 或全包文本做裸词 `position` 扫描。

反例（合法同名词，**不得误报**）：
- `position_listed`（"产业链位置"收录态，`Ch3 §C.2 N3.2-04`）
- `business_positions`（公司×节点多业务位置数据对象，`Ch9 §2.1.3 / §3.3.3`）
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


class SchemaAssertionError(AssertionError):
    """schema 断言失败——**命中即 fail**（`Ch2 §B.3`），不得降级为 warn。"""


def assert_absent(properties: Mapping[str, Any], fields: Iterable[str]) -> None:
    """断言 `properties`（**仅一个对象的字段名集合**）中**不存在**这些字段。

    违规 → 抛 `SchemaAssertionError`（非零退出由调用方负责）。
    """
    present = sorted(set(fields) & set(properties))
    if present:
        raise SchemaAssertionError(
            f"禁止字段出现在了该对象上: {present}（作用域 = 该对象字段名集合，"
            f"Ch2 §B.3 Checker-2）"
        )


def assert_present(properties: Mapping[str, Any], fields: Iterable[str]) -> None:
    """断言 `properties` 中**必须存在**这些字段；缺失 → fail。"""
    missing = sorted(set(fields) - set(properties))
    if missing:
        raise SchemaAssertionError(f"必填字段缺失: {missing}")


def enum_of(properties: Mapping[str, Any], field: str) -> list[Any]:
    """取某字段的枚举取值；不是枚举 → **响亮失败**（不返回兜底值）。"""
    spec = properties.get(field)
    if not isinstance(spec, Mapping):
        raise SchemaAssertionError(f"字段不存在: {field}")
    if "enum" not in spec:
        raise SchemaAssertionError(f"字段不是枚举: {field}（spec={spec!r}）")
    return list(spec["enum"])


def assert_gate_has_no_numeric_confidence(gate_input_fields: Iterable[str]) -> None:
    """决策门**只做结构完备性校验**，不含任何置信度数值阈值
    （`Ch2 §B.2 P-02` / `00_待拍板项清单` A5 / C123-5）。

    门只回答"该填的都填了吗"，不回答"分数够不够高"。
    """
    forbidden_tokens = (
        "confidence",
        "threshold",
        "min_",
        "minimum_",
        "score",
        "weight",
        "vote",
    )
    hits = sorted({f for f in gate_input_fields if any(t in f for t in forbidden_tokens)})
    if hits:
        raise SchemaAssertionError(
            f"决策门输入含置信度/阈值类字段: {hits}（P-02 / A5：门只做结构判定）"
        )


def load_object_properties(jsonschema_doc: Mapping[str, Any], object_name: str) -> dict[str, Any]:
    """从聚合 schema 取某对象的字段名集合（`schema["defs"][<object>]["properties"]`）。"""
    defs = jsonschema_doc.get("defs") or jsonschema_doc.get("$defs")
    if not isinstance(defs, Mapping):
        raise SchemaAssertionError("schema 文档缺少 `defs` / `$defs` 键")
    node = defs.get(object_name)
    if not isinstance(node, Mapping):
        raise SchemaAssertionError(f"schema 中不存在对象定义: {object_name}")
    props = node.get("properties")
    if not isinstance(props, Mapping):
        raise SchemaAssertionError(f"对象 {object_name} 缺少 properties")
    return dict(props)
