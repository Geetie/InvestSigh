"""`return_guard` 接线单测（AC-04：注入违例 → **真进程 exit 1**，不是 warn）。

★ 本文件**只跑仓库既有**的 `scripts/benchmark/return_guard.py`（已注册进 `run_all_gates.py`），
  证明计算层的基准口径**复用同一真源**（`G-06`），而非新写第二套校验。
"""

from __future__ import annotations

import inspect
from pathlib import Path

import yaml

from scripts.compute import returns

RETURN_GUARD = "scripts/benchmark/return_guard.py"


def _load_rules(root: Path) -> dict:
    return yaml.safe_load((root / "rules" / "benchmark.yaml").read_text(encoding="utf-8"))


def _save_rules(root: Path, doc: dict) -> None:
    (root / "rules" / "benchmark.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def test_return_guard_passes_on_pristine_rules(scratch: Path, cli) -> None:
    """反向对照（`G-05`）：未注入时门禁**放行**（否则"拦得住"没有意义）。"""
    proc = cli(RETURN_GUARD, scratch)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_return_guard_blocks_proxy_index_substitution(scratch: Path, cli) -> None:
    """① 注入：用公开指数替代基金 → `return_guard` **exit 1**。"""
    doc = _load_rules(scratch)
    doc["benchmark_objects"][0]["return_source"] = "proxy_index"
    doc["benchmark_objects"][0]["proxy_index_used"] = True
    _save_rules(scratch, doc)

    proc = cli(RETURN_GUARD, scratch)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "N3.4-05" in proc.stdout


def test_return_guard_blocks_double_fee(scratch: Path, cli) -> None:
    """② 注入：二次扣费 → `return_guard` **exit 1**。"""
    doc = _load_rules(scratch)
    doc["benchmark_objects"][0]["return_basis"]["fee_deducted_again"] = True
    _save_rules(scratch, doc)

    proc = cli(RETURN_GUARD, scratch)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "N3.4-05/07" in proc.stdout


def test_return_guard_blocks_nav_role_upgrade(scratch: Path, cli) -> None:
    """③ 注入：把净值收益升格为非诊断 → `return_guard` **exit 1**。"""
    doc = _load_rules(scratch)
    doc["return_guard"]["nav_return_role"] = "relative"
    _save_rules(scratch, doc)

    proc = cli(RETURN_GUARD, scratch)
    assert proc.returncode == 1, proc.stdout + proc.stderr


def test_compute_delegates_benchmark_caliber_to_return_guard() -> None:
    """`G-06`：`compute_benchmark_return` 的实现体**必须**经 `return_guard`（无第二套校验）。"""
    source = inspect.getsource(returns.compute_benchmark_return)
    assert "return_guard" in source
    assert "benchmark_return" in source
