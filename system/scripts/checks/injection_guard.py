#!/usr/bin/env python3
"""`injection_guard.py` —— 注入防护**效果断言守卫**（`Ch9 §N9.2-01` 判据的不变式形式）。

```
python system/scripts/checks/injection_guard.py [code_root]
```

★ 判据取**效果**不取词面（`Ch9 §N9.2-01` / `施工图 §八 N-2`）：本守卫**不设关键词黑名单**，
  只断言"数据路径不具备工具能力 / 不写建议 / 规则写收口点存在且被真调用"这些**结构不变式**。

四条机械断言（命中即 FATAL → exit 1）：

| # | 断言 | 依据 |
|---|---|---|
| A | 规则内核未被改：**复用** `checks/rules_lock_guard.check(root)`，violations 原样并入（**同一 hash 出口，不新写第二套**） | 措施②/纪律 9/10 |
| B | 数据路径无工具能力：对 `scripts/guard/**` **单遍 AST 扫描**，出现 `TOOL_PRIMITIVES` 引用 → FATAL | 措施③ |
| C | 数据路径无写建议：对 `scripts/guard/**` 单遍 AST，出现 `append_records(... "recommendations" ...)` 或写 `facts/recommendations.jsonl` → FATAL | 措施①/判据 |
| D | 规则写收口点存在且真被调用：`rulewrite.py` 的 `write_rule` **函数体内**含对 `refuse_write` 的调用 → 否则 FATAL | 措施②/R-01 |
| E | 工具收口点有生产调用方（`R-07`）：`executor.py` 的**某函数体内**调用 `write_rule`、**另一处函数体内**调用 `request_tool` → 否则 FATAL | `§一 底线 2` |

★ `D`/`E` 的断言**AST 绑定到对应函数体**（只在该 `FunctionDef` 内查找），
  **禁止**全文件字符串匹配（规避 `D-9` 手工台账被一行数据绕过）。

★ 单遍 AST（规避 `D-19` O(n²)）；**不在模块级导入 pydantic**（规避 `D-21`）；
  不修改 `sys.path` / `sys.modules` / 不装审计钩子（规避 `D-23`，仅沿用既有检查器 CLI 的幂等 path 前置）。

退出码：`0` 放行 / `1` 命中违例 / `2` 输入异常（复用 `_common.run_checker` 统一约定）。

空样本显式记 note（**不得**判 PASS=已验证）：
  - `scripts/guard/` 不存在 / `executor.py` / `rulewrite.py` 缺失 → **exit 2**（被检对象缺失＝输入异常）。
  - `data_path_modules == 0` → note `NO_GUARD_MODULES`，且 exit 2。
  - `raw/` 无外部文本 → note `NO_RAW_EXTERNAL_TEXT`（不变式真空成立，**须标注**）。
  - `registry/rules.lock.json` 缺失 → exit 2（由 `rules_lock_guard` 抛 `FileNotFoundError` 折叠）。
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
from scripts.checks.rules_lock_guard import check as rules_lock_check  # noqa: E402
from scripts.checks.rules_lock_guard import RULE_SUFFIXES  # noqa: E402

GUARD_SUBDIR = "scripts/guard"
DATA_PATH_GLOBS = (f"{GUARD_SUBDIR}/**",)
RULEWRITE_RELPATH = f"{GUARD_SUBDIR}/rulewrite.py"
EXECUTOR_RELPATH = f"{GUARD_SUBDIR}/executor.py"
RECOMMENDATION_STEM = "recommendations"

TOOL_PRIMITIVES = frozenset(
    {
        "subprocess",
        "os.system",
        "os.popen",
        "os.exec",
        "os.spawn",
        "pty.spawn",
        "eval",
        "exec",
        "compile",
        "__import__",
        "importlib.import_module",
    }
)

# 收口点名称（R-07：必须各有生产调用方，AST 绑定到函数体）
CHOKEPOINT_WRITE_RULE = "write_rule"
CHOKEPOINT_REQUEST_TOOL = "request_tool"


def _dotted(node: ast.AST) -> str:
    """把 `Name` / `Attribute` 还原为点分名（如 `os.system`）；不可还原 → `""`。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _is_tool_primitive(dotted: str) -> bool:
    return any(dotted == prim or dotted.startswith(prim + ".") for prim in TOOL_PRIMITIVES)


