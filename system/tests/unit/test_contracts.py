"""数据契约单测（`Ch9 §2.1/§2.2/§3.3.3` · `Ch11 §C/§F` · 纪律 7/8）。

这些断言对应"**唯一真源**"的硬约束：`facts/` 的 JSONL **不得增删改名**、
枚举 token **英文小写 + 下划线**、五类时间齐备、`Recommendation` 上**不得**
出现仓位/止损/共识类字段、追加式写入 + 索引可全量重建。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import pytest

from schema import models as M
from schema.store import (
    AppendOnlyViolation,
    UnknownJsonlError,
    append_records,
    jsonl_path,
    read_models,
    read_records,
    rebuild_index,
)

# ─────────────── `facts/` 的 JSONL：唯一真源，不得增删改名 ───────────────
#
# ★ 这张清单是**测试侧独立写下的设计契约**（22 个 stem，按设计分组）——
#   刻意**不**从 `schema.stems` 现取：若测试只与注册表自身比较，就是同义反复（恒真）。
#   "注册表 ↔ 夹具清空清单"那层绑定在 `tests/unit/test_schema_expand.py`。
# ★ 扩表出处：需求方 2026-09-16 裁定 18 → 22（`businesses` / `drivers` /
#   `implied_requirements` / `relation_flows`），见 `schema/stems.py` 脚注与 `T-13` 备选②。

EXPECTED_JSONL = {
    "industry_nodes", "companies", "securities", "business_positions",
    "products", "relations",
    "relation_flows",
    "sources", "claims", "claim_propagation",
    "events", "impacts",
    "businesses", "drivers", "baselines",
    "prices", "expectations",
    "implied_requirements",
    "benchmarks", "recommendations",
    "tasks",
    "dependency_edges",
}


def test_jsonl_set_is_exactly_22_and_named_as_designed() -> None:
    assert len(M.JSONL_MODELS) == 22
    assert set(M.JSONL_MODELS) == EXPECTED_JSONL


def test_facts_dir_holds_exactly_the_22_files() -> None:
    facts = Path(__file__).resolve().parents[2] / "facts"
    stems = {p.stem for p in facts.glob("*.jsonl")}
    assert stems == EXPECTED_JSONL, f"facts/ 与设计不符，差异: {stems ^ EXPECTED_JSONL}"


def test_unknown_jsonl_stem_fails_loudly() -> None:
    """未知 stem → 抛 `UnknownJsonlError`，**不得静默建新文件**。"""
    with pytest.raises(UnknownJsonlError):
        jsonl_path("/tmp/whatever", "gold_prices")


# ───────────────────────── 枚举 token：英文小写 + 下划线（纪律 7） ─────────────────────────

def _enum_classes() -> list[type[Enum]]:
    out = []
    for name in dir(M):
        obj = getattr(M, name)
        if isinstance(obj, type) and issubclass(obj, Enum) and obj is not Enum:
            out.append(obj)
    return out


def test_every_enum_member_name_is_lowercase_snake_case() -> None:
    """纪律 7：枚举**成员名**（= 代码里的标识符）必须英文小写 + 下划线。"""
    bad: list[str] = []
    for cls in _enum_classes():
        for member in cls:
            if not re.fullmatch(r"[a-z0-9_]+", member.name):
                bad.append(f"{cls.__name__}.{member.name}")
    assert not bad, "枚举成员名必须英文小写 + 下划线（纪律 7）：" + "; ".join(bad)


# 登记在案的**值**例外：`Ch2 §C.1` 逐字把机会类型写作 "enum A/B"，
# 源稿亦为"机会类型 A 类 / B 类"——wire 值以设计为准。
# ★ 这里**不放松**纪律 7：例外集合被钉死，任何**新增**的大写值都会让本测试 fail。
DOCUMENTED_ENUM_VALUE_EXCEPTIONS: dict[str, set[str]] = {
    "OpportunityType": {"A", "B"},
}


def test_enum_value_exceptions_are_exactly_the_documented_ones() -> None:
    """除登记例外外，枚举**取值**同样必须小写下划线；例外集合不得扩大。"""
    actual: dict[str, set[str]] = {}
    for cls in _enum_classes():
        odd = {str(m.value) for m in cls if not re.fullmatch(r"[a-z0-9_]+", str(m.value))}
        if odd:
            actual[cls.__name__] = odd
    assert actual == DOCUMENTED_ENUM_VALUE_EXCEPTIONS, (
        "枚举取值的例外集合发生变化——新增例外必须先登记设计锚点，"
        f"实际={actual} 期望={DOCUMENTED_ENUM_VALUE_EXCEPTIONS}"
    )


def test_tbd_is_the_unified_pending_token() -> None:
    """纪律 7：「待定」统一 `tbd`（不得出现 `TBD` / `pending` 作占位符）。"""
    assert M.TBD == "tbd"
    assert M.ParamFreezeStatus.tbd.value == "tbd"


# ───────────────────────── 五类时间语义（Ch9 §2.2） ─────────────────────────

EXPECTED_TIME_FIELDS = {
    "occurred_at",      # valid_time
    "published_at",     # valid_time
    "effective_from",   # valid_time
    "first_seen_at",    # system_time
    "analyzed_at",      # system_time
    "recorded_seq",     # system_time
    "backfilled_at",    # backfill
}


def test_time_mixin_carries_all_five_time_semantics() -> None:
    assert set(M.TimeMixin.model_fields) == EXPECTED_TIME_FIELDS


def test_numeric_claim_carries_derivation_and_locator() -> None:
    """数值保真：`NumericClaim` 必须能定位到原文并记录推导（`Ch9 §2.3`）。"""
    fields = set(M.NumericClaim.model_fields)
    for required in ("raw_text", "value", "unit_scale", "period_reported", "locator", "derivation", "is_derived"):
        assert required in fields, f"NumericClaim 缺字段 {required}"


# ───────────────────────── Recommendation：禁止字段（P-03/04/07） ─────────────────────────

FORBIDDEN_ON_RECOMMENDATION = {
    # P-03 禁止损
    "stop_loss", "stop_price", "price_stop",
    # P-04 仓位/持仓/成本
    "quantity", "position", "shares_held", "cost_basis", "portfolio_weight",
    # P-07 无来源的聚合预测
    "consensus", "market_view", "average_forecast",
}


def test_recommendation_has_no_forbidden_fields() -> None:
    present = set(M.Recommendation.model_fields) & FORBIDDEN_ON_RECOMMENDATION
    assert not present, f"Recommendation 上出现禁止字段: {sorted(present)}"


def test_recommendation_action_enum_has_no_shorting() -> None:
    assert {a.value for a in M.RecommendationAction} == {"buy", "sell", "pending", "maintain"}


def test_recommendation_requires_caliber_fields() -> None:
    """`Ch2 §C.1 / §D.2` 修复项：`opportunity_types` / `horizon` / `start_date` 必须在。"""
    fields = set(M.Recommendation.model_fields)
    assert {"opportunity_types", "horizon", "start_date"} <= fields


def test_early_judgment_requires_trio() -> None:
    """提前判断必须齐三要素；缺失 → 校验失败（记 gap，不出建议）。"""
    base = dict(
        recommendation_id="rec_1",
        security_id="sec_nvda",
        company_id="co_nvda",
        action="buy",
        horizon="1Y",
        start_date="2026-09-15",
        rule_version="v1",
        occurred_at=datetime(2026, 9, 15, tzinfo=timezone.utc),
        first_seen_at=datetime(2026, 9, 15, tzinfo=timezone.utc),
        analyzed_at=datetime(2026, 9, 15, tzinfo=timezone.utc),
        recorded_seq=1,
    )
    with pytest.raises(Exception):
        M.Recommendation(**base, early_judgment=True)
    ok = M.Recommendation(
        **base,
        early_judgment=True,
        assumptions=["假设1"],
        evidence_gaps=["缺口1"],
        verification_conditions=["验证1"],
    )
    assert ok.early_judgment is True


# ───────────────────────── 追加式不可变 + 索引可重建（AC-02） ─────────────────────────

def _node(node_id: str, now: datetime) -> M.IndustryNode:
    return M.IndustryNode(
        node_id=node_id,
        node_name="TEST",
        taxonomy_version="appendix1_v7",
        occurred_at=datetime.fromisoformat("2026-09-08T00:00:00+00:00"),
        published_at=None,
        effective_from=None,
        first_seen_at=now,
        analyzed_at=now,
        recorded_seq=1,
        backfilled_at=now,
    )


def test_write_read_reload_survives_index_deletion(code_root: Path) -> None:
    """AC-02：写入 → 删 `index/` 重建 → 数据仍在。"""
    now = datetime.now(timezone.utc)
    written = append_records(code_root, "industry_nodes", [_node("node_x", now)])
    assert written == 1

    first = rebuild_index(code_root)
    assert first.exists()

    first.unlink()                                  # 删索引
    second = rebuild_index(code_root)               # 从 facts/ 全量重建（自建父目录）
    assert second.exists()
    rows = read_records(code_root, "industry_nodes")
    assert any(r["node_id"] == "node_x" for r in rows), "重建索引后数据丢失"


def test_append_never_truncates_existing_lines(code_root: Path) -> None:
    """追加式：第二次写入不得影响第一次的行（既有行原样保留）。"""
    now = datetime.now(timezone.utc)
    before = [r["node_id"] for r in read_records(code_root, "industry_nodes")]
    append_records(code_root, "industry_nodes", [_node("node_a", now)])
    append_records(code_root, "industry_nodes", [_node("node_b", now)])
    after = [r["node_id"] for r in read_records(code_root, "industry_nodes")]
    assert after == before + ["node_a", "node_b"], "追加写把既有行改掉或重排了"
    # 全量行都能通过 pydantic 校验（追加写不得留下半截/非法行）
    assert len(read_models(code_root, "industry_nodes")) == len(after)


def test_invalid_record_is_rejected_without_partial_write(code_root: Path) -> None:
    """非法记录 → 抛异常且**不留半截数据**（`AC-05` 不吞异常）。"""
    before = len(read_records(code_root, "industry_nodes"))
    with pytest.raises(Exception):
        append_records(code_root, "industry_nodes", [{"node_id": "broken"}])
    assert len(read_records(code_root, "industry_nodes")) == before


# ───────────────────────── rel() 参数顺序回归 ─────────────────────────

def test_rel_rejects_out_of_root_paths_loudly() -> None:
    """回归：`rel` 曾静默返回绝对路径 → 免扫机制整体失效。

    现在不在 root 之下必须**抛错**（把"参数写反"从静默变成 `exit 2`）。
    """
    from scripts._common import rel

    root = Path("/tmp/a/b")
    with pytest.raises(ValueError):
        rel(root, Path("/tmp/a/b/c.py"))            # ← 参数顺序写反（path/root 互换）
    assert rel(Path("/tmp/a/b/c.py"), root) == "c.py"


# ───────────────────────── 参数读口：tbd 的合法边界（§6.1） ─────────────────────────

def test_get_param_tbd_returns_suggested_baseline_with_source_label(code_root: Path) -> None:
    """`tbd` → 返回值 = `suggested_value`，且 `value_source` 明示**不是**已冻结值。"""
    from config.freeze import get_param

    res = get_param("p01", code_root)
    assert res.freeze_status == "tbd"
    assert res.value_source == "suggested_baseline"
    assert res.effective_value is not None


def test_get_param_unknown_id_fails_loudly(code_root: Path) -> None:
    from config.freeze import UnknownParamError, get_param

    with pytest.raises(UnknownParamError):
        get_param("p99", code_root)


def test_get_param_without_any_value_fails_instead_of_returning_none(code_root: Path) -> None:
    """**关键**：既无 `value` 又无 `suggested_value` → 抛 `ParamValueUnavailable`，
    **不得静默返回 None / 0**（`§6.1` 非法列）。"""
    import yaml

    from config.freeze import ParamValueUnavailable, get_param

    path = code_root / "rules" / "freeze.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["freeze_params"][0].pop("suggested_value", None)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")

    with pytest.raises(ParamValueUnavailable):
        get_param("p01", code_root)


def test_freeze_has_exactly_11_params_all_tbd(code_root: Path) -> None:
    """验收前置：11 项待冻结参数以 `tbd` 占位（`Ch11 §C` / `§十二 N-03`）。"""
    from config.freeze import load_freeze

    rows = load_freeze(code_root)["freeze_params"]
    assert len(rows) == 11
    assert {r["freeze_status"] for r in rows} == {"tbd"}


# ───────────────────────── 追溯覆盖率：空样本必须抛错 ─────────────────────────

def test_traceback_coverage_on_empty_sample_raises() -> None:
    """空样本返回 `1.0` 是典型的"假通过"——必须抛错。"""
    from scripts.trace.traceback import traceback_coverage

    with pytest.raises(Exception):
        traceback_coverage([])
