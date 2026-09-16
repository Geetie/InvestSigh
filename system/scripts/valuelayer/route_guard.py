"""`route_guard.py` —— **混合公司的指标集防串味**（`Ch4 §C`）。

## 设计锚点（逐字）

`Ch4 §C.1`：

```yaml
- metric_set_id: MS-HW-6STAGE
  model_class: hardware
  stages: [order, production_schedule, shipment, acceptance, revenue, collection]
  metrics: [{name, unit, source_class, linked_account}]
  linked_accounts: [revenue, cogs, capex, inventory, receivables, ...]
```

- "`businesses.metric_set_id` 绑定；`business.model_class` 为路由键"；
- "**`business_id → indicator_set` 绑定**：指标**挂在 `business_id`（非 `company_id`）**"。

`Ch4 §C.2`（伪码逐字）：

```python
def validate_binding(business, metric_set):
    if business.model_class != metric_set.model_class:          # ← 外键一致性
        raise MetricSetMismatch(business.business_id, metric_set.metric_set_id)
    # 分部财务独立：指标只能写本业务分部科目，禁止跨业务引用
    for m in metric_set.metrics: assert m.owner_business_id == business.business_id
```

`Ch4 §C.3`：未注册类型归入 `MS-GENERIC` 并显式标注 `unregistered_model_class=true`
（扩展机制 = "**只改 `rules/metric-sets.yaml`**、**不改代码**"，注册表驱动）。

## 字段名的取舍（**不改设计，只登记**）

§C.2 的伪码写 `business.model_class`，而 §B.1 的 schema 块与
`04_.../01_需求拆解.md §4` 的阶段①必填逐字写 **`business_type`**（路由键）。
`schema/models.py::Business` 已按后者落字段（并在 docstring 里登记了这处行文漂移）。
⇒ 本模块**读 `business_type`**，并把 `model_class` 作为**别名**一并接受
（旧数据 / 设计伪码直译的行都能过），两侧永远是同一个值的比较 —— 不引入第二个真源。

## 为什么 `is_primary` / `weight` 这类词一个都不出现

`纪律 7` / `P-09`：参数与排序不得进决策函数。本模块只做**外键一致性**，
不排序、不打分。
"""

from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from scripts._common import CheckReport, Violation, run_checker
from scripts.valuelayer import _rules

#: `Ch4 §C.2` 逐字的异常类型名（保持字面一致，便于按设计名检索）。
MISMATCH_RULE = "Ch4-C2"


class MetricSetMismatch(RuntimeError):
    """`business.model_class` 与 `metric_set.model_class` 不一致（`Ch4 §C.2` 的外键一致性）。

    携带两个 id 而非一段自由文本：调用方（与测试）据此可**结构化**断言是哪一处串味。
    """

    def __init__(self, business_id: str, metric_set_id: str, *, detail: str = "") -> None:
        self.business_id = business_id
        self.metric_set_id = metric_set_id
        message = (
            f"MetricSetMismatch: business {business_id!r} 绑定了异类指标集 {metric_set_id!r}"
            "（Ch4 §C.2：business.model_class 必须等于 metric_set.model_class）"
        )
        if detail:
            message += f" —— {detail}"
        super().__init__(message)


class CrossBusinessMetric(MetricSetMismatch):
    """指标挂在**别的业务**上（`Ch4 §C.2`："指标只能写本业务分部科目，禁止跨业务引用"）。

    继承 `MetricSetMismatch`：设计把两种串味都归在同一个异常名下（伪码里第二条是
    `assert`，本实现给它一个**可结构化断言**的子类，语义不减、只增可定位性）。
    """

    def __init__(self, business_id: str, metric_set_id: str, owner_business_id: str, metric_name: str) -> None:
        self.owner_business_id = owner_business_id
        self.metric_name = metric_name
        super().__init__(
            business_id,
            metric_set_id,
            detail=(
                f"指标 {metric_name!r} 的 owner_business_id={owner_business_id!r} "
                f"≠ business_id={business_id!r}"
            ),
        )