class _GuardVisitor(ast.NodeVisitor):
    """对单个文件做**单遍**遍历，收集：工具原语引用 / 写建议。"""

    def __init__(self) -> None:
        self.tool_hits: list[tuple[int, str]] = []          # (lineno, 点分名)
        self.recommendation_writes: list[tuple[int, str]] = []

    # ── 工具原语引用（Name / Attribute）──
    def visit_Name(self, node: ast.Name) -> None:
        if _is_tool_primitive(node.id):
            self.tool_hits.append((node.lineno, node.id))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        dotted = _dotted(node)
        if _is_tool_primitive(dotted):
            self.tool_hits.append((node.lineno, dotted))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if _is_tool_primitive(alias.name):
                self.tool_hits.append((node.lineno, alias.name))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            dotted = f"{module}.{alias.name}" if module else alias.name
            if _is_tool_primitive(dotted):
                self.tool_hits.append((node.lineno, dotted))
        self.generic_visit(node)

    # ── 写建议 ──
    def visit_Call(self, node: ast.Call) -> None:
        dotted = _dotted(node.func)
        callee = dotted.split(".")[-1] if dotted else ""
        # C：append_records(..., "recommendations", ...)
        if callee == "append_records":
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                if isinstance(arg, ast.Constant) and arg.value == RECOMMENDATION_STEM:
                    self.recommendation_writes.append(
                        (node.lineno, "append_records:recommendations")
                    )
        # C：把 recommendations.jsonl 作为路径常量传入写入调用
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if f"{RECOMMENDATION_STEM}.jsonl" in arg.value:
                    self.recommendation_writes.append((node.lineno, "path:recommendations.jsonl"))
        self.generic_visit(node)


def _analyze(path: Path) -> _GuardVisitor:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    visitor = _GuardVisitor()
    visitor.visit(tree)          # 单遍遍历
    return visitor


def _find_func(tree: ast.AST, func_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return node
    return None


def _body_calls(func: ast.AST) -> set[str]:
    """只在该 `FunctionDef` **体内**查找被调用名（AST 绑定到函数体，规避 D-9）。"""
    calls: set[str] = set()
    body = getattr(func, "body", [])
    for stmt in body:
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Call):
                calls.add(_dotted(sub.func))
    return calls


def _raw_has_external_text(root: Path) -> bool:
    raw_dir = root / "raw"
    if not raw_dir.exists():
        return False
    return any(p.is_file() and p.name != ".gitkeep" for p in raw_dir.rglob("*"))


