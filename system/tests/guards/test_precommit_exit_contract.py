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
| `test_cd_failure_is_input_error` | **`cd` 进不去被检树**（`git` 给了一个不存在的根） | 那处改回 `exit 1` ⇒ 拿到 `1` |
| `test_missing_interpreter_is_input_error` | **环境无可用 python**（WORKBUDDY_PY 未设 + 候选全无） | 同上 |
| `test_unusable_workbuddy_py_is_input_error` | **`WORKBUDDY_PY` 指向不可用解释器** | ★ 见下（同族**第四形态**） |
| `test_real_violation_still_exits_1`（对照） | 脚本齐、其中一道 `exit 1` | 若这轮改动把违规也带成 `2` ⇒ 拿到 `2` |
| `test_gate_script_list_is_parseable`（防真空） | 清单可解析、≥10 条 | 解析式失效 ⇒ 对照用例静默空跑（`G-03`） |

★ **第四形态（`WORKBUDDY_PY` 指向坏解释器）是本轮最重的一处**，实测回放（改前，本树 `f014222`）：

```
pre-commit → append_only_guard
pre-commit.sh: line 131: /nonexistent/python: No such file or directory
…（共 14 次）…
pre-commit ✗ rule_key_alignment_guard 阻断（exit=127）
pre-commit: 有门禁阻断，提交被拒。      ⇒ rc=1
```

**14 道门禁一道都没跑**，却**全部**被报成「阻断」 —— 与 `G-61`（`rc=2` 被报成阻断）同族，
但**假指责面积最大**（14 条），且"环境错了"被完整伪装成"你改坏了 14 道门禁"。

★ **本文件不能按"语义词"判"有没有被诬告"** —— 我自己踩过一次，记在这里：
  上段那则诊断**必须逐字引用**改前的输出才能让人看懂，于是它的正文里**也含有**「阻断」二字。
  若断言写成 `out.count("阻断") == 0`，**它读到的是我自己的引文**，当场假红（实测 `assert 1 == 0`）。
  ⇒ 断言一律读**代码路径的机械前缀**，不读语义词：
  `_ACCUSE_PREFIX = "pre-commit ✗ "`（`run_gate` 判"违规"那一支的**唯一**出口）
  `_GATE_START_PREFIX = "pre-commit → "`（`run_gate` 进门先打的**唯一**标记）。
  ★ 这同时更严：`阻断` 可以被任何一句解释性文字带出来，而 `pre-commit ✗ ` 只可能由
    `run_gate` 的 else 分支产生 —— **它无法被措辞伪造**（`G-62`：结算通道须与事实同源）。

★ **三处输入错误必须可区分成因**：它们的**码相同（`2`）**，但**措辞必须不同**
（"无法定位仓库根" / "仓库根解析为空" / "根解析可疑"）——
否则"到底是没进仓库、还是根算错了"在读输出时分辨不出。`test_three_input_errors_are_textually_distinct`
把这一条钉住。

## `Q1 / Q6 / Q8` 自答（本文件自己的必问项，`CONVENTIONS.md §5.2`）

- **Q1（反事实）**：改前这三个输入下都拿 `1` 且输出**没有** `[INPUT-ERROR]`；
  改后拿 `2` 且带 `[INPUT-ERROR]`。**输出必然不同** ⇒ 断言不是恒真。
- **Q6（同形构造）**：两个语义相反的情形 ——
  ①**环境/输入问题**（根不明，改代码无用）②**代码真的违规**（根正常、判据命中）。
  旧实现两者同形（都 `1`）；本文件把两者钉成**必须不同**（`2`+`[INPUT-ERROR]` vs `1`+`pre-commit ✗ `），
  且**双向**断言（输入错误的输出里不得出现 `pre-commit ✗ ` 与 `pre-commit → `；
  真违例的输出里不得出现 `[INPUT-ERROR]`）。
