"""`Ch4 §C` —— 指标集**绑定防串味** + `§C.3` 兜底路由 + `N4.1-07~09` 不跳级（逐条正反用例）。

设计锚点（逐字）：

```python
def validate_binding(business, metric_set):
    if business.model_class != metric_set.model_class:          # ← 外键一致性
        raise MetricSetMismatch(business.business_id, metric_set.metric_set_id)
    # 分部财务独立：指标只能写本业务分部科目，禁止跨业务引用
    for m in metric_set.metrics: assert m.owner_business_id == business.business_id
```

★ 本文件专门守**混合公司**这一幕（`Ch4 §C.1` 的三个指标集就是为它设的）：
  一家公司可以同时有云业务与软件业务，**各自的指标集不得互相引用**。
  故"防串味"的正向断言不是"没抛异常"，而是"两个业务各自路由到**不同**的指标集，
  且把对方的指标集绑过来会**当场被拒**"——否则"防串味"无法与"什么都没查"区分（`G-03`）。

★ 夹具用量（`P-05` 成本账，同 `test_completeness.py`）：逻辑用例全部用**内存**的
  `MetricSet` / `Metric`；只有"注册表从 `rules/metric-sets.yaml` 读"与 CLI 退出码用例
  才用 `code_root`。
"""

from __future__ import annotations

import pytest

from conftest import run_gate_inproc
from scripts.valuelayer import _rules
from scripts.valuelayer.route_guard import (
    MISMATCH_RULE,
    OWNER_CROSS,
    OWNER_MISSING,
    CrossBusinessMetric,
    Metric,
    MetricSet,
    MetricSetMismatch,
    business_model_class,
    metric_set_from_row,
    registry,
    resolve_metric_set,
    stage_indices,
    stage_sequence_violations,
    validate_binding,
    validate_binding_or_raise,
)
from conftest import SYSTEM_ROOT
from _fixtures import METRIC_SETS, business, write_jsonl, write_rules

CHECKER = "scripts/valuelayer/route_guard.py"

HW = MetricSet(
    metric_set_id="MS-HW-6STAGE",
    model_class="hardware",
    stages=("order", "production_schedule", "shipment", "acceptance", "revenue", "collection"),
    metrics=(
        Metric("order_backlog", linked_account="revenue", owner_business_id="BIZ-HW"),
    ),
    linked_accounts=("revenue", "cogs", "capex", "inventory", "receivables"),
)
CLOUD = MetricSet(
    metric_set_id="MS-CLOUD-5STAGE",
    model_class="cloud",
    stages=("contract", "energized", "online", "utilization", "billing"),
    metrics=(Metric("energized_mw", unit="mw", owner_business_id="BIZ-CLOUD"),),
)
SW = MetricSet(
    metric_set_id="MS-SW-5STAGE",
    model_class="software",
    stages=("usage", "paid", "renewal", "retention", "upsell"),
    metrics=(),
)
GENERIC = MetricSet(metric_set_id="MS-GENERIC", model_class="generic")


def _reg() -> dict[str, MetricSet]:
    return {ms.metric_set_id: ms for ms in (HW, CLOUD, SW, GENERIC)}


# ───────────────────────── §C.2 外键一致性（正向） ─────────────────────────


def test_hardware_business_binds_to_the_hardware_metric_set() -> None:
    violations = validate_binding(business("BIZ-HW", business_type="hardware"), HW)
    assert violations == []


def test_metric_set_mismatch_is_reported_with_both_ids() -> None:
    """★ 违例必须带**两个 id**（`business_id` / `metric_set_id`）—— 否则无法定位是哪一处串味。"""
    violations = validate_binding(business("BIZ-HW", business_type="hardware"), CLOUD)
    assert [kind for kind, _ in violations][0] == MISMATCH_RULE
    with pytest.raises(MetricSetMismatch) as excinfo:
        validate_binding_or_raise(business("BIZ-HW", business_type="hardware"), CLOUD)
    assert excinfo.value.business_id == "BIZ-HW"
    assert excinfo.value.metric_set_id == "MS-CLOUD-5STAGE"


