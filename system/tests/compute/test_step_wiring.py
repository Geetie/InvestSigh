"""计算层对编排器的**接线接缝**单测（AC-03，`Ch9 §3.5` 阶段④）。

★ 诚实标注：真实 `pipeline.py` 的 step 4/5/6 处理器属阶段②③（张力 `T-08`），本批次
  **不改共享文件**。故这里证明的是：**真 `Pipeline` 对象**能注册并真调用计算层处理器，
  且产物 `DerivedValue` 真的落盘。
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from scripts.compute import step, store

SYSTEM_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "agix_prices.jsonl"


def _prepare(scratch: Path, *, with_prices: bool) -> None:
    shutil.copyfile(SYSTEM_ROOT / "rules" / "pipeline.yaml", scratch / "rules" / "pipeline.yaml")
    if with_prices:
        shutil.copyfile(FIXTURE, scratch / "facts" / "prices.jsonl")


def test_handler_returns_step_outcome_with_produced_ids(scratch: Path) -> None:
    _prepare(scratch, with_prices=True)
    handler = step.make_derived_handler(scratch)
    outcome = handler(date(2026, 9, 16), "full")
    assert outcome.produced, "有真实行情时处理器应产出 DerivedValue 引用"
    assert outcome.signals_emitted == 0        # 计算不产交易信号（Ch1 §D.3 反 KPI）
    assert outcome.degraded is False


def test_handler_marks_degraded_when_inputs_missing(scratch: Path) -> None:
    _prepare(scratch, with_prices=False)
    outcome = step.make_derived_handler(scratch)(date(2026, 9, 16), "full")
    assert outcome.produced == []
    assert outcome.degraded is True            # 缺口是正常态，但**显式**标记（不静默）


def test_real_pipeline_registers_and_invokes_compute(scratch: Path) -> None:
    """真 `Pipeline` 注册计算层处理器 → 调用它 → `derived/` 真落盘（AC-03 接线证据）。"""
    _prepare(scratch, with_prices=True)
    from scripts.orchestrate.pipeline import Pipeline

    pipeline = Pipeline(scratch)
    step.register_into(pipeline, step_no=5)
    assert 5 in pipeline._step_handlers

    outcome = pipeline._step_handlers[5](date(2026, 9, 16), "full")
    assert outcome.produced
    rows = store.read_rows(scratch, store.DERIVED_VALUES_STEM)
    assert {r["derived_id"] for r in rows}.issuperset(set(outcome.produced))
