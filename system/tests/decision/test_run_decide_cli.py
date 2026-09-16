"""决策层**真实运行**入口单测（`Ch7 §F` 端到端时序；AC-01 的"真跑通"证据）。

断言的是**进程退出码**与**真实落盘产物**，不是"函数返回了某个列表"：
- 正常 → `exit 0`，`facts/recommendations.jsonl` 真出现一条建议、`index/` 真重建；
- 行情文件缺失 / 缺参数 → `exit 2`（输入异常，**不静默**）；
- 区间内行情点不足 → 输出**缺口对象**、不生成建议 → 加 `--require-recommendation` 时 `exit 1`。
"""

from __future__ import annotations

import json
from pathlib import Path

from decision_builders import AGIX_PRICES, DEMO_STOCK_PRICES
from schema.store import read_models

SCRIPT = "scripts/decision/run_decide.py"


def _last_json_line(stdout: str) -> dict:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"stdout 中没有 JSON 摘要:\n{stdout}")


def test_cli_runs_and_emits_buy_recommendation(scratch: Path, cli) -> None:
    proc = cli(
        SCRIPT,
        scratch,
        "--stock-prices",
        str(DEMO_STOCK_PRICES),
        "--benchmark-prices",
        str(AGIX_PRICES),
        "--company-id",
        "co-demo",
        "--security-id",
        "usDEMO",
    )
    assert proc.returncode == 0, proc.stderr
    summary = _last_json_line(proc.stdout)
    assert summary["action"] == "buy"
    assert summary["signals_emitted"] == 1
    assert summary["degraded"] is False
    assert summary["recommendation_ids"]

    rows = read_models(scratch, "recommendations")
    assert len(rows) == 1
    assert (scratch / "index" / "facts.sqlite").exists()


def test_cli_exit_2_when_prices_file_missing(scratch: Path, cli) -> None:
    proc = cli(
        SCRIPT,
        scratch,
        "--stock-prices",
        str(scratch / "does-not-exist.jsonl"),
        "--benchmark-prices",
        str(AGIX_PRICES),
    )
    assert proc.returncode == 2
    assert "INPUT-ERROR" in proc.stderr


def test_cli_exit_2_when_required_flags_absent(scratch: Path, cli) -> None:
    proc = cli(SCRIPT, scratch)
    assert proc.returncode == 2
    assert "INPUT-ERROR" in proc.stderr


def test_cli_require_recommendation_exits_1_on_gap(scratch: Path, cli) -> None:
    """区间内行情点不足 → 缺口对象 → 不出建议 → `--require-recommendation` 时 `exit 1`。"""
    proc = cli(
        SCRIPT,
        scratch,
        "--stock-prices",
        str(DEMO_STOCK_PRICES),
        "--benchmark-prices",
        str(AGIX_PRICES),
        "--start",
        "2026-09-10",
        "--end",
        "2026-09-15",
        "--require-recommendation",
    )
    assert proc.returncode == 1, proc.stderr
    summary = _last_json_line(proc.stdout)
    assert summary["recommendation_ids"] == []
    assert summary["degraded"] is True
    assert not (scratch / "facts" / "recommendations.jsonl").exists()


def test_run_default_uses_repo_inputs(scratch: Path) -> None:
    """默认输入（真实 AGIX 基准 + 个股夹具）均可解析；`run_default` 在轻量根上产出建议。"""
    from scripts.decision.run_decide import run_default

    report = run_default(scratch)
    assert report.degraded is False
    assert report.action == "buy"
    assert report.recommendation_ids
