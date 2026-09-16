"""验证规范守卫的注入测试（`CONVENTIONS.md §一 V-01~V-06`）。

**本文件的用途是"防止规范被改回去"**：它断言的不是功能，而是
「这些绕过路径已不成立」。缺了它，下一次重构很容易把口子重新打开 ——
而本项目的铁律是**「声明与实现必须有机器绑定」**：只写在 `CONVENTIONS.md` 里的规范等于不存在。

覆盖 5 条绕过路径（全部是**真实可犯的错**，不是编出来的）：

| 反例 | 绕过方式 | 对应规范 |
|---|---|---|
| A | 让 `verify.py` 不带 `--batch` 也能跑（隐式全量） | V-01 |
| B | 加一个以裸 `tests` 为目标的"全量批次" | V-01 |
| C | 把某批超时设成 0 或不设上限 | V-02 |
| D | 把超时码 `124` 判成通过 | V-03 |
| E | 去掉 `run_pytest.sh` 的 broker 关闭（测试又跑在沙箱里） | V-04 |
| F | 新增测试目录却不加批次（测试永远不被跑） | V-06 |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import assert_rejected, run_gate

GUARD = "scripts/checks/verification_policy_guard.py"
VERIFY_REL = "scripts/ops/verify.py"
RUN_PYTEST_REL = "scripts/ops/run_pytest.sh"


def _patch(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, f"注入失败：{rel} 中未找到锚点 {old[:60]!r}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# ═══════════════ 反向对照（先证明守卫在干净树上不误报） ═══════════════

def test_policy_guard_passes_on_pristine_tree(code_root: Path) -> None:
    proc = run_gate(GUARD, code_root)
    assert proc.returncode == 0, f"干净树上验证规范守卫误报\n{proc.stdout}\n{proc.stderr}"
    assert "batches: 7" in proc.stdout
    assert "test_files_uncovered: 0" in proc.stdout


# ═══════════════ A · 隐式全量验证（V-01） ═══════════════

def test_implicit_full_run_is_rejected(code_root: Path) -> None:
    """让 `verify.py` 不带 `--batch` 也返回 0 → 必须 FAIL（那就是隐式全量验证）。"""
    _patch(code_root, VERIFY_REL, "return 0 if args.list else 2", "return 0")
    proc = run_gate(GUARD, code_root)
    assert_rejected(proc, rule_hint="V-01")
    assert "拒绝隐式全量验证" in proc.stdout


# ═══════════════ B · 全量批次（V-01） ═══════════════

def test_full_suite_batch_is_rejected(code_root: Path) -> None:
    """把某批目标改成裸 `tests`（全量）→ 必须 FAIL。"""
    _patch(
        code_root,
        VERIFY_REL,
        '_pytest("tests/test_ch11_invariants.py"), 30.0',
        '_pytest("tests"), 600.0',
    )
    assert_rejected(run_gate(GUARD, code_root), rule_hint="全量批次")


def test_batch_target_outside_tests_is_rejected(code_root: Path) -> None:
    """批次目标指向 `tests/` 之外 → 必须 FAIL（防止把脚本/门禁混进 pytest 批次）。"""
    _patch(code_root, VERIFY_REL, '_pytest("tests/unit")', '_pytest("scripts")')
    assert_rejected(run_gate(GUARD, code_root), rule_hint="不在 tests/ 下")


# ═══════════════ C · 超时值不适合（V-02） ═══════════════

@pytest.mark.parametrize("bad_timeout", ["0.0", "9999.0"])
def test_unreasonable_timeout_is_rejected(bad_timeout: str, code_root: Path) -> None:
    """超时设为 0 或无上限（>300s）→ 必须 FAIL。"""
    _patch(
        code_root,
        VERIFY_REL,
        '_pytest("tests/conflict"), 30.0',
        f'_pytest("tests/conflict"), {bad_timeout}',
    )
    assert_rejected(run_gate(GUARD, code_root), rule_hint="V-02")


# ═══════════════ D · 超时被判成通过（V-03） ═══════════════

def test_timeout_treated_as_pass_is_rejected(code_root: Path) -> None:
    """把超时码 124 的判定改成"通过" → 必须 FAIL。

    这是本规范里**最危险**的一种退化：卡死的批次若被当成通过，
    等于门禁整体失效（`V-03`：超时 = 该批有问题，绝不算通过）。
    """
    _patch(
        code_root,
        VERIFY_REL,
        '        return False, "**超时** —— 该批有问题（极大概率是测试本身）"',
        '        return True, "ok"',
    )
    assert_rejected(run_gate(GUARD, code_root), rule_hint="V-03")


def test_timeout_verdict_without_keyword_is_rejected(code_root: Path) -> None:
    """超时判定返回不合格但**没说明是超时** → 仍必须 FAIL（要能被识别归因）。"""
    _patch(
        code_root,
        VERIFY_REL,
        '        return False, "**超时** —— 该批有问题（极大概率是测试本身）"',
        '        return False, "some failure"',
    )
    assert_rejected(run_gate(GUARD, code_root), rule_hint="未说明")


# ═══════════════ E · 去掉沙箱外跑的修正（V-04） ═══════════════

def test_missing_broker_env_in_run_pytest_is_rejected(code_root: Path) -> None:
    """删掉 `run_pytest.sh` 里关闭 broker 的环境变量 → 必须 FAIL。"""
    _patch(code_root, RUN_PYTEST_REL, "export CODEBUDDY_SAFE_DELETE_SANDBOX=0", "# (removed)")
    assert_rejected(run_gate(GUARD, code_root), rule_hint="V-04")


def test_missing_broker_env_in_verify_is_rejected(code_root: Path) -> None:
    """删掉 `verify.py::_child_env` 里关闭 broker 的环境变量 → 必须 FAIL。"""
    _patch(
        code_root,
        VERIFY_REL,
        '"CODEBUDDY_BROKERED_FS_HOOK_ENABLED": "0",',
        "",
    )
    assert_rejected(run_gate(GUARD, code_root), rule_hint="V-04")


# ═══════════════ F · 新增测试却不入批（V-06） ═══════════════

def test_uncovered_new_test_file_is_rejected(code_root: Path) -> None:
    """新增一个**没有对应批次**的测试目录 → 必须 FAIL（否则它永远不被验证）。"""
    new_dir = code_root / "tests" / "brand_new_suite"
    new_dir.mkdir(parents=True, exist_ok=True)
    (new_dir / "test_something.py").write_text(
        "def test_placeholder_free() -> None:\n    assert True\n", encoding="utf-8"
    )
    proc = run_gate(GUARD, code_root)
    assert_rejected(proc, rule_hint="V-06")
    assert "tests/brand_new_suite/test_something.py" in proc.stdout


def test_new_file_inside_existing_batch_is_allowed(code_root: Path) -> None:
    """**反向对照**：在**已被批次覆盖**的目录里新增测试文件 → 必须放行。"""
    (code_root / "tests" / "unit" / "test_brand_new_but_covered.py").write_text(
        "def test_ok() -> None:\n    assert True\n", encoding="utf-8"
    )
    proc = run_gate(GUARD, code_root)
    assert proc.returncode == 0, f"已被批次覆盖的新测试被误报\n{proc.stdout}\n{proc.stderr}"
