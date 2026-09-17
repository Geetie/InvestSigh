#!/usr/bin/env python3
"""`research_ingest.py` —— **「研究清单」编译器**（会话内模型侧产出 → 真源）。

```
python system/scripts/ingest/research_ingest.py <code_root> [--dry-run] [--export <文件>]
```

## 这个模块补的是什么（`gap-mcp-fetch-not-reproducible` 的扩大版）

2026-09-17 冷启动端到端实测：真源从 0 行推到 395 行，靠的是 **`.workbuddy/seed/` 下
7 个脚本约 200 KB**（`seed_sources_claims` / `seed_research_structure` / `seed_entities` /
`seed_fundamentals` / `seed_repair_and_finish` / `build_views` / `build_readable_views`）。

那个目录在 `.gitignore` 内 ⇒ **不在版本库、不可重跑、不可审、不可测**。
更要命的是它内部**已经漂移**：`locator` / `period_bucket` / `metric_of` / `event_type_of`
**各写了 2~4 份**，取值不同（`_EARNINGS_METRICS` 少 6 个词元、`_PERIOD_RE` 少一种形态）
⇒ 同一次运行里不同来源的主张拿到**不同的 `event_type`**，而 `event_type` 正是
独立佐证指纹（`Ch9 §3.4.7`）的组成项 ⇒ 影响**结论强度**，且**无任何判据会发现**。

本模块把那 7 个脚本里的**机制**（不是研究内容）重写为版本库代码：

| 机制 | 原先状态 |
|---|---|
| 引文定位 `locate_quote()`（两种归一化） | 2 份不同实现 |
| **引文指纹** `quote_hash_of_located()` | ★ **4 份，且都算错了**（见下） |
| 期间桶 / 指标 / 事件类型 `period_bucket`·`metric_of`·`event_type_of` | 2 份且已漂移 |
| 行幂等追加 + `recorded_seq` 分配 | 3 份 |
| 表清单与落库顺序 | 各脚本各写一遍 |

### ★★ `quote_hash` 的契约（本次实测的**最实质修复**）

`scripts/checks/quote_provenance_guard.py::claim_quote_problems` 要求
`quote_hash == sha256(_segment(原文, start, end))` —— 即 **`sha256(locator 所指的逐字切片)`**。

而 seed 脚本写的是 `sha256(" ".join(quote.split()))` —— **归一化后的引文串**，
与"逐字切片"**不是同一条内容**（切片含原文换行与缩进）。
⇒ 那份数据**从一开始就不满足契约**，所以 `seed_repair_and_finish.py` 里才会有
一整段"**引文指纹修复**"在事后逐条重算 —— **那是补丁，不是修复**。
本模块从**产出侧**把定义改对：`quote_hash` 由 `locator` **派生**，不由调用方提供。

## ★ 设计要点

1. **接缝在投递侧**（与 `market_data.py` 同一条纪律）：会话把研究内容写成
   `raw/inbox/research_manifest_<日期>.json`，本模块负责**校验 → 派生 → 幂等落库**。
2. **机制与内容分离**：本模块**不含任何研究内容**；清单是数据（进版本库、可 diff、可重跑）。
3. **表清单唯一真源 = `TABLES`**：**导出与导入共用同一份**，故两个方向**不可能漂移**
   （本仓最高频的漂移源恰是"清单手工维护"）。
4. **未知键响亮失败**：逐行先与 `model_fields` 对照，**一次性列出全部**多余键，
   再交给 pydantic。实测价值：`Baseline.version_kind` 那类"契约缺位"缺陷
   （`extra="forbid"` 只报第一个命中，排查时得逐个试）在此处一眼可见。
5. **幂等**：按表的主键跳过已存在行，并把 `written` / `skipped` 两个集合**分开回传**
   （`Ch9 §3.5`：首跑与重跑的观测量必须可区分）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from schema.store import append_records, read_records  # noqa: E402
from scripts.validators.locator_check import parse_raw_locator  # noqa: E402

RESEARCH_INBOX_PREFIX = "research_manifest_"
"""投递口里**研究清单**的文件名前缀（与行情清单按前缀分派，同 `market_data` 的纪律）。"""

RESEARCH_INBOX_SUFFIX = ".json"
"""研究清单的后缀 —— `ingest_step.py` **按名分派**，不靠后缀猜内容。"""

MANIFEST_VERSION = 1
"""清单格式版本（结构变更时递增；本模块只接受本版本 + 未知版本响亮失败）。"""


class ResearchIngestError(ValueError):
    """清单不可用（结构 / 引用 / 契约）—— **响亮失败**，绝不静默跳行（`G-03`）。"""


# ══════════════════════════ 一、机制层（唯一真源） ══════════════════════════
#
# 这一节是本次内化的**主体**：原先散在 7 个会话脚本里、且已互相漂移的那些函数。


def _normalize_lines(lines: Sequence[str], *, join_with_space: bool) -> tuple[str, list[int]]:
    """把整份原文归一化成一个串，并给出**每个字符所属的行号**（1-based）。

    `join_with_space=True`  → 行间插一个空格（英文引文自带空格，能对上）；
    `join_with_space=False` → 行间**不插**（中日文引文跨行处原文没有空格）。

    ★ 为什么两种都要：见 `locate_quote`。原先两个会话脚本**各自只实现了一种**
      （一个用插空格、另一个才补了去空白），于是"某些引文能定位、另一些报 MISS"
      取决于**是哪段脚本写的** —— 同一个缺陷在不同脚本里表现不同，最难排查。
    """
    parts: list[str] = []
    owner: list[int] = []
    for lineno, line in enumerate(lines, start=1):
        norm = (" ".join(line.split()) if join_with_space else "".join(line.split()))
        if not norm:
            continue
        if parts and join_with_space:
            parts.append(" ")
            owner.append(lineno)
        parts.append(norm)
        owner.extend([lineno] * len(norm))
    return "".join(parts), owner


def locate_quote(root: str | Path, relpath: str, quote: str) -> str:
    """把引文映射回 `raw/` 的**行区间**：`raw/<relpath>#L<a>-L<b>`。

    **两种归一化都试**（先"行间插空格"再"全部去空白"），命中即返回；
    两种都不命中 → **响亮失败**（`ResearchIngestError`，不静默返回一个坏 locator）。

    ★ 顺序有意义：先试插空格形态可保住"不误定位"（去空白形态更容易误命中短串），
      再试去空白形态可覆盖跨行的长引文。
    """
    path = Path(root) / "raw" / relpath
    if not path.is_file():
        raise ResearchIngestError(f"引文定位失败：raw/{relpath} 不是常规文件（清单引用了不存在的原文）")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ResearchIngestError(f"raw/{relpath} 不可读（非 UTF-8 或 IO 失败）：{exc}") from exc

    for join_with_space in (True, False):
        hay, owner = _normalize_lines(lines, join_with_space=join_with_space)
        needle = " ".join(quote.split()) if join_with_space else "".join(quote.split())
        if not needle:
            continue
        pos = hay.find(needle)
        if pos >= 0:
            return f"raw/{relpath}#L{owner[pos]}-L{owner[pos + len(needle) - 1]}"
    raise ResearchIngestError(
        f"[LOCATOR-MISS] raw/{relpath}: 引文未在原文中逐字命中（两种归一化都试过）：{quote[:80]!r}"
    )


def _segment(text: str, first_line: int, last_line: int) -> str:
    """取原文第 `first_line`..`last_line` 行的**逐字切片**（1-based 闭区间，含行尾换行）。

    ★ 公式与两处既有实现**逐字相同**，但**不是同一份代码**：
      - `scripts/checks/quote_provenance_guard.py::_segment`（守卫侧，**刻意**独立实现）；
      - `scripts/guard/executor.py::_quote_segment`（采集侧）。
      三份并存是**有意**的（判据不得复用被验证方的实现）——
      但"公式相同"这件事**必须被机器检查**：见
      `tests/unit/test_research_ingest.py::test_segment_matches_guard_implementation`
      （元断言：三份在边界用例上给同一答案；任何一处改了公式即变红）。
    """
    return "".join(text.splitlines(keepends=True)[first_line - 1 : last_line])


def quote_hash_of_located(root: str | Path, locator: str) -> str:
    """`quote_hash` = `sha256(locator 区间逐字切片)` —— **从 locator 派生**，不由调用方给。

    ★ 这是本模块对 `P-01` 的**唯一正确实现**（原 seed 脚本算的是归一化引文串的哈希，
      见模块 docstring）。调用方（清单）**不得**自带 `quote_hash`：带了也**不采信**，
      而是**当场重算并与清单里的值比对**，不一致 → 响亮失败（把"事后修复"变成"产出即正确"）。
    """
    parsed = parse_raw_locator(locator)
    if parsed is None:
        raise ResearchIngestError(
            f"`quote_hash` 只能由 `raw/<relpath>#L<a>-L<b>` 形式的 locator 派生，实得 {locator!r}"
        )
    relpath, start, end = parsed
    path = Path(root) / "raw" / relpath
    text = path.read_text(encoding="utf-8")
    return hashlib.sha256(_segment(text, start, end).encode("utf-8")).hexdigest()


_PERIOD_RE = re.compile(r"(q[1-4]\s?fy\d{2}|q[1-4]-\d{4}|fy\d{2})")
"""期间词元：**两份会话实现的并集**。

