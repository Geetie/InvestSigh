"""追加式不可变守卫的注入测试（`Ch9 §3.4.2` · `施工图 §8` 纪律 4）。

**纪律 4：pre-commit 拒改既有行（新增放行）。**

这里必须**真的建一个 git 仓库**来测——diff 语义是 git 的语义，
靠 mock 出来的 diff 文本只能证明"我的解析器认我编的字符串"，
不能证明"真的 `git diff --cached` 会拦下改写"（`§6.3`：mock 掉决策函数再断言行为 = 无效测试）。
"""

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from conftest import SYSTEM_ROOT, WORK_DIR, assert_rejected

GUARD = "scripts/checks/append_only_guard.py"

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "gate-test",
    "GIT_AUTHOR_EMAIL": "gate-test@example.invalid",
    "GIT_COMMITTER_NAME": "gate-test",
    "GIT_COMMITTER_EMAIL": "gate-test@example.invalid",
}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    import os

    env = {**os.environ, **_GIT_ENV}
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=False, env=env
    )


@pytest.fixture()
def git_repo() -> Path:
    """一个带初始提交的临时 git 仓库，内含 `system/facts/*.jsonl`。

    ★ 必须放**两个** facts 文件：`git rm` 会顺带清掉留下的空父目录，
      只放一个文件时删完连 `system/` 都没了，`code_root` 直接不存在（exit 2），
      测不到"删除真源文件"这条规则本身。
    """
    repo = WORK_DIR / f"append-only-{uuid.uuid4().hex[:8]}"
    facts = repo / "system" / "facts"
    facts.mkdir(parents=True)
    (facts / "industry_nodes.jsonl").write_text(
        '{"node_id":"node_a","node_name":"A"}\n{"node_id":"node_b","node_name":"B"}\n',
        encoding="utf-8",
    )
    (facts / "tasks.jsonl").write_text('{"task_id":"t1"}\n', encoding="utf-8")
    # ★ **扩表（18 → 22）的回归**：`relation_flows` 是本批次新增的表。
    #   守卫的 pathspec 是 `system/facts/*.jsonl`（**glob**），故新文件必须**自动覆盖** ——
    #   下面的 `test_new_stem_*` 两个用例就是这条的实测证据（不靠"看代码觉得应该是"）。
    (facts / "relation_flows.jsonl").write_text(
        '{"flow_id":"F1","relation_id":"R1","flow_kind":"product"}\n'
        '{"flow_id":"F2","relation_id":"R1","flow_kind":"capital"}\n',
        encoding="utf-8",
    )
    _git(repo, "init", "-q")
    _git(repo, "add", "system/facts")
    _git(repo, "commit", "-q", "-m", "seed facts")
    try:
        yield repo
    finally:
        import shutil

        shutil.rmtree(repo, ignore_errors=True)


