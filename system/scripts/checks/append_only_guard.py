#!/usr/bin/env python3
"""`append_only_guard.py` —— **追加式不可变守卫**（`Ch9 §3.4.2` · `施工图 §8` 纪律 4）。

```
python system/scripts/checks/append_only_guard.py [code_root]
```

**纪律 4：追加式不可变 —— pre-commit 拒改既有行（新增放行）。**

`facts/*.jsonl` 是**事实表的唯一真源**，且是追加式（append-only）：
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

import os
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


def _git(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    """跑 git 子命令。非 git 仓库 / git 不可用 → 抛错（不静默放行）。"""
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False, env=env
    )
    if proc.returncode != 0:
        raise FileNotFoundError(
            f"git {' '.join(args)} 失败（rc={proc.returncode}）：{proc.stderr.strip()}"
        )
    return proc.stdout


#: git 在**钩子**里会导出这些变量；它们会让 `git rev-parse --show-toplevel` 报 **cwd** 而不是工作树根。
_HOOK_ENV_OVERRIDES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_PREFIX")


def _git_env() -> dict[str, str]:
    """跑 git 用的环境：**去掉钩子导出的 `GIT_DIR` 等**，保留 `GIT_INDEX_FILE`。

    ★ 为什么必须去（实测的**假绿**缺陷，`纪律 4` 的手段曾因此在 worktree 上失效）：
      `git` 在**钩子**里把 `GIT_DIR` 导出给子进程；此时**不带** `GIT_WORK_TREE` 的
      `git rev-parse --show-toplevel` **不查仓库**，直接把 **cwd 当工作树根**返回。
      于是从 `system/` 里跑本守卫时：

      | 仓库形态 | `--show-toplevel` | pathspec | `git diff --cached` 看到 |
      |---|---|---|---|
      | 普通仓库（cwd == 根） | 根 | `system/facts/*.jsonl` | ✅ 暂存改动 |
      | **linked worktree**（cwd == `<wt>/system`） | `<wt>/system` | `facts/*.jsonl` | ❌ **恒为空** |

      ⇒ 在 worktree 里 `git commit` 时本守卫**恒报"无被检对象"并放行** —— 即
      「追加式不可变」在**每个用 worktree 干活的人**那里都没有手段落地。
      实测（`git worktree`，基点 `bc26933` 与本提交均复现）：改写
      `facts/dependency_edges.jsonl` 的**既有行** → `git add` → `git commit` **成功**，
      被改写的行进了版本库，而守卫输出 `staged_facts_files: 0` + `RESULT: PASS`。

      去掉 `GIT_DIR` 后，git 由 cwd 向上发现 `.git`（worktree 的 `.git` 是含 `gitdir:` 的文件）
      ⇒ 得到正确的 `<wt>`。`GIT_INDEX_FILE` **必须保留**：它是**本工作树自己的**索引，
      去掉会去读主仓库的索引、看错暂存区。
    """
    env = dict(os.environ)
    for key in _HOOK_ENV_OVERRIDES:
        env.pop(key, None)
    return env


def repo_toplevel(root: Path) -> Path:
    """定位仓库根。**从仓库根跑 git**、并用"相对仓库根"的 pathspec ——
    否则在 `system/` 子目录里跑时 pathspec 会按 cwd 解析，容易悄悄指错对象。

    ★ 必须在**去掉 `GIT_DIR` 的环境**里问（见 `_git_env`）。
    ★ 并**自检** `root/facts` 确实在 `toplevel` 之下：toplevel 若被判成 `system/`，
      下面 `facts_pathspec` 会算出 `facts/*.jsonl`（一个匹配不到东西的相对路径）——
      自检把它变成**响亮的输入异常**，而不是让错误往下传成空放行。
    """
    top = _git(["rev-parse", "--show-toplevel"], root, env=_git_env()).strip()
    if not top:
        raise FileNotFoundError(f"{root}: git 未返回仓库根（不静默放行）")
    toplevel = Path(top).resolve()
    facts = (root / FACTS_DIRNAME).resolve()
    if not facts.is_relative_to(toplevel):
        raise FileNotFoundError(
            f"仓库根判定可疑：{facts} 不在 {toplevel} 之下（pathspec 会指错对象）。"
            "钩子环境的 `GIT_DIR` 会污染 `--show-toplevel`，见 `_git_env` 的说明。"
        )
    return toplevel


def facts_pathspec(root: Path, toplevel: Path) -> str:
    """`facts/*.jsonl` 相对**仓库根**的 pathspec（本仓库里通常是 `system/facts/*.jsonl`）。"""
    facts = (root / FACTS_DIRNAME).resolve()
    rel = facts.relative_to(toplevel.resolve())
    return f"{rel.as_posix()}/*.jsonl"


def count_tracked_matches(toplevel: Path, pathspec: str) -> int:
    """pathspec 匹配到的**被跟踪**文件数 —— 用来把"空 diff"的**两种成因**分开记账。

    ★ 为什么要这个数：`git diff --cached` 对**匹配不到任何路径**的 pathspec 返回空串，
      与"暂存区确实没有 facts 改动"在输出上**一模一样**。所以 `diff_bytes: 0` 有两种成因：

      ① 暂存区真没动 facts（正常，记 `NO_STAGED_FACTS_CHANGES`）；
      ② pathspec 指错对象 / 那些文件根本没被跟踪（**假绿**：守卫对任何输入都放行）。

      不把两者分开，"仓库根判错"这类缺陷就会以「看起来正常的绿」长期存活 ——
      本文件 `_git_env` 记录的 linked worktree 缺陷正是如此（守卫恒报成因 ①）。

    ★ 为什么只**记数 + 记 note** 而不直接判 `exit 2`：
      `tests/guards/test_exit_code_contract.py::test_guard_exits_zero_and_reports_scanned_on_pristine_tree`
      的既定契约是"**干净副本树**上守卫须 `exit 0`"，而副本（`<仓库>/…/_pristine/system`）
      里的 `facts/*.jsonl` 本来就**不在 git 跟踪范围内** —— 那种情形下 `0` 是合法的。
      故这里只把事实**显式记账**；"钩子不得改变仓库根判定"这条由
      `tests/injection/test_append_only.py::test_hook_env_git_dir_does_not_blind_the_guard`
      作**回归绑定**（导出 `GIT_DIR` 后改写既有行必须仍被拦下）。
    """
    tracked = _git(["ls-files", "--", pathspec], toplevel, env=_git_env())
    return len([ln for ln in tracked.splitlines() if ln.strip()])


def staged_facts_diff(toplevel: Path, pathspec: str) -> str:
    """取暂存区里 facts JSONL 的 diff（零上下文行，便于逐行判定）。"""
    return _git(["diff", "--cached", "--unified=0", "--", pathspec], toplevel, env=_git_env())



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
    # ★ 把"空 diff"的两种成因分开记账：真没改 vs pathspec 根本没匹配到东西（假绿）。
    tracked = count_tracked_matches(toplevel, pathspec)

    diff_text = staged_facts_diff(toplevel, pathspec)
    files = [ln.split(" b/", 1)[-1] for ln in diff_text.splitlines() if ln.startswith("diff --git ")]
    report.scanned["pathspec_tracked_files"] = tracked
    report.scanned["staged_facts_files"] = len(files)
    report.scanned["diff_bytes"] = len(diff_text)
    report.notes.append(f"pathspec = {pathspec}（相对仓库根 {toplevel}）")
    if tracked == 0:
        report.notes.append(
            f"PATHSPEC_MATCHES_NOTHING：{pathspec!r} 未匹配到任何**被跟踪**文件 —— "
            "下面的空 diff 不能读作「追加式不可变已验证」，它也可能是**仓库根/pathspec 判错**"
            "（钩子导出的 `GIT_DIR` 曾使 linked worktree 上恒为此形态，见 `_git_env`）"
        )
    # ★ **列出被检文件名**（不只是计数）：pathspec 是 glob，扩表后新表自动落进被检集合 ——
    #   而"扫到了几张、分别是谁"是**可审计**的证据。只报计数时，"新表没被扫到"
    #   与"新表被扫到但恰好无违例"在输出上分辨不出来（`tests/injection/test_append_only.py`
    #   ::test_new_stem_append_passes 断言的正是这条）。
    if files:
        report.notes.append("staged facts files = " + ", ".join(sorted(files)))

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
