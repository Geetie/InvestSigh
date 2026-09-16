"""`moat_guard.py` —— **护城河反误判** + 六保护对象 + 四类来源区分 + **与价格的硬隔离**（`Ch4 §F`）。

## 设计锚点（逐字）

`Ch4 §F.2` 伪码：

```python
MOAT_EVIDENCE_KINDS = {"persistent_share","pricing_power","cost_advantage",
                       "switching_cost","scale_effect","network_effect"}

def is_durable_moat(moat, claims) -> bool:
    single_point = (moat.only_from({"product_leadership"})
                    or moat.only_from({"supply_scarcity"})
                    or moat.only_from({"high_gross_margin"}))
    if single_point:
        return False                                       # N4.3-06：单点证据不足以认定
    kinds = evidence_kinds(moat, claims) & MOAT_EVIDENCE_KINDS
    return (moat.mechanism_explained
            and len(kinds) >= 2                            # 需证据组合（≥2 类）
            and moat.cross_generation_survival is True
            and moat.origin_class != "supply_demand_cycle")  # 非周期性
```

`Ch4 §F.3` 的**三条硬隔离断言**（设计明写"可直接写单测"）：

| 断言 | 内容 |
|---|---|
| A1 | `MoatInput` dataclass **不含**任何 price/return 字段 |
| A2 | 拒绝 `moat.evidence_claims` 中引用价格快照的条目 → `MoatPriceContamination` |
| A3 | 写路径断言 `moat.writer ∈ {research_skill, human}`，**不含** `price_ingest` |

> 对齐 `C45-5`："股价上涨不自动证明护城河增强" —— 在 schema 层**物理隔离**，而非靠自觉。

## ★ `evidence_kinds()` 的实现来源（设计只给了函数名，未给数据出处）

伪码里 `moat.only_from({...})` 与 `evidence_kinds(moat, claims)` 都在设计里出现，
但**取证口径**未写。本实现取**三条可判定的来源**（并集），每条都有设计出处：

1. **证据主张自带的类别声明**（键名见 `CLAIM_KINDS_KEY`，**待需求方裁定**，见报告）——
   `Ch4 §A.2` 逐字说第四章读的是 `claims.claim_nature` / `claims.quality.*`；
   本实现读的类别声明是"该主张证明了哪种护城河机制"，属 `claims` 侧字段的**补充**。
2. **`real_substitutes[].switching_cost` 非空 ⇒ `switching_cost`** ——
   `N4.3-03/04` 逐字把 `switching_cost` + `switch_trigger` 列为真实替代方案的必要项。
3. **`to_be_confirmed` 之类的未知类别一律不进 `MOAT_EVIDENCE_KINDS`**（allowlist 式，
   `R-06 ⑤`）：只有列在 `MOAT_EVIDENCE_KINDS` 里的类别才计入"≥2 类"。

★ **判据全程不含关键词/名单式文本匹配**（`R-06 ①`）：`is_durable_moat` 的每条判据
  都是对**已结构化的取值**做的集合/比较运算，且 `evidence_kinds` 的类别是**封闭集合**
  （未列出的类别默认不计入），故不可通过"换一种措辞"绕过。
"""

from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from scripts._common import CheckReport, Violation, run_checker

#: `Ch4 §F.2` 代码块**逐字**给出的六类"能支撑持久护城河"的证据类别。
MOAT_EVIDENCE_KINDS: frozenset[str] = frozenset(
    {"persistent_share", "pricing_power", "cost_advantage", "switching_cost", "scale_effect", "network_effect"}
)

#: `Ch4 §F.2` 代码块**逐字**给出的三类"单点证据"标签（单独出现 ⇒ 不足以认定持久护城河）。
SINGLE_POINT_KINDS: tuple[str, ...] = ("product_leadership", "supply_scarcity", "high_gross_margin")

#: `claims` 侧承载"该主张证明了哪种护城河机制"的键名。
#: ★ **设计未给该键名**（伪码只写了 `evidence_kinds(moat, claims)`）⇒ 本值属**待裁定**项，
#:   已登记在报告「剩余不确定性与缺口」；不裁定则用它，裁定后改这一行即可。
CLAIM_KINDS_KEY = "moat_evidence_kinds"

