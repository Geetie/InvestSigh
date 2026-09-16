"""`Ch4 §G.2/§G.3/§G.4` —— **形式完备性**的五项检查（逐项正反用例）。

本文件的结构刻意与 `§G.2` 伪码一一对应：

| 用例组 | 对应判据 | 设计出处 |
|---|---|---|
| `test_sections_nonempty_*` | `sections_nonempty` | `§G.2` 表第 1 行 + `§G.1` 六项 |
| `test_nonnull_rate_*` | `nonnull_rate >= cfg.min_nonnull_rate` | `§G.2` 表第 2 行 |
| `test_has_locator_*` | `has_locator >= 1` | `§G.2` 表第 3 行（`N9.1-11`） |
| `test_has_derivation_*` | `has_derivation >= 1` | `§G.2` 表第 4 行（`N9.2-02`） |
| `test_cross_section_consistent_*` | `cross_section_consistent` | `§G.2` 表第 5 行 + `§C.4` 末句 |
| `test_g4_*` | 未盈利 / 盈利分支必填 | `§G.4`（`N4.2-04/05`） |
| `test_threshold_*` / `test_missing_threshold_*` | **阈值只从 `rules/baseline.yaml` 读** | `§G.2` / `§J.4 J3` / `Ch11 §D.2` |

★ **反向对照成对**（`G-05`）：每一组都有"合规 ⇒ 该项 `pass`"与"注入违例 ⇒ 该项 `fail`"
  两条，且断言的是 **`check_id` 级**的判定结果（不是"整体不过"）——
  否则"哪一项不过"不可见，而 `§G.2` 要的正是"五项**逐项**可判定、可定位"。

★ **夹具用量**（`P-05` 的实测成本账）：五项检查的**逻辑**用例全部走
  `_fixtures.compliant_context()` 这份**内存**上下文（与 `seed_compliant()` 写盘的内容
  逐字对应）——`code_root` 夹具每例要复制并**删除**一份 `system/`，而宿主对工作区内删除
  逐项监察（实测 ≈16ms/项 × ≈273 项 ≈ **4.5s/例**）。把这些纯函数用例也套夹具，
  首版实测 38 例要 **216s**，全部烧在与判据无关的开销上。
  只有"阈值必须从规则文件读 / 缺键 `exit 2` / CLI 退出码 / 上下文装载"这几类
  **真的需要文件**的用例才用 `code_root`（`test_seeded_fixture_is_form_complete_end_to_end`
  保证两套输入语义一致）。
"""

from __future__ import annotations

import dataclasses

import pytest

from conftest import SYSTEM_ROOT, run_gate_inproc
from scripts.valuelayer import _rules
from scripts.valuelayer.completeness import (
    CFG_MIN_DERIVATIONS,
    CFG_MIN_FIELDS_PER_SECTION,
    CFG_MIN_LOCATORS,
    CFG_MIN_NONNULL_RATE,
    CFG_REQUIRED_DECIDED,
    CHECK_IDS,
    SECTIONS,
    STATUS_FAIL,
    STATUS_NOT_EVALUATED,
    STATUS_PASS,
    FormContext,
    current_baselines,
    form_complete,
    form_context_from,
    g4_branch_outcome,
    nonnull_rate,
    to_gap,
)
from _fixtures import (
    THRESHOLDS,
    baseline,
    claim,
    compliant_context,
    driver,
    seed_compliant,
    write_thresholds,
    write_jsonl,
    write_rules,
)

CHECKER = "scripts/valuelayer/completeness.py"

CFG = dict(THRESHOLDS)


def _ctx(**overrides) -> FormContext:
    return FormContext(**compliant_context(**overrides))


def _outcome(result, check_id: str):
    for outcome in result.outcomes:
        if outcome.check_id == check_id:
            return outcome
    raise AssertionError(f"结果里没有 {check_id}（实得 {[o.check_id for o in result.outcomes]}）")


def _run(row, cfg=None, ctx=None):
    return form_complete(row, cfg if cfg is not None else CFG, context=ctx if ctx is not None else _ctx())


# ══════════════════════════ 项①：sections_nonempty ══════════════════════════


def test_sections_nonempty_passes_on_compliant_baseline() -> None:
    """合规 baseline ⇒ 六项 section 全部非空 ⇒ 项① `pass`，且整体 `passed`。"""
    result = _run(baseline())
    assert _outcome(result, "sections_nonempty").status == STATUS_PASS, result.summary()
    assert result.passed, result.summary()


