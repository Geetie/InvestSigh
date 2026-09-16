"""step 2–6 **接线**测试（批次 7 · 集成 `I-1`，张力 `T-08` 的 **A 方案**）。

对应设计：`01_产品目标与核心闭环/01_需求拆解.md §2.2`（8 步流程 → 章节映射表）
+ `system/scripts/orchestrate/chain_steps.py` 的模块 docstring
+ `system/rules/pipeline.yaml`（step 1–6 `implemented_in_first_version: true` / `blocking: true`）

**本文件防守的是一条最容易假绿的路**：把"注册了处理器"当成"这一步做完了"。
A 方案的要求是「能真跑的接真实现，跑不了的**显式**声明未完成」——
所以每条断言都盯 **`status` 是否被诚实地记成 `gap`**，而不是盯"注册表里有 6 个键"。

★ 断言的是**编排器的对外结果**（`StepResult.status` / `RunResult.gaps` / `blocked`），
  不是内部函数是否被调用 —— 后者能被"改一行实现"绕过（`G-02` 的思路）。
"""

from __future__ import annotations

import dataclasses
from datetime import date
from pathlib import Path

import pytest

from scripts.orchestrate.chain_steps import (
    _declare_incomplete_when_empty as _adapter,  # noqa: PLC2701
)
from scripts.orchestrate.pipeline import (
    STATUS_GAP,
    STATUS_OK,
    Pipeline,
    StepOutcome,
)

RUN_DATE = date(2026, 9, 16)


def _by_step(result) -> dict[int, object]:
    return {s.step: s for s in result.steps}


# ───────────────────────── 注册面 ─────────────────────────


def test_default_pipeline_registers_steps_1_to_6(code_root: Path) -> None:
    """`rules/pipeline.yaml` 声明 step 1–6 首版已实现 → 默认必须全注册（`G-13` 的症结）。"""
    p = Pipeline(code_root)
    assert sorted(p._step_handlers) == [1, 2, 3, 4, 5, 6], (
        "step 1–6 未全部默认注册 —— `rules/pipeline.yaml` 声明它们首版已实现，"
        "靠调用方自觉注册就等于没接（G-13）"
    )


# ───────────────────── ★ 核心：注册 ≠ 完成 ─────────────────────


@pytest.mark.parametrize(
    "step_no, name_fragment",
    [(2, "trace_dedup_verify"), (3, "update_company_and_industry"), (4, "revise_growth")],
)
def test_model_side_steps_are_recorded_as_gap_not_ok(
    code_root: Path, step_no: int, name_fragment: str
) -> None:
    """★ step 2/3/4 的**模型侧**组件未实现 → 必须记 `gap`，**不得**记 `ok`。

    这是 A 方案的核心断言：注册处理器**不能**把"未实现"洗成"已完成"。
    若实现被改成"注册一个什么都不做的处理器并返回 `StepOutcome()`"，
    编排器会记 `STATUS_OK` → 本用例必红。
    """
    result = Pipeline(code_root).run_daily(RUN_DATE)
    step = _by_step(result)[step_no]
    assert name_fragment in step.name
    assert step.status == STATUS_GAP, (
        f"step {step_no}（{step.name}）被判成 {step.status} —— "
        f"其模型侧组件属阶段②③、本批次未实现，必须是 gap（A 方案：显式、不静默）"
    )
    assert step.gap, f"step {step_no} 记了 gap 状态却没给出原因（不得静默降级）"
    assert "T-08" in step.gap, "gap 未标注张力编号 T-08，无法反查裁决依据"


def test_step_4_has_no_output_because_it_has_no_reusable_deterministic_part(
    code_root: Path,
) -> None:
    """step 4 **不得**为了凑数而硬塞一个空产出（`G1-05` 要拦的正是"空执行"）。"""
    step = _by_step(Pipeline(code_root).run_daily(RUN_DATE))[4]
    assert step.produced == [], "step 4 的模型侧产出不存在，不许伪造 produced"


# ───────────────── 无产出 → 必须显式声明未完成（适配器） ─────────────────


def test_adapter_marks_empty_outcome_as_incomplete() -> None:
    """底层处理器**跑了但无产出** → 适配器补 `incomplete_reason`（不得留成 `ok`）。"""

    def _empty(_d: date, _s: str) -> StepOutcome:
        return StepOutcome(produced=[], degraded=True)

    out = _adapter(_empty, step_name="s5", upstream_note="上游输入缺失")(RUN_DATE, "full")
    assert out.incomplete_reason, "无产出却未声明未完成 → 编排器会把它记成 ok（空执行）"
    assert out.produced == []


