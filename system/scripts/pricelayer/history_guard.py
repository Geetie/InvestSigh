#!/usr/bin/env python3
"""`history_guard.py` —— **历史外推检测** + AGIX 基准特殊处理（`Ch5 §E.1/§E.2/§E.5`）。

## 逐字依据

1. **"用历史外推未来"的程序检测**（`Ch5 §E.2` 逐字伪码）：

   ```python
   def is_historical_extrapolation(forecast):
       if "past_return" in forecast.basis or forecast.basis == "trailing_return":
           return True                                    # 用历史涨幅
       if forecast.period != forecast.evidence_period:    # 用历史期推未来期
           return True
       return False
   ```

   `Ch5 §E.2` 逐字处置：「**违规即拒绝**（`N5.4-04`）：`forecast.basis` 引用 `past_return`，
   或 `forecast.period` 与证据期间不匹配 → 拒绝。**预期收益必须来自 forward assumptions；
   历史仅作诊断**」。

   ★ **与 `CONVENTIONS.md::R-06 ①` 的张力（如实登记，已收敛，不自行裁决设计）**：
     §E.2 第一句的 `"past_return" in forecast.basis` 是**子串判定**——正是 R-06 ① 禁的
     "关键词式判据"（换一种写法即可绕过）。而 §E.2 第二句 `forecast.basis == "trailing_return"`
     已是**枚举全等**语义。本实现按第二句收敛：`basis` 当**token 字段**（纪律 5 命名规范）
     做**全等**判定，`past_return` / `trailing_return` 两个 token 逐字保留。
     ⇒ 该收敛写进报告"待裁定"（若需求方要求逐字子串语义，请明示）。
   ★ **真正的穷尽判据是第二条**（`period != evidence_period`）：它是**结构性**判定，
     不依赖 `basis` 怎么写 —— 换任何词形都拦得住。

2. **AGIX 特殊问题 → 字段**（`Ch5 §E.1` 逐字四行）：

   | 问题 | 字段（`benchmarks` 新增） |
   |---|---|
   | 非上市资产无法独立建模 | `non_listed_assets{value, weight, gap_note}` |
   | 公开持仓披露延迟 | `holdings_disclosure_lag` |
   | 无法独立核验的预测 | `unverifiable_forecasts[]` |
   | 敏感性 | `sensitivity[]` |

   `Ch5 §E.1` 末句："ETF 不套用个股'赚钱机制'链路，非上市资产走**缺口/敏感性**字段"
   （`Ch5 §J8`："缺口 + 敏感性，**不硬编点值**"）。

3. **未建模部分覆盖率**（`Ch5 §E.5` 逐字）：`benchmarks.modeled_coverage` + `unmodeled_parts[]`；
   「未建模部分**显式标注**；`modeled_coverage < 1` 时不得声称'完成整个基金预测'」（`N5.4-05`）。
   阈值取 `00_待拍板项清单` **B4（已确认）**："已建模业务覆盖 ≥ 80%，否则不得称'完整预测'"。

## CLI

```
python system/scripts/pricelayer/history_guard.py [code_root]
```

退出码 `0` 放行 / `1` 命中违例 / `2` 输入异常（复用 `_common.run_checker`）。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if __package__:
    from . import HistoricalExtrapolation, PriceLayerError
else:  # 直接以脚本方式运行（CLI 出口；仓库既有守卫都是这种调用方式）
    from scripts.pricelayer import HistoricalExtrapolation, PriceLayerError

BASIS_PAST_RETURN = "past_return"
BASIS_TRAILING_RETURN = "trailing_return"
"""`Ch5 §E.2` **逐字**的两个历史基准 token（`"past_return"` / `"trailing_return"`）。"""

HISTORICAL_BASIS_TOKENS: frozenset[str] = frozenset({BASIS_PAST_RETURN, BASIS_TRAILING_RETURN})
"""历史基准 token 的封闭集合（`Ch5 §E.2` 逐字两条；按 token **全等**判定，见模块 docstring 的张力登记）。"""

MIN_MODELED_COVERAGE = Decimal("0.80")
"""未建模覆盖率阈值（`00_待拍板项清单` **B4 已确认**："已建模业务覆盖 ≥ 80%，否则不得称'完整预测'"；`Ch5 §E.5` / `J10`）。"""

NON_LISTED_ASSET_REQUIRED_KEYS: tuple[str, ...] = ("gap_note",)
"""`Ch5 §E.1` 的 `non_listed_assets{value, weight, gap_note}` 里**必须存在**的键。