@pytest.mark.parametrize(
    ("label", "row_overrides", "ctx_overrides"),
    [
        # ① 业务与产业位置：`business_refs` ∪ `relations`（§G.1① 给了**两个**载体）
        ("business_and_industry_position", {"business_refs": []}, {"relations": ()}),
        # ② 增长驱动
        ("growth_drivers", {"driver_refs": []}, {}),
        # ③ 增长确定性：四个子字段全部 tbd（载体在 drivers.jsonl，§G.1③）
        (
            "growth_certainty",
            {},
            {
                "drivers": {
                    "DRV-1": driver(
                        realization_stage="tbd", timeline="tbd", confidence="tbd", dependencies=[]
                    )
                }
            },
        ),
        # ④ 护城河
        ("moat", {"moat": []}, {}),
        # ⑤ 财务与估值：三个载体全清（§G.1⑤）
        (
            "financial_and_valuation",
            {
                "valuation_inputs": {},
                "historical_numeric_claims": [],
                "valuation": {"formula_ref": "tbd"},
            },
            {},
        ),
        # ⑥ 价格与行动：载体**在本表之外**（§G.1⑥ "不落本表"），来自第五/七章产物
        ("price_and_action", {}, {"chapter_refs": {}}),
    ],
)
def test_sections_nonempty_flags_the_very_section_that_was_emptied(
    label, row_overrides, ctx_overrides
) -> None:
    """逐个 section 清空其**全部载体** ⇒ 项① 必须红，且违例**点到该 section**。

    ★ "点了名"这件事是 `§G.2`「**逐项**可判定、可定位」的核心：
      只说"某个 section 为空"等于没定位。故断言存在一条 `locator == section_id`
      的违例（`locator` 是机器可读的定位字段；`reason` 里写的是人读的中文标题）。
    """
    result = _run(baseline(**row_overrides), ctx=_ctx(**ctx_overrides))
    outcome = _outcome(result, "sections_nonempty")
    assert outcome.status == STATUS_FAIL, f"{label} 清空后仍判 pass：{result.summary()}"
    hit = [v for v in outcome.violations if v.locator == label]
    assert hit, f"违例没有定位到 {label}（实得 {[(v.locator, v.reason) for v in outcome.violations]}）"
    assert outcome.scanned[label] == 0


def test_sections_nonempty_reports_six_sections_in_scanned() -> None:
    """`scanned` 里必须**逐 section** 可见（六项，不是"一个数"）—— 否则定位不了是哪一项。"""
    outcome = _outcome(_run(baseline()), "sections_nonempty")
    assert set(outcome.scanned) == {spec.section_id for spec in SECTIONS}
    assert len(SECTIONS) == 6, "§G.1 的六项深度 —— 少一项就不是'六项'"


def test_sections_nonempty_threshold_comes_from_cfg() -> None:
    """阈值只认 `cfg`：把 `min_fields_per_section` 抬到 3 ⇒ ② 与 ④（各只 1 个字段）当场红。

    这是"代码里**没有**内置默认阈值"的**内存侧**证据；文件侧证据见
    `test_missing_threshold_key_is_a_loud_input_error`。
    """
    assert _outcome(_run(baseline()), "sections_nonempty").status == STATUS_PASS
    cfg = {**CFG, CFG_MIN_FIELDS_PER_SECTION: 3}
    outcome = _outcome(_run(baseline(), cfg=cfg), "sections_nonempty")
    assert outcome.status == STATUS_FAIL
    assert outcome.scanned["growth_drivers"] == 1 and outcome.scanned["moat"] == 1


# ══════════════════════════ 项②：nonnull_rate ══════════════════════════


def test_nonnull_rate_passes_on_compliant_baseline() -> None:
    assert _outcome(_run(baseline()), "nonnull_rate").status == STATUS_PASS
    assert nonnull_rate(baseline()) == 1.0


def test_nonnull_rate_counts_tbd_as_blank() -> None:
    """★ `tbd` 必须被**当作空**：把"待定"当非空会让这个指标失去分辨力。"""
    row = baseline(margin_persistence="tbd")
    assert nonnull_rate(row) < 1.0
    assert _outcome(_run(row), "nonnull_rate").status == STATUS_PASS  # 0.8 的阈值下仍够
    cfg = {**CFG, CFG_MIN_NONNULL_RATE: 1.0}
    outcome = _outcome(_run(row, cfg=cfg), "nonnull_rate")
    assert outcome.status == STATUS_FAIL
    assert "margin_persistence" in outcome.violations[0].reason