def test_business_model_class_accepts_the_design_pseudocode_alias() -> None:
    """§C.2 伪码写 `business.model_class`，§B.1 的落位字段是 `business_type` ⇒ 两者都接受。

    ★ 这是**同一处漂移**的两侧，读哪一个都是同一个值；不接受别名会让"按伪码直译的行"判不了。
    """
    assert business_model_class({"business_type": "cloud"}) == "cloud"
    assert business_model_class({"model_class": "cloud"}) == "cloud"


# ───────────────────── §C.2 防串味（混合公司这一幕） ─────────────────────


def test_mixed_company_routes_each_business_to_its_own_metric_set() -> None:
    """★ 混合公司（云 + 软件，`§C.1` 的场景）：各自路由到自己的指标集，**互不串味**。"""
    reg = _reg()
    cloud_biz = business("BIZ-CLOUD", business_type="cloud", metric_set_id="MS-CLOUD-5STAGE")
    sw_biz = business("BIZ-SW", business_type="software", metric_set_id="MS-SW-5STAGE")

    cloud_set, cloud_unregistered = resolve_metric_set(cloud_biz, reg)
    sw_set, sw_unregistered = resolve_metric_set(sw_biz, reg)

    assert cloud_set.metric_set_id == "MS-CLOUD-5STAGE" and not cloud_unregistered
    assert sw_set.metric_set_id == "MS-SW-5STAGE" and not sw_unregistered
    # 两个业务的绑定各自成立
    assert validate_binding(cloud_biz, cloud_set) == []
    assert validate_binding(sw_biz, sw_set) == []
    # ★ 关键：把云业务的指标集绑给软件业务 ⇒ 当场被拒（否则"防串味"不可见）
    assert validate_binding(sw_biz, cloud_set) != []


def test_metrics_of_one_set_never_appear_in_another() -> None:
    """两套指标集的指标名**不相交** —— 这是 §C.1 分设三个指标集的直接后果。"""
    assert {m.name for m in HW.metrics} & {m.name for m in CLOUD.metrics} == set()
    assert {m.name for m in CLOUD.metrics} & {m.name for m in SW.metrics} == set()


# ───────────────────── §C.2 禁止跨业务引用指标（第二个判据） ─────────────────────


def test_metric_owner_on_another_business_is_rejected() -> None:
    """指标挂在**别的**业务上 ⇒ `OWNER_CROSS`（`Ch4 §C.2`：指标只能写本业务分部科目）。"""
    cross = MetricSet(
        metric_set_id="MS-HW-6STAGE",
        model_class="hardware",
        metrics=(Metric("order_backlog", owner_business_id="BIZ-OTHER"),),
    )
    violations = validate_binding(business("BIZ-HW", business_type="hardware"), cross)
    assert [kind for kind, _ in violations] == [OWNER_CROSS]
    with pytest.raises(CrossBusinessMetric) as excinfo:
        validate_binding_or_raise(business("BIZ-HW", business_type="hardware"), cross)
    assert excinfo.value.owner_business_id == "BIZ-OTHER"


def test_metric_without_owner_is_rejected_when_the_set_declares_owners_elsewhere() -> None:
    """★ 同一指标集里已有指标声明归属 ⇒ 缺声明的那条**无法证明**"挂在本业务上" ⇒ 违例。

    ★ 为什么缺声明也算违例（而不是跳过）：`§C.2` 的判据是 `m.owner_business_id == business.business_id`；
      字段缺失时这个等式的**左值未知**，跳过等于把"没声明"当"声明对了"（`G-03` 同族）。
    """
    partial = MetricSet(
        metric_set_id="MS-HW-6STAGE",
        model_class="hardware",
        metrics=(
            Metric("order_backlog", owner_business_id="BIZ-HW"),
            Metric("shipment_units"),  # 缺 owner_business_id
        ),
    )
    violations = validate_binding(business("BIZ-HW", business_type="hardware"), partial)
    assert [kind for kind, _ in violations] == [OWNER_MISSING]