# ───────────────────────────── 注册表对象（pydantic-free） ─────────────────────────────
#
# ★ 为什么不复用 `schema/models.py` 的 pydantic 模型：`metric-sets.yaml` 是**规则文件**，
#   其结构由 §C.1 / §C.3 定义（"改文件即扩展"），并非 `facts/` 真源对象。
#   为它拉 pydantic 只会让 `pre-commit` 路径多付 ≈0.3s（`P-03`/`P-05`）。
#   而 `facts/businesses.jsonl` 侧仍由 `schema.store` 校验（**唯一真源**不动）。


@dataclass(frozen=True)
class Metric:
    """指标集里的一条指标（`Ch4 §C.1`：`{name, unit, source_class, linked_account}` + `owner_business_id`）。

    ★ `owner_business_id` 是 §C.2 伪码直接读的字段（`m.owner_business_id`）；
      §C.1 的 yaml 块没把它列进 `metrics` 的键里，但 §C.2 的检查以它为判据
      ⇒ 它是**契约的一部分**，此处显式要求（缺则见 `validate_binding` 的 `OWNER_MISSING` 分支）。
    """

    name: str
    unit: str = ""
    source_class: str = ""
    linked_account: str = ""
    owner_business_id: str | None = None


@dataclass(frozen=True)
class MetricSet:
    """一个指标集（`Ch4 §C.1` 的一段 yaml）。"""

    metric_set_id: str
    model_class: str
    stages: tuple[str, ...] = ()
    metrics: tuple[Metric, ...] = ()
    linked_accounts: tuple[str, ...] = ()
    currency: str = ""


def _as_str_list(value: Any) -> tuple[str, ...]:
    """转成字符串元组；`None` / **`tbd`** / 空 ⇒ `()`（=「未声明」，不是"声明了一个叫 tbd 的值"）。

    ★ 为什么必须显式处理 `tbd`：13-R 转写 `rules/metric-sets.yaml` 时，设计**没给值**的字段
      如实写了 `tbd`（如 `MS-GENERIC` 的 `stages: tbd`、`MS-CLOUD-5STAGE` 的 `linked_accounts: tbd`）。
      若照字符串处理，`stages: tbd` 会变成**一个名为 `tbd` 的段名** ⇒ 真实转化链的段名
      全被判成"不在注册表里"⇒ 假红；（`metrics: tbd` 更会逐**字符**迭代而直接抛异常）。
      故 `tbd` 一律读作「**未声明**」，由各检查按 `G-03` 记"不可核"。
    """
    if _rules.is_undecided(value):
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value)
    return (str(value),)


def metric_set_from_row(row: Mapping[str, Any]) -> MetricSet:
    """把 `rules/metric-sets.yaml` 的一项转成 `MetricSet`（缺必填键 ⇒ `KeyError`，响亮）。"""
    metrics: list[Metric] = []
    raw_metrics = row.get("metrics")
    if not _rules.is_undecided(raw_metrics):
        if not isinstance(raw_metrics, (list, tuple)):
            raise ValueError(
                f"metric_set {row.get('metric_set_id')!r} 的 metrics 不是列表（也不是 `tbd`）："
                f"{type(raw_metrics).__name__}"
            )
        for m in raw_metrics:
            if not isinstance(m, Mapping):
                raise ValueError(f"metric_set {row.get('metric_set_id')!r} 的 metrics 项不是 mapping: {m!r}")
            metrics.append(
                Metric(
                    name=str(m.get("name")),
                    unit=str(m.get("unit") or ""),
                    source_class=str(m.get("source_class") or ""),
                    linked_account=str(m.get("linked_account") or ""),
                    owner_business_id=(
                        None if m.get("owner_business_id") is None else str(m["owner_business_id"])
                    ),
                )
            )
    return MetricSet(
        metric_set_id=str(row["metric_set_id"]),
        model_class=str(row["model_class"]),
        stages=_as_str_list(row.get("stages")),
        metrics=tuple(metrics),
        linked_accounts=_as_str_list(row.get("linked_accounts")),
        currency=str(row.get("currency") or "") if not _rules.is_undecided(row.get("currency")) else "",
    )