def test_nonnull_rate_threshold_is_read_from_cfg() -> None:
    """抬高阈值 ⇒ 同一份输入当场红（阈值真被读了）。"""
    cfg = {**CFG, CFG_MIN_NONNULL_RATE: 1.0}
    outcome = _outcome(_run(baseline(fcf_persistence=""), cfg=cfg), "nonnull_rate")
    assert outcome.status == STATUS_FAIL


# ══════════════════════════ 项③：has_locator ══════════════════════════


def test_has_locator_passes_on_compliant_baseline() -> None:
    outcome = _outcome(_run(baseline()), "has_locator")
    assert outcome.status == STATUS_PASS
    assert outcome.scanned["located"] >= 1


def test_has_locator_fails_when_claim_has_no_locator() -> None:
    """被引用的 claim **没有 locator** ⇒ 项③ 红（`N9.1-11`：主要结论可反查）。"""
    ctx = _ctx(claims={"CLM-1": claim("CLM-1", locator=""), "CLM-2": claim("CLM-2", locator="")})
    result = _run(baseline(), ctx=ctx)
    outcome = _outcome(result, "has_locator")
    assert outcome.status == STATUS_FAIL, result.summary()
    assert "合格定位 0 条" in outcome.violations[0].reason


def test_has_locator_points_at_the_dangling_claim_id() -> None:
    """★ **给了** claims 上下文但集合里没有该 id ⇒ 悬空引用 ⇒ `fail`，且违例点出该 id。

    "已知的 claim 集合**确定**不含它"是**可判定**的（不是"没法判"）——
      这正是 `§G.2` 项③要拦的形态，也是 `G-03` 与"上下文缺失"的分界。
    """
    ctx = _ctx(claims={}, derived={"dv-1": {"derived_id": "dv-1", "formula": "f", "operands": ["x"]}})
    result = _run(baseline(evidence_claim_ids=["CLM-NOPE"], moat=[]), ctx=ctx)
    outcome = _outcome(result, "has_locator")
    assert outcome.status == STATUS_FAIL, result.summary()
    assert "CLM-NOPE" in outcome.violations[0].reason, outcome.violations


def test_has_locator_is_not_evaluated_when_nothing_is_referenced() -> None:
    """**无被检对象**（没引用任何证据）⇒ `not_evaluated`，**不是** `pass`（`G-03`）。

    ★ 这里是"空 ≠ 已验证"最容易被违反的一处：空集合上"≥1 条定位"恒假、
      但"0 条不合格"也恒真 —— 两种读法都能自圆其说。本实现把它显式标成"没法判"。
    """
    result = _run(baseline(evidence_claim_ids=[], moat=[]))
    outcome = _outcome(result, "has_locator")
    assert outcome.status == STATUS_NOT_EVALUATED, result.summary()
    assert result.passed is False
    assert "has_locator" in result.not_evaluated and "has_locator" not in result.failed


def test_has_locator_is_not_evaluated_without_claims_context() -> None:
    """**完全没给**上下文（`context=None`）⇒ `not_evaluated`（不可核 ≠ 已核）。

    ★ 与 `test_has_locator_points_at_the_dangling_claim_id` 成对：那里是"给了上下文、
      集合里没有" ⇒ **fail**；这里是"没给上下文、集合未知" ⇒ **not_evaluated**。
      两者若混为一谈，则"仓库里根本没有 claims 文件"时，任意编造的 claim id 都拦不住。
    """
    result = form_complete(baseline(), CFG, context=None)
    assert _outcome(result, "has_locator").status == STATUS_NOT_EVALUATED
    assert "has_locator" in result.not_evaluated


# ══════════════════════════ 项④：has_derivation ══════════════════════════


def test_has_derivation_passes_on_compliant_baseline() -> None:
    assert _outcome(_run(baseline()), "has_derivation").status == STATUS_PASS


@pytest.mark.parametrize(
    ("row", "why"),
    [
        ({"derived_id": "dv-1", "formula": "rev * margin", "operands": []}, "无操作数"),
        ({"derived_id": "dv-1", "formula": "", "operands": ["rev"]}, "无公式"),
    ],
)
def test_has_derivation_requires_both_formula_and_operands(row, why) -> None:
    """`§G.2` 括号里逐字写"**公式 + 操作数**" ⇒ 缺任一即不算推导（可复查性的下限）。"""
    ctx = _ctx(derived={"dv-1": row}, drivers={"DRV-1": driver(formula_ref="tbd")})
    result = _run(baseline(), ctx=ctx)
    outcome = _outcome(result, "has_derivation")
    assert outcome.status == STATUS_FAIL, f"{why} 却仍判 pass：{result.summary()}"
    assert "dv-1" in outcome.violations[0].reason


