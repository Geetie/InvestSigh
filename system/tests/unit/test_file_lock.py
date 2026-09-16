"""`schema/store.py::_file_lock` 的跨平台锁语义（`Ch9 §3.10 J6` · 纪律 9）。

★ **本文件存在的唯一理由**：`_file_lock` 原先在模块级 `import fcntl`，
  Windows 上直接 `ModuleNotFoundError` ⇒ **全仓 ImportError**（不是测试坏了，
  是整条验证链路跑不起来）。修法是**按平台分支**：Unix 走 `fcntl.flock`
  （**建议锁**）、Windows 走 `msvcrt.locking`（**强制锁**）。

★ **两条分支的语义并不等价**，故本文件对**当前平台**做**运行时效果断言**
  （`CONVENTIONS.md §四 R-06 ⑥`：首选运行时效果断言，而非静态形式匹配）；
  对**另一侧分支**只做"该分支仍在源码里"的结构断言 —— 后者**不得**被引用为
  "该侧行为已验证"（`R-06 ④` 的措辞剥离义务）。

★ **正反向成对**（`CONVENTIONS.md §二 G-05`）：每条"拦得住"都配一条"不误伤"。

| # | 正向（必须成立） | 反向对照（不得误伤 / 不得静默） |
|---|---|---|
| 1 | 持锁期间他人**取不到** | 释放后他人**必然可取**（不永久锁死） |
| 2 | 取锁→写入→释放 正常往返 | 锁体内抛异常 → 异常**照常上抛**且锁**仍被释放** |
| 3 | 未知平台 → **响亮失败** | 两个已支持平台 → **不**抛（不得误伤） |
| 4 | 空 `records` → 返回 0 | 空 `records` **不得**建锁文件、不得建真源文件 |

★★ **总闸门（反向对照的根）**：`test_lock_is_exclusive_across_processes` ——
  一旦有人把 `_acquire_exclusive` 改成 `pass`，或改成被否决的
  「`fcntl` shim ⇒ Windows 上退化为无操作」，**该用例立刻变红**。
  它是"锁不是无操作"这一条的**唯一运行时证据来源**。
"""

from __future__ import annotations

import ast
import inspect
import os
import subprocess
import sys
import textwrap
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

from schema import models as M
from schema import store as S
from schema.store import _file_lock, append_records, read_records

SYSTEM_ROOT = Path(__file__).resolve().parents[2]          # .../InvestSigh/system
TESTS_DIR = Path(__file__).resolve().parents[1]            # .../InvestSigh/system/tests

# ★ 夹具工作区刻意落在**工作区内**的 `tests/.work/`（同 `tests/conftest.py` 的取舍）：
#   工作区之外的 `mkdir` 在 broker 打开时会抛 `EEXIST` 而非 `FileExistsError`。
_LOCK_WORK = TESTS_DIR / ".work" / "file_lock"

_HOLD_SECONDS = "3.0"

# 子进程：持锁 `_HOLD_SECONDS` 秒。用**真的子进程**（不是线程）才能证明
# 「跨进程排他」—— 同进程内的锁没有意义（本项目要防的是**两个写入者进程**）。
_HOLD_CHILD = """
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import schema.store as s
# ★ `_file_lock` 的 `root` 形参是 `Path`（`append_records` 内部先 `Path(code_root)` 再传进来），
#   故此处必须自己转 —— 直接把 `str` 传进去会在 `root / "index"` 处抛 TypeError。
with s._file_lock(Path(sys.argv[2]), sys.argv[3]):
    print("LOCKED", flush=True)
    time.sleep(float(sys.argv[4]))
print("RELEASED", flush=True)
"""


@pytest.fixture()
def lock_root(request: pytest.FixtureRequest) -> Path:
    """一个干净的 `code_root`（只需目录结构，不复制整个 `system/`）。

    ★ 刻意**不**在用例结尾 `rmtree`：交给 `pytest_sessionfinish::_clear_work_dir`
      统一清（`CONVENTIONS.md §一 V-09`：删除按**调用次数**计费，能省一次是一次）。
    """
    target = _LOCK_WORK / request.node.name
    (target / "facts").mkdir(parents=True, exist_ok=True)
    return target


def _lock_file(root: Path, stem: str) -> Path:
    return root / "index" / ".locks" / f"{stem}.lock"


