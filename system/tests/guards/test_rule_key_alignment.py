"""`13-pre` 方向 1「键对齐守卫」的**可执行反例 + 反向对照 + 白名单机器绑定**。

被检对象：`scripts/checks/rule_key_alignment_guard.py`
缺陷（`R5` 的「单向缺失即红」）：代码 `dict.get()` 读一个 `rules/*.yaml` 里**不存在**的键时，
`None` 被 `or ""` / `or {}` / `or 0` 洗成**看起来合法**的值 ⇒ 「这条规则其实没被读」
在**任何输出里都不可见**。

## 为什么这些用例必须存在（不是"顺手补测"）

本守卫的形态是「**压根没读到，却毫无症状**」。一个只会打印"扫描了 113 个 py 文件"、
从不真去比对键的守卫，也能产出**完全相同**的 stdout。⇒ 判据必须**可证伪**：
本文件用**两个方向**的真注入证明它会红：

| 方向 | 注入点 | 意图 |
|---|---|---|
| A（读的一侧） | 把代码读的键改成 `rules/` 里没有的 | 代码漂移必须红 |
| B（声明的一侧） | 把 `rules/*.yaml` 里被读的键改名 | 声明漂移必须红 |

★ **只测一个方向是不够的**：守卫完全可能拿一份**快照/自己的常量**当"声明面"（那样只有 A 会红），
或只做"声明的键都有人在读"（相反方向）。B 用来证伪"声明面不是被检 `code_root` 的真实文件"。

★ `施工图 §5.1 AC-04` 的口径：**注入违例 ⇒ 守卫 `exit 1`**（不是 warn）。
★ 反向对照（不改 ⇒ `exit 0`）**与注入放在同一份副本上**，两次运行之间唯一的差别就是那次注入。
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest
from conftest import SYSTEM_ROOT, run_gate_inproc

GUARD = "scripts/checks/rule_key_alignment_guard.py"
RULES_READER = Path("scripts") / "valuelayer" / "_rules.py"
BASELINE_YAML = Path("rules") / "baseline.yaml"

#: `_rules.py` 里那行"读 `thresholds` 分组"——**读的一侧**的注入锚点。
_READ_ANCHOR = "    group = doc.get(THRESHOLDS_GROUP)\n"
#: `rules/baseline.yaml` 的 `thresholds:` 行 ——**声明的一侧**的注入锚点。
_DECL_ANCHOR = "\nthresholds:\n"
#: 一个**不存在**的规则文件（用来证伪"引用了不存在的规则文件不会被拦"）。
_ABSENT_REF_ANCHOR = 'METRIC_SETS_RELPATH = "rules/metric-sets.yaml"\n'


def _inject(path: Path, *, old: str, new: str) -> None:
    """在 `path` 里把 `old` 换成 `new`，并★**自证注入已生效**。

    ★ 为什么必须自证（`test_scenario_tag_binding.py` 踩过、本文件沿用）：带**行尾注释**的那一行
      用"带换行"的锚点去替换会**匹配不上** ⇒ `write_text` 写回原文 ⇒ **注入是 no-op**，
      守卫照样绿，而用例以一句含糊的"期望 1 实得 0"失败、**归因指向守卫**（假缺陷）。
      ⇒ 注入型测试必须**先证明注入真的改动了输入**，否则它测的是"什么都没发生"。
    """
    text = path.read_text(encoding="utf-8")
    assert old in text, f"注入点未找到（上游文本已变？）：{old!r}"
    mutated = text.replace(old, new)
    assert mutated != text, "注入是 no-op —— 替换前后文本相同，本用例将毫无判别力"
    path.write_text(mutated, encoding="utf-8")
    assert path.read_text(encoding="utf-8") == mutated, "注入未落盘"


# ─────────────────────── ① 干净 + 覆盖面（同一份副本，后续臂的基准） ───────────────────────


def test_clean_copy_passes_and_reaches_the_real_reader_sites(code_root: Path) -> None:
    """反向对照 + **覆盖面**：干净副本必须 `exit 0`，且四类**解析形态**各有落点。

    ★ 为什么覆盖面要写进断言（而不是只在报告里描述）：本守卫是"**宁可少报**"的设计，
      它最容易的退化不是误报、而是**静默地一条也解析不出来**（那样输出里只剩
      `resolved_key_reads: 0` 与 `RESULT: PASS`，看上去完全正常）。
      下面四个文件**各自代表一种解析形态**，任一种退化都会让对应那行 `reads::…` 消失：

      | 文件 | 它代表的形态 |
      |---|---|
      | `scripts/benchmark/return_guard.py` | `path = root / "rules" / "x.yaml"`（`/` 拼接）+ `yaml.safe_load(path.read_text())` |
      | `scripts/valuelayer/_rules.py` | 模块常量 + `_load_mapping` 薄包装 + **一层组别名** |
      | `scripts/pricelayer/scenario_guard.py` | 局部**路径变量**（`path = Path(root) / SCENARIO_YAML`）+ `_cached_yaml` |
      | `scripts/orchestrate/pipeline.py` | `load_yaml("rules/x.yaml", root)` 字面量 + **链式 `.get`** |

      ★ 我**不**断言具体条数（如 `resolved_key_reads == 47`）：那是**写死的计数**，
        它随 `scripts/**` 的任何一次正常改动而变红 —— 本项目刚在卡 13-J 处理过
        "5 个写死计数改派生"（同族）。断言"**哪些文件被解析到**"才是稳定的性质。
    """
    code, out = run_gate_inproc(GUARD, code_root)

    assert code == 0, f"干净副本上应 exit 0，实得 {code}\n{out}"
    assert "RESULT: PASS" in out, f"未见 PASS 结论\n{out}"

    for rel in (
        "scripts/benchmark/return_guard.py",
        "scripts/valuelayer/_rules.py",
        "scripts/pricelayer/scenario_guard.py",
        "scripts/orchestrate/pipeline.py",
    ):
        assert f"reads::{rel}" in out, (
            f"未解析到 {rel} 的任何规则键读取 —— 该形态的解析退化了"
            f"（它会让守卫**静默地**少报，而输出看上去完全正常）\n{out}"
        )

    # 覆盖面**缺口**必须可见（`G-03`）：两个计数都要出现在输出里，哪怕为 0。
    assert "unresolved_reads:" in out, f"未输出覆盖面缺口计数（跳过不是通过）\n{out}"
    assert "ambiguous_doc_vars:" in out, f"未输出多值返回盲区计数（盲区必须可见）\n{out}"
    # `口径 13` 第 3 条：白名单与被检集合的**比值**必须输出。
    assert "白名单比值" in out, f"未输出白名单比值（口径 13 第 3 条）\n{out}"


# ─────────────────────── ② 两个注入方向（读的一侧 / 声明的一侧） ───────────────────────


def test_injecting_at_the_reading_side_is_blocked(code_root: Path) -> None:
    """★ 方向 A：把**代码**读的键改成 `rules/baseline.yaml` 里没有的 ⇒ `exit 1`。"""
    path = code_root / RULES_READER

    code, out = run_gate_inproc(GUARD, code_root)          # 反向对照（同副本、注入前）
    assert code == 0, f"未注入时应 exit 0，实得 {code}\n{out}"

    _inject(path, old=_READ_ANCHOR, new='    group = doc.get("thresholds_bogus")\n')
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 1, f"代码读了不存在的键时应 exit 1，实得 {code}\n{out}"
    assert "rules/baseline.yaml::thresholds_bogus" in out, (
        f"应点名「哪个文件的哪个键不存在」\n{out}"
    )
    assert "静默" in out, f"应说明后果是**静默失效**（不是响亮失败）\n{out}"


def test_injecting_at_the_declaring_side_is_blocked(code_root: Path) -> None:
    """★ 方向 B：把**声明**里被读的键改名 ⇒ `exit 1`（证明声明面是**被检 root 的真文件**）。

    ★ 这条同时证伪"守卫拿了快照 / 自己内置一份键表"：那种实现下，改 `code_root` 里的
      `rules/*.yaml` **不会红** —— 它永远看着别处那一份。
    """
    path = code_root / BASELINE_YAML

    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 0, f"未注入时应 exit 0，实得 {code}\n{out}"

    _inject(path, old=_DECL_ANCHOR, new="\nthresholdz:\n")
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 1, f"声明面改了键名时应 exit 1，实得 {code}\n{out}"
    assert "rules/baseline.yaml::thresholds" in out, (
        f"应点名被读而不存在的键是 `thresholds`\n{out}"
    )


# ─────────────────────── ③ 断言①（引用的规则文件必须存在）+ 输入异常 ───────────────────────


def test_unregistered_absent_rule_file_is_blocked(code_root: Path) -> None:
    """★ 引用一个**没登记**的不存在规则文件 ⇒ `exit 1`；**已登记**的 ⇒ 绿（`口径 13`）。

    ★ 为什么这条断言必须有两臂：若只有"缺文件就红"，`rules/transmission.yaml` /
      `rules/budget.yaml`（**按设计刻意未安装**，值待冻结）会让门禁**恒红** ⇒
      误报刷屏 ⇒ 门禁被关掉（本项目铁律）。若只有白名单，则**任何**拼错的规则文件名
      都会被"反正有白名单"盖过去。⇒ 两臂同时存在，白名单才不是避难所。
    """
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 0, f"未注入时应 exit 0（已登记的两条待安装文件不得恒红），实得 {code}\n{out}"
    # ★ 计数**派生自豁免表**（不写死 2）：若某条登记已无人引用（欠账其实已消），
    #   这里的读数会小于表长 ⇒ 用例变红 ⇒ 逼人把那条从表里撤掉（`口径 13` 的过期机制同族）。
    from scripts.checks import rule_key_alignment_guard as G

    registered = len(G.KNOWN_ABSENT_RULE_FILES)
    assert f"whitelisted_absent_rule_files: {registered}" in out, (
        f"应如实报出「{registered} 条已登记的待安装规则文件」计数\n{out}"
    )
    assert "待安装规则文件" in out, f"每条豁免必须打出 note（不静默）\n{out}"

    # ── 注入：新增一个**没登记**的规则文件引用 ──
    path = code_root / RULES_READER
    _inject(
        path,
        old=_ABSENT_REF_ANCHOR,
        new=_ABSENT_REF_ANCHOR + '_NOT_REGISTERED_RULE = "rules/nosuch-rules-xyz.yaml"\n',
    )
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 1, f"引用了没登记的不存在规则文件时应 exit 1，实得 {code}\n{out}"
    assert "rules/nosuch-rules-xyz.yaml" in out, f"应点名那个不存在的文件\n{out}"
    assert "KNOWN_ABSENT_RULE_FILES" in out, (
        f"应告诉读者「刻意不安装」要登记到哪里（不然下一个人只能把它改成白名单）\n{out}"
    )


def test_input_errors_are_exit_2_and_never_a_pass(code_root: Path) -> None:
    """★ 两种**输入异常**都必须 `exit 2`（"我没法判"），**不得**报成"通过"（`G-03`）。

    | 臂 | 输入 | 为什么不能算通过 |
    |---|---|---|
    | A | 根下**没有 `rules/`** | 断言②（键对齐）此时**无对象可比** —— 报 0 等于把"没检查"说成"检查过" |
    | B | `scripts/**` 里有**无法解析的 `.py`** | 该文件**根本没被扫**，而输出里一切看起来正常 |

    ★ **为什么 A 不用 `shutil.rmtree(code_root / "rules")` 造输入**（实测踩到）：
      宿主的**批量删除预算是「回合级 + 全流共享」**资源（`CONVENTIONS.md::V-09`、缺口 `G-60`）。
      夹具 teardown 本身就要删一份副本；用例再删一次 `rules/`（14 个文件）**是同一份预算上的第二次消费**。
      实测：预算耗尽时 `rmtree` 直接被拒（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`）⇒ 本用例以
      `F` 失败，而**失败原因与守卫毫无关系**（"假缺陷淹没真违规"的经典形态）。
      ⇒ 改成指向一个**本来就没有 `rules/` 的根**（`code_root/views`）：同样证明"缺声明面 ⇒ exit 2"，
        且**零删除**、与宿主配额解耦。

    ★ **为什么 B 必须存在**：本守卫初版写的是 `except SyntaxError: continue`
      —— 被 `no_placeholder_guard` 的 `SWALLOW_EXCEPTION_CONTINUE` **当场拦下**（那条判据抓得对：
      跳过扫不了的文件 = 该文件没被检查，而输出里看不出来）。本臂把"改响亮失败"这件事
      钉成可执行的：**再有人改回 `continue`，这里就会红**。
    """
    # ── 臂 A：声明面不在 ──
    bare_root = code_root / "views"          # `_ENSURE_DIRS` 保证存在；它下面没有 `rules/`
    assert not (bare_root / "rules").exists(), (
        "本用例的前提是「该根没有 rules/」，前提不成立则测的是别的东西"
    )
    code, out = run_gate_inproc(GUARD, bare_root)
    assert code == 2, f"缺少 rules/ 时应 exit 2（输入异常），实得 {code}\n{out}"
    assert "rules" in out, f"未点名缺的是 rules/\n{out}"

    # ── 臂 B：扫到无法解析的源码（★ 与臂 A 同一个 `code_root`，省一份夹具）──
    broken = code_root / RULES_READER
    _inject(
        broken,
        old="from __future__ import annotations\n",
        new="from __future__ import annotations\ndef broken(:\n",
    )
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 2, f"源码无法解析时应 exit 2（输入异常），实得 {code}\n{out}"
    assert "无法解析" in out, f"应说清原因不是「违例」而是「我没法判」\n{out}"


# ─────────────────────── ④ 白名单本身的机器绑定（`口径 13`） ───────────────────────


def test_waiver_selfcheck_rejects_incomplete_or_undated_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """★ `口径 13` 的**机器绑定**：白名单条目的**四个字段缺一**、**日期不可解析** ⇒ 响亮失败。

    ★ 为什么"白名单自己也要被测"：口径 13 逐字说白名单缺任一条就"等于把门禁关掉"。
      一个字段残缺的豁免对象，**只要还能跑**，它就已经在稀释门禁了 —— 这种状态不该
      等到某人恰好跑门禁才暴露。故 `_selfcheck_waivers()` 在**导入时**执行，
      本用例直接证伪它（否则它只是"写了但从不触发"的一段代码）。
    """
    from scripts.checks import rule_key_alignment_guard as G

    def _table(**overrides: str) -> dict[tuple[str, str], object]:
        fields = {
            "reason": "r",
            "owner": "o",
            "expected_consumer_by": "e",
            "review_by": "2026-09-30",
        }
        fields.update(overrides)
        return {("a.py", "rules/x.yaml::k"): G._Waiver(**fields)}  # type: ignore[arg-type]

    for field in ("reason", "owner", "expected_consumer_by", "review_by"):
        monkeypatch.setattr(G, "KNOWN_ZERO_KEY_READS", _table(**{field: "   "}))
        with pytest.raises(ValueError) as exc:
            G._selfcheck_waivers()
        assert field in str(exc.value), f"失败信息应点名缺哪个字段（实得 {exc.value}）"

    monkeypatch.setattr(G, "KNOWN_ZERO_KEY_READS", _table(review_by="不是日期"))
    with pytest.raises(ValueError) as exc:
        G._selfcheck_waivers()
    assert "ISO" in str(exc.value), f"日期不可解析时应说清原因（实得 {exc.value}）"


def test_expiry_mechanism_is_a_deterministic_function_of_the_review_date() -> None:
    """★ `口径 13` 第 2 条：**过期机制**必须存在，且必须是 `today` 的**确定函数**。

    ★ 为什么带 `today` 入参：把"过期"写成读系统时钟，判定就变成**随时间自己变红/绿** ——
      那是"到时才炸"的判据，不是判据。本用例直接对两个日期做断言，**永远稳定**。
    ★ `review_by` **当天不算过期**（严格 `<`）：否则 `review_by` 的含义会漂移一天。
    """
    from scripts.checks import rule_key_alignment_guard as G

    all_keys = list(G.KNOWN_ZERO_KEY_READS) + list(G.KNOWN_ABSENT_RULE_FILES)
    assert all_keys, (
        "两张豁免表**都空** ⇒ 过期机制此时无对象可测；本断言在此状态下会失败，"
        "提醒：若确实全部关闭了，请把本条改成「给出一个合成的 _Waiver」再测机制本身"
    )
    review_dates = [
        w.review_by
        for w in [*G.KNOWN_ZERO_KEY_READS.values(), *G.KNOWN_ABSENT_RULE_FILES.values()]
    ]
    earliest = min(review_dates)   # ★ 派生，不写死日期
    assert G._expired_waivers(date.fromisoformat(earliest)) == [], (
        f"review_by={earliest} **当天**不应算过期（严格小于）"
    )
    expired = G._expired_waivers(date(2099, 1, 1))
    assert len(expired) == len(all_keys), (
        f"2099 年时全部 {len(all_keys)} 条豁免都应已过期，实得 {len(expired)}"
    )


# ─────────────────────── ⑤ 无全局副作用 + `G-07` 双落点登记 ───────────────────────


def test_guard_leaves_no_global_side_effects() -> None:
    """★ **无全局副作用**：跑完后 `sys.path` 与 `scripts*` 的 `sys.modules` 必须原样。

    ★ 为什么值得单测：守卫为了 `import scripts._common` 会把**自己所在仓库**插进 `sys.path`；
      而它在测试里是**进程内执行**的（`run_gate_inproc` 走 `runpy`）⇒ 不还原就会污染整个
      测试进程 —— 后续检查器会从"已被删除的夹具目录"导入，引发一批与本守卫毫无关系的
      失败（`schema_sync_guard._load_builder` 的 docstring 记录的正是这次实测事故）。

    本用例用真仓库 `SYSTEM_ROOT` 作 `code_root`：守卫全程只读（`--no-report`），
    且**不起夹具副本** ⇒ 不增加 `guards` 批的夹具成本（该批已逼近超时，见 13-F）。
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
    """
    gates_src = (SYSTEM_ROOT / "scripts" / "ops" / "run_all_gates.py").read_text(encoding="utf-8")
    hook_src = (SYSTEM_ROOT / "scripts" / "ops" / "pre-commit.sh").read_text(encoding="utf-8")
    assert "rule_key_alignment_guard.py" in gates_src, "未登记进 run_all_gates.py::GATES"
    assert "rule_key_alignment_guard.py" in hook_src, "未登记进 pre-commit.sh"