def test_owner_equality_is_skipped_when_the_registry_declares_no_owner_at_all() -> None:
    """**已登记的取舍**（设计未裁定，见报告「剩余不确定性与缺口」）：

    `§C.1` 的注册表 yaml 里 `metrics` **不含** `owner_business_id`，而 `§C.2` 又要求逐条判等 ——
    两种读法（注册表是**模板** vs 注册表**按业务实例化**）设计没裁定。
    本实现取：一条都没声明 ⇒ 视为模板式注册表 ⇒ 跳过归属判等（否则任何按 §C.1 逐字写的
    注册表都让守卫**恒红**，而恒红的门禁一定会被关掉，`G-01`）；但该"不可核"由 `check()`
    记 `OWNER_NOT_DECLARED` note + 计数，**不得**被读成"已核"（`G-03`）。
    """
    template = MetricSet("MS-SW-5STAGE", "software", metrics=(Metric("seats"), Metric("arr")))
    assert validate_binding(business("BIZ-SW", business_type="software"), template) == []


def test_owner_check_can_be_forced_even_on_a_template_registry() -> None:
    """`require_owner=True` ⇒ 即使注册表是模板式也逐条判等（给"要求实例化"的调用方留口）。"""
    template = MetricSet("MS-SW-5STAGE", "software", metrics=(Metric("seats"),))
    violations = validate_binding(
        business("BIZ-SW", business_type="software"), template, require_owner=True
    )
    assert [kind for kind, _ in violations] == [OWNER_MISSING]


# ───────────────────── §C.3 未注册类型 → MS-GENERIC 兜底 ─────────────────────


def test_unregistered_model_class_routes_to_generic_and_is_flagged() -> None:
    """`§C.3` 逐字：未注册类型归入 `MS-GENERIC` 并**显式标注** `unregistered_model_class=true`。"""
    ms, unregistered = resolve_metric_set(
        business("BIZ-NEW", business_type="robotics", metric_set_id="MS-GENERIC"), _reg()
    )
    assert ms.metric_set_id == _rules.GENERIC_METRIC_SET_ID
    assert unregistered is True


def test_missing_generic_set_is_a_loud_input_error() -> None:
    """注册表缺兜底 `MS-GENERIC` ⇒ **响亮失败**（`MissingRuleInput`，经 `run_checker` 折叠为 `exit 2`）。

    ★ 为什么这一条必须响亮：`§C.3` 把"未注册"定义为**正常路径**，所以真正要拦的是
      "兜底本身没装"——那是规则文件缺项，属**输入异常**，不得与"数据不达标"混为一谈。
    """
    with pytest.raises(_rules.MissingRuleInput):
        resolve_metric_set(business("BIZ-NEW", business_type="robotics"), {"MS-HW-6STAGE": HW})


def test_generic_fallback_binding_is_not_a_mismatch() -> None:
    """★ `§C.2` × `§C.3` 的**冲突**收口：未注册类型绑 `MS-GENERIC` 必须**通过**。

    `§C.2` 伪码比的是 `model_class` 字面相等，而 `MS-GENERIC` 的 `model_class` 恒为 `generic`
    ⇒ 字面比较下"未注册类型"**永远**判不一致 ⇒ `§C.3` 定义的正常路径**恒红**。
    传入 `reg` 后判据改为**路由相等**（绑定的必须正是路由到的那一个）⇒ 未注册类型正常通过。
    """
    new_biz = business("BIZ-NEW", business_type="robotics", metric_set_id="MS-GENERIC")
    assert validate_binding(new_biz, GENERIC, reg=_reg()) == []