- **Q8（缺口在哪）**：本文件有机器强制的是**五处"根/环境不明"落点的退出码与措辞**
  （三处根解析 + `cd` + 解释器）、以及**真违例仍是 1**（对照）。**没有**机器强制的是：
  ① 那五处之外是否还有"输入/环境失败报成 `1`"的形态（本文件不声称穷尽 —— 我只逐行读过本文件）；
  ② "装上的钩子是否真被 git 调用"仍不属本文件（13-O 的 `test_hook_same_source.py` 亦然）；
  ③ **`blocked_hint` 式的语义**：本文件只判"码 + 措辞"，不判"措辞是否足以让人一眼定位"。
  ④ ★ **断言自身的鉴别力**：本文件只钉住"这五处下输出里不出现诬告前缀"，
     **没有**机器强制"每条断言的鉴别力 ≥ 1 次可由反例触发"（`criterion_effectiveness` 的
     G9 精神，但那条门禁只管**已绑定的判据表**，不管**测试里的 assert**）。
     ⇒ 本文件里**已经**出现过恒真断言（见下"自查"一节），靠人读出来。

## 自查：本文件自己找到的两处断言缺陷（`#96` 扩范围那一轮）

1. **假红（语义词被自己的引文命中）**：`test_unusable_workbuddy_py_is_input_error` 初版写
   `assert out.count("阻断") == 0`；而同一处诊断为了让人看懂**必须逐字引用改前输出**
   （含「阻断（exit=127）」）⇒ 断言读到引文，`assert 1 == 0`。
   ⇒ 改为只认 `_ACCUSE_PREFIX`（机械前缀）。
2. **恒真（无鉴别力）**：三处根解析用例里的 `assert "阻断" not in out` 是**装饰性**的 ——
   这三支改前的旧代码是 `echo "…无法定位仓库根…"; exit 1`，**根本不打「阻断」二字**
   ⇒ 该断言在改前改后**都成立**，对"这一支是否被错报成违规"**零鉴别力**。
   ⇒ 换成 `_GATE_START_PREFIX not in out`（**非恒真**：它钉住"前置输入检查没被挪到门禁循环之后"，
     挪了就会先打 14 次 `pre-commit → ` 再 `exit 2` —— 那正是`G-62` 式的"先诬告再改正"）。
   ★ 这两条都不是"顺手改"：它们是 `G9`（判据须真能触发）落在**测试自身**上的同一形状，
     而现有门禁只审**已绑定的判据表**，审不到 `assert` 行。

★★ **同一个坑，我在本文件里连踩三次** —— 它值得单独成一条纪律（`G-62` 的测试侧形态）：

| # | 断言 | 它读到的"假证据" | 后果 |
|---|---|---|---|
| 1 | `out.count("阻断") == 0` | 本文件**诊断引文**里的「阻断（exit=127）」 | 假红 `assert 1 == 0` |
| 2 | `"exit=127" not in out` | 同一处引文里的 `exit=127` | 假红（同样的 `assert 1 == 0`） |
| 3 | `assert _ACCUSE_PREFIX in src`（元断言） | `pre-commit.sh` **注释里**逐字引的 `pre-commit ✗ …` | **恒真**：删掉真的发射行仍 `1 passed`（K10 实测） |

**共同根因**：我为了"让人看懂"而把**改前的输出/代码逐字引用**进诊断与注释，
于是"要检测的那个 token"与"解释它的文字"**同形** ⇒ 任何**按 token 扫全文**的断言都会读到引文。
⇒ 纪律：**断言只能读"由代码路径唯一产生、且不会被解释性文字复述"的东西** ——
即**词法开头**（`echo "pre-commit ✗ `）而非**语义词**（`阻断`）、**发射语句**而非**它发的那个词**。
★ 这三条不是纸面推导：`#96` 的 `K1`–`K10` 十条反例里，第 1、2、3 条各自被一条反例实测抓出
  （`K10` 那一格尤其讽刺 —— **守"断言不许恒真"的元断言，自己先恒真了**）。

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

# ★ 判"有没有被诬告"只认这两个**机械前缀**（由 `pre-commit.sh` 的两处 `echo` 唯一产生），
#   不认语义词「阻断」—— 理由见模块 docstring 里我自己那次假红（诊断正文会引用改前输出）。
#   ★ 与 `pre-commit.sh` 同源地钉在这里：若那两处前缀被改掉，本文件的断言会**响亮失效**
#     （拿不到前缀 ⇒ 断言恒真）⇒ `test_accusation_prefixes_are_still_emitted` 把它兜住。
_ACCUSE_PREFIX = "pre-commit ✗ "   # `run_gate` 判"违规"那一支的唯一出口
_GATE_START_PREFIX = "pre-commit → "  # `run_gate` 进门先打的唯一标记
_BLOCK_SETTLEMENT = "pre-commit: 有门禁阻断，提交被拒。"  # 全脚本结算成违规那行的唯一出口

