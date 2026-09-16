"""`state_machine.py` —— 3×4 价值状态机 + 增量更新 + **无变化分支**（`Ch4 §H`）。

## 设计锚点（逐字）

`Ch4 §H.1`：

```yaml
value_state:
  growth_momentum_state: strengthening|weakening|unchanged|tbd
  certainty_state:       strengthening|weakening|unchanged|tbd
  moat_state:            strengthening|weakening|unchanged|tbd                # 趋势（既有）
  moat_level:            weak|moderate|strong|tbd                            # 水平（v1.1 回改 R-05，新增）
```

- **三个独立字段**（禁止单一总状态）："动力增强、确定性减弱、护城河不变"可**同时出现**；
- **状态变更触发**：仅当**有 `claim_impact` 改变该维度证据**时；
- **"待判断" vs "不变"**：待判断 = **信息不足、无法判断**；不变 = **已研究且确认无变化**
  （两者语义不同，`N4.5-03`）。

`Ch4 §H.2` 伪码：

```python
def update_states(old_states, new_info, impacts):
    if not new_info or not affects_dimension(impacts):
        return old_states, CheckRecord("本次核查无变化")   # ← 不写新版本
    return apply_changes(old_states, impacts), ...
```

## "3×4"怎么读

三个**方向**字段（`growth_momentum_state` / `certainty_state` / `moat_state`）× 四值
（`strengthening` / `weakening` / `unchanged` / `tbd`）= **3×4**；`moat_level` 是**水平**
（第四个数轴、取值 `weak|moderate|strong|tbd`），与 `moat_state`（趋势）**独立且可不同向**
（`§H.4①`；断言：schema **不得**把二者合并为单一 `moat` 字段 —— `schema/models.py` 已分列）。

## 两条不许越的线

1. **无新信息不产新版本**（`§H.2` / `N4.5-05`）：返回 `wrote_new_version=False`，
   并给出"本次核查无变化"的记录 —— 使"无信号"成为**正常态**（`Ch1 §C.2`）。
2. **待判断 ≠ 不变**（`N4.5-03`）：`tbd` 与 `unchanged` 是**两个不同的值**，
   本模块**不**在任何分支里把二者互换。

★ 取值域**不重抄**：方向四值取自 `schema.models.DirectionState`、水平四值取自
  `MoatLevel`（`G-06` 唯一真源；`Ch9 §N9.1-18` 是它们的落位）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Mapping, Sequence

#: 三个**方向**维度（`Ch4 §H.1`：**独立**、可同时不同向）。
DIRECTION_DIMENSIONS: tuple[str, ...] = (
    "growth_momentum_state",
    "certainty_state",
    "moat_state",
)

#: 水平维度（`§H.4①`：与 `moat_state` 分离；**不**参与"方向"三轴）。
LEVEL_DIMENSION = "moat_level"

#: 状态变更的**原因**类别（`N4.5-04`：每次状态变更含原因）。
IMPACT_DIRECTIONS: tuple[str, ...] = ("strengthening", "weakening", "unchanged", "tbd")


def _enum_values(enum_name: str) -> frozenset[str]:
    """从 `schema.models` 取枚举取值（**不重抄**，`G-06`）。惰性 import 避免 pydantic 常驻成本。"""
    import schema.models as models

    return frozenset(m.value for m in getattr(models, enum_name))


@dataclass(frozen=True)
class DimensionImpact:
    """**一条**改变某维度证据的影响（`Ch4 §H.1`："仅当有 `claim_impact` 改变该维度证据时"）。

    `dimension` ∈ `DIRECTION_DIMENSIONS`；`direction` ∈ `IMPACT_DIRECTIONS`。
    `claim_id` 是**新信息**的引用（`§H.3` 的 `new_info` / `supporting_evidence`）——
      故 `affects_dimension` 能同时回答"有没有影响"与"影响哪一维度"。
    """

    claim_id: str
    dimension: str
    direction: str


@dataclass(frozen=True)
class StateUpdate:
    """`update_states()` 的结果。

    - `states`：新的（或原样的）四字段状态；
    - `changed`：是否有维度真的变了（`False` ⇒ **不写新版本**，`§H.2`）；
    - `judgment_change`：逐维度 `bool`（可直接喂 `schema.models.CheckRecord.judgment_change`）；
    - `wrote_new_version`：**与 `changed` 同值**，但名字更直白地表达契约（"不产新信号"）。
    - `note`：核查记录的自由说明（无变化时逐字为 §H.2 的"本次核查无变化"）。
    """

    states: Mapping[str, str]
    changed: bool
    judgment_change: Mapping[str, bool] = field(default_factory=dict)
    wrote_new_version: bool = False
    note: str = ""

    def to_check_record(self, *, check_id: str, run_date: date, scope: str) -> Any:
        """构造 `Ch9 §N9.1` / `Ch1 §C.2` 的**规范** `CheckRecord`（`G-06`：不另造记录类型）。

        `signals_emitted` = 本维度变化的条数（`§H.2` 的"**不产新信号**"由此成为可观测计数）。
        """
        from schema.models import CheckRecord, CheckScope

        return CheckRecord(
            check_id=check_id,
            run_date=run_date,
            scope=CheckScope(scope),
            changed=self.changed,
            judgment_change=dict(self.judgment_change),
            signals_emitted=sum(1 for v in self.judgment_change.values() if v),
        )


def default_states() -> dict[str, str]:
    """四字段的**初值**：全部 `tbd`（`Ch4 §H.1`）。

    ★ 为什么初值是 `tbd` 而**不是** `unchanged`：`N4.5-03` 逐字区分二者 ——
      "待判断 = 信息不足、无法判断；不变 = **已研究且确认**无变化"。
      首版尚未研究 ⇒ 只能是 `tbd`。
    """
    return {dim: "tbd" for dim in DIRECTION_DIMENSIONS} | {LEVEL_DIMENSION: "tbd"}


def _field(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def value_state_refs(baseline: Any) -> dict[str, str]:
    """`Ch4 §H.4②` 逐字：输出供第七章 `classify_opportunity()` 消费的四字段。

    ```python
    def value_state_refs(baseline) -> dict:
        return {"growth_momentum_state": baseline.value_state.growth_momentum_state,
                "certainty_state":       baseline.value_state.certainty_state,
                "moat_level":            baseline.value_state.moat_level,   # 水平
                "moat_state":            baseline.value_state.moat_state}   # 趋势
    ```

    ★ 字段名与 `Ch7 §E.3`、`Ch2 §C.1/§C.2` **逐字一致**（`§H.4②` 末句）——
      故这里**不**改写成别的键名，也不增减字段。
    ★ 为什么读 `value_state_refs` 而不是 `value_state`：`schema.models.Baseline` 的落位字段是
      `value_state_refs`（`Ch9 §N9.1-18`），两者是同一对象的两种行文（已登记）。
    """
    state = _field(baseline, "value_state_refs") or _field(baseline, "value_state") or {}
    out: dict[str, str] = {}
    for key in (*DIRECTION_DIMENSIONS, LEVEL_DIMENSION):
        value = _field(state, key)
        out[key] = "tbd" if value is None else str(getattr(value, "value", value))
    return out


def affects_dimension(impacts: Iterable[Any]) -> bool:
    """是否有影响落在三个**方向**维度上（`Ch4 §H.1` / `§H.2`）。

    ★ 只认 `DIRECTION_DIMENSIONS`：`moat_level`（水平）**不是**方向维度，
      一个只改水平的信号**不应**擅自改写三个方向字段（反之亦然）。
      两者独立可不同向（`§H.4①`）。
    """
    return any(str(_field(i, "dimension") or "") in DIRECTION_DIMENSIONS for i in impacts)


def validate_impact(impact: Any) -> list[str]:
    """影响条目的**取值域**校验（`Ch4 §H.1`）。返回违例说明（空 = 通过）。"""
    dimension = str(_field(impact, "dimension") or "")
    direction = str(_field(impact, "direction") or "")
    out: list[str] = []
    if dimension not in DIRECTION_DIMENSIONS:
        out.append(
            f"dimension={dimension!r} 不在 {list(DIRECTION_DIMENSIONS)} 内 —— "
            "三方向维度是 §H.1 的封闭取值域（水平维度 moat_level 另行处理）"
        )
    if direction not in IMPACT_DIRECTIONS:
        out.append(
            f"direction={direction!r} 不在 {list(IMPACT_DIRECTIONS)} 内 —— 方向四值取自 DirectionState（§H.1）"
        )
    if not str(_field(impact, "claim_id") or ""):
        out.append("缺 claim_id —— 状态变更必须能追到改变证据的主张（§H.1/N4.5-04）")
    return out


def update_states(
    old_states: Mapping[str, str],
    new_info: Sequence[str],
    impacts: Iterable[Any],
    *,
    run_date: date | None = None,
    check_id: str = "",
    scope: str = "recheck",
) -> StateUpdate:
    """`Ch4 §H.2` 伪码逐条落地。

    ```
    if not new_info or not affects_dimension(impacts):
        return old_states, CheckRecord("本次核查无变化")   # ← 不写新版本
    return apply_changes(old_states, impacts), ...
    ```

    - `old_states` 里**缺**的维度补 `tbd`（`default_states()` 的语义）；
    - 影响条目取值非法 ⇒ `ValueError`（**响亮失败**：取值域是封闭的，
      非法值不得被静默忽略成"无影响" —— 那会让"没研究"与"研究过但没变化"不可区分）；
    - 只改 `DIRECTION_DIMENSIONS`；`moat_level` **原样保留**（不越权）。
      ★ `moat_level`（水平）不是本入口的写入对象：它的取值域是 `weak|moderate|strong|tbd`
        而本类型的 `direction` 取值域是趋势四值（`§H.1`），两者**不可混用一个字段** ——
        故"改变水平"的影响条目会被 `validate_impact` **响亮拒绝**，而不是被静默吞成"无影响"。
    """
    for impact in impacts:
        problems = validate_impact(impact)
        if problems:
            raise ValueError("状态影响条目非法：" + "；".join(problems))

    states = dict(default_states())
    states.update({k: str(getattr(v, "value", v)) for k, v in dict(old_states).items()})

    # ★ 两个条件必须**同时**不成立才走"无变化"分支（§H.2 的 `or` 语义）：
    #   `not new_info`（没有新信息）或 `not affects_dimension`（新信息不影响这些维度）。
    if not new_info or not affects_dimension(impacts):
        return StateUpdate(
            states=states,
            changed=False,
            judgment_change={dim: False for dim in DIRECTION_DIMENSIONS},
            wrote_new_version=False,
            note="本次核查无变化",
        )

    impacted_ids = {str(x) for x in new_info}
    judgment_change: dict[str, bool] = {}
    for dim in DIRECTION_DIMENSIONS:
        target: str | None = None
        for impact in impacts:
            if str(_field(impact, "dimension")) != dim:
                continue
            if str(_field(impact, "claim_id")) not in impacted_ids:
                # 该影响**不是**由本次新信息引起的 ⇒ 不构成"状态变更触发"（§H.1）。
                continue
            target = str(_field(impact, "direction"))
        if target is None:
            judgment_change[dim] = False
            continue
        judgment_change[dim] = target != states[dim]
        states[dim] = target
    changed = any(judgment_change.values())
    return StateUpdate(
        states=states,
        changed=changed,
        judgment_change=judgment_change,
        wrote_new_version=changed,
        note=(
            "状态变更：" + "；".join(f"{k}→{states[k]}" for k, v in judgment_change.items() if v)
            if changed
            else "本次核查无变化（新信息不影响三方向维度的证据）"
        ),
    )


# ─────────────────────────── 增量更新六要素（`Ch4 §H.3` / `N4.5-01`） ───────────────────────────

#: `Ch4 §H.3` 代码块里 increment 的**六要素**（逐字键名）+ `N4.5-04` 的 `reason`。
INCREMENT_REQUIRED: tuple[str, ...] = (
    "old_judgment",
    "new_info",
    "new_judgment",
    "affected_period",
    "supporting_evidence",
    "counter_evidence",
)

#: `N4.5-04`：每次状态变更**含原因**。
INCREMENT_REASON = "reason"


def validate_increment(increment: Any) -> list[str]:
    """`Ch4 §H.3` 六要素 + `N4.5-04` 原因：返回缺失/非法的键（空 = 通过）。

    ★ `new_info` **必须非空**且 `reason` **必须非空**：
      `§H.2` 的"状态变更函数仅在 `new_info != ∅` 时运行"在**记录层**的对应物 ——
      一条 `new_info` 为空的 increment 就是"制造出来的变化"（`schema.models.Increment`
      已在 schema 层拒绝 `new_info` 为空，本函数在**值**层再核一次 `reason`）。
    ★ `counter_evidence` 允许为**空数组**（`§H.3` 的示例逐字就是 `[]`）——
      "没有反证"是合法状态，但**键必须存在**（缺键 ≠ 空数组）。
    """
    if increment is None:
        return ["<increment 缺失>"]
    out: list[str] = []
    for key in INCREMENT_REQUIRED:
        value = _field(increment, key)
        if value is None:
            out.append(key)
            continue
        if key in ("new_info", "supporting_evidence", "counter_evidence"):
            if not isinstance(value, (list, tuple)):
                out.append(f"{key}(应为数组)")
            elif key == "new_info" and not value:
                out.append("new_info(不得为空)")
        elif not str(value).strip():
            out.append(f"{key}(不得为空)")
    reason = _field(increment, INCREMENT_REASON)
    if not str(reason or "").strip():
        out.append(INCREMENT_REASON)
    return out


def increment_gaps(increment: Any) -> Sequence[str]:
    """`Ch4 §G.3` 的 `gap` 衔接：六要素不全 ⇒ 返回"不足以完成"的键（供上层记 gap）。"""
    return tuple(validate_increment(increment))