def test_registered_class_bound_to_generic_is_still_caught() -> None:
    """★ 反向对照（证明上一条的放宽**没有开洞**）：注册类型（cloud）却绑 `MS-GENERIC` ⇒ 必红。

    `generic` 这个 `model_class` 与任何字面比较都能"碰上"，故字面判据在这里**放行**；
      路由判据（`cloud` → `MS-CLOUD-5STAGE` ≠ `MS-GENERIC`）把它拦下。
    """
    cloud_biz = business("BIZ-CLOUD", business_type="cloud", metric_set_id="MS-GENERIC")
    violations = validate_binding(cloud_biz, GENERIC, reg=_reg())
    assert [kind for kind, _ in violations] == [MISMATCH_RULE]


# ───────────────────── N4.1-07~09：段序（"不跳级"） ─────────────────────


def test_stage_indices_maps_registered_names() -> None:
    chain = [{"stage": s} for s in ("order", "production_schedule", "shipment")]
    assert stage_indices(HW, chain) == [0, 1, 2]


def test_stage_sequence_accepts_a_registered_contiguous_chain() -> None:
    chain = [{"stage": s} for s in ("order", "production_schedule", "shipment")]
    assert stage_sequence_violations(HW, chain) == []


def test_stage_sequence_flags_an_unregistered_stage_name() -> None:
    """段名不在注册表 `stages` 里 ⇒ 违例（**allowlist 式**：不在名单内即拒，`R-06 ⑤`）。"""
    kinds = [k for k, _ in stage_sequence_violations(HW, [{"stage": "order"}, {"stage": "乱写的段"}])]
    assert kinds == ["stage_unregistered"]


def test_stage_sequence_flags_a_skipped_stage() -> None:
    """★ `N4.1-07` 的验收逐字是"六段呈现且**不跳级**" ⇒ `order → shipment` 跳了 `production_schedule`。"""
    kinds = [k for k, _ in stage_sequence_violations(HW, [{"stage": "order"}, {"stage": "shipment"}])]
    assert kinds == ["stage_gap"]


def test_stage_sequence_flags_out_of_order_stages() -> None:
    """段序非严格递增 ⇒ `stage_order`（同时"缺中间段"也成立，故这里只断言**含**该 kinds）。"""
    kinds = [k for k, _ in stage_sequence_violations(HW, [{"stage": "shipment"}, {"stage": "order"}])]
    assert "stage_order" in kinds


def test_stage_sequence_accepts_the_full_hardware_six_stage_chain() -> None:
    """**反向对照**：六段齐备且不跳级 ⇒ 无违例（证明上面三条不是"见到链就红"）。"""
    chain = [{"stage": s} for s in HW.stages]
    assert stage_sequence_violations(HW, chain) == []


# ───────────────────── 注册表 / CLI（需要真文件） ─────────────────────


def test_registry_reads_the_rules_file(code_root) -> None:
    write_rules(code_root)
    reg = registry(code_root)
    assert set(reg) == {row["metric_set_id"] for row in METRIC_SETS}
    assert reg["MS-HW-6STAGE"].model_class == "hardware"
    assert reg["MS-HW-6STAGE"].stages[0] == "order"


def test_registry_rejects_a_duplicate_metric_set_id(code_root) -> None:
    """重复 `metric_set_id` ⇒ 响亮失败（路由会变得**取决于文件里的顺序**，不可接受）。"""
    write_rules(code_root, metric_sets=[*METRIC_SETS, dict(METRIC_SETS[0])])
    with pytest.raises(ValueError, match="重复 metric_set_id"):
        registry(code_root)


def test_metric_set_from_row_requires_the_two_key_fields() -> None:
    with pytest.raises(KeyError):
        metric_set_from_row({"metric_set_id": "MS-X"})


