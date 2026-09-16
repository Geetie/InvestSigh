#!/usr/bin/env python3
"""`order_guard.py` —— **顺序约束**与**倒填检测四规则**（`Ch5 §D.3` / `§D.4` / `§B.5`）。

## 三条逐字依据（设计是权威）

1. **顺序约束**（`Ch5 §D.3` 逐字伪码）：

   ```python
   def compute_valuation(baseline_version, params, *, compute_time):
       assert baseline_version.system_time.analyzed_at < compute_time, \
           "估值计算时间必须晚于 baseline 版本时间（禁止倒填）"
   ```

   ⇒ `assert_version_order()` 复用**唯一真源** `scripts.compute.valuation.require_baseline_before_compute`
   （`G-06`：不新写第二条顺序校验路径），并保证**时间契约必须显式**（缺 → 缺口类 `MissingInput`，
   不得用"当前时间"兜底 —— 否则倒填不可检）。

2. **倒填检测四规则**（`Ch5 §D.4` 逐字四条，本模块逐条落码）：

   | 规则 | 判定 | 处置 |
   |---|---|---|
   | `param_modified_after_issue` | `valuation_param.modified_at > recommendation.issued_at` | 标可疑 → 复核 |
   | `boundary_tuned_param` | 结论对某参数高度敏感**且**参数被调到**刚好跨阈值** | 标可疑 + **要求敏感性披露** |
   | `manual_without_history` | 假设来源为人工设定**且无变更记录** | 标可疑 |
   | `version_reversed` | baseline 版本时间**晚于**估值时间 | **拒绝**（`OrderViolation`） |

3. **反解不得回灌 baseline**（`Ch5 §B.5` 逐字伪码 + 单测要求）：

   ```python
   FORBIDDEN_BASELINE_SOURCES = {"implied_solution", "implied_requirements"}
   def assert_baseline_source_ok(assumption):
       if assumption.source in FORBIDDEN_BASELINE_SOURCES:
           raise OrderViolation("反解输出不可直接作 baseline 输入（仅作研究线索）")
   ```

   `Ch5 §B.5` 裁决 `C45-1`：「反解 = 诊断（不产建议），正估 = 定价（先 baseline 后估值）」。
   单测逐字要求：「构造一个 `source=implied_solution` 的假设写入 `baselines.driver_model`
   → 断言被 `OrderViolation` **拒绝**；反解输出**只允许**写 `implied_requirements` 或 `gap`」。

## 判据鲁棒性（`CONVENTIONS.md::R-06`）

- **写目标**用 **allowlist**（`ALLOWED_IMPLIED_WRITE_TARGETS = {"implied_requirements", "gap"}`）——
  这是 `Ch5 §B.5` **逐字给的**封闭集合，未列入即拒（可穷尽）。
- **禁用的 baseline 来源**按 `Ch5 §B.5` **逐字**取 denylist（`FORBIDDEN_BASELINE_SOURCES`）；
  `source` 的完整取值域设计**没有给**，故不自行编一个 allowlist 冒充"设计如此"
  （`R-04` 不自行裁决）—— 该缺口已写进报告"待裁定"。
- 每条规则**可判定**：输入是显式的数值 / 时间 / 枚举，不是"文本里出现了什么词"。

## CLI（可执行反例的承载面）

```
python system/scripts/pricelayer/order_guard.py [code_root]
```

退出码 `0` 放行 / `1` 命中违例 / `2` 输入异常（复用 `_common.run_checker`）。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if __package__:
    from . import PriceLayerError, order_violation
else:  # 直接以脚本方式运行（CLI 出口；仓库既有守卫都是这种调用方式）
    from scripts.pricelayer import PriceLayerError, order_violation

# ───────────────────────── 反解不得回灌 baseline（`Ch5 §B.5`） ─────────────────────────

FORBIDDEN_BASELINE_SOURCES: frozenset[str] = frozenset({"implied_solution", "implied_requirements"})
"""`Ch5 §B.5` **逐字**给出的禁用来源集合（反解输出不可直接作 baseline 输入）。"""

ALLOWED_IMPLIED_WRITE_TARGETS: frozenset[str] = frozenset({"implied_requirements", "gap"})
"""`Ch5 §B.5` **逐字**：「反解输出**只允许**写 `implied_requirements` 或 `gap`」。

