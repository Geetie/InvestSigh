#!/usr/bin/env python3
"""`shell_var_guard.py` —— **shell 变量紧邻多字节字符**守卫（命中即 fail）。

## 为什么需要它（实测故障，不是假想）

`system/scripts/ops/pre-commit.sh` 第 45 行原本是：

```sh
echo "pre-commit ✗ $label 阻断（exit=$rc）" >&2
```

`$rc` **紧跟全角括号 `）`**。shell 取变量名时把 `）` 的 UTF-8 首字节（`0xEF`）并进了
变量名，于是它去找一个叫 `rc\\xef…` 的变量 —— `set -u` 下**当场中止**：

```
system/scripts/ops/pre-commit.sh: line 45: rc<乱码>: unbound variable
```

**后果远不止"报个错"**：那一崩发生在 `FAILED=1` **之前**，所以

1. `FAILED` 没被设上；
2. **其后的门禁（⑤ `conflict_scan` / ⑥ `no_placeholder_guard` /
   ⑦ `injection_guard` / ⑧ `verification_policy_guard`）根本没跑**；
3. 脚本从未走到末尾的「有门禁阻断，提交被拒」分支。

= **一个门禁失败，会让另外 4 个门禁悄悄不被检查** —— 一个**假绿灯面**（`§一 底线 3`）。

## 判据（`CONVENTIONS.md::R-06`：可判定 + 穷尽；允许清单优于禁止清单）

**唯一判据**：`*.sh` / shell shebang 文件里，出现**未加花括号的命名变量引用
`$name`，且其紧后一个字符是非 ASCII**（字节 ≥ 0x80）→ **违例**。

- **可判定**：正则 + 字节判定，唯一结果，无解释空间。
- **穷尽**：每一处 `$` 引用要么是 `${name}`（花括号 → 天然安全，**不可能**被并名），
  要么是未加花括号 —— 后者**只要**紧后是非 ASCII 就命中。不存在"第三种形式"。
- **为什么不必区分是否真会崩**：修复动作**恒为加花括号** `${name}`（对 shell **永远等价**），
  故对"是否命中"的判定无须依赖具体 shell 的行为差异 —— **宁可按最严判，修复成本为零**。
- **刻意不覆盖**：特殊参数 `$1` `$@` `$*` `$#` `$?` `$!` `$$` `$-` 是**定长单字符**记号，
  不会被并名 → 只匹配 `$[A-Za-z_][A-Za-z0-9_]*`。**允许清单式**排除，非黑名单。

## 降噪（`CONVENTIONS.md §二 G-01`：宁可漏报不可吵）

- **整行注释**（首个非空白字符为 `#`）**跳过** —— 注释里的同形文本不参与执行，不当违例。
- 行内注释**不剥离**（剥离需引号感知的状态机，成本与误判风险都高）；
  因修复恒为零成本，对行内注释一并要求 `${}` 是**可接受的收紧**，不会造成"天天误报"。

## 扫描域（允许清单，穷尽且如实）

**允许清单**（`R-06 ⑤`：未列出的形式默认不纳入）：
**① 扩展名为 `.sh` 的文件** ∪ **② 无扩展名、且首行为 shell shebang 的文件**。

- 其它扩展名（`.py` / `.md` / `.log` / `.json` …）**一律不打开** —— 既符合允许清单原则，
  也满足 `P-05`（初版对每个文件都 `open()` 读首行，全树耗时 0.75s，**超 0.5s 指标**）。
- 跳过任何以 `.` 开头的路径分量与 `__pycache__`（与 `_common.walk_files` 既有约定一致）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# `parents[2]`：本文件在 `<code_root>/scripts/checks/` 下 → 上溯到 `code_root`。
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import (  # noqa: E402
    CheckReport,
    Violation,
    run_checker,
)

#: 未加花括号的**命名**变量引用，且紧后一个字符为多字节（非 ASCII）。
_VAR_THEN_MULTIBYTE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)(?=[^\x00-\x7F])")

#: 判据的**总体**：所有未加花括号的命名变量引用（不论紧后是什么字符）。
#: 命中数 = `_VAR_THEN_MULTIBYTE`，被检数 = 本式 —— 两个数都来自实测，**不拿行数冒充被检数**。
_UNBRACED_VAR = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")

#: shell shebang（`#!` 后到行尾出现 sh / bash / dash 作为词）。
_SHEBANG = re.compile(r"^#!.*\b(?:sh|bash|dash)\b")


def _is_shell_script(path: Path) -> bool:
    """**允许清单**式判定（`R-06 ⑤`）：`.sh`，或无扩展名且首行为 shell shebang。

    ★ **性能约束（`P-05`：新守卫 < 0.5s）**：初版对**每个**候选文件都 `open()` 读首行判 shebang，
      在 `system/` 全树上耗时 **0.75s**（超 `P-05`）—— 因为要打开上千个 `.py`/`.md`/`.log`。
      现改为：**扩展名不是 `.sh` 时直接返回 False，不打开文件**；只有**无扩展名**的文件
      才值得读首行（要 `./x` 执行它必须同时有 shebang 与可执行位）。
      这不是 denylist：判定只依据"是否在允许清单内"，未列出的一律**不纳入扫描域**。
    """
    if path.suffix == ".sh":
        return True
    if path.suffix:
        return False
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return bool(_SHEBANG.match(fh.readline()))
    except OSError:
        return False


def _iter_candidate_files(root: Path) -> list[Path]:
    """`code_root` 下所有 shell 脚本（跳过点目录/点文件）。"""
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        if "__pycache__" in rel_parts:
            continue
        if _is_shell_script(path):
            out.append(path)
    return sorted(out)


def check(root: Path) -> CheckReport:
    """逐文件扫描；命中即 `Violation`（`severity` 恒 FATAL，纪律 2 禁 warn-only）。"""
    files = _iter_candidate_files(root)
    violations: list[Violation] = []
    lines_scanned = 0
    comments_skipped = 0
    refs_checked = 0

    for path in files:
        relpath = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, raw in enumerate(text.splitlines(), start=1):
            lines_scanned += 1
            if raw.lstrip().startswith("#"):
                comments_skipped += 1
                continue
            refs_checked += len(_UNBRACED_VAR.findall(raw))
            for match in _VAR_THEN_MULTIBYTE.finditer(raw):
                name = match.group(1)
                tail = raw[match.end() : match.end() + 1]
                violations.append(
                    Violation(
                        rule="SHELL-VAR-MULTIBYTE",
                        reason=(
                            f"未加花括号的 ${name} 紧邻多字节字符 {tail!r} —— shell 会把其首字节"
                            f"并进变量名；`set -u` 下报 `{name}<乱码>: unbound variable` 并**中止脚本**"
                            f"（实测：曾使 pre-commit 的后续 4 个门禁全部未执行）。"
                            f"修法：写作 `${{{name}}}`"
                        ),
                        file=relpath,
                        line=lineno,
                    )
                )

    report = CheckReport(checker="shell_var_guard.py")
    report.violations = violations
    report.scanned = {
        "shell_files": len(files),
        "lines_scanned": lines_scanned,
        "comment_lines_skipped": comments_skipped,
        # ★ 被检总体 = 实测的未加花括号命名变量引用数（**不是行数**）
        "unbraced_var_refs_checked": refs_checked,
        "multi_byte_adjacent_hits": len(violations),
    }
    report.notes.append(
        "判据 = 未加花括号的 `$name` 紧后一个字符为多字节（R-06：可判定 + 穷尽；"
        "花括号形式天然安全，故无第三态）；特殊参数 $1/$@/$? 等定长记号**不在**匹配域（允许清单式排除）"
    )
    report.notes.append(
        "扫描域 = 允许清单：`*.sh` ∪ 无扩展名且首行为 shell shebang 的文件"
        "（其它扩展名不打开；跳过点目录/点文件）；整行注释跳过，行内注释不剥离"
    )
    if not files:
        report.notes.append(
            "NO_SHELL_FILES：扫描域内没有 shell 脚本 —— **无被检对象 ≠ 已验证**（G-03），"
            "本条按真空成立记录，不得据此判『shell 变量写法已证明安全』"
        )
    return report


if __name__ == "__main__":
    sys.exit(run_checker("shell_var_guard.py", check))
