"""契约层单测（`Ch9 §3.4.4` / `§3.5` 阶段④）：`DerivedValue` 三要件、缺口对象、异常分派。

覆盖 AC-05（错误路径 → 缺口对象）/ AC-06（边界）/ AC-08（设计对齐：三要件必须齐）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from scripts.compute import contract
from scripts.compute.contract import (
    CaliberViolation,
    ComputeGap,
    MissingInput,
    UndefinedComputation,
    derived_id_for,
    gap_for,
    make_derived,
    require_nonzero,
    require_present,
    safe_compute,
)


def test_make_derived_requires_formula_operands_method_version() -> None:
    """`Ch9 §3.4.4`：`DerivedValue` **必须携带** formula + operands + method_version。"""
    with pytest.raises(CaliberViolation):
        make_derived("dv-x", Decimal("1"), "", ["op"], method_version="v1")
    with pytest.raises(CaliberViolation):
        make_derived("dv-x", Decimal("1"), "1+1", [], method_version="v1")
    with pytest.raises(CaliberViolation):
        make_derived("dv-x", Decimal("1"), "1+1", ["op"], method_version="")
    with pytest.raises(CaliberViolation):
        make_derived("", Decimal("1"), "1+1", ["op"], method_version="v1")


def test_make_derived_happy_path_carries_all_three() -> None:
    value = make_derived("dv-ok", Decimal("0.5"), "1/2", ["operand-1"], method_version="compute-v1")
    assert value.derived_id == "dv-ok"
    assert value.formula == "1/2"
    assert value.operands == ["operand-1"]
    assert value.method_version == "compute-v1"
    assert value.computed_at is not None


def test_derived_id_is_deterministic_for_same_inputs() -> None:
    """同 kind + 同 subject + 同 method_version → 同 id（幂等的基石）。"""
    assert derived_id_for("yoy", "sec_x") == derived_id_for("yoy", "sec_x")
    assert derived_id_for("yoy", "sec_x") != derived_id_for("yoy", "sec_y")


def test_require_present_lists_all_missing_names() -> None:
    with pytest.raises(MissingInput) as excinfo:
        require_present({"a": 1, "b": None}, ("a", "b", "c"), subject="subj")
    assert set(excinfo.value.missing) == {"b", "c"}
    assert excinfo.value.subject == "subj"


def test_require_nonzero_raises_undefined_not_zero_division() -> None:
    """除零 → 缺口类异常（**不是**裸 `ZeroDivisionError`），AC-06。"""
    with pytest.raises(UndefinedComputation):
        require_nonzero(Decimal(0), "shares", subject="subj")
    require_nonzero(Decimal("1"), "shares", subject="subj")  # 非零放行


def test_safe_compute_turns_missing_into_gap_object() -> None:
    """AC-05：输入缺失 → **缺口对象**（不置 null、不置 0）。"""
    outcome = safe_compute(
        lambda: (_ for _ in ()).throw(MissingInput("缺价格", missing=["prices"], subject="sec_x")),
        kind="total_return",
        subject="sec_x",
    )
    assert isinstance(outcome, ComputeGap)
    assert outcome.missing == ["prices"]
    assert outcome.subject == "sec_x"
    assert outcome.recorded_at is not None
    payload = outcome.to_dict()
    assert payload["gap_id"] == outcome.gap_id
    assert payload["missing"] == ["prices"]


def test_safe_compute_reraises_caliber_violation() -> None:
    """口径违例是**硬错误**，不得折叠成缺口吞掉（`G-06`：口径断言唯一真源）。"""
    with pytest.raises(CaliberViolation):
        safe_compute(
            lambda: (_ for _ in ()).throw(CaliberViolation("口径错")),
            kind="benchmark_return",
            subject="p01",
        )


def test_gap_for_never_emits_empty_missing() -> None:
    """缺口必有 `missing`（空表示这不是缺口）—— 防止"假装缺口"掩盖真 bug。"""
    gap = gap_for(MissingInput("随便", subject="s"), kind="x")
    assert gap.missing == ["<unspecified>"]


def test_compute_gap_to_dict_is_json_serializable() -> None:
    import json

    gap = ComputeGap(
        gap_id="dv-gap-x-v1",
        subject="x",
        missing=["prices"],
        reason="缺行情",
        method_version="compute-v1",
        recorded_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )
    payload = json.loads(json.dumps(gap.to_dict(), ensure_ascii=False))
    assert payload["recorded_at"].startswith("2026-09-16")


def test_method_version_constant_is_single_source() -> None:
    """方法版本唯一真源在 `contract.METHOD_VERSION`（`Ch9 §3.4.4`）。"""
    assert contract.METHOD_VERSION == "compute-v1"