def test_cli_exits_zero_on_compliant_businesses_and_one_on_mismatch(code_root) -> None:
    """CLI 出口契约：绑定一致 ⇒ `exit 0`；绑定异类指标集 ⇒ `exit 1`（不是 warn，`AC-04`）。"""
    write_rules(code_root)
    write_jsonl(code_root, "businesses", [business("BIZ-HW", business_type="hardware")])
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 0, out

    write_jsonl(
        code_root, "businesses", [business("BIZ-HW", business_type="hardware", metric_set_id="MS-SW-5STAGE")]
    )
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 1, out
    assert "RESULT: FAIL" in out, out


def test_cli_flags_a_skipped_stage(code_root) -> None:
    """"不跳级"在 **CLI 出口**上也必须是 `exit 1`（否则它只是个没人调用的函数）。"""
    write_rules(code_root)
    write_jsonl(
        code_root,
        "businesses",
        [business("BIZ-HW", business_type="hardware", chain=["order", "shipment"])],
    )
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 1, out
    assert "stage_gap" in out, out


def test_cli_flags_unregistered_flag_inconsistency(code_root) -> None:
    """`§C.3` 要求"归入 MS-GENERIC **并显式标注**" ⇒ 未标注（或误标注）都是违例。"""
    write_rules(code_root)
    write_jsonl(
        code_root,
        "businesses",
        [business("BIZ-NEW", business_type="robotics", metric_set_id="MS-GENERIC", unregistered=False)],
    )
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 1, out
    assert "unregistered" in out, out


def test_cli_accepts_a_flagged_unregistered_business(code_root) -> None:
    """**反向对照**：未注册类型**正确**归入 `MS-GENERIC` 并标注 ⇒ `exit 0`（`§C.3` 的正常路径）。

    ★ 顺带证明另一处冲突已收口：`MS-GENERIC` **没有**段词汇表（`stages == []`），
      若把"段名不在空表里"判成违例，则这条正常路径同样**恒红**。本实现对"未声明 stages"
      的指标集记 `NO_STAGE_VOCABULARY` note（不可核 ≠ 违例，`G-03`）。
    """
    write_rules(code_root)
    write_jsonl(
        code_root,
        "businesses",
        [business("BIZ-NEW", business_type="robotics", metric_set_id="MS-GENERIC", unregistered=True)],
    )
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 0, out
    assert "NO_STAGE_VOCABULARY" in out, out


def test_cli_reports_owner_not_declared_as_a_note(code_root) -> None:
    """★ `G-03`：模板式注册表让"A2 跨业务引用"**不可核** ⇒ 必须显式 note + 计数，不得静默当成已核。"""
    write_rules(code_root)
    write_jsonl(
        code_root,
        "businesses",
        [
            business(
                "BIZ-SW",
                business_type="software",
                metric_set_id="MS-SW-5STAGE",
                chain=["usage", "paid", "renewal"],  # ★ 段名取自**本指标集**（软件五段）
            )
        ],
    )
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 0, out
    assert "OWNER_NOT_DECLARED" in out, out


def test_cli_flags_a_chain_borrowed_from_another_model_class(code_root) -> None:
    """★ **防串味也管段名**：软件业务却写了硬件六段的段名 ⇒ `exit 1`（`§C.1` 段名由注册表驱动）。"""
    write_rules(code_root)
    write_jsonl(
        code_root,
        "businesses",
        [
            business(
                "BIZ-SW",
                business_type="software",
                metric_set_id="MS-SW-5STAGE",
                chain=["order", "shipment"],  # 硬件段名
            )
        ],
    )
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 1, out
    assert "stage_unregistered" in out, out


def test_cli_reports_no_businesses_as_vacuous(code_root) -> None:
    """真源存在但为空 ⇒ `NO_BUSINESSES` note + `exit 0`（真空成立，**非**已验证，`G-03`）。"""
    write_rules(code_root)
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 0, out
    assert "NO_BUSINESSES" in out, out


def test_cli_treats_missing_businesses_source_as_input_error(code_root) -> None:
    """`facts/businesses.jsonl` **不存在**（≠ 存在但为空）⇒ `exit 2` 输入异常。"""
    write_rules(code_root)
    (code_root / "facts" / "businesses.jsonl").unlink(missing_ok=True)
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 2, out
    assert "INPUT-ERROR" in out, out


