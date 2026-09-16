"""决策层**真实运行**入口单测（`Ch7 §F` 端到端时序；AC-01 的"真跑通"证据）。

断言的是**进程退出码**与**真实落盘产物**，不是"函数返回了某个列表"：
- 正常 → `exit 0`，`facts/recommendations.jsonl` 真出现一条建议、`index/` 真重建；
- 行情文件缺失 / 缺参数 / **真源输入缺失** → `exit 2`（输入异常，**不静默**）；
- 区间内行情点不足 → 输出**缺口对象**、不生成建议 → 加 `--require-recommendation` 时 `exit 1`。

★ `P7-2` / `P7-3` 根因修复后的两组路径：
- **显式注入**（`--stock-prices/--benchmark-prices`）：由调用方传夹具路径（本文件前几例）；
- **真源默认**（`run_default`）：读 `<root>/facts/prices.jsonl` + `facts/benchmarks.jsonl`，
  `run_date` 作 as-of 上界、`scope` 选取目标证券。**空 root → 无产出**（不伪造）。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from decision_builders import AGIX_PRICES, DEMO_STOCK_PRICES
from schema.store import read_models

SCRIPT = "scripts/decision/run_decide.py"

# 真源行情（`facts/prices.jsonl` 行格式：security_id + day + price；`Ch9 §N9.1-19`）
_DEMO_TRUTH_ROWS = [
    {"security_id": "usDEMO", "day": "2026-04-01", "price": "100.00", "is_nav": False},
    {"security_id": "usDEMO", "day": "2026-05-15", "price": "140.00", "is_nav": False},
    {"security_id": "usDEMO", "day": "2026-06-01", "price": "150.00", "is_nav": False},
    {"security_id": "usDEMO", "day": "2026-09-15", "price": "200.00", "is_nav": False},
    {"security_id": "usAGIX", "day": "2026-04-01", "price": "33.11", "is_nav": False},
    {"security_id": "usAGIX", "day": "2026-05-15", "price": "43.60", "is_nav": False},
    {"security_id": "usAGIX", "day": "2026-06-01", "price": "49.40", "is_nav": False},
    {"security_id": "usAGIX", "day": "2026-09-15", "price": "44.53", "is_nav": False},
]


def _write_truth(scratch: Path) -> None:
    """把真源行情与基准对象写进 scratch 的 `facts/`（`run_default` 读它们）。"""
    facts = scratch / "facts"
    facts.mkdir(parents=True, exist_ok=True)
    (facts / "prices.jsonl").write_text(
        "\n".join(json.dumps(r) for r in _DEMO_TRUTH_ROWS) + "\n", encoding="utf-8"
    )
    (facts / "benchmarks.jsonl").write_text(
        json.dumps({"benchmark_id": "bm-agix", "benchmark_role": "primary", "security_id": "usAGIX"}) + "\n",
        encoding="utf-8",
    )


def _last_json_line(stdout: str) -> dict:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"stdout 中没有 JSON 摘要:\n{stdout}")


# ───────────────────────── 显式注入路径（调用方传夹具） ─────────────────────────


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


def test_cli_rerun_same_window_does_not_duplicate(scratch: Path, cli) -> None:
    """`P7-4`：同窗口 + 同规则版本连跑 2 次 → 真源仍只有 1 行（幂等，非追加重复）。"""
    args = (SCRIPT, scratch, "--stock-prices", str(DEMO_STOCK_PRICES), "--benchmark-prices", str(AGIX_PRICES))
    first = cli(*args)
    second = cli(*args)
    assert first.returncode == 0 and second.returncode == 0
    rows = read_models(scratch, "recommendations")
    assert len(rows) == 1
    # 第二次幂等命中 → 本次**无新增** → `recommendation_ids` 为空（如实回传，非伪造）
    assert _last_json_line(second.stdout)["recommendation_ids"] == []


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


# ───────────────────────── 真源默认路径（`P7-2` 修复） ─────────────────────────


def test_run_default_on_empty_root_produces_nothing(scratch: Path) -> None:
    """★ `P7-1`/`P7-2`：**空 root**（无真源行情）→ `run_default` **不产任何建议**、如实降级。"""
    from scripts.decision.run_decide import run_default

    report = run_default(scratch)
    assert report.recommendation_ids == ()
    assert report.degraded is True
    assert report.signals_emitted == 0
    assert any(g.startswith("inputs_unavailable") for g in report.gaps)
    assert not (scratch / "facts" / "recommendations.jsonl").exists()


def test_run_default_reads_truth_source_and_emits_buy(scratch: Path) -> None:
    """真源有行情 + 基准对象 → 真算收益 → 真出建议（`Ch7 §F`；收益由 `compute` 算出）。"""
    from scripts.decision.run_decide import run_default

    _write_truth(scratch)
    report = run_default(scratch)
    assert report.degraded is False
    assert report.action == "buy"
    assert report.recommendation_ids == ("rec-usDEMO-2026-04-01",)
    assert report.window == ("2026-04-01", "2026-09-15")
    rows = read_models(scratch, "recommendations")
    assert [r.recommendation_id for r in rows] == ["rec-usDEMO-2026-04-01"]


def test_run_default_depends_on_root(scratch: Path) -> None:
    """**`P7-2` 证据**：同一函数传**不同 root** → **不同结果**（不再忽略 `root`）。"""
    from scripts.decision.run_decide import run_default

    empty_root = scratch
    truth_root = scratch.parent / "second-root"
    truth_root.mkdir(parents=True, exist_ok=True)
    _write_truth(truth_root)

    empty_report = run_default(empty_root)
    truth_report = run_default(truth_root)
    assert empty_report.recommendation_ids == () and empty_report.degraded is True
    assert truth_report.recommendation_ids == ("rec-usDEMO-2026-04-01",) and truth_report.degraded is False


def test_run_default_run_date_bounds_window_and_scope_selects_security(scratch: Path) -> None:
    """`P7-3`：`run_date` 作 as-of 上界、`scope` 选取目标证券 —— 二者**真实生效**。"""
    from scripts.decision.run_decide import run_default

    _write_truth(scratch)
    # run_date 落在窗口中部 → finish 上界 = run_date（不同窗口 → review_date 不同）
    mid = run_default(scratch, run_date=date(2026, 6, 1))
    assert mid.degraded is False
    assert mid.window == ("2026-04-01", "2026-06-01")
    # run_date 早于首日 → 无可用窗口 → **无产出**（as-of 语义，不拿未来数据充数）
    early = run_default(scratch, run_date=date(2026, 1, 1))
    assert early.recommendation_ids == () and early.degraded is True
    # scope 指向一个不存在的证券 → 仍按默认唯一非基准证券选取（scope 未命中不误选）
    scoped = run_default(scratch, scope="usDEMO")
    assert scoped.recommendation_ids == ("rec-usDEMO-2026-04-01",)


def test_cli_truth_mode_exits_2_on_empty_root(scratch: Path, cli) -> None:
    """`P7-6`：空 root（无 `--stock-prices`）→ **可读**输入缺失报错 + `exit 2`（非抛栈）。"""
    proc = cli(SCRIPT, scratch)
    assert proc.returncode == 2
    assert "INPUT-ERROR" in proc.stderr
    assert "inputs_unavailable" in proc.stderr


def test_cli_truth_mode_emits_buy_from_truth(scratch: Path, cli) -> None:
    _write_truth(scratch)
    proc = cli(SCRIPT, scratch, "--run-date", "2026-09-30")
    assert proc.returncode == 0, proc.stderr
    summary = _last_json_line(proc.stdout)
    assert summary["action"] == "buy"
    assert summary["window"] == ["2026-04-01", "2026-09-15"]
    assert summary["recommendation_ids"] == ["rec-usDEMO-2026-04-01"]
