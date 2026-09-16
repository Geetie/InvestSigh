"""`valuation` 单测（`Ch5 §D.1` 方法路由 / `§D.2` 追溯链 / `§D.3` 顺序 / `§D.6` 概率）。

覆盖 DoD：「`valuation` 的方法路由**只**读 `rules/valuation-methods.yaml`；
`DerivedValue` 追溯链可追（`operand` 可达）」+「注入违例 → exit 非零」+ 反向对照。
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.compute.contract import OrderViolation
from scripts.pricelayer.valuation import (
    DEFAULT_METHOD_CLASS,
    METHOD_ROUTING_KEY,
    BaselineVersionRef,
    ValuationError,
    ValuationParams,
    assert_traceability,
    compute_valuation,
    load_method_routing,
    load_unregistered_fallback,
    route_method,
    trace_derived_chain,
)

BASELINE_AT = datetime(2026, 8, 1, tzinfo=timezone.utc)
COMPUTE_AT = datetime(2026, 9, 10, tzinfo=timezone.utc)

#: `Ch5 §D.1` 的表**内容**（ASCII 候选名，用于**纯函数**用例）。
#: ★ 规则文件真值（中文方法类名）另在 `test_real_rules_*` 里用 `real_rules` 夹具核 ——
#:   真值：`hardware`→4 / `cloud`→2 / `software`→3 / `etf`→1。
DESIGN_ROUTING = {
    "hardware": ("normalized_earnings", "cash_flow_with_reinvestment", "segment", "peer_comparison"),
    "cloud": ("cash_flow_with_reinvestment", "segment"),
    "software": ("normalized_earnings", "cash_flow", "retention_metrics"),
    "etf": ("simplified_worksheet",),
}


class _FakeDerived:
    def __init__(self, derived_id: str, formula: str, operands: list[str]) -> None:
        self.derived_id = derived_id
        self.formula = formula
        self.operands = operands


def _resolve_factory(mapping: dict[str, _FakeDerived]):
    return lambda ref: mapping.get(ref)


# ───────────────────── §D.1 方法路由 ─────────────────────


def test_routing_is_read_from_rules_yaml(scratch: Path, write_rules) -> None:
    """路由**只**从 `rules/valuation-methods.yaml` 读（`_cached_yaml`）。"""
    write_rules(scratch, "valuation-methods.yaml", {METHOD_ROUTING_KEY: DESIGN_ROUTING})
    routing = load_method_routing(scratch)
    assert routing["hardware"] == DESIGN_ROUTING["hardware"]
    assert routing["etf"] == ("simplified_worksheet",)


def test_missing_rule_file_fails_loudly(scratch: Path) -> None:
    """★ 规则文件缺失 → **响亮失败**（不静默退回"全部 generic"）。"""
    with pytest.raises(FileNotFoundError):
        load_method_routing(scratch)


def test_missing_routing_key_fails_loudly(scratch: Path, write_rules) -> None:
    """键名不符 → 响亮失败（键名设计未给，故不许静默兜底；见报告待裁定）。"""
    write_rules(scratch, "valuation-methods.yaml", {"something_else": DESIGN_ROUTING})
    with pytest.raises(ValuationError):
        load_method_routing(scratch)


def test_route_method_registered_and_unregistered() -> None:
    """`Ch5 §D.1` 末句：未注册类型归入 `generic` **并标注**。"""
    route = route_method("hardware", DESIGN_ROUTING)
    assert route.registered is True
    assert route.method_classes == DESIGN_ROUTING["hardware"]

    fallback = route_method("quantum_computing", DESIGN_ROUTING)
    assert fallback.method_class == DEFAULT_METHOD_CLASS
    assert fallback.registered is False
    assert "UNREGISTERED_MODEL_CLASS" in fallback.note


def test_route_method_rejects_tbd_model_class() -> None:
    """`model_class = tbd` 不可路由（占位值不是商业模式）。"""
    with pytest.raises(ValuationError):
        route_method("tbd", DESIGN_ROUTING)


# ───────────────────── §D.2 追溯链（operand 可达） ─────────────────────


def _chain() -> dict[str, _FakeDerived]:
    return {
        "dv-price-low": _FakeDerived("dv-price-low", "equity / shares * m", ["dv-eps", "dv-shares"]),
        "dv-eps": _FakeDerived("dv-eps", "net_income / shares", ["claim-net-income"]),
        "dv-shares": _FakeDerived("dv-shares", "shares_raw", ["shares-raw-ref"]),
    }


def test_traceability_chain_is_walkable_to_terminal_inputs() -> None:
    """★ `Ch5 §D.2`：price range → formula/operands，一路可追到**终端输入**。"""
    result = assert_traceability(
        "dv-price-low",
        _resolve_factory(_chain()),
        max_depth=3,
        required_refs=["claim-net-income"],
    )
    assert result.covers("claim-net-income"), "必须能追到第四章的 claim（链的终端）"
    assert result.covers("shares-raw-ref")
    assert result.truncated is False
    assert result.cycle_detected is False


def test_traceability_missing_formula_on_chain_is_rejected() -> None:
    """`Ch9 §3.4.4`：链上节点缺 `formula` ⇒ 追不到"怎么算的" → 拒绝。"""
    chain = _chain()
    chain["dv-eps"] = _FakeDerived("dv-eps", "", ["claim-net-income"])
    with pytest.raises(ValuationError):
        assert_traceability("dv-price-low", _resolve_factory(chain), max_depth=3)


def test_traceability_cycle_is_rejected() -> None:
    """operand 自引用（环）⇒ 链追不到头 → 拒绝。"""
    chain = {
        "dv-a": _FakeDerived("dv-a", "f", ["dv-b"]),
        "dv-b": _FakeDerived("dv-b", "g", ["dv-a"]),
    }
    result = trace_derived_chain("dv-a", _resolve_factory(chain), max_depth=5)
    assert result.cycle_detected is True
    with pytest.raises(ValuationError):
        assert_traceability("dv-a", _resolve_factory(chain), max_depth=5)


def test_traceability_too_deep_chain_is_rejected() -> None:
    """链比 `max_depth` 更深 ⇒ `truncated`（追不到终端）→ 拒绝。"""
    chain = {
        f"dv-{i}": _FakeDerived(f"dv-{i}", "f", [f"dv-{i + 1}"]) for i in range(5)
    }
    chain["dv-5"] = _FakeDerived("dv-5", "f", ["claim-x"])
    with pytest.raises(ValuationError):
        assert_traceability("dv-0", _resolve_factory(chain), max_depth=2)
    # 反向对照：同一链放到足够深度 → 放行
    assert_traceability("dv-0", _resolve_factory(chain), max_depth=6)


def test_traceability_required_ref_absent_is_rejected() -> None:
    """必需引用不在链上 ⇒ 问不到"这个价格区间从哪来" → 拒绝。"""
    with pytest.raises(ValuationError):
        assert_traceability(
            "dv-price-low",
            _resolve_factory(_chain()),
            max_depth=3,
            required_refs=["driver-gpu-shipments"],
        )


# ───────────────────── §D.3 顺序约束 + §D.6 概率 ─────────────────────


def _params(**overrides: object) -> ValuationParams:
    base: dict[str, object] = {
        "enterprise_value": Decimal("1000"),
        "net_debt": Decimal("200"),
        "shares_outstanding": Decimal("100"),
        "low_multiple": Decimal("10"),
        "high_multiple": Decimal("15"),
        "operands": ("baseline-1", "shares-1"),
        "method_class": "normalized_earnings",
    }
    base.update(overrides)
    return ValuationParams(**base)  # type: ignore[arg-type]


def test_compute_valuation_sets_traceable_formula_ref_and_range() -> None:
    """`Ch5 §D.2` / `§D.6`：区间 + `formula_ref`（指向 `DerivedValue`）+ 概率默认空。"""
    valuation = compute_valuation(
        BaselineVersionRef("baseline-1", BASELINE_AT), _params(), compute_time=COMPUTE_AT
    )
    assert valuation.range.low == Decimal("80")
    assert valuation.range.high == Decimal("120")
    assert valuation.formula_ref.startswith("dv-value_per_share_low-"), valuation.formula_ref
    assert valuation.probability is None, "§D.6：概率默认 null"


def test_compute_valuation_rejects_reversed_version_order() -> None:
    """`Ch5 §D.3` 逐字单测：baseline 版本时间晚于 `compute_time` → `OrderViolation`。"""
    with pytest.raises(OrderViolation):
        compute_valuation(
            BaselineVersionRef("baseline-1", datetime(2026, 9, 20, tzinfo=timezone.utc)),
            _params(),
            compute_time=COMPUTE_AT,
        )


def test_reverse_control_correct_order_computes() -> None:
    """反向对照：顺序正确 → 正常算出（不误伤）。"""
    valuation = compute_valuation(
        BaselineVersionRef("baseline-1", BASELINE_AT), _params(), compute_time=COMPUTE_AT
    )
    assert valuation.range.low is not None


def test_compute_valuation_requires_explicit_compute_time() -> None:
    """时间契约必须显式（`§D.3`：不得默认当前时间，否则倒填不可检）。"""
    from scripts.compute.contract import MissingInput

    with pytest.raises(MissingInput):
        compute_valuation(BaselineVersionRef("baseline-1", BASELINE_AT), _params(), compute_time=None)


def test_compute_valuation_rejects_probability_without_basis() -> None:
    """`Ch5 §J9` / B11：概率非空必须有依据（沿用 `scenario_guard` 的唯一判定）。"""
    from scripts.pricelayer import ProbabilityWithoutBasis

    with pytest.raises(ProbabilityWithoutBasis):
        compute_valuation(
            BaselineVersionRef("baseline-1", BASELINE_AT),
            _params(probability=Decimal("0.6")),
            compute_time=COMPUTE_AT,
        )


# ───────────────────── CLI：注入违例 → exit 非零 + 反向对照 ─────────────────────


def _baseline(baseline_id: str, valuation: dict[str, object]) -> dict[str, object]:
    return {"baseline_id": baseline_id, "version": 1, "business_mechanism": "x", "valuation": valuation}


def test_cli_rejects_valuation_without_formula_ref(
    scratch: Path, write_jsonl, write_rules, run_script
) -> None:
    """★ 注入违例：有价格区间但 `formula_ref=tbd` → CLI **exit 1**（`Ch5 §D.2`）。"""
    write_rules(scratch, "valuation-methods.yaml", {METHOD_ROUTING_KEY: DESIGN_ROUTING})
    write_jsonl(
        scratch,
        "baselines",
        [_baseline("b1", {"range": {"low": "80", "high": "120"}, "formula_ref": "tbd", "method_class": "x"})],
    )
    proc = run_script("scripts/pricelayer/valuation.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "VALUATION-TRACE-MISSING" in proc.stdout


def test_cli_rejects_unresolvable_formula_ref(
    scratch: Path, write_jsonl, write_rules, run_script
) -> None:
    """注入违例：`formula_ref` 指向 `derived/` 里不存在的记录 → exit 1（链断）。"""
    write_rules(scratch, "valuation-methods.yaml", {METHOD_ROUTING_KEY: DESIGN_ROUTING})
    write_jsonl(
        scratch,
        "baselines",
        [_baseline("b1", {"range": {"low": "80", "high": "120"}, "formula_ref": "dv-nope", "method_class": "x"})],
    )
    proc = run_script("scripts/pricelayer/valuation.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "VALUATION-TRACE-UNRESOLVED" in proc.stdout


def test_cli_rejects_unregistered_method_class(
    scratch: Path, write_jsonl, write_rules, run_script
) -> None:
    """注入违例：`method_class` 既不在路由表、也不是 `generic` → exit 1（`Ch5 §D.1`）。"""
    write_rules(scratch, "valuation-methods.yaml", {METHOD_ROUTING_KEY: DESIGN_ROUTING})
    write_jsonl(
        scratch,
        "baselines",
        [_baseline("b1", {"range": {"low": "80", "high": "120"}, "formula_ref": "dv-1", "method_class": "magic"})],
    )
    proc = run_script("scripts/pricelayer/valuation.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "VALUATION-METHOD-UNREGISTERED" in proc.stdout


def test_reverse_control_cli_passes_with_resolvable_chain(
    scratch: Path, write_jsonl, write_derived_jsonl, real_rules, run_script
) -> None:
    """反向对照：链可解析 + 方法已注册 → **exit 0**。

    ★ 用**真** `rules/valuation-methods.yaml`（含 `method_routing` / `unregistered_fallback` /
      `valuation_compute`）；用旧的"只写 `method_routing`"的手写半截夹具会漏掉规则绑定判据，
      正是 `G-43`/`G-45` 的病灶（夹具形状真文件写不出来）。
    """
    real_rules(scratch, "valuation-methods.yaml")
    write_jsonl(
        scratch,
        "baselines",
        [
            _baseline(
                "b1",
                {"range": {"low": "80", "high": "120"}, "formula_ref": "dv-1", "method_class": "正常化利润"},
            )
        ],
    )
    write_derived_jsonl(
        scratch,
        [
            {
                "derived_id": "dv-1",
                "value": "80",
                "formula": "a / b",
                "operands": ["a"],
                "method_version": "v1",
                "computed_at": "2026-09-15T12:00:00+00:00",
            }
        ],
    )
    proc = run_script("scripts/pricelayer/valuation.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RESULT: PASS" in proc.stdout
    assert "VALUATION-RULE-BINDING" not in proc.stdout


def test_cli_flags_partial_handwritten_rule_missing_bound_keys(
    scratch: Path, write_jsonl, write_derived_jsonl, write_rules, run_script
) -> None:
    """★ 注入违例：手写半截规则文件（只给 `method_routing`）→ **exit 1**。

    该判据正是"夹具与真文件不同源"的守卫：真文件里的 3 个键必须都在。
    """
    write_rules(scratch, "valuation-methods.yaml", {METHOD_ROUTING_KEY: DESIGN_ROUTING})
    write_jsonl(
        scratch,
        "baselines",
        [
            _baseline(
                "b1",
                {"range": {"low": "80", "high": "120"}, "formula_ref": "dv-1", "method_class": "normalized_earnings"},
            )
        ],
    )
    write_derived_jsonl(
        scratch,
        [
            {
                "derived_id": "dv-1",
                "value": "80",
                "formula": "a / b",
                "operands": ["a"],
                "method_version": "v1",
                "computed_at": "2026-09-15T12:00:00+00:00",
            }
        ],
    )
    proc = run_script("scripts/pricelayer/valuation.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "VALUATION-RULE-BINDING" in proc.stdout


def test_cli_notes_when_rule_file_absent_but_still_flags_trace(
    scratch: Path, write_jsonl, run_script
) -> None:
    """规则文件未安装时：判据③记 note（不可判定），但**追溯链判据仍然生效**。"""
    write_jsonl(
        scratch,
        "baselines",
        [_baseline("b1", {"range": {"low": "80", "high": "120"}, "formula_ref": "tbd", "method_class": "x"})],
    )
    proc = run_script("scripts/pricelayer/valuation.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "NO_VALUATION_METHODS_RULE" in proc.stdout
    assert "VALUATION-TRACE-MISSING" in proc.stdout


# ───────── 规则↔代码绑定：**在真 rules/valuation-methods.yaml 上**（防 G-43/G-45 同族病）─────────


def test_real_rules_routing_matches_team_lead_measured_values(scratch: Path, real_rules) -> None:
    """★ 在**真文件**上核路由真值（不是在手写夹具上）：4 个 `model_class` 及其方法类逐字。

    真值（`ws-ch2-rules` 安装件 `bb32863`，本卡在主干实测复核）：
    `hardware`→4 / `cloud`→2 / `software`→3 / `etf`→1。
    """
    real_rules(scratch, "valuation-methods.yaml")
    routing = load_method_routing(scratch)
    assert sorted(routing) == ["cloud", "etf", "hardware", "software"]
    assert routing["hardware"] == ("正常化利润", "含再投资现金流", "分部估值", "同行比较")
    assert routing["cloud"] == ("含再投资现金流（订阅/用量）", "分部")
    assert routing["software"] == ("正常化利润", "现金流", "留存指标")
    assert routing["etf"] == ("简化底稿",)
    assert METHOD_ROUTING_KEY in {"method_routing"}, "真文件里的键名即 method_routing"


def test_real_rules_unregistered_fallback_matches_code_defaults(
    scratch: Path, real_rules
) -> None:
    """★ 未注册回落口径**读**真文件，且与代码默认值一致（`Ch5 §D.1` 末句 / `Ch11 §D.2`）。

    ★ 主理人裁定 ③-2：`value_source == "rules"`（读到真值）＋ `notes` 为空（无回落）。
    """
    from scripts.pricelayer.valuation import DEFAULT_UNREGISTERED_MARK, load_unregistered_fallback

    real_rules(scratch, "valuation-methods.yaml")
    spec = load_unregistered_fallback(scratch)
    assert spec.method_class == "generic" == DEFAULT_METHOD_CLASS
    assert spec.mark == "unregistered" == DEFAULT_UNREGISTERED_MARK
    assert spec.value_source == "rules"
    assert spec.notes == ()


def test_unregistered_fallback_fallback_records_source_and_note(scratch: Path) -> None:
    """★ 裁定 ③-1/③-2：缺文件 ⇒ `design_default` **且必带 note**（写明缺的是哪个文件）。"""
    from scripts.pricelayer.valuation import (
        DEFAULT_METHOD_CLASS,
        DEFAULT_UNREGISTERED_MARK,
        load_unregistered_fallback,
    )

    spec = load_unregistered_fallback(scratch)          # scratch 里没有 rules/
    assert spec.value_source == "design_default"
    assert spec.notes, "design_default 必须打 note（否则单独特调看不出'缺键'）"
    assert "valuation-methods.yaml" in spec.notes[0]
    assert spec.method_class == DEFAULT_METHOD_CLASS
    assert spec.mark == DEFAULT_UNREGISTERED_MARK


def test_unregistered_fallback_partial_key_records_note(scratch: Path, real_rules) -> None:
    """★ 裁定 ③-2：键在但子键缺 ⇒ `value_source` 仍 `rules` **且** note 点名缺失子键。"""
    import yaml

    from scripts.pricelayer.valuation import load_unregistered_fallback

    real_rules(scratch, "valuation-methods.yaml")
    path = scratch / "rules" / "valuation-methods.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["unregistered_fallback"] = {"mark": "unregistered"}
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")

    spec = load_unregistered_fallback(scratch)
    assert spec.value_source == "rules"
    assert any("method_class" in n for n in spec.notes), spec.notes
    assert spec.method_class == "generic", "缺失子键取设计逐字回落值"


def test_real_rules_route_method_on_real_values(scratch: Path, real_rules) -> None:
    """在**真路由表**上：已注册 `model_class` 取到真方法类；未注册走真回落口径。"""
    real_rules(scratch, "valuation-methods.yaml")
    routing = load_method_routing(scratch)
    spec = load_unregistered_fallback(scratch)
    fallback, mark = spec.method_class, spec.mark

    hw = route_method("hardware", routing, fallback_method_class=fallback, fallback_mark=mark)
    assert hw.registered is True
    assert hw.method_classes == routing["hardware"]
    assert hw.method_class == "正常化利润"

    unknown = route_method("biotech", routing, fallback_method_class=fallback, fallback_mark=mark)
    assert unknown.registered is False
    assert unknown.method_class == "generic"
    assert mark in unknown.note


def test_rule_binding_violation_on_renamed_entry(scratch: Path, write_jsonl, real_rules, run_script) -> None:
    """★ 注入违例：真规则文件声明的方法类改了而代码没改 → CLI **exit 1**（防声明与实现脱节）。"""
    import yaml

    real_rules(scratch, "valuation-methods.yaml")
    path = scratch / "rules" / "valuation-methods.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["unregistered_fallback"]["method_class"] = "misc"
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/valuation.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "VALUATION-RULE-BINDING" in proc.stdout


def test_rule_binding_violation_on_unknown_declared_entry(
    scratch: Path, write_jsonl, real_rules, run_script
) -> None:
    """★ 注入违例：规则文件声明的 `valuation_compute.entry` 在本模块内不存在 → exit 1。"""
    import yaml

    real_rules(scratch, "valuation-methods.yaml")
    path = scratch / "rules" / "valuation-methods.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["valuation_compute"]["entry"] = "compute_value_renamed"
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/valuation.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "VALUATION-RULE-BINDING" in proc.stdout


def test_reverse_control_cli_passes_on_real_rules_file(
    scratch: Path, write_jsonl, write_derived_jsonl, real_rules, run_script
) -> None:
    """反向对照：真规则文件 + 合规估值（`method_class` 取真值）→ exit 0。"""
    real_rules(scratch, "valuation-methods.yaml")
    write_derived_jsonl(
        scratch,
        [
            {
                "derived_id": "dv-1",
                "value": "100",
                "formula": "a / b",
                "operands": ["a"],
                "method_version": "v1",
                "computed_at": "2026-09-15T12:00:00+00:00",
            }
        ],
    )
    write_jsonl(
        scratch,
        "baselines",
        [_baseline("b1", {"range": {"low": "80", "high": "120"}, "formula_ref": "dv-1", "method_class": "正常化利润"})],
    )
    proc = run_script("scripts/pricelayer/valuation.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RESULT: PASS" in proc.stdout


def test_cli_reports_fallback_source_even_without_baselines(scratch: Path, run_script) -> None:
    """★ 裁定 ③-2 的**出口面** + 防"早退吞 note"：`facts/baselines.jsonl` 为空**也必须**
    在 report 里看到"未注册回落口径来自设计回落、不是规则"。

    ★ 这条是**真实缺陷的回归锁**：首版把 `load_unregistered_fallback` 放在
      `if not baselines: return report` **之后** ⇒ 没数据时该 note 永不出现，
      "值来自回落"这件事在出口面被静默吞掉（正是 `G-03` / 静默降级同族）。
    """
    path = scratch / "facts" / "baselines.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")            # 空样本
    proc = run_script("scripts/pricelayer/valuation.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "unregistered_fallback_value_source: 0" in proc.stdout
    assert "NO_UNREGISTERED_FALLBACK" in proc.stdout
    assert "NO_BASELINE_ROWS" in proc.stdout, "早退 note 仍须在（两者不可互相顶掉）"


# ── 第四轮：**缺子键 ≠ 无可比对象**（`valuation_compute.entry` 被删也必须是红）──


def test_missing_valuation_compute_entry_is_flagged(
    scratch: Path, real_rules, run_script
) -> None:
    """★ 第四轮反例：**删** `valuation_compute.entry` ⇒ 必须 `exit 1`。

    旧写法 `if declared and declared not in globals()` 在缺键时 `declared == ""` ⇒
    **静默跳过**（"无可比对象"）⇒ "规则文件声明的入口"这一事实从规则面消失而门禁全绿。
    真文件里该键**存在**（`compute_valuation`），故缺键即"声明与实现脱节"（`Ch11 §D.2`）。
    """
    import yaml

    real_rules(scratch, "valuation-methods.yaml", "scenario.yaml")
    path = scratch / "rules" / "valuation-methods.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["valuation_compute"].pop("entry")
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/valuation.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "VALUATION-RULE-BINDING" in proc.stdout
    assert "valuation_compute.entry 缺失" in proc.stdout