def _run_guard(repo: Path) -> subprocess.CompletedProcess:
    script = SYSTEM_ROOT / GUARD
    return subprocess.run(
        [sys.executable, str(script), str(repo / "system"), "--no-report"],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_rewriting_existing_line_is_rejected(git_repo: Path) -> None:
    """改写既有行（`-` 出现）→ 必须 exit 1。"""
    target = git_repo / "system" / "facts" / "industry_nodes.jsonl"
    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    lines[0] = '{"node_id":"node_a","node_name":"A-REWRITTEN"}\n'   # 就地改写历史
    target.write_text("".join(lines), encoding="utf-8")
    _git(git_repo, "add", "system/facts/industry_nodes.jsonl")

    assert_rejected(_run_guard(git_repo), rule_hint="纪律 4")


def test_deleting_existing_line_is_rejected(git_repo: Path) -> None:
    """删除既有行 → 必须 exit 1。"""
    target = git_repo / "system" / "facts" / "industry_nodes.jsonl"
    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    target.write_text("".join(lines[1:]), encoding="utf-8")
    _git(git_repo, "add", "system/facts/industry_nodes.jsonl")

    assert_rejected(_run_guard(git_repo), rule_hint="纪律 4")


def test_deleting_the_whole_jsonl_is_rejected(git_repo: Path) -> None:
    """删除整个 JSONL（真源文件）→ 必须 exit 1。"""
    target = git_repo / "system" / "facts" / "industry_nodes.jsonl"
    _git(git_repo, "rm", "-q", "system/facts/industry_nodes.jsonl")
    assert target.exists() is False
    assert_rejected(_run_guard(git_repo), rule_hint="纪律 4")


def test_appending_new_line_passes(git_repo: Path) -> None:
    """**反向对照**：只追加新行 → 必须放行（否则无法修正历史，只能删库）。"""
    target = git_repo / "system" / "facts" / "industry_nodes.jsonl"
    with open(target, "a", encoding="utf-8") as fh:
        fh.write('{"node_id":"node_c","node_name":"C"}\n')
    _git(git_repo, "add", "system/facts/industry_nodes.jsonl")

    proc = _run_guard(git_repo)
    assert proc.returncode == 0, f"纯追加被误拦\n{proc.stdout}\n{proc.stderr}"
    assert "staged_facts_files: 1" in proc.stdout


def test_no_staged_facts_change_passes_with_explicit_note(git_repo: Path) -> None:
    """**反向对照**：暂存区没有 facts 改动 → 放行，但必须**显式说明无被检对象**。"""
    proc = _run_guard(git_repo)
    assert proc.returncode == 0
    assert "NO_STAGED_FACTS_CHANGES" in proc.stdout, "无被检对象时必须显式记 note，不得静默通过"


# ─────────── 扩表（18 → 22）回归：新表**自动**在守卫覆盖范围内（pathspec 是 glob） ───────────


def test_new_stem_append_passes(git_repo: Path) -> None:
    """★ 新增表（`relation_flows`）**追加一行** → 必须放行。

    证的是"扩表不需要改守卫"：pathspec = `system/facts/*.jsonl` 是 glob，
    新文件自动落进被检集合（若哪天有人把它改成逐文件白名单，这条会红）。
    """
    target = git_repo / "system" / "facts" / "relation_flows.jsonl"
    with open(target, "a", encoding="utf-8") as fh:
        fh.write('{"flow_id":"F3","relation_id":"R1","flow_kind":"demand_signal"}\n')
    _git(git_repo, "add", "system/facts/relation_flows.jsonl")

    proc = _run_guard(git_repo)
    assert proc.returncode == 0, f"新表的纯追加被误拦\n{proc.stdout}\n{proc.stderr}"
    assert "staged_facts_files: 1" in proc.stdout
    assert "relation_flows" in proc.stdout, "新表必须出现在被检文件清单里（不是'没被扫到'）"


def test_new_stem_rewrite_is_rejected(git_repo: Path) -> None:
    """★ 新增表里**改写既有行** → 必须 exit 1（新表同样受"追加式不可变"约束）。"""
    target = git_repo / "system" / "facts" / "relation_flows.jsonl"
    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    lines[0] = '{"flow_id":"F1","relation_id":"R1","flow_kind":"product","tampered":true}\n'
    target.write_text("".join(lines), encoding="utf-8")
    _git(git_repo, "add", "system/facts/relation_flows.jsonl")

    assert_rejected(_run_guard(git_repo), rule_hint="纪律 4")


def test_non_git_directory_fails_loudly() -> None:
    """**错误路径**：不在任何 git 仓库里 → 必须 exit 2（输入异常），**不得静默放行**。

    ★ 必须建在**真实仓库之外**：`tests/.work/` 虽然"看起来像临时目录"，但它
      位于 `/Users/gaza/Developer/InvestSigh` 内部，`git rev-parse --show-toplevel`
      照样能找到仓库根 —— 在那里测"非 git 仓库"根本测不到。
    """
    import shutil
    import tempfile

    outside = Path(tempfile.mkdtemp(prefix="nogit-append-only-"))
    try:
        (outside / "facts").mkdir()
        script = SYSTEM_ROOT / GUARD
        proc = subprocess.run(
            [sys.executable, str(script), str(outside), "--no-report"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 2, (
            f"非 git 仓库应报输入异常(2)，实得 {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
        )
        assert "INPUT-ERROR" in (proc.stdout + proc.stderr)
    finally:
        shutil.rmtree(outside, ignore_errors=True)


# ─────────── 回归：钩子环境（`GIT_DIR` 被导出）+ 反空放行绑定 ───────────
#
# ★ 这一节钉的是一个**曾经真实存在的假绿缺陷**（`纪律 4` 的手段在 worktree 上失效）：
#
#   `git` 在**钩子**里把 `GIT_DIR` 导出给子进程。此时**不带** `GIT_WORK_TREE` 的
#   `git rev-parse --show-toplevel` **不查仓库**，直接把 **cwd 当工作树根**返回。
#   本守卫用 `root`（= `<code_root>`，即 `.../system`）作 cwd 去问 toplevel，于是：
#
#   | 仓库形态 | toplevel 被判成 | pathspec | `git diff --cached` 看到 |
#   |---|---|---|---|
#   | 普通仓库（cwd == 仓库根） | 仓库根 | `system/facts/*.jsonl` | ✅ 暂存改动 |
#   | **linked worktree**（cwd == `<wt>/system`） | `<wt>/system` | `facts/*.jsonl` | ❌ **恒为空** |
#
#   ⇒ 在 worktree 里 `git commit` 时守卫**恒报「无被检对象」并 `exit 0`**。
#   实测后果（基点 `bc26933` 与本分支修复前**均复现**）：`git worktree add` 出来的工作树里
#   改写 `facts/dependency_edges.jsonl` 的**既有行** → `git add` → `git commit` **成功**，
#   被改写的行进了版本库，守卫输出 `staged_facts_files: 0` + `RESULT: PASS`。
#
#   而本项目的实际干活方式**就是** `git worktree`（`.worktrees/ws-*`）⇒ 该缺陷让
#   「追加式不可变」**对所有干活的人都没有手段落地**（`CONVENTIONS.md` 的底线 2）。
#
#   两个修法各有对应断言（缺一条都不够）：
#     ① 根因：问 toplevel 时**去掉 `GIT_DIR`**（保留 `GIT_INDEX_FILE`）→ `test_hook_env_git_dir_does_not_blind_the_guard`；
#     ② 记账：把 `pathspec_tracked_files` 记进 `scanned`，并显式记 `PATHSPEC_MATCHES_NOTHING` note ——
#        因为"pathspec 指错"与"暂存区真没改"在 `git diff` 输出上**完全一样**，
#        只靠 `NO_STAGED_FACTS_CHANGES` 一条 note 是抓不住的（该缺陷能存活很久正是因为它看起来正常）。
#        （② 不判 `exit 2`：干净**副本树**上 `facts/*.jsonl` 本就不在跟踪范围内，
#          而 `test_guard_exits_zero_and_reports_scanned_on_pristine_tree` 的既定契约要求那种情形 `exit 0`。）

def test_hook_env_git_dir_does_not_blind_the_guard(git_repo: Path) -> None:
    """★ 钩子环境回归：`GIT_DIR`/`GIT_INDEX_FILE` 被导出时，**改写既有行仍必须拦下**。

    `GIT_DIR` 指向 `<repo>/.git` 且不设 `GIT_WORK_TREE` —— 这正是钩子里的形态，
    也是"toplevel 被判成 cwd"的触发条件。
    """
    import os

    target = git_repo / "system" / "facts" / "industry_nodes.jsonl"
    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    target.write_text("".join(lines[1:]), encoding="utf-8")        # 删掉既有行
    _git(git_repo, "add", "system/facts/industry_nodes.jsonl")

    env = {
        **os.environ,
        **_GIT_ENV,
        "GIT_DIR": str(git_repo / ".git"),
        "GIT_INDEX_FILE": str(git_repo / ".git" / "index"),
    }
    proc = subprocess.run(
        [sys.executable, str(SYSTEM_ROOT / GUARD), str(git_repo / "system"), "--no-report"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert proc.returncode == 1, (
        "导出 GIT_DIR 时守卫失明（空放行）—— 这正是 linked worktree 上的失效形态；"
        "根因与修法见本节顶部注释\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "staged_facts_files: 1" in proc.stdout, (
        f"守卫必须**看见**这一处暂存改动，而不是报「无被检对象」\n{proc.stdout}"
    )


def test_empty_diff_causes_are_distinguishable() -> None:
    """★ 把"空 diff"的**两种成因**分开：真没改 vs pathspec 根本没匹配到东西（假绿）。

    `git diff --cached` 对**匹配不到任何路径**的 pathspec 返回空串，与"暂存区确实没有
    facts 改动"在输出上**一模一样**。不区分二者，"仓库根判错 / pathspec 拼错"就会以
    「看起来正常的绿」长期存活 —— 上面那个 linked worktree 缺陷就是这样活下来的。
    故守卫必须把 `pathspec_tracked_files` **记进 scanned**：成因 ② 的 `0` 与成因 ① 的
    `diff_bytes: 0` 必须能一眼分开。

    本用例造一个**真 git 仓库**，但 `facts/*.jsonl` 不在跟踪范围内 → 期望：
    `pathspec_tracked_files: 0` + `PATHSPEC_MATCHES_NOTHING` note（而**不是**默默一绿）。
    """
    import shutil

    repo = WORK_DIR / f"append-only-untracked-{uuid.uuid4().hex[:8]}"
    try:
        (repo / "system" / "facts").mkdir(parents=True)
        (repo / "system" / "facts" / "industry_nodes.jsonl").write_text("", encoding="utf-8")
        (repo / "system" / "README.md").write_text("x\n", encoding="utf-8")
        _git(repo, "init", "-q")
        _git(repo, "add", "system/README.md")          # 只跟踪 facts/ 之外的文件
        _git(repo, "commit", "-q", "-m", "no facts tracked")

        proc = subprocess.run(
            [sys.executable, str(SYSTEM_ROOT / GUARD), str(repo / "system"), "--no-report"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, (          # 契约：干净副本树须 exit 0（见 `count_tracked_matches`）
            f"非空 diff 之外的情形应放行（成因如实记账即可）\n{proc.stdout}\n{proc.stderr}"
        )
        assert "pathspec_tracked_files: 0" in proc.stdout, (
            f"`pathspec_tracked_files` 必须出现在 scanned 里 —— 否则两种成因分不开\n{proc.stdout}"
        )
        assert "PATHSPEC_MATCHES_NOTHING" in proc.stdout, (
            f"成因 ② 必须显式记 note，不得与「暂存区真没改」混同\n{proc.stdout}"
        )
    finally:
        shutil.rmtree(repo, ignore_errors=True)

