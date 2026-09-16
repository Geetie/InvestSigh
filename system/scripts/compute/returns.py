"""`returns.py` —— 基准/个股总回报确定性算术（`Ch9 §3.4.4` / `§3.4.9`；`Ch3 §D.2`）。

两条权威要求，逐条落在代码里：

1. **计算顺序**（`Ch9 §3.4.9`）：**先按公司行动复权价格序列 → 再走 `compute_total_return`**。
   本层把两步合在一个**确定性**遍历里（拆股/分立改股数、分红按当日价再投资），并输出
   `formula` + `operands` + `method_version`。
2. **基准三条硬口径**（`Ch3 §D.2` / `N3.4-05/07`）：

   - ① 基准收益来源 = **基金本身行情**，**禁用替代指数**；
   - ② `fee_deducted_again is False`（**禁止二次扣费**）；
   - ③ `nav_return` **只能标 `diagnostic`**，不得用于相对收益判定。

★ **唯一真源（`G-06`）**：上述三条口径的**断言**只在
  `scripts/benchmark/return_guard.py` 里实现一次。本模块**只调用** `return_guard.benchmark_return()`
  与 `return_guard.nav_return_diagnostic_only()`，**不复制**任何口径断言 —— 复制一份就是
  第二条同类校验路径，会与真源漂移。

★ 净值（`is_nav`）价格点**不得**进入市场价总回报：混入会制造"拿净值当市场价"的静默口径错误
  （`Ch3 §D.2` ③），故显式 `CaliberViolation`。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping, Sequence

from schema.models import DerivedValue

from .contract import (
    CaliberViolation,
    MissingInput,
    UndefinedComputation,
    derived_id_for,
    make_derived,
)


@dataclass(frozen=True)
class PricePoint:
    """一个行情点（`Ch9 §N9.1-19` `PriceSnapshot` 的算术投影）。

    `is_nav=True` 表示这是**净值**点（仅诊断，`Ch3 §D.2` ③）。
    """

    day: date
    price: Decimal
    source_ref: str = ""
    is_nav: bool = False


@dataclass(frozen=True)
class CorporateActionPoint:
    """一个公司行动（`Ch9 §3.4.9` `registry/corporate-actions.jsonl` 的算术投影）。

    - `action_type ∈ {div, split, spinoff}`（`Ch9 §3.4.9`）。
    - `div` 用 `amount`（每股现金）；`split` / `spinoff` 用 `ratio`（每股变 `ratio` 股）。
    """

    effective_date: date
    action_type: str
    amount: Decimal | None = None
    ratio: Decimal | None = None
    source_ref: str = ""


def _split_actions(window_actions: Sequence[CorporateActionPoint], *, subject: str) -> None:
    """校验公司行动类型与所需字段（`Ch9 §3.4.9`）。缺失 → 缺口对象。"""
    for a in window_actions:
        if a.action_type in {"split", "spinoff"}:
            if a.ratio is None or a.ratio <= 0:
                raise MissingInput(
                    f"{subject}: {a.action_type} 缺合法 ratio（实得 {a.ratio}）",
                    missing=["ratio"],
                    subject=subject,
                )
        elif a.action_type == "div":
            if a.amount is None:
                raise MissingInput(
                    f"{subject}: 分红行动缺 amount（每股现金，实得 {a.amount}）",
                    missing=["amount"],
                    subject=subject,
                )
        else:
            raise UndefinedComputation(
                f"{subject}: 未知公司行动类型 {a.action_type!r}（合法：div / split / spinoff）",
                missing=["action_type"],
                subject=subject,
            )


def _total_return_value(
    prices: Sequence[PricePoint],
    actions: Sequence[CorporateActionPoint],
    start: date,
    end: date,
    *,
    dividends_reinvested: bool,
    subject: str,
) -> Decimal:
    """市场价**总回报**（`(期末价值 - 期初价值) / 期初价值`），含分红再投资或现金留存。

    确定性遍历（**先复权再总回报**，`Ch9 §3.4.9`）：

    1. 取 `prices` 中 `start <= day <= end` 的点，按日升序 —— 少于 2 点 → 缺口。
    2. `shares = 1`；`cash = 0`。
    3. 对窗口内公司行动按 `(effective_date, 类型序)` 升序处理：
       - `split` / `spinoff`：`shares *= ratio`（拆股本身不改总回报，但改后续每股分红基数）；
       - `div`：`cash_d = shares * amount`；再投资 → `shares += cash_d / 当日价`，否则留 `cash`。
    4. 终值 = `shares * 期末价 + cash`；回报 = `终值 / 期初价 - 1`。
    """
    window = sorted(
        (p for p in prices if start <= p.day <= end),
        key=lambda p: p.day,
    )
    if not window:
        raise MissingInput(
            f"{subject}: 区间 [{start}..{end}] 内无行情点",
            missing=["prices"],
            subject=subject,
        )
    if len(window) == 1:
        raise UndefinedComputation(
            f"{subject}: 区间内仅 1 个行情点，总回报无定义",
            missing=["prices"],
            subject=subject,
        )
    nav_points = [p for p in window if p.is_nav]
    if nav_points:
        raise CaliberViolation(
            f"{subject}: 市场价总回报不得混入净值点（Ch3 §D.2 ③，"
            f"共 {len(nav_points)} 个 is_nav 点）"
        )

    window_actions = sorted(
        (
            a
            for a in actions
            if start <= a.effective_date <= end
        ),
        key=lambda a: (a.effective_date, {"split": 0, "spinoff": 0, "div": 1}.get(a.action_type, 2)),
    )
    _split_actions(window_actions, subject=subject)

    price_by_day = {p.day: p.price for p in window}
    price_days = sorted(price_by_day)

    def _reinvest_price(on: date) -> Decimal:
        """取 `on` 当日价；无当日价 → 之后最近一日价（确定性）。取不到 → 缺口。"""
        if on in price_by_day:
            return price_by_day[on]
        for d in price_days:
            if d > on:
                return price_by_day[d]
        raise MissingInput(
            f"{subject}: 分红再投资日 {on} 无可用价格（区间内无更晚行情点）",
            missing=["prices"],
            subject=subject,
        )

    shares = Decimal(1)
    cash = Decimal(0)
    for action in window_actions:
        if action.action_type in {"split", "spinoff"}:
            assert action.ratio is not None  # _split_actions 已保证
            shares *= action.ratio
            continue
        assert action.amount is not None  # _split_actions 已保证
        dividend_cash = shares * action.amount
        if dividends_reinvested:
            shares += dividend_cash / _reinvest_price(action.effective_date)
        else:
            cash += dividend_cash

    begin_price = window[0].price
    if begin_price <= 0:
        raise UndefinedComputation(
            f"{subject}: 期初价非正（{begin_price}），总回报无定义",
            missing=["prices"],
            subject=subject,
        )
    end_value = shares * window[-1].price + cash
    return end_value / begin_price - Decimal(1)


def compute_total_return(
    prices: Sequence[PricePoint],
    actions: Sequence[CorporateActionPoint],
    start: date,
    end: date,
    *,
    subject: str,
    currency: str = "",
    dividends_reinvested: bool = True,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """含分红再投资的**市场价格总回报**（`Ch9 §3.4.4` 示例签名 / `§3.4.9`）。

    口径固定为**同起止时间**（`start`..`end` 闭区间）+ 由调用方声明的 `currency`；
    分红是否再投资由 `dividends_reinvested` 控制（基准口径须 `True`，`Ch3 §C.3`）。
    """
    value = _total_return_value(
        prices,
        actions,
        start,
        end,
        dividends_reinvested=dividends_reinvested,
        subject=subject,
    )
    reinvest = "dividends_reinvested" if dividends_reinvested else "dividends_cash"
    formula = f"total_return({start}..{end}) [{currency or 'ccy_undisclosed'}; {reinvest}]"
    return make_derived(
        derived_id_for("total_return", subject),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )


def compute_benchmark_return(
    benchmark: Mapping[str, Any],
    prices: Sequence[PricePoint],
    actions: Sequence[CorporateActionPoint],
    start: date,
    end: date,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """**基准**市场价总回报 —— 口径断言**只**经 `return_guard`（`G-06` 唯一真源）。

    流程（`Ch3 §D.2` / `§E`）：

    1. 调 `return_guard.benchmark_return(benchmark, total_return_fn, start, end)`；
       该函数**自己**跑 ① 基金行情来源 / ② `fee_deducted_again is False` 两条断言，
       并以基准声明的 `dividends_reinvested` / `currency` 调我们的算术闭包。
    2. 用算术闭包的结果构造 `DerivedValue`（`formula` + `operands` + `method_version`）。

    ★ 本模块**不重复**写任何口径断言；违例由 `return_guard` 抛 `BenchmarkCaliberError`。
    """
    from scripts.benchmark.return_guard import benchmark_return

    def _total_return_fn(
        bm: Mapping[str, Any],
        s: date,
        e: date,
        *,
        dividends_reinvested: bool,
        currency: str,
    ) -> Decimal:
        return _total_return_value(
            prices,
            actions,
            s,
            e,
            dividends_reinvested=dividends_reinvested,
            subject=subject or str(bm.get("benchmark_id_param_ref", "<benchmark>")),
        )

    value = benchmark_return(benchmark, _total_return_fn, start, end)
    basis = benchmark.get("return_basis") or {}
    formula = (
        f"benchmark_total_return({subject}) [{start}..{end}; "
        f"ccy={basis.get('currency', '')}; dividends_reinvested={basis.get('dividends_reinvested')}; "
        f"source={benchmark.get('return_source')}; fee_deducted_again=false]"
    )
    return make_derived(
        derived_id_for("benchmark_return", subject),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )


def compute_nav_return_diagnostic(
    nav_prices: Sequence[PricePoint],
    start: date,
    end: date,
    *,
    subject: str,
) -> dict[str, Any]:
    """**净值收益**（仅诊断）—— 经 `return_guard.nav_return_diagnostic_only()` 包装。

    返回结构**强制**带 `role=diagnostic`（`Ch3 §D.2` ③），上层不得把它用于相对收益判定。
    """
    value = _total_return_value(
        nav_prices,
        (),
        start,
        end,
        dividends_reinvested=False,
        subject=f"{subject}-nav",
    )
    from scripts.benchmark.return_guard import nav_return_diagnostic_only

    return nav_return_diagnostic_only(str(value))
