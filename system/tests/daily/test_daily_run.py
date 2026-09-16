"""AC-5：**每日运行薄封装**的端到端 + 反 KPI 自测（`Ch1 §D.3` / `Ch8 §D/§E/§F`）。

锚点：`Ch1 §D.3`（反 KPI：**每天维护判断 ≠ 每天必须产生新买卖信号**）/
`Ch1 §D.1`（8 步闭环）/ `Ch8 §E`（降级可见）/ `Ch8 §N8.4-08`（同日重跑不重复产事件/建议）。

★ 反 KPI 自测：**无变化日 → `signals_emitted == 0`**、`changed is False`，且缺口
  （`gaps`）**如实报出**、不乐观改写。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from schema.models import Company
from schema.store import append_records, read_records
from scripts.daily import run as daily_run

_RUN_DAY = date(2026, 9, 16)


def _degraded_marks(root: Path) -> list[dict]:
    return [
        r
        for r in read_records(root, "tasks")
        if isinstance(r.get("parent_context"), dict) and r["parent_context"].get("degraded") is True
    ]


# ── 反 KPI：无变化日不得产信号，且如实报缺口 ────────────────────────────────

def test_no_change_day_emits_zero_signals(code_root: Path) -> None:
    report = daily_run.run_daily(code_root, _RUN_DAY)
    assert report.signals_emitted == 0
    assert report.changed is False


def test_report_is_faithful_not_optimistic(code_root: Path) -> None:
    """缺口（模型侧未实现）**如实**报出并置 blocked，不得被乐观改写为成功。"""
    report = daily_run.run_daily(code_root, _RUN_DAY)
    assert report.blocked is True
    assert len(report.gaps) > 0


# ── 降级：空真源 → 降级可见 + 保留上次有效结果（如实为空） ───────────────────

def test_degradation_is_visible_on_empty_truth(code_root: Path) -> None:
    report = daily_run.run_daily(code_root, _RUN_DAY)
    assert report.degraded is True
    assert report.degradation_visible is True
    assert report.degradation_task_id is not None
    assert report.last_valid_result_ref is None  # 首日降级：如实为空

    marks = _degraded_marks(code_root)
    assert len(marks) == 1
    assert marks[0]["parent_context"]["run_date"] == _RUN_DAY.isoformat()


# ── 幂等：同日重跑 N 次不重复产事件/建议，且运行记录幂等键唯一 ───────────────

def test_same_day_rerun_no_duplicate_events_or_recommendations(code_root: Path) -> None:
    for _ in range(3):
        report = daily_run.run_daily(code_root, _RUN_DAY)

    assert report.duplicate_events == ()
    assert report.duplicate_recommendations == ()
    assert len(read_records(code_root, "events")) == 0
    assert len(read_records(code_root, "recommendations")) == 0

    # 运行记录（check_record）追加式写入，但幂等键唯一（同日重跑用 `_r<n>` 修订号）
    keys = [
        r.get("idempotency_key")
        for r in read_records(code_root, "tasks")
        if str(r.get("idempotency_key", "")).startswith("check::")
    ]
    assert len(keys) == len(set(keys)), keys
    # 降级标记同日幂等：只落一条
    assert len(_degraded_marks(code_root)) == 1


# ── 覆盖可核（阶段④ 硬判据）在真实运行路径上生效 ────────────────────────────

def test_coverage_criterion_fires_on_run_path(code_root: Path) -> None:
    """空真源 → 覆盖目标集为空 → CV4（真空不得判过）命中 → `coverage_ok is False`。"""
    report = daily_run.run_daily(code_root, _RUN_DAY)
    assert report.coverage_ok is False
    assert any("CV4" in v for v in report.coverage_violations), report.coverage_violations


def test_coverage_ok_when_acceptance_input_is_covered(code_root: Path) -> None:
    append_records(
        code_root, "companies", [Company(company_id="c1", legal_name="C1")]
    )
    registry = code_root / "registry"
    registry.mkdir(parents=True, exist_ok=True)
    (registry / "acceptance_input_set.yaml").write_text(
        "first_list_version:\n  - c1\n", encoding="utf-8"
    )

    report = daily_run.run_daily(code_root, _RUN_DAY)
    assert report.coverage_ok is True, report.coverage_violations
