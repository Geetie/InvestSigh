"""`independence` 追源去重与独立判定测试（`ws/ch6-verify` · DoD AC-01~04 / AC-09~13）。

覆盖：
- **T01 正向（权威表逐字）**：十篇转述同一匿名订单消息 ⇒ **1 独立来源 + 10 传播记录**；
- **T01 反向对照**：3 条**真正独立**来源 ⇒ 佐证数 **3**（证不欠报）；
- **真落库 + 幂等**：`classify_and_record` 真写 `facts/claim_propagation.jsonl`，重跑 0 新增；
- **错误路径**：`origin_claim_id` 指向集合外 → 响亮失败；成环 → 响亮拒绝；缺时间 → 响亮失败；
- **边界**：空 claims → 真空成立（G-03），不崩。

★ 逻辑断言在**本进程内**直调模块（真读夹具副本的 `facts/`）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import SYSTEM_ROOT  # noqa: F401  （保证 system/ 在 sys.path 上）
from schema.models import Claim, ClaimForm, ClaimNature, SourceTier
from schema.store import append_records, read_records
from scripts.evidence.independence import (
    IndependenceInputError,
    classify_and_record,
    classify_independence,
)

_OCCURRED = "2026-09-10T00:00:00+00:00"
_ANON_MESSAGE = "anon-order-msg"


def _row(
    claim_id: str,
    *,
    source_id: str,
    origin: str | None = None,
    direct: str = "direct",
    root_source_id: str | None = None,
    seq: int = 1,
) -> dict:
    """一条原始 claim 行（**允许带可选质量/身份字段**，供独立判定的纯函数用例）。"""
    rec: dict = {
        "claim_id": claim_id,
        "source_id": source_id,
        "quote_hash": "q-" + claim_id,
        "claim_nature": "fact",
        "claim_form": "citation",
        "tier": "secondary_tertiary",
        "locator": "raw/doc.txt#L1-L1",
        "status": "pending_verification",
        "recorded_seq": seq,
        "first_seen_at": _OCCURRED,
        "occurred_at": _OCCURRED,
        "origin_claim_id": origin,
        "direct_knowledge": direct,
    }
    if root_source_id is not None:
        rec["root_source_id"] = root_source_id
    return rec


def _t01_rows() -> list[dict]:
    """1 条根主张 + 10 条转述同一匿名订单消息（指纹同、`origin` 指向根）。"""
    root = _row("root", source_id=_ANON_MESSAGE, direct="direct")
    restatements = [
        _row(f"re{i}", source_id=f"article-{i}", origin="root", direct="direct")
        for i in range(10)
    ]
    return [root, *restatements]


# ───────────────────────── T01 正向（Ch10 §2.1 权威表逐字） ─────────────────────────


def test_t01_ten_restatements_one_evidence_and_ten_propagation() -> None:
    """**AC-01**：十篇转述同一匿名订单消息 ⇒ 保留**一个原始证据来源** + **10 条传播记录**。"""
    summary = classify_independence(_t01_rows())

    assert summary.root_count == 1, f"根主张数应 == 1，实得 {summary.root_count}"
    assert summary.independent_evidence_count["root"] == 1, "独立佐证数应 == 1（不升为十份）"
    assert summary.propagation_count == 10, f"传播记录应 == 10，实得 {summary.propagation_count}"
    # 传播记录被**保留**（不是丢弃）：每一条转述都有独立的一行
    assert {p.propagated_claim_id for p in summary.propagation_rows} == {f"re{i}" for i in range(10)}
    assert all(p.independent_evidence is False for p in summary.propagation_rows), "转述不得升为独立佐证"
    assert all(p.root_claim_id == "root" for p in summary.propagation_rows)
    # 分组：全部落在同一内容组
    assert len(summary.groups) == 1


def test_t01_reverse_three_truly_independent_sources_count_three() -> None:
    """**AC-02 反向对照**：3 条真正独立（无共同上游）的同一消息来源 ⇒ 佐证数 == 3。"""
    rows = [
        _row(f"ind{i}", source_id=f"src-{i}", origin=None, direct="direct", root_source_id=_ANON_MESSAGE)
        for i in range(3)
    ]
    summary = classify_independence(rows)

    assert summary.propagation_count == 0, "无上游 ⇒ 无转述记录"
    assert len(summary.groups) == 1, "同一消息 → 同一内容组"
    assert summary.independent_evidence_count["ind0"] == 3
    assert set(summary.independent_evidence_count.values()) == {3}


def test_root_but_not_direct_is_review_candidate_not_independent() -> None:
    """根但非直接知情 → 不计独立，登记为存疑（`Ch6 §C.2` 步骤⑥ / `§F.3`）。"""
    rows = [_row("r", source_id="s", origin=None, direct="indirect")]
    summary = classify_independence(rows)
    assert summary.independent_evidence_count == {"r": 0}
    assert summary.review_candidates == ("r",)
    assert summary.propagation_count == 0


# ───────────────────────── 真落库 + 幂等（AC-03） ─────────────────────────


def _seed_claims(root: Path) -> None:
    """经**唯一写入口** `append_records` 落 1 根 + 10 转述的合法 `Claim`（真链路口径）。"""
    claims = [
        Claim(
            claim_id="root",
            source_id=_ANON_MESSAGE,
            quote_hash="q-root",
            claim_nature=ClaimNature.fact,
            claim_form=ClaimForm.original_investigation,
            tier=SourceTier.secondary_tertiary,
            occurred_at=_OCCURRED,
            first_seen_at=_OCCURRED,
            recorded_seq=1,
            impact_capability={"direct_knowledge": "direct"},
        )
    ]
    for i in range(10):
        claims.append(
            Claim(
                claim_id=f"re{i}",
                source_id=f"article-{i}",
                quote_hash=f"q-re{i}",
                claim_nature=ClaimNature.fact,
                claim_form=ClaimForm.citation,
                tier=SourceTier.secondary_tertiary,
                origin_claim_id="root",
                occurred_at=_OCCURRED,
                first_seen_at=_OCCURRED,
                recorded_seq=2 + i,
                impact_capability={"direct_knowledge": "direct"},
            )
        )
    append_records(root, "claims", claims)


def test_classify_and_record_writes_propagation_and_is_idempotent(code_root: Path) -> None:
    """**AC-03**：真落 `facts/claim_propagation.jsonl` 10 行；重跑 **0 新增**（追加式幂等）。"""
    _seed_claims(code_root)
    claims_before = (code_root / "facts" / "claims.jsonl").read_bytes()

    summary = classify_and_record(code_root)
    assert summary.independent_evidence_count["root"] == 1

    rows = read_records(code_root, "claim_propagation")
    assert len(rows) == 10, f"应落 10 行传播记录，实得 {len(rows)}"
    assert {r["propagated_claim_id"] for r in rows} == {f"re{i}" for i in range(10)}
    assert all(r["root_claim_id"] == "root" for r in rows)

    # 再跑一次：幂等，不重复追加
    classify_and_record(code_root)
    assert len(read_records(code_root, "claim_propagation")) == 10, "重跑不得重复落传播行"

    # 真源 claims.jsonl 逐字节未变（只读不改，Ch9 §3.4.2）
    assert (code_root / "facts" / "claims.jsonl").read_bytes() == claims_before


def test_latest_version_per_claim_id_not_double_counted(code_root: Path) -> None:
    """同一 `claim_id` 多版本 ⇒ 取最新版本，**不得**把历史版本当成多份佐证（`Ch9 §3.4.1`）。"""
    _seed_claims(code_root)
    # 追加一个"根"的新版本行（recorded_seq 更大）
    append_records(
        code_root,
        "claims",
        [
            Claim(
                claim_id="root",
                source_id=_ANON_MESSAGE,
                quote_hash="q-root",
                claim_nature=ClaimNature.fact,
                claim_form=ClaimForm.original_investigation,
                tier=SourceTier.secondary_tertiary,
                occurred_at=_OCCURRED,
                first_seen_at=_OCCURRED,
                recorded_seq=99,
                impact_capability={"direct_knowledge": "direct"},
            )
        ],
    )
    summary = classify_and_record(code_root)
    assert summary.root_count == 1
    assert summary.independent_evidence_count["root"] == 1
    assert summary.propagation_count == 10


# ───────────────────────── 错误路径（AC-09）与边界（AC-10） ─────────────────────────


def test_origin_outside_claim_set_fails_loud() -> None:
    """`origin_claim_id` 指向不在集合内的主张 → `IndependenceInputError`（不静默当独立）。"""
    rows = [_row("x", source_id="s", origin="missing-root")]
    with pytest.raises(IndependenceInputError, match="不在本次主张集内"):
        classify_independence(rows)


def test_origin_cycle_rejected() -> None:
    """`origin_claim_id` 成环 → `IndependenceInputError`（**响亮拒绝**，不无限回溯）。"""
    rows = [
        _row("a", source_id="s1", origin="b"),
        _row("b", source_id="s2", origin="a"),
    ]
    with pytest.raises(IndependenceInputError, match="成环"):
        classify_independence(rows)


def test_missing_time_field_fails_loud() -> None:
    """缺 `occurred_at` / `published_at` / `first_seen_at` → 响亮失败（不臆造"今天"）。"""
    rec = _row("c", source_id="s")
    for key in ("occurred_at", "published_at", "first_seen_at"):
        rec.pop(key, None)
    with pytest.raises(IndependenceInputError, match="occurred_at"):
        classify_independence([rec])


def test_empty_claims_is_vacuous_not_verified() -> None:
    """**AC-10 边界**：空 claims → 真空成立（`G-03` 显式 note），计数器为空，**不崩**。"""
    summary = classify_independence([])
    assert summary.independent_evidence_count == {}
    assert summary.propagation_count == 0
    assert any("NO_CLAIMS" in note for note in summary.notes)


def test_classify_and_record_on_empty_truth_source(code_root: Path) -> None:
    """空真源副本 → `classify_and_record` 不崩、不写传播行（`G-RC-02` 契约）。"""
    summary = classify_and_record(code_root)
    assert summary.independent_evidence_count == {}
    assert read_records(code_root, "claim_propagation") == []
