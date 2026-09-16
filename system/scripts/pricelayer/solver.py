#!/usr/bin/env python3
"""`solver.py` —— **反向求解器**：价格隐含要求的**多解集**（`Ch5 §B`）。

## 为什么必须产出多组解（`Ch5 §B.1` 逐字）

> 价格 `P = f(g, m, r, k, T)`（增长 g、利润 m、再投资 r、风险 k、持续时间 T）是**欠定方程**
> —— 一个 P 对应**无穷多组**解。故**必须展示多组解**，否则会把某一解误当"市场的唯一真相"。

## 责任分工（`Ch5 §B.3` 逐字：**模型不做算术，程序不做假设**）

| 责任 | 谁 | 内容 |
|---|---|---|
| 假设生成 | **模型** | 候选假设（g/m/r/k/T）取值与组合方向、替代解释、**假设空间边界** |
| 求解 | **程序** | 固定 4 类解第 5 类；由假设正算隐含价格；迭代找可行解集 |
| 校验 | **程序 + 人工/规则** | 程序校验口径与算术；人工/规则校验假设合理性 |

⇒ 本模块的**入参**是"候选假设组合"（`CandidateCombination[]`，由模型给），
**出参**是"解集 + 每组区间 + 替代解释"（`ImpliedSolutionSet`）。本模块**不生成任何假设**，
也**不内置 `f` 的具体形式** —— `Ch5 §B.1` 只给了抽象形式 `P = f(g,m,r,k,T)`，
具体函数式设计**没有给**，故 `forward_price` 以**调用方注入的纯函数**承载
（登记为待裁定项；不自行编一个公式冒充设计）。

## 求解方法（`Ch5 §I.2` 的控制手段逐字："限制每类假设的离散粒度 + 网格搜索上界"）

- **网格 + 单调剪枝**（`Ch5 §J1` 的建议："网格 + 单调剪枝（可单测、可控）"）；
- **离散粒度**（`00_待拍板项清单` B13，**已确认**："增长率 ±1 个百分点 / 利润率 ±0.5 / 折现率 ±0.5"）
  ⇒ 粒度由调用方显式传入（本层不内置数值；`Ch5 §J2` 要求参数化）；
- **解集展示上限**（`00_待拍板项清单` B18，**已确认**："默认展示 3 组，最多 5 组"）
  ⇒ `display_cap` 默认 `3`、硬上限 `5`；
- **网格上界告警**（`Ch5 §I.2`："设网格上限告警"）⇒ 超出 `max_grid_points` **不静默**：
  记 note + 置 `degraded`，该组合的可行区间按已扫部分给出。

## 输出结构（`Ch5 §B.2` 逐字，落 `facts/implied_requirements.jsonl`）

```json
{"implied_id":"IMP-001","solution_set_id":"SET-nvda-2026-09-15",
 "security_id":"sec_nvda","price_snapshot_id":"SNP-...","current_price":"...",
 "assumptions":{"growth":{...},"margin":{...},"reinvestment":{...},
                "risk":{...},"duration":{...}},
 "solved_variable":"reinvestment",
 "range":{"low":"...","high":"..."},
 "alternative_explanations":["...","..."],
 "feasible":true,"method_version":"v1","computed_at":"..."}
```

## CLI

```
python system/scripts/pricelayer/solver.py [code_root]
```

退出码 `0` 放行 / `1` 命中违例 / `2` 输入异常（复用 `_common.run_checker`）。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if __package__:
    from . import PriceLayerError
else:  # 直接以脚本方式运行（CLI 出口；仓库既有守卫都是这种调用方式）
    from scripts.pricelayer import PriceLayerError

METHOD_VERSION = "pricelayer-solver-v1"
"""本求解器的 `method_version`（`Ch5 §B.2` 的 `"method_version":"v1"`）。

★ 变更语义（纪律 4 追加式不可变）：`method_version` 一变，**必须落新行**，不得就地覆盖。
"""

DEFAULT_DISPLAY_CAP = 3
"""解集**默认展示组数**的设计逐字值（B18："默认展示 3 组"）。

★ 真值取自 `rules/valuation-methods.yaml::solution_set_display.default_count`（现为 `3`）；
  本常量仅作规则文件/该键缺失时的回落，并由 `check` 的绑定断言核"代码默认值 == 文件真值"。
"""

MAX_DISPLAY_CAP = 5
"""解集展示**硬上限**的设计逐字值（B18："最多 5 组"）。

★ 真值取自 `solution_set_display.max_count`（现为 `5`）；同上。
"""

DESIGN_MUST_SHOW_MULTIPLE = True
"""`Ch5 §B.1` 逐字："欠定方程 ⇒ 展示**多组**解" —— `True` 即"必须多组"。

★ 真值取自 `solution_set_display.must_show_multiple`（现为 `true`）；
  本常量仅作规则文件/该键缺失时的**设计逐字回落**，并由 `_rule_binding_violations`
  核"代码回落值 == 文件真值"（否则"规则改了、回落没改"不会被发现）。
