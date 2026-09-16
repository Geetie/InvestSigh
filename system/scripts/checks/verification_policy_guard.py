#!/usr/bin/env python3
"""`verification_policy_guard.py` —— **验证规范强制守卫**（`CONVENTIONS.md §一 V-01~V-06`）。

```
python system/scripts/checks/verification_policy_guard.py [code_root] [--no-report]
```

**为什么需要它**：本项目铁律是「**声明与实现必须有机器绑定**」——
只写在 `CONVENTIONS.md` 里、没有检查器强制的规范等于不存在
（实测教训 `D-9`：手工台账能被**一行数据编辑**绕过）。
本守卫把「禁止全量验证 / 每批必须带超时 / 超时绝不算通过 / 必须沙箱外跑 /
新增测试必须入批」落成可执行断言。

| # | 断言 | 依据 |
|---|---|---|
| A | `verify.py` **不带 `--batch`** 时必须返回 **2**（拒绝隐式全量验证） | V-01 |
| B | **不存在**以裸 `tests` 为目标的"全量批次" | V-01 |
| C | 每批 `0 < timeout <= 300s`；`BATCHES` 与 `ORDER` 键集合一致 | V-02 |
| D | 超时码 **`124` 必然判不合格**（不存在把它当放行的路径） | V-03 |
| E | `run_pytest.sh` 与 `verify.py` **都**把 broker hook 两个环境变量置 `0` | V-04 |
| F | `tests/` 下**每个测试文件**都必须被某个批次覆盖 | V-06 |

★ 退出码：`0` 放行 / `1` 命中违例 / `2` 输入异常（复用 `_common.run_checker`）。
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import (  # noqa: E402
    CheckReport,
    Violation,
    run_checker,
)

VERIFY_RELPATH = "scripts/ops/verify.py"
RUN_PYTEST_RELPATH = "scripts/ops/run_pytest.sh"
BROKER_ENV_VARS = ("CODEBUDDY_SAFE_DELETE_SANDBOX", "CODEBUDDY_BROKERED_FS_HOOK_ENABLED")
MAX_TIMEOUT_S = 300.0
TIMEOUT_EXIT_CODE = 124


def _load_verify(root: Path) -> Any:
    """按**文件路径**加载被检 `code_root` 的 `verify.py`。

    ★ 用 `spec_from_file_location` 而非 `import scripts.ops.verify`：
      ① `verify.py` 只依赖 stdlib，按路径加载**零全局副作用**（不改 `sys.path`）；
      ② 必须加载**被检 root 的那一份**，否则对夹具做注入测试时永远看着真仓库而"通过"
         （`D-23` 的同类教训：加载器必须看清自己加载的是谁）。
    """
    path = root / VERIFY_RELPATH
    if not path.exists():
        raise FileNotFoundError(f"缺少验证器: {path}")
    name = "_verify_under_audit"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载 {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def _pytest_targets(module: Any) -> list[str]:
    """从各批次的 argv 里抽出 pytest 目标（`-m pytest <targets...> -q ...`）。"""
    targets: list[str] = []
    for batch in module.BATCHES.values():
        argv = list(batch.argv)
        if "pytest" not in argv:
            continue
        idx = argv.index("pytest")
        for item in argv[idx + 1 :]:
            if item.startswith("-"):
                break
            targets.append(item)
    return targets


def _test_files(root: Path) -> list[str]:
    """`tests/` 下所有测试文件（相对 root 的 posix 路径；跳过点目录如 `.work`）。"""
    tests_dir = root / "tests"
    if not tests_dir.exists():
        raise FileNotFoundError(f"缺少 tests/ 目录: {tests_dir}")
    out: list[str] = []
    for path in sorted(tests_dir.rglob("test_*.py")):
        rel = path.relative_to(root)
        if any(part.startswith(".") or part == "__pycache__" for part in rel.parts):
            continue
        out.append(rel.as_posix())
    return out


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="verification_policy_guard")
    module = _load_verify(root)

    batches = dict(getattr(module, "BATCHES", {}))
    order = tuple(getattr(module, "ORDER", ()))
    report.scanned["batches"] = len(batches)

    # A. 拒绝隐式全量验证
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        no_batch_code = module.main([])
    report.scanned["no_batch_exit_code"] = int(no_batch_code)
    if int(no_batch_code) != 2:
        report.violations.append(
            Violation(
                "V-01",
                f"`verify.py` 不带 --batch 应返回 2（拒绝隐式全量验证），实得 {no_batch_code}",
                VERIFY_RELPATH,
            )
        )

    # B. 不存在"全量批次"（以裸 `tests` 为目标）
    targets = _pytest_targets(module)
    report.scanned["pytest_targets"] = len(targets)
    if "tests" in targets:
        report.violations.append(
            Violation(
                "V-01",
                "存在以裸 `tests` 为目标的**全量批次** —— 禁止一条命令全量验证",
                VERIFY_RELPATH,
            )
        )
    for target in targets:
        if not target.startswith("tests/"):
            report.violations.append(
                Violation("V-01", f"批次目标不在 tests/ 下（或是全量目标）: {target!r}", VERIFY_RELPATH)
            )

    # C. 每批必须带"适合"的超时；BATCHES 与 ORDER 必须一致
    if set(batches) != set(order):
        report.violations.append(
            Violation(
                "V-02",
                f"BATCHES 与 ORDER 键集合不一致：缺 {sorted(set(batches) - set(order))}，"
                f"多 {sorted(set(order) - set(batches))}",
                VERIFY_RELPATH,
            )
        )
    for name, batch in sorted(batches.items()):
        timeout = float(getattr(batch, "timeout", 0.0))
        if timeout <= 0 or timeout > MAX_TIMEOUT_S:
            report.violations.append(
                Violation(
                    "V-02",
                    f"批次 {name!r} 的 timeout={timeout}（要求 0 < t <= {MAX_TIMEOUT_S:.0f}s）"
                    "—— 超时值就是故障探测器，过宽会让卡死退化成「跑得慢」",
                    VERIFY_RELPATH,
                )
            )
    report.scanned["max_timeout_s"] = int(max((b.timeout for b in batches.values()), default=0))

    # D. 超时绝不算通过
    for name, batch in sorted(batches.items()):
        ok, why = batch.verdict(TIMEOUT_EXIT_CODE, "")
        if ok:
            report.violations.append(
                Violation(
                    "V-03",
                    f"批次 {name!r} 把超时码 {TIMEOUT_EXIT_CODE} 判成了通过（{why}）",
                    VERIFY_RELPATH,
                )
            )
        elif "超时" not in why:
            report.violations.append(
                Violation(
                    "V-03",
                    f"批次 {name!r} 的超时判定未说明「超时」（why={why!r}）——"
                    "超时必须被显式识别为该批有问题",
                    VERIFY_RELPATH,
                )
            )
    report.scanned["timeout_verdicts_checked"] = len(batches)

    # E. 必须沙箱外跑（broker hook 关闭）
    missing_env: list[str] = []
    for relpath in (VERIFY_RELPATH, RUN_PYTEST_RELPATH):
        path = root / relpath
        if not path.exists():
            report.violations.append(Violation("V-04", f"缺少文件: {relpath}", relpath))
            continue
        text = path.read_text(encoding="utf-8")
        for var in BROKER_ENV_VARS:
            # 两种写法都接受：Python 的 `"VAR": "0"` 与 shell 的 `VAR=0`
            assigned_zero = (
                f'"{var}": "0"' in text          # Python dict 字面量
                or f'{var}="0"' in text          # shell 带引号
                or f"{var}=0" in text            # shell 裸值
            )
            if var not in text or not assigned_zero:
                missing_env.append(f"{relpath}:{var}")
    if missing_env:
        report.violations.append(
            Violation(
                "V-04",
                "以下位置未把 broker hook 环境变量置 0（会导致夹具 copytree 卡死）: "
                + ", ".join(missing_env),
                RUN_PYTEST_RELPATH,
            )
        )
    report.scanned["broker_env_vars_required"] = len(BROKER_ENV_VARS) * 2

    # F. 新增测试必须入批（防「测试永远不被跑」）
    files = _test_files(root)
    report.scanned["test_files"] = len(files)
    uncovered: list[str] = []
    for rel in files:
        covered = any(rel == t or rel.startswith(t.rstrip("/") + "/") for t in targets)
        if not covered:
            uncovered.append(rel)
    if uncovered:
        report.violations.append(
            Violation(
                "V-06",
                f"以下测试文件**不被任何批次覆盖**（写了却永远不被验证）: {uncovered}"
                " → 请在 `verify.py::BATCHES` 增加/扩展批次",
                VERIFY_RELPATH,
            )
        )
    report.scanned["test_files_uncovered"] = len(uncovered)

    report.notes.append(
        f"批次超时上限 {MAX_TIMEOUT_S:.0f}s；超时码 {TIMEOUT_EXIT_CODE} 一律判不合格（V-03）"
    )
    return report


if __name__ == "__main__":
    sys.exit(run_checker("verification_policy_guard.py", check))