def test_has_derivation_is_not_evaluated_when_all_refs_are_tbd() -> None:
    """`valuation.formula_ref` 与驱动的 `formula_ref` 都是 `tbd` ⇒ 无被检对象（`G-03`）。"""
    ctx = _ctx(drivers={"DRV-1": driver(formula_ref="tbd")})
    result = _run(baseline(valuation={"method_class": "dcf", "formula_ref": "tbd"}), ctx=ctx)
    assert _outcome(result, "has_derivation").status == STATUS_NOT_EVALUATED


def test_has_derivation_accepts_driver_financial_link_formula_ref() -> None:
    """`§C.4` 的三层映射 `driver.financial_link.formula_ref` 也是推导载体之一。"""
    result = _run(
        baseline(valuation={"method_class": "dcf", "formula_ref": "tbd"}),
        ctx=_ctx(drivers={"DRV-1": driver(formula_ref="dv-1")}),
    )
    assert _outcome(result, "has_derivation").status == STATUS_PASS


# ══════════════════════ 项⑤：cross_section_consistent ══════════════════════


def test_cross_section_consistent_passes_on_compliant_baseline() -> None:
    assert _outcome(_run(baseline()), "cross_section_consistent").status == STATUS_PASS


def test_cross_section_consistent_fails_when_driver_absent_from_financial_link() -> None:
    """★ `§C.4` 末句逐字："**驱动必须出现在财务连接里**" ⇒ `financial_link.accounts` 空即违例。"""
    result = _run(baseline(), ctx=_ctx(drivers={"DRV-1": driver(accounts=[])}))
    outcome = _outcome(result, "cross_section_consistent")
    assert outcome.status == STATUS_FAIL, result.summary()
    assert "未出现在财务连接里" in outcome.violations[0].reason


def test_cross_section_consistent_fails_when_driver_ref_dangles() -> None:
    """`driver_refs` 指向不存在的驱动 ⇒ 违例（`§G.1②` 是**引用**，不是内嵌）。"""
    result = _run(baseline(driver_refs=["DRV-NOPE"]))
    outcome = _outcome(result, "cross_section_consistent")
    assert outcome.status == STATUS_FAIL
    assert "不存在的驱动" in outcome.violations[0].reason


def test_cross_section_consistent_fails_when_business_ref_dangles() -> None:
    """`business_refs` 指向不存在的业务 ⇒ 违例（`§G.1①` 是引用）。"""
    result = _run(baseline(business_refs=["BIZ-NOPE"]))
    outcome = _outcome(result, "cross_section_consistent")
    assert outcome.status == STATUS_FAIL
    assert "不存在的业务" in outcome.violations[0].reason


def test_cross_section_consistent_is_not_evaluated_without_refs() -> None:
    """没有任何跨节引用 ⇒ `not_evaluated`（无被检对象，`G-03`），不得判"一致"。"""
    result = _run(baseline(driver_refs=[], business_refs=[]))
    assert _outcome(result, "cross_section_consistent").status == STATUS_NOT_EVALUATED


def test_cross_section_consistent_is_not_evaluated_without_drivers_context() -> None:
    """引用了驱动但**根本没给**上下文 ⇒ `not_evaluated`（不可核 ≠ 已核）。"""
    result = form_complete(baseline(), CFG, context=None)
    assert _outcome(result, "cross_section_consistent").status == STATUS_NOT_EVALUATED


def test_cross_section_consistent_flags_dangling_driver_when_set_is_known() -> None:
    """给了 drivers 上下文（哪怕只有别的驱动）⇒ 悬空引用**可判定** ⇒ `fail`。"""
    result = _run(baseline(driver_refs=["DRV-NOPE"]), ctx=_ctx())
    outcome = _outcome(result, "cross_section_consistent")
    assert outcome.status == STATUS_FAIL
    assert "DRV-NOPE" in outcome.violations[0].reason


# ══════════════════════════ §G.4 盈利 / 未盈利分支 ══════════════════════════


def test_g4_unprofitable_branch_requires_five_fields() -> None:
    """未盈利公司缺 `cash_runway` 等必填 ⇒ `§G.4` 项红（`N4.2-04`）。"""
    row = baseline(
        is_profitable=False,
        business_model_note="按 token 计费",
        path_to_profitability=["FY2027 转正"],
        cash_runway="tbd",
        funding_need="tbd",
        unit_economics="tbd",
    )
    outcome = g4_branch_outcome(row)
    assert outcome.status == STATUS_FAIL
    assert "cash_runway" in outcome.violations[0].reason