"""

DEFAULT_MIN_SOLUTIONS = 2
"""多解**数值下界**（"多"的机械化）。

★ **不由本常量定义** —— 它是 `solution_set_display.must_show_multiple` 的**派生值**
  （`2 if must_show_multiple else 1`），真值源在 `rules/`（`Ch11 §D.2` / `G-06`：
  避免"语义键与数值键可互相矛盾"的同一事实两处）。
  ★ 本常量仅作规则文件缺失时的设计逐字回落（`Ch5 §B.1`："必须展示多组解"）。
"""

VALUATION_METHODS_YAML = "rules/valuation-methods.yaml"
RULE_KEY_SOLUTION_SET_DISPLAY = "solution_set_display"
RULE_KEY_ASSUMPTION_GRID = "assumption_grid"
RULE_KEY_MUST_SHOW_MULTIPLE = "must_show_multiple"
RULE_KEY_DEFAULT_COUNT = "default_count"
RULE_KEY_MAX_COUNT = "max_count"
RULE_KEY_SOLVER_REF = "solver_ref"

RULE_BOUND_ENTRIES: tuple[tuple[str, str], ...] = (
    (VALUATION_METHODS_YAML, RULE_KEY_SOLUTION_SET_DISPLAY),
    (VALUATION_METHODS_YAML, RULE_KEY_ASSUMPTION_GRID),
)
"""``(规则文件, 本模块实际读取的顶层键)`` 的机器绑定对照集合（`Ch11 §D.2`）。"""


@dataclass(frozen=True)
class SolutionSetDisplay:
    """`rules/valuation-methods.yaml::solution_set_display` 的解析结果（**带来源标注**）。

    - `value_source`：`"rules"` = 取自规则文件；`"design_default"` = 文件/键缺失，取
      **设计逐字值**（`DEFAULT_DISPLAY_CAP` / `MAX_DISPLAY_CAP` / `DESIGN_MUST_SHOW_MULTIPLE`）。
    - `notes`：**`value_source == "design_default"` 时必非空** —— 逐条写明**缺的是什么**，
      使"不走门禁的调用方"也能看到"值其实不是从规则读到的"（主理人裁定 ③-2：
      `design_default` 必须打 note，否则就是静默降级）。
    """

    default_count: int
    max_count: int
    must_show_multiple: bool
    selection: str = ""
    overflow: str = ""
    value_source: str = "design_default"
    notes: tuple[str, ...] = ()

    @property
    def min_count(self) -> int:
        """多解数值下界 = `must_show_multiple` 的**派生值**（真源 = 该语义键）。"""
        return 2 if self.must_show_multiple else 1


def load_solution_set_display(root: str | Path | None = None) -> SolutionSetDisplay:
    """读 `solution_set_display`（`Ch5 §I.2` / `§J.3` / B18）—— **唯一读口**。

    - 文件/键缺失 → 回落**设计逐字值**（B18 `3` / `5` + `Ch5 §B.1` 的"必须多组"）并标
      `value_source="design_default"` **且记一条写明缺失对象的 note**（主理人裁定 ③-1/③-2：
      回落值必须能在设计里逐字找到出处，且不得静默）。
    - `default_count > max_count` 或非正整数 → `PriceLayerError`（**响亮失败**，不静默夹紧）。
    """
    from scripts._common import _cached_yaml  # `P-02`

    def _fallback(reason: str) -> SolutionSetDisplay:
        return SolutionSetDisplay(
            default_count=DEFAULT_DISPLAY_CAP,
            max_count=MAX_DISPLAY_CAP,
            must_show_multiple=DESIGN_MUST_SHOW_MULTIPLE,
            value_source="design_default",
            notes=(
                f"NO_SOLUTION_SET_DISPLAY: {reason} —— 回落设计逐字值 "
                f"default_count={DEFAULT_DISPLAY_CAP}（B18）/ max_count={MAX_DISPLAY_CAP}（B18）/ "
                f"must_show_multiple={DESIGN_MUST_SHOW_MULTIPLE}（Ch5 §B.1）（非'已核'）",
            ),
        )

    if root is None:
        return _fallback("未给 code_root")
    path = Path(root) / VALUATION_METHODS_YAML
    if not path.exists():
        return _fallback(f"{VALUATION_METHODS_YAML} 不存在")
    doc = _cached_yaml(path) or {}
    node = doc.get(RULE_KEY_SOLUTION_SET_DISPLAY)
    if not isinstance(node, Mapping):
        return _fallback(f"{VALUATION_METHODS_YAML} 缺/非法键 {RULE_KEY_SOLUTION_SET_DISPLAY!r}")
    default_count = int(node.get(RULE_KEY_DEFAULT_COUNT) or DEFAULT_DISPLAY_CAP)
    max_count = int(node.get(RULE_KEY_MAX_COUNT) or MAX_DISPLAY_CAP)
    must_show_multiple = bool(node.get(RULE_KEY_MUST_SHOW_MULTIPLE, DESIGN_MUST_SHOW_MULTIPLE))
    if default_count < 1 or max_count < 1 or default_count > max_count:
        raise PriceLayerError(
            f"{VALUATION_METHODS_YAML}:: {RULE_KEY_SOLUTION_SET_DISPLAY} 取值非法："
            f"default_count={default_count} / max_count={max_count} "
            "（须为正整数且 default_count <= max_count；不静默夹紧）"
        )
    notes: list[str] = []
    for key in (RULE_KEY_DEFAULT_COUNT, RULE_KEY_MAX_COUNT, RULE_KEY_MUST_SHOW_MULTIPLE):
        if key not in node:
            notes.append(
                f"NO_DISPLAY_KEY: {VALUATION_METHODS_YAML}:: {RULE_KEY_SOLUTION_SET_DISPLAY}."
                f"{key} 缺失 —— 该字段取设计逐字回落值（非'已核'）"
            )
    return SolutionSetDisplay(
        default_count=default_count,
        max_count=max_count,
        must_show_multiple=must_show_multiple,
        selection=str(node.get("selection") or ""),
        overflow=str(node.get("overflow") or ""),
        value_source="rules",
        notes=tuple(notes),
    )


def all_assumption_keys() -> tuple[str, ...]:
    """五类假设的键（`Ch5 §B.4` 假设组合表：增长/利润/再投资/风险/持续时间）。

    ★ 与 `schema.models.SolvedVariable` **逐字一致**（`G-06` 唯一真源：不新造第二套键名）。
    ★ **惰性**导入 schema（pydantic ≈0.3s）：本模块带守卫 CLI，模块级不得急切付这笔成本（`P-03`）。
    """
    from schema.models import SolvedVariable

    return tuple(v.value for v in SolvedVariable)


class SolverError(PriceLayerError):
    """求解器的**输入契约**错误（候选组合缺类 / 非法网格参数等）。"""


@dataclass(frozen=True)
class SearchBound:
    """解第 5 类时的**假设空间边界**（`Ch5 §B.3`：边界由**模型**给，程序不猜）。"""

    low: Decimal
    high: Decimal

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise SolverError(f"假设空间边界非法：low({self.low}) > high({self.high})")


@dataclass(frozen=True)
class CandidateCombination:
    """模型给出的**一个候选假设组合**（`Ch5 §B.4`："固定 4 类、解第 5 类"）。

    | 字段 | 语义 |
    |---|---|
    | `fixed` | **固定不动**的四类假设（键 ∈ `all_assumption_keys()`，**不含** `solved_variable`） |
    | `solved_variable` | 本次被**解出**的那一类（`Ch5 §B.2` 的 `"solved_variable"`） |
    | `solved_bound` | 解出变量的**假设空间边界**（模型给） |
    | `alternative_explanations` | **替代解释**（`Ch5 §B.2` 逐字字段；模型给） |
    | `monotonic_increasing` | 该组合下 `f` 对解出变量是否单调递增（供**单调剪枝**，模型给方向） |
    """

    combination_id: str
    solved_variable: SolvedVariable
    fixed: dict[str, Decimal]
    solved_bound: SearchBound
    alternative_explanations: list[str]
    monotonic_increasing: bool = True

    def __post_init__(self) -> None:
        keys = all_assumption_keys()
        solved = self.solved_variable.value
        if solved not in keys:
            raise SolverError(f"未知 solved_variable={solved!r}（Ch5 §B.4 五类之一）")
        expected = {k for k in keys if k != solved}
        got = set(self.fixed)
        if got != expected:
            missing = sorted(expected - got)
            extra = sorted(got - expected)
            raise SolverError(
                f"候选组合 {self.combination_id!r} 的固定假设类不合法："
                f"缺 {missing} / 多 {extra}（Ch5 §B.4：固定其余 4 类，解第 5 类）"
            )
        if not self.alternative_explanations:
            raise SolverError(
                f"候选组合 {self.combination_id!r} 未给 alternative_explanations —— "
                "Ch5 §B.2 要求每组解含替代解释"
            )


@dataclass(frozen=True)
class ImpliedSolution:
    """一组解（对应一行 `facts/implied_requirements.jsonl`）。"""

    implied_id: str
    solution_set_id: str
    security_id: str
    price_snapshot_id: str
    current_price: Decimal
    combination: CandidateCombination
    solved_low: Decimal | None
    solved_high: Decimal | None
    feasible: bool
    method_version: str
    computed_at: datetime

    def assumptions_payload(self) -> dict[str, dict[str, Any]]:
        """`Ch5 §B.2` 的 `assumptions{growth,…,duration}` 载荷。

        固定四类 → `{"value": "<点值>"}`；被解出的一类 → `{"low":…,"high":…,"solved":true}`。
        §B.2 的内层结构写作 `{...}`（设计未给内层字段名）⇒ 用开放映射，**不伪造**内层结构。
        """
        payload: dict[str, dict[str, Any]] = {}
        solved = self.combination.solved_variable.value
        for key, value in sorted(self.combination.fixed.items()):
            payload[key] = {"value": str(value)}
        payload[solved] = {
            "low": None if self.solved_low is None else str(self.solved_low),
            "high": None if self.solved_high is None else str(self.solved_high),
            "solved": True,
        }
        return payload


@dataclass
class ImpliedSolutionSet:
    """**解集**（`Ch5 §B.2`："`solution_set_id` 聚合一组解"）。

    展示层呈现"使当前价格成立**解集**"（多组 + 每组区间 + 替代解释）。
    """

    solution_set_id: str
    security_id: str
    price_snapshot_id: str
    current_price: Decimal
    solutions: list[ImpliedSolution] = field(default_factory=list)
    folded: list[ImpliedSolution] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    degraded: bool = False
    feasible_count: int = 0
    candidate_count: int = 0
    method_version: str = METHOD_VERSION

    def to_implied_requirements(self) -> list[Any]:
        """转成 `schema.models.ImpliedRequirement`（落 `facts/implied_requirements.jsonl`）。"""
        from schema.models import ImpliedAssumptions, ImpliedRange, ImpliedRequirement

        rows: list[Any] = []
        for sol in self.solutions:
            payload = sol.assumptions_payload()
            rows.append(
                ImpliedRequirement(
                    implied_id=sol.implied_id,
                    solution_set_id=sol.solution_set_id,
                    security_id=sol.security_id,
                    price_snapshot_id=sol.price_snapshot_id,
                    current_price=sol.current_price,
                    assumptions=ImpliedAssumptions(**payload),
                    solved_variable=sol.combination.solved_variable,
                    range=ImpliedRange(low=sol.solved_low, high=sol.solved_high),
                    alternative_explanations=list(sol.combination.alternative_explanations),
                    feasible=sol.feasible,
                    method_version=sol.method_version,
                    computed_at=sol.computed_at,
                )
            )
        return rows


# ───────────────────────── 求解 ─────────────────────────


def _grid_values(bound: SearchBound, step: Decimal) -> list[Decimal]:
    """在 `[low, high]` 上按 `step` 生成**升序网格**（含上界，去重）。

    `step <= 0` → `SolverError`（不许"步长 0"这种自欺的网格）。
    """
    if step <= 0:
        raise SolverError(f"网格步长必须为正，实得 {step}")
    values: list[Decimal] = []
    value = bound.low
    while value <= bound.high:
        values.append(value)
        value = value + step
    if not values or values[-1] != bound.high:
        values.append(bound.high)
    return values


def solve_combination(
    combination: CandidateCombination,
    *,
    current_price: Decimal,
    forward_price: Callable[[dict[str, Decimal]], Decimal],
    grid_step: Decimal,
    tolerance: Decimal,
    max_grid_points: int,
    subject: str,
) -> tuple[Decimal | None, Decimal | None, bool, list[str]]:
    """解**单个**候选组合：在解出变量上找"使隐含价格等于当前价（容差内）"的取值集。

    返回 `(low, high, feasible, notes)`；`feasible=False` 时 `low/high` 均为 `None`
    （`Ch5 §B.2` 的 `feasible` 字段：该组合**不能**使当前价格成立也是一种结论）。

    - **单调剪枝**（`Ch5 §J1`）：`monotonic_increasing=True` 且已越过容差带上沿 ⇒ 提前停扫；
      方向由**模型**给（`§B.3`：程序不做假设）。
    - **网格上界**（`Ch5 §I.2`）：网格点数 > `max_grid_points` ⇒ 记 note（**不静默**）。
    """
    notes: list[str] = []
    values = _grid_values(combination.solved_bound, grid_step)
    if len(values) > max_grid_points:
        notes.append(
            f"GRID_CAP_EXCEEDED: 组合 {combination.combination_id} 的网格点 {len(values)} "
            f"> 上限 {max_grid_points}，按已扫部分给区间（Ch5 §I.2 网格上界告警）"
        )
        values = values[:max_grid_points]
    if tolerance < 0:
        raise SolverError(f"tolerance 不得为负，实得 {tolerance}")

    lower = current_price - tolerance
    upper = current_price + tolerance
    feasible_values: list[Decimal] = []
    for value in values:
        point = dict(combination.fixed)
        point[combination.solved_variable.value] = value
        implied = forward_price(point)
        inside = lower <= implied <= upper
        if inside:
            feasible_values.append(value)
        elif (
            combination.monotonic_increasing
            and implied > upper
            and feasible_values
        ):
            break  # 单调剪枝：已越过容差带且此前已有可行点 ⇒ 后续不可能再落入
    if not feasible_values:
        return None, None, False, notes
    return min(feasible_values), max(feasible_values), True, notes


def solve_implied_requirements(
    *,
    security_id: str,
    price_snapshot_id: str,
    current_price: Decimal,
    candidates: Sequence[CandidateCombination],
    forward_price: Callable[[dict[str, Decimal]], Decimal],
    grid_step: Decimal,
    tolerance: Decimal,
    solution_set_id: str,
    max_grid_points: int = 256,
    display: SolutionSetDisplay | None = None,
    display_cap: int | None = None,
    computed_at: datetime | None = None,
    method_version: str = METHOD_VERSION,
) -> ImpliedSolutionSet:
    """**反向求解主入口**：多组候选 → 解集（多组解 + 每组区间 + 替代解释）。

    - `current_price` 非正 → `SolverError`（价格隐含要求对非正价格无定义）。
    - 每个候选组合都产出一组解（含 `feasible=False` 的"该组合不成立"）；
      **可行**解按 `(区间下界, combination_id)` 稳定排序后按上限折叠
      （`Ch5 §I.2`："只保留代表解 + 区间包络（`solution_set` 上限 N，超出折叠）"）。
    - **展示上限来自规则**：`display` = `load_solution_set_display(root)` 的结果
      （`rules/valuation-methods.yaml::solution_set_display`，B18：默认 3 / 最多 5）。
      `display_cap` 是**显式覆盖**（测试用）；不传则取 `display.default_count`。
      → 规则文件改了上限，本函数行为随之改变，**不硬编码**（`Ch11 §D.2`）。
    - 上限必须 ∈ `[1, display.max_count]`（B18 的"最多 5 组"是硬上限）。
    - 求解完成后**不自行宣布合格**：多解不变式由 `assert_multi_solution()` 单独把关
      （呈现前调用），此处只把"未达下限"如实记进 `notes` + `degraded`。
    - 时间契约：`computed_at` 缺省取 `now()` —— 这是**本层自产时间**（`Ch5 §B.2` 的
      `computed_at` 就是"算出这一刻"），与 `§D.3` 的"baseline 版本时间"是两回事。
    """
    if current_price <= 0:
        raise SolverError(f"{security_id}: 当前价格非正（{current_price}），反解无定义")
    display = display or SolutionSetDisplay(
        default_count=DEFAULT_DISPLAY_CAP,
        max_count=MAX_DISPLAY_CAP,
        must_show_multiple=DESIGN_MUST_SHOW_MULTIPLE,
        value_source="design_default",
        notes=(
            "NO_SOLUTION_SET_DISPLAY: 调用方未传 display —— 回落设计逐字值"
            f"（B18 {DEFAULT_DISPLAY_CAP}/{MAX_DISPLAY_CAP}、Ch5 §B.1 多解）（非'已核'）",
        ),
    )
    cap = display.default_count if display_cap is None else display_cap
    if not 1 <= cap <= display.max_count:
        raise SolverError(
            f"展示上限 {cap} 越界（1..{display.max_count}；"
            f"`{RULE_KEY_SOLUTION_SET_DISPLAY}.{RULE_KEY_MAX_COUNT}` = B18「最多 5 组」）"
        )
    if not candidates:
        raise SolverError("候选假设组合为空 —— 反解无输入（Ch5 §B.3：假设由模型给）")

    moment = computed_at or datetime.now(timezone.utc)
    solution_set = ImpliedSolutionSet(
        solution_set_id=solution_set_id,
        security_id=security_id,
        price_snapshot_id=price_snapshot_id,
        current_price=current_price,
        candidate_count=len(candidates),
        method_version=method_version,
    )

    all_solutions: list[ImpliedSolution] = []
    for index, combination in enumerate(candidates, start=1):
        low, high, feasible, notes = solve_combination(
            combination,
            current_price=current_price,
            forward_price=forward_price,
            grid_step=grid_step,
            tolerance=tolerance,
            max_grid_points=max_grid_points,
            subject=security_id,
        )
        solution_set.notes.extend(notes)
        all_solutions.append(
            ImpliedSolution(
                implied_id=f"IMP-{solution_set_id}-{index:03d}",
                solution_set_id=solution_set_id,
                security_id=security_id,
                price_snapshot_id=price_snapshot_id,
                current_price=current_price,
                combination=combination,
                solved_low=low,
                solved_high=high,
                feasible=feasible,
                method_version=method_version,
                computed_at=moment,
            )
        )

    feasible_solutions = [s for s in all_solutions if s.feasible]
    solution_set.feasible_count = len(feasible_solutions)
    feasible_solutions.sort(key=lambda s: (s.solved_low or Decimal(0), s.combination.combination_id))
    solution_set.solutions = feasible_solutions[:cap]
    solution_set.folded = feasible_solutions[cap:]
    if solution_set.folded:
        solution_set.notes.append(
            f"SOLUTION_SET_FOLDED: 可行解 {len(feasible_solutions)} 组超出展示上限 "
            f"{cap}，已折叠 {len(solution_set.folded)} 组（Ch5 §I.2 / B18；"
            f"取自 {RULE_KEY_SOLUTION_SET_DISPLAY}.{RULE_KEY_DEFAULT_COUNT}）"
        )
    min_count = display.min_count
    if solution_set.feasible_count < min_count:
        solution_set.degraded = True
        solution_set.notes.append(
            f"SINGLE_SOLUTION_RISK: 可行解仅 {solution_set.feasible_count} 组（下限 "
            f"{min_count}）—— 欠定方程不得以单解呈现（Ch5 §B.1；下限由 "
            f"{RULE_KEY_SOLUTION_SET_DISPLAY}.{RULE_KEY_MUST_SHOW_MULTIPLE} 派生）"
        )
    return solution_set


def assert_multi_solution(
    solution_set: ImpliedSolutionSet,
    *,
    display: SolutionSetDisplay | None = None,
    min_solutions: int | None = None,
) -> None:
    """**呈现前**的多解不变式（`Ch5 §B.1`）：可行解数 < 下限 → `SingleSolutionError`。

    ★ 下限**不是常量**：默认由 `display.min_count` 派生，而 `display` 来自
      `rules/valuation-methods.yaml::solution_set_display.must_show_multiple`
      （`min_count = 2 if must_show_multiple else 1`）—— 规则改则行为改（`Ch11 §D.2`）。
      `min_solutions` 只是**显式覆盖**（测试用）。
    ★ 为什么是"呈现前"而不是"求解后"：欠定方程**天然可能**在当前候选下只有一组可行解
      —— 那本身是合法信息（应回去让模型扩假设空间）。但**呈现层不得**把单解当成
      "市场的唯一真相"，故在呈现边界上拒绝（`Ch5 §B.1` 的原话正是"否则会把某一解误当…"）。
    """
    if min_solutions is None:
        min_solutions = (
            display.min_count if display is not None else DEFAULT_MIN_SOLUTIONS
        )
    if solution_set.feasible_count < min_solutions:
        raise _single_solution_error(
            f"{solution_set.security_id}: 解集 {solution_set.solution_set_id!r} 仅有 "
            f"{solution_set.feasible_count} 组可行解（下限 {min_solutions}）—— "
            "欠定方程必须展示多组解（Ch5 §B.1）"
        )


def _single_solution_error(message: str) -> Exception:
    """惰性构造 `SingleSolutionError`（避免包级循环导入）。"""
    from . import SingleSolutionError

    return SingleSolutionError(message)


def write_solution_set(root: str | Path, solution_set: ImpliedSolutionSet) -> int:
    """把解集落 `facts/implied_requirements.jsonl`（**唯一写入口** = `schema.store`）。

    ★ 写目标受 `Ch5 §B.5` 约束：反解输出**只允许**写 `implied_requirements` 或 `gap`。
      本函数是唯一写口，故在此处调用 `order_guard.assert_write_target_allowed` 做守卫
      （`G-06`：不新写第二条写权限判定）。
    """
    from schema.store import append_records

    from .order_guard import assert_write_target_allowed

    assert_write_target_allowed("implied_requirements")
    rows = solution_set.to_implied_requirements()
    if not rows:
        return 0
    return append_records(root, "implied_requirements", rows)


# ───────────────────────── 守卫：真源扫描（CLI 承载面） ─────────────────────────

NOTE_NO_IMPLIED_ROWS = "NO_IMPLIED_ROWS"

_REQUIRED_ROW_FIELDS = (
    "implied_id",
    "solution_set_id",
    "security_id",
    "price_snapshot_id",
    "current_price",
    "solved_variable",
    "range",
    "alternative_explanations",
    "feasible",
    "method_version",
    "computed_at",
)
"""`Ch5 §B.2` 输出结构的**必填字段**（逐字取自该节 JSON）。"""


def check(root: str | Path) -> Any:
    """扫描 `facts/implied_requirements.jsonl`：多解不变式 + `Ch5 §B.2` 必填字段。

    - 每个 `solution_set_id` 的**可行**解必须 ≥ 下限（`§B.1`）；单解解集 → 违例。
      ★ 下限**读** `rules/valuation-methods.yaml::solution_set_display.must_show_multiple`
        派生（`2 if must_show_multiple else 1`），**不硬编码**（`Ch11 §D.2`）。
    - 每行的必填字段必须齐备且非空（`§B.2`）；`alternative_explanations` 必须非空。
    - 另含**规则↔代码机器绑定**（与 `facts/` 数据无关，故空样本也照跑）：
      本模块读取的 `solution_set_display` / `assumption_grid` 键必须真实存在，
      且 `assumption_grid.solver_ref` 必须指向本模块（防改名脱节）。
    - 空样本 → 显式 note（`G-03`），**不**判成"已验证"。
    """
    from scripts._common import CheckReport, Violation
    from schema.store import read_records

    root_path = Path(root)
    report = CheckReport(checker="pricelayer_solver")
    report.scanned["rule_binding_checks"] = len(RULE_BOUND_ENTRIES)
    display = load_solution_set_display(root_path)
    report.scanned["min_solution_count"] = display.min_count
    report.scanned["display_value_source"] = 1 if display.value_source == "rules" else 0
    # `design_default` 的 note 必须**真的上报**（主理人裁定 ③-2）：否则只读 report 的调用方
    # 永远看不到"展示上限其实不是从规则读到的"。
    report.notes.extend(display.notes)
    report.scanned["display_default_count"] = display.default_count
    report.scanned["display_max_count"] = display.max_count
    for text in _rule_binding_violations(root_path):
        report.violations.append(Violation("SOLVER-RULE-BINDING", text))

    rows = read_records(root_path, "implied_requirements")
    report.scanned["implied_rows"] = len(rows)
    if not rows:
        report.notes.append(f"{NOTE_NO_IMPLIED_ROWS}: 无反解行可检（非'已验证'）")
        return report

    min_count = display.min_count
    groups: dict[str, int] = {}
    for row in rows:
        implied_id = str(row.get("implied_id") or "<no-implied_id>")
        for field_name in _REQUIRED_ROW_FIELDS:
            if field_name not in row or row.get(field_name) in (None, "", [], {}):
                report.violations.append(
                    Violation(
                        "IMPLIED-ROW-INCOMPLETE",
                        f"{implied_id}: 缺 Ch5 §B.2 必填字段 {field_name!r}",
                    )
                )
        if not row.get("alternative_explanations"):
            report.violations.append(
                Violation("IMPLIED-NO-ALTERNATIVE", f"{implied_id}: 无替代解释（Ch5 §B.2）")
            )
        if row.get("feasible"):
            sid = str(row.get("solution_set_id") or "")
            groups[sid] = groups.get(sid, 0) + 1

    report.scanned["solution_sets"] = len(groups)
    for sid, count in sorted(groups.items()):
        if count < min_count:
            report.violations.append(
                Violation(
                    "IMPLIED-SINGLE-SOLUTION",
                    f"解集 {sid!r} 仅 {count} 组可行解（下限 {min_count}）—— "
                    "欠定方程必须展示多组解（Ch5 §B.1；下限由 "
                    f"{RULE_KEY_SOLUTION_SET_DISPLAY}.{RULE_KEY_MUST_SHOW_MULTIPLE} 派生）",
                )
            )
    return report


def _rule_binding_violations(root: Path) -> list[str]:
    """**规则↔代码机器绑定**：`rules/valuation-methods.yaml` 的声明必须与实现一致。

    | # | 判据 | 依据 |
    |---|---|---|
    | ① | 本模块读取的每个顶层键**真实存在** | `Ch11 §D.2`（参数只住 `rules/`） |
    | ② | `solution_set_display.default_count` / `max_count` 与代码默认值一致 | B18 / `§J.3` |
    | ③ | `solution_set_display.must_show_multiple` 与代码回落值一致 | `Ch5 §B.1`（"必须多组"） |
    | ④ | `assumption_grid.solver_ref` 指向**本模块**（改名即违例） | `§B.3` / `§I.2` |

    ★ ②③ 即主理人裁定 ③-3：**断言"回落值 == 真文件里的值"** ⇒ 让"规则改了、回落没改"变红。
    ★ **"缺键"本身即违例**（②③④ 一律先判"键在不在"，再判"值对不对"）：这四个键在真文件里
      **都存在** ⇒ 删键意味着该事实从规则面消失、代码却仍按回落值行事。写成"无可比对象
      故跳过"就是门禁**欠报**（`G-03`："跳过不是通过"）。
    ★ 规则文件不存在 → 返回空（另有 note 面，**不**当已核）。
    """
    from scripts._common import _cached_yaml

    path = root / VALUATION_METHODS_YAML
    if not path.exists():
        return []
    doc = _cached_yaml(path) or {}
    violations: list[str] = []

    for relpath, key in RULE_BOUND_ENTRIES:
        if key not in doc:
            violations.append(
                f"{relpath} 缺本模块实际读取的键 {key!r} —— 声明与实现脱节（Ch11 §D.2）"
            )

    node = doc.get(RULE_KEY_SOLUTION_SET_DISPLAY)
    if RULE_KEY_SOLUTION_SET_DISPLAY in doc and not isinstance(node, Mapping):
        violations.append(
            f"{VALUATION_METHODS_YAML}:: {RULE_KEY_SOLUTION_SET_DISPLAY} 形态非法（应为映射，"
            f"实为 {type(node).__name__}）—— 展示口径不可判定，不得静默跳过（G-03）"
        )
    elif isinstance(node, Mapping):
        # ★ **缺键 ⇒ 违例**（不是"无可比对象故跳过"）：真文件里三个键**都存在** ⇒ 删键等于
        #   "展示多少组"从规则面消失、而代码仍按回落值展示。若此处跳过，门禁即**欠报**
        #   （`G-03`："跳过不是通过"）。
        for sub_key, code_default, why in (
            (RULE_KEY_DEFAULT_COUNT, DEFAULT_DISPLAY_CAP, "B18：默认展示组数"),
            (RULE_KEY_MAX_COUNT, MAX_DISPLAY_CAP, "B18：展示硬上限"),
        ):
            if sub_key not in node:
                violations.append(
                    f"{VALUATION_METHODS_YAML}:: {RULE_KEY_SOLUTION_SET_DISPLAY}.{sub_key} 缺失 "
                    f"—— 缺键本身即违例（Ch11 §D.2）：{why}将静默退化为代码回落值 "
                    f"{code_default}（无从核对）"
                )
        if RULE_KEY_DEFAULT_COUNT in node:
            declared_default = node[RULE_KEY_DEFAULT_COUNT]
            if int(declared_default) != DEFAULT_DISPLAY_CAP:
                violations.append(
                    f"{VALUATION_METHODS_YAML}:: {RULE_KEY_SOLUTION_SET_DISPLAY}."
                    f"{RULE_KEY_DEFAULT_COUNT}={declared_default} 与代码默认值 "
                    f"{DEFAULT_DISPLAY_CAP} 不一致（B18；调用方应传 "
                    "load_solution_set_display(root).default_count）"
                )
        if RULE_KEY_MAX_COUNT in node:
            declared_max = node[RULE_KEY_MAX_COUNT]
            if int(declared_max) != MAX_DISPLAY_CAP:
                violations.append(
                    f"{VALUATION_METHODS_YAML}:: {RULE_KEY_SOLUTION_SET_DISPLAY}."
                    f"{RULE_KEY_MAX_COUNT}={declared_max} 与代码硬上限 "
                    f"{MAX_DISPLAY_CAP} 不一致（B18）"
                )
        if RULE_KEY_MUST_SHOW_MULTIPLE not in node:
            violations.append(
                f"{VALUATION_METHODS_YAML}:: {RULE_KEY_SOLUTION_SET_DISPLAY}."
                f"{RULE_KEY_MUST_SHOW_MULTIPLE} 缺失 —— 缺键本身即违例（Ch11 §D.2）："
                f"多解下限将退化为设计回落值 {DESIGN_MUST_SHOW_MULTIPLE}（非'已核'；"
                "下限由该语义键派生）"
            )
        elif bool(node[RULE_KEY_MUST_SHOW_MULTIPLE]) != DESIGN_MUST_SHOW_MULTIPLE:
            violations.append(
                f"{VALUATION_METHODS_YAML}:: {RULE_KEY_SOLUTION_SET_DISPLAY}."
                f"{RULE_KEY_MUST_SHOW_MULTIPLE}={node[RULE_KEY_MUST_SHOW_MULTIPLE]} 与代码回落值 "
                f"{DESIGN_MUST_SHOW_MULTIPLE} 不一致（Ch5 §B.1：欠定方程必须展示多组解）"
                " —— 回落值未跟随规则，属声明与实现脱节（Ch11 §D.2）"
            )

    grid = doc.get(RULE_KEY_ASSUMPTION_GRID)
    if RULE_KEY_ASSUMPTION_GRID in doc and not isinstance(grid, Mapping):
        violations.append(
            f"{VALUATION_METHODS_YAML}:: {RULE_KEY_ASSUMPTION_GRID} 形态非法（应为映射，实为 "
            f"{type(grid).__name__}）—— 假设网格归属不可判定，不得静默跳过（G-03）"
        )
    elif isinstance(grid, Mapping):
        expected = "scripts/pricelayer/solver.py"
        if RULE_KEY_SOLVER_REF not in grid:
            violations.append(
                f"{VALUATION_METHODS_YAML}:: {RULE_KEY_ASSUMPTION_GRID}.{RULE_KEY_SOLVER_REF} 缺失 "
                f"—— 缺键本身即违例（Ch11 §D.2）：无法核对假设网格是否仍归本模块 {expected!r}"
            )
        elif str(grid[RULE_KEY_SOLVER_REF]) != expected:
            violations.append(
                f"{VALUATION_METHODS_YAML}:: {RULE_KEY_ASSUMPTION_GRID}.{RULE_KEY_SOLVER_REF}="
                f"{grid[RULE_KEY_SOLVER_REF]!r} 未指向本模块 {expected!r} —— "
                "声明与实现脱节（Ch5 §B.3 / §I.2）"
            )
    return violations


def main(argv: Sequence[str] | None = None) -> int:
    """CLI：`python system/scripts/pricelayer/solver.py [code_root]`。"""
    from scripts._common import run_checker

    return run_checker("pricelayer_solver", check, argv)


if __name__ == "__main__":  # pragma: no cover - CLI 出口
    raise SystemExit(main())
