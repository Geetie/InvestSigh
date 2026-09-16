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

# ── 规则文件键名（**单一真源**：参数只住 `rules/`，代码不得内置 —— `Ch11 §D.2` / `P-09`）──
#    这些键名逐条对应 `rules/scenario.yaml` 的真实顶层键；`check()` 会做**机器绑定**
#    （键不存在 ⇒ 违例），使"规则文件改了、代码没改"当场显形。
RULE_KEY_STATUS = "scenario_method_status"
RULE_KEY_DOMAIN = "scenario_method_status_domain"
RULE_KEY_TAGS = "scenario_tags"
RULE_KEY_BLOCKING = "scenario_method_blocking"          # 子键：when / effect / downstream_output / ...
RULE_KEY_BLOCKING_WHEN = "when"
RULE_KEY_BLOCKING_EFFECT = "effect"
RULE_KEY_BLOCKING_DOWNSTREAM = "downstream_output"
RULE_KEY_BLOCKING_REQUIRED_FIELD = "required_field_at_downstream"
RULE_KEY_PROMOTION = "scenario_method_promotion"
RULE_KEY_RECORD_METHOD_VERSION = "record_method_version"
RULE_KEY_CONSISTENCY = "scenario_consistency"
RULE_KEY_PARAM_REF = "param_ref"                        # → `rules/freeze.yaml` 的参数指针（真实值 `p05`）
RULE_KEY_PROBABILITY = "probability"
RULE_KEY_PROBABILITY_DEFAULT = "default"

REQUIRED_RULE_KEYS: tuple[str, ...] = (
    RULE_KEY_STATUS,
    RULE_KEY_DOMAIN,
    RULE_KEY_TAGS,
    RULE_KEY_BLOCKING,
    RULE_KEY_PROMOTION,
    RULE_KEY_CONSISTENCY,
    RULE_KEY_PROBABILITY,
)
"""本模块**实际读取**的 `rules/scenario.yaml` 顶层键（机器绑定的对照集合）。"""


class ScenarioTag(str, Enum):
    """情景标签（`Ch5 §J4` 逐字："定义 `{bear, neutral, bull, custom}`，首版仅用一致标签"）。

    ★ 仍取 **enum 全等**（`R-06 ①`：不取"文本里像乐观"）；标签**集合**与规则文件的
      `scenario_tags` 的绑定由 `assert_rule_tags_match()` + `check()` 承担
      —— 使"规则文件改了标签集、代码没改"当场显形（`Ch11 §D.2` 防声明与实现脱节）。
    """

    bear = "bear"
    neutral = "neutral"
    bull = "bull"
    custom = "custom"


DESIGN_SCENARIO_METHOD_STATUSES: tuple[str, ...] = ("pending", "neutral", "probability_weighted")
"""`Ch5 §E.4` 逐字取值域。**仅作**规则文件缺 `scenario_method_status_domain` 时的回落 + 显式 note。"""

DEFAULT_SCENARIO_METHOD_STATUS = "pending"
"""`Ch5 §E.4` 逐字默认值：「首版方法（中性情景 vs 概率加权）未定 → **显式 `pending`**」。"""

DESIGN_BLOCKING_WHEN: str = "scenario_method_status == pending"
"""`Ch5 §E.4` 逐字阻塞条件。**仅作**规则文件缺 `scenario_method_blocking.when` 时的回落 + 显式 note。"""

PROBABILITY_DEFAULT: None = None
"""`Ch5 §D.6` 逐字：`probability` 默认 `null`（**不是 50/50**）。

★ 单测断言本常量恒为 `None`（`field_default("probability") is None` 的等价形式）——
  它是"本层没有默认概率"的**机器可核**证据。
★ 规则文件 `rules/scenario.yaml::probability.default` 的**真值**也是 `null`；两者的一致性
  由 `check()` 的机器绑定断言承担（规则文件若被改成数值 ⇒ 违例）。
"""


class ScenarioGuardError(PriceLayerError):
    """情景层的**输入结构**错误（未知标签 / 未知状态等）。"""


