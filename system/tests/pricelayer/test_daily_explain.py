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
    RecheckTrigger,
    assert_no_price_contamination,
    attribute,
    candidate_factors,
    enqueue_review,
    is_abnormal_decline,
    load_recheck_trigger,
    quote_caliber_from_snapshot,
    validate_quote,
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


# ───────── 规则↔代码绑定：**在真 rules/review.yaml 上**（防硬编码阈值）─────────


def test_real_rules_recheck_thresholds(scratch: Path, real_rules) -> None:
    """★ 复查阈值**读**真文件（`rules/review.yaml::forced_recheck`，B2：−7% / −12%）。

    规则文件写**百分点**（`-7`/`-12`），本层内部用**小数**（`-0.07`/`-0.12`）——
    换算只在 `load_recheck_trigger` 一处完成，且结果必须与设计逐字值一致。
    """
    real_rules(scratch, "review.yaml")
    trigger = load_recheck_trigger(scratch)
    assert trigger.value_source == "rules"
    assert trigger.single_day_drop == Decimal("-0.07") == ABNORMAL_DROP_1D
    assert trigger.three_day_cumulative == Decimal("-0.12") == ABNORMAL_DROP_3D
    assert trigger.keep_original_judgment_time is True, "T08"


def test_rule_threshold_change_drives_judgement(scratch: Path, real_rules) -> None:
    """★ 行为绑定：把单日阈值改成 −5% ⇒ −6% 立即命中（**不硬编码 −7%**）。"""
    import yaml

    real_rules(scratch, "review.yaml")
    path = scratch / "rules" / "review.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["forced_recheck"]["single_day_drop_pct"] = -5
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    trigger = load_recheck_trigger(scratch)
    assert trigger.single_day_drop == Decimal("-0.05")
    assert is_abnormal_decline(Decimal("-0.06"), trigger=trigger) is True
    assert is_abnormal_decline(Decimal("-0.06"), trigger=load_recheck_trigger(None)) is False


def test_positive_rule_threshold_fails_loudly(scratch: Path, real_rules) -> None:
    """★ 反例：阈值被写成非下跌口径（正数）→ **响亮失败**（不静默当阈值用）。"""
    import yaml

    real_rules(scratch, "review.yaml")
    path = scratch / "rules" / "review.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["forced_recheck"]["single_day_drop_pct"] = 7
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    with pytest.raises(Exception, match="必须为负"):
        load_recheck_trigger(scratch)


def test_enqueue_review_uses_rule_thresholds(scratch: Path, real_rules) -> None:
    """工单理由用**规则里的**阈值表述（不是代码常量）。"""
    import yaml

    real_rules(scratch, "review.yaml")
    path = scratch / "rules" / "review.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["forced_recheck"]["single_day_drop_pct"] = -5
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    ticket = enqueue_review(
        recommendation_id="rec-1",
        original_judgment_time=NOW,
        daily_change_pct=Decimal("-0.06"),
        trigger=load_recheck_trigger(scratch),
    )
    assert ticket is not None
    assert "-0.05" in ticket.trigger


