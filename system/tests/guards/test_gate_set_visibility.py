"""卡 `#96` §③ / 缺口 `G-65`：**两组门禁集合之差必须机器可见**（不得静默分裂）。

## 守的是什么

`run_all_gates.py::GATES` **27 道** vs `pre-commit.sh` **14 道**不是同一集合
⇒ 有 **13 道只在集成时跑，红着也不挡提交**（`traceback.py` 就是活例：主干即红而提交照过）。
这个差此前**在任何输出里都不可观测** —— 与 13-O 治的"清单比对象旧 ⇒ 静默少跑门禁"是**同一族**。

`pre-commit.sh` 因此多打一行（`口径 10`：本次用的是哪份清单要留现场）：

```
pre-commit: 判据树 HEAD=<sha> · 本树门禁 14 道 · run_all_gates 另有 13 道（集成时跑） · 判据=<self>
```

★ **明确不做**：把 27 道塞进 `pre-commit`。那会让每次提交变慢，而"**卡死的门禁 = 被关掉的门禁**"；
  且 `口径 16` 已定 pre-commit 不跑 pytest（13 道里的多数）。⇒ 只做**可见性**。

## 三条验收（主理人裁定）与本文件的对应

| 验收 | 钉在哪 |
|---|---|
| ① 两个数各自与实际集合一致 | `test_numbers_match_the_actual_sets`（**第三条独立路径**现算：本文件自己 parse + 自己 import） |
| ② 增/删一道门禁时两个数**自动跟着变** | `test_adding_a_registered_gate_changes_both` / `test_removing_a_gate_changes_both` / `test_unregistered_gate_is_flagged` |
| ③ 全道 PASS 不受影响 | `test_real_tree_still_passes_with_the_new_line`（真实树 `rc=0`、`阻断` 0 次） |

## ★ 本卡在动这一行之前，先修掉一处**我自己在 13-O 写下的静默缺陷**

`_gate_count` 的派生用 `while … done < "$0"` —— 而 `$0` 可以是**相对路径**。
本文件后面会 `cd "$REPO_ROOT"`，于是相对 `$0` **再也解不开** ⇒ 重定向失败
⇒ **整个循环体一次都不执行** ⇒ 计数**静默停在 `0`**，而脚本照常 `exit 0`、报"全部门禁放行"。

实测（2026-09-17，本树 `0582804`，cwd=`system/scripts/ops`）：

```
$ sh pre-commit.sh
pre-commit.sh: line 129: pre-commit.sh: No such file or directory
pre-commit: 判据树 HEAD=0582804 · 本树门禁 0 道 · 判据=pre-commit.sh
…（14 道**确实都跑了**）…   pre-commit ✓ 全部门禁放行        ⇒ rc=0
```

⇒ 13-O 那行"**可见性输出**"当场报了个**假数**，而假数比不报更坏（`G-03`：`0 道` ≠ 没门禁）。
修法：`$0` 在**任何 `cd` 之前**钉成绝对路径（`_SELF`），且计数取不到时说"**取不到**"、**不报 0**。
`test_relative_invocation_does_not_silently_count_zero` 把它钉住。

## `Q1 / Q6 / Q8` 自答（`CONVENTIONS.md §5.2`）

- **Q1（反事实）**：改前这一行**没有** `另有 … 道` 这一节；改后必有（且数值随集合变）。
  ⇒ 断言不是恒真。
- **Q6（同形构造）**：两个语义不同的情形 ——
  ①**集合差**（集成时才跑的门禁数）②**本树门禁数**（提交时真会跑的门禁数）。
  二者此前**只报一个**（②），且 ① 完全不可见；本文件把两者都钉住，且**分别**与实际集合核对。
- **Q8（缺口在哪）**：本文件**没有**机器强制的是：
  ① "那 13 道在集成时**确实**有人跑"（`run_all_gates` 只是一份清单，不是调度器）；
  ② "两处口径一致"只在**危险方向**（本树有、`run_all_gates` 无）报 `⚠` —— 反向（`run_all_gates` 有、
     本树无）**本来就是本卡要暴露的正常差**，不是缺陷；
  ③ 派生器**永不阻断提交**：这是**刻意的**（它是可见性工具，不是门禁）⇒
     "有人把差当没事"这件事**本文件管不了**。

## 夹具纪律（与本目录另两个文件相同）

① 一切落 `tmp_path`（`G-60` 的 `/tmp` 低桶）；② **零 `conftest` 依赖**，可 `--noconftest` 运行
⇒ 不消耗夹具与删除预算；③ 与 `test_hook_same_source.py` / `test_precommit_exit_contract.py`
**不共享 helper**（`G-03`：两份证据各自独立，一处坏了不会把另一处伪装成通过）。
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[2]
PRE_COMMIT = SYSTEM / "scripts" / "ops" / "pre-commit.sh"
RUN_ALL_GATES = SYSTEM / "scripts" / "ops" / "run_all_gates.py"
DERIVER = SYSTEM / "scripts" / "ops" / "gate_set_diff.py"

# ★ 与 `pre-commit.sh` 的调用点**同源**（第三份副本；另两份在 `gate_set_diff.py` 与本目录的
#   `test_precommit_exit_contract.py`）。取不到就**响亮失败**（`G-03`：0 条 ≠ 没门禁）。
_GATE_RE = re.compile(r'run_gate\s+"[^"]*"\s+"\$CODE_ROOT/(?P<rel>[^"]+)"')
# ★ 判"那一行在不在"只认**行首词法开头**，不认语义词（本仓 `G-62` 的测试侧形态：
#   解释性文字会与它解释的输出同形 —— 我在 `#96` 上一轮已因此连踩三次）。
_LINE_HEAD = "pre-commit: 判据树 HEAD="


def _clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["WORKBUDDY_PY"] = sys.executable
    if extra:
        env.update(extra)
    return env


def _run(cmd: list[str], cwd: Path, extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=str(cwd), env=_clean_env(extra), capture_output=True, text=True, check=False
    )


def _out(res: subprocess.CompletedProcess[str]) -> str:
    return (res.stdout or "") + (res.stderr or "")


def _visibility_line(text: str) -> str:
    """取出那一行；取不到就**响亮失败**（否则下面每条断言都会静默变成"测了别的东西"）。"""
    for line in text.splitlines():
        if line.startswith(_LINE_HEAD):
            return line
    raise AssertionError(f"输出里没有可见性行（`{_LINE_HEAD}`）—— 本文件全部断言都建立在它之上：\n{text}")


def _numbers(line: str) -> tuple[str, str]:
    """返回 `(本树门禁数, 另有道数)`，两者都保留**原始文本**（`0` 与 `取不到` 必须可分）。"""
    m_n = re.search(r"本树门禁 (\S+) 道", line)
    m_e = re.search(r"另有 (\d+) 道", line)
    assert m_n, f"可见性行里没有「本树门禁 N 道」：{line}"
    assert m_e, f"可见性行里没有「另有 N 道」：{line}"
    return m_n.group(1), m_e.group(1)


def _gates_of_run_all_gates(path: Path = RUN_ALL_GATES) -> list[str]:
    """**独立地**从真源模块取 `GATES` 的脚本清单（本文件自己的第三条路径）。"""
    spec = importlib.util.spec_from_file_location("_test_gate_set_visibility_rag", path)
    assert spec and spec.loader, f"无法装载 {path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return [str(entry[1]) for entry in mod.GATES]


def _gates_of_pre_commit(text: str) -> list[str]:
    rels = [m.group("rel") for m in _GATE_RE.finditer(text)]
    assert rels, "解析式失效：一条 `run_gate` 都没解析到（本文件的对照会静默空跑）"
    return rels


def _make_tree(tmp_path: Path, *, stubs: tuple[str, ...]) -> Path:
    """造一棵"像仓库"的树：真 `pre-commit.sh` + 真 `run_all_gates.py` + 指定的门禁桩。"""
    root = tmp_path / "tree"
    ops = root / "system" / "scripts" / "ops"
    ops.mkdir(parents=True)
    (root / "system" / "scripts" / "checks").mkdir(parents=True)
    (root / "system" / "scripts" / "graph").mkdir(parents=True)
    ops.joinpath("pre-commit.sh").write_bytes(PRE_COMMIT.read_bytes())
    ops.joinpath("run_all_gates.py").write_bytes(RUN_ALL_GATES.read_bytes())
    ops.joinpath("gate_set_diff.py").write_bytes(DERIVER.read_bytes())
    for rel in stubs:
        target = root / "system" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    init = _run(["git", "init", "-q", str(root)], tmp_path)
    assert init.returncode == 0, init.stderr
    return root


_ALL_STUBS = tuple(sorted(set(_gates_of_pre_commit(PRE_COMMIT.read_text(encoding="utf-8")))))

# ★ 真实树那一跑是**唯一**的慢操作（14 道真门禁）⇒ 缓存一次给两条用例共用。
#   这是**只读缓存**（存一个已完成子进程的读数），不是 `P-04` 说的"模块级可变全局副作用"：
#   没有任何用例改它、也没有用例依赖它的**写入顺序**（两次取到的是同一个对象）。
_REAL_RUN: list[subprocess.CompletedProcess[str]] = []


def _real_tree_run() -> subprocess.CompletedProcess[str]:
    if not _REAL_RUN:
        _REAL_RUN.append(_run(["sh", str(PRE_COMMIT)], SYSTEM.parent))
    return _REAL_RUN[0]


def _expected_pair() -> tuple[str, str]:
    """**独立**现算 `(本树门禁数, 另有道数)` —— 本文件自己的第三条路径（不复用任何派生器）。"""
    p = set(_gates_of_pre_commit(PRE_COMMIT.read_text(encoding="utf-8")))
    g = set(_gates_of_run_all_gates())
    return str(len(p)), str(len(g - p))


# ───────────────────────── ① 两个数各自与实际集合一致 ─────────────────────────


def test_numbers_match_the_actual_sets() -> None:
    """★ 验收①：两个数必须**各自**等于实际集合，而不是"加起来对"。

    ★ 本用例**不复用** `pre-commit.sh` 的任何派生：它自己 parse `pre-commit.sh`（`_GATE_RE`）、
      自己装载 `run_all_gates.py`（`importlib`），用**第三条路径**现算两个集合，
      再与输出行里的两个数对。⇒ 派生器写错、或 shell 侧写错，本用例都会红。
    ★ 同时钉住 `pre-commit ⊆ run_all_gates`（否则"另有 N 道"会被**低报**，
      而低报是"差看不见"的原始形态）。
    """
    line = _visibility_line(_out(_real_tree_run()))
    want_n, want_extra = _expected_pair()
    got_n, got_extra = _numbers(line)
    assert (got_n, got_extra) == (want_n, want_extra), (
        f"两个数与实际集合不符：报 ({got_n}, {got_extra})，独立现算 ({want_n}, {want_extra})\n{line}"
    )
    p = set(_gates_of_pre_commit(PRE_COMMIT.read_text(encoding="utf-8")))
    g = set(_gates_of_run_all_gates())
    assert not (p - g), (
        f"本树有门禁**未登记**进 run_all_gates：{sorted(p - g)} —— "
        f"此时「另有 N 道」会被低报（`G-07`）"
    )
    assert int(got_n) + int(got_extra) == len(g), (
        f"两数之和 {got_n}+{got_extra} ≠ |GATES|={len(g)} —— 只有 `P ⊆ G` 时才该相等"
    )


# ───────────────────────── ② 增/删一道门禁 ⇒ 两个数自动跟着变 ─────────────────────────


def _run_in_tree(root: Path, env: dict[str, str] | None = None) -> str:
    res = _run(["sh", str(root / "system" / "scripts" / "ops" / "pre-commit.sh")], root, env)
    return _out(res)


def test_adding_a_registered_gate_changes_both(tmp_path: Path) -> None:
    """★ 验收②（提升一道集成门禁到提交时）：本树门禁 `14→15`、「另有」`13→12`。

    ★ 桩齐 14 道 ⇒ `rc=0`，所以本用例同时证明"加一道**已登记**的门禁"不会带来 ⚠。
    """
    root = _make_tree(tmp_path, stubs=_ALL_STUBS)
    before = _numbers(_visibility_line(_run_in_tree(root)))
    assert before == _expected_pair(), f"夹具树基线不符合独立现算：{before} vs {_expected_pair()}"

    # 提升 `traceback.py`（它在 run_all_gates::GATES 里、此前**不在** pre-commit 里）为提交时门禁
    script = root / "system" / "scripts" / "ops" / "pre-commit.sh"
    text = script.read_text(encoding="utf-8")
    anchor = '# ★ 卡 13-O：先把「输入错误」结掉'
    assert text.count(anchor) == 1, "锚点不唯一"
    script.write_text(
        text.replace(
            anchor,
            'run_gate "traceback.py" "$CODE_ROOT/scripts/trace/traceback.py" "$CODE_ROOT"\n\n' + anchor,
            1,
        ),
        encoding="utf-8",
    )
    (root / "system" / "scripts" / "trace").mkdir(parents=True, exist_ok=True)
    (root / "system" / "scripts" / "trace" / "traceback.py").write_text(
        "import sys\nsys.exit(0)\n", encoding="utf-8"
    )
    after_line = _visibility_line(_run_in_tree(root))
    after = _numbers(after_line)
    assert int(after[0]) == int(before[0]) + 1, f"本树门禁数没跟着变：{before} → {after}"
    assert int(after[1]) == int(before[1]) - 1, f"「另有」没跟着变：{before} → {after}"
    assert "未登记" not in after_line, after_line


def test_removing_a_gate_changes_both(tmp_path: Path) -> None:
    """★ 验收②（反向）：删掉一道提交时门禁 ⇒ 本树门禁 `14→13`、「另有」`13→14`。"""
    root = _make_tree(tmp_path, stubs=_ALL_STUBS)
    before = _numbers(_visibility_line(_run_in_tree(root)))

    script = root / "system" / "scripts" / "ops" / "pre-commit.sh"
    text = script.read_text(encoding="utf-8")
    stripped = re.sub(r'\nrun_gate "graph_integrity_guard".*\n', "\n", text, count=1)
    assert stripped != text, "锚点没命中"
    script.write_text(stripped, encoding="utf-8")

    after = _numbers(_visibility_line(_run_in_tree(root)))
    assert int(after[0]) == int(before[0]) - 1, f"本树门禁数没跟着变：{before} → {after}"
    assert int(after[1]) == int(before[1]) + 1, f"「另有」没跟着变：{before} → {after}"


def test_unregistered_gate_is_flagged(tmp_path: Path) -> None:
    """★ 危险方向：本树有、`run_all_gates` 没有 ⇒ 必须报 `⚠ 未登记`（`G-07` 两处口径不一致）。

    ★ 此时「另有」**不许变** —— 因为集合差**真的**没变。
      若实现写成"机械地 `|G| - N`"，这里会错报成 `N+1` 与 `另有 - 1`，
      把"**两处口径不一致**"伪装成"**差变小了**"（`G-62`：结算通道与事实不同源）。
    """
    root = _make_tree(tmp_path, stubs=_ALL_STUBS)
    before = _numbers(_visibility_line(_run_in_tree(root)))

    script = root / "system" / "scripts" / "ops" / "pre-commit.sh"
    text = script.read_text(encoding="utf-8")
    anchor = '# ★ 卡 13-O：先把「输入错误」结掉'
    script.write_text(
        text.replace(
            anchor,
            'run_gate "zz_fake_guard" "$CODE_ROOT/scripts/checks/zz_fake_guard.py" "$CODE_ROOT"\n\n'
            + anchor,
            1,
        ),
        encoding="utf-8",
    )
    line = _visibility_line(_run_in_tree(root))
    n, extra = _numbers(line)
    assert int(n) == int(before[0]) + 1, line
    assert int(extra) == int(before[1]), (
        f"集合差**没变**却把「另有」改了 ⇒ 实现是机械地 `|G|-N`，会把不一致伪装成差变小：{line}"
    )
    assert "未登记" in line and "zz_fake_guard" in line, f"未登记的门禁没被点名：{line}"


# ───────────────────── ③ 全道 PASS 不受影响 + 我修掉的那处静默缺陷 ─────────────────────


def test_real_tree_still_passes_with_the_new_line() -> None:
    """★ 验收③：真实树**全道 PASS**，且新行在位、`阻断`/`INPUT-ERROR` 均 0 次。

    ★ 这是唯一一条**跑真实 14 道门禁**的用例（因此较慢）—— 验收③说的就是真实树。
    """
    res = _real_tree_run()
    text = _out(res)
    line = _visibility_line(text)
    assert res.returncode == 0, f"真实树没全道 PASS（rc={res.returncode}）：\n{text[-3000:]}"
    assert "阻断" not in text, f"真实树出现阻断：\n{text[-3000:]}"
    assert "[INPUT-ERROR]" not in text, f"真实树出现输入错误：\n{text[-3000:]}"
    assert "pre-commit ✓ 全部门禁放行" in text, text[-800:]
    assert line.count("另有") == 1, line


def test_relative_invocation_does_not_silently_count_zero(tmp_path: Path) -> None:
    """★★ 我修掉的那处**静默缺陷**：相对路径调用时，门禁数**不得静默变成 `0`**。

    ★ 实测回放（改前，本树 `0582804`，cwd=`system/scripts/ops`、`sh pre-commit.sh`）：
      `done < "$0"` 重定向失败 ⇒ 循环体一次都没跑 ⇒ `本树门禁 0 道`，而 14 道**确实跑了**、`rc=0`。
    ★ 断言选 `!= "0"` 而不是 `== "14"`：本用例要钉的是"**不许报假数**"，
      而"数对"由 `test_numbers_match_the_actual_sets` 负责（`G-03`：不靠单一断言）。
    ★ 追加断言"输出里不出现 `No such file`" 才真正区分改前改后：
      改前那一行是 `pre-commit.sh: line NNN: pre-commit.sh: No such file or directory`。
    """
    root = _make_tree(tmp_path, stubs=_ALL_STUBS)
    ops = root / "system" / "scripts" / "ops"
    res = _run(["sh", "pre-commit.sh"], ops)          # ★ cwd = ops，`$0` 是**相对**的
    text = _out(res)
    line = _visibility_line(text)
    n, _ = _numbers(line)
    assert n == str(len(_ALL_STUBS)), (
        f"相对路径调用把门禁数算成了 {n}（实际 {len(_ALL_STUBS)} 道）—— "
        f"`$0` 没有在任何 `cd` 之前钉成绝对路径：\n{line}"
    )
    assert "No such file" not in text, f"相对 `$0` 的重定向失败了：\n{text[:800]}"
    assert res.returncode == 0, f"rc={res.returncode}：\n{text[-1500:]}"


def test_unknown_count_is_not_reported_as_zero(tmp_path: Path) -> None:
    """★ 计数取不到时**必须说"取不到"**，**不许报 `0 道`**（假数比不报更坏）。

    ★ 造法：`source` 本文件 ⇒ `$0` 是 `sh`，`$0` 指向的"本文件"不存在 ⇒ 派生不出来。
    """
    root = _make_tree(tmp_path, stubs=_ALL_STUBS)
    res = _run(["sh", "-c", f'. "{root / "system" / "scripts" / "ops" / "pre-commit.sh"}"'], root)
    line = _visibility_line(_out(res))
    assert "本树门禁 0 道" not in line, f"取不到时报了 `0 道`（假数）：\n{line}"
    assert "取不到" in line, f"取不到时却没写「取不到」：\n{line}"


# ───────────────────────── 派生器本身（`gate_set_diff.py`） ─────────────────────────


def test_deriver_missing_module_says_unavailable_not_zero() -> None:
    """`run_all_gates.py` 不在本树 ⇒ 输出"**取不到**"，**不是**"另有 0 道"。"""
    res = _run(
        [sys.executable, str(DERIVER), str(DERIVER.parent / "no_such_run_all_gates.py"), str(PRE_COMMIT), "14"],
        SYSTEM.parent,
    )
    text = _out(res)
    assert res.returncode == 0, f"派生器**永不阻断提交**（它只是可见性工具）：rc={res.returncode}\n{text}"
    assert "取不到" in text and "另有" not in text, text


def test_deriver_flags_cross_check_mismatch() -> None:
    """两条派生路径不一致时必须报 `⚠`（`G-06` 在**派生层**的形态）。"""
    res = _run(
        [sys.executable, str(DERIVER), str(RUN_ALL_GATES), str(PRE_COMMIT), "99"],
        SYSTEM.parent,
        {"WORKBUDDY_PY": sys.executable},
    )
    assert "两处派生不一致" in _out(res), _out(res)


def test_deriver_skips_cross_check_when_shell_count_unknown() -> None:
    """`pre-commit.sh` 自己也没数出来（传 `0`）时**不许**报"派生不一致"—— 那是**假的**不一致。"""
    res = _run(
        [sys.executable, str(DERIVER), str(RUN_ALL_GATES), str(PRE_COMMIT), "0"],
        SYSTEM.parent,
    )
    text = _out(res)
    assert "两处派生不一致" not in text, f"报了一个假的不一致：{text}"
    assert "另有" in text, text


def test_deriver_usage_error_is_exit_2() -> None:
    """用法错误 = **输入错误**（`G-01`：`2`），不是"违规"（`1`）。"""
    res = _run([sys.executable, str(DERIVER), "only-one-arg"], SYSTEM.parent)
    assert res.returncode == 2, f"实得 {res.returncode}：{_out(res)}"


# ───────────────────────── 防"本文件的断言退化成恒真"（`G-03`） ─────────────────────────


def test_emitted_literals_are_still_in_the_sources() -> None:
    """★★ 上面每条断言都读**字面量**（`本树门禁 … 道` / `另有 … 道`）。

    ★ 若那些字面量被改写，所有断言会**永远成立**（测试全绿而"差"再也没人查）。
    ★ 故此处读**发射语句的词法开头**，而**不是** token 本身 ——
      `#96` 上一轮我正是在这里翻车：元断言读 token，而源码**注释里为留证据逐字引了那个 token**
      ⇒ 删掉真发射行后元断言仍 `1 passed`（`K10` 实测）。注释里不会出现 `echo "…` / `f"…`。
    """
    pc_src = PRE_COMMIT.read_text(encoding="utf-8")
    assert 'echo "pre-commit: 判据树 HEAD=' in pc_src, (
        "可见性行的发射语句不在了 ⇒ `_visibility_line` 的断言全部退化"
    )
    assert "本树门禁 ${_gate_count_text} 道" in pc_src, (
        "本树门禁数的插值不在了 ⇒ `_numbers` 的第一项退化"
    )
    assert '"**取不到**（⚠ 不得当作 0）"' in pc_src, (
        "「取不到」那一支不在了 ⇒ `test_unknown_count_is_not_reported_as_zero` 退化"
    )

    deriver_src = DERIVER.read_text(encoding="utf-8")
    assert '另有 {len(extra)} 道（集成时跑）' in deriver_src, (
        "「另有」的发射式不在了 ⇒ `_numbers` 的第二项退化"
    )
    assert '⚠ 本树另有 {len(only_here)} 道**未登记**' in deriver_src, (
        "「未登记」的发射式不在了 ⇒ `test_unregistered_gate_is_flagged` 退化"
    )


def test_sources_are_runnable() -> None:
    """元断言：上面全部用例都建立在"这三个文件能被 `sh` / `python` 跑起来"之上。"""
    syntax = subprocess.run(["sh", "-n", str(PRE_COMMIT)], capture_output=True, text=True, check=False)
    assert syntax.returncode == 0, f"pre-commit.sh 语法非法：{syntax.stderr}"
    for path in (RUN_ALL_GATES, DERIVER):
        res = _run([sys.executable, "-c", f"import ast,pathlib;ast.parse(pathlib.Path(r'{path}').read_text())"], SYSTEM.parent)
        assert res.returncode == 0, f"{path} 语法非法：{_out(res)}"
    assert shutil.which("git") is not None, "本文件的多个用例依赖真 git"
