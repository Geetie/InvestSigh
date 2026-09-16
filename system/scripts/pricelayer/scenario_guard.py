#!/usr/bin/env python3
"""`scenario_guard.py` —— **情景口径一致性** + **`probability` 默认 `null`**（`Ch5 §E.3/§E.4/§D.6`）。

## 逐字依据

1. **情景口径一致性**（`Ch5 §E.3` 逐字伪码）：

   ```python
   def assert_scenario_match(stock, benchmark):
       if stock.scenario_tag != benchmark.scenario_tag:
           raise ScenarioMismatch(stock.scenario_tag, benchmark.scenario_tag)  # 拒绝生成相对判断
       return True
   ```

   `Ch5 §E.3` 单测要求：「个股乐观 + 基准悲观 → 断言 `ScenarioMismatch`（`N5.4-08`）
   —— **不能比较个股乐观情景与基准悲观情景**」。

2. **`probability` 默认 `null`**（`Ch5 §D.6`）：

   ```python
   assert field_default("probability") is None                # 默认空
   assert "probability" not in required_fields                # 非必填
   ```

   `Ch5 §D.6` 逐字："情景概率默认 `null`（不默认 50/50）；仅当有依据才填"。
   ⇒ 本模块的入参一律 `probability: Decimal | None = None`，**没有任何"默认概率"分支**。

3. **`scenario_method_status` 默认 `pending`**（`Ch5 §E.4` 逐字）：

   ```yaml
   scenario_method_status: pending | neutral | probability_weighted    # 默认 pending
   ```

   「首版方法（中性情景 vs 概率加权）未定 → **显式 `pending`，不静默默认**」；
   `pending` 时 `assert_scenario_match` 无法建立一致口径 → **阻塞相对判断生成**
   （第七章前置门收不到可用的 `benchmark_forecast`，输出"待判断"而非建议）。

4. **情景标签体系**（`Ch5 §J4` 逐字）：`{bear, neutral, bull, custom}`，首版仅用一致标签。

## 判据鲁棒性（`R-06`）

- 情景标签取 **enum 全等**（不是"文本里像乐观"）；标签集合由 `Ch5 §J4` 逐字给出。
- `probability` 的"有依据"判据取 **allowlist 形式**：
  `probability is None` ∨（`basis_ref` 非空 **且** 该引用真的能解析到 `DerivedValue`）
  —— 未列入即拒（`Ch5 §J9` / `00_待拍板项清单` B11："须为 `DerivedValue` 且标注来源"）。

## CLI

```
python system/scripts/pricelayer/scenario_guard.py [code_root]
```

退出码 `0` 放行 / `1` 命中违例 / `2` 输入异常（复用 `_common.run_checker`）。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if __package__:
    from . import ProbabilityWithoutBasis, PriceLayerError, ScenarioMethodPending, ScenarioMismatch
else:  # 直接以脚本方式运行（CLI 出口；仓库既有守卫都是这种调用方式）
    from scripts.pricelayer import (
        ProbabilityWithoutBasis,
        PriceLayerError,
        ScenarioMethodPending,
        ScenarioMismatch,
    )

SCENARIO_YAML = "rules/scenario.yaml"


class ScenarioTag(str, Enum):
    """情景标签（`Ch5 §J4` 逐字："定义 `{bear, neutral, bull, custom}`，首版仅用一致标签"）。"""

    bear = "bear"
    neutral = "neutral"
    bull = "bull"
    custom = "custom"


SCENARIO_METHOD_STATUSES: tuple[str, ...] = ("pending", "neutral", "probability_weighted")
"""`Ch5 §E.4` 逐字的取值域（`pending | neutral | probability_weighted`）。"""

DEFAULT_SCENARIO_METHOD_STATUS = "pending"
"""`Ch5 §E.4` 逐字默认值：「首版方法（中性情景 vs 概率加权）未定 → **显式 `pending`**」。"""

PROBABILITY_DEFAULT: None = None
"""`Ch5 §D.6` 逐字：`probability` 默认 `null`（**不是 50/50**）。

★ 单测断言本常量恒为 `None`（`field_default("probability") is None` 的等价形式）——
  它是"本层没有默认概率"的**机器可核**证据。