★ 只强制 `gap_note`（"缺口"字段）：`value`/`weight` 的**内层语义设计未给**
  （§E.1 只列键名），按 `R-04` 不自行裁决 —— 缺 `value`/`weight` 记为 note 而非违例。
"""


class HistoryGuardError(PriceLayerError):
    """历史外推 / 基准覆盖判定的**输入结构**错误。"""


# ───────────────────────── 历史外推检测（`Ch5 §E.2`） ─────────────────────────


@dataclass(frozen=True)
class ForecastInput:
    """待检测的收益预测（`Ch5 §E.2` 的三个字段逐字）。

    | 字段 | 语义 |
    |---|---|
    | `basis` | 预测**依据**（token 字段；`past_return` / `trailing_return` 为历史基准） |
    | `period` | 预测**针对的期间** |
    | `evidence_period` | **证据所在的期间** |
    """

    subject: str
    basis: str
    period: str
    evidence_period: str


def _normalized_basis(basis: str) -> str:
    """把 `basis` 归一成 token（去空白 + 小写）后做**全等**比较的依据。

    ★ 为什么归一而不做子串匹配：见模块 docstring 的 `R-06 ①` 张力登记。
    """
    return basis.strip().lower()


def is_historical_extrapolation(forecast: ForecastInput) -> bool:
    """`Ch5 §E.2` 的判定（逐字语义）：用历史涨幅 **或** 用历史期推未来期 → `True`。

    - ① `basis` 归一同等于 `past_return` / `trailing_return`（`§E.2` 逐字 token）；
    - ② `period != evidence_period`（**结构性**判据：证据期间与预测期间不一致）。
    """
    if _normalized_basis(forecast.basis) in HISTORICAL_BASIS_TOKENS:
        return True
    return forecast.period != forecast.evidence_period


def assert_forward_basis(forecast: ForecastInput) -> None:
    """**违规即拒绝**（`Ch5 §E.2` / `N5.4-04`）：命中历史外推 → `HistoricalExtrapolation`。

    `Ch5 §E.2`："预期收益必须来自 forward assumptions；历史仅作诊断" ⇒ 估值/预测**不得生成**。
    """
    if is_historical_extrapolation(forecast):
        reason = (
            f"basis={forecast.basis!r} 属历史基准（Ch5 §E.2 逐字 token）"
            if _normalized_basis(forecast.basis) in HISTORICAL_BASIS_TOKENS
            else f"预测期间 {forecast.period!r} 与证据期间 {forecast.evidence_period!r} 不一致"
        )
        raise HistoricalExtrapolation(
            f"{forecast.subject}: 用历史外推未来（{reason}）—— 违规即拒绝（Ch5 §E.2 / N5.4-04）"
        )


# ───────────────────────── AGIX 基准特殊处理（`Ch5 §E.1` / `§E.5`） ─────────────────────────


@dataclass(frozen=True)
class BenchmarkCoverage:
    """AGIX（ETF 基准）的**覆盖与缺口**输入（`Ch5 §E.1` 四字段 + `§E.5` 两字段）。

    字段名逐字取 `Ch5 §E.1` / `§E.5`，其中 `holdings_disclosure_lag` / `unverifiable_forecasts` /
    `modeled_coverage` / `unmodeled_parts` **尚未进 `schema.models.Benchmark`** ⇒ 本层以**输入对象**
    承载（不改共享 schema；schema 缺口已登记待裁定）。
    """

    benchmark_id: str
    includes_non_listed_assets: bool = False
    non_listed_assets: Sequence[Any] = ()
    holdings_disclosure_lag: Any = None
    unverifiable_forecasts: Sequence[Any] | None = None
    sensitivity: Sequence[Any] = ()
    modeled_coverage: Decimal | None = None
    unmodeled_parts: Sequence[Any] = ()
    claims_complete_forecast: bool = False


@dataclass
class CoverageReport:
    """基准覆盖检查结果（违例 + 显式 note）。"""

    violations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations


def _as_entries(raw: Sequence[Any] | Mapping[str, Any] | None) -> list[Any]:
    """把 `non_listed_assets` 的两种合法形态（单条 mapping / 列表）统一成列表。"""
    if raw is None:
        return []
    if isinstance(raw, Mapping):
        return [raw]
    return list(raw)


def check_benchmark_special_cases(
    coverage: BenchmarkCoverage,
    *,
    min_modeled_coverage: Decimal = MIN_MODELED_COVERAGE,
) -> CoverageReport:
    """`Ch5 §E.1` + `§E.5` 的覆盖检查（**每项可判定、可定位**，`G-03` 空样本记 note）。

    逐项判据（都锚在节号上）：

    | # | 判据 | 依据 |
    |---|---|---|
    | ① | 含非上市资产却无 `non_listed_assets` 条目 | `§E.1`（非上市资产无法独立建模 → 走字段） |
    | ② | 某非上市资产条目缺 `gap_note` | `§E.1` 的 `non_listed_assets{value, weight, gap_note}` |
    | ③ | 含非上市资产却无 `sensitivity` | `§E.1`（敏感性）+ `§J8`（缺口 + 敏感性，不硬编点值） |
    | ④ | 含非上市资产却缺 `holdings_disclosure_lag` | `§E.1`（公开持仓披露延迟） |
    | ⑤ | 含非上市资产却**未给出** `unverifiable_forecasts` 字段（`None`） | `§E.1`（无法独立核验的预测） |
    | ⑥ | `modeled_coverage < 1` 却无 `unmodeled_parts` | `§E.5`（未建模部分显式标注） |
    | ⑦ | 声称"完整预测"且 `modeled_coverage < min_modeled_coverage` | `§E.5` + `00_待拍板项清单` B4 |
    """
    report = CoverageReport()
    report.checked.append("benchmark_special_cases")

    entries = _as_entries(coverage.non_listed_assets)
    if coverage.includes_non_listed_assets:
        if not entries:
            report.violations.append(
                f"{coverage.benchmark_id}: 声明含非上市资产但 non_listed_assets 为空 —— "
                "非上市资产无法独立建模，必须走缺口字段（Ch5 §E.1）"
            )
        for index, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                report.notes.append(
                    f"NON_LISTED_ENTRY_NOT_MAPPING: {coverage.benchmark_id} 第 {index} 条非上市资产"
                    "不是映射，键名判定跳过（G-03）"
                )
                continue
            for key in NON_LISTED_ASSET_REQUIRED_KEYS:
                if not entry.get(key):
                    report.violations.append(
                        f"{coverage.benchmark_id}: 非上市资产第 {index} 条缺 {key!r} —— "
                        "Ch5 §E.1（non_listed_assets{value, weight, gap_note}）"
                    )
            if not entry.get("value") or not entry.get("weight"):
                report.notes.append(
                    f"NON_LISTED_INNER_KEY_ABSENT: {coverage.benchmark_id} 第 {index} 条未给 "
                    "value/weight —— 设计只列了键名、未给内层语义，不判违例（R-04）"
                )
        if not list(coverage.sensitivity):
            report.violations.append(
                f"{coverage.benchmark_id}: 含非上市资产但 sensitivity 为空 —— "
                "非上市资产走缺口 + **敏感性**（Ch5 §E.1 / §J8）"
            )
        if coverage.holdings_disclosure_lag is None:
            report.violations.append(
                f"{coverage.benchmark_id}: 缺 holdings_disclosure_lag —— "
                "公开持仓披露延迟必须显式标注（Ch5 §E.1）"
            )
        if coverage.unverifiable_forecasts is None:
            report.violations.append(
                f"{coverage.benchmark_id}: 缺 unverifiable_forecasts 字段（可为空列表，但必须显式）—— "
                "无法独立核验的预测须有落点（Ch5 §E.1）"
            )
    else:
        report.notes.append(
            f"NO_NON_LISTED_ASSETS: {coverage.benchmark_id} 声明不含非上市资产，①②③④⑤ 不适用（非'已验证'）"
        )

    coverage_value = coverage.modeled_coverage
    if coverage_value is None:
        report.notes.append(
            f"NO_MODELED_COVERAGE: {coverage.benchmark_id} 未给 modeled_coverage —— "
            "⑥⑦ 不可判定（G-03：不得把'无被检对象'当'已验证'）"
        )
    else:
        if coverage_value < 1 and not list(coverage.unmodeled_parts):
            report.violations.append(
                f"{coverage.benchmark_id}: modeled_coverage={coverage_value} < 1 但未列 "
                "unmodeled_parts —— 未建模部分必须显式标注（Ch5 §E.5 / N5.4-05）"
            )
        if coverage.claims_complete_forecast and coverage_value < min_modeled_coverage:
            report.violations.append(
                f"{coverage.benchmark_id}: modeled_coverage={coverage_value} < {min_modeled_coverage} "
                "却声称完整预测 —— 不得声称'完成整个基金预测'（Ch5 §E.5 / B4）"
            )
    return report


# ───────────────────────── 守卫：真源扫描（CLI 承载面） ─────────────────────────

NOTE_NO_BENCHMARKS = "NO_BENCHMARKS"
_BENCHMARK_COVERAGE_KEYS = (
    "includes_non_listed_assets",
    "non_listed_assets",
    "holdings_disclosure_lag",
    "unverifiable_forecasts",
    "sensitivity",
    "modeled_coverage",
    "unmodeled_parts",
    "claims_complete_forecast",
)


_COVERAGE_PROFILE_KEYS = (
    "holdings_disclosure_lag",
    "unverifiable_forecasts",
    "modeled_coverage",
    "unmodeled_parts",
    "claims_complete_forecast",
)
"""`Ch5 §E.1` / `§E.5` 点名、但 `schema.models.Benchmark` **未建模**的 5 个键。

