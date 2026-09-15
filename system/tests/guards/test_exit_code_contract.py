"""守卫**退出码契约**测试（`施工图 §3.4` 具名的 `tests/guards/`）。

`§5.1 AC-04` 要求「注入违例 → 检查器 **exit 1**（不是 warn）」；
`§八 N-2` 要求「退出码 `0` 放行 / `1` 阻断 / `2` 输入异常，**不静默**」。

本文件守住**契约本身**（不是某一条规则）：

| 断言 | 含义 |
|---|---|
| 干净输入 → `0` | 否则门禁恒红 → 会被关掉 |
| `code_root` 缺失 → `2` | **输入异常必须与"通过"区分开**；折叠成 0 就是静默放行 |
| 必报 `scanned` 计数 | 「扫了 0 个对象」≠「扫了 N 个都没问题」（防 `§6.2 Phantom Subscription`） |

## 关于执行方式（重要，直接影响测试耗时）

矩阵用**进程内 `main()`** 调用，而不是起 100 多次子进程：
检查器的 `main(argv)` 本来就**返回**退出码，`sys.exit(main())` 只是把它交给进程。
矩阵关心的是"返回码随输入怎么变"，不是"shell 能不能拿到它" ——
而每次子进程启动约 0.15~1.0s，全部花在解释器启动与依赖导入上，与断言无关
（实测这一项就占整个测试套件 30s 以上）。

**代价是被换掉的那点保真度，由两条子进程用例单独补回**：
- `test_cli_wiring_exits_with_main_return_code`：证明 `python <脚本>` 真能拿到该退出码
- `test_unknown_option_is_not_silently_ignored`：证明 argparse 真的拒绝未知参数
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SYSTEM_ROOT, run_gate_inproc
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

GUARD_IDS = [g[0] for g in GUARDS]


def test_guard_matrix_is_not_empty() -> None:
    """**元断言**：矩阵本身不得为空/退化。

    一个空的 `parametrize` 会让 pytest 收集到 0 个用例而**静默全绿** ——
    比任何单条断言失败都危险（"什么都没测"看起来和"全部通过"一样）。
    """
    assert len(GUARDS) == 18, f"守卫矩阵项数异常: {len(GUARDS)}"
    assert len({name for name, _, _ in GUARDS}) == len(GUARDS), "守卫名重复"
    for _, script, _ in GUARDS:
        assert (SYSTEM_ROOT / script).exists(), f"矩阵里有不存在的脚本: {script}"


@pytest.mark.parametrize(("name", "script", "extra"), GUARDS, ids=GUARD_IDS)
def test_guard_exits_zero_and_reports_scanned_on_pristine_tree(
    name: str, script: str, extra: tuple[str, ...]
) -> None:
    """干净树上：`exit 0` **且**报出 `scanned` 计数。

    两条断言合成一个用例，是因为它们**共享同一次执行**（同一命令、同一输入）——
    拆成两个用例会把同一次执行跑两遍（实测白花 ~4.5s）。
    """
    code, out = run_gate_inproc(script, SYSTEM_ROOT, *extra)
    assert code == 0, f"{name} 在干净树上非零退出（code={code}）\n{out}"
    assert "scanned " in out, f"{name} 未上报 scanned 计数（无法区分「没扫」与「扫了没问题」）\n{out}"


@pytest.mark.parametrize(("name", "script", "extra"), GUARDS, ids=GUARD_IDS)
def test_guard_reports_input_error_for_missing_code_root(
    name: str, script: str, extra: tuple[str, ...]
) -> None:
    """★ `code_root` 不存在 → 必须返回 `2`（**不得折叠成 0 = 静默通过**）。"""
    code, out = run_gate_inproc(script, Path("/nonexistent/code_root_for_guard_contract"), *extra)
    assert code == 2, f"{name} 对不存在的 code_root 返回 {code}（应为 2）\n{out}"


# ── 保真度补回：这两条**必须**走真子进程 ──

def test_cli_wiring_exits_with_main_return_code() -> None:
    """★ 证明 `python <检查器>` 真能把 `main()` 的返回码交给 shell。

    矩阵用进程内调用换速度，那"CLI 接线是否完好"就必须单独守一条 ——
    否则可能出现"进程内全绿、命令行其实是坏的"。
    """
    script = SYSTEM_ROOT / "scripts" / "checks" / "freeze_guard.py"
    ok = subprocess.run(
        [sys.executable, str(script), str(SYSTEM_ROOT), "--no-report"],
        capture_output=True, text=True, timeout=60,
    )
    assert ok.returncode == 0, f"CLI 接线异常\n{ok.stdout}\n{ok.stderr}"

    bad = subprocess.run(
        [sys.executable, str(script), "/nonexistent/xyz", "--no-report"],
        capture_output=True, text=True, timeout=60,
    )
    assert bad.returncode == 2, f"CLI 未把输入异常的 2 传给 shell（实得 {bad.returncode}）"


def test_unknown_option_is_not_silently_ignored() -> None:
    """未知选项必须被 argparse 拒绝（非 0），不得被当成"没传"而放行。"""
    proc = subprocess.run(
        [
            sys.executable,
            str(SYSTEM_ROOT / "scripts" / "checks" / "conflict_scan.py"),
            str(SYSTEM_ROOT),
            "--definitely-not-an-option",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode != 0


def test_injection_blocks_at_process_level(code_root: Path) -> None:
    """★ **AC-04 的最终证据**：注入一个真实违例 → **真子进程** `exit 1`。

    套件里绝大多数检查器调用改成了进程内执行（省 30s+），所以必须留**至少一条**
    真进程用例把"命令行的阻断语义"钉死 —— 否则可能出现
    「进程内 exit 1、命令行其实是 exit 0」而无人发现。
    """
    import json

    # 注入 P-03 违例：`Recommendation` 上出现 `stop_loss` 字段
    schema_path = code_root / "schema" / "jsonschema" / "facts.schema.json"
    doc = json.loads(schema_path.read_text(encoding="utf-8"))
    doc["defs"]["Recommendation"]["properties"]["stop_loss"] = {"type": "number"}
    schema_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SYSTEM_ROOT / "scripts" / "checks" / "conflict_scan.py"),
         str(code_root), "--no-report", "--timing", "ci"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 1, (
        f"真进程注入违例后应 exit 1，实得 {proc.returncode}\n{combined}"
    )
    assert "P-03" in combined, f"未报出 P-03\n{combined}"
