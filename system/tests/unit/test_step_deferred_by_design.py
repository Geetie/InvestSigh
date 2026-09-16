"""`T-18`：`implemented_in_first_version` 的**唯一代码消费者**（`deferred_by_design`）。

被检对象：`scripts/orchestrate/pipeline.py` 的 `_deferred_by_design()` 与
`run_daily` / `resume` 的五个分支。

## 为什么这些用例必须存在

`rules/pipeline.yaml` 把 step 7/8 声明为 `blocking: True` **+** `implemented_in_first_version: False`，
而改前 `implemented_in_first_version` **零代码消费者** ⇒ 7/8 永不注册 ⇒ `run_daily()` 恒记 gap
并令 `blocked=True` ⇒ `status` 恒 `failed` ⇒ **`blocked` 失去判别力**（本项目铁律
「卡死的信号 = 被关掉的信号」最危险的形态）。

裁定（需求方 2026-09-17）：**首版不把 `implemented_in_first_version: False` 的步计入 `blocking`
判定，但必须记 `gaps` 并显式标 `deferred_by_design`。** 本文件用**真实 `run_daily` 调用**
（不是单测桩）证明这一点，并用一个**受控 A/B** 证明判别力**回来了**：
把同一份配置里的 `implemented_in_first_version` 由 `False` 改 `True` ⇒ `blocked` 重新为真。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from scripts.orchestrate.pipeline import (
    STATUS_GAP,
    STATUS_OK,
    Pipeline,
    StepOutcome,
    _deferred_by_design,
)

RUN_DATE = date(2026, 9, 17)
TASK_ID = "run_2026-09-17_full"


def _steps_config(step7_first_version: bool) -> list[dict[str, object]]:
    """`rules/pipeline.yaml` 的**最小等价声明**：1–6 首版已实现 + 7/8 首版不做。"""
    steps: list[dict[str, object]] = [
        {
            "step": i,
            "name": f"step{i}",
            "blocking": True,
            "implemented_in_first_version": True,
        }
        for i in range(1, 7)
    ]
    steps.append(
        {
            "step": 7,
            "name": "publish_recommendations",
            "blocking": True,
            "implemented_in_first_version": step7_first_version,
            "hook": "publish_hook",
        }
    )
    steps.append(
        {
            "step": 8,
            "name": "continuous_verification_and_history",
            "blocking": True,
            "implemented_in_first_version": False,
            "hook": "verify_hook",
        }
    )
    return steps


def _pipeline(root: Path, *, step7_first_version: bool) -> Pipeline:
    """1–6 接**确定成功**的处理器（各产出一个对象）；7/8 **不注册**（= 首版真实状态）。"""
    pipeline = Pipeline(root, config={"steps": _steps_config(step7_first_version)})
    for i in range(1, 7):
        pipeline.register_step(
            i,
            lambda _run_date, _scope, _i=i: StepOutcome(produced=[f"obj-{_i}"]),
        )
    return pipeline


# ─────────────────── ① AC-01 / AC-02：真跑 `run_daily` + A/B 判别力 ───────────────────


def test_deferred_steps_do_not_block_and_are_marked(code_root: Path) -> None:
    """★ AC-01：1–6 全 `ok` 时，7/8（首版不做）**不再**令 `blocked` 为真。

    ★ AC-02：7/8 的缺口必须能读出是「**设计上首版不做**」，而不是「忘了实现」。

    ★ 这是**真实 `run_daily` 调用**（含 `_write_check_record` 落库），不是单测桩。
    """
    pipeline = _pipeline(code_root, step7_first_version=False)
    result = pipeline.run_daily(RUN_DATE, "full")

    assert result.blocked is False, f"7/8 不应再令 blocked 为真；gaps={result.gaps}"
    by_step = {s.step: s for s in result.steps}
    assert all(by_step[i].status == STATUS_OK for i in range(1, 7)), {
        i: by_step[i].status for i in range(1, 7)
    }
    assert by_step[7].status == STATUS_GAP and by_step[8].status == STATUS_GAP

    deferred = [g for g in result.gaps if "deferred_by_design" in g]
    assert len(deferred) == 2, f"每一步都须显式标 deferred_by_design；实得 {deferred}"
    for gap in deferred:
        assert "设计上首版不做" in gap, gap
        assert "implemented_in_first_version=False" in gap, gap


def test_first_version_true_step_still_blocks(code_root: Path) -> None:
    """★ A/B 对照：把 step 7 的 `implemented_in_first_version` 改回 `True` ⇒ `blocked` 重新为真。

    ★ 这条是**判别力回来了**的直接证据：`blocked` 现在**只**由"首版该做的步是否做了"决定，
      而不是被 7/8 恒定拉红。若没有这条，`test_deferred_steps_do_not_block_and_are_marked`
      可能只是因为 `blocked` 被**任何**原因关掉了。
    """
    pipeline = _pipeline(code_root, step7_first_version=True)
    result = pipeline.run_daily(RUN_DATE, "full")

    assert result.blocked is True, f"首版该做的步未注册 ⇒ 必须 blocked；gaps={result.gaps}"
    assert not any(
        "step 7" in g and "deferred_by_design" in g for g in result.gaps
    ), f"step 7 已声明首版实现，不得标 deferred_by_design；gaps={result.gaps}"


# ─────────────────── ② AC-05：`resume` 与 `run_daily` 同结论 ───────────────────


def test_resume_agrees_with_run_daily_on_deferred_steps(code_root: Path) -> None:
    """★ 断点续跑入口必须给出**同一结论**（批次 7 审计 `B2`：两个入口不得分歧）。"""
    pipeline = _pipeline(code_root, step7_first_version=False)
    daily = pipeline.run_daily(RUN_DATE, "full")
    assert daily.blocked is False

    resumed = pipeline.resume(TASK_ID)
    assert resumed.blocked is False, f"resume 不应与 run_daily 分歧；gaps={resumed.gaps}"
    by_step = {s.step: s for s in resumed.steps}
    assert by_step[7].status == STATUS_GAP and by_step[8].status == STATUS_GAP
    assert any("deferred_by_design" in g for g in resumed.gaps), resumed.gaps


# ─────────────────── ③ 消费者本体的边界（缺键/True 都不得放松） ───────────────────


@pytest.mark.parametrize(
    ("cfg", "expected"),
    [
        ({"implemented_in_first_version": False}, True),
        ({"implemented_in_first_version": True}, False),
        ({}, False),
        ({"implemented_in_first_version": None}, False),
    ],
)
def test_deferred_helper_only_accepts_exact_false(
    cfg: dict[str, object], expected: bool
) -> None:
    """★ 只认**精确的 `False`**：`True` 与**缺键**（`None`）都不得被当成"设计上不做"。

    ★ 为什么这条重要：把"缺键"也当成 deferred 会**悄悄放松** blocking 判定 ——
      那正是本项目最忌讳的"判别力被关掉"。
    """
    assert _deferred_by_design(cfg) is expected