def test_adapter_does_not_touch_outcomes_that_produced_something() -> None:
    """**反向对照**：有产出时适配器**不得**改动语义（证明没有误伤）。"""

    def _full(_d: date, _s: str) -> StepOutcome:
        return StepOutcome(produced=["dv-1"], degraded=False)

    out = _adapter(_full, step_name="s5", upstream_note="上游输入缺失")(RUN_DATE, "full")
    assert out.incomplete_reason is None
    assert out.produced == ["dv-1"]


def test_adapter_preserves_an_existing_incomplete_reason() -> None:
    """底层已给出 `incomplete_reason` → 适配器**不覆盖**（口径归底层，`G-06`）。"""

    def _already(_d: date, _s: str) -> StepOutcome:
        return StepOutcome(produced=[], incomplete_reason="底层自己的原因")

    out = _adapter(_already, step_name="s5", upstream_note="x")(RUN_DATE, "full")
    assert out.incomplete_reason == "底层自己的原因"


# ───────────────── 默认值向后兼容 ─────────────────


def test_incomplete_reason_defaults_to_none() -> None:
    """新增字段缺省 `None` = 本步自认完成（既有处理器行为不变）。"""
    assert StepOutcome().incomplete_reason is None
    assert dataclasses.fields(StepOutcome)  # 仍是 dataclass（`replace` 依赖它）


# ───────────────── 真实运行的整体行为 ─────────────────


def test_run_daily_records_gaps_and_blocks_on_incomplete_steps(code_root: Path) -> None:
    """端到端：未完成的步必须进 `result.gaps`，且 `blocking` 步未完成 → 置 `blocked`。"""
    result = Pipeline(code_root).run_daily(RUN_DATE)
    assert result.blocked is True, "有 blocking 步未完成却未置 blocked —— 不得报成功"

    joined = "\n".join(result.gaps)
    for step_no in (2, 3, 4):
        assert f"step {step_no} " in joined, f"step {step_no} 的未完成原因没有进 result.gaps"


def test_no_step_claims_ok_without_output(code_root: Path) -> None:
    """★ 不变量：**step 2–6** 里任何记成 `ok` 的步都必须有产出。

    这条把 `G1-05` 的"空执行"判据**前移**成编排器侧的可测断言：
    只要有人注册一个"什么都不做但返回默认 `StepOutcome()`"的处理器，本用例即红
    （本批次实测抓到过：`scripts/compute/step.py` 与 `scripts/decision/step.py` 的处理器
    在上游输入为空时返回 `produced=[]` + `degraded=True` 而**不设** `incomplete_reason`，
    于是被记成 `ok` —— 那正是本用例要防的）。

    ★ **为什么把 step 1 排除在外（如实登记，不掩盖）**：`scripts/orchestrate/ingest_step.py`
    在 `raw/` 为空时**合法地**跑完却无产出（当日无可采集输入），此时它返回 `ok` + `produced=[]`
    → 仍会被 `assert_steps_complete` 判成"空执行"。这是 **`G1-05` 判据在 step 1 上的语义边界**
    （"没有输入可处理" ≠ "处理器是假的"），涉及批次 5 已验收组件与守卫语义裁定，
    **不在本批次（`I-1`）范围内**，已登记为缺口 `G-26` 上报，**不在此处自裁**。
    """
    result = Pipeline(code_root).run_daily(RUN_DATE)
    offenders = [
        (s.step, s.name)
        for s in result.steps
        if 2 <= s.step <= 6 and s.status == STATUS_OK and not s.produced and not s.skipped
    ]
    assert offenders == [], f"以下步报 ok 但 produced 与 skipped 均为空（空执行）：{offenders}"


# ───────── ★ step 2 接线（`Ch6 §6.3` 追源归因 + 独立判定）的判别式 ─────────
#
# 为什么单开一节：step 2 原先的 `produced = 全部核验通过的 claim_id` 属 **`C-03` 同族**缺陷 ——
# 那个集合**与是否写入无关** ⇒ 幂等重跑时 `produced` 仍非空 ⇒ `G1-05` 的空执行判据
# 对本步**恒假**（守卫失效），且两轮观测量完全相同（"幂等"与"非幂等"不可区分）。
# 现按契约（`4f95c3d` 裁定 R2）切分为 `produced`（本轮真正新写入）/ `skipped`（幂等命中）。
#
# ★ 判别力的来源 = **两轮观测量必须不同**：
#   若有人把 produced 改回"全部核验通过的 claim_id"，第 2 轮 `produced` 会变非空 → 本用例即红。