def test_g4_unprofitable_branch_passes_when_all_five_present() -> None:
    """未盈利分支五项齐备 ⇒ 该分支 `pass`（**反向对照**，`G-05`）。"""
    row = baseline(
        is_profitable=False,
        business_model_note="按 token 计费",
        path_to_profitability=["FY2027 转正"],
        cash_runway="18 个月",
        funding_need="usd 2bn",
        unit_economics="单卡毛利转正",
    )
    assert g4_branch_outcome(row).status == STATUS_PASS


def test_g4_profitable_branch_passes_on_compliant_baseline() -> None:
    assert g4_branch_outcome(baseline()).status == STATUS_PASS


def test_g4_branch_undetermined_is_not_evaluated() -> None:
    """`is_profitable` 未判定 ⇒ `not_evaluated`（**不猜**是哪一支，`G-03`）。"""
    assert g4_branch_outcome(baseline(is_profitable=None)).status == STATUS_NOT_EVALUATED


def test_g4_undetermined_makes_the_whole_result_not_pass() -> None:
    """分支未定 ⇒ 整体**不得**判通过（否则"没研究"会被冒充成"形式合规"）。"""
    result = _run(baseline(is_profitable=None))
    assert result.passed is False
    assert "g4_profitability_branch" in result.not_evaluated


# ══════════════════════════ §G.3 gap 衔接 ══════════════════════════


def test_gap_object_uses_the_six_design_keys() -> None:
    """`§G.3` 逐字给出 gap 的六个键；不过时必须产出它（缺口可见，不是沉默）。"""
    row = baseline(driver_refs=[])
    result = _run(row)
    gap = to_gap(result, row)
    assert gap is not None
    assert set(gap) == {"gap_type", "scope", "blocking_step", "required_input", "status", "created_at"}
    assert gap["status"] == "open"
    assert gap["required_input"], "缺口必须写明'不足以完成哪些项'（§G.3：不足以完成 X）"


def test_gap_is_none_when_form_is_complete() -> None:
    """**反向对照**：形式上完备时 `gap` 必须为 `None`（不得制造缺口）。"""
    result = _run(baseline())
    assert result.passed, result.summary()
    assert result.gap is None


# ══════════════════════════ 结果结构契约 ══════════════════════════


def test_result_exposes_all_five_pseudocode_checks() -> None:
    """结果里必须**逐项**出现 `§G.2` 伪码的五项（缺一项 = 少查了一项而没人知道）。"""
    ids = [o.check_id for o in _run(baseline()).outcomes]
    for check_id in CHECK_IDS:
        assert check_id in ids, f"§G.2 伪码的第 {check_id} 项没有出现在结果里"


def test_failed_and_not_evaluated_are_reported_separately() -> None:
    """"不达标"与"没法判"必须**分开报**（`G-03`）—— 混在一起会让人修错地方。"""
    result = _run(baseline(moat=[], driver_refs=[], business_refs=[]))
    assert "sections_nonempty" in result.failed
    assert "cross_section_consistent" in result.not_evaluated
    assert set(result.failed) & set(result.not_evaluated) == set()


def test_result_is_frozen_immutable() -> None:
    """结果对象不可变 —— 判定过程**不得**被下游就地改写（与追加式不可变同源）。"""
    result = _run(baseline())
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.passed = True  # type: ignore[misc]


# ══════════════════ 阈值必须来自 rules/baseline.yaml（需要真文件） ══════════════════


@pytest.mark.parametrize(
    "key",
    [CFG_MIN_NONNULL_RATE, CFG_MIN_FIELDS_PER_SECTION, CFG_MIN_LOCATORS, CFG_MIN_DERIVATIONS],
)
def test_missing_threshold_key_is_a_loud_input_error(code_root, key) -> None:
    """★ 缺阈值键 ⇒ **`exit 2` 输入异常**（**不得**内置默认值悄悄放行）。

    这是 `Ch4 §G.2` / `§J.4 J3` / `Ch11 §D.2` 的直接后果：阈值是**规则真源**里的参数，
    代码里放一个兜底数会让"阈值从未被拍板"这件事**不可观测**（`G-03` 同族）。
    """
    seed_compliant(code_root)
    cfg = dict(_rules.baseline_cfg(code_root))
    cfg.pop(key)
    write_thresholds(code_root, cfg)

    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 2, f"期望 exit=2（输入异常），实得 {code}\n{out}"
    assert "INPUT-ERROR" in out and key in out, out


