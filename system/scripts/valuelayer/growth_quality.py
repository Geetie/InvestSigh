"""`growth_quality.py` —— 增长质量 / ROIIC / **增长的代价五类** + **收入增速 denylist 守卫**（`Ch4 §D`）。

## 设计锚点（逐字）

`Ch4 §D.3` 伪码：

```python
def assess(driver, fin):
    roiic = compute_roiic(fin.incremental_nopat, fin.incremental_invested_capital)  # 走 compute/
    if roiic < fin.wacc:
        return GrowthQuality("low", flag="value_destructive_growth")
    ...  # 现金转化率/营运资金/融资依赖分项
```

`Ch4 §D.3` 的五项代价 → 财务科目映射（字段名逐字）：

| 代价 | 财务科目 | 字段 |
|---|---|---|
| 降价 | 收入（单价↓）/毛利率 | `price_discount` |
| 增加资本开支 | 现金流量表投资活动 / CapEx | `capex_requirement` |
| 库存 | 资产负债表存货 | `inventory_buildup` |
| 应收 | 资产负债表应收账款 | `receivables_buildup` |
| 融资 | 筹资活动 / 净负债 | `financing_need` |

`Ch4 §D.3` 末段（`N4.1-14`）：

> **收入增速不得作投资回报代理**：决策/估值只引用 `ROIC/ROIIC/每股 FCF/EVA`
> （`scripts/valuelayer/growth_quality.py` 输出的**替代指标集**），**收入增速字段设有 denylist 守卫**。

## ★ `G-06`：算术一行都不在本模块

`ROIIC = 增量 NOPAT / 增量投入资本` 与"四项分项 → 分档"的**全部算术**住在
`scripts/compute/growth.py`（`Ch9 §3.4.4` 明确规定"算术由程序层承担，模型不口算"）。
本模块**只做三件事**：① 把驱动/财务对象**翻译**成该层的入参；
② 校验五项代价字段是否交代齐全；③ 守"收入增速不得当回报代理"这条线。

★ 刻意**不**把四项压成单一数值（`Ch2 §B.2 P-01`：不得增设最低超额收益门槛）——
  `scripts/compute/growth.py::assess_growth_quality` 返回的就是**分档 + 分项明细**。

## ★ 「denylist 守卫」的实现取舍（**照 `R-06` 做，不照字面做**）

**类型约束（真防护）**：`ReturnProxy` 是一个**只含四类允许值**的枚举；回报代理的取值
只能经 `require_return_proxy()` 进入系统，未列出的名字**默认拒绝**（`R-06 ⑤` allowlist）。
这是**穷尽**的：不存在"换一种写法绕过"的形态，因为判据是"名字是否在允许集合内"，
而允许集合是**封闭**的。

**AST 检查这一半本批次未做，且这是刻意的**（见下方 `no_ast_keyword_pass()` 的 docstring）：
`Ch4 §J.4 J7` 对它的建议是"AST 检查"，但任何能写出来的 AST 形式都只能是
"**文本里出现了哪些名字**"（`R-06 ①` 明文禁止的关键词/名单式判据），而不可穷尽的形式
**不得作为防护**（`R-06 ③`）。按 `R-06 ④`，此类检查若要保留**必须在措辞上剥离防护语义**；
故本批次**不作**这种检查，并把该缺口如实登记在报告里 —— 而不是写一个永远绿的"守卫"充数。
"""

from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts._common import CheckReport, Violation, run_checker
from scripts.valuelayer import _rules

#: 五项"增长的代价"字段名（`Ch4 §D.3` 表逐字；顺序同表）。
COST_OF_GROWTH_FIELDS: tuple[str, ...] = (
    "price_discount",
    "capex_requirement",
    "inventory_buildup",
    "receivables_buildup",
    "financing_need",
)

#: `Ch4 §D.3` 伪码逐字：`ROIIC < WACC` 时的标志。
VALUE_DESTRUCTIVE_FLAG = "value_destructive_growth"

#: `Ch4 §D.3` 末段逐字的**替代指标集**（决策/估值只允许引用这四类）。
RETURN_PROXY_METRICS: frozenset[str] = frozenset(
    {"roic", "roiic", "fcf_per_share", "eva"}
)