# ══════ 真规则文件里的 `tbd` 与兜底 id 漂移（13-R 安装真文件后新增，`G-03`/`G-06`） ══════


def test_tbd_metrics_is_read_as_undeclared_not_as_three_fake_metrics() -> None:
    """★ `metrics: tbd` ⇒ **未声明**，不得逐字符变成一个叫 't'/'b'/'d' 的指标列表。

    ★ 这是一处**真缺陷**的回归钉：13-R 转写真文件时，设计没给具体指标清单 ⇒ 如实写 `tbd`。
      初版 `metric_set_from_row` 直接 `for m in row.get("metrics") or []`，对字符串会**逐字符**迭代
      ⇒ 抛 `ValueError: metrics 项不是 mapping: 't'` ⇒ `route_guard` 在真仓库上**直接崩**
      （不是"判红"，是连判都判不了）。
    """
    ms = metric_set_from_row({"metric_set_id": "MS-X", "model_class": "hardware", "metrics": "tbd"})
    assert ms.metrics == ()


def test_tbd_stages_is_read_as_undeclared_so_the_chain_is_not_falsely_rejected() -> None:
    """★ `stages: tbd` ⇒ **未声明**；否则会变成一个名为 `tbd` 的段名 ⇒ 真实转化链全被判"不在注册表里"。

    ★ 这是第二处**真缺陷**的回归钉：`MS-GENERIC` 在真文件里 `stages: tbd`。
      若读成 `("tbd",)`，任何绑它的业务都会报 `stage_unregistered`（假红）。
    """
    ms = metric_set_from_row({
        "metric_set_id": "MS-GENERIC", "model_class": "generic",
        "stages": "tbd", "metrics": "tbd", "linked_accounts": "tbd", "currency": "tbd",
    })
    assert ms.stages == () and ms.metrics == () and ms.linked_accounts == () and ms.currency == ""


def test_tbd_currency_does_not_become_a_currency_named_tbd() -> None:
    """`currency: tbd` ⇒ 空串（不是字面量 `"tbd"`）—— 否则它会混进任何按币种比较的逻辑。"""
    ms = metric_set_from_row({"metric_set_id": "MS-C", "model_class": "cloud", "currency": "tbd"})
    assert ms.currency == ""


def test_real_rules_fallback_metric_set_is_ms_generic_as_the_code_assumes() -> None:
    """★ 真文件 `routing.fallback_metric_set_id` 必须与代码常量一致 —— 否则 `check()` 报漂移违例。

    ★ 这是 `G-06` 的落法：兜底 id 的**真源**在规则文件里，代码里那个常量是**被核对的引用**
      （`check()` 运行时比对）。本用例直接对真仓库的**规则文件**断言，故它同时是
      "常量没漂"与"文件没改"两条的绊线。
    """
    routing = _rules.metric_set_routing(SYSTEM_ROOT)
    assert routing["fallback_metric_set_id"] == _rules.GENERIC_METRIC_SET_ID


def test_cli_flags_drift_between_the_rules_file_and_the_code_constant(code_root) -> None:
    """★ 把真源改成另一个兜底 id ⇒ `check()` 必须报违例（漂移不得静默）。

    ★ 反向对照：不改时 `exit 0`（`test_cli_reports_no_businesses_as_vacuous` 已覆盖同一条路径）。
    """
    write_rules(code_root, metric_sets=[{"metric_set_id": "MS-OTHER", "model_class": "generic"}])
    (code_root / "rules" / "metric-sets.yaml").write_text(
        "version: 1\nrouting:\n  fallback_metric_set_id: MS-OTHER\nmetric_sets:\n"
        "  - metric_set_id: MS-OTHER\n    model_class: generic\n",
        encoding="utf-8",
    )
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 1, out
    assert "fallback_metric_set_id" in out and "漂移" in out, out