def _try_acquire_nowait(root: Path, stem: str) -> bool:
    """**非阻塞**试取同一把锁，返回是否取到。

    ★ 刻意**不复用**生产侧的 `_acquire_exclusive`：探针若与被测实现同源，
      "实现写错了"会被"探针用同一种错法"掩盖（`CONVENTIONS.md §四 V-11` 仪器轴）。
      故这里按 `LOCK_BACKEND` **独立**实现一次非阻塞取锁。
    """
    lock_path = _lock_file(root, stem)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    got = False
    try:
        if S.LOCK_BACKEND == "fcntl":
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, S._LOCK_NBYTES)
        got = True
        return True
    except OSError:
        return False
    finally:
        if got:
            if S.LOCK_BACKEND == "fcntl":
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
            else:
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, S._LOCK_NBYTES)
        os.close(fd)


def _node(node_id: str) -> M.IndustryNode:
    now = datetime.now(timezone.utc)
    return M.IndustryNode(
        node_id=node_id,
        node_name="TEST",
        taxonomy_version="appendix1_v7",
        occurred_at=datetime.fromisoformat("2026-09-08T00:00:00+00:00"),
        published_at=None,
        effective_from=None,
        first_seen_at=now,
        analyzed_at=now,
        recorded_seq=1,
        backfilled_at=now,
    )


# ───────────────────── 0. 后端选择（`AC-06` 边界） ─────────────────────

def test_backend_is_a_real_backend_matching_the_platform() -> None:
    """正向（`AC-06`）：`LOCK_BACKEND` 必须是两个**真**后端之一，且与实际平台一致。"""
    assert S.LOCK_BACKEND in {"fcntl", "msvcrt"}
    assert S.LOCK_BACKEND == ("msvcrt" if os.name == "nt" else "fcntl")


