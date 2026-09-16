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
#   方向 1 的 AST 解析器只认「接收者已认定是规则文档」的读。实测反例：
#     `rules/banned_tokens.yaml::decision_scope.exclude_fields`
#   由 `scripts/_common.py:209` 的
#     `cfg = load_banned_tokens(root).get("decision_scope") or {}`
#   读到，但**接收者是 `Call`** ⇒ 方向 1 的解析器看不见它（它只跟 doc 变量走）。
#   若只用 AST，这个**已被消费**的键会被判成 ③ 候选 —— 正是我们要压的那类假红。
#   代价：文本命中会把「**注释 / 文档串里提过一句**」也算成消费者 ⇒ **偏保守**（少报候选）。
#   方向是对的：**宁可漏报零消费者，不可假报零消费者**（天天误报的门禁一定会被关掉）。

#: ★★ **语料必须剪掉的目录名**（本卡自己踩到的实测缺陷，非预防性设计）。
#:
#: 症状：跑 `tests/guards` **整目录**时，③ 候选从 **91 塌成 0**（`consumers_gate_test_schema`
#: 从 11 涨到 102）。根因：前面用了 `code_root` 夹具的用例在 `tests/.work/<id>/`
#: 留下**整棵 `system/` 树的副本** ⇒ 每一个键名都能在副本里"找到消费者" ⇒ ③ 全场归零。
#:
#: ★ 为什么这条必须防：一个**只报 note、不阻断**的脚本，给出"零消费者 0 条"这种
#:   **完全安静**的假结论时，没有任何门禁会拦它 —— 而它正是本卡要产出的东西。
#:   ⇒ 实测由 `tests/guards/test_rule_key_consumer_scan.py::test_every_candidate_is_listed_by_name`
#:   当场抓出（单文件跑通过、整目录跑失败 ⇒ **顺序相关** ⇒ 病根在语料面，不在用例）。
PRUNE_DIR_NAMES: frozenset[str] = frozenset({".work", "__pycache__", ".pytest_cache", ".git"})

#: ★ **已知的残余误报源**（会让 ③ **偏多** ⇒ 假红）。**必须有人看过才能定案。**
KNOWN_RESIDUAL_FALSE_POSITIVE_SOURCES: tuple[str, ...] = (
    "**整组通用消费**：`for k, v in group.items()` / `**group` / 由 `param_ref` 拼出的"
    "**动态键** —— 叶键名可以**一次都不出现**却被真读到。本扫描**没有**排除这一条。",
    "**跨进程 / 跨语言消费**：配置被外部命令、`views/**` 的前端、或运行态产物消费时，"
    "键名可能不在本扫描的语料面内。",
)

#: ★ **已知的漏报源**（方向相反：会让 ③ **偏少**，属安全方向，但也要说清）。
KNOWN_FALSE_NEGATIVE_SOURCES: tuple[str, ...] = (
    "AST 分支的「读父即消费子树」前缀规则**偏宽** —— 读了 `group` 就把 `group.*` 全部标成"
    "已消费，于是**组内某个子键真没被读**时不会进 ③。",
    "文本命中**不区分语境** —— 注释里出现过一次键名，就算「有消费者」。",
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
    """
    out: list[tuple[str, str]] = []
    pruned = 0
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
            out.append((path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")))
    report.scanned["corpus_paths_pruned"] = report.scanned.get("corpus_paths_pruned", 0) + pruned
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


def _covered_by(leaf: tuple[str, ...], dotted_reads: Iterable[str]) -> bool:
    """`leaf` 是否被某个已解析出的读 `q` **覆盖**：`q` 等于 `leaf` 或是它的前缀。

    ★ 「读父即消费子树」是**刻意**偏宽的：读 `group` 的人可能把它整个用掉。
      ⇒ 宁少报候选（安全方向），理由见 `KNOWN_FALSE_NEGATIVE_SOURCES`。
    """
    for q in dotted_reads:
        qt = tuple(q.split("."))
        if qt == leaf[: len(qt)]:
            return True
    return False


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

    runtime_ast: list[tuple[str, str]] = []
    runtime_text: list[tuple[str, str]] = []
    gate_test: list[tuple[str, str]] = []
    zero_candidates: list[tuple[str, str]] = []
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
            if _covered_by(leaf, runtime_index.get(rule_name, ())):
                runtime_ast.append((rule_name, dotted))
            elif _covered_by(leaf, gate_index.get(rule_name, ())):
                gate_test.append((rule_name, dotted))
            elif _word_hit(leaf[-1], runtime_tokens) is not None:
                runtime_text.append((rule_name, dotted))
            elif _word_hit(leaf[-1], gate_tokens) is not None:
                gate_test.append((rule_name, dotted))
            else:
                zero_candidates.append((rule_name, dotted))

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

    # ── 逐键明细：③ 候选**逐条**列出（可复核现场 —— 本脚本不判红，明细本身就是产物）──
    for rule_name, dotted in zero_candidates:
        report.scanned[f"zero::{rule_name}::{dotted}"] = 1
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
        "★★ **③ 是候选，不是判词**（`口径 5`，`batch13_taskbook.md:521-525`）："
        "「有人实现了同一件事」≠「这个键有人消费」；定案必须用**判别力**口径（改值 ⇒ 是否变红）。"
        + PROBE_STAGE_NOTE
    )
    for i, text in enumerate(KNOWN_RESIDUAL_FALSE_POSITIVE_SOURCES, start=1):
        report.notes.append(f"★ 残余**误报**源（会让 ③ 偏多 ⇒ 假红）#{i}：{text}")
    for i, text in enumerate(KNOWN_FALSE_NEGATIVE_SOURCES, start=1):
        report.notes.append(f"★ 已知**漏报**源（会让 ③ 偏少，安全方向）#{i}：{text}")
    report.notes.append(
        "★ **语料面剪掉了 scratch / 缓存目录**（`PRUNE_DIR_NAMES`：`.work` / `__pycache__` / "
        "`.pytest_cache` / `.git`）—— 实测缺陷：跑 `tests/guards` **整目录**时，前面用 "
        "`code_root` 夹具的用例在 `tests/.work/<id>/` 留下**整棵 `system/` 树的副本** ⇒ "
        "每个键名都能在副本里「找到消费者」⇒ ③ 候选 **91 → 0**（一个**完全安静**的假结论）。"
        f"本次剪掉 AST 侧 {report.scanned.get('ast_py_files_pruned', 0)} 个、语料侧 "
        f"{report.scanned.get('corpus_paths_pruned', 0)} 个路径。"
    )
    report.notes.append(
        "★ **本脚本恒 `exit 0`、未被注册进 `GATES` / `pre-commit`**（主理人硬约束 ③："
        "误报率未降下来前只允许只报 note、不阻断）。"
    )
    return report


if __name__ == "__main__":
    sys.exit(run_checker("rule_key_consumer_scan.py", check))