def registry(root: str | Path) -> dict[str, MetricSet]:
    """`metric_set_id → MetricSet`（`rules/metric-sets.yaml`；`Ch4 §C.1`）。"""
    out: dict[str, MetricSet] = {}
    for row in _rules.metric_sets(root):
        ms = metric_set_from_row(row)
        if ms.metric_set_id in out:
            raise ValueError(f"{_rules.METRIC_SETS_RELPATH} 出现重复 metric_set_id: {ms.metric_set_id!r}")
        out[ms.metric_set_id] = ms
    return out


# ───────────────────────────────── 路由与绑定校验 ─────────────────────────────────

def _field(obj: Any, *names: str) -> Any:
    """按顺序取第一个**存在**的字段（dict 与对象两种载体都支持）。

    ★ 存在的判据是"键在 / 属性在"，**不是"值非空"** —— 否则"值为空"会被静默
      降级成"字段不存在"，两者在本项目里必须可区分。
    """
    for name in names:
        if isinstance(obj, Mapping):
            if name in obj:
                return obj[name]
        elif hasattr(obj, name):
            return getattr(obj, name)
    return None


def business_model_class(business: Any) -> str:
    """取路由键（`business_type`；兼容 §C.2 伪码写的 `model_class`，见模块 docstring）。"""
    value = _field(business, "business_type", "model_class")
    return "" if value is None else str(value)


def resolve_metric_set(business: Any, reg: Mapping[str, MetricSet]) -> tuple[MetricSet, bool]:
    """按 `model_class` 路由到指标集（`Ch4 §C.1` / `§C.3`）。

    返回 `(metric_set, unregistered)`：
    - 命中注册表 ⇒ `(该指标集, False)`；
    - **未注册类型** ⇒ `(MS-GENERIC, True)`（§C.3 逐字：归入 `MS-GENERIC` 并显式标注
      `unregistered_model_class=true`）。

    ★ 为什么"未注册"**不抛异常**：§C.3 把它定义为**正常路径**（"未注册类型 | 归入 `MS-GENERIC`
      并显式标注"），抛异常会让新业务类型无法建模 —— 那是把扩展机制关掉。
      真正要拦的是 `MS-GENERIC` **不存在**这种情况（注册表缺兜底 ⇒ 响亮失败）。
    """
    model_class = business_model_class(business)
    for ms in reg.values():
        if ms.model_class == model_class:
            return ms, False
    generic = reg.get(_rules.GENERIC_METRIC_SET_ID)
    if generic is None:
        raise _rules.MissingRuleInput(
            f"{_rules.METRIC_SETS_RELPATH} 缺兜底指标集 {_rules.GENERIC_METRIC_SET_ID}"
            f"（Ch4 §C.3 要求未注册的 model_class={model_class!r} 归入它并标注）"
        )
    return generic, True


#: §C.2 第二条检查的失败种类（供结构化断言；不用自由文本猜）。
OWNER_MISSING = "owner_business_id_missing"
OWNER_CROSS = "owner_business_id_cross"


