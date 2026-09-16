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
    route_method,
    trace_derived_chain,
)

BASELINE_AT = datetime(2026, 8, 1, tzinfo=timezone.utc)
COMPUTE_AT = datetime(2026, 9, 10, tzinfo=timezone.utc)

#: `Ch5 §D.1` 的表内容（路由表的**内容**由设计给了；键名未给 ⇒ 见报告待裁定）。
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
    scratch: Path, write_jsonl, write_derived_jsonl, write_rules, run_script
) -> None:
    """反向对照：链可解析 + 方法已注册 → **exit 0**。"""
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
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RESULT: PASS" in proc.stdout


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
