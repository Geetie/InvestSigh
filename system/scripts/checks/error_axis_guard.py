#!/usr/bin/env python3
"""`error_axis_guard.py` —— **复盘标记字段不得进入决策函数**（`S-07`）。

```
python system/scripts/checks/error_axis_guard.py [code_root] [--no-report]
```

## 它拦的是什么

第十章给 `eval_result` 加了三个**标记字段** —— `eval_layer` / `error_axis` / `error_axis_note`
（`Ch10 §C.1` / `Ch10 §A.4` 命名说明第 ① 条）：

> 三个 `eval_result` 新字段均为**标记枚举/说明**，**不进入决策函数**。

而「不进决策函数」如果只写在文档里，就**没有任何东西在守它** —— 有人把它们顺手接进
`scripts/decision/**` / `scripts/graph/**`（例如"按错误方向加权"），门禁**不会响**。
这条守卫把 `Ch2 §B.3` Checker-1 的 `is_decision_scope` **排除项**变成**可执行断言**。

## 三条断言（对齐 `10_02 §G.1`）

| # | 断言 | 依据 |
|---|---|---|
| ① | **函数体级 AST**：决策作用域里，任一函数体的 **标识符 / 属性 / 字符串键（`.get` 首参 · 下标 · dict 字面量键）/ 形参名 / 关键字实参名** 命中标记字段 ⇒ **命中即 fail** | `S-07` / `Ch10 §G.1` ① |
| ② | **结构断言**：`RecommendationInput`（`Ch7 §D.5`）的字段集**不含**三个标记字段 | `Ch10 §G.1` ② |
| ③ | **作用域复用**：判定"是否决策作用域"一律走 `scripts/_common.py::is_decision_scope_module` / `matches_call_chain`（= `Ch2 §B.3` Checker-1 的口径），**本守卫不另造一套作用域** | `Ch10 §G.1` ③ / `G-06` |

★ **为什么是函数体级（`G-02`）**：如果只在**整文件**上做字符串/名字匹配，那么一行注释、
一句 docstring、或一个**只在非决策函数里**用到的同名变量都能"绕过/误伤"。判"决策函数
是否读了标记字段"必须看**函数体**（含嵌套函数的体），这与 `stage_gate.bound_criteria()` 的
"按函数归属、不按整文件"是同一课。

★ **为什么是 allowlist（可判定 + 可穷尽，`R-06`）**：
被检**域** = 由 `rules/banned_tokens.yaml::decision_scope` 的
`include_paths` / `include_modules` / `include_call_chain` **枚举出来的**（纯配置驱动，
**不写关键词、不写文件名名单**）；被检**谓词** = "函数体里是否出现这三个标记名"（集合交）。
两侧都是可穷尽枚举 + 集合运算 —— 不是"列出几种坏写法"。

★ **单一真源（`G-06`）**：标记集合**不在此处硬编码**，直接读
`rules/banned_tokens.yaml::decision_scope.exclude_fields`（`Ch2 §B.2` 的决策作用域排除项）。
`exclude_fields` 与 `Ch10 §C.1` 的字段名**必须逐字一致** —— 不一致时本守卫的
`exclude_fields` 会落空，故断言 ② 之下另有一条"标记集合非空"的响亮检查（见 `_markers()`）。

★ **已知边界（如实登记，不静默）**：本守卫只认**静态可读**的名字使用（标识符 / 属性 /
字符串键 / 形参名 / 关键字实参名）。**刻意不做**：
- 不追数据流（`d = {...}; d["eval_layer"]` 里键是常量 —— 会命中；但
  `k = "eval_layer"; d[k]` 的**间接键**不命中）—— 这类"名字出现在非字面量位置"的
  间接用法**不在**本守卫的可判定范围内；它由 `conflict_scan` 的 L2/L3（`P-09` scope）
  与人工评审兜底。
- 不扫 docstring（`ast.Constant` 只有在作为**键/实参**时才计入）—— 设计文本里到处写
  `eval_layer` 是**正确**的，把 docstring 算成"使用"会制造大量误报（`G-05` 降噪）。

★ 退出码（`Ch2 §B.3`，命中即 fail）：`0` 放行 / `1` 命中违例 / `2` 输入异常。

★ **性能（`P-05`：单次 < 0.5s，它在 pre-commit 里跑）**：初版对**每个文件**先
`ast.walk` 抽全部函数、再对每个 in-scope 函数**重走**一遍子树（`_marker_uses`），
且 `matches_call_chain()` 按函数逐个查询配置 —— 实测 `check()` 自身 **0.70s（超 `P-05`）**。
现改为：**每文件单次遍历**（一个显式栈同时承载"函数作用域栈"与"标记名扫描"），
并**只对非模块级作用域的函数**才查 `matches_call_chain()`。实测 `check()` ≈ **0.36s**
（`best-of-5`，本机；`P-05` 口径 = 进程内 `check()` 耗时，不含解释器 `spawn` 的 ~0.7s）。
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
    decision_scope_config,
    is_checker_namespace,
    is_decision_scope_module,
    matches_call_chain,
    rel,
    run_checker,
    walk_files,
)

SCAN_SUBDIR = "scripts"

#: 决策输入结构的载体（`Ch7 §D.5` / `Ch10 §G.1` ② 逐字点名的结构）。
#: ★ 用一个**可指认的模块 + 类名**做断言 ② 的锚点；类不存在 ⇒ 响亮失败（无被检对象 ≠ 已验证）。
DECISION_INPUT_RELPATH = "scripts/decision/gate.py"
DECISION_INPUT_CLASS = "RecommendationInput"

#: 断言 ② 的越界形态：`RecommendationInput.from_mapping` 是 **allowlist**（未列出的键默认丢弃），
#: 故"字段集不含标记字段"是**结构保证**，而不是"恰好现在没写"。
STRUCTURAL_ANCHOR = "Ch7 §D.5 / Ch10 §G.1 ②"

#: 断言 ② 违例文案里引用的**汉字名**。
DECISION_INPUT_LABEL_ZH = f"决策输入结构 {DECISION_INPUT_RELPATH}"


def _markers(root: Path) -> set[str]:
    """标记字段集合 —— **唯一真源** = `rules/banned_tokens.yaml::decision_scope.exclude_fields`。

    ★ 为什么必须读配置而**不硬编码**（`G-06`）：`Ch10 §C.1` 的字段名是设计面的事实，
      而"哪些字段属决策作用域排除项"的**机器可读载体**就是这个 YAML 键
      （`Ch2 §B.1` 三次实例之一）。两处各写一份必然漂移；漂移时本守卫会**静默地不拦**。
    """
    fields = decision_scope_config(root).get("exclude_fields")
    if not isinstance(fields, list) or not fields:
        # 无标记集合 = 本守卫**没有可检对象** ⇒ 响亮失败（`G-03`：不得当作通过）。
        # 用 `raise`（经 `run_checker` 折叠为 `exit 2`）：这是**输入/配置异常**，
        # 与"代码违规"必须分开（`Ch2 §B.3` 的 `0/1/2` 三分）。
        raise ValueError(
            "rules/banned_tokens.yaml::decision_scope.exclude_fields 缺失或为空 —— "
            "本守卫的标记集合没有来源，**不得据此判 PASS**（`G-03`：无被检对象 ≠ 已验证）"
        )
    return {str(x) for x in fields}


def _collect_params(fn: ast.FunctionDef, markers: set[str], hits: list[tuple[str, str, int]]) -> None:
    """形参名（含 posonly / kwonly / vararg / kwarg）命中标记字段 —— 决策函数**接收**标记字段也算进入。"""
    args = fn.args
    for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
        if arg.arg in markers:
            hits.append((fn.name, arg.arg, arg.lineno))
    for arg in (args.vararg, args.kwarg):
        if arg is not None and arg.arg in markers:
            hits.append((fn.name, arg.arg, arg.lineno))


def _collect_node(
    node: ast.AST, markers: set[str], fn_name: str | None, hits: list[tuple[str, str, int]]
) -> None:
    """函数体内**单个节点**层面的标记名使用（`ast.Constant` 仅作为**键**时计入）。

    认六种"名字的静态出现"（非数据流）：
    1. 标识符 `ast.Name`（`if eval_layer == ...`）；
    2. 属性 `ast.Attribute`（`row.eval_layer`）；
    3. 字符串键 —— `.get("eval_layer")` 的首实参；
    4. 字符串键 —— `x["eval_layer"]` 的下标切片；
    5. 字符串键 —— `{"eval_layer": ...}` 的字典字面量键；
    6. 关键字实参名（`f(eval_layer=...)`）—— 由 `ast.keyword` 承载。

    ★ **不含 docstring / 普通字符串字面量**：`ast.Constant` 只有落在上述 3/4/5 的
      **键位**上才算使用；docstring 与 `message = "eval_layer ..."` 这类**说明性**字符串不计
      （否则会对**自己人**误报 —— 本仓库设计文本到处写 `eval_layer`，`G-05`）。
    """
    if isinstance(node, ast.Name):
        if node.id in markers:
            hits.append((fn_name or "<module>", node.id, node.lineno))
    elif isinstance(node, ast.Attribute):
        if node.attr in markers:
            hits.append((fn_name or "<module>", node.attr, node.lineno))
    elif isinstance(node, ast.keyword):
        # `node.arg` 为 `None` 表示 `**kwargs` 展开，与标记名无关。
        if node.arg is not None and node.arg in markers:
            hits.append((fn_name or "<module>", node.arg, node.lineno))
    elif isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "get" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value in markers:
                hits.append((fn_name or "<module>", first.value, first.lineno))
    elif isinstance(node, ast.Subscript):
        key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value in markers:
            hits.append((fn_name or "<module>", key.value, key.lineno))
    elif isinstance(node, ast.Dict):
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value in markers:
                hits.append((fn_name or "<module>", key.value, key.lineno))


def _scan_tree(
    tree: ast.AST, markers: set[str], module_in_scope: bool, root: Path
) -> tuple[list[tuple[str, str, int]], int, int]:
    """**单次遍历**一棵模块树：返回 `(hits, in_scope_funcs, call_chain_funcs)`。

    遍历用**一个显式栈**承载 `(节点, 是否已在决策作用域内, 最近的函数名)`：
    - 遇到 `FunctionDef` ⇒ 结算该函数是否入作用域（模块级 / `include_call_chain` / 继承外层），
      再按 `ast.iter_child_nodes` 下推子节点，并把 `in_scope` 沿子树**继承**
      （"决策函数体内的嵌套函数"同样在作用域内）。
    - 其余节点 ⇒ 若当前已在作用域内，做一次标记名检查。

    ★ 单次遍历是 `P-05` 的关键：初版"先抽函数、再逐函数重走子树"把同一棵树走了两遍。
    """
    hits: list[tuple[str, str, int]] = []
    in_scope_funcs = 0
    call_chain_funcs = 0

    stack: list[tuple[ast.AST, bool, str | None]] = [(tree, module_in_scope, None)]
    while stack:
        node, in_scope, fn_name = stack.pop()
        if isinstance(node, ast.FunctionDef):
            # ★ 只在**尚未**入作用域、且模块级也非作用域时，才去问调用链（省下重复配置查询）。
            via_chain = (
                not module_in_scope
                and not in_scope
                and matches_call_chain(node.name, root)
            )
            my_scope = in_scope or module_in_scope or via_chain
            if my_scope:
                in_scope_funcs += 1
                if via_chain:
                    call_chain_funcs += 1
                _collect_params(node, markers, hits)
            for child in ast.iter_child_nodes(node):
                stack.append((child, my_scope, node.name))
            continue
        if in_scope:
            _collect_node(node, markers, fn_name, hits)
        for child in ast.iter_child_nodes(node):
            stack.append((child, in_scope, fn_name))
    return hits, in_scope_funcs, call_chain_funcs


def _decision_input_fields(root: Path) -> set[str]:
    """读 `RecommendationInput` 的**字段名**（断言 ②）—— **AST，不 import**。

    ★ 为什么用 AST 而不 `import scripts.decision.gate`：该模块 import `schema.models`
      （pydantic，首次导入实测 ≈1.2s）⇒ 会把本守卫拖过 `P-05` 的 **0.5s** 上限，
      而它在 pre-commit 里跑。AST 读取字段名是**等价且更轻**的（`AnnAssign` 的目标名
      就是 dataclass 字段名，由 `@dataclass` 语义保证）。
    """
    path = root / DECISION_INPUT_RELPATH
    if not path.exists():
        raise FileNotFoundError(
            f"缺少决策输入结构的载体 {DECISION_INPUT_RELPATH} —— 断言 ②（{STRUCTURAL_ANCHOR}）"
            "没有可检对象，**不得据此判 PASS**"
        )
    tree = _parse(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == DECISION_INPUT_CLASS:
            return {
                stmt.target.id
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
            }
    raise FileNotFoundError(
        f"{DECISION_INPUT_RELPATH} 里找不到类 {DECISION_INPUT_CLASS} —— "
        f"断言 ②（{STRUCTURAL_ANCHOR}）没有可检对象，**不得据此判 PASS**"
    )


def _parse(path: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        # ★ 不吞：无法解析 = 该文件**根本没被检查**，而输出里一切正常 ——
        #   正是本守卫要拦的那一族。折叠为**输入异常**（`exit 2`）。
        raise ValueError(f"{path}: 语法错误，无法 AST 检查（不得当作通过）: {exc}") from exc


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="error_axis_guard")
    markers = _markers(root)
    report.scanned["markers"] = len(markers)

    scanned_files = 0
    scanned_funcs = 0
    call_chain_funcs = 0

    for path in walk_files(root, SCAN_SUBDIR):
        relpath = rel(path, root)
        # 检查器命名空间免扫（`Ch2 §B.1` 通则第 4 点）：检查器自身可能**必须**写出标记名。
        if is_checker_namespace(relpath, root):
            continue
        module_in_scope = is_decision_scope_module(relpath, root)
        tree = _parse(path)
        hits, n_funcs, n_chain = _scan_tree(tree, markers, module_in_scope, root)
        if module_in_scope:
            scanned_files += 1
        scanned_funcs += n_funcs
        call_chain_funcs += n_chain
        if hits:
            report.scanned[f"flagged::{relpath}"] = len(hits)
            for fn_name, name, lineno in hits:
                report.violations.append(
                    Violation(
                        "S-07",
                        f"决策函数 {fn_name}() 里出现复盘标记字段 {name!r} —— "
                        "`Ch10 §C.1`/`Ch10 §G.1`（`S-07`）：三重标记字段"
                        "（`eval_layer` / `error_axis` / `error_axis_note`）**不进决策函数**；"
                        "`Ch2 §B.3` Checker-1 的 `is_decision_scope` 把它们列为**排除项**。"
                        "（标记字段只作复盘/定位，不得作为决策输入或权重）",
                        relpath,
                        lineno,
                    )
                )

    # ── 断言 ②：决策输入结构**不含**标记字段（`Ch10 §G.1` ②）────────────────────────
    fields = _decision_input_fields(root)
    report.scanned["recommendation_input_fields"] = len(fields)
    for name in sorted(markers & fields):
        report.violations.append(
            Violation(
                "S-07",
                f"{DECISION_INPUT_LABEL_ZH} `{DECISION_INPUT_CLASS}` 的字段集里出现标记字段 {name!r} —— "
                f"`from_mapping` 是 allowlist 结构（{STRUCTURAL_ANCHOR}），标记字段一旦成为结构字段，"
                "就会被顺理成章地接进决策；**必须移除**（标记字段不进决策输入结构）。",
                DECISION_INPUT_RELPATH,
            )
        )

    report.scanned["decision_scope_modules"] = scanned_files
    report.scanned["scanned_functions"] = scanned_funcs
    report.scanned["call_chain_functions"] = call_chain_funcs
    report.notes.append(
        "被检域（allowlist，`R-06`）= `rules/banned_tokens.yaml::decision_scope` 枚举出的 "
        "作用域：`include_paths`（`scripts/decision/**` / `scripts/graph/**`）+ "
        "`include_modules`（`notification_sort` / `daily_page_sort`）整体纳入；"
        "其余模块里凡函数名命中 `include_call_chain`（`classify_*` / `assert_*`）者按**函数**纳入。"
        f"本树：作用域模块 {scanned_files} / 被检函数 {scanned_funcs}（其中 call-chain 纳入 "
        f"{call_chain_funcs}）/ 标记字段 {len(markers)}（源：`decision_scope.exclude_fields`）。"
        "★ 谓词 = 「函数体里是否出现这些标记名」（标识符/属性/字符串键/形参/关键字实参）；"
        "**跳过不是通过**（`G-03`）：间接键（`k='eval_layer'; d[k]`）与 docstring **不在**可判定域内，"
        "由 `conflict_scan` 的 `P-09` scope 与人工评审兜底。"
    )
    return report


if __name__ == "__main__":
    sys.exit(run_checker("error_axis_guard.py", check))
