#!/usr/bin/env python3
r"""`no_placeholder_guard.py` —— **反占位符扫描**（`00_开发Agent开工提示词 §八 N-2`）。

```
python system/scripts/checks/no_placeholder_guard.py <code_root> [--fail-on warn|error]
```

规格（逐条实现 `§八 N-2`）：

- 检测：`TODO` / `FIXME` / `HACK` / `待实现` / 占位、`NotImplementedError`、
  **空函数体**、假数据返回（`mock` / `fake` / `dummy`）、`except: pass`、
  **log 后原样重抛**、演示话术（`coming soon` / `演示用` / `先写死`）、硬编码兜底返回
- 退出码：`0` 放行 / `1` 阻断 / `2` 输入异常，**不静默**
- ★ **跨行规则必须走全文匹配再回填行号** —— 逐行扫描下
  `except X:` + 下一行 `pass` **永远命中不了**，而"吞异常"恰恰最该拦。

★ **扫描范围只写 `code_root`（= `.../system`）**，**不要**写 `.`、也不要写仓库根 ——
  设计文档里天然充满"占位符/TODO"这类词，指到设计区会误报刷屏，
  结果是门禁被关掉。**降噪就是有效性：宁可漏报不可吵。**

★ 免扫命名空间：本文件自身 + `tests/**`（测试夹具里出现 `mock`/`fake` 属正常）。

---

### 两条实测修正（本文件 v2，均为"真跑"暴露出来的缺陷）

**修正 1 —— 注释与字符串必须抹白，否则文档会把自己判成违例。**
初版只去 `#` 行注释，**不抹字符串**。本包 docstring 里为解释规则必须引用
`TODO` / `占位` / `mock` 这些词，结果扫描器把自己团队的**文档**当违例刷屏。
现改用 `tokenize` 忠实抹白 `COMMENT` / `STRING` / `FSTRING_MIDDLE`，
**逐行保留换行、行号 1:1 不变**（语法不合法时退回朴素去注释，扫描器不得因
源文件语法错而停摆）。

**修正 2 —— 嵌套量词正则会灾难性回溯到卡死。**
初版 `LOG_AND_RERAISE` 用 `(?:\s*.+\n)*?`，在长文件上**永久回溯**。实测
`run_all_gates.py --timeout 25` 直接 `TIMEOUT`（卡死），而**卡死的门禁等于
被关掉的门禁**——比漏报更坏。现分两路：

1. **两行规则**（`except:` → 下一行 `pass` / `continue` / `return None`）
   仍走**全文正则 + `_line_of_offset` 回填行号**，正则已改写为
   **无嵌套量词**（两个分支在行首字符上互斥，每行唯一匹配 → 线性）。
2. **结构规则**（`log 后原样重抛` / 空函数体）需要**缩进语义**，
   正则表达不了（写出来必然又是嵌套量词）。改走**缩进感知窗口扫描**：
   在全文的行序列上做，行号天然正确，无需回填。

**修正 3 —— 空函数体必须跑在"保留字符串"的文本上。**
修正 1 抹白字符串后，`class Foo(Exception)` 后跟一段 docstring 这类**异常类**
被误判空体（全包 13 条误报）。真实语义是：**docstring 本身就是一条语句，函数体不空**。
故 `EMPTY_BODY` 改走 **AST 精确判定**（能 `ast.parse` 时）：
`def` 剔除首个 docstring 后不得只剩 `pass` / `...`（`§一 底线 1`）；`class`
只在 body 真的为空时才算——异常类/协议类"只有 docstring"是常态。
**语法不合法**时退回保守的窗口启发式（只报"声明之后一行语句都没有"），
并在报告里记 note——**不静默跳过**。

**修正 4 —— 非 `.py` 文件也必须先剥注释。**
`DATA_PLACEHOLDER` 原本对 `.sh`/`.yaml` **逐行全文**匹配，结果
`scripts/ops/pre-commit.sh` 里那句注释 `# ③ N-2 反占位符（命中即 fail）`
被判成"数据里的占位话术"。**描述规则的文字被规则自己判成违例**，
与修正 1 是同一类错误。现非 `.py` 文件同样先 `_comment_only()` 再匹配；
`.json` 无注释语法，原样扫描。
"""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

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

SCAN_EXTENSIONS = (".py", ".yaml", ".yml", ".json", ".sh")

# 免扫：测试夹具与检查器自身（检查器必须能说出这些词才能检测它们）
EXEMPT_PATTERNS = (
    "tests/",
    "scripts/checks/no_placeholder_guard.py",
)