def test_cli_clean_on_real_rules_file(scratch: Path, real_rules, run_script) -> None:
    """反向对照：真规则文件 → CLI **exit 0**（无绑定违例），即便 `facts/prices` 为空。"""
    real_rules(scratch, "review.yaml")
    proc = run_script("scripts/pricelayer/daily_explain.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "NO_PRICES" in proc.stdout
    assert "DAILY-RULE-BINDING" not in proc.stdout


def test_cli_flags_recheck_threshold_drift(scratch: Path, real_rules, run_script) -> None:
    """★ 注入违例：规则阈值改了而代码回落值没改 → CLI **exit 1**（声明与实现脱节）。"""
    import yaml

    real_rules(scratch, "review.yaml")
    path = scratch / "rules" / "review.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["forced_recheck"]["single_day_drop_pct"] = -5
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/daily_explain.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "DAILY-RULE-BINDING" in proc.stdout


def test_cli_flags_forced_recheck_key_removed(scratch: Path, run_script) -> None:
    """★ 注入违例：`review.yaml` 缺 `forced_recheck` 键 → CLI **exit 1**。"""
    import yaml

    doc = yaml.safe_load((Path(__file__).resolve().parents[2] / "rules" / "review.yaml").read_text(encoding="utf-8"))
    doc.pop("forced_recheck", None)
    path = scratch / "rules" / "review.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/daily_explain.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "DAILY-RULE-BINDING" in proc.stdout


# ───────── 规则↔代码绑定：**在真 rules/review.yaml 上**（防硬编码阈值）─────────


def test_real_rules_recheck_thresholds(scratch: Path, real_rules) -> None:
    """★ 复查阈值**读**真文件（`rules/review.yaml::forced_recheck`，B2：−7% / −12%）。

    规则文件写**百分点**（`-7`/`-12`），本层内部用**小数**（`-0.07`/`-0.12`）——
    换算只在 `load_recheck_trigger` 一处完成，且结果必须与设计逐字值一致。
    """
    real_rules(scratch, "review.yaml")
    trigger = load_recheck_trigger(scratch)
    assert trigger.value_source == "rules"
    assert trigger.single_day_drop == Decimal("-0.07") == ABNORMAL_DROP_1D
    assert trigger.three_day_cumulative == Decimal("-0.12") == ABNORMAL_DROP_3D
    assert trigger.keep_original_judgment_time is True, "T08"


def test_rule_threshold_change_drives_judgement(scratch: Path, real_rules) -> None:
    """★ 行为绑定：把单日阈值改成 −5% ⇒ −6% 立即命中（**不硬编码 −7%**）。"""
    import yaml

    real_rules(scratch, "review.yaml")
    path = scratch / "rules" / "review.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["forced_recheck"]["single_day_drop_pct"] = -5
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    trigger = load_recheck_trigger(scratch)
    assert trigger.single_day_drop == Decimal("-0.05")
    assert is_abnormal_decline(Decimal("-0.06"), trigger=trigger) is True
    assert is_abnormal_decline(Decimal("-0.06"), trigger=load_recheck_trigger(None)) is False


def test_positive_rule_threshold_fails_loudly(scratch: Path, real_rules) -> None:
    """★ 反例：阈值被写成非下跌口径（正数）→ **响亮失败**（不静默当阈值用）。"""
    import yaml

    real_rules(scratch, "review.yaml")
    path = scratch / "rules" / "review.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["forced_recheck"]["single_day_drop_pct"] = 7
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    with pytest.raises(Exception, match="必须为负"):
        load_recheck_trigger(scratch)


def test_enqueue_review_uses_rule_thresholds(scratch: Path, real_rules) -> None:
    """工单理由用**规则里的**阈值表述（不是代码常量）。"""
    import yaml

    real_rules(scratch, "review.yaml")
    path = scratch / "rules" / "review.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["forced_recheck"]["single_day_drop_pct"] = -5
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    ticket = enqueue_review(
        recommendation_id="rec-1",
        original_judgment_time=NOW,
        daily_change_pct=Decimal("-0.06"),
        trigger=load_recheck_trigger(scratch),
    )
    assert ticket is not None
    assert "-0.05" in ticket.trigger


def test_cli_clean_on_real_rules_file(scratch: Path, real_rules, run_script) -> None:
    """反向对照：真规则文件 → CLI **exit 0**（无绑定违例），即便 `facts/prices` 为空。"""
    real_rules(scratch, "review.yaml")
    proc = run_script("scripts/pricelayer/daily_explain.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "NO_PRICES" in proc.stdout
    assert "DAILY-RULE-BINDING" not in proc.stdout


def test_cli_flags_recheck_threshold_drift(scratch: Path, real_rules, run_script) -> None:
    """★ 注入违例：规则阈值改了而代码回落值没改 → CLI **exit 1**（声明与实现脱节）。"""
    import yaml

    real_rules(scratch, "review.yaml")
    path = scratch / "rules" / "review.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["forced_recheck"]["single_day_drop_pct"] = -5
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/daily_explain.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "DAILY-RULE-BINDING" in proc.stdout


def test_cli_flags_forced_recheck_key_removed(scratch: Path, run_script) -> None:
    """★ 注入违例：`review.yaml` 缺 `forced_recheck` 键 → CLI **exit 1**。"""
    import yaml

    doc = yaml.safe_load((Path(__file__).resolve().parents[2] / "rules" / "review.yaml").read_text(encoding="utf-8"))
    doc.pop("forced_recheck", None)
    path = scratch / "rules" / "review.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/daily_explain.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "DAILY-RULE-BINDING" in proc.stdout


# ── 主理人裁定 ③：`design_default` 必须带 note + 回落值必须绑定 ──


def test_trigger_fallback_records_source_and_note(scratch: Path) -> None:
    """★ 裁定 ③-1/③-2：缺 `review.yaml` ⇒ `design_default` + note 写明缺哪个文件。"""
    trigger = load_recheck_trigger(scratch)
    assert trigger.value_source == "design_default"
    assert trigger.notes
    assert "review.yaml" in trigger.notes[0]
    assert trigger.keep_original_judgment_time is True


def test_trigger_real_rules_records_rules_source_without_note(scratch: Path, real_rules) -> None:
    """对照：真文件齐备 ⇒ `rules` 且**零 note**。"""
    real_rules(scratch, "review.yaml")
    trigger = load_recheck_trigger(scratch)
    assert trigger.value_source == "rules"
    assert trigger.notes == ()


def test_trigger_missing_on_hit_key_records_note(scratch: Path, real_rules) -> None:
    """★ 裁定 ③-2：阈值在、`on_hit.keep_original_judgment_time` 缺 ⇒ `rules` + note 点名该子键。"""
    import yaml

    real_rules(scratch, "review.yaml")
    path = scratch / "rules" / "review.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["forced_recheck"]["on_hit"] = {"action": "enqueue_recheck_task"}
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    trigger = load_recheck_trigger(scratch)
    assert trigger.value_source == "rules"
    assert any("keep_original_judgment_time" in n for n in trigger.notes), trigger.notes
    assert trigger.keep_original_judgment_time is True, "缺失子键取设计逐字回落值"


def test_cli_flags_keep_original_judgment_time_drift(scratch: Path, real_rules, run_script) -> None:
    """★ 裁定 ③-3：`keep_original_judgment_time` 改假而代码回落值为真 → CLI **exit 1**（`T08`）。"""
    import yaml

    real_rules(scratch, "review.yaml")
    path = scratch / "rules" / "review.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["forced_recheck"]["on_hit"]["keep_original_judgment_time"] = False
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/daily_explain.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "DAILY-RULE-BINDING" in proc.stdout
    assert "keep_original_judgment_time" in proc.stdout
