"""`run_decide.py` —— 决策层**真实运行**入口（`Ch7 §F` 端到端时序）。

```
python system/scripts/decision/run_decide.py <code_root> \
    --stock-prices <jsonl> --benchmark-prices <jsonl> \
    [--start YYYY-MM-DD] [--end YYYY-MM-DD] \
    [--company-id ...] [--security-id ...] [--benchmark-id ...] [--rule-version ...]
```

流程（`Ch7 §F` 逐字）：**行情点 → `scripts/compute` 真算收益（`DerivedValue`）→ 前置门 →
5 规则决策 → 落 `facts/recommendations.jsonl` → 重建 `index/`**。

★ **收益值是"算出来"的，不是"填进去"的**（`Ch7 §D.2` / `N7.3-07`）：个股与基准收益
  均由 `scripts.compute.returns.compute_total_return` 从**行情点序列**确定性算出，
  携带 `formula` + `operands` + `method_version`；本脚本**不**包装任何裸露数字。

★ 退出码：`0` 正常（含"门拒绝 → 不出建议"）；`1` 传 `--require-recommendation` 却未出建议；
  `2` 输入异常（缺参数 / 行情文件缺失 / JSON 非法）。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Sequence

_ROOT = Path(__file__).resolve().parents[2]      # .../system
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from schema.models import DerivedValue  # noqa: E402
from scripts.compute.contract import ComputeError, ComputeGap, safe_compute  # noqa: E402
from scripts.compute.returns import PricePoint, compute_total_return  # noqa: E402
from scripts.decision.gate import (  # noqa: E402
    ExplainableForecast,
    JudgmentChange,
    RecommendationInput,
    ResearchBaseline,
    ReturnValue,
)
from scripts.decision.rules import build_recommendation, decide, persist_recommendation  # noqa: E402

DEFAULT_HORIZON = "2q"
DEFAULT_RULE_VERSION = "decision-v1"

# 真实运行默认输入：基准 = `ws/compute` 抓取的 **真实 AGIX 行情**；
# 个股 = 本工作流的**行情输入夹具**（注入输入，非事实主张）。
DEFAULT_BENCHMARK_PRICES = _ROOT / "tests" / "compute" / "fixtures" / "agix_prices.jsonl"
DEFAULT_STOCK_PRICES = _ROOT / "tests" / "decision" / "fixtures" / "demo_stock_prices.jsonl"


@dataclass(frozen=True)
class RunReport:
    """一次真实运行的结果（供编排接缝回传）。"""

    recommendation_ids: tuple[str, ...]
    gaps: tuple[str, ...]
    signals_emitted: int
    degraded: bool
    action: str | None


def load_prices(path: str | Path) -> list[PricePoint]:
    """读行情点 JSONL（`{day, price, source_ref?, is_nav?}`）。文件缺失 / JSON 非法 → **响亮失败**。"""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"行情文件不存在: {file_path}")
    prices: list[PricePoint] = []
    for lineno, raw in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            prices.append(
                PricePoint(
                    day=date.fromisoformat(str(row["day"])),
                    price=Decimal(str(row["price"])),
                    source_ref=str(row.get("source_ref", "")),
                    is_nav=bool(row.get("is_nav", False)),
                )
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise ValueError(f"{file_path}:{lineno} 行情行非法: {exc}") from exc
    if len(prices) < 2:
        raise ValueError(f"{file_path}: 行情点不足（<2），无法计算区间收益")
    return prices


def _window(prices: Sequence[PricePoint]) -> tuple[date, date]:
    days = sorted(p.day for p in prices)
    return days[0], days[-1]


def _total_return(
    prices: Sequence[PricePoint],
    *,
    subject: str,
    currency: str,
    start: date,
    end: date,
) -> DerivedValue | ComputeGap:
    """用 `scripts/compute` 真算区间总回报 —— **缺口类异常折叠成缺口对象**（`Ch9 §3.5` 阶段④）。

    `safe_compute` 把 `MissingInput` / `UndefinedComputation`（输入缺失 / 该计算无定义）
    折叠为 `ComputeGap`；`CaliberViolation` / `OrderViolation`（口径违例 / 倒填）
    **原样抛出**（响亮失败，不当缺口吞掉）。
    """
    return safe_compute(
        lambda: compute_total_return(
            prices,
            (),
            start,
            end,
            subject=subject,
            currency=currency,
            operands=(
                f"{subject}:begin_close({start})",
                f"{subject}:end_close({end})",
                f"{subject}:corporate_actions=none",
            ),
        ),
        kind="total_return",
        subject=subject,
    )


def _forecast(derived: DerivedValue, *, subject: str) -> ExplainableForecast:
    """把**真实** `DerivedValue` 包成"可解释预测"（`Ch7 §D.2` ①②③④）。

    ★ 点估用 `low == high`；`worksheet` 即 `DerivedValue` 本身 —— 决策层据此可追到
      `formula` / `operands` / `method_version`（本脚本**不**包装任何裸露数字）。
    """
    return ExplainableForecast(
        drivers=(f"{subject}:market_price_total_return",),
        horizon=DEFAULT_HORIZON,
        return_range=ReturnValue(low=derived.value, high=derived.value),
        worksheet=derived,
        method_version=derived.method_version,
    )


def run(
    root: str | Path,
    *,
    stock_prices_path: str | Path,
    benchmark_prices_path: str | Path,
    company_id: str = "co-demo",
    security_id: str = "usDEMO",
    benchmark_id: str = "usAGIX",
    currency: str = "USD",
    start: date | None = None,
    end: date | None = None,
    rule_version: str = DEFAULT_RULE_VERSION,
    persist: bool = True,
) -> RunReport:
    """端到端跑一次：行情 → `DerivedValue` → 门 → 5 规则 → 落库。"""
    stock_prices = load_prices(stock_prices_path)
    benchmark_prices = load_prices(benchmark_prices_path)
    stock_start, stock_end = _window(stock_prices)
    bench_start, bench_end = _window(benchmark_prices)
    begin = start or min(stock_start, bench_start)
    finish = end or max(stock_end, bench_end)

    stock_derived = _total_return(
        stock_prices, subject=company_id, currency=currency, start=begin, end=finish
    )
    bench_derived = _total_return(
        benchmark_prices, subject=benchmark_id, currency=currency, start=begin, end=finish
    )
    compute_gaps = tuple(
        gap.gap_id for gap in (stock_derived, bench_derived) if isinstance(gap, ComputeGap)
    )
    if compute_gaps:
        # 输入缺失 / 计算无定义 → **输出缺口对象，不出数值**；不生成建议，如实降级。
        return RunReport((), compute_gaps, 0, True, None)

    assert isinstance(stock_derived, DerivedValue) and isinstance(bench_derived, DerivedValue)
    stock_forecast = _forecast(stock_derived, subject=company_id)
    benchmark_forecast = _forecast(bench_derived, subject=benchmark_id)
    inp = RecommendationInput(
        company_id=company_id,
        baseline=ResearchBaseline(
            company_id=company_id,
            research_depth="tracking",
            baseline_complete=True,
        ),
        stock_forecast=stock_forecast,
        benchmark_forecast=benchmark_forecast,
        own_evidence=(f"claim:{company_id}:market",),
    )
    decision = decide(inp, JudgmentChange(fact_set_changed=True))
    if decision is None:
        return RunReport((), ("gate_rejected_no_recommendation",), 0, True, None)

    recommendation_id = f"rec-{security_id}-{begin.isoformat()}"
    rec = build_recommendation(
        decision,
        inp=inp,
        recommendation_id=recommendation_id,
        security_id=security_id,
        horizon=DEFAULT_HORIZON,
        start_date=begin,
        rule_version=rule_version,
        review_date=finish,
        change_reason=decision.change_reason,
        evidence_version_ids=(stock_forecast.worksheet.derived_id,),
    )
    if persist:
        persist_recommendation(root, rec)
        from schema.store import rebuild_index

        rebuild_index(root)
    signals = 1 if decision.is_new_signal else 0
    return RunReport((recommendation_id,), decision.gaps, signals, False, decision.action)


def run_default(root: str | Path) -> RunReport:
    """编排接缝的默认实现：用仓库内**默认输入**（真实 AGIX 基准 + 个股输入夹具）跑一次。

    输入缺失 → 返回 `degraded=True` + `gaps=("inputs_unavailable",)`，**不伪造**结果。
    """
    if not DEFAULT_STOCK_PRICES.exists() or not DEFAULT_BENCHMARK_PRICES.exists():
        return RunReport((), ("inputs_unavailable",), 0, True, None)
    return run(
        root,
        stock_prices_path=DEFAULT_STOCK_PRICES,
        benchmark_prices_path=DEFAULT_BENCHMARK_PRICES,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_decide.py", description="决策层真实运行入口")
    parser.add_argument("code_root", nargs="?", default=str(_ROOT))
    parser.add_argument("--stock-prices", default=None)
    parser.add_argument("--benchmark-prices", default=None)
    parser.add_argument("--company-id", default="co-demo")
    parser.add_argument("--security-id", default="usDEMO")
    parser.add_argument("--benchmark-id", default="usAGIX")
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--rule-version", default=DEFAULT_RULE_VERSION)
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--require-recommendation", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.code_root)
    if not root.exists():
        print(f"[INPUT-ERROR] code_root 不存在: {root}", file=sys.stderr)
        return 2
    if args.stock_prices is None or args.benchmark_prices is None:
        print("[INPUT-ERROR] 必须提供 --stock-prices 与 --benchmark-prices", file=sys.stderr)
        return 2

    try:
        report = run(
            root,
            stock_prices_path=args.stock_prices,
            benchmark_prices_path=args.benchmark_prices,
            company_id=args.company_id,
            security_id=args.security_id,
            benchmark_id=args.benchmark_id,
            currency=args.currency,
            start=date.fromisoformat(args.start) if args.start else None,
            end=date.fromisoformat(args.end) if args.end else None,
            rule_version=args.rule_version,
            persist=not args.no_persist,
        )
    except (FileNotFoundError, ValueError, KeyError, OSError, ComputeError) as exc:
        print(f"[INPUT-ERROR] run_decide: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    summary = {
        "recommendation_ids": list(report.recommendation_ids),
        "action": report.action,
        "signals_emitted": report.signals_emitted,
        "gaps": list(report.gaps),
        "degraded": report.degraded,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if args.require_recommendation and not report.recommendation_ids:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
