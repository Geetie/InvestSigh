"""测试夹具（`00_开发Agent开工提示词 §三 tests/` / `§5.1 AC-04`）。

两条设计原则：

1. **真代码 + 污染数据**：检查器一律跑**仓库里的真实脚本**（不是副本），
   只把 `code_root` 指向 `tmp_path` 的**副本**。这样测的是真实实现，
   不会被"复制出来的旧代码"骗过。
2. **子进程级断言**：断言的是**进程退出码**，不是"函数返回了违例列表"。
   `§5.1 AC-04` 要求"注入一个违例 → 检查器 **exit 1**（**不是 warn**）"——
   只有真跑进程才能证明 CLI 出口没把 1 吞成 0。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

SYSTEM_ROOT = Path(__file__).resolve().parents[1]      # .../InvestSigh/system
REPO_ROOT = SYSTEM_ROOT.parent                          # .../InvestSigh
if str(SYSTEM_ROOT) not in sys.path:
    sys.path.insert(0, str(SYSTEM_ROOT))

# ★ 夹具工作目录刻意落在**工作区内**的 `tests/.work/`，不用 pytest 的 `tmp_path`：
#   WorkBuddy 沙箱对工作区**之外**的 `mkdir` 走 broker，目录已存在时抛
#   `PermissionError: EEXIST`（而非 `FileExistsError`），`tmp_path` 因此整体崩掉。
#   放在 `tests/` 下还有两个好处：① `walk_files` 本就跳过点目录；
#   ② `tests/**` 在反占位符扫描里是免扫命名空间。
WORK_DIR = SYSTEM_ROOT / "tests" / ".work"

# session 级：同一 `(脚本, code_root, 参数)` 的结果只算一次（见 `run_gate`）
_GATE_RESULT_CACHE: dict[tuple[str, str, tuple[str, ...]], GateResult] = {}

# 复制夹具时跳过的目录：缓存与**可重建 / 可重算**产物
#   （`index` 可全量重建、`reports` 是运行产物、`derived` 可由 facts/ + method_version 重算）
#
# ★ `derived` 是**批次 11 补的**，缺陷 `G-RC-07`，与 `G-RC-02` **同族**：
#   原先只跳 `index` / `reports`，**不跳 `derived`** → `copytree(SYSTEM_ROOT)` 会把
#   真仓库的 `derived/*.jsonl` 一并复制进夹具。项目早期 `derived/` 恰好是空的
#   （只有 `.gitkeep`），所以这个耦合一直不显形；一旦真有运行写入
#   `derived/compute_gaps.jsonl`，每个夹具就**自带**一份真实缺口记录。
#   这与 `G-RC-02` 的形态逐字相同：**测试的观测量被"仓库里恰好有什么"污染**。
#   `derived` 已定为**非唯一真源**（见 `.gitignore` 的更正注释与
#   `append_only_guard` 的 pathspec = `system/facts/*.jsonl`），
#   故与 `index` / `reports` 同等待遇：**不复制**；`_ENSURE_DIRS` 会把空目录补回来。
# ★ `state.json` 是**文件**（不是目录）—— `_ignore()` 对 `names` 里的目录与文件一并过滤，
#   故同一个集合即可覆盖。这是**批次 11 补的**，缺口 `G-RC-07` 的**文件版**，机理逐字相同：
#   `copytree` 复制的是**磁盘上的一切**（不只是被 git 跟踪的东西），而 `state.json`
#   在 `.gitignore` 里却**存在于磁盘**（实测 9 KB，含真仓库的 `run_2026-09-16_full` 历史）。
#   原先只列目录 ⇒ 每个夹具副本都继承了真仓库的**运行态游标** ⇒
#   `Pipeline._read_state()` / `resume()` 会去**续跑真仓库的那一次运行** ⇒
#   "测试的观测量取决于真仓库当前恰好跑过什么"。这正是 `G-RC-02` / `G-RC-07` 的同一形态。
_COPY_SKIP = {
    "__pycache__", ".pytest_cache", ".venv", ".work", "index", "reports", "derived", ".locks",
    "state.json",
}
# 阶段① 内必然为空的目录，夹具里补出来供注入测试写入
_ENSURE_DIRS = ("views", "raw", "derived", "snapshots", "index")

# ★★ 夹具的**真源契约**：每个 `code_root` 一律从**空真源**起步。
#
# 为什么必须显式做这件事（实测，批次 8 `G-RC-02`）：
#   夹具用 `copytree(SYSTEM_ROOT, ...)` 复制整个 `system/` —— **包括 `facts/` 与 `raw/`**。
#   项目此前从没有过真实数据，所以"复制过来也等于空"，这个耦合一直没被发现。
#   一旦 `ws/real-collect` 落入第一批**真实** claim / 边 / 基线，立刻炸出：
#     `tests/claim` 8 failed · `tests/graph` 5 failed · `tests/validators` 2 failed。
#   根因不是数据错、也不是代码错，而是**测试侧契约没随真源演进**：
#   `test_locator_check` 断言 `NO_CLAIMS`、`test_graph_integrity_guard` 断言 `NO_EDGE_DATA` ——
#   这些用例要测的是"**无被检对象**"这一分支，可它们却**依赖仓库里恰好没有数据**。
#
# 正确契约 = **测试自己声明自己的数据**：夹具给空真源，需要的用例自行 `append_records` 写入。
# 这样"仓库里有没有真实数据"与"测试是否通过"**彻底解耦**（这也是能让真实数据进主线的前提）。
#
# ★★ **这张清单不得手工维护**（`G-RC-02` / `G-RC-07` 的**同一族缺陷**，本项目已栽 4 次）：
#   若将来有人加了第 23 张表而忘了改这里，夹具清空真源时就会**漏掉那张表** ⇒
#   测试又会依赖"真仓库恰好有什么"。故本清单**直接派生**自 `schema/stems.py::JSONL_STEMS`
#   （stem 的唯一真源）；而 `schema/models.py` 在导入时断言 `JSONL_MODELS` 的键集合
#   与它**逐一相等** ⇒ 三处不可能漂移。
#   `tests/unit/test_schema_expand.py` 另有显式断言（含 `JSONL_MODELS` 的集合相等），
#   使"漂移"以**可读的失败**呈现，而不是只在某个夹具里安静地少清一个文件。
#
# ★ 为什么是 `schema.stems` 而**不是** `schema.models`：后者要构造 pydantic 模型，
#   实测首次导入 ≈1.2s，而本文件**每个 pytest 批次都会加载**（最轻的 `conflict` 批仅 0.3s）。
#   清单的**内容**与 pydantic 无关，故放进 `stems.py`（导入 ≈0ms）。
from schema.stems import JSONL_STEMS  # noqa: E402

_TRUTH_STEMS: tuple[str, ...] = tuple(JSONL_STEMS)


def _reset_truth_source(target: Path) -> None:
    """把夹具副本的**真源**清空：`facts/*.jsonl` 归零、`raw/` 只留 `.gitkeep`。

    只动**数据**，不动**结构**：22 个 JSONL 仍然全部存在（`Ch9 §3.3.3`「不得增删改名」的断言照旧可测），
    `raw/` 目录仍在（`full_text_read` 的路径可写）。
    """
    facts = target / "facts"
    if facts.is_dir():
        for stem in _TRUTH_STEMS:
            (facts / f"{stem}.jsonl").write_text("", encoding="utf-8")
    raw = target / "raw"
    if raw.is_dir():
        for item in list(raw.iterdir()):
            if item.name == ".gitkeep":
                continue
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)


def _ignore(_dir: str, names: list[str]) -> set[str]:
    """跳过缓存 / 可重建产物 / 夹具自身的工作目录（否则递归复制自己）。"""
    return {n for n in names if n in _COPY_SKIP or n.startswith(".")}


def _make_writable(target: Path) -> None:
    """把副本整体改成可写。

    ★ 必须做：`rules/**` 在真仓库里是 **0444**（纪律 9/10），而注入测试
      需要**改写规则文件**来制造违例。`copytree` 会继承源权限，不改就
      "注入"不进去，测试会以 `PermissionError` 崩掉而不是断言门禁生效。
      真仓库的 0444 由 `scripts/checks/rules_lock_guard.py` 单独验证
      （该测试会**显式**把权限改回 0444）。
    """
    for path in target.rglob("*"):
        try:
            if path.is_dir():
                path.chmod(0o755)
            else:
                path.chmod(0o644)
        except OSError:
            continue


@pytest.fixture(scope="session")
def _empty_truth_template() -> Path:
    """**已废弃，不再使用**（保留仅为记录一次失败的优化尝试）。

    ★ 为什么不用的（实测教训）：本意是把"清空真源"从每例路径挪出去以省时。
      但宿主对**单次批量删除**有数量阈值（实测消息 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`,
      `threshold: 9999`, `scope: "turn"`）—— 该策略**按 turn 施加，子进程环境变量关不掉**
      （`verify.py::_child_env()` 已把两个 `CODEBUDDY_*` 置 0 仍无效）。
      会话收尾时删除该模板被**宿主拒绝** → 模板残留并**异常膨胀到 8 万+ 项** →
      下一轮 `pytest_sessionstart` 的清理判"删不干净"→ **响亮抛错 → 整批在 1s 内红**
      （症状：`unit` 批 0.84s 就报错，而 `run_pytest.sh` 单跑却是绿的）。

    → **结论：夹具不得依赖"大目录的一次性批量删除"**。回到"每例独立副本"这条朴素路径；
      性能问题另找办法（例如减少每例需要清空的文件数），**不靠引入一个巨型共享目录**。
    """
    return WORK_DIR / "_template_DEPRECATED_UNUSED"


@pytest.fixture()
def code_root(request: pytest.FixtureRequest) -> Path:
    """一份干净的 `system/` 副本（每个测试一份，互不污染，用完即删）。

    ★ 契约：**真源为空**（见 `_reset_truth_source`）—— 测试必须自己声明自己的数据，
      不得依赖"仓库里恰好有什么"（缺口 `G-RC-02`）。
    """
    target = WORK_DIR / f"{request.node.name}-{uuid.uuid4().hex[:8]}" / "system"
    try:
        shutil.copytree(SYSTEM_ROOT, target, ignore=_ignore)
        for sub in _ENSURE_DIRS:
            (target / sub).mkdir(parents=True, exist_ok=True)
        _make_writable(target)
        # 必须放在 `_make_writable` **之后**：否则清空动作会在 0444 的 `raw/` 子项上抛 `PermissionError`。
        _reset_truth_source(target)
        yield target
    finally:
        shutil.rmtree(target.parent, ignore_errors=True)


def _lock_rules_perms(target: Path) -> None:
    """把副本的 `rules/**` 复原为 `0444`（纪律 9 的不变量）。

    ★ 为什么必须做：`_make_writable()` 把整个副本改成 0644（因为**注入测试需要可写**），
      但 `rules/` 的 0444 是**纪律 9 的不变量**，而 `rules_lock_guard` 与 `injection_guard`
      **正是按 0444 判定的**（`Ch9 §3.10 J9` / 纪律 10）。
      实测：`pristine_code_root` 初版漏了这一步 → 两个守卫在副本上 `exit=1`
      （报"权限为 0o644，应为 0o444"）→ 被判成"守卫坏了"，**又是一次假缺陷**。

    ★ 这与 `scripts/ops/bootstrap_worktree.sh` 对新工作树做的事**同源**（git 不跟踪只读位），
      只是这里针对的是**夹具副本**。
    """
    rules = target / "rules"
    if not rules.is_dir():
        return
    for item in rules.rglob("*"):
        try:
            item.chmod(0o444 if item.is_file() else 0o755)
        except OSError:
            continue


@pytest.fixture(scope="session")
def pristine_code_root() -> Path:
    """一份**真源为空**的 `system/` 副本（session 级，懒建一次，用 `pytest_sessionfinish` 清理）。

    ★ 为什么需要它（`G-RC-03`，真实数据首次暴露）：
      「守卫在**干净树**上应 `exit 0`」这一类**契约用例**，必须对"干净"的输入做断言，
      而不能对"**仓库当前恰好有什么数据**"做断言 —— 否则两者会混成同一个信号：
      真实数据一进真源（`ws-real-collect`），`traceback`（见 `T-10`）与 `no_signal_day`（见 `G-RC-04`）
      **如实**变红，契约用例却把它当成"守卫坏了"→ **真违规被淹没成假缺陷**。

    ★ **不是掩盖**：`run_all_gates.py`（`gates` 批）跑的是**真仓库**，
      所以 `T-10` / `G-RC-04` 那两条真实违例**照样可见**，只是不再污染"守卫代码健康度"这一维度。

    ★ 与 `code_root` fixture 的区别：那个是**每用例一份**（互不污染，供注入测试改文件）；
      这个是**全 session 一份**（只读，供退出码契约矩阵复用，省掉 20+ 次 `copytree`）。
    """
    target = WORK_DIR / "_pristine" / "system"
    if not target.exists():
        shutil.copytree(SYSTEM_ROOT, target, ignore=_ignore)
        for sub in _ENSURE_DIRS:
            (target / sub).mkdir(parents=True, exist_ok=True)
        _make_writable(target)
        _reset_truth_source(target)
        _lock_rules_perms(target)
    return target


_SESSION_LOCK = SYSTEM_ROOT / "tests" / ".pytest-session.lock"
"""**排他会话锁**（缺口 `G-RC-10` 的机器绑定）。

## ★ 为什么锁**不能**放在 `WORK_DIR`（`tests/.work/`）里面 —— 实测缺陷

本锁的第一版放在 `WORK_DIR / ".session.lock"`，**互斥根本没生效**。根因是一条自相矛盾：
`pytest_sessionstart` 的动作序列是「**先取锁 → 再 `_clear_work_dir(loud=True)`**」，
而 `_clear_work_dir` 清空的正是 `WORK_DIR` 的**子项** ⇒ **我们自己把自己的锁删掉了**。
⇒ 第二个会话随后可以照常取锁进入 ⇒ 锁形同虚设，而它给人的"已经排他了"是**假信心**
（比没有锁更危险：没有人会再去人工确认）。

**自证**：锁自带的 `test_lock_rejects_live_concurrent_session` 一直是红的 ——
也就是说，**这个缺陷是被它自己的测试抓到的**（这正是"注入测试必须配反向对照"的价值）。

⇒ 修法：锁放在 `WORK_DIR` **之外**（`system/tests/.pytest-session.lock`），
使它**不可能**被 `_clear_work_dir` 波及。`.gitignore` 已忽略 `system/tests/.work/`，
但**不**忽略本文件 ⇒ 需在 `.gitignore` 单独忽略（见该文件对应条目）。
"""


def _pid_alive(pid: int) -> bool:
    """该 PID 是否仍存活（用于判定锁是否**陈旧**）。"""
    import os

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True      # 进程存在但无权限发信号 → 保守视为存活
    except OSError:
        return True      # 其余 OSError 一律保守视为存活（宁可误报占用，不可误判空闲）
    return True


def _acquire_session_lock() -> None:
    """取**排他会话锁**；已被**活着的**会话占用 → **响亮失败**。

    ## ★ 为什么必须加（缺口 `G-RC-10`，实测踩到）

    `pytest_sessionstart` 会调用 `_clear_work_dir()` —— 它**清空整个 `WORK_DIR`**。
    若**同一个工作树**里同时有两个 pytest 会话，**后启动的那个**会把先启动者
    **正在使用的夹具副本删掉** ⇒ 症状是"副本里应有的文件凭空消失"，
    且**随机落在不同用例上**（实测 `tests/guards` 三跑三样，全是 `FileNotFoundError`、位置漂移）。
    这正是 `CONVENTIONS.md::V-05` 明文禁止的情形。

    ## 为什么这里**要**响亮失败，而 `_clear_work_dir` 里**只告警不中断**

    两者取舍相反，是因为**性质不同**，不是自相矛盾：
    - `_clear_work_dir` 那条针对**良性且自愈**的配额残留（重启一次就好）——
      把它升级成"整批 1s 全红"比静默更坏，故只告警并继续；
    - **本条针对的是会污染结论的并发冲突**：它**不会自愈**，且**必然产出假红**。
      继续跑 = 制造一批"看起来像守卫坏了"的假缺陷 —— 而本项目的**假缺陷已经淹没过真违规**
      好几次（`G-RC-03`、`G7`、`G9-1`、以及 `G-RC-10` 本身）。
      ⇒ 必须**立刻停**，并给出**可行动**的处置（等它结束 / 换一个 worktree）。

    ## 陈旧锁自愈

    锁文件记 PID；若该 PID 已不存在（会话被 kill / 崩溃），视为**陈旧**并接管 ——
    **不得**因为一次崩溃就永久锁死本工作树。
    ★ 跨 worktree **不冲突**：每个 worktree 各有自己的 `system/tests/.work`。
    """
    import os

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    if _SESSION_LOCK.exists():
        try:
            holder = int(_SESSION_LOCK.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            holder = -1
        if holder == os.getpid():
            # ★ **同进程重复取锁 = 幂等**（实测踩到，务必保留）：
            #   `pytest_sessionstart` 在**同一个进程**里可能被触发不止一次
            #   （实测一次 `pytest <fileA> <fileB>` 就触发了两次）。若不做这个短路，
            #   第二次会把自己**刚写的**锁当成"别人的"而**拒绝启动自己** ——
            #   报错里 pid 与当前进程相同，极易被误读成"环境里真有别的会话"。
            return
        if holder > 0 and _pid_alive(holder):
            # ★ 用 `pytest.exit` 而**不是** `raise`：后者会走成 `INTERNALERROR` + 堆栈，
            #   读者容易误判成"pytest 自己坏了"；而真实语义是"**你把两个会话叠在一起了**"。
            #   `returncode=4` 与既有的 0/1/2/3/124 全不冲突，便于在批次输出里一眼认出。
            pytest.exit(
                f"[V-05] 本工作树已有 pytest 会话在跑（pid={holder}），"
                f"它正在用 {WORK_DIR}。\n"
                "  继续会让**两个会话互删对方的夹具副本** ⇒ 随机假红，且看起来像『守卫坏了』。\n"
                "  处置：① 等它结束；② 或把本次验证放到**另一个 git worktree**"
                "（每个 worktree 有自己的 `system/tests/.work`，互不冲突）。\n"
                "  依据：`CONVENTIONS.md::V-05`（两个 pytest 会话禁止并发）· 缺口 `G-RC-10`。",
                returncode=4,
            )
        # 陈旧锁：持有者已不存在或文件损坏 → 接管（不得永久锁死）
    _SESSION_LOCK.write_text(str(os.getpid()), encoding="utf-8")


def _release_session_lock() -> None:
    """释放会话锁（**仅当仍是自己持有**时才删，避免误删接管者的锁）。"""
    import os

    try:
        if _SESSION_LOCK.read_text(encoding="utf-8").strip() == str(os.getpid()):
            _SESSION_LOCK.unlink(missing_ok=True)
    except OSError:
        pass


def _clear_work_dir(*, loud: bool) -> None:
    """清空夹具工作目录（**逐子项删**，且按需**响亮失败**）。

    ★ 为什么不是一行 `shutil.rmtree(WORK_DIR, ignore_errors=True)`（**实测故障**）：
      宿主环境的 safe-delete 对**单次批量删除**有数量阈值。原先那一行一旦被拒就**静默失败**
      （`ignore_errors=True`），于是 `tests/.work` 跨多轮**累积到 8 万+ 项**，
      最终每个用例的 setup 直接以 `E` 报错 —— 表现为"`unit` 批 0.91s 就红"，
      而**日志里只有一行 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`**，极易被误读成测试坏了。

      → 逐子项删把单次删除量级压到阈值内；
      → 仍然删不干净就**响亮抛出**并给出处置提示 —— **绝不静默**（本项目三令五申的禁忌）。
    """
    if not WORK_DIR.exists():
        return
    for child in list(WORK_DIR.iterdir()):
        # ★ 会话锁**不在此清空之列**：它正是"本工作树有人在跑"的凭证，
        #   删掉它就等于把自己刚取的锁清掉（`G-RC-10` 的机器绑定会立刻失效）。
        if child == _SESSION_LOCK:
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
    leftover = [p for p in WORK_DIR.iterdir() if p != _SESSION_LOCK]
    if not leftover:
        return
    msg = (
        f"夹具工作目录未能清空（残留 {len(leftover)} 项，例如 {[p.name for p in leftover[:3]]}）：{WORK_DIR}\n"
        "  最可能的原因：宿主对**每一轮**的删除操作有累积配额（实测消息 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`,\n"
        "  `threshold: 9999`, `scope: \"turn\"`）—— 同一轮里跑了很多次测试就会耗尽它。\n"
        "  残留目录**无害**：每个用例的目录名都带 uuid，不会串用。\n"
        "  处置：下一轮（或手动分片 `rm -rf` 子项）即可清掉。"
    )
    if loud:
        # ★ **响亮告警但继续** —— 刻意**不 raise**（实测教训）：
        #   这条路径在 `pytest_sessionstart` 里执行，一旦 raise，**整批在 1s 内全红**
        #   （症状：`unit` 批 0.84s `exit=1`，而单独 `run_pytest.sh` 却是绿的 ——
        #   因为两者共用同一轮配额，谁先跑谁先耗尽）。
        #   把"良性且自愈"的情况升级成"全面停摆"，比静默更坏。
        #   正确取舍：**可见**（响亮文字）+ **不中断**（继续跑）。
        print(f"\n[WARNING] {msg}\n")
        return
    print(f"\n[WARNING] {msg}\n")


# ★ 双保险：单个 fixture 的 `finally` 在崩溃/中断时兜不住，
#   残留的夹具副本会被 git 当源码提交（实测曾积累 53 个目录）。
#   故在 session 起止各清一次 —— **临时目录绝不允许进入仓库**。
def pytest_sessionstart(session: pytest.Session) -> None:
    # ★ **顺序不能反**（`G-RC-10`）：先取锁，再清目录。
    #   反过来的话，我们会在"确认本工作树无人"**之前**就把别人的夹具删掉 ——
    #   而那正是这条锁要防的事。
    _acquire_session_lock()
    _clear_work_dir(loud=True)
    _warn_if_fs_brokered()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    _clear_work_dir(loud=False)
    # 清完再放锁（放锁后别的会话才能进来清目录）。
    _release_session_lock()


def _warn_if_fs_brokered() -> None:
    """**响亮提示**：Python 层 FS broker 开着时，夹具复制会累积到卡死。

    实测：`CODEBUDDY_SAFE_DELETE_SANDBOX=1` 或 `CODEBUDDY_BROKERED_FS_HOOK_ENABLED=1`
    时，每次文件操作都走 IPC 到宿主进程。夹具 `copytree` 每用例复制 130 个文件，
    数百用例累积数万次往返 → **进程在某个点卡死，且卡点漂移**
    （实测 `tests/unit/test_contracts.py` 分别卡在第 15 / 17 / 19 条）。

    这里**只警告不退出**：万一宿主环境变了、broker 其实很快，也不该阻断测试。
    正确跑法见警告内容。
    """
    import os

    on = (
        os.environ.get("CODEBUDDY_SAFE_DELETE_SANDBOX") == "1"
        or os.environ.get("CODEBUDDY_BROKERED_FS_HOOK_ENABLED") == "1"
    )
    if not on:
        return
    print(
        "\n"
        "=" * 78 + "\n"
        "[WARNING] Python 层 FS broker 处于**启用**状态。\n"
        "  夹具 copytree 每用例复制 130 个文件 → 每个文件一次 broker IPC →\n"
        "  累积数万次往返后**进程会卡死**（卡点在用例之间漂移，无任何输出）。\n"
        "  正确跑法（沙箱外）：\n"
        "    sh system/scripts/ops/run_pytest.sh tests/<子目录>\n"
        "    或  python system/scripts/ops/verify.py --batch <unit|conflict|guards|injection|root>\n"
        "  （verify.py 已自动为子进程关闭 broker hook）\n"
        + "=" * 78 + "\n"
    )


class GateResult:
    """检查器一次执行的结果。属性名与 `subprocess.CompletedProcess` 对齐，
    使原有的 `proc.returncode / .stdout / .stderr` 断言写法无需改动。"""

    __slots__ = ("returncode", "stdout", "stderr")

    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_gate(script_rel: str, root: Path, *extra: str, timeout: float = 60.0) -> GateResult:
    """跑检查器，`code_root` 指向夹具副本。默认走**进程内 `__main__` 入口**。

    为什么不是子进程：一个测试套件里有 **80 次**检查器调用，每次子进程启动
    ≈ 0.31s（解释器 + yaml/pydantic 导入），合计 ≈ 25s —— 这是整个套件
    49s 里的全部大头（夹具复制实测只有 0.021s，不是瓶颈）。
    `runpy` 执行的是**与命令行完全相同的入口**，不 mock 任何东西。

    ★ 进程级保真度由这两条用例守住（它们必须用 `run_gate_subprocess`）：
      - `tests/guards/...::test_cli_wiring_exits_with_main_return_code`
      - `tests/guards/...::test_injection_blocks_at_process_level`
        （注入违例 → **真进程** exit 1，AC-04 的最终证据）

    ★ **同一 `(脚本, code_root, 参数)` 只跑一次**（session 级缓存）。
      若某个测试在**同一 `code_root`** 上先跑一次、改动后再跑同一命令，
      必须改用 `run_gate_subprocess` 或换一个 `code_root`（否则拿到旧结果）。
    """
    key = (script_rel, str(root), extra)
    hit = _GATE_RESULT_CACHE.get(key)
    if hit is not None:
        return hit
    code, out = _exec_gate_script(script_rel, root, extra)
    result = GateResult(code, out)
    _GATE_RESULT_CACHE[key] = result
    return result


def run_gate_subprocess(script_rel: str, root: Path, *extra: str, timeout: float = 60.0) -> GateResult:
    """跑检查器 —— **真子进程**（用于"CLI 接线"与"进程级阻断"这两类证据）。"""
    script = SYSTEM_ROOT / script_rel
    if not script.exists():
        raise FileNotFoundError(f"检查器脚本不存在: {script}")
    cmd = [sys.executable, str(script), str(root), "--no-report", *extra]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return GateResult(proc.returncode, proc.stdout, proc.stderr)


def _exec_gate_script(script_rel: str, root: Path, extra: tuple[str, ...]) -> tuple[int, str]:
    """执行脚本的 `__main__` 入口并捕获退出码（不 mock 任何东西）。"""
    import contextlib
    import io
    import runpy

    script = SYSTEM_ROOT / script_rel
    if not script.exists():
        raise FileNotFoundError(f"检查器脚本不存在: {script}")

    argv = [str(script), str(root), "--no-report", *extra]
    buf = io.StringIO()
    old_argv = sys.argv
    sys.argv = argv
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            runpy.run_path(str(script), run_name="__main__")
        code = 0
    except SystemExit as exc:
        # sys.exit(None) 等价于 0；sys.exit("msg") 等价于 1
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    finally:
        sys.argv = old_argv
    return int(code), buf.getvalue()


# 若某脚本**没有** `if __name__ == "__main__"` 块（只有 `main()`），
# 上面的 runpy 会"跑完但什么都没发生"（退出码恒 0）—— 那是**静默的假通过**。
# 这条断言把这种脚本挡在门外：调用后必须留下 `== <checker> ==` 的痕迹。
def assert_gate_actually_ran(script_rel: str, result: GateResult) -> None:
    assert "== " in result.stdout, (
        f"{script_rel} 看似执行了但没有输出 —— 可能缺少 `__main__` 入口块"
        f"（runpy 会静默返回 0，属于假通过）"
    )


# ── 进程内执行器（供"退出码契约"这类矩阵用例）────────────────────────────────
#
# ★ 为什么可以不用子进程：脚本的 `if __name__ == "__main__": sys.exit(main())`
#   会在 `sys.exit` 处抛 `SystemExit`，捕获它就拿到了**真实退出码**。
#   `runpy.run_path(..., run_name="__main__")` 执行的正是**命令行那条入口**，
#   不 mock 任何东西，只是省掉解释器启动（每次 0.15~1.0s，全部花在启动与
#   依赖导入上，与断言内容无关；实测这一项占整个测试套件 30s 以上）。
#
# ★ 不可用 `mod.main(argv)`：**17 个守卫脚本根本没有 `main()` 函数**，
#   它们直接写 `sys.exit(run_checker(...))`（实测踩过 —— 30 条用例集体
#   AttributeError）。`runpy` 对两种写法都成立。
#
# ★ 代价是被换掉的那点保真度，由子进程用例单独补回：
#   `test_cli_wiring_exits_with_main_return_code` 证明 `python <脚本>`
#   真能把退出码交给 shell；`test_unknown_option_is_not_silently_ignored`
#   证明 argparse 真的拒绝未知参数。
def run_gate_inproc(script_rel: str, root: Path, *extra: str) -> tuple[int, str]:
    """在**本进程内**走被检脚本的 `__main__` 入口，返回 `(退出码, 合并输出)`。"""
    import contextlib
    import io
    import runpy

    script = SYSTEM_ROOT / script_rel
    if not script.exists():
        raise FileNotFoundError(f"检查器脚本不存在: {script}")

    argv = [str(script), str(root), "--no-report", *extra]
    buf = io.StringIO()
    old_argv = sys.argv
    sys.argv = argv
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            runpy.run_path(str(script), run_name="__main__")
        code = 0
    except SystemExit as exc:
        # sys.exit(None) 等价于 0；sys.exit("msg") 等价于 1
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    finally:
        sys.argv = old_argv
    return int(code), buf.getvalue()


def assert_rejected(proc: GateResult, *, rule_hint: str = "") -> None:
    """断言"注入违例后被真的拦下"。

    - `exit 1` = 阻断（期望）
    - `exit 0` = **门禁失效**（这是本函数存在的唯一理由）
    - `exit 2` = 输入异常，也可能是"没找到被检对象"，单独提示
    """
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0, (
        f"注入违例后检查器仍 exit=0 —— 门禁失效（§5.1 AC-04 要求 exit 1）。\n输出:\n{combined}"
    )
    assert proc.returncode == 1, (
        f"期望 exit=1（阻断），实得 exit={proc.returncode}（输入异常？）。\n输出:\n{combined}"
    )
    if rule_hint:
        assert rule_hint in combined, f"输出中未出现期望的规则标记 {rule_hint!r}。\n输出:\n{combined}"
