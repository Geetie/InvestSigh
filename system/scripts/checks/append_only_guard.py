#!/usr/bin/env python3
"""`append_only_guard.py` —— **追加式不可变守卫**（`Ch9 §3.4.2` · `施工图 §8` 纪律 4）。

```
python system/scripts/checks/append_only_guard.py [code_root]
```

**纪律 4：追加式不可变 —— pre-commit 拒改既有行（新增放行）。**

`facts/*.jsonl` 是 8 类对象的**唯一真源**，且是追加式（append-only）：
每一次修正都必须**追加新版本行**（`recorded_seq` 递增 + `version_kind` 标记），
而不是就地改写历史。理由（`Ch9 §3.4.2`）：就地改写会让"当时看到的是什么"
永远无法复原 —— 而本项目**整份交付的价值就在可审计**。

判据（只看 `git diff --cached`，即**即将提交的暂存区**）：

| 暂存区里的形态 | 判定 |
|---|---|
| 新增行（`+`） | ✅ 放行 |
| 新建 `facts/*.jsonl` 文件 | ✅ 放行（全为新增） |
| 删除既有行（`-`） | ❌ 阻断 |
| 改写既有行（`-`+`+`） | ❌ 阻断 |
| 删除 / 重命名整个 JSONL | ❌ 阻断 |

★ 退出码：`0` 放行 / `1` 阻断 / `2` 输入异常，**不静默**。
★ **命中即 fail，禁 warn-only**（纪律 2）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import (  # noqa: E402
    CheckReport,
    Violation,
    run_checker,
)

FACTS_DIRNAME = "facts"

# 追加式守卫的"既有行"识别：diff 里以单个 `-` 开头（排除 `--- a/...` 这行文件头）
_DELETED_LINE = "-"
_FILE_HEADER = "--- "


class AppendOnlyViolation(RuntimeError):
    """暂存区改写了 `facts/*.jsonl` 的既有行 —— 追加式不可变被破坏（`Ch9 §3.4.2`）。"""


def _git(args: list[str], cwd: Path) -> str:
    """跑 git 子命令。非 git 仓库 / git 不可用 → 抛错（不静默放行）。"""
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise FileNotFoundError(
            f"git {' '.join(args)} 失败（rc={proc.returncode}）：{proc.stderr.strip()}"
        )
    return proc.stdout


def repo_toplevel(root: Path) -> Path:
    """定位仓库根。**从仓库根跑 git**、并用"相对仓库根"的 pathspec ——
    否则在 `system/` 子目录里跑时 pathspec 会按 cwd 解析，容易悄悄指错对象。
    """
    top = _git(["rev-parse", "--show-toplevel"], root).strip()
    if not top:
        raise FileNotFoundError(f"{root}: git 未返回仓库根（不静默放行）")
    return Path(top)


def facts_pathspec(root: Path, toplevel: Path) -> str:
    """`facts/*.jsonl` 相对**仓库根**的 pathspec（本仓库里通常是 `system/facts/*.jsonl`）。"""
    facts = (root / FACTS_DIRNAME).resolve()
    rel = facts.relative_to(toplevel.resolve())
    return f"{rel.as_posix()}/*.jsonl"


def staged_facts_diff(toplevel: Path, pathspec: str) -> str:
    """取暂存区里 facts JSONL 的 diff（零上下文行，便于逐行判定）。"""
    return _git(["diff", "--cached", "--unified=0", "--", pathspec], toplevel)


def assert_append_only(diff_text: str) -> None:
    """解析 diff 文本；发现既有行被改/删 → 抛 `AppendOnlyViolation`。

    逐文件的依据是 `diff --git a/… b/…` 段落，与段内的
    `deleted file mode` / `rename from` 标记。
    """
    problems: list[str] = []
    current = "<unknown>"

    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            current = raw.split(" b/", 1)[-1]
            continue
        if raw.startswith("deleted file mode"):
            problems.append(f"{current}: 整个 JSONL 被删除（真源不得删除）")
            continue
        if raw.startswith("rename from") or raw.startswith("rename to"):
            problems.append(f"{current}: JSONL 被重命名（真源文件不得改名）")
            continue
        if raw.startswith(_FILE_HEADER) or raw.startswith("+++ "):
            continue
        if raw.startswith(_DELETED_LINE):
            problems.append(f"{current}: 存在被删除/改写的既有行 → {raw[1:120]}")

    if problems:
        raise AppendOnlyViolation("；".join(problems))


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="append_only_guard")
    toplevel = repo_toplevel(root)          # 非 git 仓库 → FileNotFoundError → exit 2
    pathspec = facts_pathspec(root, toplevel)

    diff_text = staged_facts_diff(toplevel, pathspec)
    files = [ln.split(" b/", 1)[-1] for ln in diff_text.splitlines() if ln.startswith("diff --git ")]
    report.scanned["staged_facts_files"] = len(files)
    report.scanned["diff_bytes"] = len(diff_text)
    report.notes.append(f"pathspec = {pathspec}（相对仓库根 {toplevel}）")

    if not diff_text.strip():
        report.notes.append(
            "NO_STAGED_FACTS_CHANGES：暂存区没有 facts JSONL 的改动；"
            "本次**无被检对象**，不代表‘已验证追加式不可变’"
        )
        return report

    try:
        assert_append_only(diff_text)
    except AppendOnlyViolation as exc:
        for item in str(exc).split("；"):
            report.violations.append(
                Violation("Ch9 §3.4.2 / 纪律 4", item, pathspec)
            )
    return report


if __name__ == "__main__":
    sys.exit(run_checker("append_only_guard.py", check))
