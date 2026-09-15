"""`Ch2 §B.2 P-07`：`Recommendation` 上**不得**出现无来源的聚合预测字段。

`施工图 §3.4` 具名的阶段① 测试资产（第二轮独立审计指出此前缺失）。

**为什么单开一个文件**：P-07 的失败后果是"三份判断被合并成一份"——
`Ch9 §N9.1-20` 明令**外部预期 / 价格隐含 / 独立判断不许合并**。
这个断言是那条纪律的机器化身。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SYSTEM_ROOT = Path(__file__).resolve().parents[2]
if str(SYSTEM_ROOT) not in sys.path:
    sys.path.insert(0, str(SYSTEM_ROOT))

# `Ch2 §B.2 P-07` 逐字（不得聚合无 source_id 的预测）
AGGREGATE_LIKE = (
    "consensus",
    "market_view",
    "average_forecast",
    "consensus_price",
    "consensus_estimate",
)


@pytest.fixture()
def recommendation_props() -> dict:
    doc = json.loads(
        (SYSTEM_ROOT / "schema" / "jsonschema" / "facts.schema.json").read_text(encoding="utf-8")
    )
    return doc["defs"]["Recommendation"]["properties"]


def test_recommendation_has_no_aggregate_field(recommendation_props: dict) -> None:
    present = sorted(set(recommendation_props) & set(AGGREGATE_LIKE))
    assert not present, f"Recommendation 出现聚合预测字段（P-07）：{present}"


def test_model_level_has_no_aggregate_field() -> None:
    from schema.models import Recommendation

    present = sorted(set(Recommendation.model_fields) & set(AGGREGATE_LIKE))
    assert not present, f"Recommendation 模型出现聚合预测字段（P-07）：{present}"


def test_expectation_sample_requires_source() -> None:
    """`facts/expectations.jsonl` 的每条预期**必须**带 `source_id` ——
    否则外部预测就不可追溯，等价于"一致预期"。"""
    from schema.models import ExpectationSample

    fields = set(ExpectationSample.model_fields)
    assert "source_id" in fields, "ExpectationSample 缺 source_id（无源的预期不得入库）"
    required = set(ExpectationSample.model_json_schema().get("required") or [])
    assert "source_id" in required, "source_id 必须是必填（不得可选）"
