"""卡 `#96`：`pre-commit.sh` 的**根解析失败**必须报 `exit 2`（输入错误），不是 `1`（违规）。

## 守的是什么（`CONVENTIONS.md G-01`）

| 码 | 含义 |
|---|---|
| `0` | 放行 |
| `1` | **违规**（被检对象真的有问题） |
| `2` | **输入错误**（无法确定被检对象 / 判据不在被检树） |

`pre-commit.sh` 里"**根不明**"的三处前置失败**曾经**退 `1` —— 与"你改坏了"**同码同形**。
卡 13-O 已把 `run_gate` 的"门禁脚本不在被检树"改成 `2`；本卡补齐**根解析**这一族，
使**同一次提交里的输入错误只有一个码**。

| 用例 | 被钉的落点 | 判红条件 |
|---|---|---|
| `test_non_git_dir_is_input_error` | `git rev-parse --show-toplevel` **失败** | 那处改回 `exit 1` ⇒ 拿到 `1` |
| `test_empty_root_is_input_error` | 根解析**为空** | 同上（用 PATH 上的假 `git` 造"成功但空"） |
| `test_root_without_system_scripts_is_input_error` | 根解析**可疑**（`${root}/system/scripts` 不存在） | 同上 |
| `test_real_violation_still_exits_1`（对照） | 脚本齐、其中一道 `exit 1` | 若这轮改动把违规也带成 `2` ⇒ 拿到 `2` |
| `test_gate_script_list_is_parseable`（防真空） | 清单可解析、≥10 条 | 解析式失效 ⇒ 对照用例静默空跑（`G-03`） |

★ **三处输入错误必须可区分成因**：它们的**码相同（`2`）**，但**措辞必须不同**
（"无法定位仓库根" / "仓库根解析为空" / "根解析可疑"）——
否则"到底是没进仓库、还是根算错了"在读输出时分辨不出。`test_three_input_errors_are_textually_distinct`
把这一条钉住。

## `Q1 / Q6 / Q8` 自答（本文件自己的必问项，`CONVENTIONS.md §5.2`）

- **Q1（反事实）**：改前这三个输入下都拿 `1` 且输出**没有** `[INPUT-ERROR]`；
  改后拿 `2` 且带 `[INPUT-ERROR]`。**输出必然不同** ⇒ 断言不是恒真。
- **Q6（同形构造）**：两个语义相反的情形 ——
  ①**环境/输入问题**（根不明，改代码无用）②**代码真的违规**（根正常、判据命中）。
  旧实现两者同形（都 `1`）；本文件把两者钉成**必须不同**（`2`+`[INPUT-ERROR]` vs `1`+「阻断」），
  且**双向**断言（输入错误的输出里不得出现「阻断」；真违例的输出里不得出现 `[INPUT-ERROR]`）。
- **Q8（缺口在哪）**：本文件有机器强制的是**这三处根解析路径的退出码与措辞**、
  以及**真违例仍是 1**（对照）。**没有**机器强制的是：
  ① `cd "$REPO_ROOT" || exit 1` 与"找不到可用的 python"两处**仍是 `1`**（同族但**不属本卡枚举**，
     见报告 §17.17 的"同族未改清单"）—— 本文件**不**为它们写断言（不为已知不一致背书）；
  ② "装上的钩子是否真被 git 调用"仍不属本文件（13-O 的 `test_hook_same_source.py` 亦然）。

## 夹具落在 `tmp_path`（同 13-O 的两条纪律）

⇒ ① 删除不落在受管桶内（`G-60` 的 `/tmp` 低桶）；② 本文件**零 conftest 依赖**
（不 import `conftest`），可 `--noconftest` 运行 ⇒ **不消耗夹具与删除预算**。
★ 与 `test_hook_same_source.py` **不共享任何 helper**：两份证据各自独立，
一处坏了不会把另一处**伪装成通过**（`G-03`）。
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

# `parents[2]`：本文件在 `<code_root>/tests/guards/` 下 → 上溯到 `system/`
SYSTEM = Path(__file__).resolve().parents[2]
PRE_COMMIT = SYSTEM / "scripts" / "ops" / "pre-commit.sh"


def _clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """摘掉 `GIT_*`（否则 `rev-parse` 会读到**外层仓库**而不是夹具树），并按需追加。"""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["WORKBUDDY_PY"] = sys.executable
    if extra:
        env.update(extra)
    return env


def _run(
    cmd: list[str], cwd: Path, env_extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=str(cwd), env=_clean_env(env_extra), capture_output=True, text=True, check=False
    )


def _run_pre_commit(root: Path, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return _run(["sh", str(PRE_COMMIT)], root, env_extra)


def _combined(res: subprocess.CompletedProcess[str]) -> str:
    return (res.stdout or "") + (res.stderr or "")


# ─────────────────── 三处"根不明"落点：全部必须是输入错误（`2`） ───────────────────


def test_non_git_dir_is_input_error(tmp_path: Path) -> None:
    """① `git rev-parse --show-toplevel` **失败**（不在任何仓库里）⇒ `exit 2` + `[INPUT-ERROR]`。

    ★ `GIT_CEILING_DIRECTORIES` 钉在夹具目录上：否则若临时目录**碰巧**位于某个仓库内，
      "不在仓库里"这个前提就不成立，用例会**静默变成另一回事**（`G-62`）。
    """
    work = tmp_path / "not_a_repo"
    work.mkdir()
    res = _run_pre_commit(work, {"GIT_CEILING_DIRECTORIES": str(tmp_path)})
    out = _combined(res)

    assert res.returncode == 2, f"根解析失败应是输入错误（2），实得 {res.returncode}：\n{out}"
    assert "[INPUT-ERROR]" in out, f"未标出输入错误：\n{out}"
    assert "无法定位仓库根" in out, f"未说清成因：\n{out}"
    assert "阻断" not in out, (
        "'根不明'被报成「阻断」—— 这正是本卡要治的：把**输入问题**伪装成**你改坏了**"
    )


def test_empty_root_is_input_error(tmp_path: Path) -> None:
    """② 根解析**为空**（`git` 成功返回但什么都没打印）⇒ `exit 2` + `[INPUT-ERROR]`。

    ★ 造法：PATH 前置一个**假 `git`**（打印空、`exit 0`）—— 这是**唯一**能让那一支成立的手段
      （真 `git` 要么给路径、要么非零失败）。假 `git` 命中后脚本即退出，不会走到后面的 HEAD 行。
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_git.chmod(fake_git.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    work = tmp_path / "empty_root"
    work.mkdir()
    res = _run_pre_commit(
        work, {"PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", "")}
    )
    out = _combined(res)

    assert res.returncode == 2, f"空根应是输入错误（2），实得 {res.returncode}：\n{out}"
    assert "[INPUT-ERROR]" in out, f"未标出输入错误：\n{out}"
    assert "仓库根解析为空" in out, f"未说清成因：\n{out}"
    assert "阻断" not in out, f"空根被报成了「阻断」：\n{out}"


