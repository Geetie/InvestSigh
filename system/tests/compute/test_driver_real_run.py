"""`driver` + CLI 真实运行单测（`Ch9 §3.5` 阶段④）。

覆盖 AC-01（真实输入 → 真实 `DerivedValue`，含**真子进程**证据）/ AC-05（缺输入 → 缺口对象）
/ AC-04（完整性违例 → exit 1）。

真实输入：`usAGIX`（KraneShares 人工智能 ETF）真实日线子样（westock MCP 抓取，
落 `tests/compute/fixtures/agix_prices.jsonl`）；真实基准对象取自仓库 `rules/benchmark.yaml`。
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from scripts.compute import driver, store

FIXTURES = Path(__file__).resolve().parent / "fixtures"
AGIX_PRICES = FIXTURES / "agix_prices.jsonl"
START = date(2026, 4, 1)
END = date(2026, 9, 15)
EXPECTED_TOTAL_RETURN = Decimal("44.53") / Decimal("33.11") - Decimal(1)


def test_real_run_writes_true_derived_value(scratch: Path) -> None:
    """AC-01：真读真实 AGIX 行情 + 真实基准对象 → 真 `DerivedValue`（含三要件）。"""
    report = driver.run_derived(scratch, prices_file=AGIX_PRICES, start=START, end=END)
    assert report.ok
    rows = store.read_rows(scratch, store.DERIVED_VALUES_STEM)
    assert rows, "真实运行必须落 DerivedValue"

    benchmark_rows = [r for r in rows if r["derived_id"].startswith("dv-benchmark_return-p01")]
    assert len(benchmark_rows) == 1
    row = benchmark_rows[0]
    assert Decimal(row["value"]) == EXPECTED_TOTAL_RETURN
    assert "fund_market_price" in row["formula"]
    assert row["operands"]
    assert row["method_version"] == "compute-v1"
    assert row["computed_at"]


def test_real_run_persists_gap_when_prices_absent(scratch: Path) -> None:
    """AC-05：`facts/prices.jsonl` 为空 → **缺口对象**（不置 null、不置 0 冒充实值）。"""
    report = driver.run_derived(scratch)          # 无 prices 文件
    assert report.gap_ids, "缺行情必须产出缺口对象"
    gaps = store.read_rows(scratch, store.DERIVED_GAPS_STEM)
    assert gaps
    assert all(g["missing"] for g in gaps)


def test_cli_exits_zero_on_real_run(scratch: Path, cli) -> None:
    """AC-01 的**进程级**证据：真命令行 → exit 0 + 落盘 DerivedValue。"""
    proc = cli(
        "scripts/compute/run_derived.py",
        scratch,
        "--prices-file", str(AGIX_PRICES),
        "--start", START.isoformat(),
        "--end", END.isoformat(),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "== run_derived.py" in proc.stdout
    assert '"values_written": 3' in proc.stdout or '"values_written": 2' in proc.stdout
    rows = store.read_rows(scratch, store.DERIVED_VALUES_STEM)
    assert rows


def test_cli_strict_fails_on_gaps(scratch: Path, cli) -> None:
    proc = cli("scripts/compute/run_derived.py", scratch, "--strict")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "缺口对象" in proc.stdout


def test_cli_fails_on_integrity_violation(scratch: Path, cli) -> None:
    """AC-04 补充：`derived/` 出现缺三要件的行 → CLI **exit 1**（不是 warn）。"""
    bad_row = {"derived_id": "dv-bad", "value": "1", "formula": "", "operands": [], "method_version": ""}
    path = store.values_path(scratch)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bad_row) + "\n", encoding="utf-8")

    proc = cli("scripts/compute/run_derived.py", scratch, "--no-persist")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "缺 formula" in proc.stdout