"""


class ScenarioGuardError(PriceLayerError):
    """情景层的**输入结构**错误（未知标签 / 未知状态等）。"""


@dataclass(frozen=True)
class ScenarioPolicy:
    """`scenario_method_status` 的解析结果（**带来源标注**，使"值从哪来"可审计）。

    - `status`：`Ch5 §E.4` 的三取值之一；
    - `value_source`：`"rules"` = 来自 `rules/scenario.yaml`；`"design_default"` = 文件/键缺失，
      按 `Ch5 §E.4` 的**逐字默认** `pending` 取值（**显式标注**，不是静默兜底）；
    - `method_version`：转正后记录的方法版本（`§E.4`："`status` 转 `neutral`/`probability_weighted`
      + 记 `method_version`"）。
    """

    status: str
    value_source: str
    method_version: str = ""
    notes: tuple[str, ...] = ()

    @property
    def is_pending(self) -> bool:
        return self.status == DEFAULT_SCENARIO_METHOD_STATUS


def load_scenario_policy(root: str | Path | None = None) -> ScenarioPolicy:
    """读 `rules/scenario.yaml` 的 `scenario_method_status`（**唯一读口**）。

    - 文件缺失 / 无该键 → 取 `Ch5 §E.4` 的**逐字默认** `pending`，并把 `value_source`
      标成 `"design_default"`（显式；**不静默**）。
    - 键存在但取值不在 `SCENARIO_METHOD_STATUSES` 内 → `ScenarioGuardError`（响亮失败，
      不许"未知状态当 pending 用"）。
    """
    from scripts._common import _cached_yaml  # `P-02`：配置读取走统一缓存

    if root is None:
        return ScenarioPolicy(status=DEFAULT_SCENARIO_METHOD_STATUS, value_source="design_default")
    path = Path(root) / SCENARIO_YAML
    if not path.exists():
        return ScenarioPolicy(
            status=DEFAULT_SCENARIO_METHOD_STATUS,
            value_source="design_default",
            notes=(f"NO_SCENARIO_YAML: {SCENARIO_YAML} 不存在，按 Ch5 §E.4 的逐字默认 pending",),
        )
    doc = _cached_yaml(path) or {}
    status = doc.get("scenario_method_status")
    if status is None:
        return ScenarioPolicy(
            status=DEFAULT_SCENARIO_METHOD_STATUS,
            value_source="design_default",
            notes=(f"NO_SCENARIO_METHOD_STATUS: {SCENARIO_YAML} 缺该键，按 Ch5 §E.4 默认 pending",),
        )
    if status not in SCENARIO_METHOD_STATUSES:
        raise ScenarioGuardError(
            f"{SCENARIO_YAML}: scenario_method_status={status!r} 非法；"
            f"合法值 {list(SCENARIO_METHOD_STATUSES)}（Ch5 §E.4）"
        )
    return ScenarioPolicy(
        status=str(status),
        value_source="rules",
        method_version=str(doc.get("method_version") or ""),
    )


def _tag_value(tag: ScenarioTag | str) -> str:
    """取标签的**字符串值**；未知标签 → `ScenarioGuardError`（enum 全等判定，非文本相似）。"""
    if isinstance(tag, ScenarioTag):
        return tag.value
    try:
        return ScenarioTag(tag).value
    except ValueError as exc:
        raise ScenarioGuardError(
            f"未知情景标签 {tag!r}；合法值 {[t.value for t in ScenarioTag]}（Ch5 §J4）"
        ) from exc


def assert_scenario_match(stock: ScenarioTag | str, benchmark: ScenarioTag | str) -> bool:
    """个股与基准的**情景标签必须一致**，否则**拒绝**生成相对判断（`Ch5 §E.3` / `N5.4-08`）。

    ★ 逐字依据：`Ch5 §E.3`「**不能比较个股乐观情景与基准悲观情景**」。
    ★ 返回值恒为 `True`（通过时）—— 与 `§E.3` 伪码的 `return True` 一致；失败即抛。
    """
    stock_tag = _tag_value(stock)
    benchmark_tag = _tag_value(benchmark)
    if stock_tag != benchmark_tag:
        raise ScenarioMismatch(stock_tag, benchmark_tag)
    return True


def assert_relative_judgment_allowed(policy: ScenarioPolicy) -> None:
    """`scenario_method_status = pending` → **阻塞**相对判断生成（`Ch5 §E.4` / `N5.4-07`）。

    `Ch5 §E.4` 逐字："`pending` 时 `assert_scenario_match` 无法建立一致口径
    → **阻塞相对判断生成**（第七章前置门收不到可用的 `benchmark_forecast`，
    输出'待判断'而非建议）" ⇒ 此处 `ScenarioMethodPending`（**拒绝**，不是 warn）。
    """
    if policy.is_pending:
        raise ScenarioMethodPending(
            f"scenario_method_status={policy.status}（来源 {policy.value_source}）—— "
            "方法未定 ⇒ 阻塞相对判断生成（Ch5 §E.4 / N5.4-07；下游应输出'待判断'）"
        )


def assert_probability_has_basis(
    probability: Decimal | None,
    *,
    basis_ref: str = "",
    resolve: Callable[[str], Any] | None = None,
) -> None:
    """`probability` **非空**时必须有依据，否则拒绝（`Ch5 §J9` / B11）。

    allowlist 形式（`R-06 ⑤`）：仅当
    ① `probability is None`（默认空，合法），或
    ② `basis_ref` 非空 **且**（给了 `resolve` 时）该引用能解析到非 `None` 的 `DerivedValue`
    —— 二者之一成立才放行；**未列入即拒**。
    """
    if probability is None:
        return
    if not basis_ref:
        raise ProbabilityWithoutBasis(
            "probability 非空但未标注来源 —— Ch5 §J9 / B11：须为 DerivedValue 且标注来源，"
            "否则默认 null（不是 50/50）"
        )
    if resolve is not None:
        basis = resolve(basis_ref)
        if basis is None:
            raise ProbabilityWithoutBasis(
                f"probability 的依据 {basis_ref!r} 无法解析到 DerivedValue —— "
                "Ch5 §J9：依据须为 DerivedValue（追不到 operand 的不算依据）"
            )
        if not getattr(basis, "formula", "") or not getattr(basis, "operands", None):
            raise ProbabilityWithoutBasis(
                f"probability 的依据 {basis_ref!r} 缺 formula/operands —— "
                "Ch9 §3.4.4：DerivedValue 必须携带三要件"
            )


@dataclass(frozen=True)
class ScenarioEstimate:
    """上/下行情景（`Ch5 §N5.3-05`："上下行情景字段（**不含概率**）"+ `§D.6` 概率默认空）。

    ★ 默认构造出的实例 `probability is None` —— 这是 `Ch5 §D.6` 的机器绑定。
    """

    tag: ScenarioTag
    range_low: Decimal | None = None
    range_high: Decimal | None = None
    probability: Decimal | None = PROBABILITY_DEFAULT


# ───────────────────────── 守卫：真源扫描（CLI 承载面） ─────────────────────────

NOTE_NO_BASELINE_ROWS = "NO_BASELINE_ROWS"


def check(root: str | Path) -> Any:
    """扫描 `facts/baselines.jsonl` 的 `valuation.probability`：非空必须有依据。

    判据（`Ch5 §D.6` + `§J9` + B11）：`valuation.probability` 非空时，
    `valuation.formula_ref` 必须指向一条**真实存在于 `derived/derived_values.jsonl`** 的
    `DerivedValue`（带 `formula` + `operands`）—— 否则违例。

    ★ **运行时效果**断言：引用的**能不能解析到真源里的那条记录**是判据，
      不是"字段里有没有出现某个词"（`R-06 ⑥`）。
    ★ 空样本 → 显式 note（`G-03`）。
    """
    from scripts._common import CheckReport, Violation
    from schema.store import read_records

    root_path = Path(root)
    report = CheckReport(checker="pricelayer_scenario_guard")
    baselines = read_records(root_path, "baselines")
    report.scanned["baselines"] = len(baselines)
    if not baselines:
        report.notes.append(f"{NOTE_NO_BASELINE_ROWS}: facts/baselines.jsonl 无行（非'已验证'）")
        return report

    # ★ `DerivedValue` 的真源在 `derived/derived_values.jsonl`（**不在** `facts/`）——
    #   故走 `scripts.compute.store` 的既有读口（`G-06`：不新写第二条 derived 读路径）。
    from scripts.compute.store import read_rows

    derived_ids = {
        str(row.get("derived_id"))
        for row in read_rows(root_path, "derived_values")
        if row.get("derived_id")
    }
    report.scanned["derived_values"] = len(derived_ids)
    checked = 0
    for row in baselines:
        valuation = row.get("valuation") or {}
        if not isinstance(valuation, Mapping):
            continue
        probability = valuation.get("probability")
        if probability is None:
            continue
        checked += 1
        baseline_id = str(row.get("baseline_id") or "<no-baseline_id>")
        formula_ref = str(valuation.get("formula_ref") or "")
        # `schema.models.Valuation.formula_ref` 的缺省值是 `"tbd"`（占位 token）——
        # 那**不是**一个依据引用，必须与"空"同等对待，否则"没填依据"会被误报成"依据追不到"。
        if not formula_ref or formula_ref == "tbd":
            report.violations.append(
                Violation(
                    "PROBABILITY-WITHOUT-BASIS",
                    f"baseline {baseline_id!r}: probability={probability} 但无 formula_ref —— "
                    "Ch5 §J9 / B11：须为 DerivedValue 且标注来源，否则默认 null",
                )
            )
            continue
        if formula_ref not in derived_ids:
            report.violations.append(
                Violation(
                    "PROBABILITY-BASIS-UNRESOLVED",
                    f"baseline {baseline_id!r}: probability 的依据 {formula_ref!r} "
                    "无法解析到 derived/derived_values.jsonl 中的 DerivedValue（Ch5 §J9）",
                )
            )
    report.scanned["probabilities_checked"] = checked
    if checked == 0:
        report.notes.append(
            "NO_PROBABILITY_FILLED: 无任何已填概率（默认 null 是设计常态，非'已验证'）"
        )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """CLI：`python system/scripts/pricelayer/scenario_guard.py [code_root]`。"""
    from scripts._common import run_checker

    return run_checker("pricelayer_scenario_guard", check, argv)


if __name__ == "__main__":  # pragma: no cover - CLI 出口
    raise SystemExit(main())
