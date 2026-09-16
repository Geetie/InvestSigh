"""`run_decide.py` —— 决策层**真实运行**入口（`Ch7 §F` 端到端时序）。

```
python system/scripts/decision/run_decide.py <code_root> \
    [--stock-prices <jsonl> --benchmark-prices <jsonl>] \
    [--run-date YYYY-MM-DD] [--start YYYY-MM-DD] [--end YYYY-MM-DD] \
    [--company-id ...] [--security-id ...] [--benchmark-id ...] [--rule-version ...]
```

流程（`Ch7 §F` 逐字）：**行情点 → `scripts/compute` 真算收益（`DerivedValue`）→ 前置门 →
5 规则决策 → 落 `facts/recommendations.jsonl` → 重建 `index/`**。

★ **收益值是"算出来"的，不是"填进去"的**（`Ch7 §D.2` / `N7.3-07`）：个股与基准收益
  均由 `scripts.compute.returns.compute_total_return` 从**行情点序列**确定性算出，
  携带 `formula` + `operands` + `method_version`；本脚本**不**包装任何裸露数字。

★★ **输入来源（`P7-2` 根因修复）**：**生产默认输入一律来自真源**（`<code_root>/facts/prices.jsonl`
  + `<code_root>/facts/benchmarks.jsonl`，基准回落 `rules/benchmark.yaml`），**绝不**指向
  `system/tests/**`。脚本**不再**在模块级硬编码任何仓库内夹具路径。
  - `run_default(root, ...)`：读**真源**（无行情输入 → **没有产出**，如实降级，不伪造）；
  - `run(root, stock_prices_path=..., benchmark_prices_path=...)`：**显式注入**路径
    （测试 / 一次性运行用夹具时由**调用方**显式传入，本模块不预置）。

★ **`run_date` / `scope` 语义（`P7-3`）**：`run_default` 把 `run_date` 作为**as-of 上界**
  （只取 `day ≤ run_date` 的行情点，`Ch9 §3.4.1` 双时间轴 system_time / valid_time）；
  `scope` 用于**选取目标证券**。二者**均被真实使用**，不再"怎么传都得到同一条建议"。

★ 退出码：`0` 正常（含"门拒绝 → 不出建议"）；`1` 传 `--require-recommendation` 却未出建议；
  `2` 输入异常（缺参数 / 行情文件缺失 / JSON 非法 / **真源行情缺失**）。与
  `scripts/_common.run_checker` 的约定（`0` 放行 / `1` 阻断 / `2` 输入异常）一致。
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
from scripts.decision.rules import (  # noqa: E402
    build_recommendation,
    decide,
    persist_recommendation_detailed,
)

DEFAULT_HORIZON = "2q"
DEFAULT_RULE_VERSION = "decision-v1"

# ── 真源相对路径（`Ch9 §3.3.3` 的 18 个 JSONL；**不**含任何 `tests/**` 路径）──
TRUTH_PRICES_REL: str = "facts/prices.jsonl"
TRUTH_BENCHMARKS_REL: str = "facts/benchmarks.jsonl"
TRUTH_SECURITIES_REL: str = "facts/securities.jsonl"

#: `run_default` 缺输入时的缺口前缀（编排接缝据 `gaps` 判降级，**不**伪造产出）。
INPUTS_UNAVAILABLE = "inputs_unavailable"


@dataclass(frozen=True)
class RunReport:
    """一次真实运行的结果（供编排接缝回传）。"""

    recommendation_ids: tuple[str, ...]
    gaps: tuple[str, ...]
    signals_emitted: int
    degraded: bool
    action: str | None
    #: ★ 本次**真实**使用的输入窗口 `[begin, finish]`（ISO 串）；无窗口 → `None`。
    #:  `P7-3`：如实回传"当前可用输入窗口"，**不**用任何夹具窗口冒充。
    window: tuple[str, str] | None = None
    #: ★ 本轮**考察过、但幂等键已存在故未重复写入**的 `recommendation_id`（`Ch9 §3.5` 阶段⑤）。
    #:  与 `recommendation_ids`（本轮**真正新写入**）**互斥**。幂等判定不在这里做：
    #:  它由唯一写入口 `rules.persist_recommendation_detailed` 回传（`G-06`）。
    #:  ★ 为什么必须带出来（缺陷 `G-44`）：`scripts/decision/step.py` 据此填
    #:  `StepOutcome.skipped`。缺了它，幂等重跑时该字段为空 ⇒ `G1-05` 判【空执行】
    #:  ⇒ 整轮 `blocked`（而这一轮其实什么都没坏）。
    skipped_recommendation_ids: tuple[str, ...] = ()


def load_prices(path: str | Path) -> list[PricePoint]:
    """读行情点 JSONL（`{day, price, source_ref?, is_nav?}`）。文件缺失 / JSON 非法 → **响亮失败**。

    ★ 这是**显式注入**通道（测试 / 一次性运行由调用方传文件路径）；
      **生产默认路径**（`run_default`）走真源 `facts/prices.jsonl`，见 `_load_truth_series`。
    """
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


# ─────────────────────────── 真源读取（`P7-2`） ───────────────────────────


def _load_truth_series(
    root: Path, *, prices_file: str | Path | None = None
) -> dict[str, list[PricePoint]]:
    """读**真源**行情并按 `security_id` 分组（`Ch9 §3.3.3` `prices` / `§N9.1-19`）。

    - `prices_file` 显式给出 → 读该文件（**调用方显式注入**，供测试 / 一次性运行）；
    - 缺省 → 读 `<root>/facts/prices.jsonl`（**生产真源**）。
    - 复用 `scripts.compute.driver.load_price_points`（**唯一真源**解析路径，`G-06`）——
      本模块**不**复制第二套行情解析。缺 `security_id` / 缺日期 → `MissingInput`（缺口族）
      → 折叠为"无可用行情"（返回空表），由调用方**如实降级**，**不伪造**。
    """
    from scripts.compute.driver import load_price_points

    source = Path(prices_file) if prices_file is not None else None
    try:
        return load_price_points(source, root)
    except ComputeError:
        # 缺口族（输入缺失 / 无定义）→ 无可用行情；其余（口径 / 顺序 / JSON 非法）**原样抛出**。
        return {}


def _load_primary_benchmark(root: Path) -> dict | None:
    """读 `facts/benchmarks.jsonl`（回落 `rules/benchmark.yaml`），取主基准对象（无则 `None`）。

    基准**对象**缺真源（`facts/benchmarks.jsonl` 空 **且** `rules/benchmark.yaml` 不存在）
    → `None`（调用方据此**如实降级**，不出建议），**不**伪造基准。
    """
    from scripts.compute.driver import load_benchmark_objects

    try:
        objects = load_benchmark_objects(root)
    except (OSError, ValueError):
        # 基准对象真源不可得（`facts/benchmarks.jsonl` 空 且 `rules/benchmark.yaml` 缺失/损坏）
        # → 视为"**无基准输入**"，由调用方如实降级（`Ch9 §3.5` 阶段④：输入缺失 → 缺口对象），
        #   **不**伪造基准对象。
        objects = []
    if not objects:
        return None
    for obj in objects:
        if str(obj.get("benchmark_role", "primary")) == "primary":
            return dict(obj)
    return dict(objects[0])


def _resolve_benchmark_security(benchmark: dict | None, series: dict) -> str | None:
    """解析基准对应证券：对象自带 `security_id` 优先；否则行情仅 1 个证券时取之。

    对齐 `scripts.compute.driver._resolve_security` 的口径（`Ch3 §C.3`：基准对象化，
    身份由对象/行情决定，**不硬编码单一基准代码**）。
    """
    if benchmark is None:
        return None
    explicit = benchmark.get("security_id")
    if explicit:
        return str(explicit)
    if len(series) == 1:
        return next(iter(series))
    return None


def _select_company_security(series: dict, benchmark_security: str | None, scope: str | None) -> str | None:
    """选取目标（个股）证券：`scope` 命中行情证券时优先；否则行情里除基准外的**唯一**证券。"""
    if scope and scope in series and scope != benchmark_security:
        return str(scope)
    others = sorted(sid for sid in series if sid != benchmark_security)
    if len(others) == 1:
        return others[0]
    return None


def _as_of(prices: Sequence[PricePoint], run_date: date | None) -> list[PricePoint]:
    """`run_date` 作为 **as-of 上界**：只保留 `day ≤ run_date` 的行情点（`Ch9 §3.4.1`）。

    `run_date is None` → 取全部可用点（一次性 CLI 运行无 as-of 上界）。
    """
    if run_date is None:
        return list(prices)
    return [p for p in prices if p.day <= run_date]


def _company_id(root: Path, security_id: str) -> str:
    """证券 → 公司（`Ch9 §2.1`：公司 = 研究判断对象、证券 = 可交易对象，**分离**）。

    读真源 `facts/securities.jsonl` 的 `company_id` 映射；无该真源 / 无映射时，
    以证券 id 代公司 id 并（在报告中）登记为已知近似（**不**新增冻结字段）。
    """
    from schema.store import read_records

    for row in read_records(root, TRUTH_SECURITIES_REL.split("/")[-1].removesuffix(".jsonl")):
        if str(row.get("security_id", "")) == security_id and row.get("company_id"):
            return str(row["company_id"])
    return security_id


def _benchmark_id(benchmark: dict | None, security_id: str) -> str:
    """基准 id：对象 `benchmark_id` / `benchmark_id_param_ref` 优先，否则退回证券 id。"""
    if benchmark:
        bid = benchmark.get("benchmark_id") or benchmark.get("benchmark_id_param_ref")
        if bid:
            return str(bid)
    return security_id


# ─────────────────────────── 运行 ───────────────────────────


def _run_core(
    root: str | Path,
    stock_prices: Sequence[PricePoint],
    benchmark_prices: Sequence[PricePoint],
    *,
    company_id: str,
    security_id: str,
    benchmark_id: str,
    currency: str = "USD",
    start: date | None = None,
    end: date | None = None,
    rule_version: str = DEFAULT_RULE_VERSION,
    persist: bool = True,
) -> RunReport:
    """端到端跑一次（**已解析行情序列**）：行情 → `DerivedValue` → 门 → 5 规则 → 落库。"""
    root_path = Path(root)
    stock_start, stock_end = _window(stock_prices)
    bench_start, bench_end = _window(benchmark_prices)
    begin = start or min(stock_start, bench_start)
    finish = end or max(stock_end, bench_end)
    window = (begin.isoformat(), finish.isoformat())

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
        return RunReport((), compute_gaps, 0, True, None, window)

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
        return RunReport((), ("gate_rejected_no_recommendation",), 0, True, None, window)

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
    written_ids: tuple[str, ...] = ()
    skipped_ids: tuple[str, ...] = ()
    if persist:
        # 真源目录 `facts/` 由本入口保证存在（`P7-6`：不再因缺目录抛 `FileNotFoundError`）。
        (root_path / "facts").mkdir(parents=True, exist_ok=True)
        # ★ **唯一**落库入口：它同时给出"本轮真正写入"与"本轮幂等命中"两个互斥集合
        #   （`G-06`：幂等判定只在这里做一次；`step.py` 不重算，只转述）。
        outcome = persist_recommendation_detailed(root_path, rec)
        written_ids, skipped_ids = outcome.written_ids, outcome.skipped_ids
        from schema.store import rebuild_index

        rebuild_index(root_path)
    else:
        written_ids = (recommendation_id,)  # 未落库（`--no-persist`）→ 报告"本会产出"，但不写盘

    if persist and not written_ids:
        if skipped_ids:
            # 幂等命中（同"输入窗口 + 规则版本"重跑）→ **不追加**，如实回传（`P7-4`）。
            # ★ 命中对象走**独立的 `skipped_recommendation_ids`**，**不得**折进 `recommendation_ids`：
            #   后者是"本轮真正新写入"（`tests/compute/test_step_wiring.py:48` 已钉死该语义）；
            #   若折进去，"首跑"与"幂等重跑"的 `recommendation_ids` 相同 ⇒ 幂等性在输出上不可区分。
            return RunReport(
                (),
                (f"already_persisted:{recommendation_id}",),
                0,
                False,
                decision.action,
                window,
                skipped_recommendation_ids=skipped_ids,
            )
        # 键此前不存在却一行未写入 ⇒ 既不是产出、也不是幂等命中 → 两个集合都空，如实降级。
        return RunReport((), (f"not_persisted:{recommendation_id}",), 0, True, decision.action, window)
    signals = 1 if decision.is_new_signal else 0
    return RunReport(written_ids, decision.gaps, signals, False, decision.action, window)


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
    """端到端跑一次（**显式注入**行情文件路径）：行情 → `DerivedValue` → 门 → 5 规则 → 落库。

    `stock_prices_path` / `benchmark_prices_path` 是**调用方显式注入**的行情文件；
    生产默认路径（读真源）见 `run_default`。
    """
    stock_prices = load_prices(stock_prices_path)
    benchmark_prices = load_prices(benchmark_prices_path)
    return _run_core(
        root,
        stock_prices,
        benchmark_prices,
        company_id=company_id,
        security_id=security_id,
        benchmark_id=benchmark_id,
        currency=currency,
        start=start,
        end=end,
        rule_version=rule_version,
        persist=persist,
    )


def run_default(
    root: str | Path,
    *,
    run_date: date | None = None,
    scope: str | None = None,
    prices_file: str | Path | None = None,
    currency: str = "USD",
    rule_version: str = DEFAULT_RULE_VERSION,
    persist: bool = True,
) -> RunReport:
    """编排接缝的默认实现：用 **`root` 下的真源**跑一次（`P7-2` 根因修复）。

    - **行情真源** = `<root>/facts/prices.jsonl`（`prices_file` 可显式覆盖）；
    - **基准真源** = `<root>/facts/benchmarks.jsonl`（回落 `rules/benchmark.yaml`）；
    - **`run_date`** = as-of 上界（只取 `day ≤ run_date` 的点，`Ch9 §3.4.1`）；
    - **`scope`** = 目标证券选取（命中真源证券时优先）。

    ★ **无真实上游输入 → 没有产出**：真源行情缺失 / 证券无法解析 / 窗口不足 2 点
      → 返回 `degraded=True` + `gaps=("inputs_unavailable:...",)` + `recommendation_ids=()`
      —— **绝不**用任何仓库内夹具冒充输入，**绝不**伪造建议。
    """
    root_path = Path(root)
    series = _load_truth_series(root_path, prices_file=prices_file)
    if not series:
        return RunReport((), (f"{INPUTS_UNAVAILABLE}:{TRUTH_PRICES_REL}",), 0, True, None, None)

    benchmark = _load_primary_benchmark(root_path)
    benchmark_security = _resolve_benchmark_security(benchmark, series)
    company_security = _select_company_security(series, benchmark_security, scope)
    if benchmark_security is None or company_security is None or company_security == benchmark_security:
        return RunReport(
            (), (f"{INPUTS_UNAVAILABLE}:securities_unresolved",), 0, True, None, None
        )

    company_prices = _as_of(series[company_security], run_date)
    bench_prices = _as_of(series[benchmark_security], run_date)
    if len(company_prices) < 2 or len(bench_prices) < 2:
        return RunReport(
            (), (f"{INPUTS_UNAVAILABLE}:insufficient_prices",), 0, True, None, None
        )

    return _run_core(
        root_path,
        company_prices,
        bench_prices,
        company_id=_company_id(root_path, company_security),
        security_id=company_security,
        benchmark_id=_benchmark_id(benchmark, benchmark_security),
        currency=currency,
        rule_version=rule_version,
        persist=persist,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_decide.py", description="决策层真实运行入口")
    parser.add_argument("code_root", nargs="?", default=str(_ROOT))
    parser.add_argument("--stock-prices", default=None, help="个股行情文件（显式注入；缺省走真源）")
    parser.add_argument("--benchmark-prices", default=None, help="基准行情文件（显式注入；缺省走真源）")
    parser.add_argument("--run-date", default=None, help="as-of 上界 YYYY-MM-DD（真源模式）")
    parser.add_argument("--scope", default=None, help="目标证券 id（真源模式）")
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

    try:
        if args.stock_prices is not None and args.benchmark_prices is not None:
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
        else:
            report = run_default(
                root,
                run_date=date.fromisoformat(args.run_date) if args.run_date else None,
                scope=args.scope,
                currency=args.currency,
                rule_version=args.rule_version,
                persist=not args.no_persist,
            )
    except (FileNotFoundError, ValueError, KeyError, OSError, ComputeError) as exc:
        print(f"[INPUT-ERROR] run_decide: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    # `P7-6`：真源输入缺失 → **可读**的输入缺失报错 + `exit 2`（输入异常，语义同 `run_checker`）。
    if not report.recommendation_ids and report.gaps and all(
        g.startswith(INPUTS_UNAVAILABLE) for g in report.gaps
    ):
        print(
            f"[INPUT-ERROR] run_decide: 真源输入缺失或不完整（{', '.join(report.gaps)}）；"
            f"请提供 --stock-prices/--benchmark-prices 或填充 {TRUTH_PRICES_REL}",
            file=sys.stderr,
        )
        return 2

    summary = {
        "recommendation_ids": list(report.recommendation_ids),
        # 幂等命中（本轮未新写入、但确实考察过）——与 `recommendation_ids` **互斥**。
        # 两轮输出因此**可区分**：首轮 `ids` 非空 / `skipped` 空；重跑反向。
        "skipped_recommendation_ids": list(report.skipped_recommendation_ids),
        "action": report.action,
        "signals_emitted": report.signals_emitted,
        "gaps": list(report.gaps),
        "degraded": report.degraded,
        "window": list(report.window) if report.window else None,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if args.require_recommendation and not report.recommendation_ids:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