#: `Ch4 §F.3` 断言 A3 的写路径白名单（**与 `schema.models.MoatWriter` 同源**，不另抄一份）。
def _writer_allowlist() -> frozenset[str]:
    from schema.models import MoatWriter

    return frozenset(m.value for m in MoatWriter)


class MoatPriceContamination(RuntimeError):
    """护城河条目引用了**价格**数据（`Ch4 §F.3` 断言 A2）。

    对齐 `C45-5`："股价上涨不自动证明护城河增强" —— 在 schema 层物理隔离。
    """

    def __init__(self, moat_id: str, offenders: Sequence[str]) -> None:
        self.moat_id = moat_id
        self.offenders = tuple(offenders)
        super().__init__(
            f"MoatPriceContamination: 护城河 {moat_id!r} 的证据引用了价格快照 "
            f"{list(self.offenders)} —— Ch4 §F.3/A2：护城河证据不得来自行情（写路径不含 price_ingest）"
        )


class MoatWriterNotAllowed(MoatPriceContamination):
    """`moat.writer` 不在白名单内（`Ch4 §F.3` 断言 A3）。"""

    def __init__(self, moat_id: str, writer: str) -> None:
        self.writer = writer
        RuntimeError.__init__(
            self,
            f"MoatWriterNotAllowed: 护城河 {moat_id!r} 的 writer={writer!r} 不在 "
            f"{sorted(_writer_allowlist())} 内 —— Ch4 §F.3/A3：`price_ingest` 等写路径不得写入 moat",
        )


@dataclass(frozen=True)
class MoatInput:
    """护城河判定所需的**全部**输入（`Ch4 §F.3` 断言 A1 的被检对象）。

    ★ A1 是**结构性**断言而非"约定"：本类的字段集里**没有**任何 price / return /
      snapshot / quote / past_performance 载体 ⇒ "股价变化影响护城河判定"在**类型层
      不可表达**。断言本身见 `assert_no_price_inputs()`。
    """

    moat_id: str
    mechanism: str
    origin_class: str | None
    cross_generation_survival: bool | None
    evidence_kinds: frozenset[str]
    writer: str = "research_skill"


#: `Ch4 §F.3` 断言 A1 逐字列出的**禁入字段名**。
FORBIDDEN_MOAT_INPUT_FIELDS: frozenset[str] = frozenset(
    {"price", "return", "snapshot", "quote", "past_performance"}
)


def assert_no_price_inputs() -> None:
    """`Ch4 §F.3` 断言 A1：`MoatInput` dataclass **不含**任何 price/return 字段。

    逐字对应设计的 `assert not any(k in MoatInput.__dataclass_fields__ for k in {...})`。
    `__dataclass_fields__` 与 `dataclasses.fields()` 同源（**不引入第二套字段解析**）。
    """
    present = {f.name for f in fields(MoatInput)} & FORBIDDEN_MOAT_INPUT_FIELDS
    if present:
        raise AssertionError(
            f"Ch4 §F.3/A1 被违反：MoatInput 含行情/收益字段 {sorted(present)} —— "
            "护城河判定与价格必须结构性隔离（C45-5）"
        )


