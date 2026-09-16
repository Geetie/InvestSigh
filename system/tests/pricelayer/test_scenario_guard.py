"""`scenario_guard` 单测（`Ch5 §D.6` 概率默认空 / `§E.3` 情景一致 / `§E.4` 状态 pending）。

覆盖 DoD：「`scenario_guard`：`probability` 缺省 = `null`（**有断言**）；情景不一致被拒」
+ 「注入违例 → exit 非零」+ 反向对照。
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from scripts.pricelayer import ProbabilityWithoutBasis, ScenarioMethodPending, ScenarioMismatch
from scripts.pricelayer.scenario_guard import (
    DEFAULT_SCENARIO_METHOD_STATUS,
    PROBABILITY_DEFAULT,
    SCENARIO_METHOD_STATUSES,
    ScenarioEstimate,
    ScenarioGuardError,
    ScenarioPolicy,
    ScenarioTag,
    assert_probability_has_basis,
    assert_relative_judgment_allowed,
    assert_scenario_match,
    load_scenario_policy,
)


# ───────────────────── §D.6：probability 默认 null ─────────────────────


def test_probability_default_is_none_not_fifty_fifty() -> None:
    """★ `Ch5 §D.6` 逐字断言：`probability` 默认 `null`（**不是 50/50**）。"""
    assert PROBABILITY_DEFAULT is None
    assert ScenarioEstimate(tag=ScenarioTag.neutral).probability is None


def test_probability_stays_none_when_not_provided_explicitly() -> None:
    """上/下行情景（`N5.3-05`："不含概率"）默认构造 → 概率仍为空。"""
    lower = ScenarioEstimate(tag=ScenarioTag.bear, range_low=Decimal("80"), range_high=Decimal("100"))
    upper = ScenarioEstimate(tag=ScenarioTag.bull, range_low=Decimal("120"), range_high=Decimal("150"))
    assert lower.probability is None and upper.probability is None


def test_probability_without_basis_is_rejected() -> None:
    """`Ch5 §J9` / B11：填概率但**无来源** → 拒绝（不得凭空给概率）。"""
    with pytest.raises(ProbabilityWithoutBasis):
        assert_probability_has_basis(Decimal("0.6"))


def test_probability_with_unresolvable_basis_is_rejected() -> None:
    """依据必须能解析到**真** `DerivedValue`（追不到 operand 的不算依据）。"""
    with pytest.raises(ProbabilityWithoutBasis):
        assert_probability_has_basis(Decimal("0.6"), basis_ref="dv-missing", resolve=lambda _ref: None)


def test_reverse_control_probability_with_real_derived_basis_passes() -> None:
    """反向对照：给了依据且解析到带 formula/operands 的 `DerivedValue` → **放行**。"""

    class _Fake:
        formula = "a / b"
        operands = ["a", "b"]

    assert_probability_has_basis(Decimal("0.6"), basis_ref="dv-1", resolve=lambda _ref: _Fake())


def test_reverse_control_none_probability_needs_no_basis() -> None:
    """反向对照：概率为空是**合法默认**（不需要依据）。"""
    assert_probability_has_basis(None)


# ───────────────────── §E.3：情景口径一致性 ─────────────────────


def test_scenario_mismatch_bull_vs_bear_is_rejected() -> None:
    """★ `Ch5 §E.3` 逐字单测：个股乐观 + 基准悲观 → `ScenarioMismatch`（`N5.4-08`）。"""
    with pytest.raises(ScenarioMismatch):
        assert_scenario_match(ScenarioTag.bull, ScenarioTag.bear)


def test_reverse_control_same_scenario_passes() -> None:
    """反向对照：两者同为中性 → 放行（`§E.3` 伪码 `return True`）。"""
    assert assert_scenario_match(ScenarioTag.neutral, ScenarioTag.neutral) is True
    assert assert_scenario_match("bull", "bull") is True


def test_unknown_scenario_tag_is_rejected() -> None:
    """`Ch5 §J4` 的标签集合是闭集（enum 全等判定，不是文本相似）。"""
    with pytest.raises(ScenarioGuardError):
        assert_scenario_match("optimistic", "bull")


# ───────────────────── §E.4：scenario_method_status ─────────────────────


def test_default_status_is_pending() -> None:
    """`Ch5 §E.4` 逐字：默认 `pending`（**不静默默认**成 neutral）。"""
    assert DEFAULT_SCENARIO_METHOD_STATUS == "pending"
    assert SCENARIO_METHOD_STATUSES == ("pending", "neutral", "probability_weighted")
    policy = load_scenario_policy(None)
    assert policy.status == "pending"
    assert policy.value_source == "design_default"


def test_pending_blocks_relative_judgment() -> None:
    """`Ch5 §E.4`：`pending` ⇒ **阻塞**相对判断生成（输出"待判断"而非建议）。"""
    with pytest.raises(ScenarioMethodPending):
        assert_relative_judgment_allowed(ScenarioPolicy(status="pending", value_source="rules"))


def test_reverse_control_neutral_allows_relative_judgment() -> None:
    """反向对照：`neutral` → 放行。"""
    assert_relative_judgment_allowed(
        ScenarioPolicy(status="neutral", value_source="rules", method_version="scenario-v1")
    )


def test_policy_reads_from_rules_scenario_yaml(scratch: Path, write_rules) -> None:
    """规则文件存在时按 `rules/scenario.yaml` 读（**唯一真源**），并记方法版本。"""
    write_rules(
        scratch,
        "scenario.yaml",
        {"scenario_method_status": "probability_weighted", "method_version": "scenario-v2"},
    )
    policy = load_scenario_policy(scratch)
    assert policy.status == "probability_weighted"
    assert policy.value_source == "rules"
    assert policy.method_version == "scenario-v2"


def test_illegal_status_value_is_rejected(scratch: Path, write_rules) -> None:
    """取值不在 `§E.4` 的三值域内 → 响亮失败（不许"未知状态当 pending 用"）。"""
    write_rules(scratch, "scenario.yaml", {"scenario_method_status": "maybe"})
    with pytest.raises(ScenarioGuardError):
        load_scenario_policy(scratch)


def test_missing_scenario_yaml_falls_back_to_design_default_with_note(scratch: Path) -> None:
    """文件缺失 ⇒ 按 `§E.4` 逐字默认 `pending`，但**显式标注来源**（不静默）。"""
    policy = load_scenario_policy(scratch)
    assert policy.status == "pending"
    assert policy.value_source == "design_default"
    assert any("NO_SCENARIO_YAML" in note for note in policy.notes)


# ───────────────────── CLI：注入违例 → exit 非零 + 反向对照 ─────────────────────


def _baseline_with_probability(baseline_id: str, *, probability: str | None, formula_ref: str) -> dict[str, object]:
    return {
        "baseline_id": baseline_id,
        "version": 1,
        "business_mechanism": "x",
        "valuation": {
            "probability": probability,
            "formula_ref": formula_ref,
            "range": {"low": "80", "high": "120"},
        },
    }


def test_cli_rejects_probability_without_formula_ref(
    scratch: Path, write_jsonl, run_script
) -> None:
    """★ 注入违例：填了概率却无依据 → CLI **exit 1**（`Ch5 §D.6` / `§J9` / B11）。"""
    write_jsonl(scratch, "baselines", [_baseline_with_probability("b1", probability="0.6", formula_ref="tbd")])
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "PROBABILITY-WITHOUT-BASIS" in proc.stdout


def test_cli_rejects_probability_basis_that_does_not_resolve(
    scratch: Path, write_jsonl, write_derived_jsonl, run_script
) -> None:
    """注入违例：依据 id 在 `derived/` 里**不存在** → exit 1（追溯链断）。"""
    write_jsonl(scratch, "baselines", [_baseline_with_probability("b1", probability="0.6", formula_ref="dv-nope")])
    write_derived_jsonl(
        scratch,
        [
            {
                "derived_id": "dv-other",
                "value": "1",
                "formula": "1",
                "operands": ["x"],
                "method_version": "v1",
                "computed_at": "2026-09-15T12:00:00+00:00",
            }
        ],
    )
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "PROBABILITY-BASIS-UNRESOLVED" in proc.stdout


def test_reverse_control_cli_passes_with_null_probability(
    scratch: Path, write_jsonl, run_script
) -> None:
    """反向对照：概率为空（设计常态）→ **exit 0**。"""
    write_jsonl(scratch, "baselines", [_baseline_with_probability("b1", probability=None, formula_ref="tbd")])
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "NO_PROBABILITY_FILLED" in proc.stdout


def test_reverse_control_cli_passes_with_resolvable_basis(
    scratch: Path, write_jsonl, write_derived_jsonl, run_script
) -> None:
    """反向对照：概率有依据且依据可解析 → exit 0。"""
    write_jsonl(scratch, "baselines", [_baseline_with_probability("b1", probability="0.6", formula_ref="dv-1")])
    write_derived_jsonl(
        scratch,
        [
            {
                "derived_id": "dv-1",
                "value": "0.6",
                "formula": "a / b",
                "operands": ["a", "b"],
                "method_version": "v1",
                "computed_at": "2026-09-15T12:00:00+00:00",
            }
        ],
    )
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
