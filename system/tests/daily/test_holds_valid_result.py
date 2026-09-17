"""阶段④「降级保留上次有效结果」判据的**前提谓词**契约测试。

## 缺陷（`gap-stage-gate-false-red`，2026-09-17 实测）

判据 `daily_run::degrade_keeps_last_valid` 的逻辑是：
「**若**前序存在持有有效结果的行，**则**失败行必须有 `last_valid_result_ref`」。

原实现用**更宽**的 `holds_valid_result()` 做前提，而**写路径**
（`degrade.last_valid_result_ref()`）只认 `is_valid_run_record()`。
两者的差集里恰好有「`status=="done"` + `output_refs` 非空但**无 `check_record`**」——
那**正是普通生产任务行**的形态（实测 3 条 `task_review::*`）。
⇒ 判据认为"存在可保留的结果"，写路径却**引用不到**它们（没有 `check_id`，且库里从未有过
成功运行）⇒ 判据要求引用一个**产不出的东西** ⇒ 假红（实测 `FAIL(3)`，每多跑一天多一条）。

## 为什么修法在**判据侧**，而不是把谓词改窄

验收判定器 `graph/acceptance_checks.py::t13_missing_source_not_fabricated` **逐字要求**
`holds_valid_result({"status": "done", "output_refs": ["rec-1"]})` 为**真**
（防"把真有产出的完成记录误判成无效，从而让降级掩盖真实产出"）。
⇒ 两处判据对同一谓词的要求**相反**，冲突点在**前提的选择**。
本文件把这两条相反要求**同时**钉住 —— 改任何一边都会让这里变红。
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.daily.degrade import holds_valid_result, is_valid_run_record
from scripts.delivery import stage_gate

_TASK_FILE = "tasks.jsonl"


def _append_rows(root: Path, rows: list[dict]) -> None:
    path = root / "facts" / _TASK_FILE
    with open(path, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _run_row(check_id: str, run_day: str, *, degraded: bool, status: str = "failed") -> dict:
    """一条**运行记录**行（带 `check_record`）。"""
    return {
        "task_id": f"task_{check_id}",
        "task_type": "recheck",
        "status": status,
        "idempotency_key": f"check::{check_id}",
        "check_record": {
            "check_id": check_id,
            "run_date": run_day,
            "scope": "full",
            "changed": False,
            "signals_emitted": 0,
            "degraded": degraded,
        },
    }


def _review_row(task_id: str, out_ref: str) -> dict:
    """普通生产任务行：`done` + `output_refs`、**无 `check_record`**（假红的触发器）。"""
    return {
        "task_id": task_id,
        "task_type": "review",
        "status": "done",
        "idempotency_key": f"review::{task_id}",
        "output_refs": [out_ref],
    }


def _criterion_premise(rows: list[dict], idx: int) -> bool:
    """判据在本行的**前提**是否成立 —— 即"此前是否已经有过一次成功运行"。

    ★ 本函数逐字复刻 `stage_gate.py` 判据循环里的那行表达式；若判据换了谓词，
      `test_criterion_premise_uses_write_path_predicate` 会立刻变红。
    """
    return any(is_valid_run_record(prior) for prior in rows[:idx])


# ── 假红消失：复现实测库的追加序 ────────────────────────────────────────────


def test_real_repo_shape_no_longer_arms_the_criterion(code_root: Path) -> None:
    """★ **复现 2026-09-17 实测库** ⇒ 失败行的前提**不成立** ⇒ 走首日豁免 ⇒ 不再假红。"""
    _append_rows(
        code_root,
        [
            _run_row("check_2026-09-16_full", "2026-09-16", degraded=True),
            _run_row("check_2026-09-16_full_r1", "2026-09-16", degraded=True),
            _review_row("task_review::research_quality::baseline-nvda-001", "baseline-nvda-001"),
            _review_row("task_review::forecast_quality::rec-nvda-001", "rec-nvda-001"),
            _review_row("task_review::investment_result::rec-nvda-001", "rec-nvda-001"),
        ],
    )
    rows = [
        json.loads(l)
        for l in (code_root / "facts" / _TASK_FILE).read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    assert len(rows) == 5, "前置：5 条先行记录"

    # 3 条 review 行会被**宽**谓词认作持有 —— 这正是原实现的前提来源（假红根因）
    assert all(holds_valid_result(r) for r in rows[2:]), "前置：宽谓词确实会认这 3 条"
    # 但它们**不是**成功运行 ⇒ 与写路径同口径的前提**不成立** ⇒ 豁免
    assert _criterion_premise(rows, 5) is False, (
        "前提必须不成立（库里从未有过成功运行）—— 否则判据会要求引用一个写路径产不出的 check_id"
    )


# ── 判据仍然有效：不能为消红而把前提改瘫 ────────────────────────────────────


def test_successful_run_still_arms_the_criterion(code_root: Path) -> None:
    """★ **反向对照**：只要真有过一次成功运行 ⇒ 前提成立 ⇒ 判据会被触发。

    本用例专门防"为了让红消失而把前提改成恒 `False`"（那等于把门关掉）。
    """
    _append_rows(
        code_root,
        [
            _run_row("check_2026-09-16_full", "2026-09-16", degraded=True),
            _run_row("check_2026-09-17_full", "2026-09-17", degraded=False, status="done"),
        ],
    )
    rows = [
        json.loads(l)
        for l in (code_root / "facts" / _TASK_FILE).read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    assert _criterion_premise(rows, 1) is False, "第 1 行之前只有失败运行 ⇒ 首日豁免"
    assert _criterion_premise(rows, 2) is True, (
        "第 2 行之前已有一次成功运行 ⇒ 前提成立 ⇒ 后续失败行必须保留引用（判据未被改瘫）"
    )


def test_degraded_run_does_not_arm_the_criterion() -> None:
    """**反向对照**：降级运行**不是**有效结果（它自己就在说"请用上一次的"）⇒ 不构成前提。"""
    row = _run_row("check_deg", "2026-01-01", degraded=True, status="done")
    assert is_valid_run_record(row) is False


# ── 两处判据的相反要求：必须同时满足 ────────────────────────────────────────


def test_predicate_stays_wide_for_t13(code_root: Path) -> None:
    """★ **T13 验收的逐字断言**：宽谓词必须认「`done` + `output_refs`」。

    若把 `holds_valid_result` 改窄（我最初的修法），本用例立刻变红，且
    `ACC-T13` 会在 `stage_gate` 里判红 —— 两处同时报警，不会放过。
    """
    assert holds_valid_result({"status": "done", "output_refs": ["rec-1"]}) is True, (
        "T13 要求它为真：正常完成且真有产出的记录不得被误判成「无效结果」"
    )
    assert holds_valid_result({}) is False, "空记录不得算持有（T13 的另一条断言）"
    assert holds_valid_result({"status": "failed", "output_refs": []}) is False


def test_criterion_premise_uses_write_path_predicate() -> None:
    """★ **元断言（防回退）**：判据的前提必须用 `is_valid_run_record`，不得用 `holds_valid_result`。

    回退到宽谓词 ⇒ 假红重现；这是**源码级**绑定，光靠行为测试可能被"恰好不触发"放过。
    """
    src = inspect.getsource(stage_gate)
    assert "any(is_valid_run_record(_prior)" in src, (
        "判据前提应改写为与写路径同口径的 `is_valid_run_record`"
    )
    assert "any(holds_valid_result(_prior)" not in src, (
        "不得回退到宽谓词做前提 —— 那会让判据要求引用一个写路径产不出的 check_id（假红）"
    )
