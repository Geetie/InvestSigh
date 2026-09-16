"""`Ch4 §H` —— 3×4 状态机 + **无变化分支** + `§H.3` 增量六要素（逐条正反用例）。

设计锚点（逐字）：

```python
def update_states(old_states, new_info, impacts):
    if not new_info or not affects_dimension(impacts):
        return old_states, CheckRecord("本次核查无变化")   # ← 不写新版本
    return apply_changes(old_states, impacts), ...
```

★ 本文件守的是**两条最容易越过的线**：

| # | 线 | 设计出处 | 反例（若越线） |
|---|---|---|---|
| 1 | **无新信息不产新版本** | `§H.2` / `N4.5-05` | 每次核查都写一版 → "无信号"不再是正常态 |
| 2 | **待判断 ≠ 不变** | `N4.5-03` | 首版把 `tbd` 写成 `unchanged` → "没研究"冒充"研究过且没变" |

❸ 另一条结构性事实：`moat_level`（水平）与 `moat_state`（趋势）是**两个轴**，
  可不同向 —— 故"只改水平的信号"**不得**擅自改写三个方向字段（`§H.4①`）。
"""

from __future__ import annotations

from datetime import date

import pytest

from scripts.valuelayer.state_machine import (
    DIRECTION_DIMENSIONS,
    IMPACT_DIRECTIONS,
    INCREMENT_REASON,
    INCREMENT_REQUIRED,
    LEVEL_DIMENSION,
    DimensionImpact,
    affects_dimension,
    default_states,
    increment_gaps,
    update_states,
    validate_impact,
    validate_increment,
    value_state_refs,
)
from _fixtures import baseline

RUN_DATE = date(2026, 9, 16)
STATES = {
    "growth_momentum_state": "strengthening",
    "certainty_state": "unchanged",
    "moat_state": "unchanged",
    "moat_level": "strong",
}


# ══════════════════════ 3×4 取值域与初值 ══════════════════════


def test_three_direction_dimensions_plus_one_level_dimension() -> None:
    """`§H.1`：三个**方向**字段 × 四值 = 3×4；`moat_level` 是第四个数轴（**水平**）。"""
    assert DIRECTION_DIMENSIONS == ("growth_momentum_state", "certainty_state", "moat_state")
    assert LEVEL_DIMENSION == "moat_level"
    assert IMPACT_DIRECTIONS == ("strengthening", "weakening", "unchanged", "tbd")


def test_direction_values_come_from_the_schema_enum_not_a_second_copy() -> None:
    """`G-06`：方向四值取自 `schema.models.DirectionState`（本模块**不重抄**枚举）。"""
    from schema.models import DirectionState

    assert set(IMPACT_DIRECTIONS) == {m.value for m in DirectionState}


def test_default_states_are_tbd_not_unchanged() -> None:
    """★ `N4.5-03`：首版**尚未研究** ⇒ 四字段只能是 `tbd`，**不得**写成 `unchanged`。

    "待判断 = 信息不足、无法判断"；"不变 = **已研究且确认**无变化"。把首版写成
      `unchanged` 就是拿一个"已确认"的结论覆盖"还没看"。
    """
    assert default_states() == {
        "growth_momentum_state": "tbd",
        "certainty_state": "tbd",
        "moat_state": "tbd",
        "moat_level": "tbd",
    }


# ══════════════════════ ★ 线 1：无新信息不产新版本 ══════════════════════


def test_no_new_info_produces_no_new_version() -> None:
    """`§H.2` 逐字：`not new_info` ⇒ 原样返回 + "本次核查无变化"，且 **`wrote_new_version=False`**。"""
    updates = [DimensionImpact("CLM-1", "growth_momentum_state", "weakening")]
    result = update_states(STATES, [], updates)
    assert result.states == STATES
    assert result.changed is False
    assert result.wrote_new_version is False
    assert result.note == "本次核查无变化"


def test_new_info_that_touches_no_direction_dimension_also_produces_no_new_version() -> None:
    """`§H.2` 的 `or` 的另一半：有新信息，但它**不影响三方向维度** ⇒ 同样不产新版本。"""
    result = update_states(STATES, ["CLM-9"], [])
    assert result.changed is False
    assert result.note == "本次核查无变化"


def test_level_dimension_impact_is_rejected_because_the_level_axis_has_its_own_domain() -> None:
    """★ `§H.4①`：`moat_level` 与 `moat_state` 是**两个轴**，且取值域不同
    （水平 = `weak|moderate|strong|tbd`；趋势 = `strengthening|weakening|unchanged|tbd`）。

    故"改变水平"不能借道本类型的 `direction` 字段 ⇒ 本模块**响亮拒绝**该输入，
      而不是把它当成"无影响"静默吞掉 —— 后者会让"水平没变"与"水平写错地方了"不可区分。
    """
    impact = DimensionImpact("CLM-1", LEVEL_DIMENSION, "weakening")
    assert affects_dimension([impact]) is False   # 它不是方向维度
    assert validate_impact(impact) != []          # 且取值域不合法（响亮）
    with pytest.raises(ValueError):
        update_states(STATES, ["CLM-1"], [impact])


