"""`tests/decision/` 的**构造器**：真 `DerivedValue` 底稿 + 可解释预测 + 决策输入。

单独成模块（而非塞进 `conftest.py`）的原因：`conftest` 在多测试目录间会**重名冲突**
（pytest 的 prepend 导入模式给每个 `conftest.py` 取同名模块），而本模块名 `decision_builders`
在 `tests/` 下唯一，可被本目录任一测试 `from decision_builders import ...` 直接引用。

★ **真 `DerivedValue`，不是裸数字**（`Ch7 §D.2` / `N7.3-07`）：所有预测的 `worksheet`
  一律经 `scripts.compute.contract.make_derived` 构造，**必带** `formula` + `operands` +
  `method_version` —— 测的是"真的能追到底稿"，不是伪造的数值容器。
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

SYSTEM_ROOT = Path(__file__).resolve().parents[2]      # .../InvestSigh/system
if str(SYSTEM_ROOT) not in sys.path:
    sys.path.insert(0, str(SYSTEM_ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DEMO_STOCK_PRICES = FIXTURES / "demo_stock_prices.jsonl"
AGIX_PRICES = SYSTEM_ROOT / "tests" / "compute" / "fixtures" / "agix_prices.jsonl"

from scripts.compute.contract import make_derived  # noqa: E402
from scripts.decision.gate import (  # noqa: E402
    ExplainableForecast,
    RecommendationInput,
    ResearchBaseline,
    ReturnValue,
)
from schema.models import DerivedValue  # noqa: E402


def make_worksheet(value: str, *, subject: str = "co-demo") -> DerivedValue:
    """构造**真实** `DerivedValue`（`formula` + `operands` + `method_version` 齐备）。

    以"区间总回报"形态给出，`value` 用字符串传入（`Decimal`，避免浮点误差）。
    """
    return make_derived(
        f"dv-total_return-{subject}-compute-v1",
        Decimal(value),
        f"total_return(2026-04-01..2026-09-15) [{subject}]",
        [f"{subject}:begin_close", f"{subject}:end_close"],
    )


def make_forecast(
    low: str,
    high: str | None = None,
    *,
    horizon: str = "2q",
    subject: str = "co-demo",
    drivers: tuple[str, ...] = ("driver:dc_revenue_growth",),
    worksheet: object | None = None,
) -> ExplainableForecast:
    """构造可解释预测；`high` 省略 → 点估。`worksheet` 显式给定时原样使用（供注入测试）。

    ★★ **缺省驱动**（2026-09-17 冷启动实测后更正）：原缺省为
      `("driver:market_price_total_return",)` —— 那是**已实现区间总回报**，正是
      `Ch2 §B.2` **P-08** 逐字禁止的"依据 `past_return` 的收益预测"。

      ★ 后果（这才是本仓该记住的教训）：**整套决策测试曾靠这个缺省值保持全绿** ——
      即"被禁的形态就是测试的默认前提"。新增 P-08 运行时门后，17 条用例同时变红，
      **恰是这条缺陷从未被任何判据覆盖过的证据**（不是新门太严）。

      ⇒ 缺省改为**前向**驱动名（`driver:dc_revenue_growth`，`Ch4 §H.2` 的增长驱动形态）。
      本目录下测的是 **R1–R8 的机制**，前提应是"有一个合法的前向预测"；
      "预测依据是后向值"这一情形的用例**单独**写在 `tests/decision/test_p08_realized_return.py`
      （`G-05`：正例与反例分开，缺一则该门的存在性不可判）。
    """
    hi = low if high is None else high
    ws = worksheet if worksheet is not None else make_worksheet(
        ((Decimal(low) + Decimal(hi)) / 2).__str__(), subject=subject
    )
    return ExplainableForecast(
        drivers=drivers,
        horizon=horizon,
        return_range=ReturnValue(low=Decimal(low), high=Decimal(hi)),
        worksheet=ws,
        method_version="compute-v1",
    )


def make_baseline(
    *,
    depth: str = "baseline_done",
    complete: bool = True,
    company_id: str = "co-demo",
) -> ResearchBaseline:
    """构造研究基线（默认已达 `baseline_done` 且齐备 → 过门）。"""
    return ResearchBaseline(company_id=company_id, research_depth=depth, baseline_complete=complete)


def make_input(
    *,
    stock: ExplainableForecast,
    benchmark: ExplainableForecast,
    baseline: ResearchBaseline | None = None,
    own_evidence: tuple[str, ...] = ("claim:co-demo:market",),
    company_id: str = "co-demo",
) -> RecommendationInput:
    """构造 `RecommendationInput`（**自身**基线 + 自身/基准预测 + 自身证据）。"""
    return RecommendationInput(
        company_id=company_id,
        baseline=baseline or make_baseline(company_id=company_id),
        stock_forecast=stock,
        benchmark_forecast=benchmark,
        own_evidence=own_evidence,
    )


__all__ = [
    "AGIX_PRICES",
    "DEMO_STOCK_PRICES",
    "FIXTURES",
    "SYSTEM_ROOT",
    "make_baseline",
    "make_forecast",
    "make_input",
    "make_worksheet",
]
