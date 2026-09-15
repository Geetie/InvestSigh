#!/usr/bin/env python3
"""`assert_gate_input.py` —— **L4 决策门输入结构断言**（`Ch2 §B.2 P-06` / `§B.3` Checker-3）。

```
python system/scripts/checks/assert_gate_input.py [code_root]
```

P-06 禁止项：`moat_required` / `catalyst_required` / `official_confirmation_required` /
`profitability_required` 作**买入门**；Checker-3 的 forbidden 集合还含
`realization_required` / `moat` / `catalyst`。

**正向断言**（`Ch2 §B.3` Checker-3 / `00_待拍板项清单` A5 / C123-5）：
门输入**必须且只是**"收益相对基准"的结构判定，**不得含任何置信度数值阈值**。

★ 命中即 fail，禁 warn-only（纪律 2）。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Iterator

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import (  # noqa: E402
    CheckReport,
    Violation,
    load_banned_tokens,
    rel,
    run_checker,
    walk_files,
)

# Checker-3 的 forbidden 集合（`Ch2 §B.3`，逐字）
FORBIDDEN_GATE_INPUTS = (
    "moat_required",
    "catalyst_required",
    "official_confirmation_required",
    "profitability_required",
    "realization_required",
    "moat",
    "catalyst",
)

# 置信度 / 阈值类字段形态（`Ch2 §B.2 P-02` / A5）
CONFIDENCE_LIKE = ("confidence", "threshold", "min_", "minimum_", "score", "weight", "vote")


def _dataclass_fields(cls: ast.ClassDef) -> list[str]:
    """取 dataclass / pydantic 模型的字段名（AnnAssign 形式）。"""
    out: list[str] = []
    for node in cls.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.append(node.target.id)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id not in {"model_config"}:
                    out.append(tgt.id)
    return out


def _gate_input_classes(tree: ast.AST) -> Iterator[ast.ClassDef]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {ast.unparse(b) for b in node.bases}
        decos = {ast.unparse(d) for d in node.decorator_list}
        is_input = any("dataclass" in b or "BaseModel" in b for b in bases) or any(
            "dataclass" in d for d in decos
        )
        if is_input and (node.name.startswith(("Gate", "Decision")) or node.name.endswith(("GateInput",))):
            yield node


def _gate_functions(tree: ast.AST) -> Iterator[ast.AST]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            ("gate", "decide", "assert_buy", "pass_gate")
        ):
            yield node


def assert_gate_inputs_in_tree(path: Path, root: Path, relpath: str) -> tuple[list[Violation], bool]:
    """对一个文件做 P-06 断言，返回 `(violations, 是否找到可断言的门)`。

    ★ **"本文件里没有门"本身不是违规**（实测修正）：
      初版对每个文件都记一条 `未找到可断言的门对象/门函数`，于是
      `scripts/decision/` 下**任何辅助模块**（口径读取、枚举定义…）都会把 L4 打成红。
      这是典型的误报发生器 —— 结局是有人把 L4 关掉。
      "整个目录里一个门都没有"由调用方按 `require` 决定是 note 还是 violation
      （阶段① 无门 = 正常；阶段③ `--require-l4` 无门 = 硬门失败）。
    """
    violations: list[Violation] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    found = False
    for cls in _gate_input_classes(tree):
        found = True
        fields = _dataclass_fields(cls)
        hit = sorted(set(fields) & set(FORBIDDEN_GATE_INPUTS))
        if hit:
            violations.append(
                Violation(
                    "P-06",
                    f"{cls.name} 含禁止的门输入 {hit}（规则 4/5/7/12）",
                    relpath,
                    cls.lineno,
                )
            )
        conf = sorted({f for f in fields if any(t in f for t in CONFIDENCE_LIKE)})
        if conf:
            violations.append(
                Violation(
                    "P-02",
                    f"{cls.name} 含置信度/阈值类输入 {conf}（A5：门只做结构完备性校验）",
                    relpath,
                    cls.lineno,
                )
            )

    for fn in _gate_functions(tree):
        found = True
        args = [a.arg for a in getattr(fn.args, "args", [])] + [a.arg for a in fn.args.kwonlyargs]
        hit = sorted(set(args) & set(FORBIDDEN_GATE_INPUTS))
        if hit:
            violations.append(
                Violation("P-06", f"{fn.name}() 参数含禁止的门输入 {hit}", relpath, fn.lineno)
            )
        conf = sorted({a for a in args if any(t in a for t in CONFIDENCE_LIKE)})
        if conf:
            violations.append(
                Violation("P-02", f"{fn.name}() 参数含置信度类输入 {conf}", relpath, fn.lineno)
            )
    return violations, found


NO_GATE_NOTE = (
    "NO_GATE_DECLARED：scripts/decision/** 内暂无门对象 / 门函数"
    "（gate 于阶段③ 交付，`Ch7 §D.1`）；本检查器已就绪，本次**无被检对象**，"
    "不等同于‘已验证门输入结构合规’"
)


def check(root: Path, *, require: bool = False) -> CheckReport:
    report = CheckReport(checker="assert_gate_input")
    files = [p for p in walk_files(root, "scripts/decision", (".py",)) if p.name != "__init__.py"]
    report.scanned["gate_files"] = len(files)
    if not files:
        # 阶段① 尚未交付 gate（Ch7 §D.1 → 阶段③）。显式说明，不冒充通过。
        if require:
            report.violations.append(Violation("P-06", NO_GATE_NOTE + "；--require-gate 要求必须存在", "scripts/decision"))
        else:
            report.notes.append(NO_GATE_NOTE)
        return report

    any_gate = False
    for path in files:
        v, found = assert_gate_inputs_in_tree(path, root, rel(path, root))
        report.violations.extend(v)
        any_gate = any_gate or found

    report.scanned["gate_objects_declared"] = int(any_gate)
    if not any_gate:
        if require:
            report.violations.append(Violation("P-06", NO_GATE_NOTE + "；--require-gate 要求必须存在", "scripts/decision"))
        else:
            report.notes.append(NO_GATE_NOTE)
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="assert_gate_input.py")
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--require-gate", action="store_true", help="阶段③：门必须存在")
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.code_root) if args.code_root else _ROOT
    return run_checker(
        "assert_gate_input.py",
        lambda r: check(r, require=args.require_gate),
        [str(root)] + (["--no-report"] if args.no_report else []),
    )


if __name__ == "__main__":
    sys.exit(main())
