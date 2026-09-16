"""前置门单测（`Ch7 §D.2` / `§D.5` / `§D.7` / `Ch2 §D.1 A-06`）。

覆盖：
- 研究完成门（研究深度 ≥ `baseline_done` **且** 基线齐备）；
- 可解释预测门（①驱动 ②期限 ③收益 ④底稿 缺一不可）；
- **`DerivedValue` 强制**（裸数字 → 响亮拒绝；`decide()` → `None`，**不生成建议**）；
- 收益区间合法性（`low > high` 响亮失败）；
- 提前判断三要素（任一为空 → 拦截）；
- **关系传染隔离**（`RecommendationInput.from_mapping` 丢弃 `relations`）。
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from decision_builders import make_baseline, make_forecast, make_input, make_worksheet

from scripts.decision.gate import (
    EarlyJudgmentIncomplete,
    RawNumberRejected,
    RecommendationInput,
    ReturnRangeError,
    ReturnValue,
    UnknownResearchDepthError,
    assert_early_judgment_complete,
    can_apply_return_comparison,
    has_explainable_forecast,
    require_derived_worksheet,
    research_complete,
)
from scripts.decision.rules import decide

# ───────────────────────── 研究完成门 ─────────────────────────


def test_research_complete_at_baseline_done() -> None:
    inp = make_input(stock=make_forecast("0.10"), benchmark=make_forecast("0.05"))
    assert research_complete(inp) is True


def test_research_incomplete_when_depth_below_baseline() -> None:
    shallow = make_input(
        stock=make_forecast("0.10"),
        benchmark=make_forecast("0.05"),
        baseline=make_baseline(depth="position_listed"),
    )
    assert research_complete(shallow) is False


def test_research_incomplete_when_baseline_not_complete() -> None:
    partial = make_input(
        stock=make_forecast("0.10"),
        benchmark=make_forecast("0.05"),
        baseline=make_baseline(complete=False),
    )
    assert research_complete(partial) is False


def test_unknown_research_depth_raises() -> None:
    weird = make_input(
        stock=make_forecast("0.10"),
        benchmark=make_forecast("0.05"),
        baseline=make_baseline(depth="deep_dive"),
    )
    with pytest.raises(UnknownResearchDepthError):
        research_complete(weird)


# ───────────────────────── 可解释预测门 ─────────────────────────


def test_explainable_forecast_requires_all_four_parts() -> None:
    assert has_explainable_forecast(
        make_input(stock=make_forecast("0.10"), benchmark=make_forecast("0.05"))
    )
    # ① 驱动为空
    no_drivers = make_input(
        stock=make_forecast("0.10", drivers=()),
        benchmark=make_forecast("0.05"),
    )
    assert has_explainable_forecast(no_drivers) is False
    # ② 期限为空
    no_horizon = make_input(
        stock=make_forecast("0.10", horizon=""),
        benchmark=make_forecast("0.05"),
    )
    assert has_explainable_forecast(no_horizon) is False
    # ④ 底稿为裸数字
    raw_number = make_input(
        stock=make_forecast("0.10", worksheet=0.10),
        benchmark=make_forecast("0.05"),
    )
    assert has_explainable_forecast(raw_number) is False


def test_require_derived_worksheet_returns_derived_value() -> None:
    forecast = make_forecast("0.10")
    worksheet = require_derived_worksheet(forecast)
    assert worksheet.formula and worksheet.operands and worksheet.method_version


def test_require_derived_worksheet_rejects_raw_number() -> None:
    forecast = make_forecast("0.10", worksheet=1234)
    with pytest.raises(RawNumberRejected):
        require_derived_worksheet(forecast)


# ───────────────────────── `DerivedValue` 强制 → decide 返回 None ─────────────────────────


def test_gate_rejects_raw_number_and_decide_returns_none() -> None:
    """`N7.3-07`：`forecast.worksheet` 是裸数字 → 门不过 → `decide()` 返回 `None`（不出建议）。"""
    inp = make_input(
        stock=make_forecast("0.30", worksheet=1234),
        benchmark=make_forecast("0.05"),
    )
    assert can_apply_return_comparison(inp) is False
    from scripts.decision.gate import JudgmentChange

    assert decide(inp, JudgmentChange(fact_set_changed=True)) is None


def test_gate_rejects_incomplete_baseline_and_decide_returns_none() -> None:
    from scripts.decision.gate import JudgmentChange

    inp = make_input(
        stock=make_forecast("0.30"),
        benchmark=make_forecast("0.05"),
        baseline=make_baseline(depth="relations_verified"),
    )
    assert can_apply_return_comparison(inp) is False
    assert decide(inp, JudgmentChange(fact_set_changed=True)) is None


# ───────────────────────── 收益区间合法性 ─────────────────────────


def test_return_value_rejects_inverted_range() -> None:
    with pytest.raises(ReturnRangeError):
        ReturnValue(low=Decimal("0.20"), high=Decimal("0.10"))


def test_return_value_rejects_float() -> None:
    with pytest.raises(TypeError):
        ReturnValue(low=0.1, high=0.2)  # type: ignore[arg-type]


def test_return_value_point_estimate() -> None:
    assert ReturnValue(low=Decimal("0.10"), high=Decimal("0.10")).is_point is True
    assert ReturnValue(low=Decimal("0.05"), high=Decimal("0.10")).is_point is False


# ───────────────────────── 提前判断三要素 ─────────────────────────


class _FakeRec:
    def __init__(self, assumptions, evidence_gaps, verification_conditions) -> None:
        self.assumptions = assumptions
        self.evidence_gaps = evidence_gaps
        self.verification_conditions = verification_conditions
        self.version = 3


def test_early_judgment_complete_passes() -> None:
    assert_early_judgment_complete(
        _FakeRec(["a"], ["g"], ["c"])
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"assumptions": [], "evidence_gaps": ["g"], "verification_conditions": ["c"]},
        {"assumptions": ["a"], "evidence_gaps": [], "verification_conditions": ["c"]},
        {"assumptions": ["a"], "evidence_gaps": ["g"], "verification_conditions": []},
    ],
)
def test_early_judgment_incomplete_raises(kwargs: dict) -> None:
    with pytest.raises(EarlyJudgmentIncomplete) as exc:
        assert_early_judgment_complete(_FakeRec(**kwargs))
    assert exc.value.missing


def test_early_judgment_same_version_assertion_is_conditional() -> None:
    """三要素须与结论**同版本**写入；对象未暴露序号时该断言为 no-op。"""
    rec = _FakeRec(["a"], ["g"], ["c"])
    rec.trio_written_seq = 4
    rec.version_seq = 3
    with pytest.raises(EarlyJudgmentIncomplete):
        assert_early_judgment_complete(rec)


# ───────────────────────── 关系传染隔离（输入结构） ─────────────────────────


def test_recommendation_input_has_no_relation_fields() -> None:
    fields = set(RecommendationInput.__dataclass_fields__)
    leaked = {f for f in fields if "relation" in f or "related" in f}
    assert not leaked, f"RecommendationInput 含关系类字段（违反 Ch7 §D.5）: {sorted(leaked)}"
    assert fields == {
        "company_id",
        "baseline",
        "stock_forecast",
        "benchmark_forecast",
        "own_evidence",
    }


def test_from_mapping_drops_relations_and_related_conclusions() -> None:
    """`from_mapping` 允许白名单取值：多塞的 `relations` / 关联公司结论被丢弃。"""
    payload = {
        "company_id": "co-demo",
        "baseline": {"company_id": "co-demo", "research_depth": "baseline_done", "baseline_complete": True},
        "stock_forecast": {
            "drivers": ["d"],
            "horizon": "2q",
            "return_range": {"low": "0.30", "high": "0.30"},
            "worksheet": make_worksheet("0.30"),
            "method_version": "compute-v1",
        },
        "benchmark_forecast": {
            "drivers": ["d"],
            "horizon": "2q",
            "return_range": {"low": "0.05", "high": "0.05"},
            "worksheet": make_worksheet("0.05", subject="usAGIX"),
            "method_version": "compute-v1",
        },
        "own_evidence": ["claim:co-demo:market"],
        # ↓ 这些键**不得**进入决策输入
        "relations": [{"relation_id": "rel-1", "object_id": "co-nvidia"}],
        "related_conclusion": "supplier_to_nvidia_implies_buy",
        "other_company_conclusion": "buy",
    }
    inp = RecommendationInput.from_mapping(payload)
    assert not hasattr(inp, "relations")
    assert not hasattr(inp, "related_conclusion")
    assert inp.own_evidence == ("claim:co-demo:market",)
