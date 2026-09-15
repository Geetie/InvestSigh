"""阶段判据守卫的注入测试（`Ch11 §B` / `§G G11-04` · 纪律 12）。

**纪律 12：阶段未过即阻塞，不得静默跳过。**

两类必须证明的事：
1. 阶段① 的**通过判据真的可测**（删一项 → FAIL），而不是"文件在就算过"；
2. 后续阶段的"前置未满足"返回 **`passed=False`（exit 1）**，
   **绝不返回 True 冒充通过**。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import assert_rejected, run_gate

GATE = "scripts/delivery/stage_gate.py"


def test_prep_passes_on_pristine_tree(code_root: Path) -> None:
    """**基线**：干净副本上阶段① 必须放行（否则后面所有注入测试都无法归因）。"""
    proc = run_gate(GATE, code_root, "--stage", "prep")
    assert proc.returncode == 0, f"阶段① 在干净副本上未通过\n{proc.stdout}\n{proc.stderr}"
    assert "prep: PASS" in proc.stdout


def test_missing_skill_md_blocks_prep(code_root: Path) -> None:
    """删掉一个 `SKILL.md` → 阶段① 必须 FAIL（`skills/` 是 I/O 契约载体）。"""
    (code_root / "skills" / "aichain-daily" / "SKILL.md").unlink()
    assert_rejected(run_gate(GATE, code_root, "--stage", "prep"), rule_hint="缺 SKILL.md")


def test_skill_without_io_anchor_blocks_prep(code_root: Path) -> None:
    """`SKILL.md` 存在但**没载 I/O 契约出处** → 必须 FAIL（那只是文档，不是契约）。"""
    path = code_root / "skills" / "aichain-ask" / "SKILL.md"
    path.write_text("# 提问入口\n\n只写了点散文，没有契约要素。\n", encoding="utf-8")
    proc = run_gate(GATE, code_root, "--stage", "prep")
    assert_rejected(proc, rule_hint="未引用 I/O 契约出处")


def test_collapsed_rule_layers_block_prep(code_root: Path) -> None:
    """把「已确认规则」层清空 → 必须 FAIL（两层必须显式区分且都非空）。"""
    import yaml

    path = code_root / "registry" / "prep_deliverables.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["confirmed_rules"] = []
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert_rejected(run_gate(GATE, code_root, "--stage", "prep"), rule_hint="confirmed_rules 为空")


def test_later_stages_are_blocked_not_silently_skipped(code_root: Path) -> None:
    """★ 纪律 12：阶段②–⑤ 的前置产物不存在 → **exit 1**，绝不冒充通过。"""
    proc = run_gate(GATE, code_root, "--stage", "all")
    assert proc.returncode == 1, (
        f"后续阶段应阻塞(exit 1)，实得 {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
    )
    for stage in ("nvidia_sample", "core_chain", "daily_run", "expansion"):
        assert f"{stage}: BLOCKED" in proc.stdout, f"{stage} 未显式标记 BLOCKED"
    assert "prep: PASS" in proc.stdout


@pytest.mark.parametrize("stage", ["nvidia_sample", "core_chain", "daily_run", "expansion"])
def test_each_later_stage_individually_blocked(stage: str, code_root: Path) -> None:
    """逐个阶段都必须返回阻塞（不能只靠 `--stage all` 的聚合）。"""
    proc = run_gate(GATE, code_root, "--stage", stage)
    assert proc.returncode == 1, f"{stage} 应为阻塞\n{proc.stdout}"
    assert f"{stage}: BLOCKED" in proc.stdout


def test_invalid_stage_name_is_input_error(code_root: Path) -> None:
    """**边界**：非法阶段名 → argparse 拒绝（exit 2），不得当成"通过"。"""
    proc = run_gate(GATE, code_root, "--stage", "nonexistent_stage")
    assert proc.returncode != 0, "非法阶段名必须被拒"
