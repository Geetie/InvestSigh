"""T12 传播（`Ch9 §3.4.3` / `§2.3.3`）测试。

覆盖 AC-01（真跑通：真实边 → 真实传播）/ AC-02（写 `facts/`）/ AC-05（环保留不崩）。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from schema.models import (
    Baseline,
    Claim,
    ClaimForm,
    ClaimNature,
    Company,
    Recommendation,
    RecommendationAction,
    ResearchDepth,
    SourceTier,
    Task,
)
from schema.store import append_records, read_records
from scripts.graph.propagate import propagate_retraction

NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)


def _seed_chain(code_root: Path) -> None:
    """claim:c1 → baseline:b1 → recommendation:r1，公司 CO1（深度 tracking）。"""
    append_records(
        code_root,
        "claims",
        [
            Claim(
                claim_id="c1",
                source_id="s1",
                quote_hash="q1",
                claim_nature=ClaimNature.fact,
                claim_form=ClaimForm.original_investigation,
                tier=SourceTier.primary,
                first_seen_at=NOW,
                recorded_seq=1,
            )
        ],
    )
    append_records(
        code_root,
        "baselines",
        [Baseline(baseline_id="b1", company_id="CO1", version=1, business_mechanism="hw")],
    )
    append_records(
        code_root,
        "recommendations",
        [
            Recommendation(
                recommendation_id="r1",
                security_id="SEC1",
                company_id="CO1",
                action=RecommendationAction.buy,
                horizon="2Q",
                start_date=date(2026, 9, 1),
                rule_version="v1",
            )
        ],
    )
    append_records(
        code_root,
        "companies",
        [
            Company(
                company_id="CO1",
                legal_name="Co One",
                research_depth=ResearchDepth.tracking,
                recorded_seq=1,
                first_seen_at=NOW,
            )
        ],
    )
    append_records(
        code_root,
        "dependency_edges",
        _dep_edges([("c1", "b1", "evidence"), ("b1", "r1", "supports")]),
    )


def _dep_edges(triples: list[tuple[str, str, str]]):
    from schema.models import DependencyEdge

    return [DependencyEdge(edge_id=f"e{i}", from_ref=f, to_ref=t, kind=k) for i, (f, t, k) in enumerate(triples)]


def test_real_retraction_reaches_downstream_and_enqueues(code_root: Path) -> None:
    _seed_chain(code_root)

    result = propagate_retraction(code_root, "c1", run_date=date(2026, 9, 16), apply=True)

    assert result.downstream == ("b1", "r1")
    assert result.downstream_by_kind["baselines"] == ("b1",)
    assert result.downstream_by_kind["recommendations"] == ("r1",)
    assert result.recheck_targets == ("b1", "r1")
    assert result.stale_marks == 2
    # 研究深度回退：tracking → baseline_done
    assert result.rolled_back_companies == ("CO1",)

    # 真源已追加：recheck 任务 + 新公司行（append-only，不覆盖）
    tasks = [Task.model_validate(r) for r in read_records(code_root, "tasks")]
    rechecks = [t for t in tasks if t.task_type.value == "recheck"]
    assert len(rechecks) == 2
    assert all(t.status.value == "queued" for t in rechecks)
    assert all(t.parent_context.get("reason") == "dependency_stale" for t in rechecks)

    companies = read_records(code_root, "companies")
    latest = max(companies, key=lambda r: r.get("recorded_seq") or 0)
    assert latest["research_depth"] == "baseline_done"
    assert latest["change_log"][-1]["cause"] == "c1"
    # 事件 / 主张本身**保留**（不删除）
    assert any(r["claim_id"] == "c1" for r in read_records(code_root, "claims"))


def test_retraction_is_idempotent(code_root: Path) -> None:
    _seed_chain(code_root)
    first = propagate_retraction(code_root, "c1", run_date=date(2026, 9, 16), apply=True)
    second = propagate_retraction(code_root, "c1", run_date=date(2026, 9, 16), apply=True)

    assert first.stale_marks == 2
    assert second.stale_marks == 0
    assert set(second.skipped_task_ids) == set(first.created_task_ids) or len(second.skipped_task_ids) == 2
    assert second.rolled_back_companies == ()          # 已回退过 → 不重复追加
    tasks = [r for r in read_records(code_root, "tasks") if r.get("task_type") == "recheck"]
    assert len(tasks) == 2                              # 不重复建单（G1-04）


def test_dry_run_does_not_write(code_root: Path) -> None:
    _seed_chain(code_root)
    result = propagate_retraction(code_root, "c1", apply=False)
    assert result.stale_marks == 2                      # 计算出来了
    assert [r for r in read_records(code_root, "tasks") if r.get("task_type") == "recheck"] == []
    assert max(r.get("recorded_seq") or 0 for r in read_records(code_root, "companies")) == 1


def test_cycle_is_preserved_not_crashing(code_root: Path) -> None:
    _seed_chain(code_root)
    append_records(code_root, "dependency_edges", _dep_edges([("c1", "x1", "cycle")]))
    append_records(code_root, "dependency_edges", _dep_edges([("x1", "x1", "self")]))
    result = propagate_retraction(code_root, "c1", apply=True)
    assert result.cycle_detected is True
    assert "x1" in result.downstream
