"""`G-55` 跨载体绑定守卫的**可执行反例 + 反向对照**。

被检对象：`scripts/checks/scenario_tag_binding_guard.py`
缺陷：`rules/scenario.yaml` 的取值域与实现侧枚举**值相同、各自自洽、零绑定**
⇒ **只改一侧不会红**，漂移可无限期存在（`G-55`）。

## 为什么这些用例必须存在（不是"顺手补测"）

`G-55` 这类缺陷的特点恰恰是**"守卫看起来在工作"**：一个只打印"两侧都是 4 个 token"、
从不比较的守卫，也能写出完全相同的输出。⇒ 判据必须**可证伪**：
本文件用**真实注入**（改声明侧 / 改实现侧）证明它会红，并用**反向对照**证明红是注入引起的。

★ `施工图 §5.1 AC-04` 的口径：**注入违例 ⇒ 守卫 `exit 1`**（不是 warn）。
★ 反向对照（不改 ⇒ `exit 0`）**与注入放在同一条用例、同一份副本上** ——
  这样两次运行之间**唯一的差别就是那次注入**；分成两条用例会引入"两份副本可能有别"的杂音。
"""

from __future__ import annotations

import sys
from pathlib import Path

from conftest import SYSTEM_ROOT, run_gate_inproc

GUARD = "scripts/checks/scenario_tag_binding_guard.py"
SCENARIO_YAML = Path("rules") / "scenario.yaml"
IMPL_MODULE = Path("scripts") / "pricelayer" / "scenario_guard.py"


def _scenario_yaml(root: Path) -> Path:
    return root / SCENARIO_YAML


def _inject(path: Path, *, old: str, new: str) -> None:
    """在 `path` 里把 `old` 换成 `new`，并★**自证注入已生效**。

    ★ 为什么必须自证（本文件初版就是这么坏的）：`rules/scenario.yaml` 里那一行**带行尾注释** ——

        scenario_tags: [bear, neutral, bull, custom]   # §J.4：「情景标签体系 | 枚举 | …」

    初版按 `"… [bear, neutral, bull, custom]\\n"`（**带换行**）去替换 ⇒ **没匹配上** ⇒
    `write_text` 写回了**原文**，于是"注入"是个 **no-op**，守卫当然照样绿 ——
    而用例会以一句含糊的"期望 1 实得 0"失败，**归因指向守卫**（假缺陷）。
    ⇒ 注入型测试必须**先证明注入真的改动了输入**，否则它测的是"什么都没发生"。
    """
    text = path.read_text(encoding="utf-8")
    assert old in text, f"注入点未找到（上游文本已变？）：{old!r}"
    mutated = text.replace(old, new)
    assert mutated != text, "注入是 no-op —— 替换前后文本相同，本用例将毫无判别力"
    path.write_text(mutated, encoding="utf-8")
    assert path.read_text(encoding="utf-8") == mutated, "注入未落盘"



def test_clean_copy_passes_then_injecting_into_the_declaring_side_is_blocked(code_root: Path) -> None:
    """★ **反例 + 反向对照（同一条用例、同一份副本）**。

    | 步骤 | 输入 | 期望 |
    |---|---|---|
    | (a) 反向对照 | 副本**未改** | `exit 0`（否则门禁恒红 ⇒ 会被关掉） |
    | (b) 反例 | 往 `rules/scenario.yaml::scenario_tags` **注入一个多余 token** | `exit 1` |
    | (c) 反例 | 往实现侧枚举**删一个 token** | `exit 1` |

    ★ (b)/(c) 是**两个方向**：`G-55` 的形态是"两侧都可漂移"，
      只测一个方向的话，守卫完全可能只实现了一个方向而看起来是绿的。
    """
    path = _scenario_yaml(code_root)
    declared_line = "scenario_tags: [bear, neutral, bull, custom]"
    assert declared_line in path.read_text(encoding="utf-8"), (
        "夹具里的声明面与预期不符 —— 本用例的注入点按逐字内容定位，声明侧被改动时应当先红"
    )

    # (a) 反向对照：不改 ⇒ 绿
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 0, f"未注入时应 exit 0，实得 {code}\n{out}"
    assert "双向相等" in out, f"未报出两侧相等的事实\n{out}"

    # (b) 注入声明侧：多一个 `custom_x`
    _inject(path, old=declared_line, new=declared_line.replace("custom]", "custom, custom_x]"))
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 1, f"声明侧多出 token 时应 exit 1，实得 {code}\n{out}"
    assert "声明侧多出" in out and "custom_x" in out, f"未指出是哪一侧多出、多出什么\n{out}"


def test_injecting_into_the_implementing_side_is_blocked(code_root: Path) -> None:
    """★ 往**实现侧**注入 ⇒ `exit 1`；并证明守卫读的是**被检 `code_root`** 的实现。

    这条同时是 `_load_checked_symbols()` 设计的证伪测试：
    若守卫从**自己所在仓库**导入枚举（而不是被检 root），本注入就**不会红** ——
    那种守卫"看起来在绑定"，实际永远看着真仓库那一份，**注入测试证伪不了它**。
    """
    path = code_root / IMPL_MODULE
    # 反向对照先跑一次（同副本、注入前）
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 0, f"未注入时应 exit 0，实得 {code}\n{out}"

    _inject(path, old='    custom = "custom"\n', new="")
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 1, f"实现侧缺 token 时应 exit 1，实得 {code}\n{out}"
    assert "声明侧多出" in out and "custom" in out, (
        f"应报出「声明侧多出 ['custom']」（声明有、实现没有）\n{out}"
    )


