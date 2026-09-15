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

# 复制夹具时跳过的目录：缓存与**可重建**产物（index 可全量重建、reports 是运行产物）
_COPY_SKIP = {"__pycache__", ".pytest_cache", ".venv", ".work", "index", "reports", ".locks"}
# 阶段① 内必然为空的目录，夹具里补出来供注入测试写入
_ENSURE_DIRS = ("views", "raw", "derived", "snapshots", "index")


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
        yield target
    finally:
        shutil.rmtree(target.parent, ignore_errors=True)


# ★ 双保险：单个 fixture 的 `finally` 在崩溃/中断时兜不住，
#   残留的夹具副本会被 git 当源码提交（实测曾积累 53 个目录）。
#   故在 session 起止各整目录清一次 —— **临时目录绝不允许进入仓库**。
def pytest_sessionstart(session: pytest.Session) -> None:
    shutil.rmtree(WORK_DIR, ignore_errors=True)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    shutil.rmtree(WORK_DIR, ignore_errors=True)


def run_gate(script_rel: str, root: Path, *extra: str, timeout: float = 60.0) -> subprocess.CompletedProcess:
    """跑**真实**检查器脚本，`code_root` 指向夹具副本。

    `extra` 追加到 `--no-report` 之后（如 `--timing ci` / `--fail-on warn`）。
    """
    script = SYSTEM_ROOT / script_rel
    if not script.exists():
        raise FileNotFoundError(f"检查器脚本不存在: {script}")
    cmd = [sys.executable, str(script), str(root), "--no-report", *extra]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def assert_rejected(proc: subprocess.CompletedProcess, *, rule_hint: str = "") -> None:
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