def check(root: Path) -> CheckReport:
    """断言 `Ch9 §N9.2-01` 判据的不变式形式（不依赖关键词黑名单）。"""
    report = CheckReport(checker="injection_guard")

    # ── A. 规则内核未被改：复用同一 hash 出口（不新写第二套）──
    lock_report = rules_lock_check(root)
    report.violations.extend(lock_report.violations)
    report.scanned["rules_files"] = lock_report.scanned.get("registered_files", 0)
    report.scanned["rules_files_on_disk"] = lock_report.scanned.get("files_on_disk", 0)

    # ── 被检对象缺失 → 输入异常（exit 2，非 PASS）──
    guard_dir = root / GUARD_SUBDIR
    if not guard_dir.exists():
        raise FileNotFoundError(
            f"被检对象缺失：{GUARD_SUBDIR}/ 不存在（数据路径无从扫描 → 输入异常，非通过）"
        )
    modules = [p for p in walk_files(root, GUARD_SUBDIR, (".py",))]
    if not modules:
        raise ValueError(
            "NO_GUARD_MODULES：scripts/guard/ 下无 .py 模块 —— 被检对象为空，"
            "不得判 PASS=已验证（退出码 2）"
        )

    rulewrite_path = root / RULEWRITE_RELPATH
    if not rulewrite_path.exists():
        raise FileNotFoundError(f"被检对象缺失：{RULEWRITE_RELPATH} 不存在（规则写收口点无从校验）")
    executor_path = root / EXECUTOR_RELPATH
    if not executor_path.exists():
        raise FileNotFoundError(f"被检对象缺失：{EXECUTOR_RELPATH} 不存在（生产入口无从校验）")

    report.scanned["data_path_modules"] = len(modules)

    # ── B / C. 数据路径单遍 AST：无工具能力、无写建议 ──
    tool_hits = 0
    rec_writes = 0
    for path in modules:
        visitor = _analyze(path)
        relpath = rel(path, root)
        for lineno, name in visitor.tool_hits:
            tool_hits += 1
            report.violations.append(
                Violation(
                    "措施3·工具白名单",
                    f"数据路径出现工具原语 {name!r}（外部文本不得触发工具）",
                    relpath,
                    lineno,
                )
            )
        for lineno, what in visitor.recommendation_writes:
            rec_writes += 1
            report.violations.append(
                Violation(
                    "判据·不产生建议",
                    f"数据路径写 recommendations（{what}）—— 注入型文本不得产生建议",
                    relpath,
                    lineno,
                )
            )
    report.scanned["tool_primitive_hits"] = tool_hits
    report.scanned["recommendation_writes"] = rec_writes

    # ── D. 规则写收口点：write_rule 函数体内调用 refuse_write（AST 绑定函数体）──
    rw_tree = ast.parse(rulewrite_path.read_text(encoding="utf-8"), filename=str(rulewrite_path))
    rw_func = _find_func(rw_tree, CHOKEPOINT_WRITE_RULE)
    rw_calls = _body_calls(rw_func) if rw_func is not None else set()
    if rw_func is None or not any(
        name == "refuse_write" or name.endswith(".refuse_write") for name in rw_calls
    ):
        report.violations.append(
            Violation(
                "措施2·规则只读",
                f"{RULEWRITE_RELPATH}::write_rule 函数体内未调用 refuse_write —— 规则写收口点失效/孤儿",
                RULEWRITE_RELPATH,
                rw_func.lineno if rw_func is not None else 0,
            )
        )

    # ── E. 收口点有生产调用方（R-07，AST 绑定函数体）──
    ex_tree = ast.parse(executor_path.read_text(encoding="utf-8"), filename=str(executor_path))
    func_wiring: dict[str, tuple[int, set[str]]] = {}
    for node in ast.walk(ex_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_wiring[node.name] = (node.lineno, _body_calls(node))
    calls_write_rule = any(
        any(c == CHOKEPOINT_WRITE_RULE or c.endswith(".write_rule") for c in calls)
        for _, calls in func_wiring.values()
    )
    calls_request_tool = any(
        any(c == CHOKEPOINT_REQUEST_TOOL or c.endswith(".request_tool") for c in calls)
        for _, calls in func_wiring.values()
    )
    if not calls_write_rule:
        report.violations.append(
            Violation(
                "R-07·收口点接线",
                f"{EXECUTOR_RELPATH} 无函数体调用 write_rule —— 规则写收口点无生产调用方（变相孤儿）",
                EXECUTOR_RELPATH,
            )
        )
    if not calls_request_tool:
        report.violations.append(
            Violation(
                "R-07·收口点接线",
                f"{EXECUTOR_RELPATH} 无函数体调用 request_tool —— 工具收口点无生产调用方（变相孤儿）",
                EXECUTOR_RELPATH,
            )
        )
    report.scanned["chokepoints_wired"] = int(calls_write_rule) + int(calls_request_tool)

    # ── 空样本显式记 note（不变式真空成立，须标注，不得判 PASS=已验证）──
    if not _raw_has_external_text(root):
        report.notes.append(
            "NO_RAW_EXTERNAL_TEXT：raw/ 无外部文本（数据路径不变式**真空成立**，须标注）"
        )
    report.notes.append(
        f"data_path_globs={'|'.join(DATA_PATH_GLOBS)} rules_suffixes={RULE_SUFFIXES}"
    )
    return report


if __name__ == "__main__":
    sys.exit(run_checker("injection_guard.py", check))
