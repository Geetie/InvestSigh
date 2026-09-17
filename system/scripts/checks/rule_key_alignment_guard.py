#!/usr/bin/env python3
"""`rule_key_alignment_guard.py` —— 代码读的 `rules/` 键**必须存在**（13-pre 方向 1）。

```
python system/scripts/checks/rule_key_alignment_guard.py [code_root]
```

## 它拦的是什么（`R5` 的「单向缺失即红」）

`rules/*.yaml` 是**唯一真源**（`G-06`）。代码读一个**规则文件里不存在**的键时，
Python 的 `dict.get()` **不会报错** —— 它返回 `None`，而 `None` 随后被 `or ""` / `or {}` / `or 0`
洗成一个**看起来合法的值**，于是"这条规则其实没被读"这件事**在任何输出里都不可见**。

★ **本机实测的活靶子（建表时的第一条，现已关闭）**：`scripts/pricelayer/scenario_guard.py`
的 `method_version=str(doc.get("method_version") or "")` —— `rules/scenario.yaml` **没有这个键**，
于是它静默产出空串。这正是 `phase1_open_tensions.md` 登记过的第三条并行发现。
⇒ **13-B 已把它改成"按 `scenario_consistency.param_ref` 指针解析 + 转正后取不到载体即响亮失败"**，
本条欠账随之关闭（详细来历见 `KNOWN_ZERO_KEY_READS` 上方的注释）。**本守卫保留，用于拦住下一条**。

对照 `T-18` / `G-50` / `G-55` / `G-57` / `G-58`，本形态是同一个"**声明 ≠ 有效力**"家族的**第六种**：

| # | 形态 | 谁静止 |
|---|---|---|
| `G-50` | 有实现、有调用方，判据没绑 | 判据 |
| `T-18` | `rules/` 声明的列，代码零消费者 | 声明 |
| `G-55` | 同语义两种载体，彼此无绑定 | 两侧互不认识 |
| `G-57` | 同上，但同文件内成片 | — |
| `G-58` | 同语义三载体，**位置与类型都不同** | — |
| **本条** | **代码读的键在声明里根本不存在** | **读** |

## 两条断言（`R5` 的「单向缺失即红」）

| # | 断言 | 命中形态 | 缺键时的后果 |
|---|---|---|---|
| ① | 代码**引用**的 `rules/<名>.yaml` 必须在 `rules/` 里**存在** | 整个文件缺失 | 读路径多半响亮失败（`FileNotFoundError`）—— **不是**静默，但仍属"声明面与代码不一致" |
| ② | 代码**读**的键必须在**实有键**里 | 文件在、键不在 | ★ **静默失效**：`dict.get()` 返回 `None`，被 `or ""` / `or {}` / `or 0` 洗成合法值 |

★ 两类的**判据必须能区分**，否则会把 ② 那种静默失效洗成 ① 的"待安装"：
① 的白名单（`KNOWN_ABSENT_RULE_FILES`）**只收"文件不存在"**；② 的白名单
（`KNOWN_ZERO_KEY_READS`）**只收"文件在、键不在且被静默吞掉"**。两者不共用一张表。

## 方向 2：`rules/` 声明的**记录列**必须有代码消费者（`T-18` 家族，反向绑定）

方向 1 只做**单向**：代码**读**的键必须**存在**于 `rules/`。它的补集 ——
**`rules/` 里声明了语义、代码区却从不读的键** —— 此前**无人守**，而这正是本项目
第三次同形态事故（`G-50` / `G-RC-12` / `T-18`）的暴露面：一句话概括
**「写在声明里」≠「在机器上有效力」**。

| 被检对象 | 判据 | 为什么它能藏住 |
|---|---|---|
| **记录集合的列**：① 元素全是 mapping 的 `list`（如 `pipeline.yaml::steps`）② 值全是 mapping 的 `dict` | 该列名必须在 `scripts/**` 里以**非 docstring 的字符串字面量**出现（= 代码在**按名字**读它）。否则 = **无消费者** ⇒ 违例 | 上游方向 1 与 `rule_key_consumer_scan` 都只枚举**叶键**（`_leaf_paths` 把 list 当叶子）⇒ `steps[*].implemented_in_first_version` **根本不在它们的被检集合里**；而它的名字**只出现在 docstring**（`pipeline.py:152` 等）⇒ 文本口径的扫描器又会把它当成"已消费"。**两个盲区叠加 ⇒ 死列永久存在而两处门禁都看不见。** |

★ **判据的可判定性与穷尽性（`R-06`）**：域 = `rules/*.yaml` 的**全部记录集合 × 全部列**
（纯遍历 YAML，无名单、无关键词）；判据 = "列名是否作为**非 docstring 字符串字面量**出现在
`scripts/**`"（纯 AST 常量比对）。两侧都是**可穷尽枚举 + 集合差**，不是关键词/名单枚举。
★ **为什么剔掉 docstring**：死列 `implemented_in_first_version` 改前在 `pipeline.py` /
`ingest_step.py` / `chain_steps.py` 的 docstring 里各出现一次 —— 把 docstring 当消费者，
本方向就会**恰好漏掉它要抓的那一条**。
★ **白名单**（`KNOWN_UNCONSUMED_RULE_COLUMNS`）：本仓确有若干"已声明、已知尚未接线"的记录列
⇒ 按 `口径 13` 四字段逐条登记（**不是**放宽判据）。键 = `(规则文件名, "集合::列")`。

## 分析方法（有界 + fail-safe：**宁可少报，绝不误报**）

`rules/` 的键是**嵌套**的、代码读法有六七种。故本守卫**不做**通用数据流分析，只认**能静态定死**的：

1. **定位"规则文档变量"**：模块级字符串常量（`SCENARIO_YAML = "rules/scenario.yaml"`、
   `BASELINE_RELPATH = ...`）、`/` 拼接的路径（`root / "rules" / "benchmark.yaml"`）、
   以及**作用域内的路径变量**（`path = Path(root) / SCENARIO_YAML`）→ 其值匹配
   `^rules/<名>.yaml$` 即是一个规则文件出处。
   再认三种装载点：`yaml.safe_load(...)` / `_cached_yaml(...)` / `load_yaml(...)`，
   外加 `_load_mapping(root, <该常量>)` 这种"路径在第 2 个实参"的形态；
   **同模块内的薄包装函数**（`def baseline_doc(root): return _load_mapping(root, R)`）
   取**一轮**不动点后同样算。
2. **收集读**：对已定位的文档变量，取 `doc.get("k")` 与 `doc["k"]`；
   以及**一层别名**（`g = doc.get("group")` 之后 `g.get("k")`）与**链式**
   （`doc.get("g", {}).get("k")` / `doc.get("g", {})["k"]`）。
3. **核对**：`k` 必须在该文件（或该分组）的**实有键**里。

★ **解析不出出处/键的一律跳过并计数**（`scanned.unresolved_reads`）：比如键是**函数参数**
（`baseline_threshold(root, key)` 里的 `cfg[key]`）、是 f-string、或来自循环变量。
**跳过不是"通过"** —— 计数摆在输出里，读者能看见覆盖面（`G-03`：不得把"没扫到"当"已验证"）。

★ **计数口径**：`unresolved_reads` **只统计"接收者已被认定是规则文档、但键解析不出"的读**。
"读别的 mapping"（如 `row.get("price")`、`payload["x"]`）**不计入** —— 否则该计数会被
几千个与规则无关的 `.get` 淹掉，读者再也看不出**覆盖面**在哪。同理，每个有规则读的文件
各出一行 `reads::<文件>` / `unresolved::<文件>`，**覆盖面逐文件可见**。

★ **本守卫的覆盖面边界（如实登记，不是遗漏）**：
- `config/rules.py::load_yaml(relpath, root)` 的 `relpath` 由调用方给；只有当它**在同一个
  作用域里被静态绑定**到规则路径时本守卫才能认（`BUDGET_RULES_RELPATH` 就是这种）。
- `scripts/valuelayer/_rules.py` 的 `cfg[key]`（键由**调用方**以参数传入）**不在**静态可达范围内
  —— 那是"跨函数传键"，要覆盖它必须做真正的过程间分析。该路径的**缺键行为**
  由 13-A 自己用"缺键 ⇒ `MissingRuleInput` ⇒ `exit 2`"钉住（不静默兜底），故不构成静默失效。
- ★ **多值返回盲区（有计数）**：`raw, source, notes = _configured_source(...)` 这类经
  **元组返回**取得的文档变量**不被认定为文档** ⇒ 其后的 `raw.get(...)` 既不进 `resolved`
  也不进 `unresolved`。本守卫**不静默**：计入 `scanned.ambiguous_doc_vars` 并打 note。
  要覆盖它需按"返回位置"做生产者分析 —— `13-pre` 未做，**如实登记**。
- 本守卫**只扫 `scripts/`**；`system/config/rules.py` 本身只是通用只读读口、不含键名。

## 白名单（`口径 13`）

**三张**豁免表（真源 = `waiver_tables()`）**逐条**带
`reason` / `owner` / `预期何时有消费者` / `review_by` 四字段
（`_Waiver`）；缺一即**导入时响亮失败**（`_selfcheck_waivers`）。过期未消 ⇒ **报警**（note + 计数）；
并在输出里给出**白名单与被检集合的比值**（`scanned.waiver_ratio_*_permille` + 汇总 note）。

★ 命中即 fail，禁 warn-only（纪律 2）。
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import yaml

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import (  # noqa: E402
    CheckReport,
    Violation,
    run_checker,
    walk_files,
)

RULES_DIRNAME = "rules"
SCAN_SUBDIR = "scripts"

#: **严格**匹配：整串必须就是 `rules/<名>.yaml`（不允前缀）。
#: ★ 为什么不容前缀：`MSG = "详见 rules/baseline.yaml"` 这类**说明性字符串**
#:   一旦被当成出处，守卫就开始对着文书报违例 —— 而"天天误报的门禁一定会被关掉"。
_RULE_FILE_RE = re.compile(r"^rules/(?P<name>[A-Za-z0-9_.\-]+\.ya?ml)$")

#: `rules/` 文档的装载点（"函数名（最后一段）→ 规则路径参数下标"）。
#: `None` = 规则路径出现在**任意位置**的实参里；`0`/`1` = 出现在第 0/1 个实参。
_DOC_LOADERS: dict[str, int | None] = {
    "_cached_yaml": None,
    "safe_load": None,
    "load": None,
    "load_yaml": 0,
    "_load_mapping": 1,
    "_load_rule": 1,
}

#: **作用域边界**：这些节点各自成域，遍历时**不越入**（否则会重复计数）。
_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)

#: ★ 已登记的"**代码读了规则文件里不存在的键**"。
#:
#: 每条必须写清 **为什么现在不改 / 归谁改 / 预期何时消失**（`G-03`：显式 note + 计数，不静默）。
#: 本表**不是**永久豁免 —— 它是一条**计数会摆出门禁输出**的欠账。

#: `口径 13`（`batch13_taskbook.md:682`）逐字要求白名单**自带三条**，缺一即退化成"永久豁免池"：
#:   ① **逐条** `reason` + `owner` + `预期何时有消费者`（写不出 ⇒ **不得入白名单**）；
#:   ② **过期机制**：每条带 `review_by` ⇒ 到期未消 ⇒ **报警**；
#:   ③ **输出白名单与被检集合的比值**（`whitelisted: n / total: m`）。
#:
#: ⇒ 本文件把豁免升格成**对象**（`_Waiver`）：四个字段都在，才可能被构造出来；
#:   且 `_selfcheck_waivers()` 在**导入时**逐条校验（空字段 / 日期不可解析 ⇒ 当场响亮失败）。
#:   ★ 比值由 `check()` 打进 `scanned`（键：`waiver_ratio::...`）与汇总 note ——
#:   "白名单把整道门禁稀释掉"这件事必须**可见**。
@dataclass(frozen=True)
class _Waiver:
    """一条**已登记欠账**（`口径 13`：缺任一字段 ⇒ 不得入白名单）。"""

    reason: str
    owner: str
    #: **预期何时有消费者 / 何时消失** —— 必须写成**可判定**的一句话（不是"以后再说"）
    expected_consumer_by: str
    #: ISO 日期。**到期未消 ⇒ 报警**（`口径 13` 第 2 条）
    review_by: str

    def is_expired(self, today: date) -> bool:
        return date.fromisoformat(self.review_by) < today


#: ## ★ 本表**当前为空** —— 并且这个"空"是有来历的（不是一开始就空）
#:
#: 建表时的唯一一条是：
#:
#:   `(scripts/pricelayer/scenario_guard.py, "rules/scenario.yaml::method_version")`
#:
#: 它**已被关闭**（不是被删掉）：13-B（`ws-ch5-pricelayer`，合入 `main` 后本树 `scenario_guard.py`
#: 已重写该路径）把 `doc.get("method_version") or ""` 换成
#: `_method_version_from_pointer()` —— 按 `scenario_consistency.param_ref` 指针解析，
#: **转正后取不到载体即响亮失败**（`scenario_guard.py:246-269`），并在 docstring 里逐字声明
#: 「`method_version` **不读** `rules/scenario.yaml`（该文件没有这个键）」（`:289-290`）。
#: ⇒ 覆盖这件事的**机器证据**是：合入后本守卫 `whitelisted_zero_key_reads=0` 且
#: `resolved_key_reads=47`、`0 violations`（即"读的键全部存在"，不是"读的键被白名单盖住"）。
#:
#: ★ 本表**保持机制在位**：下一条"代码读了规则文件里不存在的键"必须按 `口径 13` 四字段登记。
#: ★ **不得**因为"现在空了"就把表和 `_selfcheck_waivers()` 一起删掉 —— 那等于把机制收走，
#:   下一条欠账就只能靠"没人看见"过去了（本项目的铁律：没有检查器强制的规范等于不存在）。
KNOWN_ZERO_KEY_READS: dict[tuple[str, str], _Waiver] = {}

#: ★ 已登记的"**代码引用了一个按设计尚未安装的规则文件**"。
#:
#: ★ **与 `KNOWN_ZERO_KEY_READS` 的关键区别**（判据必须能区分这两类，否则会把
#:   "文件在、键不在、静默取空串"的**静默失效**洗成"待安装"）：
#:   - 本表：**文件不存在**，且**缺它的读路径响亮失败**（`FileNotFoundError` / 显式兜底链）
#:     ⇒ 是"值未冻结 ⇒ 13-R 不安装"的**已登记状态**，不是静默失效；
#:   - `KNOWN_ZERO_KEY_READS`：**文件在、键不在**，`dict.get()` 静默返回 `None`
#:     ⇒ 才是本守卫要拦的那一类。
#:
#: ★ **键的第 2 项是规则文件名（不带 `rules/` 前缀）** —— 这是刻意的：
#:   写成裸字面量 `"rules/transmission.yaml"` 时，本守卫扫描自己会把**登记数据当成代码引用**
#:   而自命中一条违例（实测踩过）。用不带前缀的文件名既避开自命中，也不需要"豁免本文件"这种破口。
#:
#: ★ **键按 `(文件, 规则文件)` 逐条登记**，不按规则文件名整体豁免 —— 否则将来任何一个
#:   新模块静默读同一个不存在的文件时，会被这条豁免一起盖住。
KNOWN_ABSENT_RULE_FILES: dict[tuple[str, str], _Waiver] = {
    (
        "scripts/graph/stop.py",
        "transmission.yaml",
    ): _Waiver(
        reason=(
            "**按设计刻意未安装**（`B3 amplification_cap` / `p04` 等值未冻结），"
            "且**缺它的读路径响亮失败、不静默兜底**：`load_transmit_params()` 先 `path.exists()` 判、"
            "缺即 `FileNotFoundError`（实测留痕：`ws_independent_audit_batch8_integration_transmit.md:52-57`）。"
            "登记处：`ws_graph_report.md:99`（『请主理人在集成时提供该文件』）、"
            "`ws_ch7_transmit_report.md:161`（所需键 + 建议值）、"
            "`.workbuddy/memory/2026-09-16.md:711`（『**不创建** `rules/transmission.yaml`：同理（等值未冻结）』）。"
        ),
        owner="**主理人**（安装规则文件）；值面归第十一章 `p04` 参数冻结裁定",
        expected_consumer_by=(
            "消费者**已在**（`scripts/graph/stop.py::load_transmit_params` / `scripts/transmit/**`）；"
            "本条等的是**被读的文件**。预期消失条件 = 第十一章 `p04` 冻结后主理人安装 `rules/transmission.yaml`。"
        ),
        review_by="2026-09-30",
    ),
    (
        "scripts/evidence/budget_gate.py",
        "budget.yaml",
    ): _Waiver(
        reason=(
            "**按设计刻意未安装**（三类预算值由 `p09` 冻结后填入，`06/02:320`『第十一章『检索/模型预算』"
            "参数冻结后填入』），且**缺它的读路径响亮失败、不静默兜底**：`_configured_source()` 先"
            "`rules_path.exists()` 判 → 退到 `freeze p09` 数值映射 → 再退到**调用方显式** `defaults`；"
            "三者皆无 ⇒ `BudgetConfigMissing`（`RuntimeError`，`budget_gate.py:179-184`）。"
            "登记处：`.workbuddy/memory/2026-09-16.md:702`（『缺 `rules/budget.yaml` → "
            "`BudgetConfigMissing` 响亮失败』）、`:709`（『**不创建** `rules/budget.yaml`：设计原文说"
            "『参数冻结后填入』，而 `p09.budget = tbd`』）。"
        ),
        owner="**主理人**（安装规则文件）；值面归 `p09` 预算参数冻结裁定",
        expected_consumer_by=(
            "消费者**已在**（`scripts/evidence/budget_gate.py::_configured_source`）；"
            "本条等的是**被读的文件**。预期消失条件 = `p09` 冻结后主理人安装 `rules/budget.yaml`。"
        ),
        review_by="2026-09-30",
    ),
}

#: ★ 已登记的"**`rules/` 声明了记录列、但 `scripts/**` 零消费者**"（方向 2，`T-18` 家族）。
#:
#: 键 = `(规则文件名, "<集合点路径>::<列名>")`；集合为空时集合段写 `<root>`。
#: ★ 与另两张表的键口径刻意不同（那两张是 `(代码文件, 规则键)`）：本方向**没有**单一代码文件可指，
#:   "责任人"是**声明面**（规则文件）而非某个读点 —— 故键以规则文件为准。
#:
#: ★ **每条必备 `口径 13` 四字段**（`reason` / `owner` / `expected_consumer_by` / `review_by`），
#:   缺一即**导入时响亮失败**（`_selfcheck_waivers`）。**写不出"预期何时有消费者"就不得入表。**
#: ★★ 这张表**只收"已声明、已知尚未接线"的记录列**，**绝不用它放宽判据**：
#:   新出现一条**未登记**的无消费者记录列 ⇒ 本方向**命中即 fail**（`G-01`）。
#: ★★ 本表**逐条**登记（`(规则文件名, "<集合::列>")`，**不按规则文件整体豁免**）：新出现的
#: 无消费者列若不在表里 ⇒ 命中即 fail。每条 = `(规则文件名, "<集合点路径>::<列名>", 理由)`；
#: `owner` / `expected_consumer_by` / `review_by` 由下面的物化循环**逐条**写进每个 `_Waiver`
#: （仍是四字段齐全 —— `_selfcheck_waivers` 逐条校验）。
_KNOWN_UNCONSUMED_COLUMN_SPECS: tuple[tuple[str, str, str], ...] = (
    (
        "benchmark.yaml", "benchmark_objects::benchmark_semantics",
        "**说明性列**（人读的基准语义描述，非机器契约）⇒ 本就不该有按名字的代码消费者。",
    ),
    (
        "benchmark.yaml", "benchmark_objects::change_records",
        "**变更治理载体列**：`change_governance` 的治理动作（追加版本 / 人工审批）由"
        "第八章交付；首版 `return_guard` 只逐列读 `return_*` 与 `freeze_status`。",
    ),
    (
        "benchmark.yaml", "benchmark_objects::return_basis_version",
        "**返回口径版本号**：口径版本当前由 `return_basis.version` 承载并被读取，"
        "记录级 `return_basis_version` 尚无读取点（同语义两载体，待接线或并轨）。",
    ),
    (
        "data-sources.allowlist.yaml", "sources::may_enter_decision_logic",
        "**准入策略列**（该数据源可否进入决策逻辑）：决策作用域（Ch7）首版未接线。",
    ),
    (
        "data-sources.allowlist.yaml", "sources::may_enter_first_version",
        "**准入策略列**（该数据源可否进入首版）：首版准入判定尚无按列的机器消费者。",
    ),
    (
        "data-sources.allowlist.yaml", "sources::reassessment_rule",
        "**复审规则列**：数据源复审链路首版未接线。",
    ),
    (
        "freeze.yaml", "freeze_params::blocking_targets",
        "**冻结参数的阻塞目标列**：`stage_gate` 的 `caliber_tbd_placeholder` 判据只读"
        "`freeze_status`/`confirmed_*`，未按本列接线。",
    ),
    (
        "freeze.yaml", "freeze_params::decision_owner",
        "**决策责任人列**（人读的治理信息）⇒ 无机器消费者。",
    ),
    (
        "freeze.yaml", "freeze_params::impact_note",
        "**影响说明列**（人读）⇒ 无机器消费者。",
    ),
    (
        "freeze.yaml", "freeze_params::option_set",
        "**备选值集合列**：首版只读 `freeze_status` / `suggested_value` 的接线尚未落地。",
    ),
    (
        "freeze.yaml", "freeze_params::param",
        "**参数名列**：`stage_gate` 按 `param_id`（如 `p01`）索引，未按 `param` 列名读取"
        "（同语义两载体，待并轨）。",
    ),
    (
        "freeze.yaml", "freeze_params::param_tier",
        "**参数分级列**：分级策略首版未接线。",
    ),
    (
        "freeze.yaml", "freeze_params::source_capability",
        "**数据源能力列**：`p09` 数据源参数冻结后的接线尚未落地。",
    ),
    (
        "freeze.yaml", "freeze_params::source_state",
        "**数据源状态列**：同 `source_capability`，接线待 `p09` 冻结。",
    ),
    (
        "freeze.yaml", "freeze_params::suggested_value",
        "**建议值列**：来源是 `00_待拍板项清单.md` 的建议值，首版代码不读它"
        "（值面待需求方拍板后接线）。",
    ),
    (
        "freeze.yaml", "freeze_params.option_set::basis",
        "**备选值依据说明列**（人读）⇒ 无机器消费者。",
    ),
    (
        "metric-sets.yaml", "metric_sets::basis",
        "**指标集依据说明列**（人读）⇒ 无机器消费者。",
    ),
    (
        "pipeline.yaml", "steps::gap_behavior",
        "**缺口行为声明列**（`explicit_gap_when_hook_absent`）：`G1-05` 的缺口处理在当前"
        "代码里以「显式记 gap」实现，但**未按本列名读取**（声明与实现同义、异载体）。",
    ),
    (
        "publish.yaml", "three_layer_permission::restrictions",
        "**三层权限策略列**：`publish.yaml` 属**第八章（发布）**，首版**不交付**该组 ⇒ 整组无消费者。",
    ),
    (
        "publish.yaml", "three_layer_permission::must_show",
        "**三层权限策略列**：同第八章，首版**不交付**。",
    ),
    (
        "publish.yaml", "three_layer_permission::excludes",
        "**三层权限策略列**：同第八章，首版**不交付**。",
    ),
    (
        "publish.yaml", "three_layer_permission::implies_reshare_authorization",
        "**三层权限策略列**：同第八章，首版**不交付**。",
    ),
    (
        "publish.yaml", "three_layer_permission::whitelist",
        "**三层权限策略列**：同第八章，首版**不交付**。",
    ),
    (
        "publish.yaml", "three_layer_permission::rights_clearance_per_item",
        "**三层权限策略列**：同第八章，首版**不交付**。",
    ),
    (
        "publish.yaml", "three_layer_permission::auto_authorization",
        "**三层权限策略列**：同第八章，首版**不交付**。",
    ),
    (
        "scope.yaml", "coverage_scope.dimensions::per_node",
        "**覆盖维度声明列**：首版覆盖守卫只读上层聚合，未按维度列读取。",
    ),
    (
        "scope.yaml", "coverage_scope.dimensions::rollback_allowed",
        "**覆盖维度声明列**：同 `per_node`，首版未按列读取。",
    ),
    (
        "scope.yaml", "coverage_scope.dimensions::values",
        "**覆盖维度声明列**：同 `per_node`，首版未按列读取。",
    ),
)

#: `口径 13` 四字段里可**跨条共享**的两项（同一 owner / 同一复核窗口）；`reason` 逐条不同。
_UNCONSUMED_OWNER = (
    "**主理人**（安装/接线规则文件）；接线归阶段②③ 与第八/十章交付方；"
    "人读列的处置归声明面维护方"
)
_UNCONSUMED_EXPECTED_BY = (
    "预期消失条件 = 该列出现**按名字的代码读取点**（如 `T-18` 的 `_deferred_by_design()` 范式）；"
    "**人读列**（说明/依据/责任人）永不需机器消费者 ⇒ 届时改 `review_by` 并写明**它为何是终态**"
)
_UNCONSUMED_REVIEW_BY = "2026-10-31"

KNOWN_UNCONSUMED_RULE_COLUMNS: dict[tuple[str, str], _Waiver] = {
    (file_name, dotted): _Waiver(
        reason=reason,
        owner=_UNCONSUMED_OWNER,
        expected_consumer_by=_UNCONSUMED_EXPECTED_BY,
        review_by=_UNCONSUMED_REVIEW_BY,
    )
    for file_name, dotted, reason in _KNOWN_UNCONSUMED_COLUMN_SPECS
}

#: `口径 13` 三张豁免表的**唯一真源**（`表名 → 表`）。
#:
#: ★ **为什么要合成一处**（发现于本仓 macOS 会话；与 `G-65` 同族，**未另编号**）：
#:   此前这三张表的清单被**手抄了三份** —— ① `_selfcheck_waivers()` 内联一份；
#:   ② `_expired_waivers()` 内联一份；③ `tests/guards/test_rule_key_alignment.py`
#:   内联**第三份，且只抄了前两张**。于是新增第三张表（`KNOWN_UNCONSUMED_RULE_COLUMNS`）时，
#:   ①② 跟着生效、③ **静默停在两张** ⇒ 那条反例 `assert len(expired) == len(all_keys)`
#:   以 `30 == 2` 变红（**假红**，看起来像"过期机制坏了"）。
#:   这正是本仓反复栽的「清单手工维护 ⇒ 漂移」（`G-RC-02` / `G-RC-07` / conftest 的
#:   `_TRUTH_STEMS` 注三处同族）⇒ 收敛为**一处**，其余（含测试）**一律派生**。
#:   ⇒ ★ 新增豁免表时**只改这里**；若还要改别处，说明派生没做干净。
def waiver_tables() -> tuple[tuple[str, dict[tuple[str, str], _Waiver]], ...]:
    """`口径 13` 三张豁免表的**唯一真源**（`表名 → 表`）。

    ★ **是函数而不是常量**（实测教训）：本函数的调用方里有两处**测试**要用
      `monkeypatch.setattr(G, "<表名>", ...)` **替换**某张表来证伪校验机制
      （`test_waiver_selfcheck_rejects_incomplete_or_undated_entries` /
      `test_reverse_waiver_table_is_validated`）。若把清单做成**导入期常量**，
      元组里握的是**旧 dict 对象**、属性被替换后**看不见** ⇒ 两条用例双双
      `DID NOT RAISE`（实测踩到）。⇒ 必须在**调用时**读模块全局。
    ★ 返回顺序稳定（与 `_selfcheck_waivers` / `_expired_waivers` 的报告顺序同源）。
    """
    return (
        ("KNOWN_ZERO_KEY_READS", KNOWN_ZERO_KEY_READS),
        ("KNOWN_ABSENT_RULE_FILES", KNOWN_ABSENT_RULE_FILES),
        ("KNOWN_UNCONSUMED_RULE_COLUMNS", KNOWN_UNCONSUMED_RULE_COLUMNS),
    )


def _selfcheck_waivers() -> None:
    """`口径 13` 的**机器绑定**：四个字段缺一 / 日期不可解析 ⇒ **导入时**响亮失败。
    ★ 为什么放在导入时而不是 `check()` 里：白名单是**本守卫的判据本身**。
      一份字段残缺的白名单只要还能跑，它就已经在"把门禁关掉"了 ——
      那种状态不该等到某人恰好跑门禁才暴露。**破口当场红**（纪律 2：禁 warn-only）。
    ★ 用 `raise` 而非 `assert`：`python -O` 会把 `assert` 整条剥离 ⇒ 检查器在优化模式下**静默失效**。
    ★ 表清单**派生自 `waiver_tables()`**（唯一真源）—— 此处**不**再手抄第二份（见该函数的注释）。
    """
    for name, table in waiver_tables():
        for key, waiver in table.items():
            for field in ("reason", "owner", "expected_consumer_by", "review_by"):
                if not getattr(waiver, field).strip():
                    raise ValueError(
                        f"{name}{key} 的 `{field}` 为空 —— `口径 13` 第 1 条要求白名单逐条自带 "
                        "reason/owner/预期何时有消费者/review_by，**写不出即不得入白名单**"
                    )
            try:
                date.fromisoformat(waiver.review_by)
            except ValueError as exc:
                raise ValueError(
                    f"{name}{key} 的 `review_by={waiver.review_by!r}` 不是 ISO 日期 —— "
                    "`口径 13` 第 2 条（过期机制）需要它可解析"
                ) from exc


def _expired_waivers(today: date) -> list[tuple[str, tuple[str, str], _Waiver]]:
    """已过 `review_by` 的豁免（`口径 13` 第 2 条：**到期未消 ⇒ 报警**）。

    ★ 抽成**带 `today` 入参**的纯函数，是为了让"过期"可被**确定性测试**：
      直接断言 `_expired_waivers(date(2026, 10, 1))` 命中、`_expired_waivers(date(2026, 9, 16))` 不命中 ——
      否则一到某天，用例就会自己变红（"到时才炸"的判据不是判据）。
    ★ 处置口径（**如实声明，请主理人裁定**）：这里报 **note + 计数**，**不阻断**。
      理由：`口径 13` 第 2 条逐字是「**报警**」而非"红"；把它升级成 exit 1 会让"某条欠账到期"
      拦住**全体成员**的提交（本项目铁律：误报刷屏的门禁一定会被关掉）。
      若主理人要求"到期即红"，改动点只有本函数调用处一处。
    """
    out: list[tuple[str, tuple[str, str], _Waiver]] = []
    for name, table in waiver_tables():              # 唯一真源（不再手抄第二份）
        for key, waiver in table.items():
            if waiver.is_expired(today):
                out.append((name, key, waiver))
    return out


_selfcheck_waivers()


# ───────────────────────── 遍历工具 ─────────────────────────


def _walk_ordered(node: ast.AST) -> Iterable[ast.AST]:
    """**源码顺序**深度优先遍历，且**不越入嵌套作用域**。

    ★ 为什么不用 `ast.walk`（两条都踩过）：
      1. `ast.walk` 是 **BFS** ⇒ `g = doc.get("group")` 可能排在 `g.get("k")` **之后**
         被访问，别名解析随机失效；
      2. `ast.walk` **会越入嵌套函数体** ⇒ 若外层再单独扫一遍内层函数，**内层被重复计数**
         （一条违例会以两条出现在报告里 —— 计数不可信）。
    """
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _SCOPE_NODES):
            continue
        yield from _walk_ordered(child)


def _iter_scope(body: list[ast.stmt]) -> Iterable[ast.AST]:
    """遍历**一个作用域自己**的语句（含 `if`/`for`/`with`/`try` 的内层），**不越入嵌套作用域**。

    ★ 这一层不能省：`_walk_ordered` 只在**子孙**处剪枝，作用域体里**直接**写着的
      `def` 仍会被 `_walk_ordered` 当作普通节点收下并深入其 `body` ——
      于是"模块域 + 该函数域"两份都扫到同一个 `Return`，**一条读被计两次**。
      （实测：`stop.py` 的 4 处读曾以 8 条违例出现在报告里 ⇒ 计数不可信。）
    """
    for stmt in body:
        if isinstance(stmt, _SCOPE_NODES):
            continue
        yield from _walk_ordered(stmt)


def _scopes(tree: ast.Module) -> list[list[ast.stmt]]:
    """模块体 + 每个（含嵌套的）函数/类体 —— **各一次、互不重叠**。"""
    scopes: list[list[ast.stmt]] = [tree.body]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scopes.append(node.body)
    return scopes


# ───────────────────────── 规则文件实有结构（唯一真源） ─────────────────────────


def _load_rule_docs(root: Path) -> dict[str, Any]:
    """读出 `rules/*.yaml` 的**实有结构**（键的唯一真源 = 文件本身，不写清单）。"""
    rules_dir = root / RULES_DIRNAME
    if not rules_dir.is_dir():
        raise FileNotFoundError(f"缺少 {RULES_DIRNAME}/ 目录 —— 声明面不在，不得当作通过（G-03）")
    docs: dict[str, Any] = {}
    for path in sorted(rules_dir.glob("*.yaml")):
        docs[path.name] = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not docs:
        raise FileNotFoundError(f"{RULES_DIRNAME}/ 下没有任何 .yaml —— 无被检对象 ≠ 已验证（G-03）")
    return docs


def _keys_of(node: Any) -> set[str]:
    return set(node) if isinstance(node, dict) else set()


def _as_relpath(value: str | None) -> str | None:
    """把字符串归一成规则文件名；**不是** `rules/<名>.yaml` 整串则 `None`。"""
    if not value:
        return None
    m = _RULE_FILE_RE.match(value.replace("\\", "/"))
    return m.group("name") if m else None


# ───────────────────────── AST → 规则文件出处 ─────────────────────────


def _path_string(node: ast.AST, consts: dict[str, str]) -> str | None:
    """把 `"a" / X / "b"` 这类路径表达式解析成**字符串后缀**；解析不出 → `None`。

    ★ **最左一段解析不出时取右段**：`path = Path(root) / SCENARIO_YAML` 里
      `Path(root)` 是调用、不可静态定值，但它右边的 `SCENARIO_YAML` **就是** `rules/scenario.yaml`
      —— 出处已经定死了。故 `left is None` 时返回 `right`（丢掉不可知的根前缀）。
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in consts:
        return consts[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _path_string(node.left, consts)
        right = _path_string(node.right, consts)
        if left is not None and right is not None:
            return f"{left.rstrip('/')}/{right.lstrip('/')}"
        return right if right is not None else None
    return None


def _relpaths_in(expr: ast.AST, consts: dict[str, str], paths: dict[str, str] | None = None) -> set[str]:
    """从表达式里收集它**引用到的规则文件名**（路径字面量 + 常量名 + `/` 拼接 + 路径变量）。

    ★ **`paths` 必须传**：`yaml.safe_load(path.read_text())` 里的 `path` 是**局部路径变量**，
      只有把 `paths` 一起看才能认出 `rules/benchmark.yaml` —— 否则 `return_guard.py`
      这个真正的规则消费者会**整块**落在覆盖面之外（实测踩过：加之前它 0 条读）。
    """
    out: set[str] = set()
    for sub in ast.walk(expr):
        if isinstance(sub, (ast.Constant, ast.Name, ast.BinOp)):
            name = _as_relpath(_path_string(sub, consts))
            if name:
                out.add(name)
            elif isinstance(sub, ast.Name) and paths and sub.id in paths:
                out.add(paths[sub.id])
    return out


def _module_constants(
    tree: ast.Module,
) -> tuple[dict[str, str], dict[str, tuple[tuple[str, ...], ...]]]:
    """模块级 **str 常量** 与 **"薄包装函数 → 按返回位置的规则文件名"**。

    常量链（`A = B` 且 `B` 是常量）取一轮不动点。

    `producers[函数名]` 是**按 `return` 语句顺序、按元组位置**铺平的规则文件名元组：
    - `def baseline_doc(root): return _load_mapping(root, R)` ⇒ `(("baseline.yaml",),)`；
    - `def _configured_source(...): return load_yaml(REL, root), REL, notes` ⇒
      `(("budget.yaml",), (), (), (), (), (), (), (), ())` —— **多值返回**。

    ★ 只有**恰好一个位置、且该位置恰好一个规则文件**时才被认定为"产出文档"。
      多值返回（`return doc, rel, notes`）**不认** —— 那种函数的返回值是"混装"，
      把它当文档会误报；它会被计成 `ambiguous_doc_vars`（**盲区可见**，不是静默漏掉）。
    """
    consts: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = node.value
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                consts[node.targets[0].id] = v.value
            elif isinstance(v, ast.Name) and v.id in consts:
                consts[node.targets[0].id] = consts[v.id]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            v = node.value
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                consts[node.target.id] = v.value

    producers: dict[str, tuple[tuple[str, ...], ...]] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        positions: list[tuple[str, ...]] = []
        for sub in _walk_ordered(node):
            if not isinstance(sub, ast.Return) or sub.value is None:
                continue
            elts = sub.value.elts if isinstance(sub.value, ast.Tuple) else [sub.value]
            for elt in elts:
                positions.append(tuple(sorted(_relpaths_in(elt, consts))))
        if any(positions):
            producers[node.name] = tuple(positions)
    return consts, producers


def _func_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _loader_relpaths(call: ast.Call, consts: dict[str, str], paths: dict[str, str]) -> set[str]:
    """一个**装载点调用**产出的规则文件名集合（不是装载点 / 解析不出 ⇒ 空集）。"""
    fname = _func_name(call.func)
    if fname not in _DOC_LOADERS:
        return set()
    idx = _DOC_LOADERS[fname]
    args = call.args[1:] if idx == 1 else (call.args[:1] if idx == 0 else call.args)
    out: set[str] = set()
    for a in args:
        out |= _relpaths_in(a, consts, paths)
    return out


def _const_str(node: ast.AST, consts: dict[str, str]) -> str | None:
    """把实参解析成字符串常量（仅字面量与模块常量；**不求值**）。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in consts:
        return consts[node.id]
    return None


def _get_key(node: ast.Call, consts: dict[str, str]) -> str | None:
    """`x.get("k")` / `x.get("k", default)` 的 `"k"`；解析不出返回 `None`。"""
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "get":
        return None
    if not node.args:
        return None
    return _const_str(node.args[0], consts)


#: 读的是别的 mapping（不是规则文档）—— **不是本守卫的对象，也不计入覆盖面**。
_NOT_A_RULE_DOC = object()
#: 接收者**已认定**是规则文档，但键解析不出 —— 计入 `unresolved_reads`（`G-03`：跳过不是通过）。
_UNRESOLVED = object()
#: 赋值右值是一个**多值返回**的薄弱包装（`return doc, rel, notes`）—— 目标变量落在盲区。
#: 计入 `ambiguous_doc_vars`：**盲区必须可见**，不能靠"没被扫到"过关（`G-03`）。
_AMBIGUOUS = object()


def _relpaths_referenced(tree: ast.Module, consts: dict[str, str]) -> set[str]:
    """模块里**提到过**的所有规则文件名（无论是否被装载、被读）。

    ★ 与 `_relpaths_in` 同一判据（整串必须是 `rules/<名>.yaml`），故散文里写
      "详见 `rules/baseline.yaml`" 之类的**说明性字符串不算引用**。
    """
    out: set[str] = set()
    for sub in ast.walk(tree):
        if isinstance(sub, (ast.Constant, ast.Name, ast.BinOp)):
            name = _as_relpath(_path_string(sub, consts))
            if name:
                out.add(name)
    return out


class _ModuleReads:
    def __init__(self) -> None:
        #: (rule_name, dotted_key, file, lineno)
        self.reads: list[tuple[str, str, str, int]] = []
        self.refs: set[str] = set()
        self.resolved_doc_vars = 0
        self.unresolved_reads = 0
        #: 经**多值返回**取得的文档变量数（盲区，见 `_AMBIGUOUS`）
        self.ambiguous_doc_vars = 0
        #: ★ 方向 2 用：本模块里**非 docstring 的字符串字面量**取值集合
        #:   （= "代码按**名字**提到了哪些键"）。见 `_code_string_literals`。
        self.literals: set[str] = set()


def _analyze_module(
    relpath: str,
    text: str,
    consts: dict[str, str],
    producers: dict[str, tuple[tuple[str, ...], ...]],
) -> _ModuleReads:
    """抽一个模块里"对规则文档的键读取"与"提到过的规则文件"。"""
    out = _ModuleReads()
    tree = ast.parse(text)
    out.refs = _relpaths_referenced(tree, consts)
    # ★ 方向 2：本模块的**非 docstring 字符串字面量**（键名的"代码消费者"证据）。
    #   复用同一棵 AST（不额外 parse 一次）⇒ 对方向 1 的开销几乎为零。
    out.literals = _code_string_literals(tree)

    # ★ 每个作用域**各扫一次、互不重叠**（见 `_scopes` / `_walk_ordered` 的说明）。
    #   跨作用域的闭包变量**不传递** ⇒ 内层函数里解析不出出处的读一律进 `unresolved`
    #   （fail-safe：宁可少报，绝不误报）。
    for body in _scopes(tree):
        docs_: dict[str, tuple[str, str | None]] = {}  # 文档变量 → (rule, group_key)
        paths_: dict[str, str] = {}                    # 路径变量 → rule

        for stmt in _iter_scope(body):
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                value = stmt.value
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                names: list[str] = []
                for t in targets:
                    if isinstance(t, ast.Name):
                        names.append(t.id)
                    elif isinstance(t, (ast.Tuple, ast.List)):
                        # `raw, source, notes = _configured_source(...)` —— 元组解包目标也要认
                        names.extend(e.id for e in t.elts if isinstance(e, ast.Name))
                if not names or value is None:
                    continue
                info = _resolve_value(value, consts, producers, docs_, paths_)
                rel = _as_relpath(_path_string(value, consts))
                for n in names:
                    if info is None or info is _AMBIGUOUS:
                        docs_.pop(n, None)
                    else:
                        docs_[n] = info
                    if rel:
                        paths_[n] = rel
                    else:
                        paths_.pop(n, None)
                if info is _AMBIGUOUS:
                    out.ambiguous_doc_vars += 1
                continue

            if isinstance(stmt, (ast.Call, ast.Subscript)):
                got = _resolve_read(stmt, consts, docs_)
                if got is None or got is _NOT_A_RULE_DOC:
                    continue
                if got is _UNRESOLVED:
                    out.unresolved_reads += 1
                    continue
                rule, dotted = got
                out.reads.append((rule, dotted, relpath, stmt.lineno))

        out.resolved_doc_vars += len(docs_)

    return out


def _resolve_value(
    value: ast.AST,
    consts: dict[str, str],
    producers: dict[str, tuple[tuple[str, ...], ...]],
    docs_: dict[str, tuple[str, str | None]],
    paths_: dict[str, str],
) -> tuple[str, str | None] | object | None:
    """把一个赋值右值解析成 `(rule, group_key)`。

    解析不出 → `None`（= 未知，但**不是**"经多值返回"的盲区）；
    是**多值返回**的薄弱包装 → `_AMBIGUOUS`（盲区，必须计数）。
    """
    if isinstance(value, ast.Call):
        fname = _func_name(value.func)
        if fname is not None and fname in producers:
            pos = producers[fname]
            if len(pos) == 1 and len(pos[0]) == 1:
                return (pos[0][0], None)
            return _AMBIGUOUS
        rels = _loader_relpaths(value, consts, paths_)
        if len(rels) == 1:
            return (next(iter(rels)), None)
        # `g = doc.get("group", {})` → 组别名
        key = _get_key(value, consts)
        recv = value.func.value if isinstance(value.func, ast.Attribute) else None
        if key is not None and isinstance(recv, ast.Name) and recv.id in docs_:
            rule, outer = docs_[recv.id]
            if outer is None:
                return (rule, key)
        return None
    if isinstance(value, ast.Subscript):
        key = _const_str(value.slice, consts)
        recv = value.value
        if key is not None and isinstance(recv, ast.Name) and recv.id in docs_:
            rule, outer = docs_[recv.id]
            if outer is None:
                return (rule, key)
        return None
    if isinstance(value, ast.BoolOp) and isinstance(value.op, ast.Or):
        # `doc = _cached_yaml(path) or {}` —— 取**第一个能定死出处**的分支
        for operand in value.values:
            got = _resolve_value(operand, consts, producers, docs_, paths_)
            if got is not None:
                return got
        return None
    if isinstance(value, ast.IfExp):
        # `doc = _cached_yaml(p) if p.exists() else None` —— **仅当另一支是 `None` 字面量**时认；
        # 两支都是真文档时不猜（可能是两份不同规则文件）⇒ 落 `unresolved`。
        for branch, other in ((value.body, value.orelse), (value.orelse, value.body)):
            if isinstance(other, ast.Constant) and other.value is None:
                return _resolve_value(branch, consts, producers, docs_, paths_)
    return None


def _resolve_read(
    node: ast.AST, consts: dict[str, str], docs_: dict[str, tuple[str, str | None]]
) -> tuple[str, str] | object | None:
    """把一个**读节点**解析成 `(rule, dotted_key)`。

    认两种读形态：`x.get("k")`（静默路径，本守卫的主靶）与 `x["k"]`
    （读不存在的键会 `KeyError` —— 仍然是键不对齐，一并报出）。

    返回三种"不是键值对"的哨兵：
    - `None`：这个节点**根本不是** mapping 读（比如普通函数调用）；
    - `_NOT_A_RULE_DOC`：是 mapping 读，但接收者**不是**规则文档 ⇒ 不是本守卫的对象；
    - `_UNRESOLVED`：接收者**是**规则文档，但键解析不出 ⇒ 计入覆盖面缺口。
    """
    if isinstance(node, ast.Subscript):
        key = _const_str(node.slice, consts)
        recv: ast.AST | None = node.value
        is_read = True
    elif isinstance(node, ast.Call):
        is_read = isinstance(node.func, ast.Attribute) and node.func.attr == "get" and bool(node.args)
        key = _get_key(node, consts)
        recv = node.func.value if isinstance(node.func, ast.Attribute) else None
    else:
        return None
    if not is_read:
        return None

    # 链式：doc.get("g", {}).get("k") / doc.get("g", {})["k"]
    if isinstance(recv, ast.Call):
        outer_key = _get_key(recv, consts)
        inner = recv.func.value if isinstance(recv.func, ast.Attribute) else None
        if isinstance(inner, ast.Name) and inner.id in docs_:
            rule, gkey = docs_[inner.id]
            if gkey is None:
                if outer_key is None or key is None:
                    return _UNRESOLVED
                return (rule, f"{outer_key}.{key}")
        return _NOT_A_RULE_DOC

    if isinstance(recv, ast.Name) and recv.id in docs_:
        rule, gkey = docs_[recv.id]
        if key is None:
            return _UNRESOLVED
        if gkey is None:
            return (rule, key)
        return (rule, f"{gkey}.{key}")

    return _NOT_A_RULE_DOC


# ───────────────────────── 方向 2：记录集合的"列"（`T-18` 家族的暴露面） ─────────────────────────


def _code_string_literals(tree: ast.AST) -> set[str]:
    """模块里**非 docstring** 的字符串字面量取值集合。

    ★ 为什么必须剔掉 docstring（这是实测盲区、不是洁癖）：死列
      `implemented_in_first_version` 改前在 `scripts/orchestrate/pipeline.py:152` /
      `ingest_step.py:4` / `chain_steps.py:6` **各出现一次，全部在 docstring 里** ——
      若把 docstring 也算成"消费者"，本方向就会**恰好漏掉它要抓的那一条**（假阴性）。
      注释不是字符串字面量（它是 `tokenize.COMMENT`，不进 AST）⇒ 天然不计入。
    """
    docstring_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                docstring_ids.add(id(first.value))
    out: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstring_ids
        ):
            out.add(node.value)
    return out


def _record_columns(doc: Any) -> list[tuple[str, str]]:
    """枚举一份规则文档里所有**记录集合**的**列**：`[(集合点路径, 列名), ...]`。

    一个「记录集合」定义为：
    ① 元素**全是 mapping** 的 `list`（例：`pipeline.yaml::steps`）；或
    ② 值**全是 mapping** 的 `dict`（例：`publish.yaml::three_layer_permission`）。
    其「列」= 集合内所有元素/值的键的**并集**。

    ★★ 为什么方向 2 必须覆盖这一层（这是 `T-18` 能长期藏住的**唯一原因**）：
      上游方向 1 与既有 `rule_key_consumer_scan` 都只枚举**叶键**（`_leaf_paths` 把 list 当叶子）
      ⇒ `steps: [ {…, implemented_in_first_version: …} ]` 的**列**根本不在它们的被检集合里。
    """
    out: list[tuple[str, str]] = []

    def visit(node: Any, path: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            values = list(node.values())
            if len(values) >= 2 and all(isinstance(v, dict) for v in values):
                columns: set[str] = set()
                for value in values:
                    columns |= set(value.keys())
                for column in columns:
                    out.append((".".join(path), column))
            for key, value in node.items():
                visit(value, path + (str(key),))
        elif isinstance(node, list):
            mappings = [e for e in node if isinstance(e, dict)]
            if len(mappings) >= 2 and len(mappings) == len(node):
                columns = set()
                for mapping in mappings:
                    columns |= set(mapping.keys())
                for column in columns:
                    out.append((".".join(path), column))
            for element in node:
                visit(element, path)

    visit(doc, ())
    # 去重（同一集合/列在多处出现时只保留一次）并稳定排序，使输出可复核。
    return sorted(set(out))


# ───────────────────────── 检查主体 ─────────────────────────

def check(root: Path) -> CheckReport:
    report = CheckReport(checker="rule_key_alignment_guard")
    docs = _load_rule_docs(root)
    by_name = {f"rules/{name}": doc for name, doc in docs.items()}

    scanned_files = 0
    total_reads = 0
    unresolved = 0
    ambiguous = 0
    whitelisted = 0
    whitelisted_absent = 0
    ref_pairs = 0
    # ★ 方向 2：`scripts/**` 全域里**非 docstring 字符串字面量**的取值并集
    #   （= "代码按名字提到过哪些键"）。由下面的既有遍历顺带累积（不额外 parse）。
    code_literals: set[str] = set()

    for path in walk_files(root, SCAN_SUBDIR):
        rel = path.relative_to(root).as_posix()
        scanned_files += 1
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            # ★ **不得吞掉**（本行原先是 `continue`，被 `no_placeholder_guard` 的
            #   `SWALLOW_EXCEPTION_CONTINUE` 当场拦下 —— 那条判据抓得对）：
            #   跳过"无法解析的文件"= 该文件**根本没被检查**，而输出里看起来一切正常，
            #   正是本守卫自己要拦的那一族（"声明 ≠ 有效力"）。
            #   `scripts/**` 下出现语法错误本身就是缺陷 ⇒ 报**输入异常**（`exit 2`）：
            #   "我没法判" 与 "对象不达标" 必须分开（与 `_rules.py::MissingRuleInput` 同一口径）。
            raise ValueError(
                f"{rel} 无法解析（{type(exc).__name__}: {exc}）—— 本守卫无法检查它，"
                "**不得当作通过**（`G-03`：无被检对象 ≠ 已验证）"
            ) from exc
        consts, producers = _module_constants(tree)
        mr = _analyze_module(rel, text, consts, producers)
        unresolved += mr.unresolved_reads
        ambiguous += mr.ambiguous_doc_vars
        code_literals |= mr.literals
        if mr.reads:
            report.scanned[f"reads::{rel}"] = len(mr.reads)
        if mr.unresolved_reads:
            report.scanned[f"unresolved::{rel}"] = mr.unresolved_reads
        if mr.ambiguous_doc_vars:
            report.scanned[f"ambiguous::{rel}"] = mr.ambiguous_doc_vars
        if mr.refs:
            report.scanned[f"rule_refs::{rel}"] = len(mr.refs)

        # ── 断言 ①：代码**引用**的规则文件必须存在（键对齐的退化情形） ──
        for rule_name in sorted(mr.refs):
            shown = f"rules/{rule_name}"
            if shown in by_name:
                continue
            ref_pairs += 1
            waiver = KNOWN_ABSENT_RULE_FILES.get((rel, rule_name))
            if waiver:
                whitelisted_absent += 1
                report.notes.append(
                    f"KNOWN(已登记·待安装规则文件) {rel} 引用 {shown} "
                    f"[owner={waiver.owner}；预期消失={waiver.expected_consumer_by}；"
                    f"review_by={waiver.review_by}] —— {waiver.reason}"
                )
                continue
            report.violations.append(
                Violation(
                    "13-pre/方向1",
                    f"代码引用了**不存在**的规则文件 {shown}。"
                    f"`rules/` 现有文件：{sorted(by_name)}。"
                    "若这是「值未冻结故暂不安装」的**刻意**状态，必须按 `G-03` + `口径 13` 逐条登记到本守卫的 "
                    "`KNOWN_ABSENT_RULE_FILES`（**四个字段都写**：reason / owner / "
                    "预期何时有消费者 / review_by），**不得**靠「没被扫到」过关。",
                    rel, 0,
                )
            )

        for rule_name, dotted, file_rel, lineno in mr.reads:
            doc = by_name.get(f"rules/{rule_name}")
            if doc is None:
                # 缺失已由断言 ① 报出（含白名单），此处不重复报
                continue
            total_reads += 1
            head, _, tail = dotted.partition(".")
            shown = f"rules/{rule_name}::{dotted}"
            if tail:
                group = doc.get(head)
                ok = isinstance(group, dict) and tail in group
            else:
                ok = head in _keys_of(doc)
            if ok:
                continue
            waiver = KNOWN_ZERO_KEY_READS.get((file_rel, shown))
            if waiver:
                whitelisted += 1
                report.notes.append(
                    f"KNOWN(已登记欠账) {file_rel}:{lineno} 读 {shown} "
                    f"[owner={waiver.owner}；预期消失={waiver.expected_consumer_by}；"
                    f"review_by={waiver.review_by}] —— {waiver.reason}"
                )
                continue
            report.violations.append(
                Violation(
                    "13-pre/方向1",
                    f"读的键 {shown} **在规则文件里不存在** ⇒ `dict.get()` 静默返回 None、"
                    f"被 `or ...` 洗成合法值（该规则『其实没被读』在任何输出里不可见）。"
                    f"该文件现有顶层键：{sorted(_keys_of(doc))}",
                    file_rel, lineno,
                )
            )

    # ── 方向 2：`rules/` 声明的「记录列」必须有代码消费者（`T-18` 家族） ──
    #   域 = 全部记录集合 × 全部列（纯遍历 YAML）；消费者 = `code_literals`（纯 AST 常量）。
    #   两侧都是可穷尽枚举 + 集合差，故命中即 fail（`G-01`；禁 warn-only）。
    reverse_columns = 0
    reverse_unconsumed = 0
    reverse_waived = 0
    for rule_name in sorted(docs):
        for collection, column in _record_columns(docs[rule_name]):
            reverse_columns += 1
            if column in code_literals:
                continue
            reverse_unconsumed += 1
            coll = collection or "<root>"
            shown = f"rules/{rule_name}::{coll}::{column}"
            waiver = KNOWN_UNCONSUMED_RULE_COLUMNS.get((rule_name, f"{coll}::{column}"))
            if waiver:
                reverse_waived += 1
                report.notes.append(
                    f"KNOWN(已登记·无消费者记录列) {shown} "
                    f"[owner={waiver.owner}；预期消失={waiver.expected_consumer_by}；"
                    f"review_by={waiver.review_by}] —— {waiver.reason}"
                )
                continue
            report.violations.append(
                Violation(
                    "13-pre/方向2",
                    f"记录列 {shown} **在 `scripts/**` 里没有任何按名字的消费者**："
                    f"它的名字既不出现在任何**非 docstring 的字符串字面量**里，也不作为键被读取。"
                    "⇒ 这份声明**在机器上零效力**（`T-18` 家族：『写在声明里』≠『在机器上有效力』）。"
                    "处置：① 给该列**接一个消费者**（推荐，见 `T-18` 的 `_deferred_by_design()` 范式）；"
                    "或 ② 若它是「**已声明、尚未接线**」的已知列，按 `口径 13` 四字段登记到本守卫的 "
                    "`KNOWN_UNCONSUMED_RULE_COLUMNS`（**四个字段都写**：reason / owner / "
                    "预期何时有消费者 / review_by），**不得**靠「没被扫到」过关。",
                    f"rules/{rule_name}", 0,
                )
            )

    report.scanned["py_files"] = scanned_files
    report.scanned["rule_files"] = len(docs)
    report.scanned["reverse_record_columns"] = reverse_columns
    report.scanned["reverse_unconsumed_columns"] = reverse_unconsumed
    report.scanned["whitelisted_unconsumed_columns"] = reverse_waived
    report.scanned["code_literal_names"] = len(code_literals)
    report.scanned["resolved_key_reads"] = total_reads
    report.scanned["unresolved_reads"] = unresolved
    report.scanned["ambiguous_doc_vars"] = ambiguous
    report.scanned["absent_rule_file_refs"] = ref_pairs
    report.scanned["whitelisted_zero_key_reads"] = whitelisted
    report.scanned["whitelisted_absent_rule_files"] = whitelisted_absent
    report.notes.append(
        "覆盖面：本守卫只认**静态可定死**的文档出处（模块常量 + `/` 拼接路径 + 作用域内路径变量 "
        "+ 三种装载点 + 同模块薄包装，取一轮不动点）与**一层组别名 / 链式 `.get`**；键为函数参数、"
        "f-string、循环变量的一律跳过并计数。★ `unresolved_reads` **只数「接收者已认定是规则文档、"
        "但键解析不出」的读**（读别的 mapping 不计入，否则上千个 `row.get(...)` 会把覆盖面淹掉）。"
        f"本树：py_files={scanned_files} / rule_files={len(docs)} / "
        f"resolved_key_reads={total_reads} / unresolved_reads={unresolved} / "
        f"ambiguous_doc_vars={ambiguous} / 引用缺失规则文件的 (文件,规则文件) 对={ref_pairs}。"
        "**跳过不是通过**（`G-03`）。"
    )
    # ★ `口径 13` 第 3 条：**输出白名单与被检集合的比值** ——
    #   让"白名单把整道门禁稀释掉"这件事**可见**（比值逼近 1 时，这道门已名存实亡）。
    key_total = total_reads + whitelisted
    file_total = ref_pairs + whitelisted_absent
    # ★ `CheckReport.scanned` 是 `dict[str, int]`（`scripts/_common.py`），故用**千分比整数**
    #   而不是浮点 —— 不为了好看去改公共契约（那会波及全部 25 道门）。
    report.scanned["waiver_ratio_keys_permille"] = (1000 * whitelisted // key_total) if key_total else 0
    report.scanned["waiver_ratio_absent_files_permille"] = (
        1000 * whitelisted_absent // file_total
    ) if file_total else 0
    report.scanned["waiver_ratio_reverse_permille"] = (
        1000 * reverse_waived // reverse_columns
    ) if reverse_columns else 0
    report.notes.append(
        f"白名单比值（`口径 13` 第 3 条）：键 {whitelisted} / {key_total}"
        f"（{100.0 * whitelisted / key_total:.1f}%）· "
        f"规则文件 {whitelisted_absent} / {file_total}"
        f"（{100.0 * whitelisted_absent / file_total:.1f}%）。"
        "★ 比值只作**可见性**用：它变高不自动等于缺陷，但**必须有人看过**。"
    )
    # ★ 方向 2（`T-18` 家族）的覆盖面与方法 —— **必须进输出**（读者要能判"这个数能不能用"）。
    report.notes.append(
        "覆盖面（方向 2 · 反向绑定）：域 = `rules/*.yaml` 的**记录集合 × 列**"
        "（元素/值全为 mapping 的 list/dict；纯遍历 YAML，无名单无关键词）；消费者 = `scripts/**` 里"
        "**非 docstring 的字符串字面量**（纯 AST 常量比对）。"
        f"本树：记录列 {reverse_columns} / 无消费者 {reverse_unconsumed} / 已登记 {reverse_waived} / "
        f"代码侧字面量名 {len(code_literals)}。"
        f"白名单比值（`口径 13` 第 3 条）：记录列 {reverse_waived} / {reverse_columns}"
        f"（{(100.0 * reverse_waived / reverse_columns) if reverse_columns else 0.0:.1f}%）。"
    )
    report.notes.append(
        "★ 方向 2 的**已知边界（如实登记，不静默）**：① 它只覆盖**记录集合的列** ——"
        "**顶层标量键**（如 `spec_anchor`）与**深层普通键**不在本方向域内（那部分由 "
        "`rule_key_consumer_scan.py` 的 ③ 候选覆盖，后者**只报 note、不阻断**）；"
        "② 消费者判据是「**按名字出现**」，故「整组通用消费」（`for k, v in group.items()`）"
        "下**未被点名的列**会被判成无消费者 —— 这类已按 `口径 13` 登记在 "
        "`KNOWN_UNCONSUMED_RULE_COLUMNS`（**不是**放宽判据）。"
    )
    if ambiguous:
        report.notes.append(
            f"★ **已知盲区（计数可见，不静默）**：`ambiguous_doc_vars={ambiguous}` —— 这些文档变量经"
            "**多值返回**的薄弱包装取得（例如 `raw, source, notes = _configured_source(...)`），"
            "本守卫**不认**这种形态（认了会误报），故其后的 `raw.get(...)` **既不进 resolved、"
            "也不进 unresolved**。要覆盖它需按\"返回位置\"做生产者分析 —— `13-pre` 未做，"
            "**如实登记**。"
        )
    # ★ `口径 13` 第 2 条：**过期机制** —— 到期未消 ⇒ **报警**（这里是 note + 计数，不阻断；
    #   取舍理由写在 `_expired_waivers` 的 docstring 里，请主理人裁定是否升为红）。
    expired = _expired_waivers(date.today())
    report.scanned["expired_waiver_entries"] = len(expired)
    for table_name, key, waiver in expired:
        report.notes.append(
            f"★★ EXPIRED(白名单已过期，`口径 13` 第 2 条) {table_name}{key} —— "
            f"review_by={waiver.review_by} 已过，欠账**仍未消**。owner={waiver.owner}；"
            f"预期消失={waiver.expected_consumer_by}。处置：① 消掉欠账；② 若确实还要等，"
            "由 owner 重定 `review_by`（**重定必须带理由**，否则等于永久豁免）。"
        )
    return report


if __name__ == "__main__":
    sys.exit(run_checker("rule_key_alignment_guard.py", check))
