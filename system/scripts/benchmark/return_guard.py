#!/usr/bin/env python3
"""`return_guard.py` —— **基准收益守卫**（`Ch3 §D.2` / N3.4-05/07 / `Ch9 §3.4.12`）。

```
python system/scripts/benchmark/return_guard.py [code_root]
```

三条断言（`Ch3 §D.2` 逐字）：

① 基准收益来源必须是**基金本身行情** —— **禁用公开股票指数替代整个基金**（N3.4-05）
② **禁止二次扣费**（基金费用已含在实际回报中）（N3.4-07）
③ 净值收益**只能标 `diagnostic`**，不得用于相对收益判定

★ 三者的**落点不同**（第二轮独立审计指出此处 docstring 曾含糊）：

| 断言 | 由谁强制 |
|---|---|
| ① ② | `check()` 每次门禁都跑，逐条断言 `rules/benchmark.yaml` 的 `benchmark_objects` |
| ③（配置面） | `check()` 断言 `return_guard.nav_return_role == "diagnostic"` |
| ③（运行面） | `nav_return_diagnostic_only()` / `assert_nav_not_used_for_relative()` 是**导出的运行时断言**，供调用方在计算净值收益时调用 —— 本检查器**不替调用方**跑它们。

为什么必须独立代码（`Ch3 §B`）：
这类口径错误是**静默的**（算出来仍是个数），必须由**可单测的守卫**拦截，
不能靠提示词。

★ 命中即 fail，禁 warn-only（纪律 2）。
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402

NAV_ROLE = "diagnostic"


class BenchmarkCaliberError(RuntimeError):
    """基准口径错误（静默型错误，必须由守卫拦截）。"""


def assert_benchmark_return_source(benchmark: Mapping[str, Any]) -> None:
    """① 不得用公开指数替代基金（N3.4-05）。"""
    if benchmark.get("return_source") != "fund_market_price":
        raise BenchmarkCaliberError(
            "基准收益必须取基金本身行情，禁用替代指数："
            f"return_source={benchmark.get('return_source')!r}"
        )
    if benchmark.get("proxy_index_used") is not False:
        raise BenchmarkCaliberError(
            f"不得以公开指数充当基金：proxy_index_used={benchmark.get('proxy_index_used')!r}"
        )


def assert_no_double_fee(benchmark: Mapping[str, Any]) -> None:
    """② 相对收益禁止二次扣费（N3.4-07）。"""
    basis = benchmark.get("return_basis") or {}
    if basis.get("fee_deducted_again") is not False:
        raise BenchmarkCaliberError(
            f"基金费用已含在实际回报，禁止二次扣费：fee_deducted_again={basis.get('fee_deducted_again')!r}"
        )


def nav_return_diagnostic_only(nav_value: Any) -> dict[str, Any]:
    """③ 净值收益**仅作诊断**；返回结构强制带 `role=diagnostic`。"""
    return {"role": NAV_ROLE, "value": nav_value}


def assert_nav_not_used_for_relative(result: Mapping[str, Any]) -> None:
    if result.get("used_for_relative_judgment"):
        raise BenchmarkCaliberError("净值收益仅作诊断，不得用于相对收益判定（N3.4-07）")


def benchmark_return(
    benchmark: Mapping[str, Any],
    total_return_fn,
    start: Any,
    end: Any,
) -> Decimal:
    """**基准市场价总回报**（同口径：同起止时间 / 美元 / 含分红再投资）。

    `total_return_fn` 由调用方注入（`scripts/compute/` 于阶段② 交付）——
    本函数**不自己算数**，只做**口径断言 + 调度**（N9.2-03：算术由程序层承担）。
    """
    assert_benchmark_return_source(benchmark)
    assert_no_double_fee(benchmark)
    basis = benchmark.get("return_basis") or {}
    return total_return_fn(
        benchmark,
        start,
        end,
        dividends_reinvested=bool(basis.get("dividends_reinvested")),
        currency=str(basis.get("currency", "")),
    )


def check(root: Path) -> CheckReport:
    import yaml

    report = CheckReport(checker="return_guard")
    path = root / "rules" / "benchmark.yaml"
    if not path.exists():
        raise FileNotFoundError(f"缺少基准对象声明: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("rules/benchmark.yaml 顶层必须是 mapping")

    objects = data.get("benchmark_objects") or []
    report.scanned["benchmark_objects"] = len(objects)
    if not objects:
        raise ValueError("rules/benchmark.yaml 未声明任何 benchmark_object")

    for bm in objects:
        label = str(bm.get("benchmark_id_param_ref", "<unnamed>"))
        for fn in (assert_benchmark_return_source, assert_no_double_fee):
            try:
                fn(bm)
            except BenchmarkCaliberError as exc:
                report.violations.append(
                    Violation("N3.4-05/07", f"[{label}] {exc}", "rules/benchmark.yaml")
                )

    # 净值角色断言：配置里不得把 nav 升格为相对收益口径
    guard_cfg = data.get("return_guard") or {}
    if guard_cfg.get("nav_return_role") != NAV_ROLE:
        report.violations.append(
            Violation(
                "N3.4-07",
                f"nav_return_role 必须为 {NAV_ROLE!r}，实为 {guard_cfg.get('nav_return_role')!r}",
                "rules/benchmark.yaml",
            )
        )
    report.scanned["return_guard_keys"] = len(guard_cfg)
    return report


if __name__ == "__main__":
    sys.exit(run_checker("return_guard.py", check))
