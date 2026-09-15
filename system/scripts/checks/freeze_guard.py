#!/usr/bin/env python3
"""`freeze_guard.py` —— **参数状态断言 + 红线一"不补门槛"扫描**（`Ch11 §E.1` / `§G`）。

```
python system/scripts/checks/freeze_guard.py [code_root]
```

守卫清单（`Ch11 §G`，逐条）：

| 编号 | 守卫 | 内容 |
|---|---|---|
| G11-01 | 参数状态断言 | 全 11 项拍板前 `freeze_status=tbd`；`frozen` 项须齐 `confirmed_by` / `confirmed_at` / `version` |
| G11-02 | 红线"不补门槛"扫描 | 参数名 / 值不含 `Ch2 §B.2` 禁词；**决策函数 AST 不读 `freeze_param`** |
| G11-05 | `blocking_targets` 锚点守卫 | 全部为**节号锚点**，**禁绝对行号** |

**不新立禁词**：G11-02 只**引用** `rules/banned_tokens.yaml`（`Ch11 §G`）。

★ 命中即 fail，禁 warn-only（纪律 2）。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import (  # noqa: E402
    CheckReport,
    Violation,
    rel,
    run_checker,
    walk_files,
)

# 决策作用域目录（`Ch11 §E.1`：AST 断言的对象）
DECISION_SCOPE_DIRS = ("scripts/decision", "scripts/graph")

# freeze_param 读取的标识符（`Ch11 §E.1` / `Ch2 §B.3` Checker-1 排除标记）
FREEZE_READ_MARKERS = ("get_param", "get_param_value", "freeze_param", "load_freeze", "ParamResolution")


def check_freeze_status(root: Path) -> list[Violation]:
    """G11-01：`tbd` 合法；`frozen` 必须原子携带 `confirmed_by` / `confirmed_at` / `version`。"""
    from config.freeze import load_freeze

    doc = load_freeze(root)
    v: list[Violation] = []
    for row in doc["freeze_params"]:
        pid = row.get("param_id", "<unknown>")
        status = row.get("freeze_status")
        if status == "tbd":
            continue
        if status != "frozen":
            v.append(Violation("G11-01", f"{pid}: freeze_status 非法取值 {status!r}", "rules/freeze.yaml"))
            continue
        missing = [k for k in ("confirmed_by", "confirmed_at", "version") if not row.get(k)]
        if missing:
            v.append(
                Violation(
                    "G11-01",
                    f"{pid}: freeze_status=frozen 但缺 {missing}（切换必须原子：一次提交齐三要素）",
                    "rules/freeze.yaml",
                )
            )
    return v


def check_no_new_gate(root: Path) -> list[Violation]:
    """G11-02 ①：参数名 / 值标识符不得命中禁词（复用 `Ch2 §B.2` 禁词表）。"""
    from config.freeze import NewGateError, assert_no_new_gate

    try:
        assert_no_new_gate(root)
    except NewGateError as exc:
        return [Violation("G11-02", str(exc), "rules/freeze.yaml")]
    return []


def check_anchor_only(root: Path) -> list[Violation]:
    """G11-05：`blocking_targets` 一律节号锚点。"""
    from config.freeze import AnchorFormatError, assert_anchor_only

    try:
        assert_anchor_only(root)
    except AnchorFormatError as exc:
        return [Violation("G11-05", str(exc), "rules/freeze.yaml")]
    return []


def check_no_freeze_param_in_decision_scope(root: Path) -> tuple[list[Violation], int]:
    """G11-02 ②：**决策函数 AST 不得出现任何 `freeze_param` 读入**（`Ch11 §E.1`）。

    返回 (violations, scanned_file_count)。**扫过的文件数必须上报**——
    「扫了 0 个文件」与「扫了 N 个文件且都没问题」不是同一件事（防 Phantom Subscription）。
    """
    v: list[Violation] = []
    scanned = 0
    for sub in DECISION_SCOPE_DIRS:
        for path in walk_files(root, sub, (".py",)):
            if path.name == "__init__.py":
                continue
            scanned += 1
            relpath = rel(path, root)
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:
                v.append(Violation("G11-02", f"语法错误: {exc}", relpath, exc.lineno or 0))
                continue
            for node in ast.walk(tree):
                name = None
                if isinstance(node, ast.Name):
                    name = node.id
                elif isinstance(node, ast.Attribute):
                    name = node.attr
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [a.name.split(".")[-1] for a in node.names]
                    if any(n in FREEZE_READ_MARKERS for n in names) or (
                        node.module or ""
                    ).split(".")[-1] in ("freeze", "config"):
                        v.append(
                            Violation(
                                "G11-02",
                                "决策作用域不得 import freeze / config 参数读口",
                                relpath,
                                node.lineno,
                            )
                        )
                    continue
                if name in FREEZE_READ_MARKERS:
                    v.append(
                        Violation(
                            "G11-02",
                            f"决策函数读入参数 {name!r}（参数只做基准/范围/口径/披露，不进决策函数）",
                            relpath,
                            getattr(node, "lineno", 0),
                        )
                    )
    return v, scanned


def check(root: Path) -> CheckReport:
    from config.freeze import load_freeze

    report = CheckReport(checker="freeze_guard")
    report.violations += check_freeze_status(root)
    report.violations += check_no_new_gate(root)
    report.violations += check_anchor_only(root)
    v4, scanned = check_no_freeze_param_in_decision_scope(root)
    report.violations += v4
    report.scanned["freeze_params"] = len(load_freeze(root)["freeze_params"])
    report.scanned["decision_scope_files_scanned"] = scanned
    if scanned == 0:
        report.notes.append(
            "DECISION_SCOPE_EMPTY：scripts/decision/** 与 scripts/graph/** 暂无 .py 模块"
            "（阶段②/③ 交付）；G11-02 的 AST 断言本次**无被检对象**，"
            "不等于‘已验证决策函数不读参数’"
        )
    return report


if __name__ == "__main__":
    sys.exit(run_checker("freeze_guard.py", check))
