#!/usr/bin/env python3
"""`valuation.py` —— **估值计算 + 方法路由 + `DerivedValue` 追溯链**（`Ch5 §D.1/§D.2/§D.3/§D.6`）。

## 逐字依据

1. **方法按商业模式路由**（`Ch5 §D.1`）：`rules/valuation-methods.yaml`：
   `method_class → business.model_class` 绑定；「方法注册表驱动；**未注册类型归入 generic 并标注**」。
   ⇒ 路由表**只**从 `rules/valuation-methods.yaml` 读（`_common._cached_yaml()`，`P-02`）；
     未知 `model_class` → `method_class = generic` **且 `registered=False`**（"标注"= 显式字段，不是沉默）。

2. **可追溯链**（`Ch5 §D.2` 逐字例子）：每个 price range →
   `formula` + `operands` + `method_version` + `share_count` + `compute_date`（`N5.3-02` / `N9.2-02`）。
   ⇒ 这些字段**都在 `DerivedValue` 上**（schema docstring 已明写"不重复 `DerivedValue` 的字段"），
     故 `Valuation.formula_ref` 指向 `derived/derived_values.jsonl` 的那条记录，
     本模块提供 `assert_traceability()` 保证**这条引用真的追得到 operand**。

3. **顺序约束**（`Ch5 §D.3` 逐字伪码）：

   ```python
   def compute_valuation(baseline_version, params, *, compute_time):
       assert baseline_version.system_time.analyzed_at < compute_time, \
           "估值计算时间必须晚于 baseline 版本时间（禁止倒填）"
   ```

4. **区间宽度 + 概率默认空**（`Ch5 §D.6`）：`range{low, high}`；`probability: null`。

## 复用（`G-06` 唯一真源，纪律 11 复用优先）

- **算术**一律走 `scripts.compute.valuation`（`compute_value_per_share_range`）；
  本模块**不重写**任何算式。
- **顺序**一律走 `scripts.pricelayer.order_guard.assert_version_order`
  （其自身复用 `scripts.compute.valuation.require_baseline_before_compute`）。
- **可达性**一律走 `scripts.graph.closure.forward_closure`（把 operand 引用当边喂进去），
  本模块**不新写第二套图遍历**。

## 未定的键名（如实登记，不自行编造）

`rules/valuation-methods.yaml` 的 **YAML 键名**设计**没有给**（`Ch5 §D.1` 只给了
`model_class` → `method_class` 的**映射内容**）。本模块按唯一候选键 `method_routing` 读；
键名不符时**响亮失败**（`exit 2`），**不**静默退回"全部 generic"。该键名已写进报告"待裁定"。

## CLI

```
python system/scripts/pricelayer/valuation.py [code_root]
```

退出码 `0` 放行 / `1` 命中违例 / `2` 输入异常（复用 `_common.run_checker`）。
"""

from __future__ import annotations

import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if __package__:
    from . import PriceLayerError
else:  # 直接以脚本方式运行（CLI 出口；仓库既有守卫都是这种调用方式）
    from scripts.pricelayer import PriceLayerError

VALUATION_METHODS_YAML = "rules/valuation-methods.yaml"
METHOD_ROUTING_KEY = "method_routing"
"""路由表的**候选键名**（`Ch5 §D.1` 未给键名 ⇒ 登记为待裁定；键不符即响亮失败，不静默兜底）。"""

DEFAULT_METHOD_CLASS = "generic"
"""`Ch5 §D.1` 逐字："未注册类型归入 `generic` **并标注**"。"""

METHOD_VERSION = "pricelayer-valuation-v1"


class ValuationError(PriceLayerError):
    """估值层的**输入 / 契约**错误（路由表结构非法、追溯链断裂等）。"""


