"""`history_guard` 单测（`Ch5 §E.2` 历史外推 / `§E.1` 非上市资产 / `§E.5` 覆盖率）。

覆盖 DoD：「每个守卫**注入违例 → exit 非零**」+ 反向对照；
并覆盖 `Ch5 §E.2` 的单测要求："构造 `basis="past_return"` → 断言
`is_historical_extrapolation=True` 且**估值拒绝生成**"。
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from scripts.pricelayer import HistoricalExtrapolation
from scripts.pricelayer.history_guard import (
    BASIS_PAST_RETURN,
    BASIS_TRAILING_RETURN,
    MIN_MODELED_COVERAGE,
    BenchmarkCoverage,
    ForecastInput,
    assert_forward_basis,
    check_benchmark_special_cases,
    is_historical_extrapolation,
)


def _forecast(basis: str, period: str = "FY2027", evidence_period: str = "FY2027") -> ForecastInput:
    return ForecastInput(subject="sec_nvda", basis=basis, period=period, evidence_period=evidence_period)


# ───────────────────── §E.2 历史外推检测 ─────────────────────


def test_past_return_basis_is_historical_extrapolation() -> None:
    """★ `Ch5 §E.2` 逐字单测：`basis="past_return"` → `True` **且估值拒绝生成**。"""
    forecast = _forecast(BASIS_PAST_RETURN)
    assert is_historical_extrapolation(forecast) is True
    with pytest.raises(HistoricalExtrapolation):
        assert_forward_basis(forecast)


def test_trailing_return_basis_is_historical_extrapolation() -> None:
    """`§E.2` 的第二个逐字 token（`trailing_return`）。"""
    assert is_historical_extrapolation(_forecast(BASIS_TRAILING_RETURN)) is True


def test_basis_token_is_matched_by_token_not_substring() -> None:
    """token 全等判定：`forward_uses_past_return_analysis` **不是**历史基准 token。

    ★ 这是本实现相对 `Ch5 §E.2` 第一句（子串判定）的**收敛**，理由见模块 docstring：
      子串判定属 `R-06 ①` 禁的"关键词式判据"（换一种写法即可绕过）。
      真正的穷尽判据是下面的**期间一致性**。
    """
    assert is_historical_extrapolation(_forecast("forward_uses_past_return_analysis")) is False


def test_period_mismatch_is_historical_extrapolation() -> None:
    """`§E.2` 第二条（**结构性**判据）：用历史期推未来期 → `True`。"""
    forecast = _forecast("forward_assumption", period="FY2027", evidence_period="FY2024")
    assert is_historical_extrapolation(forecast) is True
    with pytest.raises(HistoricalExtrapolation):
        assert_forward_basis(forecast)


def test_reverse_control_forward_basis_same_period_passes() -> None:
    """反向对照：forward 依据 + 期间一致 → **放行**（守卫不是恒红）。"""
    forecast = _forecast("forward_assumption", period="FY2027", evidence_period="FY2027")
    assert is_historical_extrapolation(forecast) is False
    assert_forward_basis(forecast)  # 不抛即通过


# ───────────────────── §E.1 / §E.5 基准覆盖 ─────────────────────


def _coverage(**overrides: object) -> BenchmarkCoverage:
    base: dict[str, object] = {
        "benchmark_id": "AGIX",
        "includes_non_listed_assets": False,
        "non_listed_assets": (),
        "holdings_disclosure_lag": None,
        "unverifiable_forecasts": None,
        "sensitivity": (),
        "modeled_coverage": None,
        "unmodeled_parts": (),
        "claims_complete_forecast": False,
    }
    base.update(overrides)
    return BenchmarkCoverage(**base)  # type: ignore[arg-type]


def test_non_listed_assets_require_gap_note() -> None:
    """`Ch5 §E.1`：非上市资产无法独立建模 ⇒ 必须走缺口字段（`gap_note`）。"""
    report = check_benchmark_special_cases(
        _coverage(
            includes_non_listed_assets=True,
            non_listed_assets=({"name": "OpenAI", "value": "tbd"},),
            sensitivity=({"factor": "private_mark", "note": "x"},),
            holdings_disclosure_lag="13F 滞后一个季度",
            unverifiable_forecasts=[],
        )
    )
    assert any("gap_note" in v for v in report.violations)


def test_non_listed_assets_without_sensitivity_is_rejected() -> None:
    """`Ch5 §E.1` / `§J8`：非上市资产必须配 `sensitivity`（缺口 + 敏感性，不硬编点值）。"""
    report = check_benchmark_special_cases(
        _coverage(
            includes_non_listed_assets=True,
            non_listed_assets=({"name": "OpenAI", "gap_note": "无法独立建模"},),
            holdings_disclosure_lag="13F 滞后一个季度",
            unverifiable_forecasts=[],
            sensitivity=(),
        )
    )
    assert any("sensitivity" in v for v in report.violations)


def test_holdings_disclosure_lag_missing_is_rejected() -> None:
    report = check_benchmark_special_cases(
        _coverage(
            includes_non_listed_assets=True,
            non_listed_assets=({"name": "OpenAI", "gap_note": "x"},),
            sensitivity=({"factor": "private_mark"},),
            unverifiable_forecasts=[],
            holdings_disclosure_lag=None,
        )
    )
    assert any("holdings_disclosure_lag" in v for v in report.violations)


def test_unverifiable_forecasts_field_must_be_present() -> None:
    """`Ch5 §E.1`：该字段必须**显式**（可为空列表，但不得整字段缺席）。"""
    report = check_benchmark_special_cases(
        _coverage(
            includes_non_listed_assets=True,
            non_listed_assets=({"name": "OpenAI", "gap_note": "x"},),
            sensitivity=({"factor": "private_mark"},),
            holdings_disclosure_lag="13F lag",
            unverifiable_forecasts=None,
        )
    )
    assert any("unverifiable_forecasts" in v for v in report.violations)


def test_reverse_control_complete_benchmark_passes() -> None:
    """反向对照：四类问题字段齐备 + 覆盖率达标 + 未建模部分显式列出 → **无违例**。"""
    report = check_benchmark_special_cases(
        _coverage(
            includes_non_listed_assets=True,
            non_listed_assets=({"name": "OpenAI", "value": "tbd", "weight": "tbd", "gap_note": "无法独立建模"},),
            sensitivity=({"factor": "private_mark", "note": "±20%"},),
            holdings_disclosure_lag="13F 滞后一个季度",
            unverifiable_forecasts=[],
            modeled_coverage=Decimal("0.85"),
            unmodeled_parts=("非上市持股的私募估值",),
        )
    )
    assert report.violations == [], report.violations


def test_modeled_coverage_below_one_requires_unmodeled_parts() -> None:
    """`Ch5 §E.5`：`modeled_coverage < 1` 时未建模部分必须**显式标注**。"""
    report = check_benchmark_special_cases(_coverage(modeled_coverage=Decimal("0.7")))
    assert any("unmodeled_parts" in v for v in report.violations)


def test_claiming_complete_forecast_below_threshold_is_rejected() -> None:
    """`Ch5 §E.5` + B4（已确认 0.80）：覆盖率不达标却声称完整预测 → 违例。"""
    report = check_benchmark_special_cases(
        _coverage(
            modeled_coverage=Decimal("0.5"),
            unmodeled_parts=["未建模的分部"],
            claims_complete_forecast=True,
        )
    )
    assert any("完整预测" in v for v in report.violations)
    assert MIN_MODELED_COVERAGE == Decimal("0.80")


def test_missing_modeled_coverage_is_noted_not_passed_silently() -> None:
    """`G-03`：`modeled_coverage` 缺席 ⇒ 覆盖率判据**不可判定**，必须记 note。"""
    report = check_benchmark_special_cases(_coverage())
    assert report.violations == []
    assert any("NO_MODELED_COVERAGE" in n for n in report.notes)
    assert any("NO_NON_LISTED_ASSETS" in n for n in report.notes)


# ───────────────────── CLI：注入违例 → exit 非零 + 反向对照 ─────────────────────


def test_cli_rejects_non_listed_assets_without_gap_note(
    scratch: Path, write_jsonl, run_script
) -> None:
    """★ 注入违例：非上市资产条目缺 `gap_note` → CLI **exit 1**。"""
    write_jsonl(
        scratch,
        "benchmarks",
        [
            {
                "benchmark_id": "AGIX",
                "includes_non_listed_assets": True,
                "non_listed_assets": [{"name": "OpenAI", "value": "tbd"}],
                "holdings_disclosure_lag": "13F lag",
                "unverifiable_forecasts": [],
                "sensitivity": [{"factor": "private_mark"}],
            }
        ],
    )
    proc = run_script("scripts/pricelayer/history_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "BENCHMARK-COVERAGE" in proc.stdout


def test_reverse_control_cli_passes_on_complete_benchmark(
    scratch: Path, write_jsonl, run_script
) -> None:
    """反向对照：字段齐备 → **exit 0**。"""
    write_jsonl(
        scratch,
        "benchmarks",
        [
            {
                "benchmark_id": "AGIX",
                "includes_non_listed_assets": True,
                "non_listed_assets": [
                    {"name": "OpenAI", "value": "tbd", "weight": "tbd", "gap_note": "无法独立建模"}
                ],
                "holdings_disclosure_lag": "13F lag",
                "unverifiable_forecasts": [],
                "sensitivity": [{"factor": "private_mark", "note": "±20%"}],
                "modeled_coverage": "0.85",
                "unmodeled_parts": ["非上市持股的私募估值"],
            }
        ],
    )
    proc = run_script("scripts/pricelayer/history_guard.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RESULT: PASS" in proc.stdout


def test_cli_notes_empty_sample_instead_of_passing_silently(
    scratch: Path, run_script
) -> None:
    """`G-03`：真源为空 → **note** 显式记（退出码 0 但注明"无被检对象"）。"""
    proc = run_script("scripts/pricelayer/history_guard.py", scratch, "--no-report")
    assert proc.returncode == 0
    assert "NO_BENCHMARKS" in proc.stdout


def test_reverse_control_reads_unmodeled_keys_from_coverage_profile(
    scratch: Path, write_jsonl, run_script
) -> None:
    """`schema.models.Benchmark.coverage_profile` 是开放 dict 落点 ⇒ 内层键**同样被认**。

    这 5 个键（`holdings_disclosure_lag` / `unverifiable_forecasts` / `modeled_coverage` /
    `unmodeled_parts` / `claims_complete_forecast`）在 `schema.models.Benchmark` 里**没有字段**，
    而 `coverage_profile: dict[str, Any]` 正是本项目对"设计给了键名、模型未封闭建模"的既有约定。
    只认行内平铺会把**合规的** `coverage_profile` 写法误判成"整片缺字段"。
    """
    write_jsonl(
        scratch,
        "benchmarks",
        [
            {
                "benchmark_id": "AGIX",
                "includes_non_listed_assets": True,
                "non_listed_assets": [
                    {"name": "OpenAI", "value": "tbd", "weight": "tbd", "gap_note": "无法独立建模"}
                ],
                "sensitivity": [{"factor": "private_mark", "note": "±20%"}],
                "coverage_profile": {
                    "holdings_disclosure_lag": "13F lag",
                    "unverifiable_forecasts": [],
                    "modeled_coverage": "0.85",
                    "unmodeled_parts": ["非上市持股的私募估值"],
                },
            }
        ],
    )
    proc = run_script("scripts/pricelayer/history_guard.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RESULT: PASS" in proc.stdout


def test_coverage_profile_with_insufficient_coverage_still_rejected(
    scratch: Path, write_jsonl, run_script
) -> None:
    """★ 反例控制：`coverage_profile` 内层**也没给** `unmodeled_parts` 且覆盖率 < 1 → exit 1。

    证明上一条是"内层键被读到"，而不是"内层一律放过"。
    """
    write_jsonl(
        scratch,
        "benchmarks",
        [
            {
                "benchmark_id": "AGIX",
                "includes_non_listed_assets": False,
                "coverage_profile": {"modeled_coverage": "0.60"},
            }
        ],
    )
    proc = run_script("scripts/pricelayer/history_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "BENCHMARK-COVERAGE" in proc.stdout


def test_flat_keys_still_take_precedence_over_coverage_profile(
    scratch: Path, write_jsonl, run_script
) -> None:
    """行内平铺键**优先**于 `coverage_profile`（`Ch5 §E.1` 的字面写法优先）。"""
    write_jsonl(
        scratch,
        "benchmarks",
        [
            {
                "benchmark_id": "AGIX",
                "includes_non_listed_assets": False,
                # 行内给了覆盖率（合规）→ 即便 profile 里写了更低的旧值，也不该按旧值判违例
                "modeled_coverage": "1.0",
                "coverage_profile": {"modeled_coverage": "0.10"},
            }
        ],
    )
    proc = run_script("scripts/pricelayer/history_guard.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
