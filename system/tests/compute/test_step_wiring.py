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


def test_handler_produced_empty_on_idempotent_second_run(scratch: Path) -> None:
    """★ C-03：幂等**第二次**运行 → `produced == []`（G1-05 空执行守卫不得被击穿）。

    `produced` 必须是**本次真正新增落库**的对象引用，而非"全部重算 id"——
    曾用 `report.derived_ids`，导致 `values_written=0` 的运行仍回传非空 `produced`。

    ★ **`G-44` 补强**：重跑时 `produced` 为空**必须**同时说明"我确实考察过了"，
      即 `skipped` 非空且 = 首轮那批 `derived_id`。缺了它，`chain_steps` 的
      `_declare_incomplete_when_empty`（恰好只包装 step 5/6）会把这一步判成
      `incomplete_reason` → `STATUS_GAP` → **整轮 blocked**（实测：连续第二次 `run_daily` 必然 blocked）。
    """
    _prepare(scratch, with_prices=True)
    handler = step.make_derived_handler(scratch)
    first = handler(date(2026, 9, 16), "full")
    assert first.produced, "首轮应真正落库并回传对象引用"
    assert first.skipped == [], "首轮不该有幂等命中（否则下面的判别式失去判别力）"
    rows_after_first = store.read_rows(scratch, store.DERIVED_VALUES_STEM)
    assert {r["derived_id"] for r in rows_after_first} == set(first.produced), "首轮 produced = 实际落库集合"
    second = handler(date(2026, 9, 16), "full")
    assert second.produced == [], "幂等重跑未新增落库 → produced 必须为空"
    assert len(store.read_rows(scratch, store.DERIVED_VALUES_STEM)) == len(rows_after_first), "第二轮不新增行"
    assert set(second.skipped) == set(first.produced), (
        f"★ 重跑：skipped 应恰为首轮那批 derived_id（G-44）。"
        f"实得 skipped={sorted(second.skipped)} vs 首轮 produced={sorted(first.produced)}"
    )
    assert set(second.produced) & set(second.skipped) == set(), "produced 与 skipped 必须互斥（G-42）"


def test_handler_marks_degraded_when_inputs_missing(scratch: Path) -> None:
    _prepare(scratch, with_prices=False)
    outcome = step.make_derived_handler(scratch)(date(2026, 9, 16), "full")
    assert outcome.produced == []
    assert outcome.skipped == [], (
        "★ 上游一件都没得做 ⇒ skipped **必须也为空**（不得用 skipped 这个新出口把空执行洗成'已完成'）"
    )
    assert outcome.degraded is True            # 缺口是正常态，但**显式**标记（不静默）


def test_handler_left_empty_outcome_is_still_judged_incomplete(scratch: Path) -> None:
    """★ 反向对照（`G-44` 的**关键**一条）：上游输入为空 ⇒ `produced=[]` **且** `skipped=[]`
    ⇒ 经 `chain_steps` 的适配器后**仍然**必须带 `incomplete_reason`（判 `gap`）。

    为什么单列：新增 `skipped` 出口的**风险**正是"把空执行守卫削弱成恒真"。
    本条把"真的一件都没得做"这条路径钉死：适配器的判据 `not produced and not skipped`
    在这里必须仍为真。
    """
    from scripts.orchestrate.chain_steps import _declare_incomplete_when_empty

    _prepare(scratch, with_prices=False)
    bare = step.make_derived_handler(scratch)(date(2026, 9, 16), "full")
    assert (bare.produced, bare.skipped) == ([], [])
    wrapped = _declare_incomplete_when_empty(
        step.make_derived_handler(scratch), step_name="step 5", upstream_note="上游输入为空"
    )(date(2026, 9, 16), "full")
    assert wrapped.incomplete_reason is not None, (
        "★ 真·空执行必须仍被判『未完成』—— 若这里为 None，说明 skipped 出口把守卫削成了恒真"
    )


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