def _field(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def mechanism_explained(moat: Any) -> bool:
    """`moat.mechanism` 是否**实质给出**（`Ch4 §F.1`：`mechanism` 必填；`N4.3-01` 验收）。

    ★ "实质给出"的判据 = 去空白后非空。**不**判长度/关键词 —— 那是主观质量，
      属 §G.2 明写"只能人工判断"的一侧，程序不越界。
    """
    return bool(str(_field(moat, "mechanism") or "").strip())


def evidence_kinds(moat: Any, claims: Iterable[Any] = ()) -> frozenset[str]:
    """护城河条目**实际**拿到的证据类别集合（来源见模块 docstring 的三条）。

    `claims` 为可迭代的主张对象/字典；只读其中 `CLAIM_KINDS_KEY` 声明的类别
    （缺失即视为未声明，**不猜**）。
    """
    kinds: set[str] = set()
    refs = {str(x) for x in (_field(moat, "evidence_claims") or [])}
    for claim in claims:
        cid = str(_field(claim, "claim_id") or "")
        if refs and cid not in refs:
            continue
        declared = _field(claim, CLAIM_KINDS_KEY)
        for kind in declared or []:
            kinds.add(str(kind))
    for sub in _field(moat, "real_substitutes") or []:
        cost = str(_field(sub, "switching_cost") or "").strip()
        # `tbd` 是"未披露"的占位（纪律：待定统一 tbd）⇒ 未披露的切换成本**不构成**类别证据。
        if cost and cost != "tbd":
            kinds.add("switching_cost")
    return frozenset(kinds)


def only_from(kinds: Iterable[str], allowed: Iterable[str]) -> bool:
    """伪码里 `moat.only_from(S)` 的语义：**证据非空且完全落在 `S` 内**。

    ★ "非空"这一半不可省（`G-03`）：空集 ⊆ 任何集合都成立，若允许空集，
      "**一点证据都没有**"的护城河会被判成"单点证据"，从而**歪打正着地**返回 False ——
      看起来结论对，但理由是错的。本实现让空证据走 `False`（同样不认定），
      并在返回值里保持可判定（不靠巧合）。
    """
    got = set(kinds)
    return bool(got) and got <= set(allowed)


def is_durable_moat(moat: Any, claims: Iterable[Any] = ()) -> bool:
    """`Ch4 §F.2` 伪码逐条落地（`N4.3-06`：单点证据不足以认定长期护城河）。

    四条判据缺一不可，其中三条是**硬否决**：

    1. 单点证据（仅 `product_leadership` / `supply_scarcity` / `high_gross_margin`）⇒ `False`；
    2. 机制说明实质给出（`§F.1` 必填）；
    3. 落在 `MOAT_EVIDENCE_KINDS` 内的类别 **≥ 2**（"需证据组合"）；
    4. `cross_generation_survival is True`（**`None`（`unknown`）不算 `True`** ——
       三值语义见 `Moat` 的 docstring）；
    5. `origin_class != "supply_demand_cycle"`（`§F.2` 表：紧缺时高毛利、供给恢复即消失）。
    """
    kinds = evidence_kinds(moat, claims)
    for label in SINGLE_POINT_KINDS:
        if only_from(kinds, {label}):
            return False
    effective = kinds & MOAT_EVIDENCE_KINDS
    origin = _field(moat, "origin_class")
    origin_value = getattr(origin, "value", origin)
    return bool(
        mechanism_explained(moat)
        and len(effective) >= 2
        and _field(moat, "cross_generation_survival") is True
        and str(origin_value) != "supply_demand_cycle"
    )


def moat_level_hint(moat: Any, claims: Iterable[Any] = ()) -> str:
    """护城河**水平**的判定提示（`Ch4 §H.4①`：`moat_level` 与 `moat_state` 分离）。

    ★ 本函数**不是**"水平字段的写入方"：`§H.1` 把 `moat_level` 定义在
      `value_state` 上（水平），而 `moat[]` 是条目集合。本函数只回答
      "**单条**护城河够不够格叫 strong"，供上层聚合；**不**输出任何加权或打分
      （`纪律 7` / `P-09`），只输出三档里的一个。
    """
    if is_durable_moat(moat, claims):
        return "strong"
    if len(evidence_kinds(moat, claims) & MOAT_EVIDENCE_KINDS) >= 1:
        return "moderate"
    return "weak"


# ───────────────────────────────── 硬隔离校验 ─────────────────────────────────

def validate_moat(moat: Any, *, price_snapshot_ids: Iterable[str] = ()) -> list[str]:
    """`Ch4 §F.3` 的 A2 / A3 落地。返回违例说明清单（空 = 通过）。

    - **A2**：`moat.evidence_claims` 中任一条落在**价格快照 id 集合**内 ⇒ 污染。
      判据是**集合成员判定**（不是"id 里含 price 字样"那种关键词式判据）——
      价格快照 id 的**唯一真源**是 `facts/prices.jsonl`，由调用方传入。
    - **A3**：`moat.writer` 必须在 `MoatWriter` 的白名单内（**allowlist：缺字段也拒**——
      `R-06 ⑤` "未列出的形式默认拒绝"；`§F.3` 的断言是
      `moat.writer ∈ {research_skill, human}`，而 `None` **不在**该集合内）。
    """
    moat_id = str(_field(moat, "moat_id") or "")
    out: list[str] = []
    price_ids = {str(x) for x in price_snapshot_ids}
    refs = [str(x) for x in (_field(moat, "evidence_claims") or [])]
    offenders = [r for r in refs if r in price_ids]
    if offenders:
        out.append(MoatPriceContamination(moat_id, offenders).args[0])
    writer = _field(moat, "writer")
    if str(writer or "") not in _writer_allowlist():
        out.append(
            f"{moat_id}: writer={writer!r} 不在 {sorted(_writer_allowlist())} 内 —— "
            "Ch4 §F.3/A3 的写路径白名单（`price_ingest` 不得写入 moat；缺字段同样不得放行，"
            "R-06 ⑤ allowlist 默认拒绝）"
        )
    if not mechanism_explained(moat):
        out.append(f"{moat_id}: 缺 mechanism 实质内容（Ch4 §F.1 必填 / N4.3-01）")
    origin = _field(moat, "origin_class")
    origin_value = getattr(origin, "value", origin)
    if origin_value is None or str(origin_value) == "":
        out.append(
            f"{moat_id}: 缺 origin_class（Ch4 §F.1/§F.2：四类来源区分是反误判的判据字段）"
        )
    return out


def check(root: Path) -> CheckReport:
    """对真源 `facts/baselines.jsonl` 的 `moat[]` 做 A2/A3 + 反误判检查（`Ch4 §F`）。

    - **缺失**真源 ⇒ `FileNotFoundError`（`exit 2`）；`baselines` 空 ⇒ `NO_BASELINES` note + `exit 0`；
    - **有 baseline 但 `moat[]` 全空** ⇒ 显式记 `NO_MOAT_ENTRIES` note + 计数（`G-03`）。
    """
    from schema.store import read_records, truth_source_status

    report = CheckReport(checker="valuelayer_moat_guard")
    status = truth_source_status(root, "baselines")
    if status == "missing":
        raise FileNotFoundError("缺少真源 facts/baselines.jsonl")
    baselines = read_records(root, "baselines")
    if not baselines:
        report.notes.append(
            "NO_BASELINES: facts/baselines.jsonl 存在但为空 —— 无被检对象（真空成立，非'已验证'，G-03）"
        )
        return report

    price_ids = {
        str(r.get("snapshot_id"))
        for r in read_records(root, "prices")
        if r.get("snapshot_id")
    }
    claims = read_records(root, "claims")
    report.scanned["baselines"] = len(baselines)
    report.scanned["price_snapshot_ids"] = len(price_ids)
    report.scanned["claims"] = len(claims)
    if not price_ids:
        # ★ `G-03`：A2 的判据是"是否落在**价格快照 id 集合**内"；集合为空时
        #   （`facts/prices.jsonl` 缺失或为空）这条检查**没有可核的对象** ——
        #   必须显式记出来，否则 `scanned` 里那个 0 会被读成"没有污染"。
        report.notes.append(
            "NO_PRICE_SNAPSHOTS: facts/prices.jsonl 缺失或为空 ⇒ A2（护城河证据不得引用行情）"
            "本次**不可核**（不可核 ≠ 已核，G-03）"
        )
    entries = 0
    durable = 0
    for row in baselines:
        for moat in row.get("moat") or []:
            entries += 1
            for detail in validate_moat(moat, price_snapshot_ids=price_ids):
                report.violations.append(
                    Violation("Ch4-F3", f"{row.get('baseline_id')}: {detail}", "facts/baselines.jsonl")
                )
            if is_durable_moat(moat, claims):
                durable += 1
    report.scanned["moat_entries"] = entries
    report.scanned["durable_moat_entries"] = durable
    if entries == 0:
        report.notes.append(
            f"NO_MOAT_ENTRIES: {len(baselines)} 条 baseline 的 moat[] 均为空 —— 无被检对象"
            "（真空成立，**不是**'护城河已验证'，G-03）"
        )
    return report


if __name__ == "__main__":
    import sys

    sys.exit(run_checker("valuelayer_moat_guard.py", check))
