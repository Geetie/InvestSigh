"""`Ch4 §D` —— 增长质量 / ROIIC / **增长的代价五类** / **收入增速不得作回报代理**（逐条正反用例）。

设计锚点（逐字）：

```python
def assess(driver, fin):
    roiic = compute_roiic(fin.incremental_nopat, fin.incremental_invested_capital)  # 走 compute/
    if roiic < fin.wacc:
        return GrowthQuality("low", flag="value_destructive_growth")
    ...  # 现金转化率/营运资金/融资依赖分项
```

> **收入增速不得作投资回报代理**：决策/估值只引用 `ROIC/ROIIC/每股 FCF/EVA`
> （`scripts/valuelayer/growth_quality.py` 输出的**替代指标集**），**收入增速字段设有 denylist 守卫**。

★ 本文件最要紧的一组是 `test_return_proxy_*`：
  "denylist 守卫"若只是"文本里出现 `revenue_growth` 就报错"，那就**不可穷尽**
  （换个变量名即绕过）且违反 `R-06 ①`（禁关键词式判据）。故本实现把它落成
  **运行时可判定的 allowlist 准入**（`require_return_proxy`：未列出的名字默认拒绝），
  并**成对**断言"四类许可值通过 / 其余（含还没人想出来的写法）一律拒"（`G-05`）。

★ `Ch4 §J.4 J7` 建议的 AST 检查**刻意未做**，且该缺口被写成**可断言的事实**
  （`no_ast_keyword_pass()`）—— 见 `test_no_ast_keyword_pass_declares_the_gap`。
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from conftest import run_gate_inproc
from scripts.valuelayer import _rules
from scripts.valuelayer.growth_quality import (
    COST_OF_GROWTH_FIELDS,
    RETURN_PROXY_METRICS,
    ROIIC_OPERANDS,
    VALUE_DESTRUCTIVE_FLAG,
    CostOfGrowthIncomplete,
    Financials,
    GrowthAssessment,
    ReturnProxyNotAllowed,
    TooManyDrivers,
    alternative_metric_set,
    assess,
    cost_of_growth_gaps,
    driver_tier,
    no_ast_keyword_pass,
    require_return_proxy,
    validate_cost_of_growth,
    validate_driver_count,
)
from _fixtures import THRESHOLDS, driver, write_jsonl, write_rules

CHECKER = "scripts/valuelayer/growth_quality.py"

CFG = dict(THRESHOLDS)


def _fin(**overrides) -> Financials:
    """**合规**财务入参（四项分项全部中性 ⇒ `high`）。"""
    parts = dict(
        incremental_nopat=Decimal("20"),
        incremental_invested_capital=Decimal("100"),
        wacc=Decimal("0.10"),
        cash_conversion=Decimal("0.9"),
        working_capital_change=Decimal("-1"),
        financing_dependence="none",
    )
    parts.update(overrides)
    return Financials(**parts)


# ══════════════ `§D.3` 五类"增长的代价"（字段齐备性） ══════════════


def test_cost_of_growth_has_exactly_the_five_design_fields() -> None:
    """五类代价的字段名**逐字**取 `§D.3` 表（顺序同表）—— 少一类或多一类都是漂移。"""
    assert COST_OF_GROWTH_FIELDS == (
        "price_discount",
        "capex_requirement",
        "inventory_buildup",
        "receivables_buildup",
        "financing_need",
    )


def test_cost_of_growth_passes_when_all_five_are_present() -> None:
    assert cost_of_growth_gaps(driver()) == []


def test_cost_of_growth_reports_the_missing_field_by_name() -> None:
    """缺哪一类必须**点名**（否则"五类代价"只是个不可定位的整体判定）。"""
    row = driver()
    row["cost_of_growth"] = {k: v for k, v in row["cost_of_growth"].items() if k != "financing_need"}
    assert cost_of_growth_gaps(row) == ["financing_need"]
    with pytest.raises(CostOfGrowthIncomplete) as excinfo:
        validate_cost_of_growth(row)
    assert excinfo.value.missing == ("financing_need",)


def test_missing_cost_block_reports_all_five() -> None:
    assert cost_of_growth_gaps(driver(cost_of_growth=None)) == list(COST_OF_GROWTH_FIELDS)


def test_empty_cost_entry_is_not_the_same_as_zero() -> None:
    """★ `Ch4 §G.4` 同一条思路：**空 dict ≠ 真的为 0**。

    "降价真的是 0"与"根本没研究过降价"是两件事；前者是一个（可质疑的）结论，
    后者是没做功课。故空 mapping 记"未交代"，而数值 `0` 记"已交代"。
    """
    row = driver()
    row["cost_of_growth"]["price_discount"] = {}
    assert cost_of_growth_gaps(row) == ["price_discount"]

    row["cost_of_growth"]["price_discount"] = 0
    assert cost_of_growth_gaps(row) == []


# ══════════════ `§D.2` 驱动上限（阈值只从规则文件读） ══════════════


def test_driver_tier_is_derived_from_importance_class() -> None:
    """`§D.2` 把分级写成**动作**（"按 `importance_class` 取 top-N，其余归档"）⇒ 由它派生，不新增 `tier` 字段。"""
    assert driver_tier(driver(importance_class="high")) == "primary"
    assert driver_tier(driver(importance_class="medium")) == "secondary_watchlist"


def test_driver_count_at_the_limit_passes_and_over_it_raises() -> None:
    """`§D.2`：超限**拒绝直接入库**（不是告警）—— 5 个 ok，6 个 raise。"""
    five = [driver(f"DRV-{i}") for i in range(5)]
    validate_driver_count("BIZ-1", five, CFG)  # 不抛
    with pytest.raises(TooManyDrivers) as excinfo:
        validate_driver_count("BIZ-1", [*five, driver("DRV-6")], CFG)
    assert excinfo.value.limit == 5 and excinfo.value.got == 6


def test_secondary_drivers_do_not_count_toward_the_cap() -> None:
    """**反向对照**：`§D.2` 的上限只约束 **primary**（其余归档到 secondary_watchlist）。"""
    rows = [driver(f"DRV-{i}", importance_class="high") for i in range(5)]
    rows += [driver(f"DRV-W{i}", importance_class="medium") for i in range(10)]
    validate_driver_count("BIZ-1", rows, CFG)  # 不抛


def test_driver_cap_must_come_from_the_rules_file() -> None:
    """★ 代码里**不得**内置上限：缺 `max_primary_drivers_per_business` ⇒ `MissingRuleInput`（→ `exit 2`）。"""
    with pytest.raises(_rules.MissingRuleInput):
        validate_driver_count("BIZ-1", [driver()], {})


# ══════════════ ★ "收入增速不得作投资回报代理"（allowlist 准入） ══════════════


@pytest.mark.parametrize("name", sorted(RETURN_PROXY_METRICS))
def test_return_proxy_admits_the_four_design_metrics(name) -> None:
    assert require_return_proxy(name) == name


@pytest.mark.parametrize(
    "name",
    ["revenue_growth", "revenue_cagr", "top_line_growth", "growth_rate", "收入增速", "rev_yoy"],
)
def test_return_proxy_rejects_every_unlisted_name(name) -> None:
    """★ 未列出的名字**默认拒绝**（`R-06 ⑤` allowlist）—— 包括换个写法的"收入增速"。

    ★ 为什么这构成**穷尽**的判据：判据是"名字是否在**封闭**集合内"，
      故不存在"换一种措辞绕过"的形态（对比关键词/名单式的文本匹配，`R-06 ①`）。
    """
    with pytest.raises(ReturnProxyNotAllowed) as excinfo:
        require_return_proxy(name)
    assert excinfo.value.name == name


def test_alternative_metric_set_contains_only_allowed_metrics() -> None:
    """`§D.3` 的替代指标集：输出的**每一个**名字都过同一道闸（输出侧不夹带非许可项）。"""
    out = alternative_metric_set(Decimal("0.2"), Decimal("0.1"))
    assert set(out) == set(RETURN_PROXY_METRICS)
    for name in out:
        require_return_proxy(name)


def test_no_ast_keyword_pass_declares_the_gap_instead_of_faking_a_guard() -> None:
    """★ `Ch4 §J.4 J7` 建议的 AST 检查**未做**，且这件事必须**可观测**（否则是假信心）。

    `R-06 ①/③` 禁止不可穷尽的关键词式判据、且不得把它当防护 ⇒ 本实现不作该检查，
      改为把缺口写成一句可断言的声明；将来真做了 AST 检查，本用例会红，
      从而**强制**更新登记（与 `criterion_counterexamples` 的 `ineffective` 条目同源）。
    """
    text = no_ast_keyword_pass()
    assert "NO_AST_KEYWORD_PASS" in text
    assert "require_return_proxy" in text


# ══════════════ `§D.3` assess：分档 + 价值毁灭标志（算术走 compute/） ══════════════


def test_assess_flags_value_destructive_growth_when_roiic_below_wacc() -> None:
    """★ `§D.3` 伪码的硬规则：`ROIIC < WACC` ⇒ 唯一下档 `low` + `value_destructive_growth`。"""
    result = assess(driver(), _fin(incremental_nopat=Decimal("5"), wacc=Decimal("0.10")))
    assert result.quality.grade == "low"
    assert VALUE_DESTRUCTIVE_FLAG in result.flags


def test_assess_grades_high_when_all_four_items_are_neutral() -> None:
    """**反向对照**：四项分项全中性 ⇒ `high`（证明"有输入就一定下档"不是本实现的行为）。"""
    result = assess(driver(), _fin())
    assert result.quality.grade == "high"
    assert result.flags == ()


def test_assess_grade_comes_from_the_compute_layer_not_a_second_copy() -> None:
    """★ `G-06`：分档规则**只有一处**真源（`scripts/compute/growth.py`）。

    断言方式：把同一组入参分别喂给 `assess()` 与 `scripts.compute.growth.assess_growth_quality()`，
    两者必须给出**同一个档位**。若将来有人在 value 层重写一套分档，本用例即红。
    """
    from scripts.compute.growth import assess_growth_quality, compute_roiic

    fin = _fin(incremental_nopat=Decimal("5"), wacc=Decimal("0.10"))
    via_assess = assess(driver(), fin)
    expected_roiic = compute_roiic(
        fin.incremental_nopat,
        fin.incremental_invested_capital,
        subject="DRV-1",
        operands=ROIIC_OPERANDS,
    ).value
    direct = assess_growth_quality(
        roiic=expected_roiic,
        wacc=fin.wacc,
        cash_conversion=fin.cash_conversion,
        working_capital_change=fin.working_capital_change,
        financing_dependence=fin.financing_dependence,
        subject="DRV-1",
    )
    assert via_assess.quality.grade == direct.grade
    assert Decimal(str(expected_roiic)) == Decimal("0.05")


def test_assess_does_not_downgrade_when_roiic_is_undefined() -> None:
    """★ `G-03`：分母为 0（`compute` 层抛 `UndefinedComputation`）⇒ 本次**不下档**，如实记缺口。

    ★ 为什么不能把"算不出 ROIIC"当成 `low`：那会把**没研究**冒充成**已判负向**，
      而这两件事在报告里长得一模一样 —— 正是本项目最忌的假信号。
    """
    result = assess(driver(), _fin(incremental_invested_capital=Decimal("0")))
    assert result.quality is None
    assert result.gaps and "roiic:" in result.gaps[0]
    assert any("不下增长质量档" in note for note in result.notes)


def test_assess_records_missing_cost_of_growth_without_blocking_the_grade() -> None:
    """`§D.3` 的分档只由四项分项决定；代价缺项**记进 gaps**（不阻断，但必须可见）。"""
    row = driver()
    row["cost_of_growth"] = {}
    result = assess(row, _fin())
    assert result.quality.grade == "high"
    assert any(g.startswith("cost_of_growth:") for g in result.gaps)


def test_roiic_operands_are_the_two_input_field_names() -> None:
    """★ `Ch9 §2.4.3`：落库数字必须能追到 operand ⇒ `assess` 传出去的 operands **不得为空**。

    ★ 这条是**实测暴露的真缺陷**的固化：`assess` 原先传 `operands=[]`，
      `compute` 层以 `CaliberViolation` 响亮拒绝（"operands 不得为空"）——
      即价值层在**正常输入**上直接崩。判据在此钉死，避免再退回去。
    """
    from dataclasses import fields as dc_fields

    assert ROIIC_OPERANDS == ("incremental_nopat", "incremental_invested_capital")
    assert set(ROIIC_OPERANDS) <= {f.name for f in dc_fields(Financials)}


def test_assessment_exposes_no_single_score_field() -> None:
    """`纪律 7` / `P-09` / `Ch2 §B.2 P-01`：**不得**把四项压成单一分数再做门槛。

    结果是"分档 + 分项明细 + 替代指标集"，结构上就不存在一个"分数"字段可供排序。
    """
    names = {f.name for f in dataclasses.fields(GrowthAssessment)}
    assert names == {"driver_id", "quality", "alternative_metrics", "cost_of_growth", "gaps", "notes"}


# ══════════════ 门禁入口 `check()`（需要真文件） ══════════════


def test_cli_exits_zero_on_compliant_drivers(code_root) -> None:
    write_rules(code_root)
    write_jsonl(code_root, "drivers", [driver()])
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 0, out


def test_cli_flags_missing_cost_of_growth(code_root) -> None:
    """`§D.3` 五类代价缺一 ⇒ `exit 1`（不是 warn）。"""
    write_rules(code_root)
    row = driver()
    row["cost_of_growth"].pop("receivables_buildup")
    write_jsonl(code_root, "drivers", [row])
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 1, out
    assert "receivables_buildup" in out, out


def test_cli_flags_a_source_class_outside_the_seven_plus_mixed(code_root) -> None:
    """`N4.1-03`：每驱动有**来源标签**（7 类 + `mixed` 兜底）；不在集合内的标签 ⇒ `exit 1`。"""
    write_rules(code_root)
    write_jsonl(code_root, "drivers", [driver(source_class="想象力")])
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 1, out
    assert "source_class" in out, out


def test_cli_flags_too_many_primary_drivers(code_root) -> None:
    write_rules(code_root)
    write_jsonl(code_root, "drivers", [driver(f"DRV-{i}") for i in range(6)])
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 1, out
    assert "TooManyDrivers" in out, out


def test_cli_treats_missing_drivers_source_as_input_error(code_root) -> None:
    write_rules(code_root)
    (code_root / "facts" / "drivers.jsonl").unlink(missing_ok=True)
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 2, out
    assert "INPUT-ERROR" in out, out


def test_cli_reports_no_drivers_as_vacuous(code_root) -> None:
    write_rules(code_root)
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 0, out
    assert "NO_DRIVERS" in out, out