def test_unknown_platform_fails_loudly_instead_of_silently_unlocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正向（`AC-06` 边界）：未知平台 → **抛异常**，不得静默退化为"无锁"。

    ★ 为什么**能**测：见 `_select_lock_backend` 的 docstring —— 写成模块级内联
      `if/elif/else` 时这条分支**不可测**（`pathlib` 会先抛
      `RuntimeError: cannot instantiate 'PosixPath' on your system`，守卫轮不到执行，实测）。
      抽成函数后测试可**直接调用**，该分支才真的被测到。
    """
    monkeypatch.setattr(os, "name", "plan9", raising=True)
    with pytest.raises(RuntimeError, match="不支持的平台"):
        S._select_lock_backend()


@pytest.mark.parametrize("fake_name", ["nt", "posix"])
def test_supported_platforms_are_not_falsely_rejected(
    monkeypatch: pytest.MonkeyPatch, fake_name: str,
) -> None:
    """**反向对照**（`G-05`）：两个已支持平台**不得**被误伤成"不支持"。"""
    monkeypatch.setattr(os, "name", fake_name, raising=True)
    assert S._select_lock_backend() == ("msvcrt" if fake_name == "nt" else "fcntl")


def test_both_backend_branches_still_exist_in_source() -> None:
    """结构断言（**不是**运行时证据）：两条分支都还在源码里，没被删掉一侧。

    ★ 措辞剥离（`CONVENTIONS.md §四 R-06 ④`）：本条**只能**证明"代码里还有这条分支"，
      **不得**被引用为"另一侧平台的行为已验证" —— 那需要真的在那侧平台上跑一次。
    """
    src = inspect.getsource(S._acquire_exclusive) + inspect.getsource(S._release_exclusive)
    assert "fcntl.flock" in src, "Unix 分支（`fcntl.flock`）被删掉了"
    assert "msvcrt.locking" in src, "Windows 分支（`msvcrt.locking`）被删掉了"


# ───────────────────── 1. 真接线（`AC-03`） ─────────────────────

def test_append_records_really_takes_the_lock(lock_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """真接线（`AC-03`）：`append_records` 运行时**真的**进了 `_file_lock`。

    ★ 为什么用 spy 而**不是**只读源码：`G-02` 要求函数体级绑定；而运行时 spy
      比 AST 更强 —— 它证明**这条代码路径真的走到了**，不是"源码里写了但没被调用"。
    """
    seen: list[tuple[Path, str]] = []
    real = S._file_lock

    @contextmanager
    def spy(root: Path, stem: str):  # type: ignore[no-untyped-def]
        seen.append((Path(root), stem))
        with real(root, stem):
            yield

    monkeypatch.setattr(S, "_file_lock", spy)
    assert append_records(lock_root, "industry_nodes", [_node("node_lock_1")]) == 1
    assert seen == [(lock_root, "industry_nodes")], "append_records 没有走 `_file_lock`"


def test_append_records_body_calls_the_lock_not_just_mentions_it() -> None:
    """真接线（`AC-03`，`G-02` 形态）：`append_records` **函数体内**真的**调用**了 `_file_lock`。

    ★ 为什么是 AST 而不是全文件字符串匹配：`G-02` 明令禁止后者
      （"一行数据即可绕过"）。本条只解析 `append_records` 自己的源码。
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(append_records)))
    called = {
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "_file_lock" in called, "`append_records` 函数体里没有 `_file_lock(...)` 调用"


def test_read_records_does_not_take_the_lock() -> None:
    """**反向对照**（`G-05`）：读路径**不**取锁 —— 否则上面两条会退化成恒真。

    （若"取锁"的判据在只读函数上也成立，那它就没在测任何东西。）
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(read_records)))
    called = {
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "_file_lock" not in called, "`read_records` 不该取写锁"


# ───────────────────── 2. 正常往返 + 释放后可重取 ─────────────────────

def test_acquire_write_release_roundtrip(lock_root: Path) -> None:
    """正向（`AC-04` ①）：写入口取锁 → 写入 → 释放；数据真的落盘。

    ★ 刻意**不**在外面再套一层 `_file_lock`：嵌套取同一把锁在**两个平台上都会自锁**
      （Unix：`flock` 新 fd 互斥；Windows：强制锁同进程不同 fd 也互斥，实测
      `PermissionError(13)`）。本用例走的是**真实写入口** `append_records`。
    """
    assert append_records(lock_root, "industry_nodes", [_node("node_lock_1")]) == 1
    assert [r["node_id"] for r in read_records(lock_root, "industry_nodes")] == ["node_lock_1"]
    # 锁文件落在 `index/.locks/`（**非真源目录**），不得污染 `facts/`
    assert _lock_file(lock_root, "industry_nodes").exists()
    assert not (lock_root / "facts" / "industry_nodes.lock").exists()


def test_after_release_another_acquirer_succeeds(lock_root: Path) -> None:
    """**反向对照**（`AC-05` ①）：释放后**必然**可取 —— 锁不得把文件永久锁死。"""
    with _file_lock(lock_root, "claims"):
        pass
    assert _try_acquire_nowait(lock_root, "claims") is True, (
        "锁释放后他人仍取不到 ⇒ 文件被永久锁死（异常路径没释放 / 没解锁就关 fd）"
    )


# ───────────────────── 3. 跨进程排他（核心，`AC-04`） ─────────────────────

def test_lock_is_exclusive_across_processes(lock_root: Path) -> None:
    """正向（`AC-04`）：子进程持锁期间，本进程**必然**取不到；释放后**必然**可取。

    这是"锁真的上锁了（不是无操作）"的**唯一运行时证据** ——
    被否决的方案（`fcntl` shim 让 Windows 退化为无操作）会让本条**立刻变红**。

    顺带断言两条分支各自的**平台语义**（`AC-06` ①）：
    Windows = 强制锁（不调 `locking` 的普通读**也被拒**）；
    Unix = 建议锁（普通读**不被拒**）。
    """
    stem = "industry_nodes"
    content = b"0123456789"
    # 锁文件先有内容：空文件上"读被拒"与"读了个空"不可区分（`G-62`），
    # 必须让"读"真的碰到被锁的那个字节区间。
    _lock_file(lock_root, stem).parent.mkdir(parents=True, exist_ok=True)
    _lock_file(lock_root, stem).write_bytes(content)

    proc = subprocess.Popen(
        [sys.executable, "-c", _HOLD_CHILD, str(SYSTEM_ROOT), str(lock_root), stem, _HOLD_SECONDS],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        first = proc.stdout.readline().strip()
        assert first == "LOCKED", f"子进程没打上锁就继续了，输出={first!r}"

        # ① 正向：持锁期间**取不到**
        assert _try_acquire_nowait(lock_root, stem) is False, (
            "持锁期间第二个进程仍取到了锁 ⇒ 锁没有真的排他（可能是无操作降级）"
        )

        # ② 平台语义
        if S.LOCK_BACKEND == "msvcrt":
            with pytest.raises(OSError):
                _lock_file(lock_root, stem).read_bytes()      # 强制锁：普通读也被拒
        else:
            assert _lock_file(lock_root, stem).read_bytes() == content, (
                "Unix 侧是**建议锁**：不调用 flock 的普通读**不应**被拒（被拒 = 语义写错）"
            )
    finally:
        proc.wait(timeout=30)

    # ③ 反向：释放后**必然**可取
    assert _try_acquire_nowait(lock_root, stem) is True, "子进程退出后锁仍未被释放"
    # ④ **控制组**（`V-10`）：同一条读命令在**无锁**时必须成功 ——
    #    否则"读被拒"可能只是路径/权限本身的问题，而不是锁生效。
    assert _lock_file(lock_root, stem).read_bytes() == content


# ───────────────────── 4. 异常路径：锁必须仍被释放（`AC-05`） ─────────────────────

def test_exception_inside_lock_body_still_releases_the_lock(lock_root: Path) -> None:
    """正向（`AC-05` ②）：锁体内抛异常 → 异常**照常上抛**（不吞）+ 锁**仍被释放**。"""
    with pytest.raises(RuntimeError, match="boom"):
        with _file_lock(lock_root, "claims"):
            raise RuntimeError("boom")
    assert _try_acquire_nowait(lock_root, "claims") is True, (
        "异常路径没有释放锁 ⇒ 一次失败会把真源**永久锁死**"
    )


def test_append_records_releases_the_lock_when_write_fails(lock_root: Path) -> None:
    """正向（`AC-05` ② 端到端）：`append_records` 在**持锁期间**写入失败 →
    异常上抛，且锁**仍被释放**（走**真实写入口**，不是只测 `_file_lock`）。

    ★ 制造失败的手法**跨平台一致**：把 `facts/<stem>.jsonl` 换成一个**目录**，
      `open(path, "a")` 在两个平台上都抛 `OSError`（不依赖权限位、也不依赖是否 root）。
    """
    (lock_root / "facts").mkdir(parents=True, exist_ok=True)
    (lock_root / "facts" / "industry_nodes.jsonl").mkdir()   # 让它无法被 open("a")

    with pytest.raises(OSError):
        append_records(lock_root, "industry_nodes", [_node("node_x")])

    assert _try_acquire_nowait(lock_root, "industry_nodes") is True, (
        "写入失败后锁没释放 ⇒ 一次失败会阻塞此后**所有**写入"
    )


def test_acquire_failure_is_not_masked_by_an_unlock_error(
    lock_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正向（`AC-05`）：取锁**失败**时，`finally` **不得**再解锁去**掩盖**真正的原因。

    判据：传播出来的是**取锁**的 `OSError`，而不是解锁抛的异常；
    且 `_release_exclusive` **一次都没被调用**（`held` 标志的作用）。
    """
    unlock_calls: list[int] = []

    def _acquire_always_fails(fd: int) -> None:
        raise OSError("cannot lock (injected)")

    def _unlock_would_explode(fd: int) -> None:
        unlock_calls.append(fd)
        raise RuntimeError("unlock exploded (injected)")

    monkeypatch.setattr(S, "_acquire_exclusive", _acquire_always_fails)
    monkeypatch.setattr(S, "_release_exclusive", _unlock_would_explode)

    with pytest.raises(OSError, match="cannot lock"):
        with _file_lock(lock_root, "claims"):
            pass

    assert unlock_calls == [], (
        "取锁失败后仍调用了解锁 ⇒ 真正的原因会被解锁异常**掩盖**（`G-62` 同族）"
    )


# ───────────────────── 5. 边界：空写入（`AC-06` ③） ─────────────────────

def test_empty_records_takes_no_lock_and_creates_nothing(lock_root: Path) -> None:
    """边界（`AC-06` ③）：空 `records` → 返回 0，**不取锁、不建锁文件、不建真源文件**。"""
    assert append_records(lock_root, "industry_nodes", []) == 0
    assert not _lock_file(lock_root, "industry_nodes").exists(), "空写入不该建锁文件"
    assert not (lock_root / "facts" / "industry_nodes.jsonl").exists(), "空写入不该建真源文件"