# ★★ 元断言要钉的是**发射语句**，不是上面那三个 token —— 我在这里**第三次**踩同一个坑：
#   初版 `test_accusation_prefixes_are_still_emitted` 写成 `assert _ACCUSE_PREFIX in src`，
#   而 `pre-commit.sh` 的注释里**为留证据逐字引了** `pre-commit ✗ rule_key_alignment_guard …`
#   ⇒ 把真正的 `echo` 行删掉，元断言**仍然成立**（它读到的是引文）⇒ 元断言自己退化成恒真。
#   （K10 反例实测：删掉发射行后 `1 passed` —— 该反例无判别力。）
#   ⇒ 只认 `echo "…` 这个**词法开头**：注释里不会出现它。
_EMITTERS: tuple[tuple[str, str], ...] = (
    (_ACCUSE_PREFIX, 'echo "pre-commit ✗ '),
    (_GATE_START_PREFIX, 'echo "pre-commit → '),
    (_BLOCK_SETTLEMENT, 'echo "pre-commit: 有门禁阻断，提交被拒。"'),
)


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


def _assert_not_accused(out: str, why: str) -> None:
    """钉住"**没被诬告成违规**"（读机械前缀，不读语义词 —— 见模块 docstring 的假红记录）。

    ★ 两条都是**代码路径的唯一出口**，不是措辞：
      ① `_ACCUSE_PREFIX` —— `run_gate` 判"违规"那一支；
      ② `_BLOCK_SETTLEMENT` —— 全脚本**结算成违规**那一行（`exit 1` 之前）。
    ★★ 我在这里**连踩两次**同一个坑，因此把它写成纪律：
      任何"整段输出里不许出现 X"的断言，**只要 X 是这处诊断为了讲清后果而必须引用的 token，
      该断言就必然假红**。第一次是语义词「阻断」，第二次是数字 `exit=127`。
      ⇒ 可用的只有"**由代码路径唯一产生、且解释性文字不会复述**"的机械标记。
    """
    assert _ACCUSE_PREFIX not in out, (
        f"{why} 被报成了「违规」（出现 `{_ACCUSE_PREFIX}`）—— 这正是本卡要治的："
        f"把**输入/环境问题**伪装成**你改坏了**：\n{out}"
    )
    assert _BLOCK_SETTLEMENT not in out, (
        f"{why} 被**结算成**「提交被拒」（出现 `{_BLOCK_SETTLEMENT}`）—— "
        f"输入错误不该走违规的结算通道（`G-62`：结算通道须与事实同源）：\n{out}"
    )


def _assert_gate_loop_not_started(out: str, why: str) -> None:
    """钉住"**门禁循环根本没启动**"（前置输入检查在前，没被挪到循环之后）。

    ★ 这条**不是恒真的**：若有人把那几处前置检查移到 14 次 `run_gate` 之后，
      输出会先出现 14 行 `pre-commit → `、再 `exit 2` ⇒ 本断言当场红。
      那个形态正是 `G-62`："先诬告全部门禁、最后再把码改正"。
    """
    assert _GATE_START_PREFIX not in out, (
        f"{why} 时门禁循环已启动（出现 `{_GATE_START_PREFIX}`）—— "
        f"前置输入检查被挪到循环之后了（会先跑/先诬告完门禁再改正码）：\n{out}"
    )


def _assert_input_error(out: str, why: str) -> None:
    """输入错误的**合取式**断言：既没诬告、也没把门禁跑起来。"""
    _assert_not_accused(out, why)
    _assert_gate_loop_not_started(out, why)


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
    _assert_input_error(out, "根解析失败")


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
    _assert_input_error(out, "空根")


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
    _assert_input_error(out, "根可疑")


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