def validate_binding(
    business: Any,
    metric_set: MetricSet,
    *,
    require_owner: bool | None = None,
    reg: Mapping[str, MetricSet] | None = None,
) -> list[tuple[str, str]]:
    """`Ch4 §C.2` 的伪码逐条落地。**返回违例清单**（空 = 通过）。

    ```
    if business.model_class != metric_set.model_class: raise MetricSetMismatch(...)
    for m in metric_set.metrics: assert m.owner_business_id == business.business_id
    ```

    ★ 为什么返回清单而不是只抛第一个异常：设计伪码用 `raise`/`assert` 表达**两条**检查，
      而门禁需要把**每一条**违例都报出来（"报一条就停"会让修完一条后又红一条，
      定位成本叠加）。故这里把两条都算出来，再**统一**用一个 `MetricSetMismatch`
      抛给需要异常语义的调用方（`validate_binding_or_raise`）。

    ## `reg`：`§C.2` 与 `§C.3` 的**冲突**及其收口（**本实现的裁定，已登记待需求方复核**）

    `§C.2` 的伪码用 `business.model_class != metric_set.model_class` 判外键一致性；
    `§C.3` 又规定**未注册**类型必须归入 `MS-GENERIC`（其 `model_class` 恒为 `generic`）。
    两者直接叠加 ⇒ 任何未注册类型都**永远**判不一致 ⇒ `§C.3` 定义的**正常路径恒红**
    （`G-01`：恒红的门禁一定会被关掉）。

    故本实现把这条判据写成**它的本意**而非字面：*"你绑定的指标集，必须正是你这个业务
    路由到的那一个"* ——

    - `reg` 给定（门禁路径）⇒ 判据 = **路由相等**（`resolve_metric_set` 的结果 == 绑定的 id）。
      这条比字面比较**更强**：未注册类型绑 `MS-GENERIC` 通过（`§C.3` 的正常路径），
      而"注册类型却绑 `MS-GENERIC`"会被拦下（字面比较放它过去 —— 因为 `generic` 谁都能匹配）。
    - `reg` 不给（纯函数调用）⇒ 退回 `§C.2` 伪码的字面比较（模型类相等）。

    ## `require_owner`（设计未写、由本实现显式化的取舍，已登记待裁定）

    §C.1 的指标集是**注册表**（`metrics: [{name, unit, source_class, linked_account}]`，
    **不含** `owner_business_id`），而 §C.2 又要求 `m.owner_business_id == business.business_id`
    —— 两条放在一起意味着"每个指标集只服务一个业务"。这两种读法（模板 vs 按业务实例化）
    设计**没有裁定**（见报告「剩余不确定性与缺口」）。

    为避免"任何按 §C.1 逐字写的注册表都让本守卫恒红"（**恒红的门禁一定会被关掉**，
    `G-01`），本函数取如下**可判定**折中：

    - 该指标集里**有**任一条指标声明了 `owner_business_id` ⇒ 视为"该指标集声明了归属"
      ⇒ 对**全部**指标严格判等（缺声明的记 `OWNER_MISSING`）；
    - **一条都没声明** ⇒ 视为"模板式注册表，归属未在注册表声明"
      ⇒ 跳过归属判等，但由 `check()` 记 `scanned` 计数 + 显式 note
      （`G-03`：不可核的东西**不得**被当成已核）。
    """
    business_id = str(_field(business, "business_id") or "")
    out: list[tuple[str, str]] = []
    if reg is not None:
        routed, _unregistered = resolve_metric_set(business, reg)
        if routed.metric_set_id != metric_set.metric_set_id:
            out.append(
                (
                    MISMATCH_RULE,
                    f"{business_id} 的路由结果是 {routed.metric_set_id!r}，却绑定了"
                    f" {metric_set.metric_set_id!r}（Ch4 §C.2 外键一致性：绑定的必须正是路由到的那一个；"
                    "§C.3 的 MS-GENERIC 兜底使'字面等 model_class'不适用）",
                )
            )
    elif business_model_class(business) != metric_set.model_class:
        out.append(
            (
                MISMATCH_RULE,
                f"{business_id} 的 model_class={business_model_class(business)!r} "
                f"≠ 指标集 {metric_set.metric_set_id} 的 model_class={metric_set.model_class!r}",
            )
        )
    owner_declared = any(m.owner_business_id is not None for m in metric_set.metrics)
    if require_owner is None:
        require_owner = owner_declared
    if not require_owner:
        return out
    for m in metric_set.metrics:
        if m.owner_business_id is None:
            out.append(
                (
                    OWNER_MISSING,
                    f"指标 {m.name!r}（{metric_set.metric_set_id}）缺 owner_business_id —— "
                    "该指标集已有其它指标声明归属，故本条缺失即无法证明'指标挂在本业务上'（Ch4 §C.2）",
                )
            )
            continue
        if m.owner_business_id != business_id:
            out.append(
                (
                    OWNER_CROSS,
                    f"指标 {m.name!r} 的 owner_business_id={m.owner_business_id!r} "
                    f"≠ business_id={business_id!r}（跨业务引用被拒）",
                )
            )
    return out