★ allowlist（`R-06 ⑤`）：未列入的写目标**默认拒绝** —— 故可穷尽，不靠"再补几个非法目标名"。
"""


class OrderGuardError(PriceLayerError):
    """顺序 / 倒填相关的**本层**拒绝（`OrderViolation` 之外的结构性错误，如写目标非法）。"""


def _source_of(assumption: Any) -> Any:
    """从"假设对象 / 映射"取 `source`（`Ch5 §B.5` 的 `assumption.source`）。

    支持两种载体（`None` = 未声明来源）：
    - 具 `source` 属性的对象（如 `AssumptionInput` 的同族投影对象）；
    - `Mapping`（键 `"source"`）。
    """
    if assumption is None:
        return None
    if isinstance(assumption, Mapping):
        return assumption.get("source")
    return getattr(assumption, "source", None)


def assert_baseline_source_ok(assumption: Any) -> None:
    """反解输出**不得**直接作 baseline 输入（`Ch5 §B.5` 逐字）。

    `source ∈ FORBIDDEN_BASELINE_SOURCES` → `OrderViolation`（**拒绝**，不是 warn）。
    未声明来源（`None`/空串）→ `OrderGuardError`：不声明来源的假设不得冒充"可入 baseline"
    （与 `Ch5 §D.5`「不声明来源的假设不得入库」同向）。
    """
    source = _source_of(assumption)
    if source is None or source == "":
        raise OrderGuardError(
            "假设未声明 source，不得写入 baselines.driver_model —— "
            "不声明来源的假设不可复核（Ch5 §D.5 三类来源分开存）"
        )
    if source in FORBIDDEN_BASELINE_SOURCES:
        raise order_violation(
            f"反解输出不可直接作 baseline 输入（source={source!r}，仅作研究线索）—— Ch5 §B.5 / C45-1"
        )


def assert_write_target_allowed(target: str) -> None:
    """反解产物的写目标必须在 `Ch5 §B.5` 的 allowlist 内；否则拒绝。

    未列入（含空串 / 未知表名）→ `OrderGuardError`（**默认拒绝**，`R-06 ⑤` allowlist 语义）。
    """
    if target not in ALLOWED_IMPLIED_WRITE_TARGETS:
        raise OrderGuardError(
            f"反解输出只允许写 {sorted(ALLOWED_IMPLIED_WRITE_TARGETS)}（实得 {target!r}）—— Ch5 §B.5"
        )


# ───────────────────────── 倒填检测四规则（`Ch5 §D.4`） ─────────────────────────

RULE_PARAM_MODIFIED_AFTER_ISSUE = "param_modified_after_issue"
RULE_BOUNDARY_TUNED_PARAM = "boundary_tuned_param"
RULE_MANUAL_WITHOUT_HISTORY = "manual_without_history"
RULE_VERSION_REVERSED = "version_reversed"
"""`Ch5 §D.4` 四规则的稳定 token（英文小写+下划线，纪律 5 命名规范）。"""

BACKFILL_RULES: tuple[str, ...] = (
    RULE_PARAM_MODIFIED_AFTER_ISSUE,
    RULE_BOUNDARY_TUNED_PARAM,
    RULE_MANUAL_WITHOUT_HISTORY,
    RULE_VERSION_REVERSED,
)
"""四规则的**穷尽**清单（判据现读它，非关键词式判定）。"""

NOTE_NO_RECOMMENDATION_CONTEXT = "NO_RECOMMENDATION_CONTEXT"
"""无建议上下文时 `param_modified_after_issue` **不可判定** —— 显式记 note（`G-03`）。"""


@dataclass(frozen=True)
class ParamObservation:
    """一个估值参数的**观测快照**（四规则判定的输入；全部为显式数值/时间/枚举）。

    | 字段 | 用途 |
    |---|---|
    | `name` / `value` / `decision_threshold` | 规则②：判断参数是否**刚好跨阈值** |
    | `modified_at` | 规则①：`modified_at > recommendation.issued_at` → 参数后改 |
    | `input_source` / `change_records` | 规则③：`manual` 且无变更记录 → 可疑 |
    | `low_param` / `high_param` / `conclusion_at_low` / `conclusion_at_high` | 规则②的**敏感度**由**程序算**（斜率），不由模型口算 |

    ★ `decision_threshold` 与 `low/_high/_conclusion_*` 都是**调用方给的观测**，
      阈值本身不是本层新增的门槛（`Ch11 §E.1` 红线一：参数不得被补成新的策略门槛）。
    """

    name: str
    value: Decimal
    decision_threshold: Decimal | None = None
    modified_at: datetime | None = None
    input_source: str | None = None
    change_records: Sequence[str] = ()
    low_param: Decimal | None = None
    high_param: Decimal | None = None
    conclusion_at_low: Decimal | None = None
    conclusion_at_high: Decimal | None = None


@dataclass(frozen=True)
class RecommendationContext:
    """建议上下文（规则①的右侧时间锚）。

    ★ 字段名与 `Ch5 §D.4` 逐字一致（`recommendation.issued_at`）。真实建议对象
      （`schema.models.Recommendation`）暂用 `TimeMixin.analyzed_at` 承载"发出时间"
      —— 该映射已登记为待裁定项（见报告）。
    """

    recommendation_id: str
    issued_at: datetime


@dataclass(frozen=True)
class BackfillFinding:
    """一条倒填可疑项。`requires_sensitivity` 是 `Ch5 §D.4` 规则②的处置要求（敏感性披露）。"""

    rule: str
    subject: str
    detail: str
    requires_sensitivity: bool = False

    def render(self) -> str:
        suffix = "（要求敏感性披露）" if self.requires_sensitivity else ""
        return f"[{self.rule}] {self.subject} — {self.detail}{suffix}"


@dataclass
class BackfillReport:
    """倒填检测结果（规则①②③）；规则④（版本倒序）**拒绝**故不走本报告。"""

    suspicious: list[BackfillFinding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    evaluated: list[str] = field(default_factory=list)

    @property
    def has_suspicious(self) -> bool:
        return bool(self.suspicious)


def detect_param_modified_after_issue(
    param: ParamObservation,
    recommendation: RecommendationContext | None,
    *,
    subject: str,
    report: BackfillReport,
) -> None:
    """规则①（`Ch5 §D.4`）：`valuation_param.modified_at > recommendation.issued_at` → 标可疑。

    少了任一侧时间（`param.modified_at is None` 或 `recommendation is None`）⇒ **不可判定**
    ⇒ 记显式 note 并计数（`G-03`：不得把"无被检对象"当"已验证"）。
    """
    if param.modified_at is None or recommendation is None:
        report.notes.append(
            f"{NOTE_NO_RECOMMENDATION_CONTEXT}: 参数 {param.name!r}（{subject}）"
            "缺少 modified_at 或建议上下文，规则①不可判定"
        )
        return
    report.evaluated.append(RULE_PARAM_MODIFIED_AFTER_ISSUE)
    if param.modified_at > recommendation.issued_at:
        report.suspicious.append(
            BackfillFinding(
                rule=RULE_PARAM_MODIFIED_AFTER_ISSUE,
                subject=f"{subject} / {param.name}",
                detail=(
                    f"参数在建议发出后{param.modified_at.isoformat()}被改"
                    f"（建议 issued_at={recommendation.issued_at.isoformat()}）"
                ),
            )
        )


def param_sensitivity_slope(param: ParamObservation, *, subject: str) -> Decimal:
    """规则②的**敏感度**：`|Δ结论 / Δ参数|`（**程序做算术**，`Ch5 §B.3`）。

    `high_param == low_param` 时该斜率无定义 → `UndefinedComputation`（缺口类，不返回 0/None）。
    """
    from scripts.compute.contract import UndefinedComputation

    for name in ("low_param", "high_param", "conclusion_at_low", "conclusion_at_high"):
        if getattr(param, name) is None:
            raise UndefinedComputation(
                f"{subject} / {param.name}: 规则②敏感度需要 {name}（不得默认 0）",
                missing=[name],
                subject=subject,
            )
    delta_param = param.high_param - param.low_param  # type: ignore[operator]
    if delta_param == 0:
        raise UndefinedComputation(
            f"{subject} / {param.name}: low_param == high_param，敏感度无定义",
            missing=["high_param"],
            subject=subject,
        )
    delta_conclusion = param.conclusion_at_high - param.conclusion_at_low  # type: ignore[operator]
    slope = delta_conclusion / delta_param
    return abs(slope)


def detect_boundary_tuned_param(
    param: ParamObservation,
    *,
    sensitivity_threshold: Decimal,
    boundary_margin: Decimal,
    subject: str,
    report: BackfillReport,
) -> None:
    """规则②（`Ch5 §D.4`）：结论对某参数**高度敏感** **且** 参数被调到**刚好跨阈值** → 标可疑。

    两个条件都是**程序算的**可判定量：

    - 高度敏感：`param_sensitivity_slope(param) >= sensitivity_threshold`；
    - 刚好跨阈值：`|value - decision_threshold| <= boundary_margin`。

    ★ `sensitivity_threshold` 与 `boundary_margin` **由调用方显式给出**（设计未给值，`Ch5 §J`；
      不许本层内置一个"看起来合理"的数 —— 那是自行裁决）。
    """
    if param.decision_threshold is None:
        report.notes.append(
            f"{NOTE_NO_RECOMMENDATION_CONTEXT}: 参数 {param.name!r}（{subject}）"
            "缺 decision_threshold，规则②的'跨阈值'侧不可判定"
        )
        return
    report.evaluated.append(RULE_BOUNDARY_TUNED_PARAM)
    slope = param_sensitivity_slope(param, subject=subject)
    distance = abs(param.value - param.decision_threshold)
    if slope >= sensitivity_threshold and distance <= boundary_margin:
        report.suspicious.append(
            BackfillFinding(
                rule=RULE_BOUNDARY_TUNED_PARAM,
                subject=f"{subject} / {param.name}",
                detail=(
                    f"结论对该参数高度敏感（斜率 {slope} ≥ {sensitivity_threshold}）"
                    f"且参数距阈值仅 {distance}（≤ {boundary_margin}）"
                ),
                requires_sensitivity=True,
            )
        )


def detect_manual_without_history(
    param: ParamObservation,
    *,
    subject: str,
    report: BackfillReport,
) -> None:
    """规则③（`Ch5 §D.4`）：`assumption_source=manual` **且无变更记录** → 标可疑。

    ★ 命名取舍（如实登记）：`Ch5 §D.4` 写的是 `assumption_source`，而 `Ch5 §D.5` 与
      schema 的字段名是 `input_source`（`R-15 ③` 一概念一字段名）。本模块按**字段真源**
      （`schema.models.InputSource` / §D.5）取 `input_source`，并在报告登记 §D.4 的命名差异。
      枚举值取 **`InputSource.manual.value`**（`"manual"`），不新造字面量副本。
    """
    from schema.models import InputSource

    report.evaluated.append(RULE_MANUAL_WITHOUT_HISTORY)
    if param.input_source == InputSource.manual.value and not list(param.change_records):
        report.suspicious.append(
            BackfillFinding(
                rule=RULE_MANUAL_WITHOUT_HISTORY,
                subject=f"{subject} / {param.name}",
                detail="人工设定的假设没有变更记录（无法复核改了什么、为什么改）",
            )
        )


def assert_version_order(
    baseline_analyzed_at: datetime | None,
    compute_time: datetime | None,
    *,
    subject: str,
) -> None:
    """规则④（`Ch5 §D.4` / `§D.3`）：baseline 版本时间**晚于**估值时间 → **拒绝**。

    ★ **复用** `scripts.compute.valuation.require_baseline_before_compute`（`G-06` 唯一真源）；
      本函数**不**重写比较逻辑，只做"规则④"的**命名与落点**（使四规则在代码里可逐条指认）。
    """
    from scripts.compute.valuation import require_baseline_before_compute

    require_baseline_before_compute(baseline_analyzed_at, compute_time, subject=subject)


def detect_backfill(
    params: Sequence[ParamObservation],
    *,
    subject: str,
    sensitivity_threshold: Decimal,
    boundary_margin: Decimal,
    recommendation: RecommendationContext | None = None,
    baseline_analyzed_at: datetime | None = None,
    compute_time: datetime | None = None,
) -> BackfillReport:
    """跑倒填四规则，返回报告。

    - 规则①②③ → 进 `BackfillReport.suspicious`；规则④ → 直接 `OrderViolation`（拒绝）。
    - 规则④ 的两侧时间都给了才判（`assert_version_order` 自身对 `None` 抛 `MissingInput`），
      故本函数只在**至少一侧给了**时执行，避免"没给时间"被当成倒填。
    - 空 `params` ⇒ 返回**空报告 + note**（`G-03`：不得把"无被检对象"当"已验证"）。
    """
    report = BackfillReport()
    if not params:
        report.notes.append(
            "NO_PARAM_OBSERVATIONS: 未提供任何估值参数观测 —— 倒填①②③**不可判定**（非'已验证'）"
        )
    for param in params:
        detect_param_modified_after_issue(param, recommendation, subject=subject, report=report)
        detect_boundary_tuned_param(
            param,
            sensitivity_threshold=sensitivity_threshold,
            boundary_margin=boundary_margin,
            subject=subject,
            report=report,
        )
        detect_manual_without_history(param, subject=subject, report=report)

    if baseline_analyzed_at is not None or compute_time is not None:
        assert_version_order(baseline_analyzed_at, compute_time, subject=subject)
    else:
        report.notes.append(
            "NO_TIME_PAIR: 未提供 baseline 版本时间 / 估值时间 —— 规则④（版本倒序）未执行"
        )
    return report


# ───────────────────────── 守卫：真源扫描（CLI 承载面） ─────────────────────────

NOTE_NO_IMPLIED_ROWS = "NO_IMPLIED_ROWS"
NOTE_NO_BASELINE_ROWS = "NO_BASELINE_ROWS"


def _multi_solution_violations(root: Path) -> tuple[list[str], list[str], int]:
    """`Ch5 §B.1` 多解不变式：同一 `solution_set_id` **必须**有多组解。

    返回 `(violations, notes, scanned_solution_sets)`。空样本 → 显式 note（`G-03`）。
    """
    from schema.store import read_records

    rows = read_records(root, "implied_requirements")
    groups: dict[str, int] = {}
    for row in rows:
        sid = str(row.get("solution_set_id") or "")
        if not sid:
            continue
        groups[sid] = groups.get(sid, 0) + 1
    violations: list[str] = []
    for sid, count in sorted(groups.items()):
        if count < 2:
            violations.append(
                f"solution_set {sid!r} 只有 {count} 组解 —— 欠定方程必须展示多组解"
                "（Ch5 §B.1：否则会把某一解误当市场的唯一真相）"
            )
    notes: list[str] = []
    if not groups:
        notes.append(f"{NOTE_NO_IMPLIED_ROWS}: facts/implied_requirements.jsonl 无可用解集（非'已验证'）")
    return violations, notes, len(groups)


def _baseline_backfill_violations(root: Path) -> tuple[list[str], list[str]]:
    """扫描 `baselines` 是否引用了反解产物 id（`Ch5 §B.5` 禁令的**运行时效果**断言）。

    判据取**效果**不取词面：把 `implied_requirements` 真源里的 `implied_id` 集合取出，
    再看 `baselines` 的估值字段（`formula_ref` / `forecast_assumptions` / `valuation_params` /
    `driver_model[].assumptions`）里**是否真的出现这些 id** —— 出现即"反解回灌 baseline"。

    ★ 为什么不是关键词判据（`R-06 ①`）：判据的对照物是**本仓库真源里实际存在的解 id**
      （动态集合），不是"某几个词形"；换一种写法只要引用的还是那些 id，就照样命中。
    """
    from schema.store import read_records

    implied_ids = {
        str(row.get("implied_id"))
        for row in read_records(root, "implied_requirements")
        if row.get("implied_id")
    }
    baselines = read_records(root, "baselines")
    notes: list[str] = []
    violations: list[str] = []
    if not baselines:
        notes.append(f"{NOTE_NO_BASELINE_ROWS}: facts/baselines.jsonl 无行（非'已验证'）")
    if not implied_ids:
        notes.append(f"{NOTE_NO_IMPLIED_ROWS}: 无反解 id 可比对，本判据真空成立")
    if not (baselines and implied_ids):
        return violations, notes

    for row in baselines:
        baseline_id = str(row.get("baseline_id") or "")
        valuation = row.get("valuation") or {}
        surfaces: list[str] = []
        if isinstance(valuation, Mapping):
            surfaces.append(str(valuation.get("formula_ref") or ""))
            surfaces.extend(str(x) for x in (valuation.get("forecast_assumptions") or []))
            surfaces.extend(str(x) for x in (valuation.get("valuation_params") or []))
        for dm in row.get("driver_model") or []:
            if isinstance(dm, Mapping):
                surfaces.extend(str(x) for x in (dm.get("assumptions") or []))
        hit = sorted({ref for ref in implied_ids if any(ref in s for s in surfaces)})
        if hit:
            violations.append(
                f"baseline {baseline_id!r} 的估值输入引用了反解产物 {hit} —— "
                "反解输出不可直接作 baseline 输入（Ch5 §B.5 / C45-1）"
            )
    return violations, notes


def check(root: str | Path) -> Any:
    """跑顺序 / 倒填类的**真源**检查，返回 `CheckReport`（`_common.run_checker` 契约）。

    扫两项（都是**运行时效果**断言，不是文本匹配）：
    ① `Ch5 §B.1`：`facts/implied_requirements.jsonl` 的每个 `solution_set_id` 必须有多组解；
    ② `Ch5 §B.5`：`facts/baselines.jsonl` 的估值输入**不得**引用真源里存在的反解 id。
    """
    from scripts._common import CheckReport, Violation

    root_path = Path(root)
    report = CheckReport(checker="pricelayer_order_guard")
    multi_violations, multi_notes, solution_sets = _multi_solution_violations(root_path)
    baseline_violations, baseline_notes = _baseline_backfill_violations(root_path)
    report.scanned["solution_sets"] = solution_sets
    report.scanned["backfill_checks"] = len(multi_violations) + len(baseline_violations)
    report.notes.extend(multi_notes)
    report.notes.extend(baseline_notes)
    for text in (*multi_violations, *baseline_violations):
        report.violations.append(Violation("ORDER-BACKFILL", text))
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """CLI：`python system/scripts/pricelayer/order_guard.py [code_root]`。"""
    from scripts._common import run_checker

    return run_checker("pricelayer_order_guard", check, argv)


if __name__ == "__main__":  # pragma: no cover - CLI 出口
    raise SystemExit(main())