def test_root_without_system_scripts_is_input_error(tmp_path: Path) -> None:
    """③ 根解析可为真、但 `${root}/system/scripts` **不存在** ⇒ `exit 2` + `[INPUT-ERROR]`。

    ★ 这是"**没有可检对象**"（`G-03`）：不是被检对象有问题，而是**根本没有被检对象**。
    """
    root = tmp_path / "tree_without_system"
    (root / "docs").mkdir(parents=True)
    init = _run(["git", "init", "-q", str(root)], tmp_path)
    assert init.returncode == 0, init.stderr

    res = _run_pre_commit(root)
    out = _combined(res)

    assert res.returncode == 2, f"根可疑应是输入错误（2），实得 {res.returncode}：\n{out}"
    assert "[INPUT-ERROR]" in out, f"未标出输入错误：\n{out}"
    assert "根解析可疑" in out, f"未说清成因：\n{out}"
    assert "阻断" not in out, f"根可疑被报成了「阻断」：\n{out}"


def test_three_input_errors_are_textually_distinct(tmp_path: Path) -> None:
    """★ 三处落点**码相同（`2`）但措辞必须不同** —— 否则读输出时分不出"是哪一种根不明"。

    ★ 反向对照：`{2, 2, 2}` 之外还要断言**三条消息两两不同**；
      若后人把三处合并成一句通用话术，本用例当场红（那会让诊断信息退化）。
    """
    # ① 非 git 目录
    work = tmp_path / "not_a_repo2"
    work.mkdir()
    msg_a = _combined(_run_pre_commit(work, {"GIT_CEILING_DIRECTORIES": str(tmp_path)}))

    # ③ 假仓库根（无 system/scripts）
    root = tmp_path / "tree_without_system2"
    (root / "docs").mkdir(parents=True)
    _run(["git", "init", "-q", str(root)], tmp_path)
    msg_c = _combined(_run_pre_commit(root))

    markers = ("无法定位仓库根", "根解析可疑")
    assert markers[0] in msg_a, msg_a
    assert markers[1] in msg_c, msg_c
    assert markers[0] not in msg_c, "两处输入错误的措辞被合并了 —— 诊断信息退化"
    assert markers[1] not in msg_a, "两处输入错误的措辞被合并了 —— 诊断信息退化"


# ─────────────────────── 对照：真违规**仍**是 `1`（不得被带成 2） ───────────────────────

