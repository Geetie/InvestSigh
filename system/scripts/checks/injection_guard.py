#!/usr/bin/env python3
"""`injection_guard.py` —— 注入防护**能力白名单**守卫（`Ch9 §N9.2-01` 判据的不变式形式）。

```
python system/scripts/checks/injection_guard.py [code_root]
```

★ 判据取**效果**不取词面（`Ch9 §N9.2-01` / `施工图 §八 N-2`）：本守卫**不设关键词黑名单**，
  只断言"数据路径不具备工具能力 / 不写建议 / 规则写收口点存在且被真调用"这些**结构不变式**。

★ B / C 采用**能力白名单（allowlist）**（`CONVENTIONS.md::R-06`：首选 allowlist、未列即拒、可穷尽）：
  对 `scripts/guard/**` 做**单遍 AST 扫描**，只放行**显式声明**的能力，**未列入即 FATAL** ——
  白名单对未列形式默认拒绝，故是**封闭集合**判定（不是对已知攻击形式的枚举）：

| # | 白名单 | 判据（命中即 FATAL → exit 1） |
|---|---|---|
| B | `ALLOWED_IMPORTS` | 每个 `import` 的模块路径必须 ∈ 白名单；未列入（`os` / `subprocess` / `builtins` / `importlib` / …）→ FATAL。相对导入只允许 `level == 1`（停留在被扫的 `scripts/guard` 包内） |
| C | `ALLOWED_DUNDERS` | 每个 `__x__` **标识符**（`Name` / `Attribute.attr` / `def` / `class` / 形参名）必须 ∈ 白名单；未列入（`__builtins__` / `__dict__` / `__globals__` / `__class__` / `__import__` / …）→ FATAL。动态调用（`getattr` / `eval` / …）的 **dunder 字符串字面量参数**同样受此白名单约束 |

★ **别名感知**（`A-3`）：解析导入表，把 `from schema.store import append_records as ar` 这类**别名**
  解析回真实来源，使 `ar(root, "recommendations", …)` 同样命中"不产生建议"判据；stem 非字面量仍 fail-closed。

其余静态断言（命中即 FATAL）：

| # | 断言 | 依据 |
|---|---|---|
| A | 规则内核未被改：**复用** `checks/rules_lock_guard.check(root)`，violations 原样并入（**同一 hash 出口，不新写第二套**） | 措施②/纪律 9/10 |
| C' | 不产生建议：`append_records(..., stem)` 的 stem **必须是字符串字面量**（`Name` / `Call` / `JoinedStr` / 拼接等**不可静态判定**者 → **fail closed** FATAL）；stem 字面量 == `"recommendations"` 或路径常量含 `recommendations.jsonl` → FATAL | 措施①/判据 |
| D | 规则写收口点存在且真被调用：`rulewrite.py` 的 `write_rule` **函数体内**含对 `refuse_write` 的调用 → 否则 FATAL | 措施②/R-01 |
| E | 收口点有生产调用方（`R-07`）：`executor.py` 的**若干函数体内存在**对 `write_rule` 的调用，且**存在**对 `request_tool` 的调用 → 否则 FATAL（按函数体集合判定，不要求落在同一函数） | `§一 底线 2` |

★ **辅助 lint**（`R-06` ④：不可穷尽的 denylist 只能作 lint，**必须在措辞上剥离防护语义**）：
  `eval` / `exec` / `compile` 作为**裸 `Name`** 出现 → 附加绊线。该集合不可穷尽（变量名形式的
  `getattr(x, name)` 静态不可判定），**不得**据以判"已证明"。

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
from scripts.checks.rules_lock_guard import RULE_SUFFIXES  # noqa: E402
from scripts.checks.rules_lock_guard import check as rules_lock_check  # noqa: E402

GUARD_SUBDIR = "scripts/guard"
DATA_PATH_GLOBS = (f"{GUARD_SUBDIR}/**",)
RULEWRITE_RELPATH = f"{GUARD_SUBDIR}/rulewrite.py"
EXECUTOR_RELPATH = f"{GUARD_SUBDIR}/executor.py"
RECOMMENDATION_STEM = "recommendations"

# ── 能力白名单 ①：数据路径允许 import 的**模块路径**（未列入即 FATAL）──────────────
#
# 逐项理由（`R-06` ⑤：首选 allowlist；未列形式默认拒绝，故可穷尽）：
#   __future__   —— `from __future__ import annotations`：仅前向引用注解，无运行期能力
#   typing       —— 类型注解（Any / Mapping / Sequence / Iterator / NoReturn），纯静态
#   dataclasses  —— `dataclass` / `field`：纯数据容器，无 I/O 能力
#   pathlib      —— `Path`：仅路径运算；不含进程 / 网络 / 代码执行能力
#   hashlib      —— `sha256`：纯内容指纹函数
#   contextlib   —— `contextmanager`：作用域管理，无外部能力
#   config.rules —— 项目自身配置层（`rules/` **只读**读取：`load_yaml` / `refuse_write`）
#   schema.models —— 项目自身对象模型（pydantic 校验）
#   schema.store  —— 项目自身追加式写入口（`append_records`）
#
# 明确**不**列（一律 FATAL）：os / subprocess / pty / shlex / pickle / marshal / builtins /
#   importlib / sys / shutil / socket / ctypes / multiprocessing / threading / … 等。
ALLOWED_IMPORTS = frozenset(
    {
        "__future__",
        "typing",
        "dataclasses",
        "pathlib",
        "hashlib",
        "contextlib",
        "config.rules",
        "schema.models",
        "schema.store",
    }
)

# ── 能力白名单 ②：数据路径允许使用的 **dunder 标识符**（未列入即 FATAL）──────────
#
# 理由：dunder 名字是 **Python 语言定义的有限封闭集合**，故"允许哪些"是可穷尽的 allowlist，
#   而非对攻击形式的枚举（`R-06` ⑤）。逐项理由：
#   __all__        —— 模块导出声明（赋值目标 / 列表元素）
#   __name__       —— 模块名（f-string 里取用）
#   __getattr__    —— PEP 562 惰性加载钩子
#   __dir__        —— 模块 `__dir__` 补全
#   __init__       —— 类构造器（数据类 / 异常类的常规形态）
#   __post_init__  —— dataclass 初始化后钩子
#
# 明确**不**列（一律 FATAL）：__builtins__ / __dict__ / __globals__ / __class__ / __import__ /
#   __subclasses__ / __code__ / __reduce__ / __loader__ / __spec__ / … 等。
ALLOWED_DUNDERS = frozenset(
    {
        "__all__",
        "__name__",
        "__getattr__",
        "__dir__",
        "__init__",
        "__post_init__",
    }
)

# ── 辅助 lint（**非防护**，`R-06` ④：不可穷尽的 denylist 只作 lint，措辞已剥离防护语义）──
# 不带 import 即可触达的代码执行内建；`__import__` 已由 dunder 白名单覆盖。
# ★ 该集合**不可穷尽**（如 `getattr(x, name)` 变量名静态不可判定），**不得**据以判"已证明"。
BUILTIN_CODE_EXEC_NAMES = frozenset({"eval", "exec", "compile"})

DUNDER_PREFIX = "__"
DUNDER_SUFFIX = "__"

# 动态调用：其**字面量字符串参数**若为 dunder 形态，仍须 ∈ `ALLOWED_DUNDERS`
DYNAMIC_CALLS = frozenset({"getattr", "__import__", "eval", "exec", "compile", "setattr"})

# 收口点名称（R-07：必须各有生产调用方，AST 绑定到函数体）
CHOKEPOINT_WRITE_RULE = "write_rule"
CHOKEPOINT_REQUEST_TOOL = "request_tool"
APPEND_RECORDS_NAME = "append_records"


def _dotted(node: ast.AST) -> str:
    """把 `Name` / `Attribute` 还原为点分名（如 `os.system`）；不可还原 → `""`。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _is_dunder(name: object) -> bool:
    """`__x__` 形态（下划线起止，且中间非空）。"""
    return (
        isinstance(name, str)
        and len(name) >= 5
        and name.startswith(DUNDER_PREFIX)
        and name.endswith(DUNDER_SUFFIX)
    )