# ── 逐行规则 ────────────────────────────────────────────────────────────────
LINE_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("PLACEHOLDER-TODO", "占位标记 TODO", re.compile(r"\bTODO\b")),
    ("PLACEHOLDER-FIXME", "占位标记 FIXME", re.compile(r"\bFIXME\b")),
    ("PLACEHOLDER-HACK", "占位标记 HACK", re.compile(r"\bHACK\b")),
    ("PLACEHOLDER-CN", "中文占位标记（待实现/待补/占位/未实现）", re.compile(r"待实现|待补|占位|未实现")),
    ("NOT_IMPLEMENTED", "NotImplementedError", re.compile(r"NotImplementedError")),
    ("FAKE_DATA", "假数据返回（mock/fake/dummy）", re.compile(r"\b(mock|fake|dummy)\b", re.IGNORECASE)),
    ("DEMO_TALK", "演示话术（coming soon / 演示用 / 先写死）", re.compile(r"coming soon|演示用|先写死|暂写死", re.IGNORECASE)),
    ("HARDCODED_FALLBACK", "硬编码兜底返回", re.compile(r"return\s+\{[^{}]*\}?\s*[:]\s*(['\"])status\1\s*[:]\s*(['\"])ok\2")),
)

# ── 跨行规则之一：**安全正则**（无嵌套量词）→ 全文匹配 + 回填行号 ────────────────
#
# `^[ \t]*except …:[ \t]*\n` 之后允许若干"空行 / 纯注释行"，再出现落体语句。
# 两个分支的判别字符互斥（空行只能由分支 A 匹配、`#` 行只能由分支 B 匹配），
# 每行只有唯一一种匹配方式 → **线性**，不会回溯爆炸。
_MID_LINES = r"(?:[ \t]*\n|[ \t]*\#[^\n]*\n)*"

CROSSLINE_REGEX_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "SWALLOW_EXCEPTION_PASS",
        "吞异常：except 后 pass",
        re.compile(rf"^[ \t]*except\b[^\n]*:[ \t]*\n{_MID_LINES}[ \t]*pass\b", re.MULTILINE),
    ),
    (
        "SWALLOW_EXCEPTION_CONTINUE",
        "吞异常：except 后 continue / return None",
        re.compile(
            rf"^[ \t]*except\b[^\n]*:[ \t]*\n{_MID_LINES}[ \t]*(?:continue|return[ \t]+None)\b",
            re.MULTILINE,
        ),
    ),
)

# 结构规则识别用的模式
_EXCEPT_HEADER = re.compile(r"^([ \t]*)except\b[^\n]*:(?P<tail>[ \t]*)(?P<inline>.*)$")
_DEF_HEADER = re.compile(r"^([ \t]*)(?:async[ \t]+)?(?:def|class)\b[^\n]*:(?P<tail>[ \t]*)(?P<inline>.*)$")
_LOG_CALL = re.compile(r"^(?:logger|logging|log)\s*\.\s*\w+\s*\(")
_BARE_RAISE = re.compile(r"^raise\s*$")
_BARE_PASS = re.compile(r"^pass\s*$")
_BARE_CONTINUE = re.compile(r"^continue\s*$")
_RETURN_NONE = re.compile(r"^return\s+None\s*$")

# yaml/json 里不应出现的占位话术（**仅限代码区**，设计区不在扫描范围）
#
# ★ 只跑在"**剥掉注释**"的文本上（与 .py 的 docstring 同理，见下）。
#   实测：`scripts/ops/pre-commit.sh` 的注释 `# ③ N-2 反占位符（命中即 fail）`
#   被判成占位话术——**描述规则的文字**不该被规则判成违例。
DATA_PLACEHOLDER = re.compile(r"待填写|待补充|占位符|PLACEHOLDER")


@dataclass(frozen=True)
class Finding:
    rule: str
    reason: str
    line: int


def _line_of_offset(text: str, offset: int) -> int:
    """把全文匹配的字符偏移**回填**成行号（`§八 N-2` 的硬要求）。"""
    return text.count("\n", 0, offset) + 1


# ───────────────────────── 抹白注释与字符串（修正 1） ─────────────────────────

_STRING_TOKENS = {tokenize.STRING}
for _extra in ("FSTRING_MIDDLE",):
    _tok = getattr(tokenize, _extra, None)
    if _tok is not None:
        _STRING_TOKENS.add(_tok)


def _comment_only(text: str) -> str:
    """退化路径：只去 `#` 之后内容（保留换行）。语法不合法时使用。"""
    return "\n".join(re.sub(r"#.*$", "", line) for line in text.splitlines())


