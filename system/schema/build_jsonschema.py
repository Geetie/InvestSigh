"""导出聚合 JSON Schema（`Ch9 §3.3.3` facts 18 JSONL 的 schema 定义）。

产出 `system/schema/jsonschema/facts.schema.json`，其 **`defs` 键是权威键**：
`Ch2 §B.3` Checker-2 直接读 `schema["defs"]["Recommendation"]["properties"]`。
同时保留标准键 `$defs`（内容一致），便于标准 JSON Schema 工具消费。

**为什么要内联枚举**：Checker-2 的断言形如
`set(rec["action"]["enum"]) == {"buy","sell","pending","maintain"}`——
若 `action` 是 `{"$ref": "#/$defs/RecommendationAction"}`，`.get("enum")` 会取不到。
故本脚本对 `Recommendation` 的属性做一层 `$ref` 内联，使断言可执行。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import JSONL_MODELS


def _resolve_ref(ref: str, defs: dict[str, Any]) -> dict[str, Any]:
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        raise ValueError(f"无法解析的 $ref: {ref}")
    name = ref[len(prefix):]
    if name not in defs:
        raise ValueError(f"$ref 指向不存在的定义: {name}")
    return defs[name]


def _inline_refs(node: Any, defs: dict[str, Any]) -> Any:
    """把 `{"$ref": ...}` 就地替换为被引用定义的副本（单层足够：本模型无递归引用）。"""
    if isinstance(node, dict):
        if set(node) == {"$ref"}:
            return json.loads(json.dumps(_resolve_ref(node["$ref"], defs)))
        return {k: _inline_refs(v, defs) for k, v in node.items()}
    if isinstance(node, list):
        return [_inline_refs(v, defs) for v in node]
    return node


def build(include_inlined_recommendation: bool = True) -> dict[str, Any]:
    """构建聚合 schema 文档。"""
    defs: dict[str, Any] = {}
    objects: dict[str, str] = {}

    for stem in sorted(JSONL_MODELS):
        model = JSONL_MODELS[stem]
        doc = model.model_json_schema(ref_template="#/$defs/{model}")
        name = model.__name__
        objects[stem] = name
        defs[name] = {
            "title": name,
            "type": "object",
            "properties": doc.get("properties", {}),
            "required": doc.get("required", []),
            "additionalProperties": False,
        }
        for sub_name, sub in (doc.get("$defs") or {}).items():
            defs.setdefault(sub_name, sub)

    if include_inlined_recommendation:
        defs["Recommendation"]["properties"] = _inline_refs(
            defs["Recommendation"]["properties"], defs
        )

    doc_out: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://investsigh.local/schema/facts.schema.json",
        "title": "AI 产业链研究 Agent · facts 对象 schema（Ch9 §3.3.3；表数经需求方裁定由 18 扩至 22）",
        "description": (
            "唯一真源 = facts/*.jsonl。本文件由 system/schema/build_jsonschema.py 生成，"
            "生成物需与 system/schema/models.py 一致。"
        ),
        "objects": objects,
        # ★ 权威键：Ch2 §B.3 Checker-2 读 schema["defs"]["Recommendation"]["properties"]
        "defs": defs,
        # 标准键（内容一致），供标准 JSON Schema 工具消费
        "$defs": defs,
    }
    return doc_out


def main(code_root: str | Path | None = None) -> Path:
    root = Path(code_root) if code_root else Path(__file__).resolve().parents[1]
    out_dir = root / "schema" / "jsonschema"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "facts.schema.json"
    out.write_text(
        json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return out


if __name__ == "__main__":
    print(main())