#: `compute_roiic()` 的 `operands`：取**输入字段名**（`Ch9 §2.4.3`：落库数字必须能追到 operand）。
#:
#: ★ 为什么不能传空表：`scripts/compute/contract.make_derived` 会以 `CaliberViolation` 拒绝
#:   "追不到 operand 的落库数字"，那是**契约被破坏**（不是缺口）⇒ 必须响亮失败。
#:   本常量使"ROIIC 追得到哪两个输入"成为一处**可断言**的事实，而不是散在调用点上的字面量。
ROIIC_OPERANDS: tuple[str, ...] = ("incremental_nopat", "incremental_invested_capital")


class ReturnProxyNotAllowed(RuntimeError):
    """把不在替代指标集里的东西当投资回报代理（`Ch4 §D.3` / `N4.1-14`）。

    ★ 判据是 **allowlist（默认拒绝）**：任何不在 `RETURN_PROXY_METRICS` 里的名字
      都落进这里，**包括** `revenue_growth` / `revenue_cagr` / `top_line_growth` 以及
      尚未有人想出来的写法（`R-06 ⑤`：白名单对未列出的形式默认拒绝，故可穷尽）。
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"ReturnProxyNotAllowed: {name!r} 不在替代指标集 {sorted(RETURN_PROXY_METRICS)} 内 —— "
            "Ch4 §D.3/N4.1-14：收入增速不得作投资回报代理；回报代理只允许 ROIC/ROIIC/每股 FCF/EVA"
        )


def require_return_proxy(name: str) -> str:
    """回报代理的唯一**准入**入口（`Ch4 §D.3`；`R-06 ⑤` allowlist）。

    返回入参本身（便于内联），不合格 ⇒ `ReturnProxyNotAllowed`。
    """
    if name not in RETURN_PROXY_METRICS:
        raise ReturnProxyNotAllowed(name)
    return name


def no_ast_keyword_pass() -> str:
    """**本批次不做 AST 关键词扫描** —— 返回这句声明，供调用方/测试显式读到。

    ★ 为什么把它写成函数而不是删掉（`G-03`："无被检对象不得当成已验证"）：
      留下一个**可被断言到的**声明，才能让"这里没有 AST 防护"成为一个**可观测事实**，
      而不是靠读者猜。`tests/valuelayer/` 有一条用例断言本函数存在且返回非空 ——
      将来若真做了 AST 检查，那条用例会红，从而强制更新登记（与 `criterion_counterexamples`
      里 `ineffective` 条目的机理同源）。

    ★ 为什么不做（逐条对齐 `R-06`）：
      ① 建议来源 `Ch4 §J.4 J7` 写的是"AST 检查"，但它属**技术待定项的建议**，
         而 `R-06 ①` 是**需求方铁律**（"禁止关键词/名单类判据"）—— 铁律优先；
      ② 任何可写出的 AST 形式都是"看标识符名/字符串字面量里出现了哪些词"，
         属枚举式判据，**不可穷尽**（换个变量名即绕过）；
      ③ `R-06 ③`：不可穷尽的判据**不得作为防护**；④：只能作 aux lint 且须剥离防护语义 ⇒
         那它就不能被引用为"已验证"，做了反而制造**假信心**；
      ⑥ 首选运行时效果断言 —— 本模块改以 `require_return_proxy()` 的**运行时可判定**准入
         承担防护（默认拒绝、可穷尽）。
    """
    return (
        "NO_AST_KEYWORD_PASS: 收入增速的 AST 关键词扫描本批次未做（R-06 ①/③：关键词式判据"
        "不可穷尽，不得作防护）；防护由 require_return_proxy() 的 allowlist 准入承担"
    )


class TooManyDrivers(RuntimeError):
    """某业务的**关键驱动**超过 `Ch4 §D.2` 的上限（`rules/baseline.yaml` 参数化）。"""

    def __init__(self, business_id: str, got: int, limit: int) -> None:
        self.business_id = business_id
        self.got = got
        self.limit = limit
        super().__init__(
            f"TooManyDrivers: 业务 {business_id!r} 有 {got} 个 primary 驱动 > 上限 {limit} "
            "（Ch4 §D.2：校验器**拒绝直接入库**，须先分级 primary + secondary_watchlist，"
            "或按 importance_class 取 top-N、其余归档）"
        )


class CostOfGrowthIncomplete(RuntimeError):
    """五项"增长的代价"未交代齐全（`Ch4 §D.3` 表）。"""

    def __init__(self, driver_id: str, missing: Sequence[str]) -> None:
        self.driver_id = driver_id
        self.missing = tuple(missing)
        super().__init__(
            f"CostOfGrowthIncomplete: 驱动 {driver_id!r} 缺代价字段 {list(self.missing)} —— "
            "Ch4 §D.3 要求五类代价**各有字段 + 映射**（缺项不等于'没有这项代价'）"
        )


# ───────────────────────────────── 入参翻译 ─────────────────────────────────

@dataclass(frozen=True)
class Financials:
    """`assess(driver, fin)` 的 `fin`（`Ch4 §D.3` 伪码用到的全部财务量）。

    字段名逐字取伪码：`incremental_nopat` / `incremental_invested_capital` / `wacc`，
    其余三项对应 §D.3 "由四项分项判定" 里的另外三项。
    """

    incremental_nopat: Decimal
    incremental_invested_capital: Decimal
    wacc: Decimal
    cash_conversion: Decimal
    working_capital_change: Decimal
    financing_dependence: str


def _field(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def cost_of_growth_gaps(driver: Any) -> list[str]:
    """返回五项代价里**未交代**的字段名（`Ch4 §D.3`）。空 = 齐备。

    ★ "未交代"的判据是**键缺失或为空 mapping**，不是"值为 0" ——
      降价/资本开支真的为 0 与"根本没研究过"是两件事（`Ch4 §G.4` 同一条思路：
      必填项非空 ≠ 值好看）。
    """
    block = _field(driver, "cost_of_growth")
    if block is None:
        return list(COST_OF_GROWTH_FIELDS)
    out: list[str] = []
    for name in COST_OF_GROWTH_FIELDS:
        value = _field(block, name)
        if value is None or (isinstance(value, Mapping) and not value):
            out.append(name)
    return out


def validate_cost_of_growth(driver: Any) -> None:
    """五项代价齐备性校验（`Ch4 §D.3`）。缺项 ⇒ `CostOfGrowthIncomplete`。"""
    missing = cost_of_growth_gaps(driver)
    if missing:
        raise CostOfGrowthIncomplete(str(_field(driver, "driver_id") or ""), missing)


def driver_tier(driver: Any) -> str:
    """驱动的分级（`Ch4 §D.2`："按 `importance_class` 取 top-N，其余归档"）。

    ★ 为什么由 `importance_class` 派生而不是新增一个 `tier` 字段：
      `Ch4 §D.1` 的 driver schema 块里**没有** `tier`；§D.2 逐字把它写作一个**动作**
      （"须先分级：`primary_drivers(≤5)` + `secondary_watchlist`（或按 `importance_class`
      取 top-N，其余归档）"）。凭空加字段会与"一个概念一个字段名"冲突
      （`Ch2 §C.2 R-15 ③`）。`schema/models.py::DriverModel` 的 docstring 亦已登记同一取舍。
    """
    return "primary" if str(_field(driver, "importance_class") or "") == "high" else "secondary_watchlist"


def validate_driver_count(business_id: str, drivers: Sequence[Any], cfg: Mapping[str, Any]) -> None:
    """`Ch4 §D.2` 伪码逐条落地（上限**只从 `rules/baseline.yaml` 读**）。

    ```python
    def validate_driver_count(business, drivers, cfg):
        primary = [d for d in drivers if d.tier == "primary"]
        if len(primary) > cfg.max_primary_drivers_per_business:
            raise TooManyDrivers(len(primary), cfg.max_primary_drivers_per_business)
    ```

    ★ 超限**拒绝直接入库**（不是告警）—— §D.2 明写"校验器**拒绝直接入库**"。
    """
    limit = cfg.get("max_primary_drivers_per_business")
    if limit is None:
        raise _rules.MissingRuleInput(
            f"{_rules.BASELINE_RELPATH} 缺 max_primary_drivers_per_business —— "
            "Ch4 §D.2 把该上限定义为规则文件里的可配项；代码不内置默认值"
        )
    primary = [d for d in drivers if driver_tier(d) == "primary"]
    if len(primary) > int(limit):
        raise TooManyDrivers(business_id, len(primary), int(limit))


# ───────────────────────────────── assess ─────────────────────────────────

@dataclass(frozen=True)
class GrowthAssessment:
    """`assess()` 的结果（**分档 + 分项明细 + 替代指标集**，不是单一分数）。"""

    driver_id: str
    quality: Any                      # scripts.compute.growth.GrowthQuality
    alternative_metrics: Mapping[str, str]
    cost_of_growth: Mapping[str, Any]
    gaps: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def flags(self) -> tuple[str, ...]:
        return tuple(getattr(self.quality, "flags", ()) or ())


def alternative_metric_set(roiic: Decimal, wacc: Decimal) -> dict[str, str]:
    """`Ch4 §D.3` 的**替代指标集**（决策/估值只引用它，不引用收入增速）。

    返回的是"指标名 → 口径说明"，**不是**打分表 —— 本函数不产出任何排序或分数
    （`纪律 7` / `P-09`）。四项的名字全部来自 `RETURN_PROXY_METRICS`（`require_return_proxy()`
    逐个准入，保证"输出的替代指标集"本身不可能夹带非许可项）。
    """
    out = {
        "roiic": f"增量 NOPAT / 增量投入资本（本次 = {roiic}，对照 WACC = {wacc}）",
        "roic": "税后经营利润 / 投入资本（走 scripts/compute/）",
        "fcf_per_share": "每股自由现金流（走 scripts/compute/shares）",
        "eva": "经济增加值（走 scripts/compute/）",
    }
    for name in out:
        require_return_proxy(name)     # ★ allowlist 准入：输出侧也走同一道闸
    return out


def assess(driver: Any, fin: Financials) -> GrowthAssessment:
    """`Ch4 §D.3` 的伪码逐条落地（算术**全部**走 `scripts/compute/`）。

    与伪码的唯一差别（**刻意**，且是"用实现而非例外"表达同一条规则）：
    伪码 `if roiic < fin.wacc: return GrowthQuality("low", flag=...)` 是一条**短路返回**；
    本实现把它交给 `scripts/compute/growth.py::assess_growth_quality` 的**同一硬规则**
    （该函数 docstring 逐字写着"ROIIC 低于资金成本（毁灭价值）时**唯一下档为 `low`**"）。
    这样"分档规则"只有一处真源（`G-06`），而不是"compute 一套 + valuelayer 又一套"。

    - `incremental_invested_capital == 0` ⇒ `compute` 层抛 `UndefinedComputation`
      ⇒ 本函数把它**如实记进 `gaps`**（`Ch4 §G.3`："材料不足记录缺口"，不猜一个数）。
    - 五项代价缺项 ⇒ 记进 `gaps`（不阻断分档：§D.3 的分档只由四项分项决定）。
    """
    from scripts.compute.contract import UndefinedComputation
    from scripts.compute.growth import assess_growth_quality, compute_roiic

    driver_id = str(_field(driver, "driver_id") or "")
    gaps: list[str] = []
    notes: list[str] = []

    roiic: Decimal | None = None
    try:
        roiic = compute_roiic(
            fin.incremental_nopat,
            fin.incremental_invested_capital,
            subject=driver_id,
            operands=ROIIC_OPERANDS,
        ).value
    except UndefinedComputation as exc:
        gaps.append(f"roiic:{exc}")

    missing_cost = cost_of_growth_gaps(driver)
    if missing_cost:
        gaps.append(f"cost_of_growth:{','.join(missing_cost)}")

    if roiic is None:
        # ★ 无 ROIIC 就**不下档**（`G-03`）：返回一个显式的"缺口态"，
        #   而不是把缺输入当成 low（那会把"没研究"冒充成"已判负向"）。
        return GrowthAssessment(
            driver_id=driver_id,
            quality=None,
            alternative_metrics={},
            cost_of_growth={
                name: _field(_field(driver, "cost_of_growth") or {}, name)
                for name in COST_OF_GROWTH_FIELDS
            },
            gaps=tuple(gaps),
            notes=(
                "ROIIC 无法计算（分母为 0 / 输入缺失）⇒ 本次**不下增长质量档**，"
                "如实记 gaps（Ch4 §G.3；G-03：空 ≠ 已验证）",
            ),
        )

    quality = assess_growth_quality(
        roiic=roiic,
        wacc=fin.wacc,
        cash_conversion=fin.cash_conversion,
        working_capital_change=fin.working_capital_change,
        financing_dependence=fin.financing_dependence,
        subject=driver_id,
    )
    if missing_cost:
        notes.append(
            f"五项代价缺 {missing_cost} —— 分档（§D.3 只由四项分项决定）不受影响，"
            "但缺项必须显式可见（G-03）"
        )
    return GrowthAssessment(
        driver_id=driver_id,
        quality=quality,
        alternative_metrics=alternative_metric_set(roiic, fin.wacc),
        cost_of_growth={
            name: _field(_field(driver, "cost_of_growth") or {}, name)
            for name in COST_OF_GROWTH_FIELDS
        },
        gaps=tuple(gaps),
        notes=tuple(notes),
    )


# ───────────────────────────────── 门禁入口 ─────────────────────────────────

def check(root: Path) -> CheckReport:
    """对真源 `facts/drivers.jsonl` 做 **§D.2 驱动上限** + **§D.3 代价五类齐备** 检查。

    本入口**不**计算增长质量分档（那需要 WACC / 现金转化率等财务输入，
    而它们不在 `drivers.jsonl` 里 —— 硬算只会产出"输入缺失"的假档位）。
    分档的入口是 `assess()`，由调用方把财务量喂进去。

    - 真源**缺失** ⇒ `FileNotFoundError`（`exit 2`）；**存在但为空** ⇒ `NO_DRIVERS` note + `exit 0`。
    """
    from schema.store import read_records, truth_source_status

    report = CheckReport(checker="valuelayer_growth_quality")
    status = truth_source_status(root, "drivers")
    if status == "missing":
        raise FileNotFoundError("缺少真源 facts/drivers.jsonl（Ch4 §D.1 新表，属 22 表之一）")
    drivers = read_records(root, "drivers")
    report.scanned["drivers"] = len(drivers)
    if not drivers:
        report.notes.append(
            "NO_DRIVERS: facts/drivers.jsonl 存在但为空 —— 无被检对象（真空成立，不是'已验证'，G-03）"
        )
        return report

    cfg = _rules.baseline_cfg(root)
    by_business: dict[str, list[Any]] = {}
    for d in drivers:
        by_business.setdefault(str(d.get("business_id") or ""), []).append(d)
        missing = cost_of_growth_gaps(d)
        if missing:
            report.violations.append(
                Violation(
                    "Ch4-D3",
                    f"{d.get('driver_id')}: 五项代价缺 {missing}（Ch4 §D.3 表要求各有字段 + 映射）",
                    "facts/drivers.jsonl",
                )
            )
        if not (d.get("source_class") in {
            "demand_expansion", "share", "price", "product_mix",
            "unit_usage", "penetration", "new_business", "mixed",
        }):
            report.violations.append(
                Violation(
                    "Ch4-D1",
                    f"{d.get('driver_id')}: source_class={d.get('source_class')!r} 不在 "
                    "§D.1 的 7 类 + mixed 兜底内（N4.1-03：每驱动有来源标签，可统计分布）",
                    "facts/drivers.jsonl",
                )
            )
    for business_id, rows in sorted(by_business.items()):
        try:
            validate_driver_count(business_id, rows, cfg)
        except TooManyDrivers as exc:
            report.violations.append(
                Violation("Ch4-D2", f"{exc}", "facts/drivers.jsonl")
            )
    report.scanned["businesses_with_drivers"] = len(by_business)
    report.scanned["primary_drivers"] = sum(1 for d in drivers if driver_tier(d) == "primary")
    return report


if __name__ == "__main__":
    import sys

    sys.exit(run_checker("valuelayer_growth_quality.py", check))