def test_null_threshold_value_is_also_a_loud_input_error(code_root) -> None:
    """阈值写成 `null`（= "待定"）⇒ 同样 `exit 2`：空值不得被当成一个可用阈值。"""
    seed_compliant(code_root)
    cfg = dict(_rules.baseline_cfg(code_root))
    cfg[CFG_MIN_LOCATORS] = None
    write_thresholds(code_root, cfg)
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 2, out
    assert "不得被当成一个可用阈值" in out, out


def test_cli_reads_thresholds_from_the_rules_file(code_root) -> None:
    """阈值抬到不可满足 ⇒ CLI 必须 `exit 1`；这证明 CLI 真的读了 `rules/baseline.yaml`。"""
    seed_compliant(code_root)
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 0, out

    cfg = dict(_rules.baseline_cfg(code_root))
    cfg[CFG_MIN_FIELDS_PER_SECTION] = 6
    write_thresholds(code_root, cfg)
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 1, out
    assert "sections_nonempty" in out, out


def test_cli_exits_one_on_violation_and_zero_on_compliant(code_root) -> None:
    """CLI 出口契约：合规 ⇒ `exit 0`；注入违例 ⇒ `exit 1`（**不是 warn**，`G-01`/`AC-04`）。"""
    seed_compliant(code_root)
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 0, out

    write_jsonl(code_root, "baselines", [baseline(driver_refs=[], moat=[])])
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 1, out
    assert "RESULT: FAIL" in out, out


def test_cli_reports_no_baselines_as_vacuous_not_verified(code_root) -> None:
    """真源存在但为空 ⇒ 显式 `NO_BASELINES` note + `exit 0`（真空成立，**非**已验证，`G-03`）。"""
    write_rules(code_root)
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 0, out
    assert "NO_BASELINES" in out, out


def test_context_loader_reads_the_five_sources(code_root) -> None:
    """`form_context_from()` 必须真的把五类来源装进来（否则上列"不可核"分支会遮蔽一切）。"""
    seed_compliant(code_root)
    ctx = form_context_from(code_root)
    assert set(ctx.drivers) == {"DRV-1"}
    assert set(ctx.businesses) == {"BIZ-1"}
    assert set(ctx.claims) == {"CLM-1", "CLM-2"}
    assert set(ctx.derived) == {"dv-1"}
    assert ctx.relations, "relations 上下文为空 ⇒ §G.1① 的第二个载体永远判不到"
    assert ctx.chapter_refs.get("CO-1"), "§G.1⑥ 的跨章引用为空 ⇒ ⑥ 永远 not_evaluated"


def test_seeded_fixture_is_form_complete_end_to_end(code_root) -> None:
    """端到端：夹具写出的 `facts/` 经 `form_context_from()` 后**六项全过**。

    ★ 这条是上面所有"内存上下文"用例的**地基**：若夹具写盘的内容与内存上下文不一致，
      那些内存用例就会在一个现实中不存在的输入上判分（`G-RC-02` 的同族风险）。
    """
    seed_compliant(code_root)
    cfg = _rules.baseline_cfg(code_root)
    result = form_complete(baseline(), cfg, context=form_context_from(code_root))
    assert result.passed, result.summary()
    assert result.gap is None


# ══════════ 阈值来自**已安装的真规则文件**（`R8-1` 的深度 + 13-R 的键名） ══════════
#
# ★ 本节的用例全部**只读真仓库的 `rules/**`**（经 `conftest.SYSTEM_ROOT`），**不用夹具**：
#   它们要钉住的正是"代码的读口与真文件的结构对不对得上" —— 用夹具（自己写一份）测这件事
#   等于自己给自己出题。初版正是在这里**实测**出了失败：代码按顶层扁平键读，而真文件是
#   `thresholds:` 分组、且键名是 `min_locator_count` / `min_derivation_count`
#   ⇒ 若没有本节，那处不合只会在"门禁恒红"时才被发现（`G-01`）。


def _real_thresholds() -> dict:
    """真仓库 `rules/baseline.yaml::thresholds`（只读；文件不在 ⇒ 由本函数响亮失败）。"""
    return dict(_rules.baseline_cfg(SYSTEM_ROOT))


def test_real_rules_thresholds_group_is_present() -> None:
    """`cfg` = `baseline["thresholds"]`（`R8-1`）—— 真文件里该分组必须存在且为 mapping。"""
    thresholds = _real_thresholds()
    assert thresholds, "真 rules/baseline.yaml 的 thresholds 分组为空"
    assert _rules.is_undecided(thresholds) is False