def strip_comments_and_strings(text: str) -> str:
    """把注释与字符串字面量**抹成空白**，**逐行保留换行 → 行号 1:1 不变**。

    为什么必须做：docstring 里为解释规则会引用 `TODO` / `占位` / `mock`
    这些词，朴素扫描会把**文档**当违例，报告被噪声淹没 → 门禁被关掉。

    语法不合法时退回 `_comment_only`：扫描器**不得**因源文件语法错而停摆。
    """
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return _comment_only(text)

    lines = text.splitlines(keepends=True)
    for tok in toks:
        if tok.type not in _STRING_TOKENS and tok.type != tokenize.COMMENT:
            continue
        (srow, scol), (erow, ecol) = tok.start, tok.end
        for row in range(srow, erow + 1):
            idx = row - 1
            if idx < 0 or idx >= len(lines):
                continue
            line = lines[idx]
            body_len = len(line.rstrip("\r\n"))          # 绝不跨行吃掉换行符
            start = scol if row == srow else 0
            end = ecol if row == erow else body_len
            start = min(max(start, 0), body_len)
            end = min(max(end, start), body_len)
            lines[idx] = line[:start] + " " * (end - start) + line[end:]
    return "".join(lines)


# ───────────────────────── 缩进感知窗口（修正 2） ─────────────────────────

def _indent_of(raw: str) -> int:
    expanded = raw[: len(raw) - len(raw.lstrip(" \t"))].expandtabs(8)
    return len(expanded)


def _block_body(lines: list[str], header_idx: int, indent: int) -> tuple[str, list[tuple[int, str]]]:
    """取 header 行之后、缩进大于 `indent` 的语句行 —— 返回 (inline 语句, [(行号, 语句)])。"""
    inline = ""
    header = lines[header_idx]
    colon = header.find(":", len(header) - len(header.lstrip()))
    if colon != -1:
        inline = header[colon + 1 :].strip()
    body: list[tuple[int, str]] = []
    j = header_idx + 1
    while j < len(lines):
        raw = lines[j]
        if raw.strip() == "":
            j += 1
            continue
        if _indent_of(raw) <= indent:
            break
        body.append((j + 1, raw.strip()))                # 行号 = 索引 + 1
        j += 1
    return inline, body


def scan_log_and_reraise(code: str) -> Iterator[Finding]:
    """`LOG_AND_RERAISE`：`except` 块内**只有**一条 log 调用 + 一条裸 `raise`。

    跑在"字符串已抹白"的 `code` 上（避免 docstring 里举例的写法被当真）。
    缩进感知窗口 → 行号天然正确。
    """
    lines = code.splitlines()
    for i, raw in enumerate(lines):
        m = _EXCEPT_HEADER.match(raw)
        if not m:
            continue
        inline, body = _block_body(lines, i, _indent_of(raw))
        stmts = ([inline] if inline and not inline.startswith("#") else []) + [s for _, s in body]
        stmts = [s for s in stmts if s and not s.startswith("#")]
        if len(stmts) >= 2 and _LOG_CALL.match(stmts[0]) and _BARE_RAISE.match(stmts[-1]):
            if all(_LOG_CALL.match(s) or _BARE_RAISE.match(s) for s in stmts):
                yield Finding("LOG_AND_RERAISE", "log 后原样重抛（只加了日志，没有处理）", i + 1)


# ── EMPTY_BODY：AST 精确判定（修正 3） ──

def _is_docstring_stmt(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _is_placeholder_stmt(stmt: ast.stmt) -> bool:
    """`pass` 或 `...` —— 都是"没写实现"的等价写法（`§一 底线 1`）。"""
    if isinstance(stmt, ast.Pass):
        return True
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and stmt.value.value is Ellipsis
    )


