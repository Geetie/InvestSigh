"""`P-08` 运行时门：**已实现收益不得充当收益预测**（`Ch2 §B.2`）。

★ 为什么单开一个文件（而不是塞进 `test_rules.py`）：

  本目录的其余用例测的是 **R1–R8 的机制**，其前提是"有一个**合法前向**预测"。
  本文件测的是**该前提被破坏时**的行为 —— 前提不同，夹具不同，混在一起会让
  "缺省驱动"到底该是前向还是后向变得含糊（正是 `decision_builders.make_forecast`
  原先缺省写成后向值、从而让整套测试**靠被禁形态保持全绿**的那个坑）。

★ 判据两半（本仓铁律 16）：
  - **运行时**：`decide()` 里 R4 之后、R2 之前的 P-08 门（本文件）；
  - **产出侧**：`build_recommendation` 的 `FalsifiersMissing`（`test_persistence.py`）。
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from decision_builders import make_forecast, make_input

from scripts.decision.gate import (
    ExplainableForecast,
    JudgmentChange,
    RecommendationInput,
    ResearchBaseline,
    ReturnValue,
)
from scripts.decision.rules import (
    REALIZED_RETURN_BASIS_IDS,
    realized_return_basis_offenders,
    realized_return_drivers,
)
from scripts.decision.rules import decide

REALIZED = "sec-nvda-2026-08-03..2026-09-16:market_price_total_return"
"""★ **逐字取自真源**：`scripts/decision/run_decide.py::_forecast` 产出的驱动串形态
（`f"{subject}:market_price_total_return"`，`subject` 即 `<security>-<begin>..<finish>`）。
用一个**真实发生过**的串当反例输入，而不是编一个好认的假串。"""

FORWARD = "driver:dc_revenue_growth"
"""前向驱动名（`Ch4 §H.2` 的增长驱动形态）—— 正例输入。"""


def _forecast(low: str, high: str, driver: str) -> ExplainableForecast:
    """可解释预测：真 `DerivedValue` 底稿 + 指定驱动串（其余字段取合法值）。"""
    return make_forecast(low, high, drivers=(driver,))


def _input(*, stock_driver: str, bench_driver: str) -> RecommendationInput:
    return RecommendationInput(
        company_id="company-nvidia",
        baseline=ResearchBaseline(
            company_id="company-nvidia", research_depth="tracking", baseline_complete=True
        ),
        stock_forecast=_forecast("0.10", "0.12", stock_driver),
        benchmark_forecast=_forecast("0.05", "0.06", bench_driver),
        own_evidence=("claim:x",),
    )


# ─────────────────────────── 谓词的区分力（词元 vs 子串） ───────────────────────────

@pytest.mark.parametrize(
    ("token", "expected"),
    [
        (REALIZED, True),                       # ★ 真源既有形态
        ("nvda:market_price_total_return", True),
        ("past_return", True),                  # `P-08` 逐字用词
        ("NVDA:Past-Return", True),              # 大小写 / 分隔符归一
        ("trailing_return", True),
        ("historical_return", True),
        ("realized_return", True),
        # ── 以下**不得**命中：若命中，说明判据退化成了"含 return 就算" ──
        ("driver:dc_revenue_growth", False),
        ("driver:guidance_revision", False),
        ("market_price", False),                # 只差一半 ⇒ `_` 边界不成立
        ("dc_revenue_total", False),
        ("returning_customer_growth", False),   # 含 `return` 但不同物
    ],
)
def test_basis_token_discrimination(token: str, expected: bool) -> None:
    """判据是**词元/后缀**级，不是子串级（`R-06` ①；本仓已栽过 `unadjusted` ⊃ `adjusted`）。"""
    hit = realized_return_drivers(_forecast("0.10", "0.12", token))
    assert bool(hit) is expected, f"{token!r} → {hit}"


def test_basis_ids_closed_set_covers_the_canonical_name() -> None:
    """元断言：`P-08` 逐字用词 `past_return` **必须**在闭集里（防闭集漂移掉规范名）。"""
    assert "past_return" in REALIZED_RETURN_BASIS_IDS
    assert REALIZED_RETURN_BASIS_IDS, "闭集不得为空 —— 否则本门无被检对象（G-03）"


def test_offenders_scan_both_sides() -> None:
    """**两侧都查**：只拦个股侧会让"基准侧是后视值"的相对比较继续成立。"""
    only_bench = _input(stock_driver=FORWARD, bench_driver=REALIZED)
    assert realized_return_basis_offenders(only_bench) == (REALIZED,)
    only_stock = _input(stock_driver=REALIZED, bench_driver=FORWARD)
    assert realized_return_basis_offenders(only_stock) == (REALIZED,)
    assert realized_return_basis_offenders(_input(stock_driver=FORWARD, bench_driver=FORWARD)) == ()


# ─────────────────────────── 门在 `decide()` 上的行为 ───────────────────────────

@pytest.mark.parametrize("side", ["stock", "benchmark"])
def test_realized_return_never_yields_buy_or_sell(side: str) -> None:
    """★ 拿已实现收益 ⇒ **必得 `pending`**，且**两侧任一侧**后视都拦（R1 与 R2 一起拦）。"""
    inp = _input(
        stock_driver=REALIZED if side == "stock" else FORWARD,
        bench_driver=REALIZED if side == "benchmark" else FORWARD,
    )
    d = decide(inp, JudgmentChange(fact_set_changed=True))
    assert d is not None
    assert d.action == "pending", d.action
    assert d.status == "uncertain"
    assert d.is_new_signal is False, "P-08 门产出的建议**不得**是新交易信号（G1-02①）"
    assert "realized_return_not_a_forecast" in d.gaps, d.gaps
    assert REALIZED in d.change_reason, "被拦的原因必须落进 change_reason 以便复核"


def test_forward_basis_still_reaches_buy() -> None:
    """★ **反向对照**（`G-05`）：换成前向驱动 ⇒ 门**不得**误伤，R1 仍能出 `buy`。

    没有这一条，上一条会被"门把所有情况都拦成 pending"满足（判据退化为恒真）。
    """
    d = decide(_input(stock_driver=FORWARD, bench_driver=FORWARD), JudgmentChange(fact_set_changed=True))
    assert d is not None
    assert d.action == "buy", f"{d.action} / {d.change_reason}"
    assert d.is_new_signal is True


def test_maintain_rule_is_not_shadowed_by_p08_gate() -> None:
    """门在 R4 **之后** ⇒ 无变化日的 `maintain` 不受影响（否则会把"维持原判断"也误拦）。

    ★ 这条钉的是**门的相对位置**（顺序契约），不是门本身 —— 位置写错时只有它变红。
    """
    d = decide(_input(stock_driver=REALIZED, bench_driver=REALIZED), JudgmentChange())
    assert d is not None
    assert d.action == "maintain", d.action
    assert d.is_new_signal is False
