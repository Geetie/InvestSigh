#!/usr/bin/env python3
"""`module_denylist.py` —— **模块 denylist 守卫**（`Ch3 §D.3` / N3.3-02 / N3.3-04 / C3-5）。

```
python system/scripts/checks/module_denylist.py [code_root]
```

交付**止于"研究 + 股票建议"**：不得出现组合权重优化 / 账户管理 / 交易执行 / 跨资产配置类模块。
环境项（利率 / 融资 / AI 需求 / 能源 / 政策）**只作输入**注入公司/基准研究，
**不得独立成择时或跨资产配置模块**（`Ch3 §F.1`）。

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

# `Ch3 §D.3` DENIED_MODULES（逐字）
DENIED_MODULES = {
    "gold",
    "btc",
    "crypto",
    "cross_asset_allocation",
    "portfolio_weight_optimizer",
    "account_management",
    "trade_execution",
}

# 仅"模块/文件/顶层对象名"层面判定，避免与合法业务词碰撞
def check_modules(names: list[str], relpath: str) -> list[Violation]:
    return [
        Violation("N3.3-02/04", f"禁止新增模块: {m}", relpath)
        for m in names
        if m in DENIED_MODULES
    ]


def _module_names(path: Path) -> list[str]:
    """取模块名 / 顶层类名 / 顶层函数名 / 导入的顶层包名。"""
    names: list[str] = [path.stem]
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return names
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
        elif isinstance(node, ast.Import):
            names.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module.split(".")[0])
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    names.append(tgt.id)
    return names


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="module_denylist")
    files = walk_files(root, "scripts", (".py",))
    report.scanned["py_files"] = len(files)
    report.scanned["denied_modules"] = len(DENIED_MODULES)
    for path in files:
        report.violations.extend(check_modules(_module_names(path), rel(path, root)))
    return report


if __name__ == "__main__":
    sys.exit(run_checker("module_denylist.py", check))