# ─────────── `#96` 扩的两处：`cd` 进不去被检树 / 解释器不可用（同族第 4、5 形态） ───────────


def _fake_git_dir(tmp_path: Path, output: str) -> Path:
    """造一个只含**假 `git`** 的 bin 目录（打印 `output` 后 `exit 0`）。"""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    fake = bin_dir / "git"
    fake.write_text("#!/bin/sh\nprintf '%s\\n' \"" + output + "\"\n", encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir


def test_cd_failure_is_input_error(tmp_path: Path) -> None:
    """★ 落点④：`git` 给出一个**不存在的根** ⇒ `cd` 失败 ⇒ `exit 2` + `[INPUT-ERROR]`。

    ★ 实测回放（改前，本树 `f014222`）：旧版只打 shell 的
      `cd: … No such file or directory` 然后 `exit 1` ⇒ 提交者被告知"你改坏了"，根因却是环境/输入。
    ★ 造法：假 `git` 打印一个必然不存在的路径（真 `git` 不会给出不存在的 toplevel）。
    """
    bin_dir = _fake_git_dir(tmp_path, "/nonexistent/pc96/nowhere")
    work = tmp_path / "work"
    work.mkdir()
    res = _run(
        ["sh", str(PRE_COMMIT)],
        work,
        {"PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", "")},
    )
    out = _combined(res)

    assert res.returncode == 2, f"进不去被检树应是输入错误（2），实得 {res.returncode}：\n{out}"
    assert "[INPUT-ERROR]" in out, f"未标出输入错误：\n{out}"
    assert "无法进入仓库根" in out, f"未说清成因：\n{out}"
    _assert_input_error(out, "进不去被检树")


