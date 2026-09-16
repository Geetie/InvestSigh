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


# ═══════════ 夹具不得继承**运行态**（`G-RC-07` 的文件版） ═══════════
#
# `state.json` 是运行态游标（含真仓库的 run 历史），`.gitignore` 明确它是"每次运行重写、可重建"。
# `copytree` 复制的是**磁盘上的一切**（不只是 git 跟踪的东西）—— 原先 `_COPY_SKIP` 只列**目录**，
# 于是 `state.json` 被带进每个夹具副本，`resume()` 会去续跑**真仓库**那一次运行。
# 与 `G-RC-02` / `G-RC-07` 同一形态：**测试观测量取决于真仓库当前恰好有什么**。


def test_fixture_does_not_inherit_runtime_state(code_root: Path) -> None:
    """夹具副本**不得**含 `state.json`（否则 `resume()` 会续跑真仓库的运行）。"""
    assert not (code_root / "state.json").exists(), (
        "夹具继承了真仓库的 state.json —— `resume()` 会去续跑真仓库的那一次运行，"
        "测试观测量因此与真仓库的运行历史耦合（G-RC-07 的文件版）"
    )
    # 机制层断言：防本用例因"真仓库恰好没有该文件"而变成**空转**
    # （`G-03`：无被检对象 ≠ 已验证，故不能只靠运行时那一条）。
    from conftest import _COPY_SKIP  # noqa: PLC0415

    assert "state.json" in _COPY_SKIP, "夹具的复制跳过清单必须包含 state.json"


def test_unimplemented_criteria_are_listed_as_notes(code_root: Path) -> None:
    """阶段②–⑤ 的未实现判据必须**逐条列出**（不得因"反正阻塞了"而藏起来）。

    ★ 注意断言的**对象**：本用例要求的是"五阶段的判据台账**都出现**"，
      而不是"每个阶段都有缺口"。当某阶段判据全部绑定后，台账行仍须存在
      （`stage_gate.check()` 已改为**无条件发射**）—— 否则"该阶段判据已全部绑定"
      与"台账代码路径根本没跑"在输出上不可区分（前者是好事、后者是守卫静默失效，
      观测量却完全相同）。这是本条要求的**加强版**，不是放松。
    """
    proc = run_gate(GATE, code_root, "--stage", "all")
    assert proc.returncode == 1
    assert "t01_t14_all_pass" in proc.stdout, "T01–T14 缺口必须显式可见"
    assert "判据台账[core_chain]" in proc.stdout
    for stage in ("nvidia_sample", "daily_run", "expansion"):
        assert f"判据台账[{stage}]" in proc.stdout


# ═══════════ 阶段④「降级保留上次有效结果」· 首日豁免的**实际有效性** ═══════════
#
# 为什么单开一节：这条豁免判据的第一版**是死代码**（批次 11 自查抓到，实测真仓库
# `degrade_first_day_exempt: 0` 而 2 条违例一条没少）。根因：
#   它取 `parent_context.run_date`，而 `_write_check_record()` 写的 `parent_context`
#   只有 `{"orchestrator": "pipeline.run_daily"}` —— **不含 run_date**
#   （run_date 真正落在 `check_record.run_date`）。于是每个任务都取到 `""` →
#   `min(...)` = `""` → `_earliest` 为**空串**（假值）→ 豁免分支**永不进入**。
# 形态与本文档开头点名的那两类同族：**"改了"但机器上不生效**。
#
# ★ 故本节的断言**必须落在"豁免计数"上**，只断言"没有违例"是不够的 ——
#   豁免生效 与 判据根本没跑 都表现为"没有违例"，两者观测量相同（与 `G-03` 同源：
#   没有可观测的证据，就不等于已验证）。

_DAY = "2026-09-16"


