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

# ───────────────── 矩阵从**真源派生**（缺口 `G-28` 的根治） ─────────────────
#
# ★ 为什么不再手写（实测缺陷 `G-28`）：本矩阵原先是**手写清单**，且自带
#   `assert len(GUARDS) == 20`。门禁从 20 增到 23、再到 24 的过程中，
#   **新增的守卫零覆盖**（`shell_var_guard` / `graph_integrity_guard` /
#   `locator_check` / `criterion_effectiveness_guard` 四条不在矩阵里），
#   而那条计数断言还在替 20 把关 —— **清单与真源各写一份，必然漂移**。
#   这正是本项目反复出现的形态：**同一事实的两个存放处**（同 `V-02` 对
#   "批次里有多少项"的处理：数字只留在真源里）。
#
# ★ 派生后：**任何新守卫只要进 `GATES`，就自动**受「干净 → 0 / 缺 `code_root` → 2 /
#   必报 `scanned`」三条契约约束 —— 谁都不需要再改本文件。
#
# ★ 单例真源 = `run_all_gates.py::GATES`。**不复制**它的内容。
_GATES_REL = "scripts/ops/run_all_gates.py"
_TIMING = "ci"
"""`--timing` 的取值：与 `run_all_gates` 的 CI 口径一致（矩阵只关心退出码，不关心时机）。"""


def _load_gates() -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """按**文件路径**加载真源的 `GATES`（不依赖包导入顺序，零全局副作用）。"""
    import importlib.util

    path = SYSTEM_ROOT / _GATES_REL
    spec = importlib.util.spec_from_file_location("_run_all_gates_under_contract", path)
    if spec is None or spec.loader is None:  # pragma: no cover - 仅在文件不可读时
        raise ImportError(f"无法加载门禁真源: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(module.GATES)


def _render(extra: tuple[str, ...]) -> tuple[str, ...]:
    """把真源里的占位符渲染成本矩阵用的实参。

    ★ **未知占位符必须响亮失败**：若静默原样传给守卫，守卫就会拿一个**不存在的取值**去跑，
      退出码契约于是**形同虚设**（"用错参数跑通了"看起来和"契约成立"一样）。
    """
    rendered: list[str] = []
    for token in extra:
        if token == "{timing}":
            rendered.append(_TIMING)
        elif "{" in token or "}" in token:
            raise ValueError(
                f"`GATES` 出现未登记的占位符 {token!r} —— 本矩阵不知道怎么渲染它。"
                "请在 `_render()` 里登记，或去掉该占位符；**不得静默原样下传**。"
            )
        else:
            rendered.append(token)
    return tuple(rendered)


# (显示名, 相对脚本路径, 额外参数) —— **派生**，不再手写
GUARDS: tuple[tuple[str, str, tuple[str, ...]], ...] = tuple(
    (display.split()[0].removesuffix(".py"), relscript, _render(extra))
    for display, relscript, extra in _load_gates()
)

GUARD_IDS = [g[0] for g in GUARDS]


def test_guard_matrix_derives_from_gates_one_to_one() -> None:
    """**元断言**：矩阵必须与真源 `run_all_gates.GATES` **一一对应**。

    ★ 这里**不再写"矩阵有 N 项"**（那是同一事实的第二个存放处，`G-28` 就是这么烂掉的）。
      改查三件**结构性**性质：

    1. 矩阵与真源的 **relscript 集合完全相等**（既不漏、也不多）——
       ★ 这一条防的是"有人给派生加了个 filter/skip"：那会让某条守卫**静默退出契约覆盖**，
       而派生的表象会让它看起来"自动覆盖了"。**派生 ≠ 不可被削弱**，故仍需断言。
    2. 显示名唯一（`parametrize` 的 id 会合并同名项 → 用例数悄悄变少）。
    3. 每个脚本**真实存在**（防真源里写了不存在的路径）。
    4. 矩阵非空（空 `parametrize` 会收集到 0 个用例而**静默全绿** —— 比任何单条失败都危险）。
    """
    gates = _load_gates()
    assert len(GUARDS) > 0, "守卫矩阵为空 —— 空 parametrize 会静默全绿"
    assert {s for _, s, _ in GUARDS} == {s for _, s, _ in gates}, (
        "矩阵与真源 GATES 的脚本集合不一致 —— 派生被削弱了（有人加了 filter/skip？）"
    )
    # 显示名要**按同一口径归一化**再比（真源写的是 `conflict_scan.py` /
    # `stage_gate.py --stage prep`，矩阵用的是归一化后的 `conflict_scan` / `stage_gate`）——
    # 我第一版就是漏了这一步，拿两套口径直接比集合，于是断言自成假红。
    expected_names = {d.split()[0].removesuffix(".py") for d, _, _ in gates}
    assert {n for n, _, _ in GUARDS} == expected_names, (
        "矩阵与真源 GATES 的显示名集合不一致（按归一化口径比较）"
    )
    assert len({name for name, _, _ in GUARDS}) == len(GUARDS), "守卫名重复"
    for _, script, _ in GUARDS:
        assert (SYSTEM_ROOT / script).exists(), f"矩阵里有不存在的脚本: {script}"


@pytest.mark.parametrize(("name", "script", "extra"), GUARDS, ids=GUARD_IDS)
def test_guard_exits_zero_and_reports_scanned_on_pristine_tree(
    name: str, script: str, extra: tuple[str, ...], pristine_code_root: Path
) -> None:
    """干净树上：`exit 0` **且**报出 `scanned` 计数。

    两条断言合成一个用例，是因为它们**共享同一次执行**（同一命令、同一输入）——
    拆成两个用例会把同一次执行跑两遍（实测白花 ~4.5s）。

    ★ `code_root` 用 `pristine_code_root`（**真源为空**的副本），**不是** `SYSTEM_ROOT`（真仓库）
      —— 见 `conftest.pristine_code_root` 与缺口 `G-RC-03`：真实数据入真源后
      `traceback` / `no_signal_day` **如实**变红，若此处拿真仓库当真源，
      **真违规会被淹没成"守卫坏了"**。判据只该问"守卫代码在干净输入上是否正确"。
    """
    code, out = run_gate_inproc(script, pristine_code_root, *extra)
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