def _append_stem_arg(call: ast.Call) -> ast.AST | None:
    """取 `append_records(...)` 的 stem 实参节点（`stem=` 关键字优先，其次第 2 个位置参数）。"""
    for kw in call.keywords:
        if kw.arg == "stem":
            return kw.value
    if len(call.args) >= 2:
        return call.args[1]
    return None


class _GuardVisitor(ast.NodeVisitor):
    """对单个文件做**单遍**遍历，收集：越界 import / 越界 dunder / 写建议 / 不可判定 stem。

    `alias_map` 解析导入别名（局部名 → 完全限定名），使**改名导入**的 `append_records` 仍可识别。
    """

    def __init__(self) -> None:
        self.import_outside: list[tuple[int, str]] = []          # (lineno, 模块路径)
        self.dunder_outside: list[tuple[int, str]] = []          # (lineno, dunder 名)
        self.builtin_codeexec: list[tuple[int, str]] = []        # (lineno, 内建名) —— 辅助 lint
        self.recommendation_writes: list[tuple[int, str]] = []   # (lineno, 说明)
        self.unverifiable_stem_calls: list[tuple[int, str]] = []  # (lineno, 说明)
        self.alias_map: dict[str, str] = {}                      # 局部名 → 完全限定名

    # ── 能力白名单 ①：import 模块路径 ──
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name not in ALLOWED_IMPORTS:
                self.import_outside.append((node.lineno, alias.name))
            # `import a.b` 绑定名 `a`（指向模块 `a`）；`import a.b as x` 绑定 `x`（指向 `a.b`）
            local = alias.asname or alias.name.split(".")[0]
            self.alias_map[local] = alias.name if alias.asname else alias.name.split(".")[0]
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level and node.level > 0:
            # 相对导入：只允许 level == 1（停留在被扫的 `scripts/guard` 包内）
            if node.level != 1:
                self.import_outside.append((node.lineno, "." * node.level + (node.module or "")))
            for alias in node.names:
                self.alias_map[alias.asname or alias.name] = alias.name
            self.generic_visit(node)
            return
        module = node.module or ""
        if module not in ALLOWED_IMPORTS:
            self.import_outside.append((node.lineno, module))
        for alias in node.names:
            local = alias.asname or alias.name
            self.alias_map[local] = f"{module}.{alias.name}" if module else alias.name
        self.generic_visit(node)

    # ── 能力白名单 ②：dunder 标识符 + 辅助 lint（裸内建）──
    def _check_dunder(self, name: object, lineno: int) -> None:
        if _is_dunder(name) and name not in ALLOWED_DUNDERS:  # type: ignore[operator]
            self.dunder_outside.append((lineno, str(name)))

    def visit_Name(self, node: ast.Name) -> None:
        self._check_dunder(node.id, node.lineno)
        if node.id in BUILTIN_CODE_EXEC_NAMES:
            self.builtin_codeexec.append((node.lineno, node.id))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self._check_dunder(node.attr, node.lineno)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_dunder(node.name, node.lineno)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_dunder(node.name, node.lineno)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._check_dunder(node.name, node.lineno)
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        self._check_dunder(node.arg, node.lineno)
        self.generic_visit(node)

    # ── 别名解析 + 动态调用 dunder 参数 + 写建议 ──
    def _resolve(self, dotted: str) -> str:
        """把点分名的**首段**经 `alias_map` 解析回真实来源（如 `ar` → `schema.store.append_records`）。"""
        if not dotted:
            return ""
        head, _, tail = dotted.partition(".")
        resolved_head = self.alias_map.get(head, head)
        return f"{resolved_head}.{tail}" if tail else resolved_head

    def visit_Call(self, node: ast.Call) -> None:
        dotted = _dotted(node.func)
        resolved = self._resolve(dotted)
        callee = resolved.split(".")[-1] if resolved else ""
        literal_args = [
            arg
            for arg in list(node.args) + [kw.value for kw in node.keywords]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
        ]

        # 能力白名单 ②：动态调用的**字面量字符串参数**为 dunder 形态时，仍须 ∈ 白名单
        if callee in DYNAMIC_CALLS:
            for arg in literal_args:
                self._check_dunder(arg.value, node.lineno)

        # C：append_records（含别名 / 点分访问）的 stem 必须可静态判定（fail closed）
        if callee == APPEND_RECORDS_NAME:
            self._check_append_stem(node)

        # C：把 recommendations.jsonl 作为路径常量传入写入调用
        for arg in literal_args:
            if f"{RECOMMENDATION_STEM}.jsonl" in arg.value:
                self.recommendation_writes.append((node.lineno, "path:recommendations.jsonl"))

        self.generic_visit(node)

    def _check_append_stem(self, node: ast.Call) -> None:
        """stem 为字符串字面量 → 仅当等于 recommendations 判违例；否则 fail closed。"""
        stem = _append_stem_arg(node)
        if isinstance(stem, ast.Constant) and isinstance(stem.value, str):
            if stem.value == RECOMMENDATION_STEM:
                self.recommendation_writes.append(
                    (node.lineno, "append_records:recommendations")
                )
            return
        form = type(stem).__name__ if stem is not None else "MISSING_STEM_ARG"
        self.unverifiable_stem_calls.append((node.lineno, f"append_records:{form}"))


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
    """断言 `Ch9 §N9.2-01` 判据的不变式形式（能力白名单，不依赖关键词黑名单）。"""
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

    # ── B / C. 数据路径单遍 AST：能力白名单 + 写建议 ──
    import_outside_hits = 0
    dunder_outside_hits = 0
    builtin_codeexec_hits = 0
    rec_writes = 0
    unverifiable_stem_calls = 0
    for path in modules:
        visitor = _analyze(path)
        relpath = rel(path, root)
        for lineno, module in visitor.import_outside:
            import_outside_hits += 1
            report.violations.append(
                Violation(
                    "能力白名单·import",
                    f"数据路径 import 了白名单外的模块 {module!r} —— "
                    "外部文本不得触达白名单外的能力（未列入即拒）",
                    relpath,
                    lineno,
                )
            )
        for lineno, name in visitor.dunder_outside:
            dunder_outside_hits += 1
            report.violations.append(
                Violation(
                    "能力白名单·dunder",
                    f"数据路径使用了白名单外的 dunder 名 {name!r} —— "
                    "未列入即拒（dunder 为语言定义的封闭集合）",
                    relpath,
                    lineno,
                )
            )
        for lineno, name in visitor.builtin_codeexec:
            builtin_codeexec_hits += 1
            report.violations.append(
                Violation(
                    "辅助lint·代码执行内建",
                    f"数据路径出现代码执行内建 {name!r}（辅助 lint，非完整防护）",
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
        for lineno, what in visitor.unverifiable_stem_calls:
            unverifiable_stem_calls += 1
            report.violations.append(
                Violation(
                    "判据·不产生建议",
                    f"append_records 的 stem 无法静态判定（{what}）—— "
                    "fail closed：无法证明不写建议，即判违例",
                    relpath,
                    lineno,
                )
            )
    report.scanned["import_outside_allowlist"] = import_outside_hits
    report.scanned["dunder_outside_allowlist"] = dunder_outside_hits
    report.scanned["builtin_codeexec_hits"] = builtin_codeexec_hits
    report.scanned["recommendation_writes"] = rec_writes
    report.scanned["unverifiable_stem_calls"] = unverifiable_stem_calls

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
    body_calls_per_func: list[set[str]] = []
    for node in ast.walk(ex_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body_calls_per_func.append(_body_calls(node))
    calls_write_rule = any(
        any(c == CHOKEPOINT_WRITE_RULE or c.endswith(".write_rule") for c in calls)
        for calls in body_calls_per_func
    )
    calls_request_tool = any(
        any(c == CHOKEPOINT_REQUEST_TOOL or c.endswith(".request_tool") for c in calls)
        for calls in body_calls_per_func
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

    # ── 显式记 note（设计说明 / 空样本，**不得**判 PASS=已验证）──
    report.notes.append(
        "CAPABILITY_ALLOWLIST: 数据路径的 import 模块（ALLOWED_IMPORTS）与 dunder 标识符"
        "（ALLOWED_DUNDERS）均受**显式白名单**约束，**未列入即 FATAL**；白名单对未列形式默认拒绝，"
        "故为**封闭集合**判定（CONVENTIONS.md::R-06）。"
    )
    report.notes.append(
        "AUX_LINT: builtin_codeexec_hits 为**辅助 lint**（eval/exec/compile 裸名），该集合**不可穷尽**，"
        "仅作附加绊线，**不得**据以判『已证明』（R-06 ④）。"
    )
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