def test_update_states_never_rewrites_the_level_axis() -> None:
    """`update_states` 只写三个**方向**维度；`moat_level` 原样保留（`§H.4①` 的轴分离）。"""
    result = update_states(STATES, ["CLM-1"], [DimensionImpact("CLM-1", "moat_state", "weakening")])
    assert result.changed is True
    assert result.states["moat_state"] == "weakening"
    assert result.states[LEVEL_DIMENSION] == "strong"


def test_change_is_produced_when_new_info_does_affect_a_direction() -> None:
    """**反向对照**（`G-05`）：新信息落在方向维度上 ⇒ 必须产新版本且可定位到该维度。"""
    result = update_states(
        STATES, ["CLM-1"], [DimensionImpact("CLM-1", "growth_momentum_state", "weakening")]
    )
    assert result.changed is True
    assert result.wrote_new_version is True
    assert result.states["growth_momentum_state"] == "weakening"
    assert result.judgment_change["growth_momentum_state"] is True
    assert result.judgment_change["certainty_state"] is False


def test_impact_from_an_unrelated_claim_does_not_trigger_a_change() -> None:
    """`§H.1`："仅当有 `claim_impact` **改变该维度证据**时"——影响必须由**本次**新信息引起。"""
    updates = [DimensionImpact("CLM-OLD", "certainty_state", "weakening")]
    result = update_states(STATES, ["CLM-NEW"], updates)
    assert result.changed is False


def test_three_dimensions_can_move_in_different_directions_at_once() -> None:
    """`§H.1`："动力增强、确定性减弱、护城河不变"**可同时出现**（三个独立字段，不是单一总状态）。"""
    result = update_states(
        STATES,
        ["CLM-1", "CLM-2"],
        [
            DimensionImpact("CLM-1", "growth_momentum_state", "strengthening"),
            DimensionImpact("CLM-2", "certainty_state", "weakening"),
        ],
    )
    assert result.states["growth_momentum_state"] == "strengthening"
    assert result.states["certainty_state"] == "weakening"
    assert result.states["moat_state"] == "unchanged"
    assert result.changed is True


def test_missing_dimensions_are_filled_with_tbd() -> None:
    """传进来的旧状态缺维度 ⇒ 补 `tbd`（"没研究"），**不**补 `unchanged`。"""
    result = update_states({"growth_momentum_state": "weakening"}, [], [])
    assert result.states["certainty_state"] == "tbd"
    assert result.states["moat_state"] == "tbd"


# ══════════════════════ 取值域非法 ⇒ 响亮失败 ══════════════════════


@pytest.mark.parametrize(
    ("impact", "fragment"),
    [
        (DimensionImpact("CLM-1", "不存在的维度", "weakening"), "dimension"),
        (DimensionImpact("CLM-1", "certainty_state", "更好"), "direction"),
        (DimensionImpact("", "certainty_state", "weakening"), "claim_id"),
    ],
)
def test_illegal_impact_is_a_loud_failure_not_a_silent_no_change(impact, fragment) -> None:
    """★ 非法取值必须 `ValueError` —— **不得**被静默忽略成"无影响"。

    ★ 为什么（`G-03` 同族）：静默忽略会让"研究过但没变化"与"取值写错了"在输出上
      **逐字相同**，而前者正是 `§H.2` 无变化分支要表达的东西。
    """
    assert any(fragment in p for p in validate_impact(impact))
    with pytest.raises(ValueError, match="状态影响条目非法"):
        update_states(STATES, ["CLM-1"], [impact])


def test_tbd_is_a_legal_direction_value() -> None:
    """**反向对照**：`tbd` 是四值之一（"待判断"），**不是**非法值 —— 不得被误拦。"""
    assert validate_impact(DimensionImpact("CLM-1", "certainty_state", "tbd")) == []


# ══════════════════════ `§H.4②` value_state_refs ══════════════════════


def test_value_state_refs_has_exactly_the_four_design_fields() -> None:
    """`§H.4②` 逐字输出四字段，供第七章 `classify_opportunity()` 消费（键名不得改）。"""
    refs = value_state_refs(baseline())
    assert set(refs) == {
        "growth_momentum_state",
        "certainty_state",
        "moat_level",
        "moat_state",
    }
    assert refs["growth_momentum_state"] == "strengthening"
    assert refs["moat_level"] == "strong"
    assert refs["moat_state"] == "unchanged"


def test_value_state_refs_defaults_to_tbd_when_the_baseline_has_no_state() -> None:
    """缺状态 ⇒ 四字段一律 `tbd`（"没研究"），**不得**猜一个方向。"""
    row = baseline()
    row.pop("value_state_refs")
    assert set(value_state_refs(row).values()) == {"tbd"}


