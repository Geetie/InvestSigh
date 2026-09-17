"""`tests/unit/test_traceback_coverage.py` —— `Ch10 §B.2` 六结果追溯覆盖率。

覆盖（`06_WS-F` 卡 DoD）：

- **AC-01 真跑通**：`six_results_complete` / `traceback_coverage_ok` 真被调用；
- **AC-04**：四要素缺环 ⇒ `TraceIncomplete`（**命中即 fail**，`Ch1 §F G1-03`）；
- **AC-05/06**：空样本 / 未知事件研究 / 空视图 ⇒ 明确拒绝或 `not_evaluated`，**不返假通过**；
- **复用而非新立**（`G-06`）：四要素覆盖率经 `Ch1 §E` 既有 `traceback()` / `traceback_coverage()`。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import run_gate_inproc
from scripts.trace.traceback_coverage import (
    SIX_RESULTS,
    TraceEvaluationGap,
    TraceIncomplete,
    check,
    four_elements_coverage,
    load_six_results_ref,
    missing_six_results,
    six_results_complete,
    traceback_coverage_ok,
    verify_hook_step8,
)

CLI = "scripts/trace/traceback_coverage.py"

_EVENT_STUDIES_REL = "views/event_studies.jsonl"

_DV_ID = "dv-nvda-dc-gross-margin-001"
_CLAIM_ID = "claim-nvidia-newsroom-q4-fy2025-4d13454fd859"


def _write_jsonl(root: Path, rel: str, rows: list[dict]) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )


def _full_refs() -> dict:
    return {name: f"{name}-ref-001" for name in SIX_RESULTS}


def _seed_four_element_fixture(root: Path) -> None:
    """搭一条四要素齐备的结论（复用 `Ch1 §E`：evidence + assumptions + computation + prev）。"""
    _write_jsonl(
        root,
        "facts/recommendations.jsonl",
        [
            {
                "recommendation_id": "rec-nvda-001",
                "security_id": "sec-nvda",
                "company_id": "company-nvidia",
                "action": "buy",
                "horizon": "1Y",
                "start_date": "2025-02-27",
                "status": "active",
                "version": 2,
                "recorded_seq": 2,
                "evidence_version_ids": [_CLAIM_ID, _DV_ID],
                "assumptions": [],
                "supersedes": "rec-nvda-001",
            }
        ],
    )
    _write_jsonl(
        root,
        "facts/baselines.jsonl",
        [
            {
                "baseline_id": "baseline-nvda-001",
                "company_id": "company-nvidia",
                "version": 1,
                "driver_model": [{"driver_id": "DRV-1", "assumptions": ["数据中心 AI 资本开支增速维持"]}],
            }
        ],
    )
    _write_jsonl(
        root,
        "derived/derived_values.jsonl",
        [
            {
                "derived_id": _DV_ID,
                "value": "0.75",
                "formula": "gross_profit / revenue",
                "operands": ["raw/x.txt#L212", "raw/x.txt#L225"],
                "method_version": "compute-v1",
                "version": "v2",
            }
        ],
    )


# ─────────────────────────── 六结果齐备（集合关系，R-06） ───────────────────────────


def test_six_results_complete_true_and_false(code_root: Path) -> None:
    """全环 → True；缺一环 → False（判据是集合关系，非关键词）。"""
    _write_jsonl(
        code_root,
        _EVENT_STUDIES_REL,
        [{"event_study_id": "es-nvda-001", "six_results_ref": _full_refs()}],
    )
    assert six_results_complete("es-nvda-001", code_root) is True

    partial = _full_refs()
    del partial["verification"]
    _write_jsonl(
        code_root,
        _EVENT_STUDIES_REL,
        [{"event_study_id": "es-nvda-001", "six_results_ref": partial}],
    )
    assert six_results_complete("es-nvda-001", code_root) is False
    assert missing_six_results(partial) == ["verification"]


def test_six_results_unknown_event_study_is_not_complete(code_root: Path) -> None:
    """未知 `event_study_id` ⇒ 引用集合为空 ⇒ False（不判通过）。"""
    assert load_six_results_ref("es-does-not-exist", code_root) == {}
    assert six_results_complete("es-does-not-exist", code_root) is False


# ─────────────────────────── 四要素覆盖率（复用 Ch1 §E） ───────────────────────────


def test_four_element_coverage_ok_and_incomplete(code_root: Path) -> None:
    """齐备 → True 且覆盖 1.0；删 `derived/` ⇒ `TraceIncomplete`（命中即 fail）。"""
    _seed_four_element_fixture(code_root)
    assert traceback_coverage_ok(["rec-nvda-001"], code_root) is True
    assert four_elements_coverage(["rec-nvda-001"], code_root) == 1.0

    (code_root / "derived" / "derived_values.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(TraceIncomplete) as exc:
        traceback_coverage_ok(["rec-nvda-001"], code_root)
    assert "computation" in str(exc.value)


def test_empty_sample_raises_not_passes() -> None:
    """空样本 ⇒ `TraceEvaluationGap`（`G-03`：不得返回 True 冒充通过）。"""
    with pytest.raises(TraceEvaluationGap):
        traceback_coverage_ok([])


# ─────────────────────────── AC-03：CLI 门禁 ───────────────────────────


def test_cli_passes_on_empty_truth_source_with_not_evaluated(code_root: Path) -> None:
    """空视图 + 空建议 ⇒ exit 0，且 note 显式 `NOT_EVALUATED`（不判通过，也不误报）。"""
    code, out = run_gate_inproc(CLI, code_root)
    assert code == 0, out
    assert "NOT_EVALUATED" in out


def test_cli_fails_on_incomplete_six_results(code_root: Path) -> None:
    """事件研究缺环 ⇒ CLI exit 1（阻断），并报 `N10.1-01`。"""
    partial = _full_refs()
    del partial["transmission"]
    _write_jsonl(
        code_root,
        _EVENT_STUDIES_REL,
        [{"event_study_id": "es-nvda-001", "six_results_ref": partial}],
    )
    code, out = run_gate_inproc(CLI, code_root)
    assert code == 1, out
    assert "N10.1-01" in out


def test_verify_hook_step8_is_check_alias(code_root: Path) -> None:
    """`verify_hook_step8`（`Ch1 §E` 第 8 步落点）与 `check` 同源。"""
    report = verify_hook_step8(code_root)
    assert report.checker == "traceback_coverage"
    assert report.checker == check(code_root).checker
