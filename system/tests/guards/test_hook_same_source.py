"""卡 13-O：钩子同源化 —— 两条**可判红**反例（`G-61`）。

## 这两条用例在守什么

`.git/hooks/pre-commit`（薄壳）与 `system/scripts/ops/pre-commit.sh`（判据清单）之间的
**同源关系**，以及"门禁脚本不在被检树"这件事**必须与"违规"可区分**。

| 用例 | 断言 | **判红条件**（把实现改回去就红） |
|---|---|---|
| `test_install_hooks_prints_a_same_source_shell` | `--print` 的正文**不含** `exec sh "/…` 形式的绝对路径、含 `rev-parse --show-toplevel`、含 `unset GIT_DIR`、含 `[INPUT-ERROR]`/`exit 2`、`sh -n` 通过 | 正文改回 `exec sh "/Users/…/pre-commit.sh"` ⇒ "不含绝对路径"失败（实测 E4：**只回退那一行**即可红） |
| `test_input_error_is_distinguishable_from_violation` | (a) 脚本全缺 ⇒ 含 `[INPUT-ERROR]`、**不含** `阻断`、**不含** `can't open file`、`exit=2`；<br>(b) 脚本齐、其中一道 `exit 1` ⇒ 含 `阻断`、`exit=1` | 去掉 `pre-commit.sh` 的输入预检 ⇒ (a) 变 `exit=1` 且报"阻断" ⇒ 失败 |
| `test_check_detects_drift_between_installed_hook_and_template` | 未安装 ⇒ `2`；刚装完 ⇒ `0`；把装上的钩子改一个字 ⇒ `1` 且**打得出差异** | `--check` 只 `exit 0`（不做 `cmp`）⇒ 第 ③ 步拿到 `0` ⇒ 失败 |
| `test_gate_script_list_is_parseable`（防真空） | 清单能被解析、≥10 条、无重复、全是 `.py` | 解析式失效 ⇒ 上面那条用例静默空跑（`G-03`） |

## `Q1 / Q6` 自答（本文件自己的两条必问项，见 `CONVENTIONS.md §5.2`）

- **Q1（反事实）**：把"门禁脚本缺失"这一情形放进 (a) —— 若实现是旧的，输出是
  `python: can't open file … [Errno 2]` + `阻断` + `exit=1`；现在是 `[INPUT-ERROR]` + `exit=2`。
  **输出必然不同** ⇒ 断言有判别力（不是恒真）。
- **Q6（同形构造）**：两个语义不同的输入 ——
  ①**判据与对象不同源**（缺脚本，改代码无用）②**代码真的违规**（脚本在、判据命中）——
  旧实现两者**输出同形**（都报 `阻断` + `exit 1`，见 `G-61` / `G-01`）；
  本用例正是把这两者**钉成必须不同**（`exit 2` vs `exit 1`、`[INPUT-ERROR]` vs `阻断`）。
  ★ 同一问法用在用例 4：**未安装 / 装好一致 / 装好但漂移** 三种态
  —— 若 `--check` 只回 `0`，三态同形（都"通过"）⇒ 那正是方向②**零可观测**的老样子。
  用例 4 末尾的 `{2, 0, 1}` 反向对照就是在钉"三态必须可分"。
- **Q8（缺口在哪）**：本节有机器强制的只有**薄壳正文形态**（用例 1）、**退出码契约**（用例 2）、
  **漂移可分**（用例 4）。**没有**机器强制的是：①方向②（落后树少跑新门禁）**不自动报警**；
  ②"装上的钩子"是否真被 git 调用（本文件不装、不调真钩子）—— 如实登记，不算已验证（`G-03`）。

## 夹具落在系统临时目录（`tmp_path`）

⇒ ① 删除不落在受管桶内（`G-60` 的 `/tmp` 低桶实测）；② 本文件**可 `--noconftest` 运行**
（`main` `261f8c9` 已采纳该零配额范式）⇒ **验证本卡不消耗任何删除预算**。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# `parents[2]`：本文件在 `<code_root>/tests/guards/` 下 → 上溯到 `system/`
# ★ 不依赖 `conftest.py`（`--noconftest` 下也成立）
SYSTEM = Path(__file__).resolve().parents[2]
INSTALL_HOOKS = SYSTEM / "scripts" / "ops" / "install_hooks.sh"
PRE_COMMIT = SYSTEM / "scripts" / "ops" / "pre-commit.sh"


def _clean_env() -> dict[str, str]:
    """把 git 的环境变量摘掉 —— 否则 `rev-parse` 会读到**外层仓库**而不是夹具树。"""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    # 固定解释器：与 `pre-commit.sh` 的 `${WORKBUDDY_PY:-}` 约定一致
    env["WORKBUDDY_PY"] = sys.executable
    return env


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=_clean_env(),
        capture_output=True,
        text=True,
        check=False,
    )


# ────────────────────────── 用例 1：薄壳必须同源 ──────────────────────────


def test_install_hooks_prints_a_same_source_shell() -> None:
    res = _run(["sh", str(INSTALL_HOOKS), "--print"])
    assert res.returncode == 0, res.stderr
    body = res.stdout

    # ① 语法必须是合法 sh（防"生成了一段跑不起来的东西"）
    syntax = subprocess.run(
        ["sh", "-n"], input=body, text=True, capture_output=True, check=False
    )
    assert syntax.returncode == 0, f"生成的薄壳语法非法：{syntax.stderr}"

    # ② ★ 核心：不得出现"exec 一个绝对路径"—— 那正是判据与对象不同源的载体
    offenders = [
        line for line in body.splitlines() if re.search(r'\bexec\s+sh\s+"/', line)
    ]
    assert not offenders, f"薄壳里出现硬编码绝对路径（判据与对象不同源）：{offenders}"

    # ③ 必须用"从 cwd 向上发现仓库"的方式取根，且必须摘掉 GIT_DIR
    assert "rev-parse --show-toplevel" in body
    assert "unset GIT_DIR" in body, "钩子里 git 已导出 GIT_DIR ⇒ 不摘掉会把 cwd 当仓库根"

    # ④ 必须显式把"判据根本身不在被检树"报成**输入错误**（`G-61`）
    assert "[INPUT-ERROR]" in body
    assert "exit 2" in body


# ────────────────────── 用例 2：输入错误 vs 违规，必须可区分 ──────────────────────

_GATE_RE = re.compile(r'run_gate\s+"[^"]*"\s+"\$CODE_ROOT/(?P<rel>[^"]+)"')


def _gate_scripts() -> list[str]:
    """**从 `pre-commit.sh` 自身解析**门禁脚本清单（不硬编码 —— 加门禁时本用例自动跟上）。"""
    text = PRE_COMMIT.read_text(encoding="utf-8")
    rels = [m.group("rel") for m in _GATE_RE.finditer(text)]
    assert len(rels) >= 10, f"只解析到 {len(rels)} 条门禁，解析式可能已失效：{rels}"
    return rels


def _make_tree(tmp_path: Path, stubs: dict[str, str]) -> Path:
    """造一棵"像仓库"的临时树：git init + 真 `pre-commit.sh` + 指定的门禁桩。"""
    root = tmp_path / "tree"
    (root / "system" / "scripts" / "ops").mkdir(parents=True)
    (root / "system" / "scripts" / "checks").mkdir(parents=True)
    (root / "system" / "scripts" / "graph").mkdir(parents=True)
    (root / "system" / "scripts" / "ops" / "pre-commit.sh").write_bytes(
        PRE_COMMIT.read_bytes()
    )
    for rel, code in stubs.items():
        target = root / "system" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8")
    init = _run(["git", "init", "-q", str(root)])
    assert init.returncode == 0, init.stderr
    return root


def _run_pre_commit(root: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        ["sh", str(root / "system" / "scripts" / "ops" / "pre-commit.sh")], cwd=root
    )


def test_input_error_is_distinguishable_from_violation(tmp_path: Path) -> None:
    rels = _gate_scripts()
    output_ok = "import sys\nsys.exit(0)\n"
    output_bad = "import sys\nsys.exit(1)\n"

    # ── (a) 判据与对象不同源：门禁脚本**全缺** ⇒ 输入错误（`exit 2`），**不写"阻断"** ──
    tree_a = _make_tree(tmp_path / "a", stubs={})
    res_a = _run_pre_commit(tree_a)
    combined_a = res_a.stdout + res_a.stderr

    assert res_a.returncode == 2, (
        f"缺门禁脚本应以 2（输入错误）结束，实得 {res_a.returncode}：\n{combined_a}"
    )
    assert "[INPUT-ERROR]" in combined_a, f"未报输入错误：\n{combined_a}"
    assert "阻断" not in combined_a, (
        "缺脚本被报成了「阻断」—— 这正是 G-61：把'判据不在你这个对象里'伪装成'你改坏了'"
    )
    assert "门禁脚本不在被检树" in combined_a
    # ★ 这一条**单独**钉住"输入预检"那一半（否则 `rc=2` 的映射也能产出 `[INPUT-ERROR]`，
    #   预检被删掉也不会红）：缺脚本时**根本不该去调 python**、更不该吃它的 `[Errno 2]`。
    assert "can't open file" not in combined_a, (
        "缺脚本时仍去调了 python 并吃它的 Errno 2 —— 说明**输入预检**没生效"
        "（预检应在跑门禁之前就判定，并一次性把处置写清）"
    )

    # ── (b) 对照：脚本齐（全是桩），其中**一道真返回 1** ⇒ 违规（`exit 1`）+ 明确"阻断" ──
    stubs = {rel: output_ok for rel in rels}
    bad_rel = rels[0]
    stubs[bad_rel] = output_bad
    tree_b = _make_tree(tmp_path / "b", stubs=stubs)
    res_b = _run_pre_commit(tree_b)
    combined_b = res_b.stdout + res_b.stderr

    assert res_b.returncode == 1, (
        f"真违例应以 1（违规）结束，实得 {res_b.returncode}：\n{combined_b}"
    )
    assert "阻断" in combined_b, f"真违例未报「阻断」：\n{combined_b}"
    assert "[INPUT-ERROR]" not in combined_b, (
        f"脚本齐备却报了输入错误（预检误判）：\n{combined_b}"
    )

    # ── ★ 两条路径的输出**必须不同形**（本用例的全部意义） ──
    assert (res_a.returncode, "阻断" in combined_a) != (
        res_b.returncode,
        "阻断" in combined_b,
    )


def test_gate_script_list_is_parseable() -> None:
    """防"解析式失效导致上面那条用例悄悄退化成空跑"（`G-03`：无对象不得当已验证）。"""
    rels = _gate_scripts()
    assert all(rel.endswith(".py") for rel in rels), rels
    assert len(set(rels)) == len(rels), "门禁清单里有重复项"


# ──────────────── 用例 4：钩子漂移必须可见（`T3`，`G-59` 同族） ────────────────


def test_check_detects_drift_between_installed_hook_and_template(tmp_path: Path) -> None:
    """「装上的」与「版本化的」漂移必须**可见** —— 方向②（静默失去门禁）此前零可观测通道。

    ★ 判红条件：`--check` 若只 `exit 0`（不做 `cmp`）⇒ 第 ③ 步拿到 `0`、断言失败。
    ★ 全部落在 `tmp_path`：`--git-common-dir` 在夹具树里就是 `<夹具>/.git`
      ⇒ **绝不触碰**共享的 `.../InvestSigh/.git/hooks/`。
    """
    root = _make_tree(tmp_path / "drift", stubs={})
    # `install` 模式需要真 `install_hooks.sh` + 真 `pre-commit.sh`（`_make_tree` 已放后者）
    shutil.copy(INSTALL_HOOKS, root / "system" / "scripts" / "ops" / "install_hooks.sh")
    hook = root / ".git" / "hooks" / "pre-commit"

    def check() -> subprocess.CompletedProcess[str]:
        return _run(["sh", str(INSTALL_HOOKS), "--check"], cwd=root)

    # ① 未安装 ⇒ `2`（`2`=输入错误：没有可比对的对象，不是漂移）
    res0 = check()
    assert res0.returncode == 2, f"未安装应为 2，实得 {res0.returncode}：{res0.stderr}"

    # ② 安装后 ⇒ `0`（装上的 == 模板）
    inst = _run(["sh", str(root / "system/scripts/ops/install_hooks.sh")], cwd=root)
    assert inst.returncode == 0, inst.stderr
    assert hook.exists(), f"安装未落地：{hook}"
    res1 = check()
    assert res1.returncode == 0, f"刚装完应为 0，实得 {res1.returncode}：{res1.stderr}"

    # ③ ★ 核心：把装上的钩子改一个字 ⇒ 必须报漂移（`1`）且**打得出差异**
    hook.write_text(
        hook.read_text(encoding="utf-8").replace(
            "exec sh", "exec sh  # 被谁偷偷改了"
        ),
        encoding="utf-8",
    )
    res2 = check()
    combined = res2.stdout + res2.stderr
    assert res2.returncode == 1, (
        f"装上的薄壳与模板不一致时必须报漂移（exit=1），实得 {res2.returncode}：\n{combined}"
    )
    assert "漂移" in combined
    assert "被谁偷偷改了" in combined, f"只报了'漂移'却没说清漂在哪 ⇒ 修的人无从下手：\n{combined}"

    # ★ 反向对照：`--check` 的结论**跟着对象变**（不是恒 `1` 也不是恒 `0`）
    assert {res0.returncode, res1.returncode, res2.returncode} == {2, 0, 1}