def _check_task(task_id: str, *, status: str, last_valid: str | None = None) -> dict:
    """一条 `verify` 任务行（含 `check_record`），字段形状与 `_write_check_record()` 一致。"""
    return {
        "task_id": task_id,
        "task_type": "verify",
        "status": status,
        "idempotency_key": f"check::{task_id}",
        "parent_context": {"orchestrator": "pipeline.run_daily"},
        "last_valid_result_ref": last_valid,
        "output_refs": [],
        "check_record": {
            "check_id": task_id,
            "run_date": _DAY,
            "changed": False,
            "judgment_change": {},
            "signals_emitted": 0,
            "degraded": False,
        },
    }


def _done_task_with_output(task_id: str) -> dict:
    """一条**正常完成且持有产出**的行。

    ★ 它**没有** `last_valid_result_ref`（那是降级链才有的字段）。若"是否持有有效结果"
      只看那一个字段，本行就会被误判成"没有有效结果"→ 后续失败行被**误豁免** → 漏报。
      这正是 `_holds_valid_result()` 取**两载体并集**的理由。
    """
    return {
        "task_id": task_id,
        "task_type": "verify",
        "status": "done",
        "idempotency_key": f"check::{task_id}",
        "parent_context": {"orchestrator": "pipeline.run_daily", "run_date": _DAY},
        "output_refs": ["rec-nvda-001"],
    }


def _write_tasks(code_root: Path, rows: list[dict]) -> None:
    (code_root / "facts" / "tasks.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def test_first_day_degrade_exemption_is_effective_and_counted(code_root: Path) -> None:
    """★ 首日降级（此前**无**任何行持有有效结果）→ 豁免，且**计数必须可见且 > 0**。"""
    _write_tasks(code_root, [_check_task("check_d1_full", status="failed")])
    proc = run_gate(GATE, code_root, "--stage", "daily_run")
    assert "degrade_first_day_exempt: 1" in proc.stdout, (
        "首日豁免必须**实际生效**且计数可见 —— 计数恒 0 意味着豁免分支根本没进（死代码）。\n"
        f"{proc.stdout}"
    )
    assert "失败但未保留 last_valid_result_ref" not in proc.stdout, proc.stdout


def test_degrade_violation_fires_when_a_prior_result_exists(code_root: Path) -> None:
    """**反向对照**：此前已有行持有有效结果 → 仍必须 FATAL（不放松）。

    ★ 本条同时是"取 run_date 最早"那版判据的**反例**：两行的 `run_date` 同为 `_DAY`，
      按日期判定会把失败行当成"首日"而豁免 —— 那是**漏报真违规**。
      按**追加序**判定则不受同日重跑影响。
    """
    _write_tasks(
        code_root,
        [
            _done_task_with_output("check_d1_full"),
            _check_task("check_d1_full_r1", status="failed"),
        ],
    )
    proc = run_gate(GATE, code_root, "--stage", "daily_run")
    assert "失败但未保留 last_valid_result_ref" in proc.stdout, (
        "此前已完成并持有产出 ⇒ 引用本该在却被丢掉，必须 FATAL\n" + proc.stdout
    )
    assert "degrade_first_day_exempt: 0" in proc.stdout, proc.stdout


def test_failed_row_that_kept_ref_does_not_exempt_the_next_one(code_root: Path) -> None:
    """前序**失败但保留了引用**的行同样算"持有有效结果" → 紧随其后的失败行**不得**豁免。

    这是 `_holds_valid_result()` 的第二个载体（`last_valid_result_ref`）的判别力来源。
    """
    _write_tasks(
        code_root,
        [
            _check_task("check_d1_full", status="failed", last_valid="rec-nvda-001"),
            _check_task("check_d1_full_r1", status="failed"),
        ],
    )
    proc = run_gate(GATE, code_root, "--stage", "daily_run")
    assert "check_d1_full_r1 失败但未保留 last_valid_result_ref" in proc.stdout, proc.stdout
    assert "degrade_first_day_exempt: 0" in proc.stdout, proc.stdout
