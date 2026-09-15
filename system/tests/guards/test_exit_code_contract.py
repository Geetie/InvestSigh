"""守卫**退出码契约**测试（`施工图 §3.4` 具名的 `tests/guards/`）。

`§5.1 AC-04` 要求「注入违例 → 检查器 **exit 1**（不是 warn）」；
`§八 N-2` 要求「退出码 `0` 放行 / `1` 阻断 / `2` 输入异常，**不静默**」。

本文件守住**契约本身**，而不是某一条规则：
- 干净输入 → `0`
- `code_root` 不存在 → `2`（**输入异常必须与"通过"区分开**）
- 未知参数 → argparse 拒绝（非 0）

为什么值得单独成测：退出码是**门禁与 CI 之间唯一的接口**。
`0/1/2` 一旦被折叠（例如把输入异常也返回 0），整条流水线会在"什么都没检查"时全绿。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SYSTEM_ROOT = Path(__file__).resolve().parents[2]      # tests/guards/ → tests/ → system/

# (显示名, 相对脚本路径, 额外参数)
GUARDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("conflict_scan", "scripts/checks/conflict_scan.py", ("--timing", "ci")),
    ("append_only_guard", "scripts/checks/append_only_guard.py", ()),
    ("rules_lock_guard", "scripts/checks/rules_lock_guard.py", ()),
    ("registry_schema_guard", "scripts/checks/registry_schema_guard.py", ()),
    ("schema_sync_guard", "scripts/checks/schema_sync_guard.py", ()),
    ("assert_gate_input", "scripts/checks/assert_gate_input.py", ()),
    ("freeze_guard", "scripts/checks/freeze_guard.py", ()),
    ("launch_guard", "scripts/checks/launch_guard.py", ()),
    ("module_denylist", "scripts/checks/module_denylist.py", ()),
    ("no_signal_day", "scripts/checks/no_signal_day.py", ()),
    ("no_placeholder_guard", "scripts/checks/no_placeholder_guard.py", ("--fail-on", "warn")),
    ("neutrality_check", "scripts/views/neutrality_check.py", ()),
    ("return_guard", "scripts/benchmark/return_guard.py", ()),
    ("anti_padding", "scripts/scope/anti_padding.py", ()),
    ("gap_to_task", "scripts/tasks/gap_to_task.py", ()),
    ("traceback", "scripts/trace/traceback.py", ()),
    ("pipeline", "scripts/orchestrate/pipeline.py", ()),
    ("stage_gate", "scripts/delivery/stage_gate.py", ("--stage", "prep")),
)


def _run(script: str, *args: str, timeout: float = 60.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SYSTEM_ROOT / script), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.mark.parametrize(("name", "script", "extra"), GUARDS, ids=[g[0] for g in GUARDS])
def test_every_guard_exits_zero_on_pristine_tree(
    name: str, script: str, extra: tuple[str, ...]
) -> None:
    """干净树上每个守卫都必须 `exit 0`（否则门禁恒红 → 会被关掉）。"""
    proc = _run(script, str(SYSTEM_ROOT), "--no-report", *extra)
    assert proc.returncode == 0, (
        f"{name} 在干净树上非零退出（exit={proc.returncode}）\n{proc.stdout}\n{proc.stderr}"
    )


@pytest.mark.parametrize(("name", "script", "extra"), GUARDS, ids=[g[0] for g in GUARDS])
def test_every_guard_reports_input_error_for_missing_code_root(
    name: str, script: str, extra: tuple[str, ...]
) -> None:
    """★ `code_root` 不存在 → 必须 `exit 2`（**不得折叠成 0 = 静默通过**）。"""
    proc = _run(script, "/nonexistent/code_root_for_guard_contract_test", "--no-report", *extra)
    assert proc.returncode == 2, (
        f"{name} 对不存在的 code_root 返回 exit={proc.returncode}（应为 2）\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


@pytest.mark.parametrize(("name", "script", "extra"), GUARDS, ids=[g[0] for g in GUARDS])
def test_every_guard_reports_scanned_count(
    name: str, script: str, extra: tuple[str, ...]
) -> None:
    """★ 每个守卫都必须报出 `scanned` 计数 —— 「扫了 0 个对象」与
    「扫了 N 个且都没问题」不是同一件事（防 `§6.2 Phantom Subscription`）。"""
    proc = _run(script, str(SYSTEM_ROOT), "--no-report", *extra)
    assert "scanned " in proc.stdout, f"{name} 未上报 scanned 计数\n{proc.stdout}"


def test_unknown_option_is_not_silently_ignored() -> None:
    """未知选项必须被 argparse 拒绝（非 0），不得被当成"没传"而放行。"""
    proc = _run("scripts/checks/conflict_scan.py", str(SYSTEM_ROOT), "--definitely-not-an-option")
    assert proc.returncode != 0
