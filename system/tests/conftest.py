"""测试夹具（`00_开发Agent开工提示词 §三 tests/` / `§5.1 AC-04`）。

两条设计原则：

1. **真代码 + 污染数据**：检查器一律跑**仓库里的真实脚本**（不是副本），
   只把 `code_root` 指向 `tmp_path` 的**副本**。这样测的是真实实现，
   不会被"复制出来的旧代码"骗过。
2. **子进程级断言**：断言的是**进程退出码**，不是"函数返回了违例列表"。
   `§5.1 AC-04` 要求"注入一个违例 → 检查器 **exit 1**（**不是 warn**）"——
   只有真跑进程才能证明 CLI 出口没把 1 吞成 0。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

SYSTEM_ROOT = Path(__file__).resolve().parents[1]      # .../InvestSigh/system
REPO_ROOT = SYSTEM_ROOT.parent                          # .../InvestSigh
if str(SYSTEM_ROOT) not in sys.path:
    sys.path.insert(0, str(SYSTEM_ROOT))

# ★ 夹具工作目录刻意落在**工作区内**的 `tests/.work/`，不用 pytest 的 `tmp_path`：
#   WorkBuddy 沙箱对工作区**之外**的 `mkdir` 走 broker，目录已存在时抛
#   `PermissionError: EEXIST`（而非 `FileExistsError`），`tmp_path` 因此整体崩掉。
#   放在 `tests/` 下还有两个好处：① `walk_files` 本就跳过点目录；
#   ② `tests/**` 在反占位符扫描里是免扫命名空间。
WORK_DIR = SYSTEM_ROOT / "tests" / ".work"

# session 级：同一 `(脚本, code_root, 参数)` 的结果只算一次（见 `run_gate`）
_GATE_RESULT_CACHE: dict[tuple[str, str, tuple[str, ...]], GateResult] = {}

# 复制夹具时跳过的目录：缓存与**可重建**产物（index 可全量重建、reports 是运行产物）
_COPY_SKIP = {"__pycache__", ".pytest_cache", ".venv", ".work", "index", "reports", ".locks"}
# 阶段① 内必然为空的目录，夹具里补出来供注入测试写入
_ENSURE_DIRS = ("views", "raw", "derived", "snapshots", "index")

# ★★ 夹具的**真源契约**：每个 `code_root` 一律从**空真源**起步。
#
# 为什么必须显式做这件事（实测，批次 8 `G-RC-02`）：
#   夹具用 `copytree(SYSTEM_ROOT, ...)` 复制整个 `system/` —— **包括 `facts/` 与 `raw/`**。
#   项目此前从没有过真实数据，所以"复制过来也等于空"，这个耦合一直没被发现。
#   一旦 `ws/real-collect` 落入第一批**真实** claim / 边 / 基线，立刻炸出：
#     `tests/claim` 8 failed · `tests/graph` 5 failed · `tests/validators` 2 failed。
#   根因不是数据错、也不是代码错，而是**测试侧契约没随真源演进**：
#   `test_locator_check` 断言 `NO_CLAIMS`、`test_graph_integrity_guard` 断言 `NO_EDGE_DATA` ——
#   这些用例要测的是"**无被检对象**"这一分支，可它们却**依赖仓库里恰好没有数据**。
#
# 正确契约 = **测试自己声明自己的数据**：夹具给空真源，需要的用例自行 `append_records` 写入。
# 这样"仓库里有没有真实数据"与"测试是否通过"**彻底解耦**（这也是能让真实数据进主线的前提）。
_TRUTH_STEMS = (
    "industry_nodes", "companies", "securities", "business_positions", "products", "relations",
    "sources", "claims", "claim_propagation", "events", "impacts", "baselines", "prices",
    "expectations", "benchmarks", "recommendations", "dependency_edges", "tasks",
)


def _reset_truth_source(target: Path) -> None:
    """把夹具副本的**真源**清空：`facts/*.jsonl` 归零、`raw/` 只留 `.gitkeep`。

    只动**数据**，不动**结构**：18 个 JSONL 仍然全部存在（`Ch9 §3.3.3`「不得增删改名」的断言照旧可测），
    `raw/` 目录仍在（`full_text_read` 的路径可写）。
    """
    facts = target / "facts"
    if facts.is_dir():
        for stem in _TRUTH_STEMS:
            (facts / f"{stem}.jsonl").write_text("", encoding="utf-8")
    raw = target / "raw"
    if raw.is_dir():
        for item in list(raw.iterdir()):
            if item.name == ".gitkeep":
                continue
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)


def _ignore(_dir: str, names: list[str]) -> set[str]:
    """跳过缓存 / 可重建产物 / 夹具自身的工作目录（否则递归复制自己）。"""
    return {n for n in names if n in _COPY_SKIP or n.startswith(".")}


def _make_writable(target: Path) -> None:
    """把副本整体改成可写。

    ★ 必须做：`rules/**` 在真仓库里是 **0444**（纪律 9/10），而注入测试
      需要**改写规则文件**来制造违例。`copytree` 会继承源权限，不改就
      "注入"不进去，测试会以 `PermissionError` 崩掉而不是断言门禁生效。
      真仓库的 0444 由 `scripts/checks/rules_lock_guard.py` 单独验证
      （该测试会**显式**把权限改回 0444）。
    """
    for path in target.rglob("*"):
        try:
            if path.is_dir():
                path.chmod(0o755)
            else:
                path.chmod(0o644)
        except OSError:
            continue


@pytest.fixture()
def code_root(request: pytest.FixtureRequest) -> Path:
    """一份干净的 `system/` 副本（每个测试一份，互不污染，用完即删）。"""
    target = WORK_DIR / f"{request.node.name}-{uuid.uuid4().hex[:8]}" / "system"
    try:
        shutil.copytree(SYSTEM_ROOT, target, ignore=_ignore)
        for sub in _ENSURE_DIRS:
            (target / sub).mkdir(parents=True, exist_ok=True)
        _make_writable(target)
        # ★ 空真源契约（见上方 `_reset_truth_source` 的说明）：必须放在 `_make_writable` **之后**，
        #   否则清空动作会在 0444 的 `raw/` 子项上抛 `PermissionError`。
        _reset_truth_source(target)
        yield target
    finally:
        shutil.rmtree(target.parent, ignore_errors=True)


def _lock_rules_perms(target: Path) -> None:
    """把副本的 `rules/**` 复原为 `0444`（纪律 9 的不变量）。

    ★ 为什么必须做：`_make_writable()` 把整个副本改成 0644（因为**注入测试需要可写**），
      但 `rules/` 的 0444 是**纪律 9 的不变量**，而 `rules_lock_guard` 与 `injection_guard`
      **正是按 0444 判定的**（`Ch9 §3.10 J9` / 纪律 10）。
      实测：`pristine_code_root` 初版漏了这一步 → 两个守卫在副本上 `exit=1`
      （报"权限为 0o644，应为 0o444"）→ 被判成"守卫坏了"，**又是一次假缺陷**。

    ★ 这与 `scripts/ops/bootstrap_worktree.sh` 对新工作树做的事**同源**（git 不跟踪只读位），
      只是这里针对的是**夹具副本**。
    """
    rules = target / "rules"
    if not rules.is_dir():
        return
    for item in rules.rglob("*"):
        try:
            item.chmod(0o444 if item.is_file() else 0o755)
        except OSError:
            continue


@pytest.fixture(scope="session")
def pristine_code_root() -> Path:
    """一份**真源为空**的 `system/` 副本（session 级，懒建一次，用 `pytest_sessionfinish` 清理）。

    ★ 为什么需要它（`G-RC-03`，真实数据首次暴露）：
      「守卫在**干净树**上应 `exit 0`」这一类**契约用例**，必须对"干净"的输入做断言，
      而不能对"**仓库当前恰好有什么数据**"做断言 —— 否则两者会混成同一个信号：
      真实数据一进真源（`ws-real-collect`），`traceback`（见 `T-10`）与 `no_signal_day`（见 `G-RC-04`）
      **如实**变红，契约用例却把它当成"守卫坏了"→ **真违规被淹没成假缺陷**。

    ★ **不是掩盖**：`run_all_gates.py`（`gates` 批）跑的是**真仓库**，
      所以 `T-10` / `G-RC-04` 那两条真实违例**照样可见**，只是不再污染"守卫代码健康度"这一维度。

    ★ 与 `code_root` fixture 的区别：那个是**每用例一份**（互不污染，供注入测试改文件）；
      这个是**全 session 一份**（只读，供退出码契约矩阵复用，省掉 20+ 次 `copytree`）。
    """
    target = WORK_DIR / "_pristine" / "system"
    if not target.exists():
        shutil.copytree(SYSTEM_ROOT, target, ignore=_ignore)
        for sub in _ENSURE_DIRS:
            (target / sub).mkdir(parents=True, exist_ok=True)
        _make_writable(target)
        _reset_truth_source(target)
        _lock_rules_perms(target)
    return target


# ★ 双保险：单个 fixture 的 `finally` 在崩溃/中断时兜不住，
#   残留的夹具副本会被 git 当源码提交（实测曾积累 53 个目录）。
#   故在 session 起止各整目录清一次 —— **临时目录绝不允许进入仓库**。
def pytest_sessionstart(session: pytest.Session) -> None:
    shutil.rmtree(WORK_DIR, ignore_errors=True)
    _warn_if_fs_brokered()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    shutil.rmtree(WORK_DIR, ignore_errors=True)


def _warn_if_fs_brokered() -> None:
    """**响亮提示**：Python 层 FS broker 开着时，夹具复制会累积到卡死。

    实测：`CODEBUDDY_SAFE_DELETE_SANDBOX=1` 或 `CODEBUDDY_BROKERED_FS_HOOK_ENABLED=1`
    时，每次文件操作都走 IPC 到宿主进程。夹具 `copytree` 每用例复制 130 个文件，
    数百用例累积数万次往返 → **进程在某个点卡死，且卡点漂移**
    （实测 `tests/unit/test_contracts.py` 分别卡在第 15 / 17 / 19 条）。

    这里**只警告不退出**：万一宿主环境变了、broker 其实很快，也不该阻断测试。
    正确跑法见警告内容。
    """
    import os

    on = (
        os.environ.get("CODEBUDDY_SAFE_DELETE_SANDBOX") == "1"
        or os.environ.get("CODEBUDDY_BROKERED_FS_HOOK_ENABLED") == "1"
    )
    if not on:
        return
    print(
        "\n"
        "=" * 78 + "\n"
        "[WARNING] Python 层 FS broker 处于**启用**状态。\n"
        "  夹具 copytree 每用例复制 130 个文件 → 每个文件一次 broker IPC →\n"
        "  累积数万次往返后**进程会卡死**（卡点在用例之间漂移，无任何输出）。\n"
        "  正确跑法（沙箱外）：\n"
        "    sh system/scripts/ops/run_pytest.sh tests/<子目录>\n"
        "    或  python system/scripts/ops/verify.py --batch <unit|conflict|guards|injection|root>\n"
        "  （verify.py 已自动为子进程关闭 broker hook）\n"
        + "=" * 78 + "\n"
    )


class GateResult:
    """检查器一次执行的结果。属性名与 `subprocess.CompletedProcess` 对齐，
    使原有的 `proc.returncode / .stdout / .stderr` 断言写法无需改动。"""

    __slots__ = ("returncode", "stdout", "stderr")

    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_gate(script_rel: str, root: Path, *extra: str, timeout: float = 60.0) -> GateResult:
    """跑检查器，`code_root` 指向夹具副本。默认走**进程内 `__main__` 入口**。

    为什么不是子进程：一个测试套件里有 **80 次**检查器调用，每次子进程启动
    ≈ 0.31s（解释器 + yaml/pydantic 导入），合计 ≈ 25s —— 这是整个套件
    49s 里的全部大头（夹具复制实测只有 0.021s，不是瓶颈）。
    `runpy` 执行的是**与命令行完全相同的入口**，不 mock 任何东西。

    ★ 进程级保真度由这两条用例守住（它们必须用 `run_gate_subprocess`）：
      - `tests/guards/...::test_cli_wiring_exits_with_main_return_code`
      - `tests/guards/...::test_injection_blocks_at_process_level`
        （注入违例 → **真进程** exit 1，AC-04 的最终证据）

    ★ **同一 `(脚本, code_root, 参数)` 只跑一次**（session 级缓存）。
      若某个测试在**同一 `code_root`** 上先跑一次、改动后再跑同一命令，
      必须改用 `run_gate_subprocess` 或换一个 `code_root`（否则拿到旧结果）。
    """
    key = (script_rel, str(root), extra)
    hit = _GATE_RESULT_CACHE.get(key)
    if hit is not None:
        return hit
    code, out = _exec_gate_script(script_rel, root, extra)
    result = GateResult(code, out)
    _GATE_RESULT_CACHE[key] = result
    return result


def run_gate_subprocess(script_rel: str, root: Path, *extra: str, timeout: float = 60.0) -> GateResult:
    """跑检查器 —— **真子进程**（用于"CLI 接线"与"进程级阻断"这两类证据）。"""
    script = SYSTEM_ROOT / script_rel
    if not script.exists():
        raise FileNotFoundError(f"检查器脚本不存在: {script}")
    cmd = [sys.executable, str(script), str(root), "--no-report", *extra]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return GateResult(proc.returncode, proc.stdout, proc.stderr)


def _exec_gate_script(script_rel: str, root: Path, extra: tuple[str, ...]) -> tuple[int, str]:
    """执行脚本的 `__main__` 入口并捕获退出码（不 mock 任何东西）。"""
    import contextlib
    import io
    import runpy

    script = SYSTEM_ROOT / script_rel
    if not script.exists():
        raise FileNotFoundError(f"检查器脚本不存在: {script}")

    argv = [str(script), str(root), "--no-report", *extra]
    buf = io.StringIO()
    old_argv = sys.argv
    sys.argv = argv
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            runpy.run_path(str(script), run_name="__main__")
        code = 0
    except SystemExit as exc:
        # sys.exit(None) 等价于 0；sys.exit("msg") 等价于 1
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    finally:
        sys.argv = old_argv
    return int(code), buf.getvalue()


# 若某脚本**没有** `if __name__ == "__main__"` 块（只有 `main()`），
# 上面的 runpy 会"跑完但什么都没发生"（退出码恒 0）—— 那是**静默的假通过**。
# 这条断言把这种脚本挡在门外：调用后必须留下 `== <checker> ==` 的痕迹。
def assert_gate_actually_ran(script_rel: str, result: GateResult) -> None:
    assert "== " in result.stdout, (
        f"{script_rel} 看似执行了但没有输出 —— 可能缺少 `__main__` 入口块"
        f"（runpy 会静默返回 0，属于假通过）"
    )


# ── 进程内执行器（供"退出码契约"这类矩阵用例）────────────────────────────────
#
# ★ 为什么可以不用子进程：脚本的 `if __name__ == "__main__": sys.exit(main())`
#   会在 `sys.exit` 处抛 `SystemExit`，捕获它就拿到了**真实退出码**。
#   `runpy.run_path(..., run_name="__main__")` 执行的正是**命令行那条入口**，
#   不 mock 任何东西，只是省掉解释器启动（每次 0.15~1.0s，全部花在启动与
#   依赖导入上，与断言内容无关；实测这一项占整个测试套件 30s 以上）。
#
# ★ 不可用 `mod.main(argv)`：**17 个守卫脚本根本没有 `main()` 函数**，
#   它们直接写 `sys.exit(run_checker(...))`（实测踩过 —— 30 条用例集体
#   AttributeError）。`runpy` 对两种写法都成立。
#
# ★ 代价是被换掉的那点保真度，由子进程用例单独补回：
#   `test_cli_wiring_exits_with_main_return_code` 证明 `python <脚本>`
#   真能把退出码交给 shell；`test_unknown_option_is_not_silently_ignored`
#   证明 argparse 真的拒绝未知参数。
def run_gate_inproc(script_rel: str, root: Path, *extra: str) -> tuple[int, str]:
    """在**本进程内**走被检脚本的 `__main__` 入口，返回 `(退出码, 合并输出)`。"""
    import contextlib
    import io
    import runpy

    script = SYSTEM_ROOT / script_rel
    if not script.exists():
        raise FileNotFoundError(f"检查器脚本不存在: {script}")

    argv = [str(script), str(root), "--no-report", *extra]
    buf = io.StringIO()
    old_argv = sys.argv
    sys.argv = argv
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            runpy.run_path(str(script), run_name="__main__")
        code = 0
    except SystemExit as exc:
        # sys.exit(None) 等价于 0；sys.exit("msg") 等价于 1
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    finally:
        sys.argv = old_argv
    return int(code), buf.getvalue()


def assert_rejected(proc: GateResult, *, rule_hint: str = "") -> None:
    """断言"注入违例后被真的拦下"。

    - `exit 1` = 阻断（期望）
    - `exit 0` = **门禁失效**（这是本函数存在的唯一理由）
    - `exit 2` = 输入异常，也可能是"没找到被检对象"，单独提示
    """
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0, (
        f"注入违例后检查器仍 exit=0 —— 门禁失效（§5.1 AC-04 要求 exit 1）。\n输出:\n{combined}"
    )
    assert proc.returncode == 1, (
        f"期望 exit=1（阻断），实得 exit={proc.returncode}（输入异常？）。\n输出:\n{combined}"
    )
    if rule_hint:
        assert rule_hint in combined, f"输出中未出现期望的规则标记 {rule_hint!r}。\n输出:\n{combined}"