@dataclass(frozen=True)
class ScenarioPolicy:
    """`rules/scenario.yaml` 的解析结果（**带来源标注**，使"值从哪来"可审计）。

    - `status`：`scenario_method_status` 的取值（域见 `domain`）；
    - `value_source`：`"rules"` = 来自 `rules/scenario.yaml`；`"design_default"` = 文件/键缺失，
      按 `Ch5 §E.4` 的**逐字默认** `pending` 取值（**显式标注**，不是静默兜底）；
    - `domain`：合法取值域 —— 读 `scenario_method_status_domain`（真值 = 设计三取值）；
    - `blocking` / `blocking_effect` / `blocking_downstream` / `required_field_at_downstream`：
      **读** `scenario_method_blocking`（真文件里就有该口径键）—— 阻塞与否**不再硬编码**；
    - `method_version`：转正后记录的方法版本。★ **不是** `rules/scenario.yaml` 的键
      （该文件只有指针 `scenario_consistency.param_ref → p05`）；值从指针指向的
      `rules/freeze.yaml::p05`（**复用** `config.freeze.get_param`，`G-06`）解析。
      `status == pending` 时恒为空串（转正尚未发生）；
      `status != pending` 而版本不可用 ⇒ **响亮失败**（`ScenarioGuardError`，**不静默取空串**）。
    - `method_version_source`：`"not_applicable_pending"` | `"freeze:<param_id>"`；
    - `param_ref` / `record_method_version`：指针与"转正须记版本"的规则声明。
    """

    status: str
    value_source: str
    domain: tuple[str, ...] = DESIGN_SCENARIO_METHOD_STATUSES
    blocking: bool = True
    blocking_effect: str = ""
    blocking_downstream: str = ""
    required_field_at_downstream: str = ""
    method_version: str = ""
    method_version_source: str = "not_applicable_pending"
    param_ref: str = ""
    record_method_version: bool = True
    notes: tuple[str, ...] = ()

    @property
    def is_pending(self) -> bool:
        """便利判定：`status` 是否等于**设计逐字**默认 `pending`（与 `blocking` 相互独立）。"""
        return self.status == DEFAULT_SCENARIO_METHOD_STATUS


def _blocking_from_rule(doc: Mapping[str, Any], notes: list[str]) -> dict[str, Any]:
    """读 `scenario_method_blocking` 并解析 `when`（**严格最小文法，未知形态响亮失败**）。

    `rules/scenario.yaml` 的真值形如 `when: "scenario_method_status == pending"`。
    本函数只认这一种形态：`<字段> == <单个 token>`，且字段必须恰为 `scenario_method_status`。
    ★ **不发明表达式求值器**：形态不认识就抛 `ScenarioGuardError`（"程序不做假设"），
      绝不"看不懂就当不阻塞"。
    """
    node = doc.get(RULE_KEY_BLOCKING)
    if not isinstance(node, Mapping):
        notes.append(
            f"NO_BLOCKING_RULE: {SCENARIO_YAML} 缺 {RULE_KEY_BLOCKING!r} —— "
            f"回落 Ch5 §E.4 逐字条件 {DESIGN_BLOCKING_WHEN!r}（非'已核'）"
        )
        return {
            "blocking_status": DEFAULT_SCENARIO_METHOD_STATUS,
            "effect": "",
            "downstream": "",
            "required_field": "",
        }
    when = str(node.get(RULE_KEY_BLOCKING_WHEN) or "").strip()
    parts = [p.strip() for p in when.split("==")]
    if len(parts) != 2 or parts[0] != RULE_KEY_STATUS or not parts[1] or any(c.isspace() for c in parts[1]):
        raise ScenarioGuardError(
            f"{SCENARIO_YAML}: {RULE_KEY_BLOCKING}.{RULE_KEY_BLOCKING_WHEN} 形态不认识: {when!r}；"
            "只认 `<字段> == <单个 token>` 且字段恰为 'scenario_method_status' —— "
            "不发明表达式求值器（Ch5 §E.4 逐字形如 'scenario_method_status == pending'）"
        )
    return {
        "blocking_status": parts[1],
        "effect": str(node.get(RULE_KEY_BLOCKING_EFFECT) or ""),
        "downstream": str(node.get(RULE_KEY_BLOCKING_DOWNSTREAM) or ""),
        "required_field": str(node.get(RULE_KEY_BLOCKING_REQUIRED_FIELD) or ""),
    }


