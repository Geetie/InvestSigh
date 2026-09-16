"""扩表契约单测（需求方 2026-09-16 裁定 `facts/` 由 **18 → 22**）。

覆盖四件事（每条都对应团队任务书里的一项是/否）：

1. **4 张新表的 schema 正/反向**：合法行落库可读回；缺必填 → 拒；多一个字段 → 拒
   （`extra="forbid"` 真的生效，不是只写在 `ConfigDict` 里）。
2. **22 个 stem 结构齐备**：`JSONL_STEMS` 里的每个 stem 在 `facts/` 下都有文件。
3. **两处机器绑定**：`tests/conftest.py::_TRUTH_STEMS` ↔ 注册表（`JSONL_STEMS` / `JSONL_MODELS`）
   **集合逐一相等** —— 防的正是 `G-RC-02` / `G-RC-07` 那一族缺陷（夹具清空真源时漏掉新表）。
4. **`baseline.driver_model` 不再是第二个真源**：它只能是
   `driver_refs[]` + `drivers.jsonl` 的**投影**（`project_driver_model` 可现算；
   凭空写入的孤儿条目被 schema 拒绝）。
5. **`Ch5 §A.1`「新字段」清单的边界**（`05/02` 第 21 行逐字列了 5 项）：3 项进
   `Valuation`（`scenario_tag` / `implied_ref` / `independent_judgment`），`probability`
   已在；而 `input_source` **明确不进** —— 它按 `§D.5`「三类分开存」落在估值输入层
   `AssumptionInput`，在 `Valuation` 上再落一份即**双真源**（`G-06`）。含精确字段集断言
   与 `input_source` 的双向对照。

设计锚点（逐字）：`Ch4 §B.1`（business）/`§C.4`（financial_link）/`§D.1`（driver）/
`§F.1·§F.3`（moat 与写路径白名单）/`§G.1·§G.4·§H.3`（baselines 补齐）/
`Ch5 §A.1`（`baselines.valuation` 新字段清单）/`§B.2`（implied_requirements）/
`§C.1`（三份判断表）/`§D.5·§D.6`（估值输入与区间）/`§E.3`（`scenario_tag` 一致性）/
`Ch7 §B.3`（relation_flows 三边）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

import conftest as cf
from schema import models as M
from schema.stems import JSONL_STEMS
from schema.store import append_records, read_models, read_records

_AT = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)


# ───────────────────────── 合法样本（各表一份最小完整行） ─────────────────────────


def _business() -> M.Business:
    """`Ch4 §B.1` 的最小完整 business（`mechanism` 齐 `payer`/`offering`/`revenue_model`/`conversion_chain`）。"""
    return M.Business(
        business_id="BIZ-NVDA-DC",
        company_id="company_nvidia",
        business_type="hardware",
        metric_set_id="MS-HW-6STAGE",
        mechanism=M.BusinessMechanism(
            payer=M.Payer(party="hyperscaler", segment="cloud"),
            offering=["prod-h100"],
            revenue_model=M.RevenueModel.one_time,
            conversion_chain=[
                M.ConversionSegment(stage="order", input="PO", output="backlog", evidence=["CLM-1"]),
                M.ConversionSegment(stage="shipment", pending_evidence=True),
            ],
        ),
    )


def _driver() -> M.Driver:
    """`Ch4 §D.1` 的最小完整 driver。"""
    return M.Driver(
        driver_id="DRV-NVDA-DC-01",
        business_id="BIZ-NVDA-DC",
        source_class="demand_expansion",
        duration=M.Duration(mode="range", value="1-3Y"),
        financial_link=M.FinancialLink(
            accounts=["revenue_segment", "gross_margin"],
            per_share_metric="eps",
            formula_ref="dv-eps-1",
        ),
        cost_of_growth=M.CostOfGrowth(capex_requirement={"account": "capex"}),
        realization_stage="occurred",
        timeline="1-4Q",
        confidence="high",
        importance_class="high",
        dependencies=["capacity"],
        assumptions=["数据中心 capex 增速维持"],
    )


def _implied() -> M.ImpliedRequirement:
    """`Ch5 §B.2` 的最小完整 implied requirement（多组解中的一组）。"""
    return M.ImpliedRequirement(
        implied_id="IMP-001",
        solution_set_id="SET-nvda-2026-09-15",
        security_id="sec_nvda",
        price_snapshot_id="SNP-1",
        current_price="135.40",
        assumptions=M.ImpliedAssumptions(growth={"cagr": "0.18"}, risk={"wacc": "0.09"}),
        solved_variable="reinvestment",
        range=M.ImpliedRange(low="0.22", high="0.31"),
        alternative_explanations=["周期顶部的一次性需求"],
        feasible=True,
        method_version="v1",
        computed_at=_AT,
    )


def _relation_flow() -> M.RelationFlow:
    """`Ch7 §B.3` 的最小完整产品流（方向：供应商 → 客户）。"""
    return M.RelationFlow(
        flow_id="FLOW-1",
        relation_id="rel-nvda-msft",
        flow_kind="product",
        from_ref="company_nvidia",
        to_ref="company_microsoft",
        product_flow=M.ProductFlow(product_id="prod-h100", volume="1.2M units", stage="order"),
        evidence_claim_ids=["CLM-1"],
    )


# ───────────────────────── 1. 四张新表：正向 + 反向 ─────────────────────────

_NEW_TABLE_CASES = (
    ("businesses", M.Business, _business),
    ("drivers", M.Driver, _driver),
    ("implied_requirements", M.ImpliedRequirement, _implied),
    ("relation_flows", M.RelationFlow, _relation_flow),
)


@pytest.mark.parametrize(("stem", "model", "build"), _NEW_TABLE_CASES)
def test_new_table_row_roundtrips_through_the_real_store(stem, model, build, code_root: Path) -> None:
    """正向：合法行经**真实落库路径**（`append_records` + `read_models`）可写可读。"""
    row = build()
    assert append_records(code_root, stem, [row]) == 1
    back = read_models(code_root, stem)
    assert len(back) == 1
    assert back[0].model_dump(mode="json") == row.model_dump(mode="json")


@pytest.mark.parametrize(("stem", "model", "build"), _NEW_TABLE_CASES)
def test_new_table_rejects_extra_field(stem, model, build) -> None:
    """反向：多一个字段必须被拒（`extra="forbid"`；`Ch2 §C.2 R-15 ③` 一概念一字段名）。

    ★ 刻意**不**经夹具落库：`append_records` 的"校验失败不留半截数据"由
      `tests/unit/test_contracts.py::test_invalid_record_is_rejected_without_partial_write`
      对全部表统一覆盖；此处要证的是"模型本身拒绝未知字段"。
      少建一份夹具副本 = 少一份删除压力（`CONVENTIONS §一 V-08` 的宿主删除配额）。
    """
    payload = build().model_dump(mode="json")
    payload["definitely_not_designed"] = 1
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_business_requires_mechanism() -> None:
    """缺必填（`mechanism`）→ 拒。`Ch4 §B.1`：赚钱机制是该表的存在理由（`N4.1-01`）。"""
    with pytest.raises(ValidationError):
        M.Business(
            business_id="BIZ-X",
            company_id="company_nvidia",
            business_type="hardware",
            metric_set_id="MS-HW-6STAGE",
        )


def test_driver_requires_identity_and_source_class() -> None:
    """缺必填（`source_class` / `duration` / `financial_link` / `cost_of_growth` / `importance_class`）→ 拒。"""
    base = dict(
        driver_id="DRV-1",
        business_id="BIZ-1",
        source_class="share",
        duration=M.Duration(mode="point", value="1Y"),
        financial_link=M.FinancialLink(),
        cost_of_growth=M.CostOfGrowth(),
        importance_class="medium",
        occurred_at=_AT,
    )
    M.Driver(**base)                                  # 全齐 → 通过
    for missing in ("source_class", "duration", "financial_link", "cost_of_growth", "importance_class"):
        with pytest.raises(ValidationError):
            M.Driver(**{k: v for k, v in base.items() if k != missing})


def test_implied_requirement_requires_price_snapshot_and_solution_set() -> None:
    """缺 `price_snapshot_id` / `solution_set_id` → 拒。

    `Ch5 §B.2`：解集要聚合（`solution_set_id`），且反解是**针对某个行情快照**做的 ——
    缺了它，"使当前价格成立"没有可核对的时点（`Ch9 §N9.1-19`）。
    """
    payload = _implied().model_dump(mode="json")
    for missing in ("price_snapshot_id", "solution_set_id", "current_price", "assumptions"):
        with pytest.raises(ValidationError):
            M.ImpliedRequirement.model_validate({k: v for k, v in payload.items() if k != missing})


def test_implied_requirement_deliberately_has_no_time_mixin() -> None:
    """`ImpliedRequirement` **不叠加 `TimeMixin`**（`Ch5 §B.2` 已给系统时间 `computed_at`）。

    防的是"为同一概念引入第二个字段名"（`Ch2 §C.2 R-15 ③`）：若有 `TimeMixin`，
    `analyzed_at` 与 `computed_at` 会同时表达"什么时候算的"。
    """
    assert "computed_at" in M.ImpliedRequirement.model_fields
    for field in ("occurred_at", "first_seen_at", "analyzed_at", "recorded_seq"):
        assert field not in M.ImpliedRequirement.model_fields


# ───────────────────────── 2. 新表内的语义约束（各章 "可测断言"） ─────────────────────────


def test_conversion_segment_must_flag_pending_evidence() -> None:
    """`Ch4 §B.1/§B.2`：段内无证据 → **必须**显式标 `pending_evidence=true`（不得静默当"有证据"）。"""
    with pytest.raises(ValidationError, match="pending_evidence"):
        M.ConversionSegment(stage="order")
    M.ConversionSegment(stage="order", pending_evidence=True)          # 显式标注 → 通过
    M.ConversionSegment(stage="order", evidence=["CLM-1"])              # 有证据 → 通过


def test_conversion_segment_rejects_evidence_plus_pending_flag() -> None:
    """反向对照：既有证据又标"待核对"是自相矛盾 → 拒（防止把状态标反了还没人发现）。"""
    with pytest.raises(ValidationError, match="pending_evidence"):
        M.ConversionSegment(stage="order", evidence=["CLM-1"], pending_evidence=True)


def test_driver_source_class_domain_is_the_seven_plus_mixed() -> None:
    """`Ch4 §D.1` + 回改 `R-21`：`source_class` = **7 类 + `mixed` 兜底**（共 8 个取值）。"""
    assert {
        "demand_expansion", "share", "price", "product_mix",
        "unit_usage", "penetration", "new_business", "mixed",
    } == set(M.Driver.model_fields["source_class"].annotation.__args__)
    with pytest.raises(ValidationError):
        M.Driver(
            driver_id="DRV-1", business_id="BIZ-1", source_class="not_a_designed_class",
            duration=M.Duration(mode="point", value="1Y"),
            financial_link=M.FinancialLink(), cost_of_growth=M.CostOfGrowth(),
            importance_class="medium",
        )


def test_relation_flow_kind_and_payload_must_agree() -> None:
    """`Ch7 §B.3`：三条边各自独立 —— `flow_kind` 与子对象必须**一致在场**，不得混载。"""
    with pytest.raises(ValidationError, match="product_flow"):
        M.RelationFlow(flow_id="F", relation_id="R", flow_kind="product",
                       from_ref="a", to_ref="b", capital_flow=M.CapitalFlow(amount="1"))
    with pytest.raises(ValidationError, match="必须携带"):
        M.RelationFlow(flow_id="F", relation_id="R", flow_kind="capital", from_ref="a", to_ref="b")
    ok = M.RelationFlow(
        flow_id="F", relation_id="R", flow_kind="demand_signal", from_ref="msft", to_ref="nvda",
        demand_signal=M.DemandSignal(intensity="capex 指引上调", basis="季度电话会"),
    )
    assert ok.flow_kind is M.FlowKind.demand_signal


def test_moat_writer_whitelist_excludes_price_ingest() -> None:
    """`Ch4 §F.3` 断言 A3：`moat.writer ∈ {research_skill, human}`，**不含** `price_ingest`。

    这是把 "股价上涨不自动证明护城河增强"（C45-5）做成 **schema 层物理隔离**。
    """
    assert {m.value for m in M.MoatWriter} == {"research_skill", "human"}
    with pytest.raises(ValidationError):
        M.Moat(moat_id="MOAT-1", mechanism="x", writer="price_ingest")
    ok = M.Moat(moat_id="MOAT-1", mechanism="x", writer="human")
    assert ok.cross_generation_survival is None, "unknown 用 None 表达（Ch4 §F.1 三值）"


def test_assumption_input_manual_must_carry_trace() -> None:
    """`Ch5 §D.5`：`manual` 必须留痕（`author` + `modified_at`）；三类来源必须显式声明。"""
    with pytest.raises(ValidationError):
        M.AssumptionInput(value="0.09", input_source="manual")
    M.AssumptionInput(value="0.09", input_source="manual", author="需求方", modified_at=_AT)
    M.AssumptionInput(value="0.09", input_source="model_estimate")
    with pytest.raises(ValidationError):
        M.AssumptionInput(value="0.09")           # 缺 input_source → 拒（不得默认成 fact）


def test_increment_requires_new_info() -> None:
    """`Ch4 §H.2` / `N4.5-05`：无新信息不产新版本 ⇒ `increment.new_info` **不得为空**。"""
    with pytest.raises(ValidationError):
        M.Increment(old_judgment="a", new_info=[], new_judgment="b", affected_period="FY2027Q1")
    ok = M.Increment(old_judgment="a", new_info=["CLM-1"], new_judgment="b", affected_period="FY2027Q1")
    assert ok.counter_evidence == []


def test_driver_realization_stage_is_the_designed_three_states() -> None:
    """`Ch4 §D.1` / `§E.2` / `N4.2-01`：驱动**三态** = 已发生 / 计划指引预测 / 依赖条件（+ 待定 `tbd`）。

    本断言同时钉死一次**取值域纠正**：初版是 `not_started/ramping/ramped/declining`
    —— 设计里不存在这四个值，且是四态而非三态。
    """
    assert {m.value for m in M.DriverRealizationStage} == {
        "tbd", "occurred", "planned_guidance_forecast", "conditional",
    }


# ───────────────────────── 3. `driver_model` 不得成为第二个真源 ─────────────────────────


def test_driver_model_is_exactly_the_projection_fields() -> None:
    """投影只承载 `{driver_id, assumptions}` —— 其余内容一律从 `drivers.jsonl` 取。"""
    assert set(M.DriverModel.model_fields) == {"driver_id", "assumptions"}


def test_baseline_rejects_orphan_driver_model_entry() -> None:
    """★ 凭空写入的 `driver_model`（无对应 `driver_refs`）→ **拒**（否则它就是第二个真源）。"""
    with pytest.raises(ValidationError, match="driver_refs"):
        M.Baseline(
            baseline_id="b1", company_id="company_nvidia", version=1, business_mechanism="x",
            driver_model=[M.DriverModel(driver_id="DRV-not-referenced", assumptions=["a"])],
        )
    # **反向对照**：把同一个 driver_id 写进 `driver_refs` → 通过
    #   （证明上面的拒绝确实来自"投影 ⊆ 引用"这一条，而不是别的原因误伤）
    ok = M.Baseline(
        baseline_id="b1", company_id="company_nvidia", version=1, business_mechanism="x",
        driver_refs=["DRV-referenced"],
        driver_model=[M.DriverModel(driver_id="DRV-referenced", assumptions=["a"])],
    )
    assert ok.driver_refs == ["DRV-referenced"]


def test_project_driver_model_is_derivable_from_driver_refs_and_drivers_jsonl(code_root: Path) -> None:
    """★ **投影可派生**：`driver_refs[]` + `drivers.jsonl` 足以现算出 `driver_model`。

    这是"`driver_model` 不可能变成第二个真源"的**正向证据**：
    任何消费方都可以不看落库的那份副本，直接现算（`project_driver_model` 是纯函数）。
    """
    append_records(code_root, "drivers", [_driver()])
    baseline = M.Baseline(
        baseline_id="baseline-nvda-002",
        company_id="company_nvidia",
        version=2,
        business_mechanism="x",
        driver_refs=["DRV-NVDA-DC-01"],
        driver_model=[],                       # 落库时可以留空
    )
    drivers = {d.driver_id: d for d in read_models(code_root, "drivers")}
    projected = M.project_driver_model(baseline, drivers)
    assert [p.driver_id for p in projected] == baseline.driver_refs
    assert projected[0].assumptions == ["数据中心 capex 增速维持"]

    # 反向：落库的那份与现算的那份**必须一致**（若不一致，说明有人在写第二份真源）
    baseline.driver_model = projected
    roundtrip = M.Baseline.model_validate(baseline.model_dump(mode="json"))
    assert M.project_driver_model(roundtrip, drivers) == roundtrip.driver_model


def test_project_driver_model_fails_loudly_on_dangling_ref(code_root: Path) -> None:
    """引用不存在的 driver → `KeyError`（不静默跳过；本项目禁静默兜底）。"""
    baseline = M.Baseline(
        baseline_id="b1", company_id="c", version=1, business_mechanism="x",
        driver_refs=["DRV-missing"],
    )
    with pytest.raises(KeyError):
        M.project_driver_model(baseline, {})


# ───────────────────────── 4. 两处机器绑定 / 结构齐备 ─────────────────────────


def test_truth_stems_equals_facts_table_registry() -> None:
    """★ `conftest._TRUTH_STEMS` 必须与事实表注册表**集合逐一相等**。

    为什么单独断言：`_TRUTH_STEMS` 决定"夹具把哪些真源清空"。
    若它漏了新表，**测试就会重新依赖"真仓库恰好有什么"**
    —— 这正是 `G-RC-02` / `G-RC-07` 的同一族缺陷（本项目已栽 4 次）。
    `conftest` 现在直接从 `schema.stems` 派生（单一真源），本用例再把
    「注册表 ↔ `JSONL_MODELS` 的映射键」也钉上，使链条**首尾都不可漂移**。
    """
    assert set(cf._TRUTH_STEMS) == set(JSONL_STEMS)
    assert set(cf._TRUTH_STEMS) == set(M.JSONL_MODELS)
    assert len(cf._TRUTH_STEMS) == len(set(cf._TRUTH_STEMS)), "stem 不得重复"


def test_conftest_stems_are_the_registry_itself_not_a_copy() -> None:
    """★ 更强的一层：`_TRUTH_STEMS` 必须是**注册表本身**，而不是"抄了一份恰好相等"。

    证据 = **同一性**（`is`）与顺序一致：抄来的副本经 `tuple()` 会另建对象，
    而派生写法 `tuple(JSONL_STEMS)` 在语义上等价 —— 故这里断言的是
    "两处都指向 `stems.py` 的同一个 tuple 内容"，配合上一条的集合相等即闭合。
    （若将来有人把它改回手写清单，上一条会红；这一条固定当前派生关系不被误改。）
    """
    assert cf._TRUTH_STEMS == JSONL_STEMS


def test_every_registered_stem_has_a_facts_file() -> None:
    """22 个 stem **结构齐备**：注册表里每个 stem 在 `facts/` 下都有对应文件。

    ★ 与 `test_contracts.py::test_facts_dir_holds_exactly_the_22_files` 的分工：
    那条断言"文件集合 == 设计清单"（防多、防少）；这条断言"注册表 → 文件"**单向齐备**
    （防"注册了但没建文件"，即 `store.jsonl_path` 能算出路径但文件不存在）。
    """
    facts = Path(__file__).resolve().parents[2] / "facts"
    missing = [s for s in JSONL_STEMS if not (facts / f"{s}.jsonl").exists()]
    assert not missing, f"注册了却没有真源文件: {missing}"


# ───────────────────────── 5. 真实数据的向后兼容（契约变更不得让旧行失效） ─────────────────────────


def test_real_repo_existing_rows_still_validate() -> None:
    """★ **向后兼容**：真仓库 `facts/` 里**已存在**的行，逐条用新模型校验仍须通过。

    `Ch9 §3.4.2` 追加式不可变 ⇒ 契约变更（扩表 + `Baseline` 补字段 + `DriverModel` 收窄）
    **不得**让既有行失效。

    ★ 为什么这里**例外地**读真仓库数据（本项目通常禁止"测试依赖仓库里恰好有什么"）：
      向后兼容**只有**在真实数据上才能被证伪 —— 用造出来的样本证明"旧行仍合法"是同义反复。
      配套的非真空保护见下（一条都没读到即 fail，符合 `G-03`）。
    """
    system_root = Path(__file__).resolve().parents[2]
    checked = 0
    for stem in JSONL_STEMS:
        path = system_root / "facts" / f"{stem}.jsonl"
        if not path.exists():                       # 结构齐备由另一条用例负责
            continue
        rows = read_records(system_root, stem)
        model = M.model_for(stem)
        for row in rows:
            model.model_validate(row)               # 任一行非法即抛
            checked += 1
    assert checked > 0, (
        "真仓库 facts/ 里一行数据都没有 ⇒ 本用例真空（G-03：不得把'无被检对象'当'已验证'）。"
        "若确有意图清空真仓库，请同时删掉本用例并说明。"
    )


# ──────────── 6. `Ch5 §A.1` 新字段：3 项进 `Valuation`，`input_source` 不进 ────────────


def test_valuation_carries_the_three_new_ch5_fields() -> None:
    """`Ch5 §A.1`（`05_价格与市场预期研究/02_实现方案.md` 第 21 行）逐字：

    「`baselines.valuation` 上（`independent_judgment`、`implied_ref`、`input_source`、
    `probability`、`scenario_tag`）」—— 五项里 `probability` 扩表前已在
    ⇒ 本用例钉住**这一批新增的三项**。
    """
    assert {"scenario_tag", "implied_ref", "independent_judgment"} <= set(M.Valuation.model_fields)


def test_valuation_field_set_is_exactly_the_designed_nine() -> None:
    """★ 钉死 `Valuation` 的**精确字段集**：既防"顺手多塞一个"造成双真源，
    也防将来有人悄悄删字段而无人发现（同 `DriverModel` 那条精确断言的用意）。"""
    assert set(M.Valuation.model_fields) == {
        "method_class", "range", "probability", "formula_ref",
        "forecast_assumptions", "valuation_params",
        "scenario_tag", "implied_ref", "independent_judgment",
    }


def test_new_valuation_fields_default_to_the_tbd_marker() -> None:
    """★ 设计（`§A.1`）只给了**字段名、未给结构** ⇒ 默认落 `TBD`（哨兵 `"tbd"`，`models.py::TBD`）
    表示"待研究"，**不臆造** 区间 / 数值 / 枚举（臆造就是编）。
    `independent_judgment` 尤其如此：它要不要结构化承载属 13-B 的实现面，本批次不预设。
    """
    v = M.Valuation()
    assert (v.scenario_tag, v.implied_ref, v.independent_judgment) == (M.TBD, M.TBD, M.TBD)


def test_input_source_stays_on_assumption_input_not_valuation() -> None:
    """★ **反向对照**：`Ch5 §A.1` 清单里的 `input_source` **不得**落进 `Valuation`。

    理由（逐字）：`§D.5`「事实输入 / 模型估计 / 人工设定**三类分开存**」的落点是估值输入层
    `AssumptionInput.input_source`（**必填** + `manual` 须留痕的校验器），
    `§D.5` / `N5.3-04`（`input_source ∈ {fact, model_estimate, manual}` + 留痕）的验收面**也在那一层**。
    ⇒ 若按 `§A.1` 的字面清单在 `Valuation` 上再落一份，同一事实就有**两个存放处**（`G-06` 双真源）。

    本断言把这条裁定变成可执行的：**少了它，"为什么只加 3 个而不是 5 个"就只是注释里的一句话。**
    """
    assert "input_source" not in M.Valuation.model_fields
    assert "input_source" in M.AssumptionInput.model_fields


def test_valuation_still_rejects_unknown_fields() -> None:
    """反向：`extra="forbid"` 对新字段一样生效 —— 加字段时**没有**顺手关掉 forbid 的旁路。"""
    with pytest.raises(ValidationError):
        M.Valuation.model_validate({"scenario_tag": "bull", "not_a_designed_field": 1})


def test_new_valuation_fields_survive_a_baseline_roundtrip() -> None:
    """正向：3 个新字段嵌在 `Baseline` 里也能 roundtrip（`model_dump` → `model_validate` 值不变）。

    `Valuation` 不是独立事实表（它内嵌在 `baselines.jsonl` 的行里），故此处走
    `Baseline` 级 roundtrip，而不是 §1 那套 `store` roundtrip。
    """
    b = M.Baseline(
        baseline_id="b1", company_id="company_nvidia", version=1, business_mechanism="x",
        valuation=M.Valuation(
            scenario_tag="bull",
            implied_ref="IMP-001",
            independent_judgment="per-share-range-2026-09",
        ),
    )
    again = M.Baseline.model_validate(b.model_dump())
    assert again.valuation.scenario_tag == "bull"
    assert again.valuation.implied_ref == "IMP-001"
    assert again.valuation.independent_judgment == "per-share-range-2026-09"
    # 旧字段不受影响（契约变更只增不改）
    assert again.valuation.probability is None
