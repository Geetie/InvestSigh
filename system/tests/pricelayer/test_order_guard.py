"""`order_guard` 单测（`Ch5 §B.5` 反解不得回灌 + `§D.3/§D.4` 顺序与倒填四规则）。

覆盖 DoD：「`order_guard` 四规则逐条有正反用例；倒填被拒（贴真实输出）」
+ 「每个守卫**注入违例 → exit 非零**」+ 反向对照。

★ `Ch5 §B.5` 的单测要求**逐字**："构造一个 `source=implied_solution` 的假设写入
  `baselines.driver_model` → 断言被 `OrderViolation` 拒绝；反解输出**只允许**写
  `implied_requirements` 或 `gap`"。
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.compute.contract import MissingInput, OrderViolation
from scripts.pricelayer.order_guard import (
    ALLOWED_IMPLIED_WRITE_TARGETS,
    FORBIDDEN_BASELINE_SOURCES,
    RULE_BOUNDARY_TUNED_PARAM,
    RULE_MANUAL_WITHOUT_HISTORY,
    RULE_PARAM_MODIFIED_AFTER_ISSUE,
    BackfillReport,
    OrderGuardError,
    ParamObservation,
    RecommendationContext,
    assert_baseline_source_ok,
    assert_version_order,
    assert_write_target_allowed,
    detect_backfill,
)

BASELINE_AT = datetime(2026, 8, 1, tzinfo=timezone.utc)
COMPUTE_AT = datetime(2026, 9, 10, tzinfo=timezone.utc)
ISSUED_AT = datetime(2026, 9, 5, tzinfo=timezone.utc)


# ───────────────────── §B.5 反解不得回灌 baseline ─────────────────────


def test_implied_solution_source_is_rejected() -> None:
    """★ `Ch5 §B.5` 逐字单测：`source=implied_solution` → `OrderViolation`。"""
    with pytest.raises(OrderViolation):
        assert_baseline_source_ok({"source": "implied_solution"})


def test_implied_requirements_source_is_rejected() -> None:
    """同样禁用集合里的第二个 token（`implied_requirements`）。"""
    with pytest.raises(OrderViolation):
        assert_baseline_source_ok({"source": "implied_requirements"})
    assert FORBIDDEN_BASELINE_SOURCES == frozenset({"implied_solution", "implied_requirements"})


def test_reverse_control_legitimate_source_passes() -> None:
    """反向对照：`model_estimate`（模型产出假设）**放行**（守卫不是恒红）。"""
    assert_baseline_source_ok({"source": "model_estimate"})
    assert_baseline_source_ok({"source": "fact"})


def test_undeclared_source_is_rejected() -> None:
    """不声明来源的假设不得冒充"可入 baseline"（`Ch5 §D.5` 三类来源分开存）。"""
    with pytest.raises(OrderGuardError):
        assert_baseline_source_ok({"source": ""})
    with pytest.raises(OrderGuardError):
        assert_baseline_source_ok({"source": None})


def test_write_target_allowlist_is_ch5_b5_verbatim() -> None:
    """`Ch5 §B.5` 逐字：反解输出**只允许**写 `implied_requirements` 或 `gap`。"""
    assert ALLOWED_IMPLIED_WRITE_TARGETS == frozenset({"implied_requirements", "gap"})
    assert_write_target_allowed("implied_requirements")
    assert_write_target_allowed("gap")
    with pytest.raises(OrderGuardError):
        assert_write_target_allowed("baselines")      # ← 回灌 baseline 的写目标
    with pytest.raises(OrderGuardError):
        assert_write_target_allowed("recommendations")


# ───────────────────── §D.4 规则①：参数后改 ─────────────────────


def _param(**overrides: object) -> ParamObservation:
    base: dict[str, object] = {
        "name": "wacc",
        "value": Decimal("0.09"),
        "decision_threshold": None,
        "modified_at": None,
        "input_source": "model_estimate",
        "change_records": (),
    }
    base.update(overrides)
    return ParamObservation(**base)  # type: ignore[arg-type]


def test_rule1_param_modified_after_issue_is_suspicious() -> None:
    report = detect_backfill(
        [_param(modified_at=datetime(2026, 9, 8, tzinfo=timezone.utc))],
        subject="baseline-1",
        sensitivity_threshold=Decimal("0"),
        boundary_margin=Decimal("0"),
        recommendation=RecommendationContext("REC-1", ISSUED_AT),
    )
    assert any(f.rule == RULE_PARAM_MODIFIED_AFTER_ISSUE for f in report.suspicious)


def test_reverse_control_rule1_param_modified_before_issue_passes() -> None:
    """反向对照：参数在建议**之前**改 → 不标可疑。"""
    report = detect_backfill(
        [_param(modified_at=datetime(2026, 9, 1, tzinfo=timezone.utc))],
        subject="baseline-1",
        sensitivity_threshold=Decimal("0"),
        boundary_margin=Decimal("0"),
        recommendation=RecommendationContext("REC-1", ISSUED_AT),
    )
    assert not report.suspicious


def test_rule1_without_recommendation_is_noted_not_silently_passed() -> None:
    """`G-03`：无建议上下文 ⇒ **不可判定**，必须显式记 note（不得当"已验证"）。"""
    report = detect_backfill(
        [_param(modified_at=datetime(2026, 9, 8, tzinfo=timezone.utc))],
        subject="baseline-1",
        sensitivity_threshold=Decimal("0"),
        boundary_margin=Decimal("0"),
        recommendation=None,
    )
    assert report.suspicious == []
    assert any("NO_RECOMMENDATION_CONTEXT" in n for n in report.notes)


# ───────────────────── §D.4 规则②：临界凑值 ─────────────────────


def _boundary_param(*, value: str, threshold: str) -> ParamObservation:
    return _param(
        name="growth",
        value=Decimal(value),
        decision_threshold=Decimal(threshold),
        low_param=Decimal("0.10"),
        high_param=Decimal("0.12"),
        conclusion_at_low=Decimal("0.20"),
        conclusion_at_high=Decimal("0.40"),
    )


def test_rule2_boundary_tuned_param_requires_sensitivity_disclosure() -> None:
    """`Ch5 §D.4` 规则②：高敏感 + 刚好跨阈值 → 可疑，**且要求敏感性披露**。"""
    report = detect_backfill(
        [_boundary_param(value="0.1005", threshold="0.10")],
        subject="baseline-1",
        sensitivity_threshold=Decimal("5"),      # 斜率 = (0.40-0.20)/(0.12-0.10) = 10 ≥ 5
        boundary_margin=Decimal("0.001"),
    )
    boundary = [f for f in report.suspicious if f.rule == RULE_BOUNDARY_TUNED_PARAM]
    assert boundary, "应判为临界凑值"
    assert boundary[0].requires_sensitivity is True, "规则②的处置是**要求敏感性披露**"


def test_reverse_control_rule2_far_from_threshold_passes() -> None:
    """反向对照：参数离阈值很远 → 不标可疑。"""
    report = detect_backfill(
        [_boundary_param(value="0.1500", threshold="0.10")],
        subject="baseline-1",
        sensitivity_threshold=Decimal("5"),
        boundary_margin=Decimal("0.001"),
    )
    assert not report.suspicious


def test_reverse_control_rule2_low_sensitivity_passes() -> None:
    """反向对照：结论对该参数**不敏感**（斜率低于阈值）→ 不标可疑。"""
    report = detect_backfill(
        [_boundary_param(value="0.1005", threshold="0.10")],
        subject="baseline-1",
        sensitivity_threshold=Decimal("50"),     # 斜率 10 < 50
        boundary_margin=Decimal("0.001"),
    )
    assert not report.suspicious


# ───────────────────── §D.4 规则③：无历史假设 ─────────────────────


def test_rule3_manual_without_history_is_suspicious() -> None:
    report = detect_backfill(
        [_param(input_source="manual", change_records=())],
        subject="baseline-1",
        sensitivity_threshold=Decimal("0"),
        boundary_margin=Decimal("0"),
    )
    assert any(f.rule == RULE_MANUAL_WITHOUT_HISTORY for f in report.suspicious)


def test_reverse_control_rule3_manual_with_history_passes() -> None:
    """反向对照：人工设定**有**变更记录 → 不标可疑（可复核）。"""
    report = detect_backfill(
        [_param(input_source="manual", change_records=("2026-09-01 改为 0.09",))],
        subject="baseline-1",
        sensitivity_threshold=Decimal("0"),
        boundary_margin=Decimal("0"),
    )
    assert not report.suspicious


def test_reverse_control_rule3_model_estimate_without_history_passes() -> None:
    """反向对照：非人工来源且无变更记录 → 规则③不适用（它的判据含 `manual`）。"""
    report = detect_backfill(
        [_param(input_source="model_estimate", change_records=())],
        subject="baseline-1",
        sensitivity_threshold=Decimal("0"),
        boundary_margin=Decimal("0"),
    )
    assert not report.suspicious


# ───────────────────── §D.4 规则④：版本倒序（拒绝） ─────────────────────


def test_rule4_version_reversed_is_rejected() -> None:
    """`Ch5 §D.4` 规则④：baseline 版本时间**晚于**估值时间 → **拒绝**（`OrderViolation`）。"""
    with pytest.raises(OrderViolation):
        assert_version_order(
            datetime(2026, 9, 20, tzinfo=timezone.utc),
            COMPUTE_AT,
            subject="baseline-1",
        )


def test_reverse_control_rule4_correct_order_passes() -> None:
    assert_version_order(BASELINE_AT, COMPUTE_AT, subject="baseline-1")  # 不抛即通过


def test_rule4_missing_time_is_gap_not_silent_pass() -> None:
    """时间契约必须显式（缺 → `MissingInput`），否则倒填不可检（`Ch5 §D.3`）。"""
    with pytest.raises(MissingInput):
        assert_version_order(None, COMPUTE_AT, subject="baseline-1")


def test_empty_params_reports_note_not_pass() -> None:
    """`G-03`：空参数表 ⇒ 规则①②③**不可判定**，必须记 note。"""
    report = detect_backfill(
        [],
        subject="baseline-1",
        sensitivity_threshold=Decimal("0.02"),
        boundary_margin=Decimal("0.01"),
    )
    assert isinstance(report, BackfillReport)
    assert report.suspicious == []
    assert any("NO_PARAM_OBSERVATIONS" in n for n in report.notes)
    assert any("NO_TIME_PAIR" in n for n in report.notes)


# ───────────────────── CLI：注入违例 → exit 非零 + 反向对照 ─────────────────────


def _baseline(baseline_id: str, *, formula_ref: str = "dv-x") -> dict[str, object]:
    return {
        "baseline_id": baseline_id,
        "version": 1,
        "business_mechanism": "x",
        "valuation": {"formula_ref": formula_ref, "forecast_assumptions": [], "valuation_params": []},
        "driver_model": [],
    }


def test_cli_rejects_baseline_referencing_implied_output(
    scratch: Path, write_jsonl, run_script
) -> None:
    """★ 注入违例：`baselines` 的估值输入引用了反解 id → CLI **exit 1**（`Ch5 §B.5`）。"""
    write_jsonl(
        scratch,
        "implied_requirements",
        [
            {"implied_id": "IMP-001", "solution_set_id": "SET-1", "feasible": True},
            {"implied_id": "IMP-002", "solution_set_id": "SET-1", "feasible": True},
        ],
    )
    write_jsonl(scratch, "baselines", [_baseline("baseline-1", formula_ref="IMP-001")])
    proc = run_script("scripts/pricelayer/order_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "ORDER-BACKFILL" in proc.stdout


def test_cli_rejects_single_solution_set_too(scratch: Path, write_jsonl, run_script) -> None:
    """多解不变式也在本守卫里（`Ch5 §B.1`）：单解解集 → exit 1。"""
    write_jsonl(
        scratch,
        "implied_requirements",
        [{"implied_id": "IMP-001", "solution_set_id": "SET-1", "feasible": True}],
    )
    proc = run_script("scripts/pricelayer/order_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "solution_set" in proc.stdout


def test_reverse_control_cli_passes_when_no_backfill(
    scratch: Path, write_jsonl, run_script
) -> None:
    """反向对照：baseline 引用的是普通 DerivedValue，且解集多解 → **exit 0**。"""
    write_jsonl(
        scratch,
        "implied_requirements",
        [
            {"implied_id": "IMP-001", "solution_set_id": "SET-1", "feasible": True},
            {"implied_id": "IMP-002", "solution_set_id": "SET-1", "feasible": True},
        ],
    )
    write_jsonl(scratch, "baselines", [_baseline("baseline-1", formula_ref="dv-price-range")])
    proc = run_script("scripts/pricelayer/order_guard.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RESULT: PASS" in proc.stdout


# ── 第四轮订正：① 只数**可行**解 ② 下限**读规则** ③ 缺 `solution_set_id` **不再静默跳过** ──


def test_infeasible_rows_do_not_count_toward_multi_solution(
    scratch: Path, write_jsonl, run_script
) -> None:
    """★ 反例①：同解集里 1 行 `feasible=true` + 1 行 `feasible=false` ⇒ 仍**单解** ⇒ exit 1。

    旧实现数**全部**行 ⇒ 把"1 组可行解 + 1 组不可行"算成 2 组 ⇒ **漏报**；
    且与 `solver.check` 的同名判据（只数 `feasible`）**口径冲突** —— 同一不变式不能两个口径。
    """
    write_jsonl(
        scratch,
        "implied_requirements",
        [
            {"implied_id": "IMP-001", "solution_set_id": "SET-1", "feasible": True},
            {"implied_id": "IMP-002", "solution_set_id": "SET-1", "feasible": False},
        ],
    )
    proc = run_script("scripts/pricelayer/order_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "只有 1 组**可行**解" in proc.stdout
    assert "IMPLIED_INFEASIBLE_ROWS" in proc.stdout, "被排除的行必须**计数可见**（不静默）"


def test_row_missing_solution_set_id_is_flagged(
    scratch: Path, write_jsonl, run_script
) -> None:
    """★ 反例③：有行**缺必填 `solution_set_id`** ⇒ exit 1（旧实现 `continue` 静默跳过）。

    `schema.models.ImpliedRequirement.solution_set_id` 是**必填**字段（无默认值）⇒
    缺它 = 脏数据，且那些行**落在多解不变式之外**（判据对它们**没管**）。
    """
    write_jsonl(
        scratch,
        "implied_requirements",
        [
            {"implied_id": "IMP-001", "solution_set_id": "SET-1", "feasible": True},
            {"implied_id": "IMP-002", "solution_set_id": "SET-1", "feasible": True},
            {"implied_id": "IMP-003", "feasible": True},          # ← 缺必填键
        ],
    )
    proc = run_script("scripts/pricelayer/order_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "缺必填 `solution_set_id`" in proc.stdout


def test_multi_solution_lower_bound_follows_the_rule_key(
    scratch: Path, real_rules, write_jsonl, run_script
) -> None:
    """★ 反例②（行为绑定）：下限**读规则** —— `must_show_multiple: false` ⇒ 下限降为 1 ⇒ 单解集**不再红**。

    这是 `Ch5 §B.1`「必须展示多组解」的**机械下限**在 `rules/` 里的唯一出处
    （`rules/valuation-methods.yaml::solution_set_display.must_show_multiple`）。
    旧实现硬编码 `count < 2` ⇒ 规则改了**代码不动**（`Ch11 §D.2` / `P-09`：
    「参数只能住 `rules/`，代码不得内置」；批 13 任务书方案②**也**明确要求删掉常量 `2`）。
    """
    import yaml

    real_rules(scratch, "valuation-methods.yaml")
    write_jsonl(
        scratch,
        "implied_requirements",
        [{"implied_id": "IMP-001", "solution_set_id": "SET-1", "feasible": True}],
    )
    # 真值（`must_show_multiple: true`）⇒ 下限 2 ⇒ 单解集是违例
    proc = run_script("scripts/pricelayer/order_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "下限 2" in proc.stdout

    path = scratch / "rules" / "valuation-methods.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["solution_set_display"]["must_show_multiple"] = False
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")

    # 规则改 ⇒ 行为必须跟着改：下限 1 ⇒ 同一份数据**放行**
    proc = run_script("scripts/pricelayer/order_guard.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RESULT: PASS" in proc.stdout


def test_row_missing_implied_id_is_flagged_even_without_baselines(
    scratch: Path, write_jsonl, run_script
) -> None:
    """★ 修 8：缺必填 `implied_id` 的行不得被**静默排除**出"反解 id 黑名单"。

    ★ 同时锁住**早退吞违例**这个形状：本用例**刻意不写 `baselines`** ⇒ 会走
      `if not (baselines and implied_ids): return` 分支；若把该违例放在早退之后，
      它就被**静默吞掉**（与 `valuation.check` 的 D-1 是同一形状的坑）。
    """
    write_jsonl(
        scratch,
        "implied_requirements",
        [
            {"implied_id": "IMP-001", "solution_set_id": "SET-1", "feasible": True},
            {"implied_id": "IMP-002", "solution_set_id": "SET-1", "feasible": True},
            {"solution_set_id": "SET-1", "feasible": True},          # ← 缺必填 implied_id
        ],
    )
    proc = run_script("scripts/pricelayer/order_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "缺必填 `implied_id`" in proc.stdout
