"""接线与登记层的注入测试（`§一 底线 2` 真接线 / `Ch9 §3.4.9`）。

本文件存在的理由：**独立审计抓到两类"能通过 100% 覆盖率测试的假交付"** ——
1. `schema/registry_models.py` 是**孤儿模块**（无人导入），
   而 `registry/prep_deliverables.yaml` 却声明它是 `QualityLabel` 的载体；
2. `stage_gate.py` 的 docstring 声称检查了 `T01–T14`，**代码里根本没有**。

两类都是 `§一 底线 2`「真接线」点名的形态。断言方式一律是**注入→必须 exit 非零**，
不是"函数被调用了"。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from conftest import SYSTEM_ROOT, assert_rejected, run_gate

REGISTRY_GUARD = "scripts/checks/registry_schema_guard.py"
GATE = "scripts/delivery/stage_gate.py"


# ═══════════ 登记层真源：`registry_models` 的读取方必须真的在跑 ═══════════

def test_registry_models_is_actually_imported() -> None:
    """`schema/registry_models.py` 必须有**真实调用方**（防孤儿模块）。

    这条测试不查"文件存在"，而是查**谁导入它** —— 孤儿模块的判据就是"无人导入"。
    """
    guard = SYSTEM_ROOT / "scripts" / "checks" / "registry_schema_guard.py"
    text = guard.read_text(encoding="utf-8")
    assert "from schema.registry_models import" in text, (
        "registry_schema_guard.py 未导入 registry_models —— registry_models 仍是孤儿模块"
    )
    # 而且必须真的用到 REGISTRY_MODELS / registry_model_for，不是只 import 不调用
    assert "REGISTRY_MODELS" in text and "registry_model_for(" in text


def test_registry_guard_registered_in_gate_runner() -> None:
    """守卫必须出现在门禁跑测器里（否则写了没人跑 = 假接线）。"""
    runner = (SYSTEM_ROOT / "scripts" / "ops" / "run_all_gates.py").read_text(encoding="utf-8")
    assert "registry_schema_guard.py" in runner


def test_valid_registry_record_passes(code_root: Path) -> None:
    """**反向对照**：合法登记记录 → 放行。"""
    path = code_root / "registry" / "quality-labels.jsonl"
    path.write_text(
        json.dumps(
            {
                "label_id": "ql_1",
                "subject_kind": "source",
                "subject_id": "westock",
                "human_verified": True,
                "label_value": "high",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    proc = run_gate(REGISTRY_GUARD, code_root)
    assert proc.returncode == 0, f"合法登记记录被误报\n{proc.stdout}\n{proc.stderr}"
    assert "lines_validated: 1" in proc.stdout


def test_invalid_registry_record_is_rejected(code_root: Path) -> None:
    """非法登记记录（缺必填字段）→ 必须 exit 1。"""
    path = code_root / "registry" / "corporate-actions.jsonl"
    path.write_text(json.dumps({"action_id": "ca_1"}) + "\n", encoding="utf-8")
    assert_rejected(run_gate(REGISTRY_GUARD, code_root), rule_hint="CorporateAction")


def test_extra_field_on_registry_record_is_rejected(code_root: Path) -> None:
    """`extra="forbid"` 必须真的生效（多一个字段也拦）。"""
    path = code_root / "registry" / "idempotency.jsonl"
    path.write_text(
        json.dumps(
            {
                "idempotency_key": "k1",
                "first_seen_at": "2026-09-16T00:00:00+00:00",
                "task_ref": "task_1",
                "unexpected_field": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert_rejected(run_gate(REGISTRY_GUARD, code_root), rule_hint="IdempotencyRecord")


def test_unregistered_registry_jsonl_is_rejected(code_root: Path) -> None:
    """`registry/` 出现未登记模型的 JSONL → 必须 exit 1（没人读的数据）。"""
    (code_root / "registry" / "sneaky.jsonl").write_text("{}\n", encoding="utf-8")
    assert_rejected(run_gate(REGISTRY_GUARD, code_root), rule_hint="未在 REGISTRY_MODELS 登记")


def test_missing_declared_registry_file_is_rejected(code_root: Path) -> None:
    """已登记模型的文件被删 → 必须 exit 1（真源缺失）。"""
    (code_root / "registry" / "quality-labels.jsonl").unlink()
    assert_rejected(run_gate(REGISTRY_GUARD, code_root), rule_hint="登记层真源缺失")


def test_empty_registry_source_is_not_reported_as_verified(code_root: Path) -> None:
    """**关键**：真源为空时**不得**当作"已验证结构合规" —— 必须显式记 note。"""
    proc = run_gate(REGISTRY_GUARD, code_root)
    assert proc.returncode == 0
    assert "EMPTY_REGISTRY_SOURCE" in proc.stdout, "空真源必须显式说明，不得静默通过"
    assert "lines_validated: 0" in proc.stdout


# ═══════════ 判据台账：不得"声明了 automated 却没实现" ═══════════

def test_prep_has_zero_unimplemented_criteria(code_root: Path) -> None:
    """阶段① 声明的 4 条 automated 判据必须**全部实现**（PASS 的前提）。"""
    proc = run_gate(GATE, code_root, "--stage", "prep")
    assert proc.returncode == 0
    assert "prep.criteria_not_implemented: 0" in proc.stdout
    assert "prep.criteria_bound: 4" in proc.stdout


def test_newly_declared_criterion_without_implementation_blocks_stage(code_root: Path) -> None:
    """★ 注入一条**新声明**的 automated 判据（代码里没实现）→ 阶段① 必须 FAIL。

    这正是独立审计抓到的那类缺陷（`t01_t14_all_pass` 只写在 docstring 里）。
    有了这条机制，"声明"与"实现"不可能再悄悄脱节。
    """
    path = code_root / "registry" / "delivery.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    for st in doc["delivery_stages"]:
        if st.get("key") == "prep":
            st["pass_criteria_testable"].append(
                {
                    "id": "invented_automated_criterion",
                    "statement": "一条被声明为 automated 但代码里没有的判据",
                    "check_kind": "automated",
                }
            )
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")

    assert_rejected(
        run_gate(GATE, code_root, "--stage", "prep"), rule_hint="invented_automated_criterion"
    )


def test_unimplemented_criteria_are_listed_as_notes(code_root: Path) -> None:
    """阶段②–⑤ 的未实现判据必须**逐条列出**（不得因"反正阻塞了"而藏起来）。"""
    proc = run_gate(GATE, code_root, "--stage", "all")
    assert proc.returncode == 1
    assert "t01_t14_all_pass" in proc.stdout, "T01–T14 缺口必须显式可见"
    assert "判据台账[core_chain]" in proc.stdout
    for stage in ("nvidia_sample", "daily_run", "expansion"):
        assert f"判据台账[{stage}]" in proc.stdout