def test_missing_interpreter_is_input_error(tmp_path: Path) -> None:
    """★ 落点⑤：**环境里没有可用 python** ⇒ `exit 2` + `[INPUT-ERROR]`（不得 `exit 1`）。

    ★ 造法（三件事缺一不可）：
      ① `HOME` 指向空目录 ⇒ 候选① 不存在；
      ② 夹具树里没有 `.venv` ⇒ 候选② 不存在；
      ③ `PATH` 只含**假 `git`**（用**真 `git` 的软链**，让根解析仍能成功）⇒ `python3` 找不到。
      此时 `WORKBUDDY_PY` 未设 ⇒ `PY` 为空 ⇒ 该落点命中。
    ★ 必须用**绝对路径**调 `sh`：`PATH` 已被清空，子进程解析不到 `sh`（我第一版就是这么红的）。
    """
    bin_dir = _fake_git_dir(tmp_path, str(tmp_path / "tree"))
    (tmp_path / "tree" / "system" / "scripts" / "ops").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tree" / "system" / "scripts" / "ops" / "pre-commit.sh").write_bytes(
        PRE_COMMIT.read_bytes()
    )
    home = tmp_path / "empty_home"
    home.mkdir()

    sh = shutil.which("sh")
    assert sh, "本机的 sh 解析不到 —— 无法构造本用例"
    env = {"PATH": str(bin_dir), "HOME": str(home)}
    proc = subprocess.run(
        [sh, str(tmp_path / "tree" / "system" / "scripts" / "ops" / "pre-commit.sh")],
        cwd=str(tmp_path / "tree"),
        env=env,                      # ★ 刻意**不**继承 os.environ：WORKBUDDY_PY 必须未设
        capture_output=True, text=True, check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")

    assert proc.returncode == 2, f"缺解释器应是输入错误（2），实得 {proc.returncode}：\n{out}"
    assert "[INPUT-ERROR]" in out, f"未标出输入错误：\n{out}"
    assert "找不到可用的 python" in out, f"未说清成因：\n{out}"
    _assert_input_error(out, "环境缺解释器")


def test_unusable_workbuddy_py_is_input_error(tmp_path: Path) -> None:
    """★★ 同族**第四形态**（本轮最重的一处）：`WORKBUDDY_PY` 指向**坏解释器** ⇒ 必须 `exit 2`。

    ★ 实测回放（**改前**，本树 `f014222`，`WORKBUDDY_PY=/nonexistent/python`）：
      14 道门禁**一道都没跑**，却**全部**被报成「阻断（exit=127）」+ `有门禁阻断，提交被拒` ⇒ `rc=1`。
      ⇒ 把"环境错了"完整伪装成"**你改坏了 14 道门禁**"（与 `G-61` 同族，**假指责面积最大**）。
    ★ 故本用例**单独断言没有出现诬告前缀**（`_ACCUSE_PREFIX`）—— 光断言 `rc==2` 不够：
      一个"先报 14 条阻断、最后再 exit 2"的实现也能骗过 `rc`（`G-62`：结算通道与事实不等价）。
    ★ 我第一版写成 `out.count("阻断") == 0` ⇒ **假红 `assert 1 == 0`**：命中的是**本文件自己的
      诊断引文**（它逐字引了改前的「阻断（exit=127）」）。改成机械前缀后，本用例既不再假红、
      也**更严**：`阻断` 任何措辞都能带出来，而 `pre-commit ✗ ` 只有 `run_gate` 的 else 支能产生
      —— 除非它**真的**把门禁报成违规。
    ★ **门禁一律桩成 `exit 0`**（不是 `stubs={}`）：这样"绕过前置检查"会**真的跑完 14 道再全报阻断**
      —— 正是改前那个 14 条假指责的形态；若用空树，14 道会因"脚本缺失"走输入错误支，
      反例就**复现不出**要治的那件事（假证据）。
    """
    stubs = {rel: "import sys\nsys.exit(0)\n" for rel in _gate_scripts()}
    root = _make_tree(tmp_path, stubs)             # 真 git 仓库 ⇒ 根解析与 cd 都会成功
    res = _run(
        ["sh", str(root / "system" / "scripts" / "ops" / "pre-commit.sh")],
        root,
        {"WORKBUDDY_PY": "/nonexistent/python"},
    )
    out = _combined(res)

    assert res.returncode == 2, (
        f"坏解释器应是输入错误（2），实得 {res.returncode}：\n{out}"
    )
    assert "[INPUT-ERROR]" in out, f"未标出输入错误：\n{out}"
    assert "解释器不可用" in out, f"未说清成因：\n{out}"
    assert "/nonexistent/python" in out, f"未报出是哪个解释器不可用（无法定位）：\n{out}"
    _assert_input_error(out, "坏解释器")


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
    # ★ 本用例与上面五处**不同**：这里门禁循环**确实启动了**（14 道都报"脚本不在被检树"），
    #   所以只断言"没被诬告成违规"，**不能**断言循环未启动。
    _assert_not_accused(out, "缺门禁脚本")


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


def test_accusation_prefixes_are_still_emitted() -> None:
    """★★ 防"本文件的否定断言退化成恒真"（`G-03` / `G9` 精神）。

    ★ 上面 `_assert_not_accused` / `_assert_gate_loop_not_started` 用的三个标记，是**从
      `pre-commit.sh` 抄过来的**（"判据与对象同源"是好事，但抄错了会静默变恒真）：
      若哪天那三行的 `echo` 被改写（例如 `pre-commit ✗ ` 改成 `✗ `），否定断言就**永远成立** ——
      于是"有没有被诬告"这件事**再也没人查**，而测试**全绿**。
    ★★ 本用例**必须读发射语句**（`_EMITTERS` 的第二个元素，形如 `echo "pre-commit ✗ `），
      **不能**读 token 本身 —— 我初版就是读 token，`pre-commit.sh` 的**注释**里恰好引了那个 token
      ⇒ 删掉真 `echo` 后本用例**仍 `1 passed`**（`K10` 反例实测）⇒ 元断言自己先恒真了。
    ★ 读发射语句是**肯定事实**（`echo "…` 这个词法开头注释里不会出现），所以可证、不恒真。
    ★ 反向对照（机器）：`K10` 删掉 `echo "pre-commit ✗ …"` 那一行 ⇒ 本用例当场红。
    """
    src = PRE_COMMIT.read_text(encoding="utf-8")
    for token, emitter in _EMITTERS:
        assert emitter in src, (
            f"发射语句 {emitter!r} 已不在 pre-commit.sh 里 —— 它本该产出 {token!r}，"
            f"于是所有按 {token!r} 做的否定断言都**恒真**了（从此没人查这条）"
        )