_INBOX_NAME = "2026-09-16_nvda_q2.txt"
_INBOX_TEXT = (
    "NVIDIA 数据中心业务的季度收入在报告期内显著增长。\n"
    "本行为夹具文本的第二行，用于让 locator 的行区间可核。\n"
)


def _seed_inbox(code_root: Path) -> None:
    """往投递口放一份待采集文本 —— 走**真实写路径**造 claim，不手工拼 JSONL。"""
    inbox = code_root / "raw" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / _INBOX_NAME).write_text(_INBOX_TEXT, encoding="utf-8")


def _lines(code_root: Path, stem: str) -> int:
    path = code_root / "facts" / f"{stem}.jsonl"
    if not path.exists():
        return 0
    return len([ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()])


def test_step2_wiring_discriminates_between_first_run_and_rerun(code_root: Path) -> None:
    """★ step 2 的双跑判别式：**首轮写入 → 重跑双空 produced + 真源不增行**。

    断言四件事，缺一不可：
    1. 首轮 `produced` **非空**（否则"重跑为空"没有判别力 —— 一个永远不写的实现也能骗过）；
    2. 首轮 `skipped` 为空；
    3. 重跑 `produced == []`；
    4. 重跑 `skipped` **非空**，且集合 = 首轮新写入集合（这正是 `G1-05` 修正判据
       `not produced and not skipped` 所要保留的信息："读了 N 个对象、判定均无需追加"
       **不是**空执行）。
    ★ 另加**真源行数不增**：断言的是**文件**，不是模块自报（自报曾在批次 10 被证伪一次）。
    """
    _seed_inbox(code_root)

    first = Pipeline(code_root).run_daily(RUN_DATE)
    s2_first = {s.step: s for s in first.steps}[2]
    claims_after_first = _lines(code_root, "claims")
    prop_after_first = _lines(code_root, "claim_propagation")

    assert s2_first.produced, (
        "首轮 step 2 必须真正写入 —— 若为空，本用例对'重跑为空'就不具备判别力"
    )
    assert s2_first.skipped == [], f"首轮不应有幂等命中，实得 {s2_first.skipped}"

    second = Pipeline(code_root).run_daily(RUN_DATE)
    s2_second = {s.step: s for s in second.steps}[2]

    assert s2_second.produced == [], (
        f"幂等重跑 produced 必须为空，实得 {s2_second.produced}。\n"
        "非空即说明 produced 又被填成'全部核验通过的 claim_id / 全部对象引用'"
        "（与是否写入无关，C-03 同族）—— 那会让 G1-05 的空执行判据对本步**恒假**。"
    )
    assert s2_second.skipped, "重跑必须把幂等命中记进 skipped，否则会被误判成'空执行'"
    assert set(s2_second.skipped) == set(s2_first.produced), (
        "重跑的幂等命中集合必须 = 首轮新写入集合；"
        f"实得 skipped={sorted(s2_second.skipped)} vs 首轮 produced={sorted(s2_first.produced)}"
    )
    assert _lines(code_root, "claims") == claims_after_first, (
        f"幂等重跑**不得**往 facts/claims.jsonl 追加行："
        f"首轮 {claims_after_first} → 重跑 {_lines(code_root, 'claims')}"
    )
    assert _lines(code_root, "claim_propagation") == prop_after_first, (
        f"幂等重跑**不得**往 facts/claim_propagation.jsonl 追加行："
        f"首轮 {prop_after_first} → 重跑 {_lines(code_root, 'claim_propagation')}"
    )


def test_step2_still_declares_model_side_gap(code_root: Path) -> None:
    """接线**不得**把"接线了"洗成"这一步做完了"（A 方案的核心）。

    `Ch6 §6.3` 七步判定中的**交叉验证 / 采纳与否**仍属模型侧、阶段②③ ——
    故本步必须**继续**记 `gap` 并给出原因；`produced` 非空**不**构成"该步已完成"的证据。
    """
    _seed_inbox(code_root)
    result = Pipeline(code_root).run_daily(RUN_DATE)
    s2 = {s.step: s for s in result.steps}[2]
    assert s2.status == STATUS_GAP, (
        f"step 2 接线后仍必须是 gap（模型侧未交付），实得 {s2.status} —— "
        "不得因为接上了确定性骨架就把'未完成'洗成'已完成'"
    )
    assert s2.gap, "记了 gap 却没给原因（不得静默）"
    assert "交叉验证" in s2.gap, f"gap 应指明仍缺的模型侧部分，实得：{s2.gap}"
