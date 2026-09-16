"""`completeness.py` —— **形式完备性校验器**（`Ch4 §G.2` 逐字伪码 + `§G.3` gap 衔接 + `§G.4` 分支）。

## 设计锚点（逐字）

`Ch4 §G.2`：

| 可自动校验（形式完备性） | 只能人工判断（实质质量） |
|---|---|
| 六项 section 非空且达最小字段数 | 推理是否成立 |
| 必填字段非空率 ≥ 阈值 | 假设是否合理 |
| ≥1 原始材料定位（locator） | 机制解释是否有洞察 |
| ≥1 推导（公式 + 操作数） | 竞争分析深度 |
| 跨节引用一致（驱动出现在财务连接里） | 结论可信度 |

```python
# scripts/valuelayer/completeness.py
def form_complete(baseline, cfg) -> CheckResult:
    checks = [sections_nonempty(baseline, cfg),
              nonnull_rate(baseline) >= cfg.min_nonnull_rate,
              has_locator(baseline) >= 1,          # 含原始材料定位（N9.1-11）
              has_derivation(baseline) >= 1,       # 含推导（N9.2-02）
              cross_section_consistent(baseline)]
    return CheckResult(passed=all(checks), failed=[...])   # 形式上拦截空标题
```

> **最低标准**：程序做**形式完备性检查**（拦截空标题/无定位/无推导/跨节不一致）；
> **实质质量评审**只能人工（记 `tasks` 的 `human_review` 记录）。

## 本模块的三条纪律

1. **五项逐项可判定、可定位**：`CheckResult.outcomes` 里**每一项**都有自己的
   `check_id` / `status` / 违例清单 —— "哪一项不过"与"为什么不过"都在输出里，
   不存在"整体不过但说不清是哪一项"。
2. **阈值只从 `rules/baseline.yaml` 读**（`Ch4 §G.2` 的 `cfg` / `§J.4 J3` / `Ch11 §D.2` 单一真源）：
   本模块**不内置任何阈值**；缺键 ⇒ `_rules.MissingRuleInput`（CLI 折叠为 `exit 2`）。
3. **空 ≠ 已验证**（`G-03`）：没有可核对象的那一项记 `not_evaluated` + 显式 note + 计数，
   **不判通过**。

## ★ ⑥「价格与行动」的接缝（**设计本身的一处环**，本模块只如实暴露、不自裁）

`§G.1⑥` 逐字写"引用第五章三份判断 + 第七章建议（**不落本表**，`§A.1`）"，
而 `§G.2` 的 `sections_nonempty` 要"**六项** section 非空"。同时 `§A.1` 规定
第四章是**第五章的输入**（第五章消费第四章产出）⇒ "阶段② 要求六项齐备"会要求
第五章产物先存在，形成环。

本模块的处理：⑥ 的载体在 `facts/implied_requirements.jsonl`（Ch5）+
`facts/recommendations.jsonl`（Ch7），由 `FormContext.chapter_refs` 提供。
**没有 context 时记 `not_evaluated`**（显式 note + 计数），既不判通过、也不伪造违例。
已上报主理人裁定（`R-04`：有歧义 → 写清并上报，不自行裁决）。
"""

from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from scripts._common import CheckReport, Violation, run_checker
from scripts.valuelayer import _rules, state_machine

#: 五项检查的 id（**逐字**取 §G.2 伪码里的函数名/表达式名，便于按设计名检索）。
CHECK_IDS: tuple[str, ...] = (
    "sections_nonempty",
    "nonnull_rate",
    "has_locator",
    "has_derivation",
    "cross_section_consistent",
)

#: `Ch4 §G.2` / `§J.4 J3` 要求参数化在 `rules/baseline.yaml::thresholds` 的阈值键。
#:
#: ★ 键名以**已安装的规则文件为准**（`R8-1`：代码按本文件实有结构读）。13-R 安装后实测：
#:   `min_nonnull_rate` / `min_locator_count` / `min_derivation_count` / `min_fields_per_section`。
#:   初版曾把后两个写成 `min_locators` / `min_derivations`（当时设计只给语义、没有真文件可核），
#:   安装后**实测报"缺键"** ⇒ 判据恒红（`G-01`）⇒ 照实有键名改正。
CFG_MIN_NONNULL_RATE = "min_nonnull_rate"
CFG_MIN_FIELDS_PER_SECTION = "min_fields_per_section"
CFG_MIN_LOCATORS = "min_locator_count"
CFG_MIN_DERIVATIONS = "min_derivation_count"

#: 必须有**已拍板的值**才算"可判定"的三项（`min_fields_per_section` 不在内，见下）。
#:
#: ★ 为什么 `min_fields_per_section` 单列：13-R 转写时如实写了 `tbd`
#:   （设计 §G.2 表格只写"达最小字段数"、未给数值；`00_待拍板项清单.md B5` 也只定了
#:   非空率与定位数）。故该项的子语义被拆成**可核部分**（section 非空 ⇒ 照常强制）
#:   与**待拍板部分**（达最小字段数 ⇒ 记 `不可核` + 计数 + note，`G-03`）。
CFG_REQUIRED_DECIDED = (CFG_MIN_NONNULL_RATE, CFG_MIN_LOCATORS, CFG_MIN_DERIVATIONS)


STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_NOT_EVALUATED = "not_evaluated"


# ───────────────────────────── 结果类型（可定位） ─────────────────────────────


@dataclass(frozen=True)
class CheckViolation:
    """**单条**形式完备性违例（可定位到 section / 字段 / 引用 id）。"""

    check_id: str
    reason: str
    locator: str = ""

    def render(self) -> str:
        return f"[{self.check_id}] {self.reason}" + (f" @ {self.locator}" if self.locator else "")


@dataclass(frozen=True)
class CheckOutcome:
    """**五项中一项**的结果（`pass` / `fail` / `not_evaluated` 三态，穷尽互斥）。"""

    check_id: str
    status: str
    violations: tuple[CheckViolation, ...] = field(default_factory=tuple)
    scanned: Mapping[str, int] = field(default_factory=dict)
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return self.status == STATUS_PASS


@dataclass(frozen=True)
class CheckResult:
    """`form_complete()` 的返回值（`Ch4 §G.2` 的 `CheckResult(passed=..., failed=[...])`）。"""

    passed: bool
    outcomes: tuple[CheckOutcome, ...]
    failed: tuple[str, ...]
    not_evaluated: tuple[str, ...]
    gap: Mapping[str, Any] | None = None

    def violations(self) -> list[CheckViolation]:
        """把所有 `fail` 项（含 `not_evaluated` 的解释性违例）摊平成一个清单。"""
        out: list[CheckViolation] = []
        for outcome in self.outcomes:
            out.extend(outcome.violations)
        return out

    def summary(self) -> str:
        parts = []
        for outcome in self.outcomes:
            parts.append(f"{outcome.check_id}={outcome.status}")
        return "；".join(parts)


# ───────────────────────────── 上下文（跨表/跨章引用） ─────────────────────────────