@pytest.mark.parametrize("key", CFG_REQUIRED_DECIDED)
def test_real_rules_required_thresholds_are_decided(key) -> None:
    """★ 三项**必须已拍板**的阈值在真文件里都要有值 —— 否则 `chapter4_g_depth` 会恒红（`G-01`）。"""
    value = _rules.baseline_threshold_from(_real_thresholds(), key)
    assert value is not None


def test_real_rules_min_fields_is_tbd_and_that_is_not_an_error() -> None:
    """★ `min_fields_per_section` 在真文件里是 `tbd` ⇒ 取值为 `None`，且**不是**缺键、**不**抛异常。

    ★ 为什么要钉住这条：它是 `G-01`（恒红的门禁一定会被关掉）与"阈值不得内置"两条约束的
      **交点**。若代码在这里抛"缺键"，判据恒红；若代码在这里兜一个默认数（如 1），
      "设计从未拍板"这件事就**不可观测**（`G-03`）。唯一正确的形态是：可核、且**如实说不核**。
    """
    assert _rules.threshold_or_none(_real_thresholds(), CFG_MIN_FIELDS_PER_SECTION) is None
    # 缺键仍然响亮失败（`tbd` 与"没这个键"是两件事）
    with pytest.raises(_rules.MissingRuleInput):
        _rules.threshold_or_none(_real_thresholds(), "not_a_key_at_all")


def test_real_rules_section_titles_match_the_code() -> None:
    """六项 section 的**名称真源** = 真文件 `form_completeness.sections`；代码里的标题必须逐字一致。

    ★ 漂移绊线：初版代码把标题写成 `① 业务与产业位置`（圆圈数字后**多一个空格**），
      与真文件的 `①业务与产业位置` 不同 —— 不影响判定（判定按 `section_id`），
      但会让**给人读的违例文案**与设计真源对不上。此处把它钉死。
    """
    doc = _rules.baseline_doc(SYSTEM_ROOT)
    declared = doc["form_completeness"]["sections"]
    assert [spec.title for spec in SECTIONS] == list(declared)


def test_real_rules_declares_the_guard_and_entry_the_code_provides() -> None:
    """真文件声明的 `entry` / `guard` 必须**正是**本模块提供的那个（否则文件与实现对不上）。"""
    section = _rules.baseline_doc(SYSTEM_ROOT)["form_completeness"]
    assert section["entry"] == "form_complete"
    assert SECTIONS and CHECK_IDS
    assert form_complete.__name__ == section["entry"]
    assert section["guard"] == "scripts/valuelayer/completeness.py"


def test_real_rules_cross_section_flag_matches_the_implemented_behaviour() -> None:
    """真文件 `require_cross_section_consistent: true` ⇒ 本模块必须**真的**跑这条检查。"""
    flags = _rules.baseline_doc(SYSTEM_ROOT)["form_completeness"]
    assert flags["require_cross_section_consistent"] is True
    assert "cross_section_consistent" in CHECK_IDS


# ══════════ 项①的「达最小字段数」半项：阈值为 `tbd` 时的降级（`G-03`/`G-01`） ══════════


def test_undecided_min_fields_enforces_nonempty_and_reports_the_undecided_half() -> None:
    """★ 阈值为 `tbd` ⇒ 『非空』照常强制 + 『达最小字段数』记**不可核**（含计数），**不**恒红。

    ★ 这条同时钉住三件事：
      1. 合规 baseline ⇒ 该项仍 `pass`（不因"设计没拍板"就拦，`G-01`）；
      2. `outcome.notes` 里逐字报出 `MIN_FIELDS_UNDECIDED` 与**几个** section 受影响（`G-03`）；
      3. 同一次跑里"空标题"**照样**被拦 —— 即"降级"没有把可核的那半项也一起放掉。
    """
    cfg = {**CFG, CFG_MIN_FIELDS_PER_SECTION: "tbd"}

    ok = _outcome(_run(baseline(), cfg=cfg), "sections_nonempty")
    assert ok.status == STATUS_PASS, ok.violations
    assert any(n.startswith("MIN_FIELDS_UNDECIDED") for n in ok.notes)
    assert f"本次 {len(SECTIONS)} 个 section" in "".join(ok.notes)

    empty = _outcome(_run(baseline(moat=[]), cfg=cfg), "sections_nonempty")
    assert empty.status == STATUS_FAIL
    assert [v.locator for v in empty.violations], "空 section 未被逐项定位"


