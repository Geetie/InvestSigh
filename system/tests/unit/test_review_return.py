"""`tests/unit/test_review_return.py` —— `Ch10 §D` 复盘收益（`return_guard` 复用 + 口径经 p10）。

覆盖（`06_WS-F` 卡 DoD）：

- **AC-01 真跑通**：`compute_review_return` 在真实入口上可调（含 ok / blocked 两条）；
- **AC-02 `tbd` 路径**：口径未冻结 → `status="blocked_by_caliber"` + `missing` 列出四键；
- **AC-04 断言真拦得住**（逐条反向对照，`G-05`）：
  ① 生效价取「看到消息那天」→ `EffectivePriceViolation`；
  ② 二次扣费 → `BenchmarkCaliberError`；③ 替代指数 → `BenchmarkCaliberError`；
- **AC-05/06 边界**：无行情 / 无基准 / 窗口入参覆盖口径 → 明确降级或明确拒绝，**不崩溃、不返假数字**。

数据纪律：`code_root` 夹具真源为空，本文件**自声明**自己的数据（`G-RC-02`）。
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from conftest import run_gate_inproc
from scripts.benchmark.return_guard import BenchmarkCaliberError
from scripts.compute.contract import CaliberViolation
from scripts.compute.returns import PricePoint
from scripts.review.review_return import (
    CALIBER_KEYS,
    STATUS_BLOCKED_CALIBER,
    STATUS_BLOCKED_NO_BENCHMARK,
    STATUS_BLOCKED_NO_PRICE,
    STATUS_OK,
    EffectivePriceViolation,
    assert_effective_price_next_tradable,
    compute_review_return,
    effective_price,
    nav_diagnostic,
    read_caliber_terms,
)

CLI = "scripts/review/review_return.py"

_FROZEN_TERMS = {
    "signal_effective_price": "next_tradable_point",
    "transaction_cost": "0.002",
    "pre_tax_caliber": "pre_tax",
    "review_window": 30,
}


# ─────────────────────────── 夹具 ───────────────────────────


def _write_jsonl(root: Path, rel: str, rows: list[dict]) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )


def _freeze_p10(root: Path, terms: dict) -> None:
    """把副本的 `rules/freeze.yaml::p10` 置为 `frozen` 并写入具体口径值。"""
    path = root / "rules" / "freeze.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    for row in doc["freeze_params"]:
        if row.get("param_id") == "p10":
            row["freeze_status"] = "frozen"
            row["value"] = {
                "same_start_end": True,
                "currency": "USD",
                "price_kind": "market_price_total_return",
                "caliber_terms": dict(terms),
            }
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _rec_row(*, start_date: str = "2025-01-01") -> dict:
    return {
        "recommendation_id": "rec-nvda-001",
        "security_id": "sec-nvda",
        "company_id": "company-nvidia",
        "action": "buy",
        "horizon": "1Y",
        "start_date": start_date,
        "status": "active",
        "version": 1,
        "recorded_seq": 1,
        "evidence_version_ids": [],
        "assumptions": [],
        "supersedes": None,
        "first_seen_at": None,
        "published_at": None,
        "analyzed_at": None,
    }


def _price(security_id: str, day: str, price: str, *, is_nav: bool = False) -> dict:
    return {"security_id": security_id, "day": day, "price": price, "is_nav": is_nav}


def _benchmark_row(*, fee_deducted_again: bool = False, proxy_index_used: bool = False) -> dict:
    return {
        "benchmark_id": "bm-agix",
        "benchmark_role": "primary",
        "security_id": "sec-agix",
        "return_source": "fund_market_price",
        "proxy_index_used": proxy_index_used,
        "return_basis": {
            "same_start_end": True,
            "currency": "USD",
            "dividends_reinvested": True,
            "price_kind": "market_price_total_return",
            "fee_deducted_again": fee_deducted_again,
        },
    }


def _seed_ok_inputs(root: Path, *, fee_deducted_again: bool = False, proxy_index_used: bool = False) -> None:
    _write_jsonl(root, "facts/recommendations.jsonl", [_rec_row()])
    _write_jsonl(
        root,
        "facts/prices.jsonl",
        [
            # 信号日（2025-01-01）的收盘价必须被排除（禁「看到消息那天的收盘价」）
            _price("sec-nvda", "2025-01-01", "50"),
            _price("sec-nvda", "2025-01-02", "100"),
            _price("sec-nvda", "2025-01-20", "110"),
            _price("sec-nvda", "2025-01-02", "99", is_nav=True),
            _price("sec-nvda", "2025-01-20", "108", is_nav=True),
            _price("sec-agix", "2025-01-02", "200"),
            _price("sec-agix", "2025-01-20", "210"),
        ],
    )
    _write_jsonl(
        root,
        "facts/benchmarks.jsonl",
        [_benchmark_row(fee_deducted_again=fee_deducted_again, proxy_index_used=proxy_index_used)],
    )


# ─────────────────────────── AC-02：口径未冻结（最常见真实路径） ───────────────────────────


def test_frozen_default_reports_blocked_by_caliber(code_root: Path) -> None:
    """默认真源 p10 为 `tbd` ⇒ `blocked_by_caliber` + `missing` 列出四键，**不出数字**。"""
    assert sorted(read_caliber_terms(code_root)) == sorted(CALIBER_KEYS)
    _write_jsonl(code_root, "facts/recommendations.jsonl", [_rec_row()])

    result = compute_review_return("rec-nvda-001", root=code_root)
    assert result.status == STATUS_BLOCKED_CALIBER
    assert list(result.missing) == list(CALIBER_KEYS)
    assert result.total_return is None and result.relative_return is None
    assert not result.computed


# ─────────────────────────── AC-01：真跑通（ok 路径） ───────────────────────────


def test_ok_path_computes_total_and_relative_return(code_root: Path) -> None:
    """口径冻结 + 行情/基准齐备 ⇒ `ok`：绝对 0.1、相对 0.05；净值点不混入市场价总回报。"""
    _freeze_p10(code_root, _FROZEN_TERMS)
    _seed_ok_inputs(code_root)

    result = compute_review_return("rec-nvda-001", root=code_root)
    assert result.status == STATUS_OK, result.as_dict()
    assert result.effective_price_day == date(2025, 1, 2)  # 严格晚于信号日 2025-01-01
    assert result.total_return == Decimal("0.1")
    assert result.benchmark_return == Decimal("0.05")
    assert result.relative_return == Decimal("0.05")
    assert result.nav_diagnostic is None  # 市场价总回报不混净值点（③）
    assert result.formula_refs  # 可追溯：两条 DerivedValue 的 id


def test_nav_diagnostic_is_labelled_role_diagnostic() -> None:
    """③ 净值收益仅作诊断：`nav_diagnostic` 薄包装 `return_guard`，强制 `role=diagnostic`。"""
    labelled = nav_diagnostic("0.07")
    assert labelled["role"] == "diagnostic" and labelled["value"] == "0.07"


# ─────────────────────────── AC-04：三条反向对照（命中即 fail） ───────────────────────────


def test_reverse_control_effective_price_same_day_is_rejected() -> None:
    """① 生效价 = 信号日（看到消息那天的价）⇒ `EffectivePriceViolation`。"""
    with pytest.raises(EffectivePriceViolation):
        assert_effective_price_next_tradable(date(2025, 1, 1), date(2025, 1, 1))
    # 正当对照：严格晚于 ⇒ 放行
    assert_effective_price_next_tradable(date(2025, 1, 1), date(2025, 1, 2))


def test_reverse_control_effective_price_skips_signal_day(code_root: Path) -> None:
    """生效价跳过信号日：信号日有 50，次日 100 ⇒ 取次日的 100（不是 50）。"""
    rec = _rec_row()
    prices = {
        "sec-nvda": [
            PricePoint(day=date(2025, 1, 1), price=Decimal("50")),
            PricePoint(day=date(2025, 1, 2), price=Decimal("100")),
        ]
    }
    chosen = effective_price(rec, prices)
    assert chosen is not None and chosen.day == date(2025, 1, 2) and chosen.price == Decimal("100")


def test_reverse_control_double_fee_is_rejected(code_root: Path) -> None:
    """② 二次扣费 ⇒ `return_guard` 抛 `BenchmarkCaliberError`（不被本模块吞掉）。"""
    _freeze_p10(code_root, _FROZEN_TERMS)
    _seed_ok_inputs(code_root, fee_deducted_again=True)
    with pytest.raises(BenchmarkCaliberError):
        compute_review_return("rec-nvda-001", root=code_root)


def test_reverse_control_proxy_index_is_rejected(code_root: Path) -> None:
    """③ 以公开指数替代基金 ⇒ `return_guard` 抛 `BenchmarkCaliberError`。"""
    _freeze_p10(code_root, _FROZEN_TERMS)
    _seed_ok_inputs(code_root, proxy_index_used=True)
    with pytest.raises(BenchmarkCaliberError):
        compute_review_return("rec-nvda-001", root=code_root)


# ─────────────────────────── AC-05/06：边界（降级 / 拒绝，不崩溃不造假） ───────────────────────────


def test_edge_no_price_degrades(code_root: Path) -> None:
    """无行情 ⇒ `blocked_by_no_price`（`total_return` 保持 None，不返假数字）。"""
    _freeze_p10(code_root, _FROZEN_TERMS)
    _write_jsonl(code_root, "facts/recommendations.jsonl", [_rec_row()])
    result = compute_review_return("rec-nvda-001", root=code_root)
    assert result.status == STATUS_BLOCKED_NO_PRICE
    assert result.total_return is None


def test_edge_no_benchmark_degrades(code_root: Path) -> None:
    """无基准对象（facts 空 + rules 声明清空）⇒ `blocked_by_no_benchmark`。"""
    _freeze_p10(code_root, _FROZEN_TERMS)
    _write_jsonl(code_root, "facts/recommendations.jsonl", [_rec_row()])
    _write_jsonl(
        code_root,
        "facts/prices.jsonl",
        [_price("sec-nvda", "2025-01-02", "100"), _price("sec-nvda", "2025-01-20", "110")],
    )
    (code_root / "rules" / "benchmark.yaml").write_text(
        yaml.safe_dump({"version": 1, "benchmark_objects": []}), encoding="utf-8"
    )
    result = compute_review_return("rec-nvda-001", root=code_root)
    assert result.status == STATUS_BLOCKED_NO_BENCHMARK
    assert result.relative_return is None


def test_edge_window_arg_cannot_override_caliber(code_root: Path) -> None:
    """入参 window ≠ 冻结口径 ⇒ `CaliberViolation`（口径不在本模块，`§D.1`）。"""
    _freeze_p10(code_root, _FROZEN_TERMS)
    _seed_ok_inputs(code_root)
    with pytest.raises(CaliberViolation):
        compute_review_return("rec-nvda-001", window=999, root=code_root)


# ─────────────────────────── AC-03：CLI 真跑通（门禁入口） ───────────────────────────


def test_cli_runs_and_reports_blocked_without_fake_pass(code_root: Path) -> None:
    """CLI：真源仅一条建议、口径未冻结 ⇒ exit 0 且**显式 note `blocked_by_caliber`**。"""
    _write_jsonl(code_root, "facts/recommendations.jsonl", [_rec_row()])
    code, out = run_gate_inproc(CLI, code_root)
    assert code == 0, out
    assert "blocked_by_caliber" in out
