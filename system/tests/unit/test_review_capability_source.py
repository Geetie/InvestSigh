"""`tests/unit/test_review_capability_source.py` —— `Ch10 §E.3` 能力来源唯一性。

覆盖（`06_WS-F` 卡 DoD）：

- **AC-04 ①**：把**回放收益当能力结论** ⇒ `CapabilitySourceViolation`（**命中即 fail**，`G-01`）；
- **AC-04**：`replay_usage` 越界 ⇒ `ReplayUsageViolation`（只读枚举 `N10.3-09`）；
- **AC-05/06 边界**：空结论集 / 空前向流 ⇒ `not_evaluated`（`G-03`，不判通过）；
  无真实时间戳 ⇒ 记未评估；回填 / 版本错序 ⇒ `ForwardStreamViolation`。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import run_gate_inproc
from scripts.review.capability_source import (
    FORWARD_STREAM_SOURCE,
    REPLAY_USAGE_ALLOWED,
    CapabilitySourceViolation,
    ForwardStreamViolation,
    ReplayUsageViolation,
    assert_capability_from_forward_only,
    assert_forward_not_backfilled,
    assert_replay_usage_allowed,
    check,
    evaluate_capability_source,
    max_seq_upto,
)

CLI = "scripts/review/capability_source.py"

_CONCLUSIONS_REL = "views/capability_conclusions.jsonl"


def _write_jsonl(root: Path, rel: str, rows: list[dict]) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )


def _conclusion(*, source: str, cid: str = "cap-001") -> dict:
    return {"conclusion_id": cid, "source": source, "statement": "能力结论候选"}


def _forward_row(*, seq: int, first_seen_at: str, backfilled_at: str | None = None) -> dict:
    return {
        "recommendation_id": "rec-nvda-001",
        "security_id": "sec-nvda",
        "recorded_seq": seq,
        "first_seen_at": first_seen_at,
        "backfilled_at": backfilled_at,
    }


# ─────────────────────────── AC-04 ①：回放收益不得当能力结论 ───────────────────────────


def test_replay_return_as_capability_is_rejected(code_root: Path) -> None:
    """反向对照：`source="replay_return"` ⇒ `CapabilitySourceViolation`。"""
    _write_jsonl(code_root, _CONCLUSIONS_REL, [_conclusion(source="replay_return")])
    with pytest.raises(CapabilitySourceViolation):
        assert_capability_from_forward_only(code_root)


def test_forward_stream_source_is_accepted(code_root: Path) -> None:
    """正向对照：`source="forward_advice_stream"` ⇒ 放行（合法不误伤，`G-05`）。"""
    _write_jsonl(code_root, _CONCLUSIONS_REL, [_conclusion(source=FORWARD_STREAM_SOURCE)])
    assert_capability_from_forward_only(code_root)  # 不抛


def test_empty_conclusions_do_not_raise_but_are_not_evaluated(code_root: Path) -> None:
    """空结论集 ⇒ 断言不抛；但 `evaluate` 记 `not_evaluated`（**不判通过**，`G-03`）。"""
    assert_capability_from_forward_only(code_root)  # 无可核对象 → 不抛
    report = evaluate_capability_source(code_root)
    assert report.conclusions_evaluated is False
    assert any("NOT_EVALUATED" in n for n in report.notes)


# ─────────────────────────── replay_usage 只读枚举 ───────────────────────────


def test_replay_usage_allowed_enum() -> None:
    assert REPLAY_USAGE_ALLOWED == frozenset({"process", "data_timing", "update_logic"})
    for value in REPLAY_USAGE_ALLOWED:
        assert_replay_usage_allowed(value)  # 不抛
    with pytest.raises(ReplayUsageViolation):
        assert_replay_usage_allowed("investment_capability")


# ─────────────────────────── 前向流：真实时间戳 + 不可回填 ───────────────────────────


def test_forward_stream_valid_passes() -> None:
    """合法前向流（同键、时间递增、seq 递增）⇒ 断言放行。"""
    stream = [
        _forward_row(seq=1, first_seen_at="2025-01-01T00:00:00"),
        _forward_row(seq=2, first_seen_at="2025-01-05T00:00:00"),
    ]
    assert_forward_not_backfilled(stream)  # 不抛
    assert max_seq_upto(stream, stream[0]) == 1
    assert max_seq_upto(stream, stream[1]) == 2


def test_forward_stream_backfilled_at_is_rejected() -> None:
    """`backfilled_at` 非空 ⇒ `ForwardStreamViolation`。"""
    stream = [_forward_row(seq=1, first_seen_at="2025-01-01T00:00:00", backfilled_at="2025-02-01T00:00:00")]
    with pytest.raises(ForwardStreamViolation):
        assert_forward_not_backfilled(stream)


def test_forward_stream_out_of_order_seq_is_rejected() -> None:
    """后插入却给早时间戳（seq 抬高同期真行上界）⇒ `ForwardStreamViolation`。"""
    stream = [
        _forward_row(seq=2, first_seen_at="2025-01-02T00:00:00"),
        _forward_row(seq=3, first_seen_at="2025-01-01T00:00:00"),  # 更晚写入却被标更早
    ]
    with pytest.raises(ForwardStreamViolation):
        assert_forward_not_backfilled(stream)


def test_forward_stream_missing_timestamp_is_unverifiable() -> None:
    """无真实时间戳 ⇒ 严格断言 `raise`；分类函数记未评估（`G-03`）。"""
    from scripts.review.capability_source import iter_forward_violations

    stream = [{"recommendation_id": "rec-x", "recorded_seq": 1, "first_seen_at": None}]
    with pytest.raises(ForwardStreamViolation):
        assert_forward_not_backfilled(stream)

    violations, unverifiable = iter_forward_violations(stream)
    assert violations == []
    assert unverifiable == 1


# ─────────────────────────── AC-03：CLI 门禁 ───────────────────────────


def test_cli_fails_when_replay_used_as_capability(code_root: Path) -> None:
    """真源含 `source="replay_return"` 的结论 ⇒ CLI exit 1（阻断，不是 warn）。"""
    _write_jsonl(code_root, _CONCLUSIONS_REL, [_conclusion(source="replay_return")])
    code, out = run_gate_inproc(CLI, code_root)
    assert code == 1, out
    assert "N10.3-10" in out


def test_cli_passes_with_clean_truth_source(code_root: Path) -> None:
    """真源为空（夹具）⇒ exit 0 且显式 `NOT_EVALUATED` note（不判通过，也不误报）。"""
    code, out = run_gate_inproc(CLI, code_root)
    assert code == 0, out
    assert "NOT_EVALUATED" in out


def test_check_reports_backfilled_row_violation(code_root: Path) -> None:
    """`check` 对回填行给出 `N10.3-11` 违例。"""
    _write_jsonl(
        code_root,
        "facts/recommendations.jsonl",
        [_forward_row(seq=1, first_seen_at="2025-01-01T00:00:00", backfilled_at="2025-02-01T00:00:00")],
    )
    report = check(code_root)
    assert any(v.rule == "N10.3-11" for v in report.violations)