def test_tbd_threshold_does_not_silently_become_a_number() -> None:
    """`tbd` **不得**被当成一个数（写 1 就等于替需求方拍板）：出现 `>= 1` 之类的比较即算失败。

    ★ 判据：`sections_nonempty` 在 `tbd` 下的**原因文案**不得出现"最小字段数 N"这种比较口径，
      而应逐字给出"为空"。两者是**可区分**的（前者=有一个数在比，后者=只判非空）。
    """
    cfg = {**CFG, CFG_MIN_FIELDS_PER_SECTION: "tbd"}
    empty = _outcome(_run(baseline(moat=[]), cfg=cfg), "sections_nonempty")
    reasons = " ".join(v.reason for v in empty.violations)
    assert "最小字段数" not in reasons, reasons
    assert "为空" in reasons, reasons


# ══════════ 版本选择：只判「当前版本」（追加式真源的必然，`Ch9 §N9.1-17`） ══════════
#
# ★ 为什么需要这一组（WS-A · 卡 `01_WS-A` 的 AC-02/AC-03）：
#   `facts/baselines.jsonl` 是**追加式版本表**（纪律 4），"补深度"的唯一合规动作是
#   **追加新版本行**（旧行原样留存）。若门禁对**所有历史行**逐条判 §G，则一次"补深度"
#   会让它刚补完的历史缺口**永久变红**（恒红 = 一定会被关掉，`G-01`）。
#   ⇒ 判据的被检对象必须是"每条 `company_id` 的当前版本"。
#   ★ 反向仍要拦：当前版本不完备 ⇒ **照样 `exit 1`**（下面第二条用例钉住这一点，
#     免得"只判当前版本"退化成"什么都不判"）。


def test_current_baselines_picks_the_highest_version_per_company() -> None:
    """同一 `company_id` 多版本 ⇒ 只取最高版本；不同公司各自保留一条。"""
    rows = [
        {"company_id": "CO-1", "version": 1, "baseline_id": "b1"},
        {"company_id": "CO-1", "version": 3, "baseline_id": "b3"},
        {"company_id": "CO-2", "version": 1, "baseline_id": "c1"},
    ]
    picked = current_baselines(rows)
    assert [r["baseline_id"] for r in picked] == ["b3", "c1"]


def test_current_baselines_breaks_ties_by_recorded_seq() -> None:
    """同 `version` 时以追加序 `recorded_seq` 判先后（追加式真源的行序即时序）。"""
    rows = [
        {"company_id": "CO-1", "version": 2, "recorded_seq": 5, "baseline_id": "a"},
        {"company_id": "CO-1", "version": 2, "recorded_seq": 9, "baseline_id": "b"},
    ]
    picked = current_baselines(rows)
    assert [r["baseline_id"] for r in picked] == ["b"]


def test_current_baselines_does_not_drop_rows_without_version_keys() -> None:
    """★ 缺 `company_id` / `version` 的行**不得被静默丢弃**（各自成键、仍被判）。

    否则"缺键"会变成一条绕过被检的旁路（`G-03`：没有可检对象 ≠ 已验证）。
    """
    rows = [{"baseline_id": "x"}, {"baseline_id": "y", "version": "tbd"}]
    picked = current_baselines(rows)
    assert {r["baseline_id"] for r in picked} == {"x", "y"}


def test_cli_judges_only_the_current_version_per_company(code_root) -> None:
    """历史版本不完备、当前版本完备 ⇒ **`exit 0`**，且显式记账"跳过了几条历史版本"。"""
    seed_compliant(code_root)
    rows = [
        baseline(version=1, moat=[], driver_refs=[], business_refs=[]),  # 历史版本：不完备
        baseline(version=2),  # 当前版本：完备
    ]
    write_jsonl(code_root, "baselines", rows)
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 0, out
    assert "HISTORICAL_VERSIONS_SKIPPED" in out, out


def test_cli_current_version_incomplete_still_fails(code_root) -> None:
    """**反向对照**：当前版本不完备 ⇒ 仍 `exit 1`（"只判当前版本"不等于"放行一切"）。"""
    seed_compliant(code_root)
    rows = [
        baseline(version=1),  # 历史版本：完备
        baseline(version=2, moat=[], driver_refs=[], business_refs=[]),  # 当前版本：不完备
    ]
    write_jsonl(code_root, "baselines", rows)
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 1, out
    assert "sections_nonempty" in out, out
