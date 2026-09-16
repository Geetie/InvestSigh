"""`driver.py` —— 确定性计算层的**真实运行编排**（`Ch9 §3.5` 阶段④）。

把"真实输入 → 真实 `DerivedValue`"这条路径串起来，供 `run_derived.py`（CLI）与
`step.py`（step ⑤/⑥ 处理器工厂）**共用**，避免第二条编排路径（`G-06` 唯一真源）。

输入（**全部真实读取**，注入式，不联网、不猜数）：

| 输入 | 来源 | 说明 |
|---|---|---|
| 基准对象 | `facts/benchmarks.jsonl`（优先）或 `rules/benchmark.yaml::benchmark_objects` | `Ch3 §C.3` 对象化基准 |
| 行情 | `facts/prices.jsonl` 或 `--prices-file` | `PricePoint`（`is_nav` 点被拒，`Ch3 §D.2` ③） |
| 公司行动 | `registry/corporate-actions.jsonl` | `Ch9 §3.4.9` |

输出：`derived/derived_values.jsonl`（`DerivedValue`）+ `derived/compute_gaps.jsonl`（缺口对象）。

★ 口径：基准收益**只**经 `returns.compute_benchmark_return` → `return_guard`（`G-06`）。
★ 输入缺失 → 缺口对象（`Ch9 §3.5` 阶段④），**不得**返回 `None`/`0` 冒充实值。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

from schema.models import DerivedValue

from .contract import (
    ComputeGap,
    MissingInput,
    gap_for,
    safe_compute,
)
from .returns import CorporateActionPoint, PricePoint, compute_benchmark_return, compute_total_return
from .store import append_derived_values, append_gaps, iter_all_values

PRICES_REL = "facts/prices.jsonl"
BENCHMARKS_REL = "facts/benchmarks.jsonl"
CORPORATE_ACTIONS_REL = "registry/corporate-actions.jsonl"
BENCHMARK_RULES_REL = "rules/benchmark.yaml"

VALID_REQUIRED_FIELDS = ("formula", "operands", "method_version")


@dataclass
class DriverReport:
    """一次真实运行的结果摘要（供 CLI 打印与测试断言）。"""

    values_written: int = 0
    gaps_written: int = 0
    derived_ids: list[str] = field(default_factory=list)
    gap_ids: list[str] = field(default_factory=list)
    integrity_violations: list[str] = field(default_factory=list)
    hard_errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.integrity_violations and not self.hard_errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "values_written": self.values_written,
            "gaps_written": self.gaps_written,
            "derived_ids": sorted(self.derived_ids),
            "gap_ids": sorted(self.gap_ids),
            "integrity_violations": list(self.integrity_violations),
            "hard_errors": list(self.hard_errors),
        }


# ─────────────────────────── 输入读取 ───────────────────────────


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno} 不是合法 JSON: {exc}") from exc
    return out


def load_benchmark_objects(root: Path) -> list[dict[str, Any]]:
    """读基准对象：`facts/benchmarks.jsonl` 优先；为空则回落到 `rules/benchmark.yaml`（真实声明）。"""
    rows = _read_jsonl(root / BENCHMARKS_REL)
    if rows:
        return rows
    from config.rules import load_yaml

    cfg = load_yaml(BENCHMARK_RULES_REL, root)
    objects = cfg.get("benchmark_objects") or []
    return [dict(obj) for obj in objects]


def load_price_points(prices_file: Path | None, root: Path) -> dict[str, list[PricePoint]]:
    """读行情点，按 `security_id` 分组。

    行字段：`security_id`（必填）+ 日期（`day` 或 `occurred_at`）+ `price`（+ 可选 `is_nav`）。
    缺 `security_id` → `MissingInput`（**不得**默认某个证券）；非法 `price` → `ValueError`（响亮失败）。
    """
    source = prices_file if prices_file is not None else (root / PRICES_REL)
    rows = _read_jsonl(source)
    grouped: dict[str, list[PricePoint]] = {}
    for idx, row in enumerate(rows, start=1):
        security_id = str(row.get("security_id") or "")
        if not security_id:
            raise MissingInput(
                f"{source}:{idx} 缺 security_id（不得默认证券）",
                missing=["security_id"],
                subject=str(source),
            )
        raw_day = row.get("day") or row.get("occurred_at") or row.get("snapshot_day")
        if not raw_day:
            raise MissingInput(
                f"{source}:{idx} 缺日期（day / occurred_at）",
                missing=["day"],
                subject=security_id,
            )
        day = date.fromisoformat(str(raw_day)[:10])
        try:
            price = Decimal(str(row.get("price")))
        except (InvalidOperation, TypeError) as exc:
            raise ValueError(f"{source}:{idx} price 非法: {row.get('price')!r}") from exc
        grouped.setdefault(security_id, []).append(
            PricePoint(day=day, price=price, source_ref=f"{source.name}#L{idx}", is_nav=bool(row.get("is_nav", False)))
        )
    return grouped


def load_corporate_actions(root: Path) -> list[CorporateActionPoint]:
    """读公司行动（`Ch9 §3.4.9`）：`{effective_date, type, amount|ratio, ...}`。"""
    rows = _read_jsonl(root / CORPORATE_ACTIONS_REL)
    actions: list[CorporateActionPoint] = []
    for idx, row in enumerate(rows, start=1):
        raw_date = row.get("effective_date") or row.get("date")
        if not raw_date:
            raise MissingInput(
                f"{CORPORATE_ACTIONS_REL}:{idx} 缺 effective_date",
                missing=["effective_date"],
                subject=str(row.get("security_id") or "<unknown>"),
            )
        amount = row.get("amount")
        ratio = row.get("ratio")
        actions.append(
            CorporateActionPoint(
                effective_date=date.fromisoformat(str(raw_date)[:10]),
                action_type=str(row.get("type") or row.get("action_type") or ""),
                amount=Decimal(str(amount)) if amount is not None else None,
                ratio=Decimal(str(ratio)) if ratio is not None else None,
                source_ref=f"{CORPORATE_ACTIONS_REL}#L{idx}",
            )
        )
    return actions


def _benchmark_subject(benchmark: Mapping[str, Any]) -> str:
    return str(
        benchmark.get("benchmark_id")
        or benchmark.get("benchmark_id_param_ref")
        or "<unnamed-benchmark>"
    )


def _resolve_security(
    benchmark: Mapping[str, Any],
    by_security: Mapping[str, Sequence[PricePoint]],
) -> str | None:
    """解析基准对应证券：基准自带的 `security_id` 优先；否则行情里只有唯一证券时用它。"""
    explicit = benchmark.get("security_id")
    if explicit:
        return str(explicit)
    securities = sorted(by_security)
    if len(securities) == 1:
        return securities[0]
    return None


# ─────────────────────────── 运行 ───────────────────────────


def run_derived(
    root: str | Path,
    *,
    prices_file: str | Path | None = None,
    start: date | None = None,
    end: date | None = None,
    persist: bool = True,
) -> DriverReport:
    """跑一遍确定性计算：基准总回报（经 `return_guard`）+ 缺口对象，并落 `derived/`。

    - 每个基准对象：解析证券 → 取该证券行情 → 调 `compute_benchmark_return`；
      缺对象/缺行情/窗口不足 → **缺口对象**（`safe_compute` 折叠）。
    - 另对每个有行情的证券调一次 `compute_total_return`（个股口径演示）。
    - `persist=False` → 只算不落（供纯校验）。
    """
    root_path = Path(root)
    report = DriverReport()
    values: list[DerivedValue] = []
    gaps: list[ComputeGap] = []

    benchmarks = load_benchmark_objects(root_path)
    price_source = Path(prices_file) if prices_file is not None else None
    by_security = load_price_points(price_source, root_path)
    actions = load_corporate_actions(root_path)

    if not benchmarks:
        _add_gap(
            gap_for(
                MissingInput(
                    "无基准对象（facts/benchmarks.jsonl 与 rules/benchmark.yaml 均为空）",
                    missing=["benchmarks"],
                    subject="<benchmark-set>",
                ),
                kind="benchmark",
            ),
            gaps,
            report,
        )

    for benchmark in benchmarks:
        subject = _benchmark_subject(benchmark)
        security_id = _resolve_security(benchmark, by_security)
        if security_id is None:
            _add_gap(
                gap_for(
                    MissingInput(
                        f"{subject}: 无法解析基准对应证券（未声明 security_id，且行情非唯一证券）",
                        missing=["security_id"],
                        subject=subject,
                    ),
                    kind="benchmark",
                ),
                gaps,
                report,
            )
            continue
        scoped = list(by_security.get(security_id, []))
        window = _resolve_window(scoped, start, end)
        if window is None:
            _add_gap(
                gap_for(
                    MissingInput(
                        f"{subject}: 证券 {security_id} 区间 [{start}..{end}] 内行情不足（<2 点）",
                        missing=["prices"],
                        subject=subject,
                    ),
                    kind="benchmark",
                ),
                gaps,
                report,
            )
            continue
        begin, finish = window
        operands = [f"{BENCHMARK_RULES_REL}#{subject}", f"prices({security_id})"]
        outcome = safe_compute(
            lambda bm=benchmark, s=scoped, b=begin, f=finish, sub=subject, ops=operands: compute_benchmark_return(
                bm,
                s,
                actions,
                b,
                f,
                subject=sub,
                operands=ops,
            ),
            kind="benchmark_return",
            subject=subject,
        )
        _collect(outcome, values, gaps, report)

    # 个股口径：每个有行情的证券算一次总回报（真实 DerivedValue，非基准口径）
    for security_id in sorted(by_security):
        scoped = list(by_security[security_id])
        window = _resolve_window(scoped, start, end)
        if window is None:
            continue
        begin, finish = window
        outcome = safe_compute(
            lambda sec=security_id, s=scoped, b=begin, f=finish: compute_total_return(
                s,
                actions,
                b,
                f,
                subject=f"{sec}-{b}..{f}",
                currency="",
                dividends_reinvested=True,
                operands=[f"prices({sec})"],
            ),
            kind="total_return",
            subject=f"{security_id}-{begin}..{finish}",
        )
        _collect(outcome, values, gaps, report)

    if persist:
        report.values_written = append_derived_values(root_path, values)
        report.gaps_written = append_gaps(root_path, gaps)

    report.integrity_violations = assert_derived_integrity(root_path)
    return report


def _resolve_window(
    points: Sequence[PricePoint],
    start: date | None,
    end: date | None,
) -> tuple[date, date] | None:
    """解析区间：显式 `start`/`end` 优先；缺则用该证券行情的 [min, max]。不足 2 点 → None。"""
    scoped = list(points)
    if not scoped:
        return None
    begin = start or min(p.day for p in scoped)
    finish = end or max(p.day for p in scoped)
    in_window = [p for p in scoped if begin <= p.day <= finish]
    if len(in_window) < 2:
        return None
    return begin, finish


def _collect(
    outcome: DerivedValue | ComputeGap,
    values: list[DerivedValue],
    gaps: list[ComputeGap],
    report: DriverReport,
) -> None:
    """按结果类型分派：`DerivedValue` 入 values，`ComputeGap` 入 gaps（**互斥**）。"""
    if isinstance(outcome, ComputeGap):
        _add_gap(outcome, gaps, report)
    else:
        values.append(outcome)
        report.derived_ids.append(outcome.derived_id)


def _add_gap(gap: ComputeGap, gaps: list[ComputeGap], report: DriverReport) -> None:
    """记录一个缺口对象到 `gaps` 与 `report.gap_ids`（**两处必须同时更新**）。

    ★ 曾漏更 `report.gap_ids` —— 于是"缺行情"的缺口被算进 `gaps` 却没进摘要，
      处理器据此判 `degraded=False`（把缺口静默当成功）。本函数是唯一入账口。
    """
    gaps.append(gap)
    report.gap_ids.append(gap.gap_id)


def assert_derived_integrity(root: str | Path) -> list[str]:
    """自检 `derived/derived_values.jsonl`：每行必须带 `formula` + `operands` + `method_version`。

    违例 → 逐条返回人读说明（调用方据此 **exit 1**）。这是**计算层自己的完整性断言**，
    与 `return_guard` 的基准口径断言职责不同（`G-06`：不复制口径校验）。
    """
    violations: list[str] = []
    for idx, row in enumerate(iter_all_values(root), start=1):
        for key in VALID_REQUIRED_FIELDS:
            val = row.get(key)
            if key == "operands":
                if not isinstance(val, list) or not val:
                    violations.append(f"derived_values.jsonl#L{idx} 缺 {key}")
            elif not val:
                violations.append(f"derived_values.jsonl#L{idx} 缺 {key}")
    return violations
