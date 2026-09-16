"""`daily_explain` 单测（`Ch5 §F.1` 口径校验 / `§F.2` 三分类 / `§F.3` 因果链 / `§F.4` 硬隔离 / `§F.5` 复查）。

覆盖 DoD：「注入违例 → exit 非零」+ 反向对照；
并覆盖 `Ch5 §F.3` 的逐字单测要求："构造一个'时间接近但因果链不可达'的消息
→ 断言归为 `Unexplained`"。
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from schema.models import MoatWriter

from scripts.graph.adjacency import Edge
from scripts.pricelayer import MoatPriceContamination, QuoteCaliberViolation
from scripts.pricelayer.daily_explain import (
    ABNORMAL_DROP_1D,
    ABNORMAL_DROP_3D,
    FACTOR_KINDS,
    Factor,
    PriceMove,
    QuoteCaliber,
    attribute,
    candidate_factors,
    enqueue_review,
    is_abnormal_decline,
    quote_caliber_from_snapshot,
    validate_quote,
    assert_no_price_contamination,
)

NOW = datetime(2026, 9, 15, 21, 0, tzinfo=timezone.utc)


def _caliber(**overrides: object) -> QuoteCaliber:
    base: dict[str, object] = {
        "quote_time": NOW,
        "trading_session": "regular",
        "currency": "USD",
        "adjusted_flag": True,
        "corporate_actions_ref": "ca-v1",
    }
    base.update(overrides)
    return QuoteCaliber(**base)  # type: ignore[arg-type]


# ───────────────────── §F.1 行情口径校验 ─────────────────────


def test_valid_quote_caliber_passes() -> None:
    validate_quote(_caliber())  # 不抛即通过


@pytest.mark.parametrize(
    "field",
    ["quote_time", "trading_session", "currency", "adjusted_flag", "corporate_actions_ref"],
)
def test_each_missing_caliber_element_is_rejected(field: str) -> None:
    """`Ch5 §F.1` 五要素**逐项**可判定：缺哪一项就报哪一项（不得只报"口径不合格"）。"""
    bad = _caliber(**{field: None if field in ("quote_time", "adjusted_flag") else "tbd"})
    with pytest.raises(QuoteCaliberViolation) as excinfo:
        validate_quote(bad)
    assert field in str(excinfo.value), f"违例信息应点出缺的那一项：{field}"


def test_quote_caliber_from_snapshot_maps_schema_fields() -> None:
    """schema → `Ch5 §F.1` 五要素的**唯一映射点**（两处命名差异在此收口）。"""

    class _Snapshot:
        published_at = NOW
        occurred_at = None
        trading_session = "regular"
        currency = "USD"
        adjustment_caliber_version = "ca-v1"
        delayed = False

    caliber = quote_caliber_from_snapshot(_Snapshot())
    assert caliber.quote_time == NOW
    assert caliber.adjusted_flag is True
    assert caliber.corporate_actions_ref == "ca-v1"
    validate_quote(caliber)


def test_quote_caliber_from_snapshot_marks_tbd_caliber_as_unadjusted() -> None:
    class _Snapshot:
        published_at = NOW
        occurred_at = None
        trading_session = "regular"
        currency = "USD"
        adjustment_caliber_version = "tbd"
        delayed = True

    caliber = quote_caliber_from_snapshot(_Snapshot())
    assert caliber.adjusted_flag is False
    with pytest.raises(QuoteCaliberViolation):
        validate_quote(caliber)


# ───────────────────── §F.3 四类因素 + 因果链归因 ─────────────────────


def _move() -> PriceMove:
    return PriceMove(security_id="sec_nvda", move_date=NOW, change_pct=Decimal("-0.05"))


def test_candidate_factors_cover_the_four_design_kinds() -> None:
    """`Ch5 §F.3` / `N5.5-02`：基准 / 同行 / 公司事件 / 环境四类。"""
    factors = [Factor(kind, label=f"f{i}") for i, kind in enumerate(FACTOR_KINDS)]
    factors.append(Factor("astrology", label="f-unknown"))
    kept = candidate_factors(_move(), factors)
    assert [f.kind for f in kept] == list(FACTOR_KINDS)


def test_causal_chain_reachable_factor_is_confirmed() -> None:
    """`Ch5 §F.3`：有 `claim_id` **且**经传导路径可达 → **已确认**。"""
    edges = [Edge("claim-1", "sec_nvda", "affects", "dependency_edges")]
    explanation = attribute(_move(), [Factor("company_event", "指引上调", claim_id="claim-1")], edges=edges)
    assert len(explanation.confirmed) == 1
    assert explanation.unexplained is False


def test_time_proximity_only_is_unexplained() -> None:
    """★ `Ch5 §F.3` 逐字单测：**仅时间接近**（无 event/claim 引用）→ `Unexplained`。"""
    factor = Factor("environment", "当天大盘也跌", observed_at=NOW)
    explanation = attribute(_move(), [factor], edges=[])
    assert explanation.confirmed == []
    assert explanation.unexplained is True


def test_evidence_present_but_unreachable_is_inferred() -> None:
    """`Ch5 §F.2` 中档：有部分证据但**因果链不可达** → **合理推断**（不是已确认）。"""
    explanation = attribute(
        _move(), [Factor("peer", "同行财报", claim_id="claim-9")], edges=[]
    )
    assert explanation.confirmed == []
    assert len(explanation.inferred) == 1
    assert explanation.unexplained is False


def test_reverse_control_reachable_chain_not_flagged_unexplained() -> None:
    """反向对照：传导路径可达 → **不**判为无法解释（守卫不是恒红）。"""
    edges = [Edge("claim-1", "sec_nvda", "affects", "dependency_edges")]
    explanation = attribute(_move(), [Factor("company_event", "事件", claim_id="claim-1")], edges=edges)
    assert explanation.unexplained is False


# ───────────────────── §F.4 硬隔离（价格不写护城河） ─────────────────────


def test_price_writer_is_rejected_by_moat_allowlist() -> None:
    """★ `Ch5 §F.4` 逐字单测：把价格派生值当写路径 → `MoatPriceContamination`。

    "共用断言" = schema 的 `MoatWriter` 白名单（`Ch4 §F.3` 断言 A3）。
    """
    with pytest.raises(MoatPriceContamination):
        assert_no_price_contamination("price_ingest")


def test_reverse_control_allowed_moat_writers_pass() -> None:
    """反向对照：白名单内的写路径（`research_skill` / `human`）→ 放行。"""
    for member in MoatWriter:
        assert_no_price_contamination(member.value)


# ───────────────────── §F.5 异常下跌 → 强制复查 ─────────────────────


def test_abnormal_drop_thresholds_follow_confirmed_values() -> None:
    """`Ch5 §F.5` + B2（已确认）：单日 ≤ −7% 或 3 日累计 ≤ −12%。"""
    assert ABNORMAL_DROP_1D == Decimal("-0.07")
    assert ABNORMAL_DROP_3D == Decimal("-0.12")
    assert is_abnormal_decline(Decimal("-0.07")) is True
    assert is_abnormal_decline(Decimal("-0.01"), three_day_change_pct=Decimal("-0.12")) is True
    assert is_abnormal_decline(Decimal("-0.01"), three_day_change_pct=Decimal("-0.05")) is False


def test_enqueue_review_sets_rechecking_status_and_original_time() -> None:
    """`Ch5 §F.5`：`status=rechecking` + `original_judgment_time`；**不自动止损/抄底**。"""
    ticket = enqueue_review(
        recommendation_id="REC-1",
        original_judgment_time=datetime(2026, 9, 1, tzinfo=timezone.utc),
        daily_change_pct=Decimal("-0.08"),
    )
    assert ticket is not None
    assert ticket.status == "rechecking"
    assert ticket.original_judgment_time == datetime(2026, 9, 1, tzinfo=timezone.utc)


def test_reverse_control_normal_move_enqueues_nothing() -> None:
    """反向对照：正常波动 → **不产工单**。"""
    assert (
        enqueue_review(
            recommendation_id="REC-1",
            original_judgment_time=NOW,
            daily_change_pct=Decimal("-0.01"),
            three_day_change_pct=Decimal("+0.02"),
        )
        is None
    )


# ───────────────────── CLI：注入违例 → exit 非零 + 反向对照 ─────────────────────


def _price_row(snapshot_id: str, *, caliber_version: str, published_at: str | None = "2026-09-15T21:00:00+00:00") -> dict[str, object]:
    return {
        "snapshot_id": snapshot_id,
        "security_id": "sec_nvda",
        "price": "180.0",
        "currency": "USD",
        "trading_session": "regular",
        "adjustment_caliber_version": caliber_version,
        "published_at": published_at,
    }


def test_cli_rejects_quote_without_caliber_version(
    scratch: Path, write_jsonl, run_script
) -> None:
    """★ 注入违例：行情缺复权/公司行动口径 → CLI **exit 1**（`Ch5 §F.1` / T11）。"""
    write_jsonl(scratch, "prices", [_price_row("SNP-1", caliber_version="tbd")])
    proc = run_script("scripts/pricelayer/daily_explain.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "QUOTE-CALIBER" in proc.stdout


def test_reverse_control_cli_passes_with_complete_caliber(
    scratch: Path, write_jsonl, run_script
) -> None:
    """反向对照：口径五要素齐备 → **exit 0**。"""
    write_jsonl(scratch, "prices", [_price_row("SNP-1", caliber_version="ca-v1")])
    proc = run_script("scripts/pricelayer/daily_explain.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RESULT: PASS" in proc.stdout


def test_cli_notes_empty_price_source(scratch: Path, run_script) -> None:
    """`G-03`：行情真源为空 → 显式 note（退出码 0 但注明"无被检对象"）。"""
    proc = run_script("scripts/pricelayer/daily_explain.py", scratch, "--no-report")
    assert proc.returncode == 0
    assert "NO_PRICES" in proc.stdout