★ 落点存在**设计/schema 的口径差**（本流不擅改 `schema/**`）：
  - `Ch5 §E.1`（"字段（`benchmarks` **新增**）"）/ `§E.5`（`benchmarks.modeled_coverage`）读起来是**行内平铺键**；
  - 而 `schema/models.py::Benchmark.coverage_profile: dict[str, Any]` 是本项目对"设计给了键名、
    模型未封闭建模"的**既有开放 dict 约定**（见 `models.py` 对 `BusinessMechanism.cost_structure` 的说明）。
故本流**两边都认**：行内平铺键优先，其次读 `coverage_profile` 内层。裁定后只需删掉其中一路。
"""


def _coverage_value(row: Mapping[str, Any], key: str) -> Any:
    """按「行内平铺 → `coverage_profile` 内层」的顺序取一个未建模的覆盖率键。"""
    if key in row:
        return row[key]
    profile = row.get("coverage_profile")
    if isinstance(profile, Mapping):
        return profile.get(key)
    return None


def _coverage_from_row(row: Mapping[str, Any]) -> BenchmarkCoverage:
    """把 `facts/benchmarks.jsonl` 的一行投影成 `BenchmarkCoverage`（缺键 → 缺省值）。

    前 3 个键（`includes_non_listed_assets` / `non_listed_assets` / `sensitivity`）是
    `schema.models.Benchmark` 的**真实字段** ⇒ 只读行内；后 5 个走 `_coverage_value`（见上）。
    """
    modeled_raw = _coverage_value(row, "modeled_coverage")
    return BenchmarkCoverage(
        benchmark_id=str(row.get("benchmark_id") or "<no-benchmark_id>"),
        includes_non_listed_assets=bool(row.get("includes_non_listed_assets")),
        non_listed_assets=row.get("non_listed_assets") or (),
        holdings_disclosure_lag=_coverage_value(row, "holdings_disclosure_lag"),
        unverifiable_forecasts=_coverage_value(row, "unverifiable_forecasts"),
        sensitivity=row.get("sensitivity") or (),
        modeled_coverage=(None if modeled_raw in (None, "") else Decimal(str(modeled_raw))),
        unmodeled_parts=_coverage_value(row, "unmodeled_parts") or (),
        claims_complete_forecast=bool(_coverage_value(row, "claims_complete_forecast")),
    )


def check(root: str | Path) -> Any:
    """扫描 `facts/benchmarks.jsonl`：非上市资产 / 披露延迟 / 未可核验预测 / 覆盖率。

    ★ 空样本 → 显式 note（`G-03`），**不**判成"已验证"。
    """
    from scripts._common import CheckReport, Violation
    from schema.store import read_records

    root_path = Path(root)
    report = CheckReport(checker="pricelayer_history_guard")
    rows = read_records(root_path, "benchmarks")
    report.scanned["benchmarks"] = len(rows)
    report.scanned["coverage_keys"] = len(_BENCHMARK_COVERAGE_KEYS)
    if not rows:
        report.notes.append(f"{NOTE_NO_BENCHMARKS}: facts/benchmarks.jsonl 无行（非'已验证'）")
        return report

    for row in rows:
        coverage = _coverage_from_row(row)
        result = check_benchmark_special_cases(coverage)
        report.notes.extend(result.notes)
        for text in result.violations:
            report.violations.append(Violation("BENCHMARK-COVERAGE", text))
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """CLI：`python system/scripts/pricelayer/history_guard.py [code_root]`。"""
    from scripts._common import run_checker

    return run_checker("pricelayer_history_guard", check, argv)


if __name__ == "__main__":  # pragma: no cover - CLI 出口
    raise SystemExit(main())
