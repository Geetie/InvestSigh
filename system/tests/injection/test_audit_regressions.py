"""**审计反例回归测试** —— 把第二轮独立审计构造出的 4 条绕过路径钉死。

审计员实测的绕过（全部**当时成功**、每条只需一行数据编辑）：

| 反例 | 绕过方式 | 现状 |
|---|---|---|
| `D3` | 往 `stage_gate.IMPLEMENTED_CRITERIA` 塞两个 id → `core_chain` PASS | 该集合已删除，改为 AST 绑定 → 必须改**函数体** |
| `D4` | 把 `registry/delivery.yaml` 的 `check_kind: automated` 改成 `manual` → PASS | 新增断言「判据不得降级为非自动」 |
| `E`  | 把 `implementation_carrier` 改成不存在的路径 → 阶段① 仍 PASS | 新增「载体必须真实存在」断言 |
| `E2` | 改 `schema/models.py` 不改生成物 → 17 门禁 + 105 测试全绿 | 新增 `schema_sync_guard.py` |

**这一整个文件的用途是"防止修复被回退"**：它们断言的不是功能，而是
"这条绕过路径已经不成立了"。缺了它们，下一次重构很容易把口子重新打开。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from conftest import SYSTEM_ROOT, assert_rejected, run_gate

GATE = "scripts/delivery/stage_gate.py"
SCHEMA_GUARD = "scripts/checks/schema_sync_guard.py"
REGISTRY_FILE = "registry/delivery.yaml"
PREP_FILE = "registry/prep_deliverables.yaml"


def _read_yaml(root: Path, rel: str) -> dict:
    return yaml.safe_load((root / rel).read_text(encoding="utf-8"))


def _write_yaml(root: Path, rel: str, doc: dict) -> None:
    (root / rel).write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _core_chain_has_data(root: Path) -> None:
    """补上 `core_chain` 的前置产物，使阶段③ 有资格进入"该不该 PASS"的判定。"""
    (root / "facts" / "relations.jsonl").write_text(
        json.dumps({"relation_id": "r1", "subject_id": "a", "object_id": "b"}) + "\n",
        encoding="utf-8",
    )
    (root / "facts" / "impacts.jsonl").write_text(
        json.dumps(
            {
                "impact_id": "i1",
                "conditions": ["c1"],
                "counter_forces": ["f1"],
                "time_lag": "1Q",
            }
        )
        + "\n",
        encoding="utf-8",
    )


# ═══════════ D3：不能靠"改一张手写清单"把未实现判据变成已实现 ═══════════

def test_hand_maintained_impl_set_no_longer_exists() -> None:
    """`IMPLEMENTED_CRITERIA` 这个手写集合必须**不再被定义**（D3 的绕过入口）。

    ★ 判据是"**没有这个绑定**"，不是"文件里不出现这几个字" ——
      源码注释里必须能引用旧名字来解释"为什么删掉它"，否则后人会重新加回来。
      用 AST 查模块级赋值目标，比字符串匹配精确。
    """
    import ast

    source = (SYSTEM_ROOT / "scripts" / "delivery" / "stage_gate.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    bound_names = {
        tgt.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for tgt in node.targets
        if isinstance(tgt, ast.Name)
    }
    bound_names |= {
        node.target.id
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert "IMPLEMENTED_CRITERIA" not in bound_names, (
        "手写实现清单又被定义回来了 —— D3 绕过会重新成立（应使用 bound_criteria() 的 AST 绑定）"
    )
    assert "def bound_criteria(" in source


def test_unimplemented_criterion_blocks_stage_even_with_data(code_root: Path) -> None:
    """★ D3 回归：补上数据后，**未实现**的 `t01_t14_all_pass` 必须阻断阶段③。"""
    _core_chain_has_data(code_root)
    proc = run_gate(GATE, code_root, "--stage", "core_chain")
    assert proc.returncode == 1, (
        f"阶段③ 带着未实现判据 PASS 了（D3 复活）\n{proc.stdout}\n{proc.stderr}"
    )
    assert "t01_t14_all_pass" in proc.stdout
    assert "criteria_not_implemented" in proc.stdout
    assert "core_chain: BLOCKED" in proc.stdout


def test_criterion_declared_but_not_bound_in_function_body_is_rejected(code_root: Path) -> None:
    """★ D3 的另一半：往 YAML **新增**一条 automated 判据（函数体没绑定）→ 阶段① FAIL。"""
    doc = _read_yaml(code_root, REGISTRY_FILE)
    for stage in doc["delivery_stages"]:
        if stage.get("key") == "prep":
            stage["pass_criteria_testable"].append(
                {"id": "ghost_criterion", "statement": "幽灵判据", "check_kind": "automated"}
            )
    _write_yaml(code_root, REGISTRY_FILE, doc)

    assert_rejected(run_gate(GATE, code_root, "--stage", "prep"), rule_hint="ghost_criterion")


# ═══════════ D4：不能把 automated 判据自行降级 ═══════════

def test_downgrading_check_kind_is_rejected(code_root: Path) -> None:
    """★ D4 回归：把 `check_kind` 从 `automated` 改成 `manual` → 必须 FAIL。

    审计员当时只改了一个词，`core_chain` 就从 BLOCKED 变成 PASS。
    """
    doc = _read_yaml(code_root, REGISTRY_FILE)
    for stage in doc["delivery_stages"]:
        if stage.get("key") == "core_chain":
            for crit in stage["pass_criteria_testable"]:
                crit["check_kind"] = "manual"
    _write_yaml(code_root, REGISTRY_FILE, doc)
    _core_chain_has_data(code_root)

    proc = run_gate(GATE, code_root, "--stage", "core_chain")
    assert_rejected(proc, rule_hint="不得")
    assert "降级为非自动检查" in proc.stdout


# ═══════════ E：implementation_carrier 必须真实存在 ═══════════

def test_nonexistent_carrier_is_rejected(code_root: Path) -> None:
    """★ E 回归：载体指向不存在的文件 → 必须 FAIL（初版只校验非空字符串）。"""
    doc = _read_yaml(code_root, PREP_FILE)
    doc["confirmed_rules"][0]["implementation_carrier"] = "scripts/does_not_exist/nowhere.py"
    _write_yaml(code_root, PREP_FILE, doc)

    assert_rejected(run_gate(GATE, code_root, "--stage", "prep"), rule_hint="文件不存在")


def test_existing_carrier_passes(code_root: Path) -> None:
    """**反向对照**：载体真实存在 → 放行（否则这条断言会把真载体也拦掉）。"""
    doc = _read_yaml(code_root, PREP_FILE)
    doc["confirmed_rules"][0]["implementation_carrier"] = "scripts/checks/conflict_scan.py"
    _write_yaml(code_root, PREP_FILE, doc)

    proc = run_gate(GATE, code_root, "--stage", "prep")
    assert proc.returncode == 0, f"真实载体被误报\n{proc.stdout}\n{proc.stderr}"


# ═══════════ E2：schema 生成物漂移必须被发现 ═══════════

def test_schema_drift_is_detected(code_root: Path) -> None:
    """★ E2 回归：改 `models.py` 不同步生成物 → 必须 FAIL（初版 17 门禁全绿）。"""
    models = code_root / "schema" / "models.py"
    original = models.read_text(encoding="utf-8")
    models.write_text(
        original.replace(
            "    rule_version: str",
            "    rule_version: str\n    drifted_new_field: str = \"x\"",
            1,
        ),
        encoding="utf-8",
    )
    assert models.read_text(encoding="utf-8") != original, "注入失败：未找到锚点"
    assert_rejected(run_gate(SCHEMA_GUARD, code_root), rule_hint="漂移")


def test_in_sync_schema_passes(code_root: Path) -> None:
    """**反向对照**：生成物与模型一致 → 放行。

    ★ 断言里的对象数**由注册表现取**（不写字面量 18/22）：表数是需求方裁定项
      （2026-09-16 由 18 扩至 22，见 `schema/stems.py`），把它抄进测试就是又一份手工台账；
      而这里要证的命题与具体数字无关 —— "报告里的对象数 == 注册表里的 stem 数"。
    """
    from schema.models import JSONL_MODELS  # 本用例已需 pydantic；与守卫口径同一真源

    proc = run_gate(SCHEMA_GUARD, code_root)
    assert proc.returncode == 0, f"同步的 schema 被误报\n{proc.stdout}\n{proc.stderr}"
    assert f"objects: {len(JSONL_MODELS)}" in proc.stdout


def test_schema_guard_loaded_from_checked_code_root(code_root: Path) -> None:
    """★ 关键：守卫必须加载**被检 code_root** 的 schema 包。

    若加载的是守卫自己那份，给副本注入漂移时会"看不见" → 永远 PASS。
    `test_schema_drift_is_detected` 能失败，本身就是这条的证明。
    """
    source = (SYSTEM_ROOT / "scripts" / "checks" / "schema_sync_guard.py").read_text(encoding="utf-8")
    assert "def _load_builder(" in source
    assert "sys.modules" in source, "必须清掉已缓存的 schema 包，否则加载的是本脚本自己那份"


# ═══════════ 判据台账：绑定数必须可观测 ═══════════

@pytest.mark.parametrize("stage", ["prep", "nvidia_sample", "core_chain", "daily_run", "expansion"])
def test_criteria_binding_is_reported_per_stage(stage: str, code_root: Path) -> None:
    """每个阶段都必须报出"声称 automated"与"函数体真的绑定"两个计数（可观测）。"""
    proc = run_gate(GATE, code_root, "--stage", stage)
    assert f"{stage}.criteria_bound" in proc.stdout
    assert f"{stage}.criteria_not_implemented" in proc.stdout
