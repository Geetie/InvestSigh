"""`scripts/pricelayer/` —— 第五章**价格层**（`施工图 §2 阶段②`；设计锚点 `Ch5 §B~§F`）。

**一句话**（`Ch5 §0`）：本章是**价格层** —— 回答"当前价格隐含了什么假设、外部预期是什么、
我们独立判断是什么、价格变动怎么解释"，并向第七章输出"收益比较"的输入。

| 模块 | 职责 | 设计锚点 |
|---|---|---|
| `solver` | **反向求解**：固定 4 类解第 5 类，产出**解集 + 区间 + 替代解释** | `Ch5 §B.1/§B.2/§B.3/§B.4` |
| `valuation` | 估值计算 + 方法按 `model_class` 路由 + `DerivedValue` 追溯链 | `Ch5 §D.1/§D.2/§D.3/§D.6` |
| `order_guard` | 顺序约束 + **倒填检测四规则** + 反解不得回灌 baseline | `Ch5 §D.3/§D.4/§B.5` |
| `scenario_guard` | 情景口径一致性 + **`probability` 默认 `null`** + `scenario_method_status` | `Ch5 §D.6/§E.3/§E.4` |
| `history_guard` | AGIX 底稿特殊处理 + 非上市资产 + **历史外推检测** | `Ch5 §E.1/§E.2/§E.5` |
| `daily_explain` | 每日解释：行情**口径校验** + 三分类 + **因果链可达性** | `Ch5 §F.1~§F.5` |
| `step` | 对编排器的**接线接缝**（`StepHandler` 签名一致；step 5 / 6） | `Ch9 §3.5` 阶段④/⑤ |

★ **本包三处不许打折的约束**（批次 13-B 任务卡逐字）：

1. `solver` 的 `P = f(g, m, r, k, T)` 是**欠定方程**（`Ch5 §B.1`）⇒ **必须产出多组解**
   （`min_solutions=2`），否则某一解会被误当"市场的唯一真相"。
2. `order_guard` 的**倒填四规则**（`Ch5 §D.4`）+ `§B.5`：`source=implied_solution` 的假设
   写入 `baselines.driver_model` **必须被拒**；反解输出**只允许**写 `implied_requirements` 或 `gap`。
3. `scenario_guard` 的 `probability` **默认 `null`**（`Ch5 §D.6` / `§E.4`）：**不得**给个默认概率糊过去。

★ **模型不做算术、程序不做假设**（`Ch5 §B.3`）：候选假设（g/m/r/k/T 的取值与组合方向、
替代解释、**假设空间边界**）由**模型**给；固定 4 类解第 5 类、正算与迭代求解由**程序**做。
故本包的入参是"候选假设组合"，出参是"解集 + 区间 + 替代解释"——本包**不生成任何假设**。

★ **惰性导入**（`CONVENTIONS.md §三 P-03` / PEP 562）：包 `__init__` 不在导入期急切拉起子模块
  与 pydantic（`DerivedValue` / `ImpliedRequirement` ≈0.3s/次）。取子模块用
  `from scripts.pricelayer import solver` 或 `scripts.pricelayer.solver`（首次触碰才 `import`）。

★ **异常族的唯一真源**（`G-06`）：本模块只放本层**自有**的拒绝类异常；
  时间顺序类异常 `OrderViolation` **复用** `scripts.compute.contract`（确定性计算层的既有出口），
  经 `order_violation()` **惰性**取用 —— 不新造第二套顺序异常（那会变成第二条校验路径）。
"""

from __future__ import annotations

import importlib
from typing import Any

_SUBMODULES = (
    "solver",
    "valuation",
    "order_guard",
    "scenario_guard",
    "history_guard",
    "daily_explain",
    "step",
)

__all__ = [
    *_SUBMODULES,
    "PriceLayerError",
    "ScenarioMismatch",
    "ScenarioMethodPending",
    "ProbabilityWithoutBasis",
    "HistoricalExtrapolation",
    "MoatPriceContamination",
    "QuoteCaliberViolation",
    "SingleSolutionError",
    "order_violation",
]


