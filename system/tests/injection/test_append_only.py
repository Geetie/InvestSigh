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
