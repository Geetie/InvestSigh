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
| 2 | ③ 候选**逐键列出**（明细条数 = 计数） | 计数说有 92 条、明细只有 3 条 ⇒ 读者**无法复核**任何一条 |
| 3 | **恒 `exit 0`**，且输出里**写明「候选 ≠ 判词」** | 有人把"候选"读成"已判定" ⇒ 未定案的计数被当成缺陷（硬约束③的机器绑定） |
| 4 | 输入异常（根下**没有** `rules/`）⇒ `exit 2` | 折叠成 `exit 0` + "零消费者 0 条" = **把"没查到"说成"查过且没问题"**（`G-03`） |
| 5 | **证据分级**（四级）互斥穷尽，且 `evidence_none` **逐位等于** ③ 候选数 | 两级轴各走各的 ⇒ "91/92 这个数有多硬"重新变回不可区分（`G-62`） |
| 6 | ③ 的**下界 / 宽松上界**都出现且有序，输出里写明**上界不是候选集** | 只报一个数 ⇒ 「都有强证据」与「几乎没有强证据」输出逐位相同（`G-62`） |
| 7 | ★ **独立方法已定性的零消费者键，不得被本扫描判成「精确读」** | 两个独立方法**互相矛盾**却都不发声 —— 这正是本卡第二轮漏掉 4 个键的形态 |
| 8 | ★ **仪器隔离**：本扫描器自身被**恰好排除一次** | 仪器给自己当消费者 ⇒ **编辑本文件就会改变读数**（自指污染，本卡第二轮实测） |

★ 8 条都用**真实仓库 + 只读**，**不起 `code_root` 夹具**（零 `copytree` ⇒ 零删除成本）；
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


def _detail_lines(out: str, prefix: str) -> list[str]:
    """取形如 `  scanned <prefix>::<file>::<dotted>: 1` 的明细行。"""
    head = f"  scanned {prefix}::"
    return [ln for ln in out.splitlines() if ln.startswith(head)]


def test_evidence_tiers_are_exhaustive_and_none_equals_candidates() -> None:
    """证据四级（精确/前缀推定/文本/无）互斥穷尽，且 `无` **逐位等于** ③ 候选数。

    ★ 四级之和 ≠ 叶键数 ⇒ 有键**没被分级**（读者会以为"都分过级了"）；
    ★ `evidence_none` ≠ ③ 候选数 ⇒ 三态与证据级**两根轴各走各的** ——
      它们本该是"同一条判据的两个出口"，不一致就意味着其中一个在说谎。
    """
    code, out = run_gate_inproc(SCAN, SYSTEM_ROOT)
    assert code == 0, out

    leaf = _scanned(out, "leaf_keys")
    exact = _scanned(out, "evidence_ast_exact")
    prefix = _scanned(out, "evidence_ast_prefix")
    text = _scanned(out, "evidence_text")
    none = _scanned(out, "evidence_none")
    cand = _scanned(out, "zero_consumer_candidates")

    assert exact + prefix + text + none == leaf, (
        f"证据四级**不穷尽**：{exact}+{prefix}+{text}+{none}={exact + prefix + text + none} "
        f"≠ 叶键 {leaf} —— 差额那批键没被分级，而输出看起来一切正常"
    )
    assert none == cand, (
        f"`evidence_none`={none} ≠ ③ 候选数={cand} —— 两级轴不同源："
        "「④无证据」与「③零消费者候选」本应是同一条判据"
    )
    assert _scanned(out, "evidence_tier_sum_check") == leaf, "脚本自证的四级和与叶键数不一致"
    assert _scanned(out, "evidence_tier_selfcheck") == 1, (
        "脚本自证的 `evidence_tier_selfcheck` 不是 1 —— 自证字段本身失效了"
    )
    # ★ 明细必须与计数同源（否则"分级"只是三个数字，无法复核任何一条）。
    for prefix_name, expected in (
        ("exact", exact),
        ("prefix", prefix),
        ("text", text),
        ("zero", cand),
    ):
        listed = _detail_lines(out, prefix_name)
        assert len(listed) == expected, (
            f"`{prefix_name}::` 明细 {len(listed)} 条 ≠ 计数 {expected} —— 计数与明细不同源"
        )
    # ★ 地板真值：`exact` 那一档必须有东西（否则"精确读"这个通道可能是死的，
    #   下面那条"独立方法定性的键不得被精确读"就会**空过**）。
    assert exact > 0, (
        "`evidence_ast_exact` 为 0 ⇒ 「精确读」这条通道什么都没产出。"
        "★ 此时本文件下面那条绑定会**空过**（`G-03`：无被检对象 ≠ 已验证）"
    )