- `seed_sources_claims.py` 只认 `q[1-4]fy\\d{2}|fy\\d{2}`；
- `seed_research_structure.py` 多认 `q[1-4]-\\d{4}`（自然年季度）与 `q[1-4]\\s?fy\\d{2}`。
⇒ 取并集：任何**一份**原先能识别的形态，现在都识别。
"""


def period_bucket(key: str) -> str:
    """从主张键里取**期间桶**：`q2fy27` → `FY2027Q2` · `q2-2026` → `CY2026Q2` · 无 → `undated`。"""
    match = _PERIOD_RE.search(key)
    if match is None:
        return "undated"
    token = match.group(1).replace(" ", "")
    if token.startswith("q") and "fy" in token:
        return f"FY20{token[4:]}{token[0:2].upper()}"
    if token.startswith("q") and "-" in token:
        # ★★ 形态是 `q<季度>-<自然年>`（`_PERIOD_RE` 的 `q[1-4]-\d{4}`），故**季度在前**。
        #   这里修掉一个**从会话脚本继承来的真 bug**：原 `seed_research_structure.py` 写的是
        #   `y, q = tok[1:].split("-")`（把年当季度），于是 `q2-2026` 被算成 `CY2Q2026` ——
        #   一个**看起来合法但年份/季度互换**的期间桶。它没有被发现，是因为当时那条路径
        #   产出的主张在别处显式写了 `period_bucket`（`seed_entities.py` 的 TSMC 事件），
        #   派生值**从未被消费** ⇒ 错值静默存活。
        quarter, year = token[1:].split("-")
        return f"CY{year}Q{quarter}"
    return f"FY20{token[2:]}"


def metric_of(key: str, override: str | None = None) -> str:
    """从主张键里取**指标名**：去掉期间词元与转述前缀 `restate-`。

    ★ 去 `restate-` 的目的是让**转述**与它引用的**根**落在同一指标上
      （`Ch9 §3.4.7`"同源两条引文只能算一份独立佐证"在指纹层的落地）。
    """
    if override:
        return override
    stripped = _PERIOD_RE.sub("", key.replace("restate-", ""))
    return "-".join(part for part in stripped.split("-") if part)


_EARNINGS_METRIC_PREFIXES: tuple[str, ...] = (
    "rev", "gm", "opex", "opinc", "eps", "netincome", "dc-", "edge-", "buyback",
    "hyperscale", "acie", "grace", "spectrumx",
    # ★ 以下是 `seed_research_structure.py` 有、而 `seed_sources_claims.py` **没有**的那 6 个
    #   —— 取并集的直接后果：那两个脚本各自产出的主张，此前拿到的 `event_type` **不同**。
    "azure", "rpo", "mcloud", "hpc", "node", "capex",
)
"""`earnings` 的指标前缀（两份会话实现的**并集**）。"""

_GUIDANCE_METRIC_PREFIXES: tuple[str, ...] = ("guide", "anthropic", "msft-azure", "helios")
"""`guidance` 的指标前缀（并集）。"""

_SUPPLY_METRIC_PREFIXES: tuple[str, ...] = (
    "supply", "total-commitments", "additional-commitments", "plan-sk-hynix",
)

_PRODUCT_METRIC_PREFIXES: tuple[str, ...] = (
    "vr", "reporting-framework", "plan-aws", "forecast-vr",
)


def event_type_of(metric: str) -> str:
    """事件类型 token（`EventType` 域）：**只由 metric 决定**。

    ★ "只由 metric 决定"是有意的：转述与其根用的是**同一个** metric
      （`metric_of` 去掉了 `restate-`），故两者**必然同类** —— 独立佐证计数不会被
      "转述换个写法就变成另一类事件"污染。
    """
    if metric.startswith(_EARNINGS_METRIC_PREFIXES):
        return "earnings"
    if metric.startswith(_GUIDANCE_METRIC_PREFIXES):
        return "guidance"
    if metric.startswith(_SUPPLY_METRIC_PREFIXES):
        return "supply"
    if metric.startswith(_PRODUCT_METRIC_PREFIXES):
        return "product"
    return "other"


def claim_id_of(source_key: str, key: str) -> str:
    """主张 id 的**唯一**构造式：`claim-<source_key>-<key>`。

    ★ 原先 4 个会话脚本各写一遍这个 f-string；`claim_id_of` 把它收成一处，
      使"引用一个主张"与"定义一个主张"**不可能**拼出不同的串。
    """
    return f"claim-{source_key}-{key}"


# ══════════════════════════ 二、表清单（唯一真源） ══════════════════════════


@dataclass(frozen=True)
class _Ctx:
    """一次编译的公共上下文（时间轴 / 已有行 / 序号水位）。"""

    root: Path
    system_time: datetime
    run_date: date
    seq_watermark: dict[str, int] = field(default_factory=dict)


def _claim_inputs(row: dict[str, Any]) -> tuple[str, str, str, str]:
    """取（或**从行本身反推**）主张的四个派生输入：`(source_key, key, quote, raw_relpath)`。

    ★★ 为什么必须能反推（而不是只接受清单显式给出）：

      **会话**写清单时给的是**最小输入**（`source_key` / `key` / `quote` / `raw_relpath`），
      机制把其余全部算出来；而**导出**得到的是**成品行**（只有 `claim_id` / `locator` /
      `impact_capability.quote`，没有那四个输入）。

      若只支持前者，`导出 → 清空 → 导入` 的往返就**不可能**做 —— 而往返正是
      "内化后的机制真的能重建会话产出"的唯一机器证明。

    ⇒ 反推规则三条，全部是**结构性**的，不是猜测：
      - `key = claim_id.removeprefix(f"claim-{source_id}-")`（`claim_id_of` 的逆）；
      - `raw_relpath` 来自 `locator` 的语法解析（`locator_check.parse_raw_locator`，共享契约）；
      - `quote` 取 `impact_capability.quote`（`Ch9 §3.4.7` 里它就是为这一用途落的）。
    """
    raw_relpath = row.pop("raw_relpath", None)
    key = row.pop("key", None)
    quote = row.pop("quote", None)
    source_key = row.pop("source_key", None)

    claim_id = str(row.get("claim_id") or "")
    source_id = str(row.get("source_id") or "")
    if key is None or source_key is None:
        prefix = f"claim-{source_id}-"
        if not source_id or not claim_id.startswith(prefix):
            raise ResearchIngestError(
                f"{body_of(row)}: 无法确定主张的 `key` —— 清单既未给 `key`，"
                f"且 `claim_id` 不是 `claim-<source_id>-<key>` 形态（source_id={source_id!r}）"
            )
        source_key = source_key or source_id
        key = key or claim_id[len(prefix):]

    parsed = parse_raw_locator(str(row.get("locator") or ""))
    if raw_relpath is None:
        if parsed is None:
            raise ResearchIngestError(
                f"{body_of(row)}: 清单既未给 `raw_relpath`，现有 `locator` 也不是 "
                f"`raw/<relpath>#L<a>-L<b>` 形态 ⇒ 引文无法定位（`P-01`）"
            )
        raw_relpath = parsed[0]
    if quote is None:
        quote = str((row.get("impact_capability") or {}).get("quote") or "")
    if not quote:
        raise ResearchIngestError(
            f"{body_of(row)}: 无引文可定位 —— 清单未给 `quote`，行内也没有 "
            "`impact_capability.quote`（引文指纹的输入缺失，不得静默跳过）"
        )
    return str(source_key), str(key), str(quote), str(raw_relpath)


def _derive_claims(row: dict[str, Any], ctx: _Ctx) -> None:
    """主张的**可确定派生**：`locator` / `quote_hash` / `impact_capability` 三键。

    输入可以是**最小形式**（`source_key`/`key`/`quote`/`raw_relpath`）也可以是**成品行**
    （见 `_claim_inputs`）。**任何**既有值都会被重算并**比对**：不一致即响亮失败 ——
    这让"事后修复引文指纹"（原 `seed_repair_and_finish.py` 的第三段）变成**产出即正确**。
    """
    source_key, key, quote, relpath = _claim_inputs(row)
    row.setdefault("claim_id", claim_id_of(source_key, key))

    located = locate_quote(ctx.root, relpath, quote)
    previous = row.get("locator")
    if previous is not None and str(previous) != located:
        raise ResearchIngestError(
            f"{body_of(row)}: 行内 `locator` 与按 `quote` 重新定位的结果不一致 —— "
            f"{previous!r} vs {located!r}（两者必须指向同一条内容）"
        )
    row["locator"] = located

    derived_hash = quote_hash_of_located(ctx.root, located)
    declared = row.get("quote_hash")
    if declared is not None and str(declared) != derived_hash:
        raise ResearchIngestError(
            f"{body_of(row)}: `quote_hash` 与 locator 区间切片不符 —— 该值**必须由机制派生**"
            f"（`P-01`），不得由调用方提供。（给 {str(declared)[:12]}… / 派生得 {derived_hash[:12]}…）"
        )
    row["quote_hash"] = derived_hash

    metric = metric_of(key, row.pop("metric", None))
    cap = dict(row.get("impact_capability") or {})
    cap["metric"] = metric
    cap["period_bucket"] = period_bucket(key)
    cap["event_type"] = event_type_of(metric)
    # ★ 引文**必须随行持久化**：`_claim_inputs` 在"成品行"形态下正是从
    #   `impact_capability.quote` 反推 `quote` 的（否则导出→导入不可能往返）。
    #   口径与既有真源一致：折叠空白后的引文串（不是切片 —— 切片是 `quote_hash` 的输入）。
    cap["quote"] = " ".join(quote.split())
    row["impact_capability"] = cap


def body_of(row: Mapping[str, Any]) -> str:
    """给错误信息一个**可指名**的行标识（不猜、不编）。"""
    for key in ("claim_id", "source_id", "company_id", "baseline_id", "recommendation_id", "task_id"):
        if row.get(key):
            return f"{key}={row[key]!r}"
    return f"行(前 40 字符)={json.dumps(dict(list(row.items())[:3]), ensure_ascii=False)[:40]}"


def _derive_sources(row: dict[str, Any], ctx: _Ctx) -> None:
    """来源的**可确定派生**：`content_hash` 与 `raw_line_count`（都由 raw 文件本身决定）。"""
    raw_rel = row.get("raw_path") or (row.get("observed_stats") or {}).get("raw_path")
    if not raw_rel:
        return
    path = ctx.root / str(raw_rel)
    if not path.is_file():
        raise ResearchIngestError(f"{body_of(row)}: 清单声明的原文不存在：{raw_rel}")
    text = path.read_text(encoding="utf-8")
    row["content_hash"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    stats = dict(row.get("observed_stats") or {})
    stats["raw_line_count"] = len(text.splitlines())
    row["observed_stats"] = stats


@dataclass(frozen=True)
class TableSpec:
    """一张表的编译规则（**导出与导入共用** —— 这是"不可能漂移"的结构性保证）。"""

    stem: str
    pk: tuple[str, ...]
    derive: Callable[[dict[str, Any], _Ctx], None] | None = None
    #: 导出时的**归属过滤**：只导出属于"研究内容"的行（`None` = 全表）。
    owns: Callable[[Mapping[str, Any]], bool] | None = None


def _owns_review_task(row: Mapping[str, Any]) -> bool:
    """`tasks` 表里**属于研究清单**的行 = 三层复盘行 + 缺口任务行。

    ★ 其余 `tasks` 行（每日运行的 `check_record` 行、降级标记行）由**编排器**写，
      不归研究清单 ⇒ 不导出、不重放（否则两个写入方会互相覆盖对方的观测面）。
    """
    task_id = str(row.get("task_id") or "")
    key = str(row.get("idempotency_key") or "")
    return task_id.startswith("task_eval_") or key.startswith("research::")


TABLES: tuple[TableSpec, ...] = (
    TableSpec("companies", ("company_id",)),
    TableSpec("securities", ("security_id",)),
    TableSpec("products", ("product_id",)),
    TableSpec("sources", ("source_id",), derive=_derive_sources),
    TableSpec("claims", ("claim_id",), derive=_derive_claims),
    TableSpec("businesses", ("business_id",)),
    TableSpec("drivers", ("driver_id",)),
    TableSpec("baselines", ("baseline_id", "version")),
    TableSpec("relations", ("relation_id",)),
    TableSpec("relation_flows", ("flow_id",)),
    TableSpec("business_positions", ("company_id", "node_id")),
    TableSpec("events", ("event_id",)),
    TableSpec("impacts", ("impact_id",)),
    TableSpec("expectations", ("sample_id",)),
    TableSpec("claim_propagation", ("propagation_id",)),
    TableSpec("recommendations", ("recommendation_id",)),
    TableSpec("tasks", ("task_id",), owns=_owns_review_task),
)
"""**表清单唯一真源**（顺序 = 落库顺序，满足引用依赖）。