def test_value_state_refs_reads_enum_values_too() -> None:
    """状态字段可能是 schema 枚举 ⇒ 取 `.value`（`G-06`：同一对象的两种行文）。"""
    from schema.models import DirectionState, MoatLevel

    refs = value_state_refs(
        {
            "value_state_refs": {
                "growth_momentum_state": DirectionState.weakening,
                "certainty_state": DirectionState.unchanged,
                "moat_level": MoatLevel.moderate,
                "moat_state": DirectionState.tbd,
            }
        }
    )
    assert refs == {
        "growth_momentum_state": "weakening",
        "certainty_state": "unchanged",
        "moat_level": "moderate",
        "moat_state": "tbd",
    }


# ══════════════════════ 规范 CheckRecord（`Ch1 §C.2` / `Ch9 §N9.1`） ══════════════════════


def test_check_record_counts_signals_emitted_as_the_number_of_changed_dimensions() -> None:
    """`§H.2` 的"**不产新信号**"必须成为**可观测计数**（否则它只是 docstring 里的一句话）。

    ★ 记录类型复用 `schema.models.CheckRecord`（`Ch1 §C.2` / `G-06`：不另造记录类型），
      故这里顺带断言 `scope` 真的落在 schema 的封闭取值域内。
    """
    changed = update_states(
        STATES,
        ["CLM-1", "CLM-2"],
        [
            DimensionImpact("CLM-1", "growth_momentum_state", "weakening"),
            DimensionImpact("CLM-2", "moat_state", "weakening"),
        ],
    ).to_check_record(check_id="CHK-1", run_date=RUN_DATE, scope="recheck")
    assert changed.signals_emitted == 2
    assert changed.changed is True
    assert changed.scope.value == "recheck"

    unchanged = update_states(STATES, [], []).to_check_record(
        check_id="CHK-2", run_date=RUN_DATE, scope="recheck"
    )
    assert unchanged.signals_emitted == 0
    assert unchanged.changed is False


def test_check_record_default_scope_is_a_valid_schema_scope() -> None:
    """`update_states` 的默认 `scope` 必须**本身就是**合法取值（否则默认调用即崩）。"""
    from schema.models import CheckScope

    record = update_states(STATES, [], []).to_check_record(check_id="CHK-3", run_date=RUN_DATE, scope="recheck")
    assert record.scope in set(CheckScope)
    assert update_states.__kwdefaults__["scope"] in {m.value for m in CheckScope}


# ══════════════════════ `§H.3` 增量六要素（`N4.5-01/04`） ══════════════════════


def _increment(**overrides):
    row = {
        "old_judgment": "moat_state=unchanged",
        "new_info": ["CLM-9"],
        "new_judgment": "moat_state=weakening",
        "affected_period": "FY2027Q1",
        "supporting_evidence": ["CLM-9"],
        "counter_evidence": [],
        "reason": "竞争对手发布同类产品，切换成本下降",
    }
    row.update(overrides)
    return row


def test_increment_has_exactly_the_six_design_keys_plus_reason() -> None:
    assert INCREMENT_REQUIRED == (
        "old_judgment",
        "new_info",
        "new_judgment",
        "affected_period",
        "supporting_evidence",
        "counter_evidence",
    )
    assert INCREMENT_REASON == "reason"


def test_complete_increment_passes() -> None:
    assert validate_increment(_increment()) == []


@pytest.mark.parametrize("key", [*INCREMENT_REQUIRED, INCREMENT_REASON])
def test_each_missing_key_is_reported_by_name(key) -> None:
    """六要素 + 原因缺任一项 ⇒ **点名**报出（`§G.3`：缺口必须可定位）。"""
    row = _increment()
    row.pop(key)
    assert key in increment_gaps(row)


def test_empty_counter_evidence_is_legal_but_a_missing_key_is_not() -> None:
    """★ `§H.3` 的示例里 `counter_evidence` 逐字就是 `[]` —— "没有反证"是合法状态。

    但**键必须存在**：缺键 ≠ 空数组（前者是"没交代"，后者是"交代了：没有反证"）。
    """
    assert validate_increment(_increment(counter_evidence=[])) == []
    row = _increment()
    row.pop("counter_evidence")
    assert "counter_evidence" in increment_gaps(row)


def test_empty_new_info_is_rejected() -> None:
    """★ `§H.2` 的"状态变更函数仅在 `new_info != ∅` 时运行"在**记录层**的对应物：

    一条 `new_info` 为空的 increment 就是**制造出来的变化** ⇒ 拒。
    """
    assert "new_info(不得为空)" in increment_gaps(_increment(new_info=[]))


def test_blank_reason_is_rejected() -> None:
    """`N4.5-04`：每次状态变更**含原因** —— 空白原因等于没给。"""
    assert INCREMENT_REASON in increment_gaps(_increment(reason="   "))


def test_missing_increment_is_reported_not_crashed() -> None:
    assert tuple(increment_gaps(None)) == ("<increment 缺失>",)