def validate_binding_or_raise(
    business: Any,
    metric_set: MetricSet,
    *,
    require_owner: bool | None = None,
    reg: Mapping[str, MetricSet] | None = None,
) -> None:
    """`Ch4 §C.2` 的**异常语义**入口（伪码用 `raise`；需要单测"会抛"的调用方用它）。"""
    violations = validate_binding(business, metric_set, require_owner=require_owner, reg=reg)
    if not violations:
        return
    business_id = str(_field(business, "business_id") or "")
    kind, detail = violations[0]
    if kind in (OWNER_MISSING, OWNER_CROSS):
        # ★ `owner_business_id` / `metric_name` **必须从被检集合里取**（不是从 `business` 取）——
        #   否则异常携带的"违规归属"就是本业务的 id，等于把**违例的地址**报成了自己的地址，
        #   调用方（与单测）无法据此定位是哪一条指标串了味。
        offender = next(
            (
                m
                for m in metric_set.metrics
                if m.owner_business_id is not None and m.owner_business_id != business_id
            ),
            None,
        )
        raise CrossBusinessMetric(
            business_id,
            metric_set.metric_set_id,
            owner_business_id=(offender.owner_business_id if offender is not None else ""),
            metric_name=(offender.name if offender is not None else "<未声明归属的指标>"),
        )
    raise MetricSetMismatch(business_id, metric_set.metric_set_id, detail=detail)


# ─────────────────────────── 转化链路分段 → 指标集 stages 的序一致性 ───────────────────────────
#
# `N4.1-07 ~ N4.1-09` 的**验收方式**逐字："硬件六段呈现且**不跳级**" / "云五段呈现" /
# "软件五段呈现"。段名由注册表驱动（`§C.1`），故这条检查**只读注册表**、不写死任何段名
# （`R-06` ①：禁关键词/名单式判据）。
#
# 判据（可判定 + 穷尽）：把 `conversion_chain` 各段的 `stage` 映射到注册表 `stages` 的下标，
#   ① 出现注册表里没有的段名 → 违例（**不在名单内**即拒，allowlist 式）；
#   ② 下标**必须严格递增**（顺序即 §B.1"获取→交付→使用→变现"的实例化顺序）；
#   ③ 两个已出现下标之间**不得有空洞**（"不跳级"）。
# 每条链的每个段只落入上述三类的至多一种判定，无第三态。

def stage_indices(metric_set: MetricSet, chain: Any) -> list[int]:
    """把一条 `conversion_chain` 的段名映射成注册表下标；**未注册段名 → `-1`**。"""
    order = {name: idx for idx, name in enumerate(metric_set.stages)}
    out: list[int] = []
    for seg in chain or []:
        stage = _field(seg, "stage")
        out.append(order.get(str(stage), -1))
    return out


def stage_sequence_violations(metric_set: MetricSet, chain: Any) -> list[tuple[str, str]]:
    """`N4.1-07~09` 的"不跳级"检查（见上方判据说明）。返回 `(kind, detail)` 清单。"""
    indices = stage_indices(metric_set, chain)
    out: list[tuple[str, str]] = []
    unregistered = [i for i, idx in enumerate(indices) if idx < 0]
    if unregistered:
        names = [
            str(_field((chain or [])[i], "stage"))
            for i in unregistered
        ]
        out.append(
            (
                "stage_unregistered",
                f"conversion_chain 出现 {metric_set.metric_set_id} 的 stages 里没有的段名 {names} "
                "—— 段名由 rules/metric-sets.yaml 驱动（Ch4 §C.1/§C.3）",
            )
        )
    known = [idx for idx in indices if idx >= 0]
    if known != sorted(known) or len(set(known)) != len(known):
        out.append(
            (
                "stage_order",
                f"conversion_chain 的段序 {known} 未严格递增（注册表序 = {list(metric_set.stages)}）"
                "—— 顺序即 Ch4 §B.1 的'获取→交付→使用→变现'实例化顺序",
            )
        )
    if known:
        span = set(range(min(known), max(known) + 1))
        holes = sorted(span - set(known))
        if holes:
            names = [metric_set.stages[i] for i in holes]
            out.append(
                (
                    "stage_gap",
                    f"conversion_chain 跳级：{names}（下标 {holes}）缺失，"
                    "而 N4.1-07 的验收是'六段呈现且**不跳级**'",
                )
            )
    return out