def load_method_routing(root: str | Path | None = None) -> dict[str, tuple[str, ...]]:
    """读 `rules/valuation-methods.yaml` 的 `method_class → model_class` 路由表。

    返回 `{model_class: (method_class, ...)}`（值可为单值或列表 —— `Ch5 §D.1` 的表中
    `hardware` 对应**四个**方法类，故允许列表）。

    - 文件缺失 / 键缺失 / 结构非法 → `FileNotFoundError` / `ValuationError`
      （**响亮失败**：不静默退化成"全部 generic"，否则路由形同不存在）。
    - 读取走 `scripts._common._cached_yaml`（`P-02`：禁止循环内直接读盘）。
    """
    from scripts._common import _cached_yaml

    if root is None:
        raise FileNotFoundError(f"{VALUATION_METHODS_YAML} 的根目录未给出（不得默认当前目录）")
    path = Path(root) / VALUATION_METHODS_YAML
    if not path.exists():
        raise FileNotFoundError(
            f"缺 {VALUATION_METHODS_YAML} —— 估值方法路由的唯一真源（Ch5 §D.1）"
        )
    doc = _cached_yaml(path) or {}
    raw = doc.get(METHOD_ROUTING_KEY)
    if not isinstance(raw, Mapping) or not raw:
        raise ValuationError(
            f"{VALUATION_METHODS_YAML}: 缺非空的 {METHOD_ROUTING_KEY!r} 映射 —— "
            "设计未给键名，本模块以该键为唯一候选（键名不符即失败，不静默兜底）"
        )
    routing: dict[str, tuple[str, ...]] = {}
    for model_class, value in raw.items():
        if isinstance(value, str):
            classes = (value,)
        elif isinstance(value, (list, tuple)) and value:
            classes = tuple(str(v) for v in value)
        else:
            raise ValuationError(
                f"{VALUATION_METHODS_YAML}: model_class={model_class!r} 的取值为空或类型非法（{value!r}）"
            )
        routing[str(model_class)] = classes
    return routing


@dataclass(frozen=True)
class MethodRoute:
    """一次方法路由的结果（**带"是否已注册"标注**，`Ch5 §D.1` 末句）。"""

    model_class: str
    method_classes: tuple[str, ...]
    registered: bool
    note: str = ""

    @property
    def method_class(self) -> str:
        """主方法类（列表取首个；`§D.1` 的表里 `hardware` 到多方法，取首个为单位内主方法）。"""
        return self.method_classes[0] if self.method_classes else DEFAULT_METHOD_CLASS


def route_method(model_class: str, routing: Mapping[str, tuple[str, ...]]) -> MethodRoute:
    """把 `business.model_class` 路由到估值方法类（`Ch5 §D.1`）。

    未注册的 `model_class` → `method_class = "generic"` **且 `registered=False` +
    `note`**（`§D.1`："未注册类型归入 generic **并标注**"）。
    """
    if not model_class or model_class == "tbd":
        raise ValuationError(
            "model_class 缺失（'tbd' 亦不可路由）—— Ch5 §D.1 路由需要一个已识别的商业模式"
        )
    classes = routing.get(model_class)
    if classes:
        return MethodRoute(model_class=model_class, method_classes=tuple(classes), registered=True)
    return MethodRoute(
        model_class=model_class,
        method_classes=(DEFAULT_METHOD_CLASS,),
        registered=False,
        note=f"UNREGISTERED_MODEL_CLASS: {model_class!r} 未注册，归入 {DEFAULT_METHOD_CLASS}（Ch5 §D.1）",
    )


# ───────────────────────── 追溯链（`Ch5 §D.2`；复用 forward_closure） ─────────────────────────


@dataclass
class TraceResult:
    """追溯链遍历结果（`Ch5 §D.2`：`formula` + `operands` + `method_version` 可追）。"""

    root_id: str
    reached: tuple[str, ...] = ()
    terminal_refs: tuple[str, ...] = ()
    depth_of: dict[str, int] = field(default_factory=dict)
    truncated: bool = False
    cycle_detected: bool = False
    missing_formula: tuple[str, ...] = ()

    def covers(self, ref: str) -> bool:
        """`ref` 是否在链上（已展开的派生节点 ∪ 终端外部引用）。"""
        return ref in set(self.reached) or ref in set(self.terminal_refs)


