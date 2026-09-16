"""`13-pre` 方向 2「键 → 消费者」扫描器的**结构不变量**测试。

被检对象：`scripts/checks/rule_key_consumer_scan.py`

## 为什么这里测的**不是**「它会不会红」

该脚本**按设计恒 `exit 0`、且未注册进 `GATES`/`pre-commit`** —— 依据主理人对 13-pre 方向 2 的
**硬约束 ③**：「误报率未降下来前，只允许**只报 note、不阻断**，**绝不接门禁**」。
所以"它会红"不是它的性质，**测它会不会红反而会把一条未定案的判据悄悄变成门禁**。

⇒ 这里测的是三件**它必须成立、且失效时不会发出任何声音**的事：

| # | 不变量 | 失效时的症状（为什么必须机器绑） |
|---|---|---|
| 1 | 三态**互斥且穷尽**（三类之和 = 叶键总数） | 少算的那批键**不出现在任何一态里** ⇒ 读者以为"都分类过了"。**这是"静默漏检"的教科书形态** |
| 2 | ③ 候选**逐键列出**（明细条数 = 计数） | 计数说有 91 条、明细只有 3 条 ⇒ 读者**无法复核**任何一条 |
| 3 | **恒 `exit 0`**，且输出里**写明「候选 ≠ 判词」** | 有人把"候选"读成"已判定" ⇒ 未定案的计数被当成缺陷（硬约束③的机器绑定） |
| 4 | 输入异常（根下**没有** `rules/`）⇒ `exit 2` | 折叠成 `exit 0` + "零消费者 0 条" = **把"没查到"说成"查过且没问题"**（`G-03`） |

★ 4 条都用**真实仓库 + 只读**，**不起 `code_root` 夹具**（零 `copytree` ⇒ 零删除成本）；
第 4 条用 `system/views`（本就没有 `rules/`），**零新建零删除**。
"""

from __future__ import annotations

import re

from conftest import SYSTEM_ROOT, run_gate_inproc

SCAN = "scripts/checks/rule_key_consumer_scan.py"


def _scanned(out: str, key: str) -> int:
    """从输出里取 `scanned <key>: <n>`。

    ★ **取不到就失败，不许当归零**：缺失的计数与"计数为 0"是**不同的事实**，
      前者意味着**判据没被算出来**（`G-62`）。用 `assert m` 把它变成红。
    """
    m = re.search(rf"^  scanned {re.escape(key)}: (-?\d+)$", out, re.M)
    assert m, (
        f"输出里没有 `scanned {key}` —— 该计数**没被算出来**。"
        "★ 不得当成 0（`G-62`：不可区分 ⇒ 必须让它在输出里可见）"
    )
    return int(m.group(1))


def test_tri_state_is_mutually_exclusive_and_exhaustive() -> None:
    """三类之和 = 叶键总数，且叶键 > 0。"""
    code, out = run_gate_inproc(SCAN, SYSTEM_ROOT)
    assert code == 0, out

    leaf = _scanned(out, "leaf_keys")
    assert leaf > 0, f"叶键为 0 ⇒ **无被检对象**（`G-03`：无被检对象 ≠ 已验证）。输出：{out}"

    parts = {
        "consumers_runtime_ast": _scanned(out, "consumers_runtime_ast"),
        "consumers_runtime_text": _scanned(out, "consumers_runtime_text"),
        "consumers_gate_test_schema": _scanned(out, "consumers_gate_test_schema"),
        "zero_consumer_candidates": _scanned(out, "zero_consumer_candidates"),
    }
    assert sum(parts.values()) == leaf, (
        f"三态**不穷尽**：{parts} 之和 {sum(parts.values())} ≠ 叶键 {leaf} —— "
        "差额那批键**不在任何一态里**，而输出看起来一切正常"
    )
    assert _scanned(out, "tri_state_sum_check") == leaf, (
        "脚本自证的三态和与叶键数不一致 —— 自证字段本身失效了"
    )


def test_every_candidate_is_listed_by_name() -> None:
    """③ 候选必须**逐键**列出：明细条数 = 计数。

    ★★ 本用例**同时是语料中毒探测器**（实测抓到过一次真缺陷）：跑 `tests/guards` **整目录**时，
    前面用 `code_root` 夹具的用例在 `tests/.work/<id>/` 留下**整棵 `system/` 树的副本**
    ⇒ 每个键名都能在副本里"找到消费者"⇒ ③ 候选 **91 → 0**、明细同时归零。
    ⇒ **单文件跑通过、整目录跑失败**（顺序相关）⇒ 病根在语料面。
    修法在扫描器侧（`PRUNE_DIR_NAMES` + 一条"语料面不得残留 scratch 路径"的自证 ⇒ `exit 2`）。
    """
    code, out = run_gate_inproc(SCAN, SYSTEM_ROOT)
    assert code == 0, out

    listed = [ln for ln in out.splitlines() if ln.startswith("  scanned zero::")]
    count = _scanned(out, "zero_consumer_candidates")
    assert count > 0, (
        "本树应当有候选；为 0 说明分类塌成了一态（判据失效），"
        "**或**语料被夹具副本中毒（`tests/.work/**` 里是整树副本）——"
        "两种情况都必须当场失败，不得当成「一切都好」"
    )
    assert len(listed) == count, (
        f"③ 候选计数={count} 但明细只有 {len(listed)} 条 —— "
        "计数与明细不同源 ⇒ 读者无法复核任何一条"
    )


def test_scanner_never_blocks_and_says_candidate_is_not_a_verdict() -> None:
    """恒 `exit 0`；且输出里必须**写明**「候选 ≠ 判词」（硬约束③的机器绑定）。"""
    code, out = run_gate_inproc(SCAN, SYSTEM_ROOT)
    assert code == 0, f"本脚本按设计不得阻断；实得 exit {code}。输出：{out}"
    assert _scanned(out, "zero_consumer_candidates") > 0, (
        "这条用例的前提是「有候选」；无候选时它测的是别的东西"
    )
    for needle in ("候选", "判别力", "不阻断"):
        assert needle in out, (
            f"输出里缺 {needle!r} —— 「③ 是候选不是判词」这条**必须**出现在输出里，"
            "否则读者会把候选读成已判定（硬约束③）"
        )
    assert "口径 5" in out, "必须点名判据的出处（`口径 5`，batch13_taskbook.md:521-525）"


def test_missing_rules_dir_is_exit_2_not_a_pass() -> None:
    """根下没有 `rules/` ⇒ `exit 2`（输入异常），**不得**折叠成「零消费者 0 条」。

    ★ 用 `system/views`：它**本来就没有** `rules/` ⇒ **零新建零删除**，
      且与本会话宿主的批量删除配额**解耦**（配额已越顶，任何删除都会被拒）。
    """
    bare_root = SYSTEM_ROOT / "views"
    assert not (bare_root / "rules").exists(), (
        "本条用例的前提是「该根没有 rules/」，前提不成立则测的是别的东西"
    )
    code, out = run_gate_inproc(SCAN, bare_root)
    assert code == 2, (
        f"缺 `rules/` 必须报输入异常（`exit 2`），实得 exit {code}。"
        f"★ 若写成 exit 0，就把「**没查到**」说成了「查过且没问题」（`G-03`）。输出：{out}"
    )