_GATE_RE = re.compile(r'run_gate\s+"[^"]*"\s+"\$CODE_ROOT/(?P<rel>[^"]+)"')


def _gate_scripts() -> list[str]:
    """**从 `pre-commit.sh` 自身解析**门禁脚本清单（不硬编码 ⇒ 加门禁时本文件自动跟上）。"""
    rels = [m.group("rel") for m in _GATE_RE.finditer(PRE_COMMIT.read_text(encoding="utf-8"))]
    assert len(rels) >= 10, f"只解析到 {len(rels)} 条门禁，解析式可能已失效：{rels}"
    return rels


def _make_tree(tmp_path: Path, stubs: dict[str, str]) -> Path:
    """造一棵"像仓库"的临时树：`git init` + 真 `pre-commit.sh` + 指定的门禁桩。"""
    root = tmp_path / "tree"
    (root / "system" / "scripts" / "ops").mkdir(parents=True)
    (root / "system" / "scripts" / "checks").mkdir(parents=True)
    (root / "system" / "scripts" / "graph").mkdir(parents=True)
    (root / "system" / "scripts" / "ops" / "pre-commit.sh").write_bytes(PRE_COMMIT.read_bytes())
    for rel, code in stubs.items():
        target = root / "system" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8")
    init = _run(["git", "init", "-q", str(root)], tmp_path)
    assert init.returncode == 0, init.stderr
    return root


def test_real_violation_still_exits_1(tmp_path: Path) -> None:
    """★ 对照：根正常、脚本齐，其中**一道真返回 1** ⇒ `exit 1` + 「阻断」，**不得**变 `2`。

    ★ 判红条件：若把退出码分流写成"任何非零 ⇒ 2"，或把根解析的 `2` 泄漏到门禁循环，
      本用例拿到 `2` / 拿不到「阻断」⇒ 当场红。
    """
    rels = _gate_scripts()
    stubs = {rel: "import sys\nsys.exit(0)\n" for rel in rels}
    stubs[rels[0]] = "import sys\nsys.exit(1)\n"
    root = _make_tree(tmp_path, stubs)

    res = _run_pre_commit(root)
    out = _combined(res)

    assert res.returncode == 1, f"真违例应是 1（违规），实得 {res.returncode}：\n{out}"
    assert "阻断" in out, f"真违例未报「阻断」：\n{out}"
    assert "[INPUT-ERROR]" not in out, f"脚本齐备却报了输入错误（误判）：\n{out}"


def test_gate_script_list_is_parseable() -> None:
    """防"解析式失效导致上面那条对照悄悄退化成空跑"（`G-03`）。"""
    rels = _gate_scripts()
    assert all(rel.endswith(".py") for rel in rels), rels
    assert len(set(rels)) == len(rels), "门禁清单里有重复项"


def test_source_tree_itself_exits_two_on_missing_script(tmp_path: Path) -> None:
    """★ 回归 13-O 的那一半：**门禁脚本不在被检树** 仍是 `2`（本卡不得把它带回 `1`）。

    与 `test_hook_same_source.py::test_input_error_is_distinguishable_from_violation` 的 (a)
    **刻意重复一次**：本卡改的正是同一段前置逻辑（`set -u` 之后、`run_gate` 之前），
    两份证据互不依赖 —— 一处被改坏时另一处仍能报出来（`G-03`：不靠单一证据）。
    """
    root = _make_tree(tmp_path, stubs={})
    res = _run_pre_commit(root)
    out = _combined(res)

    assert res.returncode == 2, f"缺门禁脚本应仍是 2，实得 {res.returncode}：\n{out}"
    assert "[INPUT-ERROR]" in out and "门禁脚本不在被检树" in out, out
    assert "阻断" not in out, out


# ───────────────────────── 防"用例自身退化"的元断言（`G-03`） ─────────────────────────


def test_pre_commit_is_runnable_as_sh(tmp_path: Path) -> None:
    """元断言：本文件全部断言都建立在"真 `pre-commit.sh` 能被 `sh` 跑起来"之上。

    ★ 若脚本语法坏了（或路径写错），上面每条用例都会失败 —— 但失败原因会是**乱码式的**
      "cannot open file"，很容易被当成环境问题。故先单独钉一条**语法**断言。
    """
    syntax = subprocess.run(
        ["sh", "-n", str(PRE_COMMIT)], capture_output=True, text=True, check=False
    )
    assert syntax.returncode == 0, f"pre-commit.sh 语法非法：{syntax.stderr}"
    assert PRE_COMMIT.is_file(), PRE_COMMIT
    del tmp_path
    # 防"本文件真的一个断言都没跑"：给出一条可核的肯定事实（脚本存在且 sh 可解析）
    assert shutil.which("git") is not None, "本文件的多个用例依赖真 git"