def trace_derived_chain(
    root_id: str,
    resolve: Any,
    *,
    max_depth: int | None = None,
    max_nodes: int = 512,
) -> TraceResult:
    """展开 `root_id` 的 operand 链，并**用 `forward_closure` 给权威判定**。

    - `resolve(derived_id) -> DerivedValue | None`：解析器。返回 `None` 表示该引用是
      **终端外部引用**（`claim_id` / baseline 引用 / 原始值引用）—— 链到此为止。
    - 边：`derived_id → 每个 operand`（`kind="operand"`，`source="dependency_edges"`，
      复用图层的既有 `Edge` 与闭包引擎；`Ch5 §J7` 要求可达性深度与 `max_depth` 一致）。
    - 展开用 `seen` 去重（**有环也必然终止**，每个节点只展开一次），节点数超 `max_nodes`
      ⇒ 立刻停并置 `truncated`（不静默：链太深与"链正常"必须可区分）。
    - 深度判定由 `forward_closure` 负责：`truncated=True` 表示"命中 `max_depth` 且仍有
      未展开的下游" ⇒ 链**追不到头**（`§D.2` 的可追溯性不成立）。
    - 节点缺 `formula` → 记进 `missing_formula`（`Ch9 §3.4.4`：必须存公式而非仅结果）。
    """
    from scripts.graph.adjacency import Edge
    from scripts.graph.closure import DEFAULT_MAX_DEPTH, forward_closure

    depth_cap = DEFAULT_MAX_DEPTH if max_depth is None else max_depth
    if depth_cap < 0:
        raise ValuationError(f"max_depth 必须 >= 0，实得 {depth_cap}")

    edges: list[Any] = []
    terminal: set[str] = set()
    missing_formula: set[str] = set()
    seen: set[str] = {root_id}
    queue: deque[str] = deque([root_id])
    node_cap_hit = False
    while queue:
        node_id = queue.popleft()
        node = resolve(node_id)
        if node is None:
            terminal.add(node_id)
            continue
        if not getattr(node, "formula", ""):
            missing_formula.add(node_id)
        for operand in getattr(node, "operands", []) or []:
            edges.append(Edge(node_id, str(operand), "operand", "dependency_edges"))
            if str(operand) not in seen:
                seen.add(str(operand))
                queue.append(str(operand))
        if len(seen) > max_nodes:
            node_cap_hit = True
            break

    result = forward_closure(Path("."), root_id, max_depth=depth_cap, edges=edges)
    return TraceResult(
        root_id=root_id,
        reached=tuple(result.reached),
        terminal_refs=tuple(sorted(terminal)),
        depth_of=dict(result.depth_of),
        truncated=bool(result.truncated) or node_cap_hit,
        cycle_detected=bool(result.cycle_detected),
        missing_formula=tuple(sorted(missing_formula)),
    )


def assert_traceability(
    root_id: str,
    resolve: Any,
    *,
    max_depth: int | None = None,
    required_refs: Sequence[str] = (),
) -> TraceResult:
    """断言 `root_id` 的追溯链可追（`Ch5 §D.2` / `N5.3-02`）。

    任一不成立即 `ValuationError`（**拒绝**，不是 warn）：

    - 链上节点缺 `formula`（`Ch9 §3.4.4`）；
    - 链上出现环（operand 自引用 ⇒ 追不到头）；
    - `truncated`（深度用尽仍未见底 ⇒ 追不到终端输入）；
    - `required_refs`（如第四章的 `driver` / `claim`）**不在**链上（问不到"这个价格区间从哪来"）。
    """
    result = trace_derived_chain(root_id, resolve, max_depth=max_depth)
    if result.missing_formula:
        raise ValuationError(
            f"{root_id}: 追溯链上的 {list(result.missing_formula)} 缺 formula —— "
            "Ch9 §3.4.4 要求存公式而非仅结果"
        )
    if result.cycle_detected:
        raise ValuationError(f"{root_id}: 追溯链存在环（operand 自引用）—— 链追不到头（Ch5 §D.2）")
    if result.truncated:
        raise ValuationError(
            f"{root_id}: 追溯链在 max_depth 内未见底 —— 追不到终端输入（Ch5 §D.2 / J7）"
        )
    uncovered = [ref for ref in required_refs if not result.covers(ref)]
    if uncovered:
        raise ValuationError(
            f"{root_id}: 追溯链上找不到必需引用 {uncovered} —— "
            "问不到'这个价格区间从哪来'就不是可追溯（Ch5 §D.2 / N5.3-02）"
        )
    return result