★ 为什么"导出与导入共用一份"是结构性保证：本仓最高频的漂移源正是"清单手工维护"
  （已栽 ≥5 次，症状恒为**假红**）。顺序、主键、派生规则三样若分两处写，
  `export → wipe → import` 的等价性就**不可能**被保证。
"""

_TABLE_BY_STEM: dict[str, TableSpec] = {spec.stem: spec for spec in TABLES}

#: 不在本模块管辖的表（各自有**唯一**写入方；列举出来是为了让"缺席"也是**显式**的）。
NOT_OWNED_BY_RESEARCH: dict[str, str] = {
    "industry_nodes": "scripts/ingest/seed_industry_nodes.py（产业节点种子，已内化）",
    "prices": "scripts/ingest/market_data.py（行情清单）",
    "benchmarks": "scripts/ingest/market_data.py（基准清单）",
    "dependency_edges": "★ 尚无生产写入方（缺口 `B-2`）",
    "implied_requirements": "★ 尚无生产写入方（缺口 `B-15`/`C-1`）",
}


# ══════════════════════════ 三、通用写库机制 ══════════════════════════


def next_seq(root: str | Path, stem: str, ctx: _Ctx | None = None) -> int:
    """下一个 `recorded_seq` = 该表当前最大值 + 1（**不得**恒为 1）。

    追加式不可变真源以 `recorded_seq` 区分同一业务键的版本（`Ch9 §3.4.1`）；
    首跑时自然得 1（与既有数据一致），重跑时 idempotent 跳过故不消耗。
    ★ 水位在**一次编译内**缓存（`ctx.seq_watermark`），避免每行都重扫整表。
    """
    if ctx is not None and stem in ctx.seq_watermark:
        seq = ctx.seq_watermark[stem] + 1
        ctx.seq_watermark[stem] = seq
        return seq
    numeric = [
        row.get("recorded_seq")
        for row in read_records(Path(root), stem)
        if isinstance(row.get("recorded_seq"), int)
    ]
    seq = (max(numeric) if numeric else 0) + 1
    if ctx is not None:
        ctx.seq_watermark[stem] = seq
    return seq


def _validate_keys(stem: str, rows: Sequence[Mapping[str, Any]]) -> None:
    """逐行与模型字段对照，**一次性列出全部**多余键（`extra="forbid"` 只报第一个）。

    实测价值：`Baseline.version_kind` 那类"契约缺位"缺陷在此处一眼可见 ——
    否则得靠 pydantic 逐个试，且**同一行有多个多余键时改一个才现一个**。
    """
    from schema.models import model_for

    allowed = set(model_for(stem).model_fields)
    problems: list[str] = []
    for row in rows:
        extra = sorted(set(row) - allowed)
        if extra:
            problems.append(f"  {body_of(row)}: 多余键 {extra}")
    if problems:
        raise ResearchIngestError(
            f"facts/{stem}.jsonl 的行模型不认以下键（`extra=forbid`）：\n"
            + "\n".join(problems)
            + "\n★ 这通常意味着**契约缺位**（设计里有、模型里没有）或清单写错 —— "
            "两者都不许静默丢弃（`R-04`：不擅自扩契约；先登记、再改模型）。"
        )


def append_idempotent(
    root: str | Path, stem: str, rows: Sequence[Any], *, ctx: _Ctx | None = None
) -> tuple[list[str], list[str]]:
    """按**业务主键 + 出现序**幂等追加；返回 `(本轮真正写入的 id, 幂等跳过的 id)`。

    ★ 两集合必须分开（`Ch9 §3.5`）：若折成一个，"首跑"与"重跑"的观测量相同
      ⇒ 幂等性在输出上**不可区分**（本仓 `test_step_wiring` 已把该语义钉死）。

    ★★ 为什么键是"**主键 + 出现序**"而不是"**主键**"（2026-09-17 往返验证抓到）：

      追加式真源里**同一主键可以有多行** —— 它们就是该业务键的**版本序列**
      （`Ch9 §3.4.1`："同一业务键取 `recorded_seq` 最大者为当前版本"）。
      实测形态：`facts/drivers.jsonl` **18 行 / 只有 9 个不同 `driver_id`**
      （会话的"收口"脚本为补 `financial_link.formula_ref` 把 9 条各**追加了一份**）。

      若按主键去重：首跑会把 18 行里的后 9 行**当重复丢掉** ⇒ 真源里只剩 9 行，
      而"补过 formula_ref 的那一版"正是后 9 行 ⇒ **静默丢掉了修正版**。
      重跑时才"恰好"看起来对（重跑本来就该一行不写）—— 典型的**首跑就错、重跑隐藏**。

      ⇒ 正确语义：清单是**有序序列**；某主键的第 N 行对应真源里该主键的第 N 行。
      于是"已存在前 k 行 ⇒ 跳过清单里该主键的前 k 行、写入其余"，
      首跑写全部、重跑一行不写，**且版本序列完整**。
    """
    spec = _TABLE_BY_STEM[stem]
    if not rows:
        return [], []
    fresh, written, skipped = partition_new(spec, rows, read_records(Path(root), stem))
    if fresh:
        append_records(Path(root), stem, fresh)
    return written, skipped


def partition_new(
    spec: TableSpec, rows: Sequence[Any], existing: Sequence[Mapping[str, Any]]
) -> tuple[list[Any], list[str], list[str]]:
    """幂等规则的**唯一真源**：把模型行切成 `(待写入, written_ids, skipped_ids)`。

    ★ 为什么必须抽出来：`dry_run` 与真实写入问的是**同一个问题**
      （"这行会不会被写"）。两处各写一遍 ⇒ 迟早一处改、另一处不改 ⇒
      **预检报告与实际写入不一致**（而预检的全部价值就在"预检说的话算数"）。
      本仓"清单手工维护 ⇒ 漂移"已栽 ≥5 次，症状恒为**假**信息。
    """
    dumped = [row.model_dump(mode="json") for row in rows]
    existing_count: dict[tuple[str, ...], int] = {}
    for r in existing:
        key = tuple(str(r.get(f)) for f in spec.pk)
        existing_count[key] = existing_count.get(key, 0) + 1

    seen: dict[tuple[str, ...], int] = {}
    fresh: list[Any] = []
    written: list[str] = []
    skipped: list[str] = []
    for row, raw in zip(rows, dumped):
        key = tuple(str(raw.get(f)) for f in spec.pk)
        ordinal = seen.get(key, 0) + 1
        seen[key] = ordinal
        ident = "/".join(str(raw.get(f)) for f in spec.pk)
        if ordinal <= existing_count.get(key, 0):
            skipped.append(f"{ident}#{ordinal}")
            continue
        fresh.append(row)
        written.append(f"{ident}#{ordinal}")
    return fresh, written, skipped


# ══════════════════════════ 四、导出 ══════════════════════════


def _export_claim(row: Mapping[str, Any]) -> dict[str, Any]:
    """主张行的导出形态 = **行本身** + **派生不出来的输入**（最小必要集）。

    ★ 为什么要有这一步（2026-09-17 往返验证抓到）：

      `metric` 在机制里是 `metric_of(key, override)` —— 允许调用方给出**覆盖值**
      （原会话脚本的 `NEWC` 元组第 7 项就是它，例如把 `anthropic-2gw-mi450` 覆盖成
      `anthropic-2gw`）。**覆盖值不可从行反推**（行里只存结果，不存"它是覆盖来的"）
      ⇒ 若导出时不带上它，导入只能按 `key` 重新派生 ⇒ 得到**另一个合法但不同**的值
      ⇒ 往返不等价，而两边都"看起来对"（最难发现的一类）。

      ⇒ 一般原则：**导出必须带上"重新派生不出来的那把输入"**，其余一律不导出
        （导出一份自己也能算出来的东西，等于给了它两个真源）。
    """
    out = dict(row)
    capability = row.get("impact_capability") or {}
    claim_id = str(row.get("claim_id") or "")
    source_id = str(row.get("source_id") or "")
    prefix = f"claim-{source_id}-"
    if source_id and claim_id.startswith(prefix):
        out["source_key"] = source_id
        out["key"] = claim_id[len(prefix):]
    parsed = parse_raw_locator(str(row.get("locator") or ""))
    if parsed is not None:
        out["raw_relpath"] = parsed[0]
    if capability.get("quote"):
        out["quote"] = capability["quote"]
    # ★ 只在**与派生值不同**时导出 `metric`（= 它确实是覆盖值）。相同则不导出 ——
    #   与派生值相同的输入是冗余信息，冗余就是漂移的入口。
    if "key" in out and capability.get("metric"):
        derived = metric_of(str(out["key"]))
        if str(capability["metric"]) != derived:
            out["metric"] = capability["metric"]
    return out


def export_manifest(
    root: str | Path, *, run_date: str, system_time: str | None = None
) -> dict[str, Any]:
    """把当前真源里的**研究内容**导出为清单（供清空后重跑，或供人工 diff）。

    ★ 往返等价由 `tests/unit/test_research_ingest.py::test_manifest_roundtrip_...` 钉住；
      `claims` 需额外带上"派生不出来的输入"，见 `_export_claim`。
    """
    root_path = Path(root)
    out: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "run_date": run_date,
        "system_time": system_time or datetime.now(timezone.utc).isoformat(),
        "tables": {},
    }
    for spec in TABLES:
        rows = read_records(root_path, spec.stem)
        if spec.owns is not None:
            rows = [r for r in rows if spec.owns(r)]
        if not rows:
            continue
        if spec.stem == "claims":
            out["tables"][spec.stem] = [_export_claim(r) for r in rows]
        else:
            out["tables"][spec.stem] = [dict(r) for r in rows]
    return out


# ══════════════════════════ 五、导入（编译） ══════════════════════════


@dataclass
class CompileReport:
    """一次编译的**如实**回传（`R-03`：降级与跳过都要可见）。"""

    filename: str = ""
    written: dict[str, list[str]] = field(default_factory=dict)
    skipped: dict[str, list[str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def rows_written(self) -> int:
        return sum(len(v) for v in self.written.values())

    @property
    def rows_skipped(self) -> int:
        return sum(len(v) for v in self.skipped.values())

    def render(self) -> str:
        parts = [
            f"{stem}: +{len(self.written.get(stem, []))}"
            + (f"（幂等跳过 {len(self.skipped[stem])}）" if self.skipped.get(stem) else "")
            for stem in (*self.written, *self.skipped)
        ]
        return " · ".join(parts) if parts else "无行"


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ResearchIngestError(f"研究清单不存在：{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResearchIngestError(f"{path}: 非法 JSON：{exc}") from exc
    if not isinstance(data, Mapping):
        raise ResearchIngestError(f"{path}: 清单顶层必须是 object")
    version = data.get("manifest_version")
    if version != MANIFEST_VERSION:
        raise ResearchIngestError(
            f"{path}: 清单版本 {version!r} 不受支持（本模块只认 {MANIFEST_VERSION}）—— "
            "**不静默按旧版解析**（结构性差异会被读成'清单写错'）"
        )
    unknown = sorted(set(data.get("tables") or {}) - set(_TABLE_BY_STEM))
    if unknown:
        raise ResearchIngestError(
            f"{path}: 清单含本模块不管辖的表 {unknown}；不管辖的表及其唯一写入方见 "
            f"`NOT_OWNED_BY_RESEARCH`（不得由本模块代写）"
        )
    return dict(data)


def compile_manifest(
    root: str | Path, manifest: Mapping[str, Any], *, filename: str = "", dry_run: bool = False
) -> CompileReport:
    """把一份清单编译成真源行并**幂等落库**（校验 → 派生 → 定序 → 写）。

    ★ 全程**不吞错**：任何一个引用 / 契约 / 结构问题都**响亮失败**且**一行不写**
      （先完成全部派生与校验，最后才 `append_records`）—— 半途写一半的状态
      会让"重跑到底干净了吗"变成不可判定。
    """
    from schema.models import model_for

    root_path = Path(root)
    report = CompileReport(filename=filename)
    tables: Mapping[str, Any] = manifest.get("tables") or {}
    if not tables:
        report.notes.append("清单为空（无 tables）—— 无被检对象，**不等于**'已落库'（G-03）")
        return report

    run_date = date.fromisoformat(str(manifest["run_date"]))
    system_time = datetime.fromisoformat(str(manifest["system_time"]))
    if system_time.tzinfo is None:
        raise ResearchIngestError("清单的 `system_time` 必须带时区（UTC）")
    ctx = _Ctx(root=root_path, system_time=system_time, run_date=run_date)

    # ── ① 先全部派生 + 校验（此时**尚未写盘**）──────────────────────────────
    staged: dict[str, list[Any]] = {}
    for spec in TABLES:                      # ★ 顺序 = `TABLES` 的顺序（引用依赖）
        raw_rows = tables.get(spec.stem) or []
        if not isinstance(raw_rows, list):
            raise ResearchIngestError(f"{filename}: tables.{spec.stem} 必须是数组")
        prepared: list[dict[str, Any]] = []
        for raw in raw_rows:
            if not isinstance(raw, Mapping):
                raise ResearchIngestError(f"{filename}: tables.{spec.stem} 的成员必须是 object")
            row = dict(raw)
            row.pop("recorded_seq", None)      # `recorded_seq` **一律由机制分配**，清单不得自带
            if spec.derive is not None:
                spec.derive(row, ctx)
            prepared.append(row)
        _validate_keys(spec.stem, prepared)
        model = model_for(spec.stem)
        staged[spec.stem] = [model.model_validate(row) for row in prepared]

    # ── ② 一次性写盘（全部通过后才写第一个字）──────────────────────────────
    if dry_run:
        # ★ `dry_run` **必须真的不写盘**：只把"将写入 / 将跳过"算出来。
        #   原实现只往 notes 加一句话 —— 那会让"预检"变成一次真实写入（危险且不可察觉）。
        for spec in TABLES:
            rows = staged.get(spec.stem) or []
            if not rows:
                continue
            _fresh, will_write, will_skip = partition_new(
                spec, rows, read_records(root_path, spec.stem)
            )
            if will_write:
                report.written[spec.stem] = will_write
            if will_skip:
                report.skipped[spec.stem] = will_skip
        report.notes.append("dry-run：以上为**将写入 / 将跳过**的行，未写盘")
        return report

    for spec in TABLES:
        rows = staged.get(spec.stem) or []
        filled = 0
        for row in rows:
            row.recorded_seq = next_seq(root_path, spec.stem, ctx)
            if hasattr(row, "first_seen_at") and row.first_seen_at is None:
                row.first_seen_at = ctx.system_time
                filled += 1
            if hasattr(row, "analyzed_at") and row.analyzed_at is None:
                row.analyzed_at = ctx.system_time
        if filled:
            # ★ 补全必须**可见**（`R-03`）：system_time 是"永不未知"的一类时间
            #   （`Ch9 §2.2`），清单里若为空则由机制补；补齐不等于"原本就是这样"，
            #   故逐表报出条数，供人工判"是清单漏写还是设计允许"。
            report.notes.append(
                f"{spec.stem}: 补全 {filled} 行的 `first_seen_at`（清单未给 system_time）"
            )
        written, skipped = append_idempotent(root_path, spec.stem, rows, ctx=ctx)
        # ★ 只在**非空**时登记：否则 `written == {"claims": []}` 会被读成"写过 claims"
        #   —— 而 `report.written` 的语义是"本轮**真正写入**的 id"（两个集合必须二分）。
        if written:
            report.written[spec.stem] = written
        if skipped:
            report.skipped[spec.stem] = skipped
    return report


def research_inbox_files(root: str | Path) -> list[Path]:
    """投递口下的研究清单文件（按名排序，保证可复现）。"""
    inbox = Path(root) / "raw" / "inbox"
    if not inbox.is_dir():
        return []
    return sorted(
        p
        for p in inbox.iterdir()
        if p.is_file()
        and p.name.startswith(RESEARCH_INBOX_PREFIX)
        and p.name.endswith(RESEARCH_INBOX_SUFFIX)
    )


def is_research_manifest(name: str) -> bool:
    """文件名是否是研究清单（`ingest_step.py` **按名前缀分派**，不靠后缀猜内容）。"""
    return name.startswith(RESEARCH_INBOX_PREFIX) and name.endswith(RESEARCH_INBOX_SUFFIX)


def ingest_research_file(
    root: str | Path, spec_path: str | Path, *, dry_run: bool = False
) -> CompileReport:
    """编译单个清单文件。`dry_run=True` → 只校验与派生，不写盘（供预检）。"""
    path = Path(spec_path)
    manifest = _load_manifest(path)
    return compile_manifest(root, manifest, filename=path.name, dry_run=dry_run)


def ingest_research_inbox(root: str | Path) -> tuple[list[str], list[str], bool, list[str]]:
    """编译投递口下的全部研究清单，返回 `(written, skipped, degraded, notes)`。

    与 `market_data.ingest_market_inbox` **逐字同形**（同一套接缝约定），
    便于 `ingest_step.py` 用同一模式接两条通路。
    """
    root_path = Path(root)
    notes: list[str] = []
    written: list[str] = []
    skipped: list[str] = []
    degraded = False
    for path in research_inbox_files(root_path):
        try:
            report = ingest_research_file(root_path, path)
        except ResearchIngestError as exc:
            # ★ 清单不可用 ⇒ **响亮**报出并置降级（不静默跳过：跳过的清单看起来"没问题"）
            notes.append(f"{path.name}: [RESEARCH-MANIFEST-ERROR] {exc}")
            degraded = True
            continue
        notes.append(f"{path.name}: {report.render()}")
        for stem, ids in report.written.items():
            written.extend(f"{stem}:{i}" for i in ids)
        for stem, ids in report.skipped.items():
            skipped.extend(f"{stem}:{i}" for i in ids)
        notes.extend(report.notes)
    return written, skipped, degraded, notes


# ══════════════════════════ 六、命令行入口 ══════════════════════════


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="research_ingest.py", description="研究清单编译器")
    parser.add_argument("code_root", nargs="?", default=str(_ROOT))
    parser.add_argument("--manifest", default=None, help="指定清单文件（缺省编译投递口下全部）")
    parser.add_argument("--export", default=None, help="把当前真源的研究内容导出到该文件")
    parser.add_argument("--run-date", default=None, help="导出时用的运行日（默认今天）")
    parser.add_argument("--dry-run", action="store_true", help="只校验/派生，不写盘")
    args = parser.parse_args(argv)

    root = Path(args.code_root)
    if not root.is_dir():
        print(f"[INPUT-ERROR] code_root 不存在或不是目录：{root}", file=sys.stderr)
        return 2
    try:
        if args.export:
            manifest = export_manifest(
                root, run_date=args.run_date or date.today().isoformat()
            )
            Path(args.export).write_text(
                json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=False),
                encoding="utf-8",
            )
            counts = {k: len(v) for k, v in manifest["tables"].items()}
            print(f"[export] {args.export}：{sum(counts.values())} 行 / {len(counts)} 表")
            for stem, n in counts.items():
                print(f"  {stem}: {n}")
            return 0
        if args.manifest:
            report = ingest_research_file(root, args.manifest, dry_run=args.dry_run)
            print(f"[research_ingest] {Path(args.manifest).name}: {report.render()}")
            for note in report.notes:
                print(f"  note: {note}")
            return 0
        written, skipped, degraded, notes = ingest_research_inbox(root)
        for note in notes:
            print(f"  note: {note}")
        print(f"[research_ingest] 写入 {len(written)} 行 · 幂等跳过 {len(skipped)} 行 · degraded={degraded}")
        return 1 if degraded else 0
    except ResearchIngestError as exc:
        print(f"[INPUT-ERROR] research_ingest: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - 手工入口
    raise SystemExit(main())