def test_zero_candidate_is_a_range_and_the_bound_is_not_a_candidate_set() -> None:
    """③ 必须同时给出**下界**与**宽松上界**，且输出里**写明上界不是候选集**（`G-62`）。

    ★ 为什么必须绑：只报一个数时，「92 条都有强证据支撑」与
      「92 条里只有极少数有强证据支撑」**输出逐位相同** —— 读者无从判断这个数有多硬。
    """
    code, out = run_gate_inproc(SCAN, SYSTEM_ROOT)
    assert code == 0, out

    lower = _scanned(out, "zero_candidate_lower_bound")
    upper = _scanned(out, "zero_candidate_permissive_bound")
    cand = _scanned(out, "zero_consumer_candidates")
    assert lower == cand, f"下界 {lower} 与候选数 {cand} 不同源 —— 两个名字一个东西，必须相等"
    assert upper == lower + _scanned(out, "evidence_ast_prefix") + _scanned(out, "evidence_text"), (
        "宽松上界 ≠ 下界 + 前缀推定 + 文本命中 —— 上界的推导与分级计数不同源（不可复核）"
    )
    assert lower <= upper, f"下界 {lower} > 上界 {upper}，区间倒过来了"
    assert _scanned(out, "zero_candidate_permissive_permille") >= _scanned(
        out, "zero_candidate_permille"
    ), "两个千分比的大小关系与两个绝对值不一致 ⇒ 比值不是从同一对基数算出来的"
    assert "上界不是候选集" in out, (
        "输出里必须写明**上界不是候选集** —— 否则有人会把 230 当候选去追，"
        "那是硬约束 ③ 明确禁止的误报（只 note、不阻断）"
    )


#: ★★ **地板真值，来源是独立方法**（`13-G`：`ws-ch2-rules` 用全仓 `grep` + 逐键定性，
#: 不是本扫描器）—— `rules/metric-sets.yaml` 里已被证实**零消费者**的 6 个叶键。
#:
#: ★ V-10 规则 6（比的是**意图**还是**串**）：这里比的是**集合包含关系**，
#:   绑定的**意图**是「本扫描器**不得**对这 6 个键给出『有人精确读了这条路径』的证据」——
#:   因为那会与 `13-G` 的结论**直接矛盾**。两个独立方法矛盾时必须**当场爆**，不得各自沉默。
#:
#: ★ 为什么这 6 条能抓到真缺陷：本卡第二轮之前，本扫描器把这 6 个键里的
#:   `routing.{key,binding_field,metric_owner_field}` 判成「运行时 AST 有消费者」
#:   （被 `_rules.metric_set_routing()` 的 `doc.get("routing")` **前缀推定**覆盖），
#:   把 `conversion_chain_per_model_class.{hardware,cloud,software}` 判成「文本命中」
#:   （叶名是通用词）。⇒ 4 个**已确证的零消费者**被静默吞掉，输出毫无异常。
#:   ⇒ 本用例**就是那条缺陷的绊线**。
_INDEPENDENTLY_CONFIRMED_ZERO_CONSUMERS: tuple[str, ...] = (
    "metric-sets.yaml::routing.key",
    "metric-sets.yaml::routing.binding_field",
    "metric-sets.yaml::routing.metric_owner_field",
    "metric-sets.yaml::conversion_chain_per_model_class.hardware",
    "metric-sets.yaml::conversion_chain_per_model_class.cloud",
    "metric-sets.yaml::conversion_chain_per_model_class.software",
)


def test_independently_confirmed_zero_consumers_are_not_given_exact_evidence() -> None:
    """`13-G` 独立证实的 6 个零消费者键，**不得**被本扫描判成「精确读」。

    ★ 反面前提见 `_INDEPENDENTLY_CONFIRMED_ZERO_CONSUMERS` 的注释：这条绑定就是
      "4 个键被静默吞掉"那次缺陷的绊线。
    ★ 它**不**断言这 6 个键在 ③ 里 —— 它们现在落在 `prefix::` / `text::` 弱证据档，
      这正是"证据分级"要表达的东西（弱证据 ≠ 判词）。
    """
    code, out = run_gate_inproc(SCAN, SYSTEM_ROOT)
    assert code == 0, out

    # 前提：`exact::` 通道是活的（否则下面的断言会**空过**）。
    exact_lines = _detail_lines(out, "exact")
    assert len(exact_lines) == _scanned(out, "evidence_ast_exact") > 0, (
        "`exact::` 明细不完整或为 0 ⇒ 本条绑定的前提不成立（`G-03`）"
    )
    for key in _INDEPENDENTLY_CONFIRMED_ZERO_CONSUMERS:
        assert not any(ln.startswith(f"  scanned exact::{key}: ") for ln in exact_lines), (
            f"{key} 被判成「有人**精确读**了这条路径」—— 这与 `13-G` 的独立结论**直接矛盾**。"
            "★ 两个独立方法矛盾时必须当场爆（`口径 12`：不得把矛盾静默成两个数）"
        )


def test_scanner_excludes_its_own_file_from_the_corpus() -> None:
    """仪器隔离：本扫描器自身必须从语料面**恰好排除一次**（自指污染的绊线）。

    ★ 实测由来（本卡第二轮）：我在本扫描器 docstring 里举例写下 `hardware`/`cloud`/`software`
      ⇒ 它们立刻在 `scripts/**` 语料里"命中" ⇒ 3 个键从 ②门禁搬到 ①运行时（② `11 → 8`）。
      ⇒ **编辑仪器改变了被测对象的读数**，而输出看不出异常。
    ★ 若文件改名后 `SELF_RELPATH` 失效，本用例（以及脚本自身的 `exit 2` 自证）会红。
    """
    code, out = run_gate_inproc(SCAN, SYSTEM_ROOT)
    assert code == 0, out
    assert _scanned(out, "corpus_self_paths_excluded") == 1, (
        "仪器隔离没生效（应为恰好 1 次）—— 本扫描器会给自己当消费者，"
        "于是**每加一条举例说明都可能把某个键从 ③ 里挪走**，而输出看不出异常（`G-62`）"
    )
    assert "仪器隔离" in out, "输出里必须写明仪器自身被排除这件事（否则读者不知道语料面被剪过）"
