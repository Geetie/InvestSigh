"""**关系传染**的程序约束单测（`Ch7 §D.5` / `N7.4-11` / 裁决 C7-7）。

铁律：**关系只作研究路径，不作结论依据**。「供应商与 NVIDIA 有关系」只能触发
"对供应商**独立研究**"任务，**不触发买入**。本测试用**三条互补证据**钉住它：

1. **结构断言**：`RecommendationInput` 的字段里**不存在** `relations` / 关联结论；
   决策函数的参数里也不含关系对象。
2. **不变性**：把关联公司结论注入到输入映射的外围（同名 dataclass 之外），
   `decide()` 输出**完全不变**。
3. **触发路径**：供应商能否被买入，**只**取决于它**自身**的收益预测，与"和谁有关系"无关。
"""

from __future__ import annotations

import inspect

from decision_builders import make_forecast, make_input

from scripts.decision.gate import JudgmentChange, RecommendationInput
from scripts.decision.rules import decide


def test_recommendation_input_has_no_relations_or_related_conclusion() -> None:
    fields = set(RecommendationInput.__dataclass_fields__)
    assert "relations" not in fields
    assert "related_conclusion" not in fields
    assert "other_company_conclusion" not in fields
    assert not {f for f in fields if "relation" in f or "related" in f}


def test_decide_signature_has_no_relation_parameter() -> None:
    """`decide()` 的参数里不得出现任何关系对象（关系不得进入决策函数）。"""
    params = list(inspect.signature(decide).parameters)
    assert not {p for p in params if "relation" in p or "related" in p}
    assert params == [
        "inp",
        "judgment",
        "has_active_positive_recommendation",
        "price_drop_triggered",
    ]


def test_related_company_conclusion_does_not_change_decision() -> None:
    """注入关联公司结论 → 决策输出**完全不变**（不变性，`§D.5` 断言 3）。"""
    supplier_inp = make_input(stock=make_forecast("0.10", "0.12"), benchmark=make_forecast("0.05", "0.06"))
    baseline_decision = decide(supplier_inp, JudgmentChange(fact_set_changed=True))

    # 把"关联公司结论"塞进输入映射（会被 allowlist 丢弃）+ 放进一个旁路对象。
    payload = {
        "relations": [{"relation_id": "rel-1", "object_id": "co-nvidia"}],
        "related_conclusion": "buy",
        "other_company_conclusion": "buy",
    }
    assert set(payload) - set(RecommendationInput.__dataclass_fields__) == set(payload)

    again = decide(supplier_inp, JudgmentChange(fact_set_changed=True))
    assert again == baseline_decision


def test_supplier_buy_is_driven_only_by_own_forecast() -> None:
    """供应商被买入**只**因为它自身"正收益且跑赢基准"；与"和 NVIDIA 有关系"无关。

    反证：把自身预测改为"跑不赢"，同一"有关系"事实下输出变为卖出 —— 决定权在自己身上。
    """
    buy_inp = make_input(stock=make_forecast("0.10", "0.12"), benchmark=make_forecast("0.05", "0.06"))
    sell_inp = make_input(stock=make_forecast("0.02", "0.03"), benchmark=make_forecast("0.10", "0.11"))
    assert decide(buy_inp, JudgmentChange(fact_set_changed=True)).action == "buy"
    assert decide(sell_inp, JudgmentChange(fact_set_changed=True)).action == "sell"
