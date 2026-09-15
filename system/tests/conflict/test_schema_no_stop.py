"""`Ch2 §B.2 P-03`：`Recommendation` 上**不得**出现止损类字段。

`施工图 §3.4` 具名的阶段① 测试资产（第二轮独立审计指出此前缺失）。

**为什么单开一个文件**：P-03 的失败后果是"投资建议悄悄变成了交易指令"。
它单独成测，是为了让**谁改动 `Recommendation` 字段**时能立刻被这一条挡住，
而不是埋在几百个断言里。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SYSTEM_ROOT = Path(__file__).resolve().parents[2]

# `Ch2 §B.2 P-03` 逐字（禁止损）
STOP_LIKE = ("stop_loss", "stop_price", "price_stop", "stop", "trailing_stop")


@pytest.fixture()
def recommendation_props() -> dict:
    doc = json.loads(
        (SYSTEM_ROOT / "schema" / "jsonschema" / "facts.schema.json").read_text(encoding="utf-8")
    )
    return doc["defs"]["Recommendation"]["properties"]


def test_recommendation_has_no_stop_like_field(recommendation_props: dict) -> None:
    present = sorted(set(recommendation_props) & set(STOP_LIKE))
    assert not present, f"Recommendation 出现止损类字段（P-03）：{present}"


def test_model_level_has_no_stop_like_field() -> None:
    """schema 与 pydantic 模型两侧都要查（schema 是生成物，模型是真源）。"""
    import sys

    if str(SYSTEM_ROOT) not in sys.path:
        sys.path.insert(0, str(SYSTEM_ROOT))
    from schema.models import Recommendation

    present = sorted(set(Recommendation.model_fields) & set(STOP_LIKE))
    assert not present, f"Recommendation 模型出现止损类字段（P-03）：{present}"


def test_recommendation_action_has_no_short() -> None:
    """P-05：`action` 枚举不得含做空（裸词 `short` / `short_sell`）。"""
    import sys

    if str(SYSTEM_ROOT) not in sys.path:
        sys.path.insert(0, str(SYSTEM_ROOT))
    from schema.models import RecommendationAction

    values = {m.value for m in RecommendationAction}
    assert values == {"buy", "sell", "pending", "maintain"}, values