# ───────────────────────── 估值计算（`Ch5 §D.2` / `§D.3` / `§D.6`） ─────────────────────────


@dataclass(frozen=True)
class BaselineVersionRef:
    """基线版本引用（`Ch5 §D.3` 伪码的 `baseline_version`）。"""

    baseline_id: str
    analyzed_at: datetime | None


@dataclass(frozen=True)
class ValuationParams:
    """估值输入参数（**算术输入**；假设本身由模型/人工给，`Ch5 §B.3`）。"""

    enterprise_value: Decimal
    net_debt: Decimal
    shares_outstanding: Decimal
    low_multiple: Decimal
    high_multiple: Decimal
    operands: tuple[str, ...]
    method_class: str = DEFAULT_METHOD_CLASS
    forecast_assumptions: tuple[str, ...] = ()
    valuation_params: tuple[str, ...] = ()
    probability: Decimal | None = None
    probability_basis_ref: str = ""


def compute_valuation(
    baseline_version: BaselineVersionRef,
    params: ValuationParams,
    *,
    compute_time: datetime | None,
    method_version: str = METHOD_VERSION,
) -> Any:
    """`Ch5 §D.3` 逐字签名的估值计算：**先**顺序断言，**再**算术。

    - 顺序（`§D.3` 第四条规则 / `§D.4` 规则④）：`baseline_version.analyzed_at < compute_time`，
      否则 `OrderViolation`；任一时间缺失 → `MissingInput`（**不得**用"当前时间"兜底）。
    - 算术：**复用** `scripts.compute.valuation.compute_value_per_share_range`
      （`G-06`：本模块不重写算式）。
    - 概率：非空时经 `scenario_guard.assert_probability_has_basis` 校验
      （`§D.6` + `§J9` + B11）。

    返回 `schema.models.Valuation`（`formula_ref` 指向 low 侧的 `DerivedValue`）。
    """
    from scripts.compute.valuation import compute_value_per_share_range
    from schema.models import Valuation, ValuationRange

    from .order_guard import assert_version_order
    from .scenario_guard import assert_probability_has_basis

    subject = baseline_version.baseline_id
    assert_version_order(baseline_version.analyzed_at, compute_time, subject=subject)
    assert compute_time is not None  # assert_version_order 已拒绝 None（Ch5 §D.3）

    assert_probability_has_basis(params.probability, basis_ref=params.probability_basis_ref)

    computed = compute_value_per_share_range(
        params.enterprise_value,
        params.net_debt,
        params.shares_outstanding,
        params.low_multiple,
        params.high_multiple,
        subject=subject,
        operands=params.operands,
        method_version=method_version,
        computed_at=compute_time,
        baseline_analyzed_at=baseline_version.analyzed_at,
        probability=params.probability,
    )
    return Valuation(
        method_class=params.method_class,
        range=ValuationRange(low=computed.low.value, high=computed.high.value),
        probability=params.probability,
        formula_ref=computed.low.derived_id,
        forecast_assumptions=list(params.forecast_assumptions),
        valuation_params=list(params.valuation_params),
    )


# ───────────────────────── 守卫：真源扫描（CLI 承载面） ─────────────────────────

NOTE_NO_BASELINE_ROWS = "NO_BASELINE_ROWS"
TBD_TOKEN = "tbd"