def test_absent_or_malformed_declaration_fails_loudly(code_root: Path) -> None:
    """★ 声明面**缺键**或**退化成标量**都必须响亮失败（`exit 2`），不得真空通过。

    - 缺键：`set()` vs 非空枚举 ⇒ 若不查，报出的是"实现侧多出全部 token"，**归因错**；
    - 标量：`set("bear") == {'b','e','a','r'}` ⇒ 拿**字符集合**去和枚举比，
      "看着像在比、其实毫无意义"。这两种都要 `exit 2`（输入异常，`§八 N-2`：不静默）。
    """
    path = _scenario_yaml(code_root)
    original = path.read_text(encoding="utf-8")
    declared_line = "scenario_tags: [bear, neutral, bull, custom]"

    _inject(path, old=declared_line, new="")           # 整行删掉（键缺席）
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 2, f"声明面缺键时应 exit 2（输入异常），实得 {code}\n{out}"
    assert "scenario_tags" in out, f"未点名缺哪个键\n{out}"

    # ★ 两个臂**各自从原文出发**（不是在上一次注入的结果上继续叠加）——
    #   否则第二个臂的注入锚点已被第一个臂删掉，`_inject` 会以"注入点未找到"失败，
    #   把"形态检查没生效"这件待证的事，混成"我的测试写坏了"（实测踩到）。
    path.write_text(original, encoding="utf-8")
    _inject(path, old=declared_line, new="scenario_tags: bear")   # 退化成标量
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 2, f"声明面退化成标量时应 exit 2，实得 {code}\n{out}"
    assert "标量" in out, f"未说明形态错误\n{out}"


def test_guard_leaves_no_global_side_effects() -> None:
    """★ **无全局副作用**：跑完之后 `sys.path` 与 `scripts*` 的 `sys.modules` 必须原样。

    ★ 为什么值得单测：本守卫为了"从被检 root 读实现侧"，必须**临时**删掉 `scripts*` 的
      import 缓存并把被检 root 插到 `sys.path` 首位。而它在测试里是**进程内执行**的
      （`run_gate_inproc` 走 `runpy`）⇒ 不还原就会污染整个测试进程：
      后续检查器会从**已被删除的夹具目录**导入，引发一批与本守卫毫无关系的失败
      （`schema_sync_guard._load_builder` 的 docstring 记录的正是这次实测事故）。
      **带全局副作用的加载器必须自己收尾**，这条把"必须"变成可执行的。

    本用例用真仓库 `SYSTEM_ROOT` 作 `code_root`：守卫全程只读（`--no-report`），
    且**不起夹具副本** ⇒ 不增加 `guards` 批的夹具成本（该批已逼近超时，见报告）。
    """
    scripts_before = {
        n: m for n, m in sys.modules.items() if n == "scripts" or n.startswith("scripts.")
    }
    path_before = list(sys.path)

    code, out = run_gate_inproc(GUARD, SYSTEM_ROOT)
    assert code == 0, f"真仓库上应 exit 0，实得 {code}\n{out}"

    scripts_after = {
        n: m for n, m in sys.modules.items() if n == "scripts" or n.startswith("scripts.")
    }
    assert set(scripts_after) == set(scripts_before), (
        "`scripts*` 的 sys.modules 条目集合被改变了 —— 加载器没有收尾\n"
        f"多出 {sorted(set(scripts_after) - set(scripts_before))}；"
        f"缺失 {sorted(set(scripts_before) - set(scripts_after))}"
    )
    assert all(scripts_after[n] is m for n, m in scripts_before.items()), (
        "`scripts*` 的模块对象被替换了（不是原来那批）—— 说明缓存被重建过"
    )
    assert sys.path == path_before, "`sys.path` 未还原"


def test_gate_is_registered_in_both_places() -> None:
    """★ `G-07`：本守卫必须**同时**进 `run_all_gates.py::GATES` 与 `pre-commit.sh`。

    ★ 为什么需要这条断言：`G-07`（"门禁必须两处同时登记"）此前**没有机器绑定**
      —— 只进一处 = "提交时放行、CI 时拦"（或反之），两处口径不一致本身就是同一族的缺陷。
      本断言把**本守卫**的这条义务变成可执行的（成本 = 两次读文件，不起夹具）。

    ★ 我**没有**顺手写一条"`GATES` 里的每条都必须进 `pre-commit.sh`"的通用规则：
      `pre-commit.sh` 只跑 11 道（"施工纪律"子集）而 `GATES` 有 25 条，
      **两者的包含关系是设计决定、不是缺陷** ⇒ 通用规则需要一次裁定，
      不该由本卡凭"看起来更严"自行发明（那会当场造出一条假红的门禁）。
    """
    gates_src = (SYSTEM_ROOT / "scripts" / "ops" / "run_all_gates.py").read_text(encoding="utf-8")
    hook_src = (SYSTEM_ROOT / "scripts" / "ops" / "pre-commit.sh").read_text(encoding="utf-8")
    assert "scenario_tag_binding_guard.py" in gates_src, "未登记进 run_all_gates.py::GATES"
    assert "scenario_tag_binding_guard.py" in hook_src, "未登记进 pre-commit.sh"