@dataclass(frozen=True)
class FormContext:
    """形式完备性判定所需的**跨表 / 跨章**引用。

    ★ 为什么需要一个显式上下文对象（而不是让 `form_complete` 自己读盘）：
      `§G.1` 的六项里，③ 的载体在 `facts/drivers.jsonl`、⑤ 的推导在 `derived/`、
      ① 的 `relations` 在 `facts/relations.jsonl`、⑥ 在**第五/七章产物**里。
      若 `form_complete` 直接读盘，它就无法在**纯函数**语义下被单测，
      且"读的是哪一份真源"会变得不可见。故由调用方（`form_context_from(root)`）装好再传。
    """

    drivers: Mapping[str, Any] = field(default_factory=dict)
    businesses: Mapping[str, Any] = field(default_factory=dict)
    claims: Mapping[str, Any] = field(default_factory=dict)
    derived: Mapping[str, Any] = field(default_factory=dict)
    relations: tuple[Any, ...] = ()
    #: ⑥ 的跨章引用：键 = `company_id`，值 = 该公司的第五/七章产物引用（非空即"有引用"）。
    chapter_refs: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


def _field(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def _is_blank(value: Any) -> bool:
    """值是否"实质为空"（`tbd` / `None` / 空串 / 空列表 / 空 mapping）。

    ★ `tbd` 计为**空**：`纪律 7` 把 `tbd` 定为"待定"的统一 token，
      它表示"尚未确定"——把 `tbd` 当非空会让"六个空标题"顺利通过形式校验，
      正是 `§G.2` 要拦的形态。
    """
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip() or value.strip().lower() == "tbd"
    if isinstance(value, Mapping):
        return not value
    if isinstance(value, (list, tuple, set)):
        return not list(value)
    return False


# ───────────────────────────── 六项 section 的规格（`Ch4 §G.1`） ─────────────────────────────
#
# ★ 字段名**逐个**取自 `§G.1` 的"字段"列（逐字），不自造：
#   ① `business_refs[]` + `relations`（N9.1-06）
#   ② `driver_refs[]`
#   ③ `drivers[].realization_stage/timeline/confidence` + `dependencies[]`
#   ④ `moat[]`
#   ⑤ `valuation_inputs` + `historicals`（= `historical_numeric_claims`，§G.1⑤ 的行文）
#      + `DerivedValue` 引用（落位 = `valuation.formula_ref`）
#   ⑥ 引用第五章三份判断 + 第七章建议（**不落本表**）


@dataclass(frozen=True)
class SectionSpec:
    """一个 section 的规格：它的字段名 + 该字段"非空"如何判定（可判定谓词）。"""

    section_id: str
    title: str
    fields: tuple[str, ...]


def _present_business_refs(baseline: Any, ctx: FormContext) -> bool:
    return not _is_blank(_field(baseline, "business_refs"))


def _present_relations(baseline: Any, ctx: FormContext) -> bool:
    company_id = str(_field(baseline, "company_id") or "")
    return any(
        company_id
        and company_id in {str(_field(r, "subject_id") or ""), str(_field(r, "object_id") or "")}
        for r in ctx.relations
    )


def _present_driver_refs(baseline: Any, ctx: FormContext) -> bool:
    return not _is_blank(_field(baseline, "driver_refs"))


def _referenced_drivers(baseline: Any, ctx: FormContext) -> list[Any]:
    return [ctx.drivers[str(ref)] for ref in (_field(baseline, "driver_refs") or []) if str(ref) in ctx.drivers]


def _present_realization_stage(baseline: Any, ctx: FormContext) -> bool:
    rows = _referenced_drivers(baseline, ctx)
    return bool(rows) and all(not _is_blank(_field(r, "realization_stage")) for r in rows)


def _present_timeline(baseline: Any, ctx: FormContext) -> bool:
    rows = _referenced_drivers(baseline, ctx)
    return bool(rows) and all(not _is_blank(_field(r, "timeline")) for r in rows)


def _present_confidence(baseline: Any, ctx: FormContext) -> bool:
    rows = _referenced_drivers(baseline, ctx)
    return bool(rows) and all(not _is_blank(_field(r, "confidence")) for r in rows)


def _present_dependencies(baseline: Any, ctx: FormContext) -> bool:
    rows = _referenced_drivers(baseline, ctx)
    return bool(rows) and all(not _is_blank(_field(r, "dependencies")) for r in rows)


def _present_moat(baseline: Any, ctx: FormContext) -> bool:
    return not _is_blank(_field(baseline, "moat"))


def _present_valuation_inputs(baseline: Any, ctx: FormContext) -> bool:
    inputs = _field(baseline, "valuation_inputs")
    if inputs is None:
        return False
    # `§G.1⑤` 的 `valuation_inputs` 是"五因素→每股价值"的入口（`Ch5 §B.4`）；
    # 任一因素已给即视为该字段非空（**不要求五项齐备** —— 齐备度由非空率承担）。
    return any(not _is_blank(_field(inputs, name)) for name in _VALUATION_FACTORS)


_VALUATION_FACTORS: tuple[str, ...] = (
    "growth_assumption",
    "margin_assumption",
    "reinvestment_assumption",
    "risk_assumption",
    "duration_assumption",
)


def _present_historicals(baseline: Any, ctx: FormContext) -> bool:
    return not _is_blank(_field(baseline, "historical_numeric_claims"))


def _present_valuation_ref(baseline: Any, ctx: FormContext) -> bool:
    valuation = _field(baseline, "valuation")
    return not _is_blank(_field(valuation, "formula_ref")) if valuation is not None else False


def _present_chapter5_judgements(baseline: Any, ctx: FormContext) -> bool:
    company_id = str(_field(baseline, "company_id") or "")
    refs = ctx.chapter_refs.get(company_id) or ()
    return any(str(r).startswith("ch5:") for r in refs)


def _present_chapter7_recommendation(baseline: Any, ctx: FormContext) -> bool:
    company_id = str(_field(baseline, "company_id") or "")
    refs = ctx.chapter_refs.get(company_id) or ()
    return any(str(r).startswith("ch7:") for r in refs)


#: `section_id → (field_name → 非空谓词)`。谓词全部只读**已结构化**的取值（`R-06 ①`）。
SECTION_FIELD_PREDICATES: Mapping[str, Mapping[str, Callable[[Any, FormContext], bool]]] = {
    "business_and_industry_position": {
        "business_refs": _present_business_refs,
        "relations": _present_relations,
    },
    "growth_drivers": {"driver_refs": _present_driver_refs},
    "growth_certainty": {
        "drivers_realization_stage": _present_realization_stage,
        "drivers_timeline": _present_timeline,
        "drivers_confidence": _present_confidence,
        "drivers_dependencies": _present_dependencies,
    },
    "moat": {"moat": _present_moat},
    "financial_and_valuation": {
        "valuation_inputs": _present_valuation_inputs,
        "historical_numeric_claims": _present_historicals,
        "valuation_formula_ref": _present_valuation_ref,
    },
    "price_and_action": {
        "chapter5_judgements": _present_chapter5_judgements,
        "chapter7_recommendation": _present_chapter7_recommendation,
    },
}

#: 六项 section（`Ch4 §G.1` 的 ①~⑥，顺序与设计表一致）。
SECTIONS: tuple[SectionSpec, ...] = (
    SectionSpec(
        "business_and_industry_position", "①业务与产业位置",
        tuple(SECTION_FIELD_PREDICATES["business_and_industry_position"]),
    ),
    SectionSpec("growth_drivers", "②增长驱动", tuple(SECTION_FIELD_PREDICATES["growth_drivers"])),
    SectionSpec("growth_certainty", "③增长确定性", tuple(SECTION_FIELD_PREDICATES["growth_certainty"])),
    SectionSpec("moat", "④护城河", tuple(SECTION_FIELD_PREDICATES["moat"])),
    SectionSpec(
        "financial_and_valuation", "⑤财务与估值",
        tuple(SECTION_FIELD_PREDICATES["financial_and_valuation"]),
    ),
    SectionSpec("price_and_action", "⑥价格与行动", tuple(SECTION_FIELD_PREDICATES["price_and_action"])),
)


# ───────────────────────────── §G.4 未盈利 / 盈利分支 ─────────────────────────────

#: `Ch4 §G.4` 表逐字：未盈利公司（`is_profitable=False`）的必填增量。
UNPROFITABLE_REQUIRED: tuple[str, ...] = (
    "business_model_note",
    "path_to_profitability",
    "cash_runway",
    "funding_need",
    "unit_economics",
)

#: `Ch4 §G.4` 表逐字：盈利公司（`is_profitable=True`）的必填增量。
PROFITABLE_REQUIRED: tuple[str, ...] = (
    "margin_persistence",
    "fcf_persistence",
    "reinvestment_return",
    "share_dilution_impact",
)


def profitability_required_gaps(baseline: Any) -> tuple[str, tuple[str, ...]]:
    """`Ch4 §G.4` 分支校验：返回 `(status, 缺失字段)`。

    `status ∈ {profitable, unprofitable, undetermined}`：
    - `is_profitable is True` / `False` ⇒ 按对应分支核必填（`N4.2-04/05`）；
    - `is_profitable is None`（= 未判定，**不猜**）⇒ `undetermined` + 空 tuple，
      由调用方记 `not_evaluated`（`G-03`）。
    """
    flag = _field(baseline, "is_profitable")
    if flag is None:
        return "undetermined", ()
    required = PROFITABLE_REQUIRED if flag is True else UNPROFITABLE_REQUIRED
    missing = tuple(name for name in required if _is_blank(_field(baseline, name)))
    return ("profitable" if flag is True else "unprofitable"), missing


#: `§G.2` "必填字段非空率" 的**被除集合**。
#: ★ 口径（本实现选定，已登记待裁定）：取 `§G.1` 六项深度所对应的**baseline 本表字段**
#:   （`business_refs` / `driver_refs` / `moat` / `valuation_inputs` /
#:   `historical_numeric_claims` / `valuation`）+ `§G.4` 分支必填字段。
#:   **不**把 `baseline_id` / `company_id` 这类恒非空的标识字段算进去 ——
#:   把它们计入会把非空率**人为抬高**，使这个指标失去分辨力。
REQUIRED_BASELINE_FIELDS: tuple[str, ...] = (
    "business_mechanism",
    "business_refs",
    "driver_refs",
    "moat",
    "valuation_inputs",
    "historical_numeric_claims",
    "valuation",
)


def required_field_names(baseline: Any) -> tuple[str, ...]:
    """本次的必填字段集合（含 `§G.4` 分支项；`undetermined` 时不含分支项）。"""
    status, _ = profitability_required_gaps(baseline)
    branch: tuple[str, ...] = ()
    if status == "profitable":
        branch = PROFITABLE_REQUIRED
    elif status == "unprofitable":
        branch = UNPROFITABLE_REQUIRED
    return REQUIRED_BASELINE_FIELDS + branch


def nonnull_rate(baseline: Any) -> float:
    """必填字段非空率（`Ch4 §G.2`）。分母 = `required_field_names(baseline)` 的条数。"""
    names = required_field_names(baseline)
    if not names:
        return 0.0
    filled = sum(1 for name in names if not _is_blank(_field(baseline, name)))
    return filled / len(names)


# ───────────────────────────── 五项检查 ─────────────────────────────


def sections_nonempty(baseline: Any, cfg: Mapping[str, Any], ctx: FormContext) -> CheckOutcome:
    """`§G.2` 项①：「六项 section 非空且达最小字段数」。

    阈值 = `cfg["min_fields_per_section"]`（`rules/baseline.yaml::thresholds`）。

    ★ 该项是**唯一**一个被拆成两半的检查（`G-03` 的必然结果，不是折中）：
      - **「非空」** —— 可核，**无阈值**，照常强制（阈值缺省也拦得住"空标题"）；
      - **「达最小字段数」** —— 需阈值 `min_fields_per_section`，而 13-R 转写真文件时
        如实写了 `tbd`（设计 §G.2 表格只写"达最小字段数"、未给数值；`B5` 只定了
        非空率与定位数）⇒ 该半项**不可核** ⇒ 记 `notes` + `scanned` 计数，
        **既不放行也不恒红**（`G-01`：恒红的门禁一定会被关掉）。

    ★ 逐 section 报出"哪些字段为空"，**可定位**到 section（`locator = section_id`）。
    """
    minimum = _rules.threshold_or_none(cfg, CFG_MIN_FIELDS_PER_SECTION)
    effective = 1 if minimum is None else int(minimum)
    violations: list[CheckViolation] = []
    scanned: dict[str, int] = {}
    for spec in SECTIONS:
        predicates = SECTION_FIELD_PREDICATES[spec.section_id]
        present = tuple(name for name in spec.fields if predicates[name](baseline, ctx))
        scanned[spec.section_id] = len(present)
        if len(present) < effective:
            absent = tuple(name for name in spec.fields if name not in present)
            if minimum is None:
                reason = f"{spec.title} 为空（0 个字段非空，§G.2 项①'六项 section 非空'）；空字段 {list(absent)}"
            else:
                reason = (
                    f"{spec.title} 仅 {len(present)} 个字段非空 < 最小字段数 {effective}；"
                    f"空字段 {list(absent)}"
                )
            violations.append(CheckViolation("sections_nonempty", reason, spec.section_id))
    notes: tuple[str, ...] = ()
    if minimum is None:
        # ★ 计数不写 0：写"几个 section 的'最小字段数'半项不可核"——本次是全部 6 个，
        #   故取 `len(SECTIONS)`，与"没有任何不可核项"的 0 明确区分开（G-03 的"显式 + 计数"）。
        #   ★ **不放进本 outcome 的 `scanned`**：那个映射的契约是"**逐 section** 的字段计数"
        #     （`test_sections_nonempty_reports_six_sections_in_scanned` 钉住了这条）。
        #     把"非对象计数"混进去会让"六项是否都有定位"这件事被稀释。
        #     机器可读的计数落在 CLI 的 `report.scanned["min_fields_undecided_sections"]`（见 `check()`）。
        notes = (
            f"MIN_FIELDS_UNDECIDED: `{_rules.BASELINE_RELPATH}::{_rules.THRESHOLDS_GROUP}"
            f".{CFG_MIN_FIELDS_PER_SECTION}` 为 `tbd`（设计未给数值，13-R 如实转写）⇒ "
            f"§G.2 项①的『达最小字段数』半项**不可核**（本次 {len(SECTIONS)} 个 section），"
            "已按下界 1（=『非空』）强制；不可核 ≠ 已核（G-03）",
        )
    return CheckOutcome(
        check_id="sections_nonempty",
        status=STATUS_FAIL if violations else STATUS_PASS,
        violations=tuple(violations),
        scanned=scanned,
        notes=notes,
    )



def nonnull_rate_outcome(baseline: Any, cfg: Mapping[str, Any]) -> CheckOutcome:
    """`§G.2` 项②：「必填字段非空率 ≥ 阈值」（阈值 = `cfg.min_nonnull_rate`）。"""
    minimum = float(_rules.baseline_threshold_from(cfg, CFG_MIN_NONNULL_RATE))
    rate = nonnull_rate(baseline)
    names = required_field_names(baseline)
    blank = [name for name in names if _is_blank(_field(baseline, name))]
    violations: list[CheckViolation] = []
    if rate < minimum:
        violations.append(
            CheckViolation(
                "nonnull_rate",
                f"必填字段非空率 {rate:.4f} < 阈值 {minimum}（空字段 {blank}）",
                str(_field(baseline, "baseline_id") or ""),
            )
        )
    return CheckOutcome(
        check_id="nonnull_rate",
        status=STATUS_FAIL if violations else STATUS_PASS,
        violations=tuple(violations),
        scanned={"required_fields": len(names), "blank_fields": len(blank)},
    )


def locator_refs(baseline: Any) -> tuple[str, ...]:
    """baseline 上的**原始材料定位**载体（`§G.2` 项③ / `N9.1-11`）。

    取 `evidence_claim_ids`（baseline 层证据）∪ `moat[].evidence_claims`（护城河条目证据）
    引用到的 claim id，去重升序。
    """
    refs: set[str] = {str(x) for x in (_field(baseline, "evidence_claim_ids") or [])}
    for moat in _field(baseline, "moat") or []:
        refs |= {str(x) for x in (_field(moat, "evidence_claims") or [])}
    return tuple(sorted(refs))


def has_locator(baseline: Any, ctx: FormContext) -> tuple[int, tuple[str, ...]]:
    """返回 `(定位条数, 缺定位的引用 id)`。

    ★ "有定位"的判据 = 被引用的 claim 存在且其 `locator` 实质非空（`tbd` 不算）。
      引用**指向不存在的 claim** 时，既不凭空算作"有定位"，也不静默跳过 ——
      它进 `missing`（可定位）。若**根本没提供** claims 上下文（`ctx_supplied=False`）
      ⇒ 交由调用方判 `not_evaluated`（`G-03`）；若提供了但集合里没有 ⇒ 悬空引用（可判定）。
    """
    refs = locator_refs(baseline)
    if not refs:
        return 0, ()
    located = 0
    missing: list[str] = []
    for ref in refs:
        claim = ctx.claims.get(ref)
        if claim is None or _is_blank(_field(claim, "locator")):
            missing.append(ref)
        else:
            located += 1
    return located, tuple(missing)


def has_locator_outcome(
    baseline: Any, cfg: Mapping[str, Any], ctx: FormContext, *, ctx_supplied: bool = True
) -> CheckOutcome:
    """`§G.2` 项③：「≥1 原始材料定位（locator）」（条数阈值 = `cfg.min_locators`）。

    ## `ctx_supplied`：`G-03` 在"上下文式设计"里的**唯一**可判定分界

    `ctx.claims` 为空有**两种**完全不同的成因，必须分开（否则会开一个洞）：

    | 成因 | 我们知道什么 | 判定 |
    |---|---|---|
    | **没提供** claims 上下文（`ctx_supplied=False`）| 不知道 claim 集合长什么样 | `not_evaluated`（不可核 ≠ 已核） |
    | **提供了**，但集合里**没有**被引用的 claim | 已知的 claim 集合**确定**不含它 ⇒ 悬空引用 | `fail`（可判定，且点出该 id） |

    ★ 若把两者都判 `not_evaluated`，则在"真源里根本没有 claims"的仓库上，
      baseline 里**任意编造的 claim id 都不会被拦** —— 那正是 `§G.2` 项③要防的东西。
      而 `check()` / `g_depth_violations()` 两条生产路径都经 `form_context_from()`，
      故 `ctx_supplied` 恒为 `True` ⇒ 该洞在生产路径上已被关闭。
    """
    minimum = int(_rules.baseline_threshold_from(cfg, CFG_MIN_LOCATORS))
    refs = locator_refs(baseline)
    if not refs:
        return CheckOutcome(
            check_id="has_locator",
            status=STATUS_NOT_EVALUATED,
            violations=(
                CheckViolation(
                    "has_locator",
                    "baseline 未引用任何证据（evidence_claim_ids 与 moat[].evidence_claims 均为空）⇒ "
                    "无被检对象，不得判'已定位'（G-03）",
                    str(_field(baseline, "baseline_id") or ""),
                ),
            ),
            scanned={"locator_refs": 0},
            notes=("NO_LOCATOR_REFS: 无被检对象（真空成立，非'已验证'）",),
        )
    located, missing = has_locator(baseline, ctx)
    violations: list[CheckViolation] = []
    if not ctx_supplied:
        return CheckOutcome(
            check_id="has_locator",
            status=STATUS_NOT_EVALUATED,
            violations=(
                CheckViolation(
                    "has_locator",
                    f"引用了 {len(refs)} 条证据，但本次未提供 claims 上下文 ⇒ 定位无法核"
                    "（**不是**'已定位'，G-03）",
                    str(_field(baseline, "baseline_id") or ""),
                ),
            ),
            scanned={"locator_refs": len(refs)},
            notes=("NO_CLAIMS_CONTEXT: 缺少 claims 上下文，定位不可核",),
        )
    if located < minimum:
        violations.append(
            CheckViolation(
                "has_locator",
                f"合格定位 {located} 条 < 阈值 {minimum}（无定位的引用：{list(missing)}）",
                str(_field(baseline, "baseline_id") or ""),
            )
        )
    return CheckOutcome(
        check_id="has_locator",
        status=STATUS_FAIL if violations else STATUS_PASS,
        violations=tuple(violations),
        scanned={"locator_refs": len(refs), "located": located, "missing_locator": len(missing)},
    )


def formula_refs(baseline: Any, ctx: FormContext) -> tuple[str, ...]:
    """baseline 上的**推导**载体（`§G.2` 项④ / `N9.2-02`）。

    两个来源（都是设计逐字给的落位）：
    - `§G.1⑤` 的 `DerivedValue` 引用 → `valuation.formula_ref`；
    - `§C.4` 的三层映射 `formula_ref: <DerivedValue ref>` → `driver.financial_link.formula_ref`。
    """
    refs: set[str] = set()
    valuation = _field(baseline, "valuation")
    if valuation is not None:
        ref = _field(valuation, "formula_ref")
        if not _is_blank(ref):
            refs.add(str(ref))
    for driver in _referenced_drivers(baseline, ctx):
        link = _field(driver, "financial_link")
        ref = _field(link, "formula_ref") if link is not None else None
        if not _is_blank(ref):
            refs.add(str(ref))
    return tuple(sorted(refs))


def has_derivation(baseline: Any, ctx: FormContext) -> tuple[int, tuple[str, ...]]:
    """返回 `(合格推导条数, 不合格的 formula_ref)`。

    ★ "含推导（**公式 + 操作数**）"的判据逐字取 §G.2 括号里的两个要件：
      `derived` 行必须**同时**有非空 `formula` 与非空 `operands`。
      只有公式没有操作数 ⇒ 不可复查，**不算**推导。
    """
    refs = formula_refs(baseline, ctx)
    ok = 0
    bad: list[str] = []
    for ref in refs:
        row = ctx.derived.get(ref)
        if row is None or _is_blank(_field(row, "formula")) or _is_blank(_field(row, "operands")):
            bad.append(ref)
        else:
            ok += 1
    return ok, tuple(bad)


def has_derivation_outcome(
    baseline: Any, cfg: Mapping[str, Any], ctx: FormContext, *, ctx_supplied: bool = True
) -> CheckOutcome:
    """`§G.2` 项④：「≥1 推导（公式 + 操作数）」（条数阈值 = `cfg.min_derivations`）。

    `ctx_supplied` 的语义与项③同源：**没给** `derived/` 上下文 ⇒ `not_evaluated`；
    **给了但集合里没有**该 `formula_ref` ⇒ 悬空引用 ⇒ `fail`（可判定，见 `has_locator_outcome`）。
    """
    minimum = int(_rules.baseline_threshold_from(cfg, CFG_MIN_DERIVATIONS))
    refs = formula_refs(baseline, ctx)
    if not refs:
        return CheckOutcome(
            check_id="has_derivation",
            status=STATUS_NOT_EVALUATED,
            violations=(
                CheckViolation(
                    "has_derivation",
                    "baseline 未引用任何 DerivedValue（valuation.formula_ref 与 "
                    "driver.financial_link.formula_ref 均为空）⇒ 无被检对象，不得判'有推导'（G-03）",
                    str(_field(baseline, "baseline_id") or ""),
                ),
            ),
            scanned={"formula_refs": 0},
            notes=("NO_FORMULA_REFS: 无被检对象（真空成立，非'已验证'）",),
        )
    ok, bad = has_derivation(baseline, ctx)
    violations: list[CheckViolation] = []
    if not ctx_supplied:
        return CheckOutcome(
            check_id="has_derivation",
            status=STATUS_NOT_EVALUATED,
            violations=(
                CheckViolation(
                    "has_derivation",
                    f"引用了 {len(refs)} 条 formula_ref，但本次未提供 derived/ 上下文 ⇒ 推导无法核"
                    "（**不是**'有推导'，G-03）",
                    str(_field(baseline, "baseline_id") or ""),
                ),
            ),
            scanned={"formula_refs": len(refs)},
            notes=("NO_DERIVED_CONTEXT: 缺少 derived/ 上下文，推导不可核",),
        )
    if ok < minimum:
        violations.append(
            CheckViolation(
                "has_derivation",
                f"合格推导 {ok} 条 < 阈值 {minimum}（不满足'公式 + 操作数'的引用：{list(bad)}）",
                str(_field(baseline, "baseline_id") or ""),
            )
        )
    return CheckOutcome(
        check_id="has_derivation",
        status=STATUS_FAIL if violations else STATUS_PASS,
        violations=tuple(violations),
        scanned={"formula_refs": len(refs), "ok": ok, "incomplete": len(bad)},
    )


def cross_section_consistent(baseline: Any, ctx: FormContext, *, ctx_supplied: bool = True) -> CheckOutcome:
    """`§G.2` 项⑤：「跨节引用一致（**驱动出现在财务连接里**）」（`§C.4` 末句）。

    三条子判据，逐条可定位：

    | # | 判据 | 设计出处 |
    |---|---|---|
    | 1 | 每个 `driver_refs[]` 必须在 `facts/drivers.jsonl` 里**真实存在** | `§G.1②`（引用而非内嵌）+ `G-06` |
    | 2 | 每个被引用的驱动必须有 `financial_link.accounts` 非空 —— **"驱动出现在财务连接里"** | `§C.4` 末句逐字 |
    | 3 | 每个 `business_refs[]` 必须在 `facts/businesses.jsonl` 里**真实存在** | `§G.1①` + `§B.1` |

    ★ `driver_refs` 为空时本项**不是**"通过"，而是"无被检对象"：
      引用不存在就谈不上"跨节一致"。由 `sections_nonempty` 的 ② 负责把它判失败，
      本项**如实记 `not_evaluated`**（`G-03`）。
    """
    driver_refs = [str(x) for x in (_field(baseline, "driver_refs") or [])]
    business_refs = [str(x) for x in (_field(baseline, "business_refs") or [])]
    baseline_id = str(_field(baseline, "baseline_id") or "")

    if not driver_refs and not business_refs:
        return CheckOutcome(
            check_id="cross_section_consistent",
            status=STATUS_NOT_EVALUATED,
            violations=(
                CheckViolation(
                    "cross_section_consistent",
                    "baseline 未引用任何 driver / business ⇒ 无跨节引用可核，"
                    "不得判'一致'（G-03）",
                    baseline_id,
                ),
            ),
            scanned={"driver_refs": 0, "business_refs": 0},
            notes=("NO_CROSS_REFS: 无被检对象（真空成立，非'已验证'）",),
        )

    violations: list[CheckViolation] = []
    missing_drivers = [ref for ref in driver_refs if ref not in ctx.drivers]
    if driver_refs and not ctx.drivers and not ctx_supplied:
        return CheckOutcome(
            check_id="cross_section_consistent",
            status=STATUS_NOT_EVALUATED,
            violations=(
                CheckViolation(
                    "cross_section_consistent",
                    f"引用了 {len(driver_refs)} 个 driver，但本次未提供 drivers 上下文 ⇒ 跨节一致性不可核"
                    "（**不是**'一致'，G-03）",
                    baseline_id,
                ),
            ),
            scanned={"driver_refs": len(driver_refs), "business_refs": len(business_refs)},
            notes=("NO_DRIVERS_CONTEXT: 缺少 drivers 上下文，跨节一致性不可核",),
        )
    if missing_drivers:
        violations.append(
            CheckViolation(
                "cross_section_consistent",
                f"driver_refs 指向不存在的驱动 {missing_drivers}（§G.1② 是引用，不是内嵌）",
                baseline_id,
            )
        )
    for ref in driver_refs:
        driver = ctx.drivers.get(ref)
        if driver is None:
            continue
        link = _field(driver, "financial_link")
        accounts = _field(link, "accounts") if link is not None else None
        if _is_blank(accounts):
            violations.append(
                CheckViolation(
                    "cross_section_consistent",
                    f"驱动 {ref} 未出现在财务连接里（financial_link.accounts 为空）—— "
                    "§C.4 末句逐字要求'驱动必须出现在财务连接里'",
                    ref,
                )
            )
    missing_businesses = [ref for ref in business_refs if ref not in ctx.businesses]
    if business_refs and not ctx.businesses and not ctx_supplied:
        return CheckOutcome(
            check_id="cross_section_consistent",
            status=STATUS_NOT_EVALUATED,
            violations=(
                CheckViolation(
                    "cross_section_consistent",
                    f"引用了 {len(business_refs)} 个 business，但本次未提供 businesses 上下文 ⇒ 引用不可核"
                    "（**不是**'一致'，G-03）",
                    baseline_id,
                ),
            ),
            scanned={"driver_refs": len(driver_refs), "business_refs": len(business_refs)},
            notes=("NO_BUSINESSES_CONTEXT: 缺少 businesses 上下文，引用不可核",),
        )
    if missing_businesses:
        violations.append(
            CheckViolation(
                "cross_section_consistent",
                f"business_refs 指向不存在的业务 {missing_businesses}（§G.1① 是引用）",
                baseline_id,
            )
        )
    return CheckOutcome(
        check_id="cross_section_consistent",
        status=STATUS_FAIL if violations else STATUS_PASS,
        violations=tuple(violations),
        scanned={
            "driver_refs": len(driver_refs),
            "business_refs": len(business_refs),
            "missing_drivers": len(missing_drivers),
            "missing_businesses": len(missing_businesses),
        },
    )


# ───────────────────────────── §G.3 gap 衔接 ─────────────────────────────

#: `Ch9 §G.3`（= `N9.1-21`）gap 对象的**六个键**（逐字）：
#: `{gap_type, scope, blocking_step, required_input, status, created_at}`
GAP_KEYS: tuple[str, ...] = (
    "gap_type",
    "scope",
    "blocking_step",
    "required_input",
    "status",
    "created_at",
)

#: 形式完备性不过时的缺口类型（`§G.3`："驱动展示'未完成 / 不足以完成 X'"）。
GAP_TYPE_INCOMPLETE_SECTIONS = "baseline_incomplete"
GAP_SCOPE_COMPANY = "company"


def to_gap(result: CheckResult, baseline: Any, *, created_at: str = "") -> dict[str, Any] | None:
    """`Ch4 §G.3` gap 衔接：完备性不过 ⇒ 产出**第九章 gap 对象形状**的 dict；通过 ⇒ `None`。

    ★ 为什么返回 dict 而不是自定义类（`G-06` 唯一真源）：`§G.3` 逐字写"**复用**第九章
      `gap` 对象（**不新建**）"，而第九章的 `gap` **在当前代码区尚无载体**
      （`scripts/tasks/gap_to_task.py` 的 docstring 引用了它的键，但没有构造入口）。
      故此处只按**设计逐字给出的六键**产出可序列化 dict，**不新造一个 gap 类** ——
      待第九章落地唯一真源后，本函数应改为调用它（已登记为待收口项）。
    """
    if result.passed:
        return None
    failed = list(result.failed)
    return {
        "gap_type": GAP_TYPE_INCOMPLETE_SECTIONS,
        "scope": GAP_SCOPE_COMPANY,
        "blocking_step": "stage:nvidia_sample" if "nvidia_sample" else "ch4_form_completeness",
        "required_input": failed,
        "status": "open",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
    }


# ───────────────────────────── form_complete（§G.2 主入口） ─────────────────────────────


def form_complete(
    baseline: Any,
    cfg: Mapping[str, Any],
    *,
    context: FormContext | None = None,
    check_g4_branch: bool = True,
) -> CheckResult:
    """`Ch4 §G.2` 的伪码逐条落地。**五项逐项可判定、可定位**。

    - `passed` = 五项**全部** `pass`；
    - `failed` = 状态为 `fail` 的 check_id（有序、去重）；
    - `not_evaluated` = 状态为 `not_evaluated` 的 check_id（`G-03`：不计为通过）；
    - `gap` = 未通过时的 `§G.3` 缺口对象（六键）。

    ★ 为什么把 `not_evaluated` 与 `fail` **分开报**：两者都让 `passed=False`，
      但"不达标"与"没法判"是**两件事**（`G-03` 的核心）。混在一起会让
      "配置/上下文没给全"看起来像"数据不合格"，从而修错地方。

    ★ `context=None`（**未提供**上下文）与 `context=FormContext()`（提供了但为空）
      是**两件事**：前者"引用不可核" ⇒ `not_evaluated`；后者"引用悬空" ⇒ `fail`。
      见 `has_locator_outcome` 的取值表。两条生产路径（`check()` / `g_depth_violations()`）
      都传 `form_context_from(root)` ⇒ 恒为"已提供"。
    """
    ctx = context or FormContext()
    ctx_supplied = context is not None
    outcomes: list[CheckOutcome] = [
        sections_nonempty(baseline, cfg, ctx),
        nonnull_rate_outcome(baseline, cfg),
        has_locator_outcome(baseline, cfg, ctx, ctx_supplied=ctx_supplied),
        has_derivation_outcome(baseline, cfg, ctx, ctx_supplied=ctx_supplied),
        cross_section_consistent(baseline, ctx, ctx_supplied=ctx_supplied),
    ]
    if check_g4_branch:
        outcomes.append(g4_branch_outcome(baseline))

    failed = tuple(o.check_id for o in outcomes if o.status == STATUS_FAIL)
    not_evaluated = tuple(o.check_id for o in outcomes if o.status == STATUS_NOT_EVALUATED)
    passed = not failed and not not_evaluated
    result = CheckResult(
        passed=passed,
        outcomes=tuple(outcomes),
        failed=failed,
        not_evaluated=not_evaluated,
    )
    return CheckResult(
        passed=passed,
        outcomes=result.outcomes,
        failed=result.failed,
        not_evaluated=result.not_evaluated,
        gap=to_gap(result, baseline),
    )


def g4_branch_outcome(baseline: Any) -> CheckOutcome:
    """`Ch4 §G.4` 未盈利 / 盈利分支必填（`N4.2-04/05`）。

    ★ 它不是 `§G.2` 伪码五项之一，而是同一张表里 `§G.4` 的**独立要求**；
      本函数把它作为**第六项**并列报出（`failed` / `not_evaluated` 里同样逐项可见），
      以免它被塞进 `nonnull_rate` 的比值里而**失去可定位性**。
    """
    status, missing = profitability_required_gaps(baseline)
    if status == "undetermined":
        return CheckOutcome(
            check_id="g4_profitability_branch",
            status=STATUS_NOT_EVALUATED,
            violations=(
                CheckViolation(
                    "g4_profitability_branch",
                    "is_profitable 未判定（None）⇒ 无法决定该核哪一支必填项，"
                    "不得判通过也不得猜一支（Ch4 §G.4 / G-03）",
                    str(_field(baseline, "baseline_id") or ""),
                ),
            ),
            scanned={"required": 0},
            notes=("PROFITABILITY_UNDETERMINED: 分支未定，必填项无从核",),
        )
    required = PROFITABLE_REQUIRED if status == "profitable" else UNPROFITABLE_REQUIRED
    violations = ()
    if missing:
        violations = (
            CheckViolation(
                "g4_profitability_branch",
                f"{status} 公司的必填增量缺 {list(missing)}（Ch4 §G.4 / N4.2-04/05）",
                str(_field(baseline, "baseline_id") or ""),
            ),
        )
    return CheckOutcome(
        check_id="g4_profitability_branch",
        status=STATUS_FAIL if violations else STATUS_PASS,
        violations=violations,
        scanned={"required": len(required), "missing": len(missing)},
    )


# ───────────────────────────── 上下文装载 ─────────────────────────────


def form_context_from(root: str | Path) -> FormContext:
    """从 `code_root` 装出 `FormContext`（**复用**既有真源读口，`G-06`）。

    - `facts/{drivers,businesses,claims,relations}.jsonl` → `schema.store.read_records`
      （**不**另写 JSONL 解析）；
    - `derived/` → `scripts.compute.store.iter_all_values`（`Ch9 §3.3.3`）；
    - ⑥ 的跨章引用 → `facts/implied_requirements.jsonl`（Ch5）+
      `facts/recommendations.jsonl`（Ch7），按 `company_id` 归并成 `ch5:` / `ch7:` 前缀的引用。
    """
    from schema.store import read_records, truth_source_status

    drivers = {
        str(r.get("driver_id")): r
        for r in read_records(root, "drivers")
        if r.get("driver_id")
    }
    businesses = {
        str(r.get("business_id")): r
        for r in read_records(root, "businesses")
        if r.get("business_id")
    }
    claims = {
        str(r.get("claim_id")): r for r in read_records(root, "claims") if r.get("claim_id")
    }
    derived: dict[str, Any] = {}
    if truth_source_status(root, "claims") != "missing":
        from scripts.compute.store import iter_all_values

        for row in iter_all_values(root):
            key = str(row.get("derived_id") or "")
            if key:
                derived[key] = row

    chapter: dict[str, list[str]] = {}
    for row in read_records(root, "implied_requirements"):
        company_id = str(row.get("company_id") or "")
        if company_id:
            chapter.setdefault(company_id, []).append(f"ch5:{row.get('requirement_id') or row.get('sample_id') or ''}")
    for row in read_records(root, "recommendations"):
        company_id = str(row.get("company_id") or "")
        if company_id:
            chapter.setdefault(company_id, []).append(f"ch7:{row.get('recommendation_id') or ''}")
    return FormContext(
        drivers=drivers,
        businesses=businesses,
        claims=claims,
        derived=derived,
        relations=tuple(read_records(root, "relations")),
        chapter_refs={k: tuple(sorted(v)) for k, v in chapter.items()},
    )


# ──────────────────── 版本选择：只判"当前版本"（追加式真源的必然） ────────────────────
#
# ★ 为什么必须有这一步（**不是**为了绕开门禁，是追加式真源的结构性后果）：
#   `facts/baselines.jsonl` 是**追加式版本表**（`Ch9 §3.4.2` 纪律 4 / `§N9.1-17`
#   主键 = `(company_id, version)`），历史版本**不得删改**、保留供 as-of 回看。
#   一条 baseline 要"补深度"，唯一合规的动作是**追加新版本行**（旧行原样留存）。
#   ⇒ 若门禁对**所有历史行**逐条判 §G 形式完备性，则任何一次"补深度"都会
#     让**它自己刚补完的历史缺口**永久变红（恒红门禁 = 一定会被关掉，`G-01`），
#     且"当前研究基线是否完备"这个问题**永远不会得到回答**。
#   ⇒ 判据的**被检对象**必须是"每条 `company_id` 的当前版本"：
#     门禁回答的是"**现在**这条研究基线完不完备"，历史版本由 as-of 回看承担。
#   ★ 反面（`G-03`：真空不得当已核）：被跳过的历史版本**必须显式记账 + 计数**，
#     不得静默丢弃 —— 故 `check()` / `g_depth_violations()` 都把跳过数写进输出。


def _sort_key(row: Any) -> tuple[int, int]:
    """版本排序键 = `(version, recorded_seq)`；非整数（含缺失 / `tbd`）一律按 `-1` 处理。

    ★ 为什么两个分量：`version` 是设计给的版本号；`recorded_seq` 是追加序（同版本重写时的次序）。
      `version` 缺失或非法时**不猜值**，按最小处理 —— 于是"当前版本"会退化为"recorded_seq 最大者"，
      仍是**可判定**的（不制造一个假版本号）。
    """

    def _as_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return -1

    return (_as_int(_field(row, "version")), _as_int(_field(row, "recorded_seq")))


def current_baselines(rows: Sequence[Any]) -> list[Any]:
    """从 `baselines` 全量行里挑出**每条 `company_id` 的当前版本**（其余为历史版本）。

    返回顺序按分组键升序（稳定、可复现）。分组键取 `company_id`；缺失时退回 `baseline_id`
    （两者都缺的行自成一键，仍会被判 —— 不因缺键而漏判）。
    """
    latest: dict[str, Any] = {}
    for row in rows:
        key = str(_field(row, "company_id") or _field(row, "baseline_id") or "<unnamed>")
        current = latest.get(key)
        if current is None or _sort_key(row) > _sort_key(current):
            latest[key] = row
    return [latest[k] for k in sorted(latest)]


# ───────────────────────────── 门禁入口 ─────────────────────────────


def check(root: Path) -> CheckReport:
    """CLI：对 `facts/baselines.jsonl` 每条 baseline 跑 `form_complete`。

    ★ 配置缺失（`rules/baseline.yaml` 缺文件/缺键）⇒ `MissingRuleInput` 上抛 ⇒
      `run_checker` 折叠为 **`exit 2 输入异常`**。这与"数据不达标"（`exit 1`）
      **刻意分开**（见 `_rules` 的 docstring）。
    """
    from schema.store import read_records, truth_source_status

    report = CheckReport(checker="valuelayer_completeness")
    status = truth_source_status(root, "baselines")
    if status == "missing":
        raise FileNotFoundError("缺少真源 facts/baselines.jsonl")
    all_baselines = read_records(root, "baselines")
    if not all_baselines:
        # ★ 先看"有没有被检对象"，再读配置：无对象时不必要求规则文件就绪 ——
        #   否则"真源为空"这一事实会被"规则没装好"的输入异常**遮住**，
        #   而两者要传达的信息完全不同。
        report.scanned["baselines"] = 0
        report.notes.append(
            "NO_BASELINES: facts/baselines.jsonl 存在但为空 —— 无被检对象（真空成立，非'已验证'，G-03）"
        )
        return report
    # ★ 只判各 company_id 的**当前版本**（理由见 `current_baselines` 的注释）；
    #   被跳过的历史版本**显式记账 + 计数**（`G-03`：真空/跳过不得当已核）。
    baselines = current_baselines(all_baselines)
    report.scanned["baselines"] = len(baselines)
    report.scanned["baselines_all_versions"] = len(all_baselines)
    report.scanned["baselines_historical_skipped"] = len(all_baselines) - len(baselines)
    if len(all_baselines) != len(baselines):
        report.notes.append(
            f"HISTORICAL_VERSIONS_SKIPPED: facts/baselines.jsonl 共 {len(all_baselines)} 行，"
            f"其中 {len(all_baselines) - len(baselines)} 行为同公司旧版本；"
            "本次只判各 company_id 的当前版本（追加式版本表，历史版本供 as-of 回看："
            "Ch9 §N9.1-17 / §3.4.2）"
        )
    cfg = _rules.baseline_cfg(root)

    ctx = form_context_from(root)
    report.scanned["drivers"] = len(ctx.drivers)
    report.scanned["claims"] = len(ctx.claims)
    report.scanned["derived"] = len(ctx.derived)
    report.scanned["chapter_refs_companies"] = len(ctx.chapter_refs)
    totals = {cid: 0 for cid in CHECK_IDS}
    undecided_threshold = 0
    for row in baselines:
        baseline_id = str(row.get("baseline_id") or "<unnamed>")
        result = form_complete(row, cfg, context=ctx)
        for outcome in result.outcomes:
            totals[outcome.check_id] = totals.get(outcome.check_id, 0) + 1
            # ★ 逐项把「半项不可核」等声明带到 CLI 输出（`G-03`：不可核必须**显式可见**）。
            #   违例清单是"拦不拦"的通道，装不下"不拦但没核"的事实 —— 故走 `notes`。
            #   同时把"最小字段数半项不可核"的次数**机器可读地**计数（见下 `scanned`）：
            #   note 是给人读的，`scanned` 是给守卫/汇总读的，两者都要有（G-03 的"显式 + 计数"）。
            for note in outcome.notes:
                report.notes.append(f"{outcome.check_id}[{baseline_id}]: {note}")
                if note.startswith("MIN_FIELDS_UNDECIDED"):
                    undecided_threshold += 1
            for violation in outcome.violations:
                if outcome.status == STATUS_PASS:
                    continue
                report.violations.append(
                    Violation(
                        f"Ch4-G2-{outcome.check_id}",
                        f"{baseline_id}: {violation.reason}",
                        "facts/baselines.jsonl",
                    )
                )
        if result.gap:
            report.notes.append(
                f"gap[{baseline_id}]: required_input={result.gap['required_input']} "
                f"（Ch4 §G.3：缺口可见且标注'不足以完成'哪一步）"
            )
        report.notes.append(f"form_complete[{baseline_id}]: {result.summary()}")
    report.scanned["checks_total"] = sum(totals.values())
    # ★ 半项不可核的**机器可读**计数（`G-03`：不可核要"显式 + 计数"）。
    #   放在 CLI 顶层 `scanned` 而不是逐项 outcome 的 `scanned`：后者是"逐 section 的字段计数"。
    report.scanned["min_fields_undecided_sections"] = undecided_threshold
    return report


def g_depth_violations(root: Path) -> list[Violation]:
    """**阶段② 判据 `chapter4_g_depth` 的门禁侧入口**（`Ch11 §B` / `施工图 §2 阶段②`）。

    ★ 与 `check()` 的唯一区别在**配置缺失的归因**：
      - `check()` 的语义是"CLI 跑一次完备性校验" ⇒ 配置缺失 = **输入异常**（`exit 2`）；
      - 本函数的语义是"阶段判据**判不通过**" ⇒ 配置缺失 = **该判据不合格**
        （阶段**阻塞**，纪律 12：阶段未过即阻塞，不得静默跳过）。

      把二者混成一个出口，会让"规则文件没装好"变成整个 `stage_gate` 进程以
      `exit 2` 崩掉 —— 五个阶段的台账一条都打不出来，`verify.py` 的
      `_stage_gate_verdict` 会把"输出里五个阶段都没出现"判成"可能静默跳过"（假红）。
      故此处**显式分开**：配置缺失也**照样**产出一条违例（BLOCKED），
      让阶段状态可读、原因可查。
    """
    from schema.store import read_records, truth_source_status

    if truth_source_status(root, "baselines") == "missing":
        return [Violation("nvidia_sample", "缺少真源 facts/baselines.jsonl", "facts/baselines.jsonl")]
    all_baselines = read_records(root, "baselines")
    if not all_baselines:
        return [
            Violation(
                "nvidia_sample",
                "facts/baselines.jsonl 存在但为空 —— 无被检对象，不得据'为空'判 Ch4 §G 深度达标（G-03）",
                "facts/baselines.jsonl",
            )
        ]
    # ★ 与 `check()` 同源：只判各 `company_id` 的**当前版本**（`current_baselines` 的注释给出理由）。
    #   历史版本被跳过这件事，在 `check()` 侧有显式 `scanned`/`notes` 记账；
    #   本函数（阶段判据侧）**只报违例、不报计数**（沿用其既有契约），
    #   故这里对"跳过"的处理是**同一判据、同一被检对象**，不因出口不同而改变口径（`G-06`）。
    baselines = current_baselines(all_baselines)
    try:
        cfg = _rules.baseline_cfg(root)
        # ★ 只要求**必须已拍板**的三项（`CFG_REQUIRED_DECIDED`）。
        #   `min_fields_per_section` **不在内**：真文件里它是 `tbd`（设计未给值），
        #   把它也列进来会让判据以"规则未拍板"为由**恒红**（`G-01`）——
        #   该项的"非空"半部分照常强制，另一半在 `sections_nonempty` 里记不可核（`G-03`）。
        for key in CFG_REQUIRED_DECIDED:
            _rules.baseline_threshold_from(cfg, key)
    except _rules.MissingRuleInput as exc:
        return [
            Violation(
                "nvidia_sample",
                f"Ch4 §G 深度**无法判定**：{exc}",
                _rules.BASELINE_RELPATH,
            )
        ]

    ctx = form_context_from(root)
    out: list[Violation] = []
    for row in baselines:
        baseline_id = str(row.get("baseline_id") or "<unnamed>")
        result = form_complete(row, cfg, context=ctx)
        if result.passed:
            continue
        # ★ `blocked_hint` 的落点：本条短语**专属**于 chapter4_g_depth
        #   （`registry/criterion_counterexamples.yaml` 登记的就是它）——
        #   它不出现在任何别的判据的违例文案里，故"门禁红了"能归因到本判据。
        for violation in result.violations():
            out.append(
                Violation(
                    "nvidia_sample",
                    f"Ch4 §G 形式完备性未过 [{baseline_id}][{violation.check_id}]：{violation.reason}",
                    "facts/baselines.jsonl",
                )
            )
    return out


if __name__ == "__main__":
    import sys

    sys.exit(run_checker("valuelayer_completeness.py", check))