def check(root: str | Path) -> Any:
    """扫描 `facts/baselines.jsonl` 的 `valuation`：追溯链字段必填 + 方法已注册。

    逐项判据（仅在 `valuation.range` **有值**时检查 —— 无区间的估值不是"已算出的估值"）：

    | # | 判据 | 依据 |
    |---|---|---|
    | ① | `formula_ref` 非空且非 `tbd` | `Ch5 §D.2` / `N5.3-02` |
    | ② | `formula_ref` 能解析到 `derived/derived_values.jsonl` 的 `DerivedValue` | `Ch5 §D.2`（追得回公式与操作数） |
    | ③ | `method_class` 非 `tbd`，且 ∈ 路由表（或显式 `generic` 标注） | `Ch5 §D.1` |

    ★ 空样本 → 显式 note（`G-03`）。
    """
    from scripts._common import CheckReport, Violation
    from schema.store import read_records

    root_path = Path(root)
    report = CheckReport(checker="pricelayer_valuation")
    baselines = read_records(root_path, "baselines")
    report.scanned["baselines"] = len(baselines)
    if not baselines:
        report.notes.append(f"{NOTE_NO_BASELINE_ROWS}: facts/baselines.jsonl 无行（非'已验证'）")
        return report

    from scripts.compute.store import read_rows

    derived_ids = {
        str(row.get("derived_id")) for row in read_rows(root_path, "derived_values") if row.get("derived_id")
    }
    report.scanned["derived_values"] = len(derived_ids)

    routing_loaded = True
    routing: dict[str, tuple[str, ...]] = {}
    try:
        routing = load_method_routing(root_path)
    except FileNotFoundError:
        routing_loaded = False
        report.notes.append(
            f"NO_VALUATION_METHODS_RULE: {VALUATION_METHODS_YAML} 不存在 —— "
            "方法注册判据③不可判定（未安装规则时属输入缺口，非'守卫已通过'）"
        )
    report.scanned["routing_model_classes"] = len(routing)

    checked = 0
    for row in baselines:
        baseline_id = str(row.get("baseline_id") or "<no-baseline_id>")
        valuation = row.get("valuation") or {}
        if not isinstance(valuation, Mapping):
            continue
        rng = valuation.get("range") or {}
        bounds = [rng.get("low"), rng.get("high")] if isinstance(rng, Mapping) else []
        if all(b in (None, "") for b in bounds):
            continue  # 无区间的估值 → 未算出，不检（避免把"还没算"判成"算错了"）
        checked += 1
        formula_ref = str(valuation.get("formula_ref") or "")
        if not formula_ref or formula_ref == TBD_TOKEN:
            report.violations.append(
                Violation(
                    "VALUATION-TRACE-MISSING",
                    f"baseline {baseline_id!r}: 有价格区间但 formula_ref 为空/tbd —— "
                    "Ch5 §D.2 / N5.3-02：价格区间必须可反查公式与操作数",
                )
            )
        elif formula_ref not in derived_ids:
            report.violations.append(
                Violation(
                    "VALUATION-TRACE-UNRESOLVED",
                    f"baseline {baseline_id!r}: formula_ref={formula_ref!r} 在 "
                    "derived/derived_values.jsonl 中不存在 —— 追溯链断裂（Ch5 §D.2）",
                )
            )
        method_class = str(valuation.get("method_class") or "")
        if not method_class or method_class == TBD_TOKEN:
            report.violations.append(
                Violation(
                    "VALUATION-METHOD-MISSING",
                    f"baseline {baseline_id!r}: method_class 为空/tbd —— Ch5 §D.1 要求方法可查",
                )
            )
        elif routing_loaded:
            # 已注册的**方法类** = 路由表各 `model_class` 取值（`method_class`）的并集。
            # ★ 不能拿路由表的**键**（那是 `model_class`）去比对 `Valuation.method_class` ——
            #   两者是不同的集合（`Ch5 §D.1`："`method_class → business.model_class` 绑定"）。
            registered_method_classes = {
                method_class for classes in routing.values() for method_class in classes
            } | {DEFAULT_METHOD_CLASS}
            if method_class not in registered_method_classes:
                report.violations.append(
                    Violation(
                        "VALUATION-METHOD-UNREGISTERED",
                        f"baseline {baseline_id!r}: method_class={method_class!r} 不在 "
                        f"{VALUATION_METHODS_YAML} 的注册方法类内，且未标注为 {DEFAULT_METHOD_CLASS} "
                        "（Ch5 §D.1：未注册类型归入 generic **并标注**）",
                    )
                )
    report.scanned["valuations_checked"] = checked
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """CLI：`python system/scripts/pricelayer/valuation.py [code_root]`。"""
    from scripts._common import run_checker

    return run_checker("pricelayer_valuation", check, argv)


if __name__ == "__main__":  # pragma: no cover - CLI 出口
    raise SystemExit(main())