def _method_version_from_pointer(
    doc: Mapping[str, Any],
    status: str,
    param_ref: str,
    *,
    root: str | Path,
    record_required: bool,
) -> str:
    """按 `scenario_consistency.param_ref` 指针解析 `method_version`（**无静默兜底**）。

    `§E.4` 逐字："`status` 转 `neutral`/`probability_weighted` **+ 记 `method_version`**"
    —— 故 `status != pending` 时版本必须**可用**；不可用即 **`ScenarioGuardError`**。
    版本值面在 `rules/freeze.yaml::<param_ref>`（真文件里 `scenario_consistency.param_ref = p05`，
    `p05 = return_forecast_method`，其 `suggested_value.algorithm` 现为 `tbd`）
    ⇒ **复用** `config.freeze.get_param` 单一参数读口（`G-06` / `Ch11 §D.2`）。
    """
    if status == DEFAULT_SCENARIO_METHOD_STATUS:
        # 转正尚未发生 ⇒ §E.4 的"记 method_version"尚未适用，空串是**正确值**而非兜底。
        return ""
    if not record_required:
        return ""
    if not param_ref:
        raise ScenarioGuardError(
            f"{SCENARIO_YAML}: {RULE_KEY_CONSISTENCY}.{RULE_KEY_PARAM_REF} 为空，"
            f"而 scenario_method_status={status!r} 已转正 ⇒ method_version 无载体可解析"
            "（Ch5 §E.4 要求转正时记录 method_version；不静默取空串）"
        )
    from config.freeze import UnknownParamError, get_param  # 单一参数读口（G-06）

    try:
        resolution = get_param(param_ref, root)
    except UnknownParamError as exc:
        raise ScenarioGuardError(
            f"{SCENARIO_YAML}: {RULE_KEY_CONSISTENCY}.{RULE_KEY_PARAM_REF}={param_ref!r} "
            f"在 {getattr(exc, 'args', ('rules/freeze.yaml',))[0]} 中不存在 —— 指针悬空"
        ) from exc
    value = resolution.effective_value
    if not isinstance(value, Mapping):
        raise ScenarioGuardError(
            f"{param_ref}: effective_value 不是映射（{type(value).__name__}）—— "
            f"无法取 method_version（shape 未约定即响亮失败）"
        )
    version = str(value.get("algorithm") or "").strip()
    if not version or version == "tbd":
        raise ScenarioGuardError(
            f"scenario_method_status={status!r} 已转正，但 {param_ref}（{resolution.param}）的 "
            f"algorithm={version or '<空>'!r} ⇒ **method_version 不可用**；"
            f"§E.4 要求转正时记录 method_version（{param_ref} 现 freeze_status="
            f"{resolution.freeze_status!r} / resolved_at={value.get('resolved_at')!r}）"
            " —— 不得静默取空串（先冻结参数再转正状态）"
        )
    return version