# ───────────────────────────────────── 门禁入口 ─────────────────────────────────────

def check(root: Path) -> CheckReport:
    """对**真源** `facts/businesses.jsonl` 逐业务做绑定 + 序一致性检查（`Ch4 §C`）。

    - 真源**缺失** ⇒ 抛 `FileNotFoundError`（经 `run_checker` 折叠为 `exit 2`）；
    - 真源**存在但为空** ⇒ 显式 `NO_BUSINESSES` note + `exit 0`（`G-03`：无被检对象
      ≠ 已验证，但也不是违例 —— 与 `locator_check` 的 `NO_CLAIMS` 同例）；
    - `MS-GENERIC` 兜底命中 ⇒ 逐条计入 `scanned` 并在 note 里点名（§C.3 要求**显式标注**）。
    """
    from schema.store import read_records, truth_source_status

    report = CheckReport(checker="valuelayer_route_guard")
    status = truth_source_status(root, "businesses")
    if status == "missing":
        raise FileNotFoundError(
            f"缺少真源 facts/businesses.jsonl（Ch4 §B.1 新表，属 22 表之一）—— 结构性违例"
        )
    businesses = read_records(root, "businesses")
    reg = registry(root)
    report.scanned["metric_sets"] = len(reg)
    report.scanned["businesses"] = len(businesses)

    # ★ 兜底指标集 id 的**漂移核对**（`G-06`）：`MS-GENERIC` 在代码里是个常量，
    #   而它的真源是 `rules/metric-sets.yaml::routing.fallback_metric_set_id`（`Ch4 §C.3`）。
    #   与其在代码里"再声明一次"（第二真源），不如**在运行时核对**：不一致即报违例 ——
    #   这样"只改规则文件、不改代码"的扩展机制（§C.3）不会被一个陈旧常量悄悄挡住。
    fallback_id = str(_rules.metric_set_routing(root).get("fallback_metric_set_id") or "")
    report.scanned["fallback_metric_set_id"] = 1 if fallback_id == _rules.GENERIC_METRIC_SET_ID else 0
    if fallback_id != _rules.GENERIC_METRIC_SET_ID:
        report.violations.append(
            Violation(
                MISMATCH_RULE,
                f"{_rules.METRIC_SETS_RELPATH}::routing.fallback_metric_set_id={fallback_id!r} 与"
                f" route_guard 的常量 {_rules.GENERIC_METRIC_SET_ID!r} 不一致"
                "（Ch4 §C.3：漂移即须显式可见，不得靠陈旧常量静默兜底）",
                _rules.METRIC_SETS_RELPATH,
            )
        )
    if not businesses:
        report.notes.append(
            "NO_BUSINESSES: facts/businesses.jsonl 存在但为空 —— 无被检对象"
            "（真空成立，**不是**'已验证'，G-03）；断言已就绪，待真实业务数据"
        )
        return report

    unregistered = 0
    owner_declared_sets = 0
    stage_not_evaluable = 0
    for biz in businesses:
        business_id = str(biz.get("business_id") or "<unnamed>")
        bound_id = str(biz.get("metric_set_id") or "")
        if bound_id not in reg:
            report.violations.append(
                Violation(
                    MISMATCH_RULE,
                    f"{business_id} 的 metric_set_id={bound_id!r} 不在 {_rules.METRIC_SETS_RELPATH} 注册表里 "
                    "（Ch4 §C.1：businesses.metric_set_id 必须绑定注册表项）",
                    "facts/businesses.jsonl",
                )
            )
            continue
        metric_set = reg[bound_id]
        if any(m.owner_business_id is not None for m in metric_set.metrics):
            owner_declared_sets += 1
        # 路由键一致性：**绑定的指标集必须正是路由到的那一个**（`§C.2` 外键一致性；
        # 用 `reg` 判据而非字面比 model_class —— 理由见 `validate_binding` 的 docstring）。
        for kind, detail in validate_binding(biz, metric_set, reg=reg):
            report.violations.append(
                Violation(MISMATCH_RULE if kind == MISMATCH_RULE else kind, f"{business_id}: {detail}",
                          "facts/businesses.jsonl")
            )
        # §C.3：未注册类型必须显式标注（不是靠"没用 MS-GENERIC"猜）
        resolved, is_unregistered = resolve_metric_set(biz, reg)
        flagged = bool(biz.get("unregistered_model_class"))
        if is_unregistered != flagged:
            report.violations.append(
                Violation(
                    MISMATCH_RULE,
                    f"{business_id}: 路由判定 unregistered={is_unregistered} 与"
                    f" unregistered_model_class={flagged} 不一致"
                    "（Ch4 §C.3：未注册类型须归入 MS-GENERIC **并显式标注**）",
                    "facts/businesses.jsonl",
                )
            )
        if is_unregistered:
            unregistered += 1
        mechanism = biz.get("mechanism") or {}
        chain = mechanism.get("conversion_chain")
        if metric_set.stages:
            for kind, detail in stage_sequence_violations(metric_set, chain):
                report.violations.append(
                    Violation(kind, f"{business_id}: {detail}", "facts/businesses.jsonl")
                )
        elif chain:
            # ★ `G-03`：段序判据的**参照序列**就是注册表的 `stages`。未声明 `stages` 的指标集
            #   （`MS-GENERIC` 就是如此 —— `§C.3` 的兜底集没有段词汇表）⇒ "不跳级"**不可核**。
            #   若把它当违例，则 `§C.3` 的**正常路径恒红**（恒红的门禁一定会被关掉，`G-01`）；
            #   若静默跳过，则"没核"会被读成"核过且没问题"。故两件都不做，改为**显式计数 + note**。
            stage_not_evaluable += 1
    report.scanned["unregistered_model_class"] = unregistered
    report.scanned["metric_sets_with_owner_declared"] = owner_declared_sets
    report.scanned["stage_sequence_not_evaluable"] = stage_not_evaluable
    if stage_not_evaluable:
        report.notes.append(
            f"NO_STAGE_VOCABULARY: {stage_not_evaluable} 个业务绑定的指标集**未声明** stages"
            "（如 §C.3 的兜底集）⇒ 段序（`N4.1-07` 的'不跳级'）**不可核**"
            "（不可核 ≠ 已核、也 ≠ 违例，G-03）"
        )
    if owner_declared_sets < len(businesses):
        report.notes.append(
            f"OWNER_NOT_DECLARED: {len(businesses) - owner_declared_sets} 个业务绑定的指标集"
            "在注册表里**未声明** metric.owner_business_id ⇒ 该指标集的'跨业务引用'检查**不可核**"
            "（不可核 ≠ 已核，G-03）；是否要求注册表逐条声明归属属 Ch4 §C.1 与 §C.2 的读法歧义，"
            "已登记待裁定"
        )
    if unregistered:
        report.notes.append(
            f"unregistered_model_class={unregistered}：{unregistered} 个业务的路由键未在注册表出现，"
            f"已归入 {_rules.GENERIC_METRIC_SET_ID}（Ch4 §C.3）—— 计数不为 0 即须显式可见"
        )
    return report


if __name__ == "__main__":
    import sys

    sys.exit(run_checker("valuelayer_route_guard.py", check))
