"""夹具**排他会话锁**的回归测试（缺口 `G-RC-10` 的机器绑定）。

## 为什么需要这条锁（实测踩到，不是假想）

`conftest.pytest_sessionstart` 会 `_clear_work_dir()` —— 它**清空整个 `system/tests/.work/`**。
若**同一个工作树**里同时有两个 pytest 会话，**后启动的那个**会把先启动者正在用的
**夹具副本删掉** ⇒ 症状是"副本里应有的文件凭空消失"，且**随机落在不同用例上**。

实测：同一轮内跑 `tests/guards` 三次，三次结果互不相同，全是 `FileNotFoundError` 且位置漂移
（`ps` 佐证当时有多个 pytest 会话并发，其中两个在同一工作树）。这正是
`CONVENTIONS.md::V-05`「两个 pytest 会话禁止并发：必然互删夹具」禁止的情形。

★ 危害在于**它必然产出假红**，而假红会被读成"守卫坏了 / 改动改坏了"——
本项目的假缺陷已经淹没过真违规好几次。故本条判据的目的不是"跑得更好"，
而是**把静默互删变成响亮、可行动的报错**。

## 三个分支（缺一不可）

| 分支 | 期望 |
|---|---|
| 无锁 | 取锁成功，锁内容 = 自己的 pid；释放后锁消失 |
| **锁被活着的会话持有** | **必须 `RuntimeError`**，且消息含 `V-05` 与处置建议（**不得**继续去清目录） |
| 锁的持有者已不存在（陈旧） | **必须接管**（不抛错）—— **不得因一次崩溃就永久锁死本工作树** |

★ 本用例用 `monkeypatch` 把 `WORK_DIR` 指到独立子目录，**不碰**当前会话真正持有的锁
（否则会把正在跑的这次会话的锁删掉 —— 那本身就是一次自伤）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

import conftest
from conftest import SYSTEM_ROOT


@pytest.fixture()
def isolated_work_dir(monkeypatch: pytest.MonkeyPatch) -> Path:
    """把 `conftest.WORK_DIR` 指到一个独立子目录（用完删除）。"""
    # ★ 目录必须落在**工作区内**：工作区外的 mkdir 走宿主 broker 会抛 PermissionError。
    target = SYSTEM_ROOT / "tests" / ".work" / f"_locktest-{uuid.uuid4().hex[:8]}"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(conftest, "WORK_DIR", target)
    monkeypatch.setattr(conftest, "_SESSION_LOCK", target / ".session.lock")
    try:
        yield target
    finally:
        shutil.rmtree(target, ignore_errors=True)


def _dead_pid() -> int:
    """返回一个**确定已退出**的 pid（起一个子进程并等它结束）。

    ★ 不用"很大的数"充当死 pid：macOS 上超出范围的 pid 会让 `os.kill(pid, 0)` 抛
      `ERANGE`（而非 `ProcessLookupError`），而 `_pid_alive()` 对其它 `OSError`
      **保守判为存活** ⇒ 前置条件会不成立、用例假红。
      "起一个真进程再等它退出"才是**确定**的死 pid。
    """
    proc = subprocess.Popen([sys.executable, "-c", "pass"])   # noqa: S603
    pid = proc.pid
    proc.wait()
    return pid


def test_lock_acquire_then_release(isolated_work_dir: Path) -> None:
    """无锁 → 取锁成功（锁内容 = 自己的 pid）→ 释放后锁消失。"""
    lock = conftest._SESSION_LOCK
    assert not lock.exists()

    conftest._acquire_session_lock()
    assert lock.exists(), "取锁后锁文件必须存在（否则这条绑定是空的）"
    assert lock.read_text(encoding="utf-8").strip() == str(os.getpid()), "锁必须记下持有者 pid"

    conftest._release_session_lock()
    assert not lock.exists(), "释放后锁必须消失"


def test_lock_rejects_live_concurrent_session(isolated_work_dir: Path) -> None:
    """★ 锁被**活着的**会话持有 → 必须**响亮失败**，且消息可行动。

    ★ 占用者必须是**另一个真活着的进程**（`os.getpid()` 不行 —— 那会命中"同进程重复取锁
      幂等"分支，见下一条用例）。这里起一个真实子进程充当"另一个仍在跑的会话"。
    """
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])  # noqa: S603
    try:
        assert other.pid != os.getpid(), "前置条件不成立：子进程 pid 竟与本进程相同"
        conftest._SESSION_LOCK.write_text(str(other.pid), encoding="utf-8")

        # ★ 用的是 `pytest.exit`（抛 `Exit`）而**不是** `RuntimeError`：后者会走成
        #   `INTERNALERROR` + 堆栈，容易被误读成"pytest 自己坏了"（见 `_acquire_session_lock` 注释）。
        with pytest.raises(pytest.exit.Exception) as exc:
            conftest._acquire_session_lock()

        msg = str(getattr(exc.value, "msg", "") or exc.value)
        assert "V-05" in msg, f"报错必须点出禁令编号（否则读者不知道该查哪条规范）：{msg}"
        assert "worktree" in msg, f"报错必须给出**可行动的处置**（换 worktree / 等它结束）：{msg}"
        assert str(other.pid) in msg, f"报错必须指出占用者 pid（便于人工核对）：{msg}"
        assert getattr(exc.value, "returncode", None) == 4, (
            "退出码必须与 0/1/2/3/124 区分开，便于在批次输出里一眼认出"
        )
    finally:
        other.kill()
        other.wait()


def test_lock_is_idempotent_for_same_pid(isolated_work_dir: Path) -> None:
    """★ **同进程重复取锁必须幂等**（实测踩到，务必保留）。

    背景：`pytest_sessionstart` 在**同一个进程**里可能被触发不止一次
    （实测 `pytest <fileA> <fileB>` 触发了两次）。若不做短路，第二次会把自己**刚写的**
    锁当成"别人的"而**拒绝启动自己** —— 报错里 pid 与当前进程相同，
    **极易被误读成"环境里真有别的会话"**（我这次就是这么被绊了一下）。
    """
    conftest._SESSION_LOCK.write_text(str(os.getpid()), encoding="utf-8")

    conftest._acquire_session_lock()          # 必须安静通过，不得抛错

    assert conftest._SESSION_LOCK.exists(), "幂等分支不得把锁删掉"


def test_lock_takes_over_when_holder_is_dead(isolated_work_dir: Path) -> None:
    """★ 持有者已不存在（陈旧锁）→ **必须接管**，不得永久锁死本工作树。

    用 `_dead_pid()` 构造**确定已退出**的 pid（不用大数硬凑，理由见该函数 docstring）。
    """
    stale_pid = _dead_pid()
    assert not conftest._pid_alive(stale_pid), "前置条件不成立：该 pid 竟被判为存活"

    conftest._SESSION_LOCK.write_text(str(stale_pid), encoding="utf-8")
    conftest._acquire_session_lock()          # 不得抛错
    assert conftest._SESSION_LOCK.read_text(encoding="utf-8").strip() == str(os.getpid()), (
        "陈旧锁必须被接管（锁内容改成本会话的 pid）"
    )


def test_release_does_not_remove_another_sessions_lock(isolated_work_dir: Path) -> None:
    """释放**只删自己持有的锁**：若锁已被他人接管，不得误删对方的锁。"""
    conftest._SESSION_LOCK.write_text("999999999", encoding="utf-8")
    conftest._release_session_lock()
    assert conftest._SESSION_LOCK.exists(), "误删了他人持有的锁 —— 会让并发保护失效"
