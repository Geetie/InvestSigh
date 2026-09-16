#!/usr/bin/env python3
"""`rule_key_consumer_scan.py` —— `rules/` 声明的键**有没有消费者**（13-pre 方向 2）。

```
python system/scripts/checks/rule_key_consumer_scan.py [code_root]
```

## ★★ 先读这一段，否则会误用本脚本

1. **本脚本恒返 `exit 0`**（`violations` 恒为空），一切结果只进 `scanned` / `notes`。
   依据主理人对 13-pre 方向 2 的**硬约束 ③**：「误报率未降下来前，只允许**只报 note、
   不阻断**，**绝不接门禁**」。**它也没有被注册进** `run_all_gates.GATES` / `pre-commit.sh`
   —— 所以它**没有机会**把一个未定案的计数变成红。
2. **它只做「候选生成」，不做判词。** `③ 零消费者候选` 是**候选集合**，
   **不是**「已判定的零消费者」。依据 `口径 5`（`batch13_taskbook.md:521-525`）：

   > 「有人实现了同一件事」≠「这个键有人消费」……判「某声明是否被消费」，
   > **必须用「判别力」口径（改值 ⇒ 是否变红）**，不能把「这个行为已被测试覆盖」当成「键被消费」。

   ⇒ ★ **判词不在本脚本内**。本脚本输出的是**判别力探针的输入清单**。
3. 定案那一步（**判别力探针**：在 scratch 副本上把键改成**矛盾值** ⇒ 跑门禁 + 相关测试 ⇒
   看是否变红）**有删除成本**（scratch 副本要删），必须按主理人宣布的窗口单独跑
   —— 见 `PROBE_STAGE_NOTE`。**本脚本一次删除都不做**（纯读）。

## 三态（逐键落恰一类，三类**各自计数**，`R5` + 硬约束②）

| 态 | 判据 | 它是什么意思 |
|---|---|---|
| ① **有消费者·运行时** | AST 解析出「代码从**这个** rules 文件读了**这个**键路径或其前缀」；或键名在 `scripts/**` 里以**词边界**出现 | 生产代码在读它 |
| ② **有消费者·门禁·测试·schema** | AST 命中 `scripts/checks/**`；或键名在 `tests/ schema/ registry/ config/ views/` 里词边界出现 | 只有门禁·测试·schema 在读它 |
| ③ **零消费者候选** | 上面两条都不命中 | ★ **待判别力探针定案**；未定案前**不得**当缺陷 |

★ ①② 是**互斥**的（先判 ① 再判 ②），故三者之和 = 叶键总数。

## ★★ 正交的第二根轴：「这条认定是靠什么**形状**的证据得出的」（本卡第二轮新增）

三态说的是「键被谁消费」；但**同一个 ①/②**，底下的证据**判别力差别极大**。实测（对象 = 本树）：

| 证据级 | 形状 | 实测 | 它到底证明了什么 |
|---|---|---|---|
| `evidence_ast_exact` | 方向 1 的 AST 解析出「读了**这个**叶键路径」 | **25** | 强：有代码精确读了这条路径 |
| `evidence_ast_prefix` | AST 只读到**严格前缀**（通常是整个组），本扫描**推定**子树全被消费 | **56** | 弱：**推定的**，不是观测到的 |
| `evidence_text` | 上述都不中，仅靠「键名在语料里以词边界出现过一次」 | **82** | 弱：**不区分**「代码在读它」与「夹具/文档照抄了它」 |
| `evidence_none` | 三条都不中 ⇒ 就是 ③ | **92** | 与 `zero_consumer_candidates` **必然相等**（自证） |

⇒ 于是 ③ 的**下界** 92 是「本扫描严格判定」，**宽松上界** = `leaf_keys - evidence_ast_exact` = **230**
（凡证据不是「精确读到该路径」的，都**可能**是漏报）。

★★ **这不是"我不敢下结论"，而是 `G-62` 要求的可区分枚举输出**：只报一个 `92` 时，
「92 条都有强证据支撑」与「92 条里只有极少数有强证据支撑」**输出逐位相同**。
⇒ 两个数**都**必须出现（`zero_candidate_permissive_bound` + `zero_candidate_permissive_permille`），
且**上界不是候选集**：候选仍只有 `zero_consumer_candidates` 那 92 条（硬约束 ③ 的口径不变）。

## ★ 试过并**否掉**的判据：「镜像文件」启发式（负面结果，留痕防重复）

我试过「证据文件若成组重述了同一 rules 文件的键名（`mirror` 计数），则该命中不算消费」。
**实测证明它没有判别力**：一个**真读多个键**的消费者（如 `scripts/_common.py` 读
`banned_tokens.yaml::decision_scope.*`）与一个**逐字照抄**的夹具（`tests/valuelayer/_fixtures.py`
重述 `baseline.yaml` 的 11 个键名）**同形**，阈值取 1/2/3/5/8 分别给出 83/50/23/16/3 条，
**没有一档能把"照抄"与"真读"分开**（`::version` / `::spec_anchor` 这类真读会被误标，
`financial_link.per_share_metric` 这类嫌疑会漏标）。
⇒ **不采纳**。真照抄的形状与真读的形状只能由**判别力探针**（改值 ⇒ 是否变红）分开。

## 与 `13-pre` 方向 1 的关系（**不重复实现**）

方向 1 的守卫解析**同一条信息**的**反方向**（代码读了哪个键 ⇒ 键是否存在）。
本脚本**复用它的 AST 设施**（`_analyze_module` / `_module_constants` / `_load_rule_docs`），
**绝不写第二份**「谁从哪个 rules 文件读了哪个键」的解析器 —— 两份实现必然漂移
（`G-55` / `G-06` 同族：同语义两载体彼此无绑定）。本脚本只补上「键 → 消费者」这一半。

## `口径 13` 第 3 条（比值）

输出 `zero_candidate_permille`（③ / 叶键总数，**千分比整数**）与 `leaf_keys`。
比值只作**可见性**用：它变高**不自动**等于缺陷，但**必须有人看过**。
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator

# ★ `scripts` 包引导：直接以 `python scripts/checks/xxx.py` 运行时 `sys.path[0]` 是
#   `scripts/checks/`，`import scripts._common` 会 `ModuleNotFoundError`。
#   照抄方向 1 守卫的同一段引导（**同一个坑，不各修各的**）。
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ★ 复用方向 1 守卫的 AST 设施（`scripts/checks/` 是包，见 `checks/__init__.py`）。
#   理由写在模块 docstring「与方向 1 的关系」里：**绝不写第二份解析器**。
from scripts._common import CheckReport, run_checker  # noqa: E402
from scripts.checks.rule_key_alignment_guard import (  # noqa: E402
    _analyze_module,
    _load_rule_docs,
    _module_constants,
)

RULES_DIRNAME = "rules"

#: 面 A（**运行时**）：`scripts/**` **全域**。
#: ★ 域过窄是**误报的根源**：第一版只扫 `scripts/checks/`，于是
#:   `rules/benchmark.yaml::return_guard.must_use_fund_market_price`（由
#:   `scripts/benchmark/return_guard.py` 读）被判成零消费者 —— **假红**。
#:   ⇒ 主理人**硬约束 ①**「扫描域必须覆盖 `scripts/**` 全域」。
RUNTIME_DIRS: tuple[str, ...] = ("scripts",)
RUNTIME_EXTS: tuple[str, ...] = (".py", ".sh", ".yaml", ".yml", ".json")

#: 面 B（**门禁·测试·schema**）：主理人硬约束「必须把门禁/schema/测试算进消费者」。
GATE_DIRS: tuple[str, ...] = ("tests", "schema", "registry", "config", "views")
GATE_EXTS: tuple[str, ...] = (".py", ".sh", ".yaml", ".yml", ".json", ".jsonl")

# ★★ 为什么除了 AST 还要一层「文本词边界命中」（不是偷懒，是**必要的假红抑制**）：
#   方向 1 的 AST 解析器只认「接收者已认定是规则文档」的读；**接收者是 `Call`** 时它看不见。
#   实测反例（★ 本卡第二轮**换过一次**，原因见下面那条 ⚑）：
#     `rules/banned_tokens.yaml::decision_scope.include_paths`
#   由 `scripts/_common.py:266` 的
#     `for pattern in cfg.get("include_paths") or []:`（`cfg = decision_scope_config(root)`）
#   读到；`decision_scope_config` 内部写的是 `load_banned_tokens(root).get("decision_scope")`
#   ⇒ 接收者是 `Call` ⇒ 方向 1 的解析器看不见它（它只跟 doc 变量走）。
#   若只用 AST，这个**已被消费**的键会被判成 ③ 候选 —— 正是我们要压的那类假红。
#   代价：文本命中会把「**注释 / 文档串里提过一句**」也算成消费者 ⇒ **偏保守**（少报候选）。
#   方向是对的：**宁可漏报零消费者，不可假报零消费者**（天天误报的门禁一定会被关掉）。
#
#   ⚑ **原反例是错的，且错得很有教益（必须留痕）**：本文件原先举的反例是
#     `banned_tokens.yaml::decision_scope.exclude_fields`。它**根本没有消费者** ——
#     `decision_scope_config()` 全仓只有 3 个调用点（`_common.py:264` / `:277` / `:290`），
#     分别只读 `include_paths` / `include_modules` / `include_call_chain` / `exclude_markers`，
#     **没有任何人读 `exclude_fields`**（真 `grep -rnw` 全仓 0 处，排除本文件）。
#     ⇒ 它当时之所以被判成"有消费者"，**唯一原因是本文件的 docstring 提到了它**。
#     ⇒ ★★ **我用来证明"宽口径必要"的那个例子，是宽口径自己造出来的**（自证循环）：
#       反例由被检验的口径挑，必然挑不出口径的错。教训：**反例必须来自独立方法**（这里是真 `grep` + 读调用点）。
#     ⇒ 修法两条：① 反例换成上面那个**已核实**的（`include_paths`）；② 本文件自身从语料面排除
#       （`SELF_RELPATH`），否则仪器会持续给自己当消费者。
#
#   ★★ 但这个取舍的**代价必须被量出来，否则它就是静默的**（`G-62`）。实测代价（本卡第二轮）：
#     两个独立的宽口径（「读父即消费子树」的前缀推定 + 「文本命中」）合起来把 ③ 的
#     **上界推到 230**，且它**已经吞掉了 `13-G` 用独立方法（全仓 `grep` + 逐键定性）
#     证实的 4 个零消费者键** —— `metric-sets.yaml::routing.key` / `routing.binding_field` /
#     `routing.metric_owner_field`（被 `_rules.metric_set_routing()` 的 `doc.get("routing")`
#     整体前缀覆盖）、`conversion_chain_per_model_class` 的三个叶键（键名是 `hardware`/`cloud`/
#     `software` 这种**通用词**，全仓到处出现）。
#     ⇒ 修法不是"收紧口径"（那会把假红放进来），而是**把证据分级 + 区间变成输出**
#       （见模块 docstring「正交的第二根轴」与 `证据分级` 一节）。

#: ★★ **语料必须剪掉的目录名**（本卡自己踩到的实测缺陷，非预防性设计）。
#:
#: 症状：跑 `tests/guards` **整目录**时，③ 候选从 **91 塌成 0**（`consumers_gate_test_schema`
#:   ★ 91 是**当时的读数**（那棵树 + 那时还含本文件自身的语料）；本文件排除自身后同口径读数为 92，
#:     两者不可直接比（`口径 9`：读数必须连"在哪个树上、什么口径"一起读）。
#: 从 11 涨到 102）。根因：前面用了 `code_root` 夹具的用例在 `tests/.work/<id>/`
#: 留下**整棵 `system/` 树的副本** ⇒ 每一个键名都能在副本里"找到消费者" ⇒ ③ 全场归零。
#:
#: ★ 为什么这条必须防：一个**只报 note、不阻断**的脚本，给出"零消费者 0 条"这种
#:   **完全安静**的假结论时，没有任何门禁会拦它 —— 而它正是本卡要产出的东西。
#:   ⇒ 实测由 `tests/guards/test_rule_key_consumer_scan.py::test_every_candidate_is_listed_by_name`
#:   当场抓出（单文件跑通过、整目录跑失败 ⇒ **顺序相关** ⇒ 病根在语料面，不在用例）。
PRUNE_DIR_NAMES: frozenset[str] = frozenset({".work", "__pycache__", ".pytest_cache", ".git"})

#: ★★ **本扫描器自身的文件，必须从语料面排除**（同族实测缺陷，第三处）。
#:
#: 由来（本卡第二轮，我自己踩的）：我在本文件的 docstring 里写下
#: `metric-sets.yaml::routing.{key,binding_field,metric_owner_field}` 与
#: `conversion_chain_per_model_class.{hardware,cloud,software}` 作为**反例说明**；
#: 而 `scripts/**` 是**面 A（运行时）**的语料面 ⇒ 这三个叶名（`hardware`/`cloud`/`software`）
#: 立刻在 `runtime_tokens` 里"命中" ⇒ 它们的 ②`门禁·测试·schema` **搬到了** ①`运行时`
#: （实测 ② `11 → 8`、① 文本 `72 → 75`）。
#:
#: ★ 为什么这必须修，不是"数字难看"：**编辑仪器不得改变被测对象的读数**。
#:   本文件每加一次"举例说明"，就可能把某个键从 ③ 里**挪走**；而输出里看不出任何异常
#:   （`G-62`：不可区分）。⇒ 排除自身是**仪器隔离**，与 `PRUNE_DIR_NAMES` 同族但更强：
#:   那条剪"夹具副本"，这条剪"仪器自己"。
SELF_RELPATH: str = "scripts/checks/rule_key_consumer_scan.py"

#: ★ **已知的残余误报源**（会让 ③ **偏多** ⇒ 假红）。**必须有人看过才能定案。**
KNOWN_RESIDUAL_FALSE_POSITIVE_SOURCES: tuple[str, ...] = (
    "**整组通用消费**：`for k, v in group.items()` / `**group` / 由 `param_ref` 拼出的"
    "**动态键** —— 叶键名可以**一次都不出现**却被真读到。本扫描**没有**排除这一条。",
    "**跨进程 / 跨语言消费**：配置被外部命令、`views/**` 的前端、或运行态产物消费时，"
    "键名可能不在本扫描的语料面内。",
)

#: ★ **已知的漏报源**（方向相反：会让 ③ **偏少**）。★★ 前两条原本只是"声明"，
#:   本卡第二轮给它们补上了**实测规模**（`evidence_ast_prefix` / `evidence_text` 两个计数）
#:   —— 没有规模声明的漏报源，读者无法判断它值不值得追。
KNOWN_FALSE_NEGATIVE_SOURCES: tuple[str, ...] = (
    "AST 分支的「读父即消费子树」前缀规则**偏宽** —— 读了 `group` 就把 `group.*` 全部标成"
    "已消费，于是**组内某个子键真没被读**时不会进 ③。★ **实测 56 条**（`evidence_ast_prefix`），"
    "逐条明细见输出里的 `prefix::<file>::<dotted>`。★ 已确证的实例：`metric-sets.yaml::routing.*`"
    "—— `_rules.metric_set_routing()` 写的是 `dict(group)`（整组返回），于是 5 个叶键全被前缀覆盖，"
    "而 `13-G` 证实其中 `key` / `binding_field` / `metric_owner_field` **零消费者**。"
    "★ 把 `prefix::` 明细列出来的目的：这 56 条是**判别力探针的第一优先级**（结构上可疑，不是猜的）。",
    "文本命中**不区分语境** —— 注释里出现过一次键名，就算「有消费者」；"
    "★ 更实的一层：**夹具 / 注册表 / 测试串里「逐字照抄」了 rules 的键名**，也被算成消费者。"
    "已确证实例：`tests/valuelayer/_fixtures.py::ROUTING` 逐字重述 `metric-sets.yaml::routing`；"
    "`13-G` 结论里被吞掉的 `conversion_chain_per_model_class.{hardware,cloud,software}` 正是"
    "因为叶名是通用词（这三个词在 `scripts/**` 里到处都是）。★ **实测 82 条**"
    "（`evidence_text`），逐条明细见输出里的 `text::<file>::<dotted>`。"
    "★ 我**试过**用「证据文件是否成组重述本 rules 文件键名」来把「照抄」挑出来 —— **失败了**，"
    "理由见模块 docstring「试过并**否掉**的判据」（真读多个键的文件与照抄夹具**同形**）。",
)

PROBE_STAGE_NOTE = (
    "★ **判别力探针不在本脚本内**（`口径 5`）：定案需要「在 **scratch 副本**上把该键改成"
    "**矛盾值**或**删掉** ⇒ 跑 `pre-commit` + 相关批次测试 ⇒ **是否变红**」。它有**删除成本**"
    "（scratch 副本要删；本会话宿主批量删除配额实测 `count 108656 ≥ threshold 99999` "
    "⇒ 任何 ≥1 项删除都被拒），故必须按主理人宣布的窗口单独跑（`V-08` 一轮一批）。"
    "**本脚本一次删除都不做。** ⇒ 在那一步跑完之前，③ 只能作为**候选**存在，"
    "**不得**写成「已判定」。"
)


# ───────────────────────── 语料与键路径 ─────────────────────────


#: `_word_hit` 的 token 切分与「纯标识符」前提（**等价性论证**见 `_word_hit` 的 docstring）。
_TOKEN_RX = re.compile(r"[A-Za-z0-9_]+")
_PURE_TOKEN_RX = re.compile(r"[A-Za-z0-9_]+\Z")


def _is_pruned(path: Path, root: Path) -> bool:
    """路径的**任一段**是点目录或 `PRUNE_DIR_NAMES` ⇒ 剪掉（理由见 `PRUNE_DIR_NAMES`）。"""
    return any(p.startswith(".") or p in PRUNE_DIR_NAMES for p in path.relative_to(root).parts)


def _load_corpus(
    root: Path, dirs: Iterable[str], exts: tuple[str, ...], report: CheckReport
) -> list[tuple[str, str]]:
    """把若干目录下的相关后缀文件读成 `(relpath, text)` 列表。

    ★ **只读**：不写、不删、不建。缺席的目录**跳过**（由 `check()` 把语料面文件数记进
      `scanned`，读者据此判断覆盖面，而不是猜）。
    ★ **剪掉 scratch / 缓存目录**（`_is_pruned`）：否则夹具留下的**整树副本**
      会把每个键名都变成"有消费者" ⇒ ③ 静默归零。
    ★ **剪掉本扫描器自身**（`SELF_RELPATH`）：否则仪器会给自己当消费者（理由见该常量）。
    """
    out: list[tuple[str, str]] = []
    pruned = 0
    excluded_self = 0
    for d in dirs:
        base = root / d
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in exts:
                continue
            if _is_pruned(path, root):
                pruned += 1
                continue
            rel = path.relative_to(root).as_posix()
            if rel == SELF_RELPATH:
                excluded_self += 1
                continue
            out.append((rel, path.read_text(encoding="utf-8")))
    report.scanned["corpus_paths_pruned"] = report.scanned.get("corpus_paths_pruned", 0) + pruned
    report.scanned["corpus_self_paths_excluded"] = (
        report.scanned.get("corpus_self_paths_excluded", 0) + excluded_self
    )
    return out


def _token_index(corpus: list[tuple[str, str]]) -> dict[str, str]:
    """`token -> 首个出现它的 relpath`。单遍切分（等价性见 `_word_hit`）。"""
    index: dict[str, str] = {}
    for relpath, text in corpus:
        for token in set(_TOKEN_RX.findall(text)):
            if token not in index:
                index[token] = relpath
    return index


def _leaf_paths(node: Any, prefix: tuple[str, ...] = ()) -> Iterator[tuple[str, ...]]:
    """枚举 YAML 的**叶键路径**（落到非 dict 的值；list 视为叶子）。"""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _leaf_paths(value, prefix + (str(key),))
    else:
        yield prefix


def _read_kind(leaf: tuple[str, ...], dotted_reads: Iterable[str]) -> tuple[str, str | None]:
    """`leaf` 是被**怎么读到**的：`("exact"|"prefix"|"none", 命中的那个读 或 None)`。

    * `exact`：存在一个读 `q`，其点路径**恰好等于** `leaf` ⇒ 有代码精确读了这条路径。
    * `prefix`：只存在 `q` 是 `leaf` 的**严格前缀**（通常是整个组）⇒ **本扫描推定的**，不是观测到的。
    * `none`：什么读都没覆盖它。

    ★★ 为什么要拆开（本卡第二轮新增，是**实测缺陷**不是预防性设计）：
      `_covered_by` 的「读父即消费子树」是**刻意偏宽**的，但它把两件判别力**完全不同**的事
      压成了同一个布尔值。实测代价：`13-G` 用独立方法证实的 4 个零消费者键
      （`metric-sets.yaml::routing.{key,binding_field,metric_owner_field}` +
      `conversion_chain_per_model_class` 的三个叶键）**被静默吞掉**，读输出的人看不出
      「这条键有消费者」是**观测到的**还是**推定的**（`G-62`：不可区分 ⇒ 必须可见）。
    """
    prefix: str | None = None
    for q in dotted_reads:
        qt = tuple(q.split("."))
        if qt == leaf:
            return "exact", q
        if prefix is None and qt == leaf[: len(qt)]:
            prefix = q
    return ("prefix", prefix) if prefix is not None else ("none", None)


def _covered_by(leaf: tuple[str, ...], dotted_reads: Iterable[str]) -> bool:
    """`leaf` 是否被某个已解析出的读 `q` **覆盖**：`q` 等于 `leaf` 或是它的前缀。

    ★ 保留为 `_read_kind` 的**薄封装**（三态判定的口径不变）：**绝不写第二份"谁覆盖谁"的判定**
      （同语义两载体必然漂移，`G-55`/`G-06` 同族）。
    ★ 「读父即消费子树」是**刻意**偏宽的：读 `group` 的人可能把它整个用掉。
      ⇒ 宁少报候选，理由与**实测代价**见 `KNOWN_FALSE_NEGATIVE_SOURCES`。
    """
    return _read_kind(leaf, dotted_reads)[0] != "none"


def _word_hit(name: str, token_index: dict[str, str]) -> str | None:
    """键名在语料里以**词边界**出现 ⇒ 返回首个命中的 `relpath`（可复核），否则 `None`。

    ★★ **为什么用 token 索引而不是逐键正则**（等价性论证，不是"图快"）：
      词边界正则 `(?<![A-Za-z0-9_])name(?![A-Za-z0-9_])` 的语义**恰好**是
      「`name` 是文本里一段**极大**的 `[A-Za-z0-9_]+` 游程」。
      ⇒ 把语料**切一遍** `[A-Za-z0-9_]+` 得到 token 集合后，命中判定退化成 O(1) 成员测试，
        与逐键正则**逐位等价**。
      ★ **前提**：`name` 自身必须是纯 `[A-Za-z0-9_]+`。实测本仓 255 个叶键**全部**满足；
        **不满足时报输入异常**，绝不静默判「无消费者」（`G-62`：不可区分 ⇒ 必须可见）。
      ★ 实测收益：修改前逐键正则扫全部语料 = `7.36s user`；同一对象上方向 1 守卫是
        `1.19s user` ⇒ 我的扫描器曾是它的 **6 倍**。改为单遍 token 索引后回到同量级。
    """
    if not name:
        return None
    if not _PURE_TOKEN_RX.match(name):
        raise ValueError(
            f"键名 {name!r} 含 `[A-Za-z0-9_]` 之外的字符 —— 本扫描用「一遍切 token」"
            "代替逐键正则（等价性见本函数 docstring），该等价**只在纯标识符键名上成立**。"
            "**不得**静默判它「无消费者」。要支持这种键名，请退回逐键正则实现。"
        )
    return token_index.get(name)


# ───────────────────────── AST 消费者索引 ─────────────────────────


def _ast_consumer_index(root: Path, report: CheckReport) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """返回 `(运行时索引, 门禁索引)`：`规则文件名 -> {解析出的读的点路径}`。

    ★ 复用方向 1 的 `_analyze_module`（**不重写**）。`scripts/checks/**` 归**门禁**桶，
      其余 `scripts/**` 归**运行时**桶 —— 两态**互斥且穷尽**，同一个键不会进两态。
    """
    runtime: dict[str, set[str]] = {}
    gate: dict[str, set[str]] = {}
    base = root / "scripts"
    if not base.is_dir():
        return runtime, gate
    parsed = 0
    pruned = 0
    for path in sorted(base.rglob("*.py")):
        if _is_pruned(path, root):
            pruned += 1
            continue
        relpath = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            # ★ **不得吞掉**（`no_placeholder_guard::SWALLOW_EXCEPTION_CONTINUE` 抓的就是这个）：
            #   跳过「无法解析的文件」= 该文件**根本没进消费者索引**，而输出里看起来一切正常
            #   ⇒ 「零消费者候选」会被**静默伪造**（`G-62`）。⇒ 报输入异常（`exit 2`），
            #   与「对象不达标」分开。
            raise ValueError(
                f"{relpath} 无法解析（{type(exc).__name__}: {exc}）—— 本扫描无法为它建消费者索引，"
                "**不得**当作「没有消费者」（`G-03`：无被检对象 ≠ 已验证）"
            ) from exc
        parsed += 1
        consts, producers = _module_constants(tree)
        module_reads = _analyze_module(relpath, text, consts, producers)
        bucket = gate if relpath.startswith("scripts/checks/") else runtime
        for rule_name, dotted, _file_rel, _lineno in module_reads.reads:
            bucket.setdefault(rule_name, set()).add(dotted)
    report.scanned["ast_py_files_parsed"] = parsed
    report.scanned["ast_py_files_pruned"] = pruned
    return runtime, gate


# ───────────────────────── 主检查 ─────────────────────────


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="rule_key_consumer_scan")

    docs = _load_rule_docs(root)
    runtime_index, gate_index = _ast_consumer_index(root, report)
    runtime_corpus = _load_corpus(root, RUNTIME_DIRS, RUNTIME_EXTS, report)
    gate_corpus = _load_corpus(root, GATE_DIRS, GATE_EXTS, report)

    report.scanned["rule_files"] = len(docs)
    report.scanned["runtime_corpus_files"] = len(runtime_corpus)
    report.scanned["gate_test_corpus_files"] = len(gate_corpus)

    # ★ **自证：语料面里不得残留 scratch 路径**。没有魔数、精确判定 ——
    #   一旦 `_load_corpus`/`_ast_consumer_index` 的剪枝被改坏，这里当场 `exit 2`，
    #   而不是安静地给出"③ 候选 0 条"（见 `PRUNE_DIR_NAMES` 的实测由来）。
    leaked = [
        rel
        for rel, _text in runtime_corpus + gate_corpus
        if any(p.startswith(".") or p in PRUNE_DIR_NAMES for p in Path(rel).parts)
    ]
    if leaked:
        raise ValueError(
            f"语料面残留 {len(leaked)} 个 scratch / 缓存路径（例：{leaked[:3]}）—— "
            "夹具副本会让**每个**键名都「有消费者」，③ 候选会静默归零。"
            "本扫描**不得**据此当作通过（`G-03`）。"
        )

    # ★ **仪器隔离的自证**：本文件存在 ⇒ 它必须被**恰好排除一次**。
    #   否则（如文件改名后 `SELF_RELPATH` 失效）自指污染会**静默复现**：
    #   本文件里每一条"举例说明"都会把自己变成消费者，读数随编辑漂移。
    if (root / SELF_RELPATH).is_file() and report.scanned.get("corpus_self_paths_excluded", 0) != 1:
        raise ValueError(
            f"仪器隔离失效：{SELF_RELPATH} 存在，但它被排除的次数是 "
            f"{report.scanned.get('corpus_self_paths_excluded', 0)}（应为 1）—— "
            "自指污染会静默改变读数（`G-62`）。本扫描**不得**据此当作通过。"
        )

    runtime_ast: list[tuple[str, str]] = []
    runtime_text: list[tuple[str, str]] = []
    gate_test: list[tuple[str, str]] = []
    zero_candidates: list[tuple[str, str]] = []
    # ★ 正交轴：证据级（与三态**不是**同一个划分，见模块 docstring「第二根轴」）。
    evidence_exact: list[tuple[str, str]] = []
    evidence_prefix: list[tuple[str, str]] = []
    evidence_text: list[tuple[str, str]] = []
    leaf_total = 0

    # ★ 语料**只切一遍** token（等价性见 `_word_hit`），不要在 255 个键上各扫一遍语料。
    runtime_tokens = _token_index(runtime_corpus)
    gate_tokens = _token_index(gate_corpus)
    report.scanned["runtime_tokens"] = len(runtime_tokens)
    report.scanned["gate_test_tokens"] = len(gate_tokens)

    for rule_name in sorted(docs):
        for leaf in _leaf_paths(docs[rule_name]):
            if not leaf:  # 空文档 / 顶层就是标量 ⇒ 不是「声明的键」
                continue
            leaf_total += 1
            dotted = ".".join(leaf)
            rt_kind, _rt_q = _read_kind(leaf, runtime_index.get(rule_name, ()))
            gt_kind, _gt_q = _read_kind(leaf, gate_index.get(rule_name, ()))
            text_hit: str | None = None
            if _covered_by(leaf, runtime_index.get(rule_name, ())):
                runtime_ast.append((rule_name, dotted))
            elif _covered_by(leaf, gate_index.get(rule_name, ())):
                gate_test.append((rule_name, dotted))
            elif _word_hit(leaf[-1], runtime_tokens) is not None:
                text_hit = runtime_tokens[leaf[-1]]
                runtime_text.append((rule_name, dotted))
            elif _word_hit(leaf[-1], gate_tokens) is not None:
                text_hit = gate_tokens[leaf[-1]]
                gate_test.append((rule_name, dotted))
            else:
                zero_candidates.append((rule_name, dotted))

            # ── 证据级：**精确读**压过一切；其次前缀推定；其次文本；最后 ③ ──
            #    ★ 顺序写死在这里，且下面自证 `evidence_none == len(zero_candidates)`。
            if rt_kind == "exact" or gt_kind == "exact":
                evidence_exact.append((rule_name, dotted))
            elif rt_kind == "prefix" or gt_kind == "prefix":
                evidence_prefix.append((rule_name, dotted))
            elif text_hit is not None:
                evidence_text.append((rule_name, dotted))

    report.scanned["leaf_keys"] = leaf_total
    report.scanned["consumers_runtime_ast"] = len(runtime_ast)
    report.scanned["consumers_runtime_text"] = len(runtime_text)
    report.scanned["consumers_runtime_total"] = len(runtime_ast) + len(runtime_text)
    report.scanned["consumers_gate_test_schema"] = len(gate_test)
    report.scanned["zero_consumer_candidates"] = len(zero_candidates)
    # ★ `口径 13` 第 3 条：**比值**（千分比整数 —— `CheckReport.scanned` 的注解是
    #   `dict[str, int]`，浮点会破坏公共契约）。
    report.scanned["zero_candidate_permille"] = (
        1000 * len(zero_candidates) // leaf_total if leaf_total else 0
    )
    # 三类之和必须 = 叶键总数（互斥+穷尽）；这条**自证**让"分类漏了"当场可见。
    report.scanned["tri_state_sum_check"] = (
        len(runtime_ast) + len(runtime_text) + len(gate_test) + len(zero_candidates)
    )

    # ── 正交轴：证据级（四级，互斥穷尽 ⇒ 和必须 = 叶键总数）──
    report.scanned["evidence_ast_exact"] = len(evidence_exact)
    report.scanned["evidence_ast_prefix"] = len(evidence_prefix)
    report.scanned["evidence_text"] = len(evidence_text)
    report.scanned["evidence_none"] = len(zero_candidates)
    report.scanned["evidence_tier_sum_check"] = (
        len(evidence_exact) + len(evidence_prefix) + len(evidence_text) + len(zero_candidates)
    )
    # ★ 两个自证：① 四级之和 = 叶键数；② `evidence_none` 必须**逐位等于** ③ 候选数 ——
    #   后者是「同一条判据的两个出口」，离了它两级轴就可能悄悄各走各的。
    _tier_ok = report.scanned["evidence_tier_sum_check"] == leaf_total
    _none_ok = report.scanned["evidence_none"] == len(zero_candidates)
    report.scanned["evidence_tier_selfcheck"] = 1 if (_tier_ok and _none_ok) else 0

    # ★★ ③ 的**区间**（`G-62`：单个数字会把"有强证据"与"只有推定/文本证据"压成同一种输出）。
    #   下界 = 严格判定；宽松上界 = 凡证据不是「精确读到该路径」的都可能漏报。
    #   ★ 上界**不是候选集**：候选仍只有 `zero_consumer_candidates`（硬约束 ③ 的口径不变）。
    report.scanned["zero_candidate_lower_bound"] = len(zero_candidates)
    report.scanned["zero_candidate_permissive_bound"] = len(zero_candidates) + len(
        evidence_prefix
    ) + len(evidence_text)
    report.scanned["zero_candidate_permissive_permille"] = (
        1000 * report.scanned["zero_candidate_permissive_bound"] // leaf_total if leaf_total else 0
    )

    # ── 逐键明细：③ 候选**逐条**列出（可复核现场 —— 本脚本不判红，明细本身就是产物）──
    for rule_name, dotted in zero_candidates:
        report.scanned[f"zero::{rule_name}::{dotted}"] = 1
    # ── 弱证据**也**逐条列出：这 138 条是判别力探针的**优先清单**，必须可机读，不能只给个计数 ──
    for rule_name, dotted in evidence_exact:
        report.scanned[f"exact::{rule_name}::{dotted}"] = 1
    for rule_name, dotted in evidence_prefix:
        report.scanned[f"prefix::{rule_name}::{dotted}"] = 1
    for rule_name, dotted in evidence_text:
        report.scanned[f"text::{rule_name}::{dotted}"] = 1
    # ── 反方向也要可复核：AST 索引覆盖到哪些 rules 文件、语料面有多大 ──
    report.scanned["rules_with_ast_reads"] = len(runtime_index) + len(gate_index)

    # ── 方法与边界（**必须进输出**：读者要能判"这个数能不能用"）──
    report.notes.append(
        "三态判据：① 运行时 = 方向 1 的 AST 解析出的读覆盖该叶键路径（或其前缀），"
        "或键名在 `scripts/**` 全域以词边界出现；② 门禁·测试·schema = AST 命中 "
        "`scripts/checks/**`，或键名在 `tests/ schema/ registry/ config/ views/` 里词边界出现；"
        "③ 零消费者候选 = 前两条都不中。"
        f"本树：叶键 {leaf_total} / ①运行时 {len(runtime_ast)}(AST)+{len(runtime_text)}(文本) / "
        f"②门禁·测试·schema {len(gate_test)} / ③候选 {len(zero_candidates)}。"
    )
    report.notes.append(
        "★★ **③ 是一个区间，不是一个数**（`G-62`）：下界 "
        f"{report.scanned['zero_candidate_lower_bound']}（本扫描严格判定）；宽松上界 "
        f"{report.scanned['zero_candidate_permissive_bound']}"
        f"（千分比 {report.scanned['zero_candidate_permissive_permille']}‰，基数仍是叶键 "
        f"{leaf_total}）= 下界 + 前缀推定 {report.scanned['evidence_ast_prefix']} + 文本命中 "
        f"{report.scanned['evidence_text']}。**上界不是候选集**（候选仍只有下界那么多）："
        "它的意思是「凡证据不是『精确读到该路径』的，都可能其实零消费者」。"
        f"本树有**精确证据**的只有 {report.scanned['evidence_ast_exact']} 条 —— "
        "把这两个数摆在一起，读者才能看出「92」这个数本身有多硬（也才看得出它有多软）。"
    )
    report.notes.append(
        "★ 证据分级（与三态**正交**，四级互斥穷尽；明细见 `prefix::` / `text::` 前缀的行）："
        f"精确读 {report.scanned['evidence_ast_exact']} / 前缀推定 "
        f"{report.scanned['evidence_ast_prefix']} / 文本命中 {report.scanned['evidence_text']} / 无 "
        f"{report.scanned['evidence_none']}；自证 `evidence_tier_selfcheck`="
        f"{report.scanned['evidence_tier_selfcheck']}（要求：四级和 = 叶键数，且 `evidence_none` "
        "逐位等于 ③ 候选数）。"
        "★ **`prefix::` 那批是判别力探针的第一优先级**：它们是「读了整组就把子树全标成已消费」"
        "推出来的，已确证 `metric-sets.yaml::routing.*` 里 3 个键就是被这条推定吞掉的。"
    )
    report.notes.append(
        "★★ **③ 是候选，不是判词**（`口径 5`，`batch13_taskbook.md:521-525`）："
        "「有人实现了同一件事」≠「这个键有人消费」；定案必须用**判别力**口径（改值 ⇒ 是否变红）。"
        + PROBE_STAGE_NOTE
    )
    for i, text in enumerate(KNOWN_RESIDUAL_FALSE_POSITIVE_SOURCES, start=1):
        report.notes.append(f"★ 残余**误报**源（会让 ③ 偏多 ⇒ 假红）#{i}：{text}")
    for i, text in enumerate(KNOWN_FALSE_NEGATIVE_SOURCES, start=1):
        report.notes.append(
            f"★ 已知**漏报**源（会让 ③ 偏少）#{i}：{text}"
            "★ 注意：**「偏少」不等于无害** —— 本树已实测它吞掉了 `13-G` 独立证实的 4 个零消费者键，"
            "而输出当时看不出任何异常（`G-62`：不可区分）。"
        )
    report.notes.append(
        "★ **语料面剪掉了 scratch / 缓存目录**（`PRUNE_DIR_NAMES`：`.work` / `__pycache__` / "
        "`.pytest_cache` / `.git`）—— 实测缺陷：跑 `tests/guards` **整目录**时，前面用 "
        "`code_root` 夹具的用例在 `tests/.work/<id>/` 留下**整棵 `system/` 树的副本** ⇒ "
        "每个键名都能在副本里「找到消费者」⇒ ③ 候选 **91 → 0** —— 一个**完全安静**的假结论。"
        "★ 91 是**当时的读数**（那时语料面还含本文件自身，且不排除自身）；与现在的 92 不可直接比"
        "（`口径 9`：读数必须连「在哪个树上、什么口径」一起读）。"
        f"本次剪掉 AST 侧 {report.scanned.get('ast_py_files_pruned', 0)} 个、语料侧 "
        f"{report.scanned.get('corpus_paths_pruned', 0)} 个路径。"
    )
    report.notes.append(
        "★ **仪器隔离**：本扫描器自身的文件（`SELF_RELPATH`）已从语料面排除 "
        f"（本次排除 {report.scanned.get('corpus_self_paths_excluded', 0)} 个）。理由（实测）："
        "我在本文件 docstring 里举反例时写下了 `hardware`/`cloud`/`software` 等叶名 ⇒ 它们立刻在"
        "`scripts/**` 语料里「命中」⇒ 3 个键从 ②门禁搬到了 ①运行时（实测 ② `11 → 8`）。"
        "★ **编辑仪器不得改变被测对象的读数**；若 `SELF_RELPATH` 失效（文件改名），本脚本 "
        "`exit 2` 而不是静默漂移。"
    )
    report.notes.append(
        "★ **已知的残余分桶缺陷（本轮新发现，未修）**：`scripts/checks/**` 在"
        "**AST** 分支归 ②（门禁），但它的**文本**命中会落到 ①（运行时）—— 因为 "
        "`runtime_corpus` 是 `scripts/**` **全域**而 `gate_corpus` 不含 `scripts/checks/**`。"
        "⇒ 同一个文件里的同一个键名，走 AST 与走文本会得到**不同的态**（`G-62` 同族）。"
        "本卡**不修**（会改动 ①/② 语义 ⇒ 必须与主理人确认后单独一轮），先如实登记。"
    )
    report.notes.append(
        "★ **本脚本恒 `exit 0`、未被注册进 `GATES` / `pre-commit`**（主理人硬约束 ③："
        "误报率未降下来前只允许只报 note、不阻断）。"
    )
    return report


if __name__ == "__main__":
    sys.exit(run_checker("rule_key_consumer_scan.py", check))