class PriceLayerError(Exception):
    """价格层拒绝类异常的基类。

    ★ 与 `scripts.compute.contract` 的分工：缺口类（`MissingInput` / `UndefinedComputation`）
      与顺序类（`OrderViolation`）**复用**计算层的既有权威出口（`G-06` 唯一真源）；
      本基类只承载**价格层特有**的拒绝（情景不一致 / 历史外推 / 价格污染 / 行情口径 /
      解集退化成单解）。这些在 `Ch5 §E.3` / `§E.2` / `§F.4` / `§F.1` / `§B.1` 各有逐字依据。
    """


class ScenarioMismatch(PriceLayerError):
    """情景口径不一致 → **拒绝**生成相对判断（`Ch5 §E.3` / `N5.4-08`）。

    `Ch5 §E.3` 逐字：「**不能比较个股乐观情景与基准悲观情景**」。
    """

    def __init__(self, stock_tag: str, benchmark_tag: str) -> None:
        super().__init__(
            f"情景标签不一致：个股={stock_tag!r} / 基准={benchmark_tag!r} —— "
            "口径不同不得生成相对判断（Ch5 §E.3 / N5.4-08）"
        )
        self.stock_tag = stock_tag
        self.benchmark_tag = benchmark_tag


class ScenarioMethodPending(PriceLayerError):
    """`scenario_method_status = pending` → **阻塞**相对判断生成（`Ch5 §E.4` / `N5.4-07`）。

    `Ch5 §E.4` 逐字：`pending` 时 `assert_scenario_match` 无法建立一致口径
    → **阻塞相对判断生成**（第七章前置门收不到可用的 `benchmark_forecast`，输出"待判断"而非建议）。
    """


class ProbabilityWithoutBasis(PriceLayerError):
    """`probability` 非空却**无依据** → 拒绝（`Ch5 §J9` / `00_待拍板项清单` B11）。

    B11 逐字：`probability` 「须为 `DerivedValue` 且标注来源；否则默认 `null`（**不是 50/50**）」。
    """


class HistoricalExtrapolation(PriceLayerError):
    """用历史收益率外推未来 → **拒绝**（`Ch5 §E.2` / `N5.4-04`）。

    `Ch5 §E.2` 逐字：「预期收益必须来自 forward assumptions；历史仅作诊断」。
    """


class MoatPriceContamination(PriceLayerError):
    """价格派生值试图写入护城河/基本面结论 → **拒绝**（`Ch5 §F.4`，承 `C45-5`）。

    `Ch5 §F.4` 逐字：「价格涨跌**只触发复查**，**不写** `baselines.moat` / 基本面结论」；
    与第四章 `§F.3` 断言 A3 **共用**断言面（schema 的 `MoatWriter` 写路径白名单）。
    """


class QuoteCaliberViolation(PriceLayerError):
    """行情**口径校验未通过**（`Ch5 §F.1` / `N5.5-01`）。

    `Ch5 §F.1` 逐字：「校验未通过的行情**不用于**解释与收益计算」。
    """


class SingleSolutionError(PriceLayerError):
    """解集退化为**单解** → 拒绝呈现（`Ch5 §B.1`）。

    `Ch5 §B.1` 逐字：`P = f(g, m, r, k, T)` 是**欠定方程**——一个 `P` 对应**无穷多组**解。
    「故**必须展示多组解**，否则会把某一解误当'市场的唯一真相'」。
    """


def order_violation(message: str) -> Exception:
    """惰性构造**唯一真源**的 `OrderViolation`（`scripts/compute/contract.py`；`G-06`）。

    ★ 为什么惰性：`scripts.compute.contract` 在模块级导入 `schema.models`（pydantic，≈0.3s）。
      守卫（`P-03` / `P-05`）不得在模块级急切付这笔成本，故本包一律经本函数按需取用。
    """
    from scripts.compute.contract import OrderViolation

    return OrderViolation(message)


def __getattr__(name: str) -> Any:
    """PEP 562：子模块按需导入（首次访问才付出 pydantic / yaml 的导入成本）。"""
    if name in _SUBMODULES:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals()) + list(_SUBMODULES))