def load_scenario_policy(root: str | Path | None = None) -> ScenarioPolicy:
    """读 `rules/scenario.yaml` 的 `scenario_method_status` 及其相邻口径键（**唯一读口**）。

    读取面（都是**真文件里存在的键**，不硬编码）：

    | 键 | 用途 | 缺失时 |
    |---|---|---|
    | `scenario_method_status` | 状态值 | 回落 `§E.4` 逐字默认 `pending` + `value_source="design_default"` + note |
    | `scenario_method_status_domain` | 合法取值域 | 回落设计逐字三取值 + note；**值非法 → 响亮失败** |
    | `scenario_method_blocking.when` | 阻塞条件 | 回落 `§E.4` 逐字条件 + note；**形态不认识 → 响亮失败** |
    | `scenario_consistency.param_ref` | `method_version` 指针 | 转正后为空 ⇒ **响亮失败** |
    | `scenario_method_promotion.record_method_version` | 是否须记版本 | 默认 `True`（`§E.4` 逐字要求） |

    ★ `method_version` **不读** `rules/scenario.yaml`（该文件没有这个键）—— 见
      `ScenarioPolicy` 文档与 `_method_version_from_pointer`。
    """
    from scripts._common import _cached_yaml  # `P-02`：配置读取走统一缓存

    if root is None:
        return ScenarioPolicy(status=DEFAULT_SCENARIO_METHOD_STATUS, value_source="design_default")
    root_path = Path(root)
    path = root_path / SCENARIO_YAML
    if not path.exists():
        return ScenarioPolicy(
            status=DEFAULT_SCENARIO_METHOD_STATUS,
            value_source="design_default",
            notes=(f"NO_SCENARIO_YAML: {SCENARIO_YAML} 不存在，按 Ch5 §E.4 的逐字默认 pending",),
        )
    doc = _cached_yaml(path) or {}
    notes: list[str] = []

    status = doc.get(RULE_KEY_STATUS)
    if status is None:
        return ScenarioPolicy(
            status=DEFAULT_SCENARIO_METHOD_STATUS,
            value_source="design_default",
            notes=(f"NO_SCENARIO_METHOD_STATUS: {SCENARIO_YAML} 缺该键，按 Ch5 §E.4 默认 pending",),
        )
    status = str(status)

    domain_raw = doc.get(RULE_KEY_DOMAIN)
    if isinstance(domain_raw, list) and domain_raw and all(isinstance(x, str) for x in domain_raw):
        domain = tuple(str(x) for x in domain_raw)
    else:
        domain = DESIGN_SCENARIO_METHOD_STATUSES
        notes.append(
            f"NO_DOMAIN_KEY: {SCENARIO_YAML} 缺/非法 {RULE_KEY_DOMAIN!r} —— "
            f"回落 Ch5 §E.4 逐字取值域 {list(domain)}（非'已核'）"
        )
    if status not in domain:
        raise ScenarioGuardError(
            f"{SCENARIO_YAML}: {RULE_KEY_STATUS}={status!r} 非法；"
            f"合法值 {list(domain)}（取自 {RULE_KEY_DOMAIN}，Ch5 §E.4）"
        )

    blocking = _blocking_from_rule(doc, notes)
    promotion = doc.get(RULE_KEY_PROMOTION)
    record_required = True
    if isinstance(promotion, Mapping) and RULE_KEY_RECORD_METHOD_VERSION in promotion:
        record_required = bool(promotion.get(RULE_KEY_RECORD_METHOD_VERSION))
    consistency = doc.get(RULE_KEY_CONSISTENCY)
    param_ref = ""
    if isinstance(consistency, Mapping):
        param_ref = str(consistency.get(RULE_KEY_PARAM_REF) or "")

    method_version = _method_version_from_pointer(
        doc, status, param_ref, root=root_path, record_required=record_required
    )

    return ScenarioPolicy(
        status=status,
        value_source="rules",
        domain=domain,
        blocking=status == blocking["blocking_status"],
        blocking_effect=blocking["effect"],
        blocking_downstream=blocking["downstream"],
        required_field_at_downstream=blocking["required_field"],
        method_version=method_version,
        method_version_source=(
            "not_applicable_pending" if not method_version else f"freeze:{param_ref}"
        ),
        param_ref=param_ref,
        record_method_version=record_required,
        notes=tuple(notes),
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
    """`policy.blocking` 为真 → **阻塞**相对判断生成（`Ch5 §E.4` / `N5.4-07`）。

    ★ 阻塞与否**读** `rules/scenario.yaml::scenario_method_blocking.when`（真文件里逐字
      `scenario_method_status == pending`），**不在本函数里硬编码**（`Ch11 §D.2`：参数只住
      `rules/`，代码不得内置）。规则文件改了条件 ⇒ 本函数行为随之改变，无需改代码。
    ★ `Ch5 §E.4` 逐字 ⇒ 此处 `ScenarioMethodPending`（**拒绝**，不是 warn）。
    """
    if not policy.blocking:
        return
    detail = "；".join(x for x in (policy.blocking_effect, policy.blocking_downstream) if x)
    raise ScenarioMethodPending(
        f"scenario_method_status={policy.status}（来源 {policy.value_source}）—— "
        f"方法未定 ⇒ 阻塞相对判断生成（Ch5 §E.4 / N5.4-07；下游应输出'待判断'）"
        f"{f'；规则文件口径：{detail}' if detail else ''}"
        f"{f'；下游所需字段：{policy.required_field_at_downstream}' if policy.required_field_at_downstream else ''}"
    )


def assert_rule_tags_match(root: str | Path | None = None) -> tuple[str, ...]:
    """`rules/scenario.yaml::scenario_tags` 必须与 `ScenarioTag` 枚举**逐字一致**。

    标签判定取 **enum 全等**（`R-06 ①`，不能动态化）；但标签**集合**是参数 ⇒ 必须绑到
    `rules/`（`Ch11 §D.2`）。不一致 ⇒ `ScenarioGuardError`（`Ch11 §D.2` 防声明与实现脱节）。
    规则文件缺失 ⇒ 返回空元组（调用方按"不可判定"处理，**不**当已核）。
    """
    from scripts._common import _cached_yaml

    if root is None:
        return ()
    path = Path(root) / SCENARIO_YAML
    if not path.exists():
        return ()
    doc = _cached_yaml(path) or {}
    declared = doc.get(RULE_KEY_TAGS)
    if not isinstance(declared, list):
        raise ScenarioGuardError(
            f"{SCENARIO_YAML}: 缺/非法 {RULE_KEY_TAGS!r}（应为标签列表，`Ch5 §J4`）"
        )
    tags = tuple(str(x) for x in declared)
    expected = tuple(t.value for t in ScenarioTag)
    if tags != expected:
        raise ScenarioGuardError(
            f"{SCENARIO_YAML}:: {RULE_KEY_TAGS}={list(tags)} 与代码枚举 "
            f"{list(expected)} 不一致 —— 规则文件改了而代码没改（Ch11 §D.2 / Ch5 §J4）"
        )
    return tags


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
    rule_violations, rule_notes = _rule_binding_violations(root_path)
    report.scanned["rule_keys_required"] = len(REQUIRED_RULE_KEYS)
    report.notes.extend(rule_notes)
    for text in rule_violations:
        report.violations.append(Violation("SCENARIO-RULE-BINDING", text))

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


def _rule_binding_violations(root: Path) -> tuple[list[str], list[str]]:
    """**规则↔代码机器绑定**：`rules/scenario.yaml` 必须含本模块实际读取的键，且口径一致。

    判据（都是"声明 vs 实现"的运行时效果断言，不是词面匹配）：

    | # | 判据 | 依据 |
    |---|---|---|
    | ① | 本模块读取的每个顶层键**真实存在** | `Ch11 §D.2`（参数只住 `rules/`，代码不得内置） |
    | ② | `scenario_tags` 与代码枚举**逐字一致** | `Ch5 §J4` + `Ch11 §D.2` |
    | ③ | `probability.default` **恒为 `null`** | `Ch5 §D.6`「不默认 50/50」 |
    | ④ | `probability.must_be_null_50_50` 为 `false` | `Ch5 §D.6` 逐字 |
    | ⑤ | `scenario_method_status` 能解析（含转正后 `method_version` 可用） | `Ch5 §E.4`（**无静默兜底**） |

    ★ 规则文件不存在 → 显式 note（`G-03`：**不**当"已核"）。
    """
    from scripts._common import _cached_yaml

    path = root / SCENARIO_YAML
    if not path.exists():
        return [], [f"NO_SCENARIO_YAML_FOR_BINDING: {SCENARIO_YAML} 不存在 —— 规则绑定不可判定"]
    doc = _cached_yaml(path) or {}
    violations: list[str] = []
    notes: list[str] = []

    missing = [k for k in REQUIRED_RULE_KEYS if k not in doc]
    if missing:
        violations.append(
            f"{SCENARIO_YAML} 缺本模块实际读取的键 {missing} —— 声明与实现脱节（Ch11 §D.2）"
        )

    try:
        assert_rule_tags_match(root)
    except ScenarioGuardError as exc:
        violations.append(str(exc))

    probability = doc.get(RULE_KEY_PROBABILITY)
    if isinstance(probability, Mapping):
        if probability.get(RULE_KEY_PROBABILITY_DEFAULT) is not None:
            violations.append(
                f"{SCENARIO_YAML}:: {RULE_KEY_PROBABILITY}.{RULE_KEY_PROBABILITY_DEFAULT}="
                f"{probability.get(RULE_KEY_PROBABILITY_DEFAULT)!r} 非 null —— "
                "Ch5 §D.6：情景概率默认 null（**不默认 50/50**）"
            )
        if bool(probability.get("must_be_null_50_50")):
            violations.append(
                f"{SCENARIO_YAML}:: {RULE_KEY_PROBABILITY}.must_be_null_50_50 为真 —— "
                "Ch5 §D.6 逐字：不默认 50/50"
            )
    else:
        notes.append(f"NO_PROBABILITY_SECTION: {SCENARIO_YAML} 缺 {RULE_KEY_PROBABILITY!r}（G-03）")

    try:
        policy = load_scenario_policy(root)
    except ScenarioGuardError as exc:
        violations.append(str(exc))
    else:
        notes.extend(policy.notes)
    return violations, notes


def main(argv: Sequence[str] | None = None) -> int:
    """CLI：`python system/scripts/pricelayer/scenario_guard.py [code_root]`。"""
    from scripts._common import run_checker

    return run_checker("pricelayer_scenario_guard", check, argv)


if __name__ == "__main__":  # pragma: no cover - CLI 出口
    raise SystemExit(main())
