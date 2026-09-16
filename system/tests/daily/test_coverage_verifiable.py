"""`coverage_verifiable`（覆盖可核）判据的**正反两向**测试。

锚点：`Ch3 §N3.2-03`（三分量分别可表达）/ `Ch3 §N3.2-04`（研究深度四态）/
`00_交付施工图 §2 阶段④`（`coverage_matches_acceptance_input`）/ `10/01 §N10.1-06`。

★ 契约（对齐 `tests/conftest.py`）：`code_root` 夹具给**空真源**，测试自己声明数据。
"""

from __future__ import annotations

import json
from pathlib import Path

from schema.models import BusinessPosition, Company, ResearchDepth
from schema.store import append_records
from scripts.daily import coverage


def _append_raw(root: Path, stem: str, rows: list[dict]) -> None:
    """绕过 pydantic 直接写真源行（用于注入**畸形**数据，测判据的鲁棒性）。"""
    path = root / "facts" / f"{stem}.jsonl"
    with open(path, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_acceptance(root: Path, ids: list[str]) -> None:
    registry = root / "registry"
    registry.mkdir(parents=True, exist_ok=True)
    body = "first_list_version:\n" + "".join(f"  - {i}\n" for i in ids)
    (registry / "acceptance_input_set.yaml").write_text(body, encoding="utf-8")


def _reasons(report) -> list[str]:
    return [v.reason for v in report.violations]


# ── 正向：达标 → 0 违例 ──────────────────────────────────────────────────────

def test_pass_when_components_and_depth_valid(code_root: Path) -> None:
    """① 三分量齐备 ② 深度四态合法 ③ 目标集覆盖 ④ 非真空 → PASS。"""
    append_records(
        code_root,
        "companies",
        [Company(company_id="c1", legal_name="C1", research_depth=ResearchDepth.baseline_done)],
    )
    append_records(
        code_root,
        "business_positions",
        [
            BusinessPosition(
                company_id="c1",
                node_id="n1",
                position_listed=True,
                research_depth=ResearchDepth.relations_verified,
                scan_frequency="daily",
            ),
            BusinessPosition(
                company_id="c1",
                node_id="n2",
                position_listed=True,
                research_depth=ResearchDepth.position_listed,
                scan_frequency="weekly",
            ),
        ],
    )
    _write_acceptance(code_root, ["c1"])

    report = coverage.check(code_root)
    assert report.passed, _reasons(report)
    assert report.scanned["business_positions"] == 2
    assert report.scanned["coverage_target"] == 1


def test_coverage_target_prefers_acceptance_input(code_root: Path) -> None:
    _write_acceptance(code_root, ["c1", "c2"])
    target, note = coverage.coverage_target(code_root)
    assert target == ["c1", "c2"]
    assert "ACCEPTANCE_INPUT_OK" in note


# ── 反向：逐条注入 → 命中对应子判据 ──────────────────────────────────────────

def test_cv1_missing_component(code_root: Path) -> None:
    """CV1：`business_positions` 缺三份量之一（此处缺 scan_frequency）→ 违例。"""
    _append_raw(code_root, "companies", [{"company_id": "c1", "research_depth": "position_listed", "recorded_seq": 1}])
    _append_raw(
        code_root,
        "business_positions",
        [{"company_id": "c1", "node_id": "n1", "position_listed": True,
          "research_depth": "position_listed", "scan_frequency": ""}],
    )
    report = coverage.check(code_root)
    assert any("CV1" in r for r in _reasons(report)), _reasons(report)


def test_cv1_position_listed_not_boolean(code_root: Path) -> None:
    """CV1：`position_listed` 不是布尔可判定值（覆盖维度不可核）→ 违例。"""
    _append_raw(code_root, "companies", [{"company_id": "c1", "research_depth": "position_listed", "recorded_seq": 1}])
    _append_raw(
        code_root,
        "business_positions",
        [{"company_id": "c1", "node_id": "n1", "position_listed": "maybe",
          "research_depth": "position_listed", "scan_frequency": "daily"}],
    )
    report = coverage.check(code_root)
    assert any("CV1" in r for r in _reasons(report)), _reasons(report)


def test_cv2_invalid_depth(code_root: Path) -> None:
    """CV2：深度不在四态内（`neutral` 属**未研究伪装中性**的禁用形态）→ 违例。"""
    _append_raw(code_root, "companies", [{"company_id": "c1", "research_depth": "neutral", "recorded_seq": 1}])
    report = coverage.check(code_root)
    assert any("CV2" in r for r in _reasons(report)), _reasons(report)


def test_cv3_silent_omission(code_root: Path) -> None:
    """CV3：验收输入含 c2，但覆盖台账无 c2 → 静默遗漏。"""
    append_records(code_root, "companies", [Company(company_id="c1", legal_name="C1")])
    _write_acceptance(code_root, ["c1", "c2"])
    report = coverage.check(code_root)
    assert any("CV3" in r and "c2" in r for r in _reasons(report)), _reasons(report)


def test_cv4_no_target_is_not_a_pass(code_root: Path) -> None:
    """CV4：真空不得判过（`G-03`）。空真源 → 违例，不得静默当"已覆盖"。"""
    report = coverage.check(code_root)
    assert not report.passed
    assert any("CV4" in r for r in _reasons(report)), _reasons(report)


def test_acceptance_absent_is_explicit_note(code_root: Path) -> None:
    """缺验收输入 → **显式** note（不静默），并退化为 companies 集合。"""
    append_records(code_root, "companies", [Company(company_id="c1", legal_name="C1")])
    report = coverage.check(code_root)
    assert any("ACCEPTANCE_INPUT_ABSENT" in n for n in report.notes), report.notes
    assert report.scanned["coverage_target"] == 1


def test_nodes_without_coverage_record_visible_not_a_violation(code_root: Path) -> None:
    """在册节点无覆盖记录 → 记 note + 计数（可见），但**不判违例**（DoD §4 G-2）。"""
    _append_raw(code_root, "industry_nodes", [{"node_id": "node_x", "node_name": "X"}])
    append_records(code_root, "companies", [Company(company_id="c1", legal_name="C1")])
    report = coverage.check(code_root)
    assert report.scanned["nodes_without_coverage_record"] == 1
    assert any("INDUSTRY_NODES_WITHOUT_COVERAGE" in n for n in report.notes), report.notes
    assert report.passed, _reasons(report)