def _function_body_is_empty(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = list(node.body)
    if body and _is_docstring_stmt(body[0]):
        body = body[1:]          # ★ docstring 不算实现，但也不算"函数体不存在"
    if not body:
        return True              # def 只有 docstring → 空实现
    return all(_is_placeholder_stmt(s) for s in body)


def scan_empty_body_ast(text: str) -> tuple[list[Finding], bool]:
    """AST 精确判定空函数体 / 空类体。

    返回 `(findings, parsed)`。`parsed=False` 表示语法不合法、调用方须走兜底
    —— **不用 `None` 当哨兵**：`except …: return None` 属于"吞异常 + 置 null"
    （`§5.1 AC-05`），本文件自己先违反就说不过去。
    """
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return [], False
    out: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _function_body_is_empty(node):
                out.append(
                    Finding("EMPTY_BODY", "空函数体（剔除 docstring 后只剩 pass/...）", node.lineno)
                )
        elif isinstance(node, ast.ClassDef) and not node.body:
            out.append(Finding("EMPTY_BODY", "空类体（声明后无语句）", node.lineno))
    return sorted(out, key=lambda f: f.line), True


def scan_empty_body_fallback(comment_free: str) -> Iterator[Finding]:
    """语法不合法时的保守兜底：只报"声明之后一行语句都没有"（宁漏不误伤）。"""
    lines = comment_free.splitlines()
    for i, raw in enumerate(lines):
        if not _DEF_HEADER.match(raw):
            continue
        inline, body = _block_body(lines, i, _indent_of(raw))
        if not inline and not body:
            yield Finding("EMPTY_BODY", "空函数体/类体（声明后无语句）", i + 1)


# ───────────────────────── 扫描 ─────────────────────────

def scan_file(path: Path, root: Path) -> tuple[list[Finding], list[str]]:
    """返回 `(findings, notes)`。`notes` 用于记录"降级到兜底路径"这类不静默的事实。"""
    text = path.read_text(encoding="utf-8")
    findings: list[Finding] = []
    notes: list[str] = []

    if path.suffix == ".py":
        # 注释/字符串抹白 → 逐行规则与两行跨行规则都跑在"代码本身"上
        code = strip_comments_and_strings(text)

        for lineno, line in enumerate(code.splitlines(), start=1):
            for rule, reason, pattern in LINE_RULES:
                if pattern.search(line):
                    findings.append(Finding(rule, reason, lineno))

        # ── 跨行（两行）规则：**全文匹配 + 回填行号** ──
        for rule, reason, pattern in CROSSLINE_REGEX_RULES:
            for m in pattern.finditer(code):
                findings.append(Finding(rule, reason, _line_of_offset(code, m.start())))

        # ── 跨行（结构）规则 ──
        findings.extend(scan_log_and_reraise(code))

        # ★ EMPTY_BODY 走**原文**（保留 docstring）：docstring 本身是语句，
        #   异常类"只有 docstring"不是空体（修正 3）。
        ast_findings, parsed = scan_empty_body_ast(text)
        if parsed:
            findings.extend(ast_findings)
        else:
            notes.append(f"{rel(path, root)}: 语法不合法，EMPTY_BODY 降级为保守窗口扫描")
            findings.extend(scan_empty_body_fallback(_comment_only(text)))
    else:
        # ★ 非 .py 文件同样**先剥注释**再判：`# … 占位符 …` 是在**描述规则**，
        #   不是占位数据。JSON 无注释语法 → 原样扫描。
        scannable = text if path.suffix == ".json" else _comment_only(text)
        for lineno, line in enumerate(scannable.splitlines(), start=1):
            if DATA_PLACEHOLDER.search(line):
                findings.append(Finding("DATA_PLACEHOLDER", "数据/配置中的占位话术", lineno))
    return findings, notes


def _is_exempt(relpath: str) -> bool:
    normalized = relpath.replace("\\", "/")
    return any(pat in normalized for pat in EXEMPT_PATTERNS)


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="no_placeholder_guard")
    # ★ `rel(path, root)` —— 参数顺序**必须**是 (path, root)。曾写成
    #   `rel(root, p)`，`relative_to` 抛 ValueError 后 `rel` 返回裸绝对路径，
    #   于是 `_is_exempt` 永远 False、**免扫机制整体失效**（连本文件与 tests/
    #   都被扫），正是"误报刷屏 → 门禁被关掉"的引信。
    files = [p for p in walk_files(root, "", SCAN_EXTENSIONS) if not _is_exempt(rel(p, root))]
    report.scanned["files"] = len(files)
    report.scanned["exempt_patterns"] = len(EXEMPT_PATTERNS)
    report.scanned["line_rules"] = len(LINE_RULES)
    report.scanned["crossline_regex_rules"] = len(CROSSLINE_REGEX_RULES)
    report.scanned["crossline_structural_rules"] = 2
    for path in files:
        findings, notes = scan_file(path, root)
        report.notes.extend(notes)
        for f in findings:
            report.violations.append(Violation(f.rule, f.reason, rel(path, root), f.line))
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="no_placeholder_guard.py")
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--fail-on", default="warn", choices=("warn", "error"))
    parser.add_argument("--no-report", action="store_true")
    # ★ `--fail-on warn` 即"命中即 fail"（本包不接受 warn-only，纪律 2）
    args, _unknown = parser.parse_known_args(argv)
    root = Path(args.code_root) if args.code_root else _ROOT
    return run_checker(
        "no_placeholder_guard.py",
        check,
        [str(root)] + (["--no-report"] if args.no_report else []),
    )


if __name__ == "__main__":
    sys.exit(main())
