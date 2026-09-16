"""⑥ `origin_claim_id` **产出方**测试（`ws/evidence-fix` · 批次 10 · `T01` 系统层缺口）。

审计发现：`T01` 的**判定层**通过（1 根 + 10 转述 → 独立佐证 1），但 `origin_claim_id`
**全仓无产出方** —— 10 篇**同根、同指纹、但未标** `origin_claim_id` 的转述会被算成 **10 份独立佐证**。
本模块证明：去重步骤（`plan_origin_attribution` / `classify_and_record`）会**产出** `origin_claim_id`
（把转述链到根主张），使 `T01` 的**现实形态**也在**系统层**成立。

三情形（逐字对齐任务书）：
- (a) 10 篇同根转述（**含** `origin_claim_id`）→ 独立佐证 **1**；
- (a') ★系统层：根来源主张**在场** + 10 篇**未标** origin 的转述 → 产出方补链 → **1**；
- (b) 3 条**真独立**（无共同上游、根来源主张不在场）→ **3**（不欠报）；
- (c) 10 篇同指纹但无 `origin_claim_id` 且**根来源主张不在场** → **现状如实登记**（仍算 10，残余）。

★ 依据 `06_公开信息与证据筛选/02_实现方案.md §C.1/§C.2/§F.3`。
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
    plan_origin_attribution,
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
    """一条**原始** claim 行（允许带可选质量/身份字段，供纯函数用例）。"""
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


def _claim(
    claim_id: str,
    *,
    source_id: str,
    origin: str | None = None,
    direct: str = "direct",
    capability_root: str | None = None,
    seq: int = 1,
) -> Claim:
    """一条**schema 合法**的 `Claim`（根来源信号经 `impact_capability` 承载）。"""
    capability: dict = {"direct_knowledge": direct}
    if capability_root is not None:
        capability["root_source_id"] = capability_root
    return Claim(
        claim_id=claim_id,
        source_id=source_id,
        quote_hash="q-" + claim_id,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.citation,
        tier=SourceTier.secondary_tertiary,
        origin_claim_id=origin,
        occurred_at=_OCCURRED,
        first_seen_at=_OCCURRED,
        recorded_seq=seq,
        impact_capability=capability,
    )


def _latest(root: Path) -> dict[str, dict]:
    """取每 `claim_id` 的最新版本行。"""
    latest: dict[str, dict] = {}
    for row in read_records(root, "claims"):
        cid = row["claim_id"]
        if cid not in latest or int(row.get("recorded_seq") or 0) >= int(
            latest[cid].get("recorded_seq") or 0
        ):
            latest[cid] = row
    return latest


# ───────────────────────────── (a) 判定层：含 origin ⇒ 1 ─────────────────────────────


def test_a_ten_restatements_with_origin_count_one() -> None:
    """(a) 10 篇同根转述（**含 `origin_claim_id`**）⇒ 独立佐证 **1**、传播 **10**（判定层，基线）。"""
    rows = [_row("root", source_id=_ANON_MESSAGE)] + [
        _row(f"re{i}", source_id=f"article-{i}", origin="root") for i in range(10)
    ]
    summary = classify_independence(rows)
    assert summary.independent_evidence_count["root"] == 1
    assert summary.propagation_count == 10


# ─────────────────────── (a') ★系统层：未标 origin 也产出并补链 ⇒ 1 ───────────────────────


def test_a_prime_system_layer_producer_links_unlabelled_restatements(code_root: Path) -> None:
    """★ **系统层**：根来源主张在场 + 10 篇**未标** `origin_claim_id` 的转述 ⇒ 产出方补链 ⇒ **1**。

    这是 `T01` 的**现实形态**（真实链路下 `origin_claim_id` 常缺）——**判定层之外**也成立。
    """
    claims = [_claim("root", source_id=_ANON_MESSAGE)] + [
        _claim(f"re{i}", source_id=f"article-{i}", capability_root=_ANON_MESSAGE) for i in range(1, 11)
    ]
    append_records(code_root, "claims", claims)

    plan = plan_origin_attribution(read_records(code_root, "claims"))
    assert plan.links == {f"re{i}": "root" for i in range(1, 11)}, plan.links

    summary = classify_and_record(code_root)
    assert summary.independent_evidence_count["root"] == 1, "系统层：应守住 1（非仅判定层）"
    assert summary.propagation_count == 10
    assert len(read_records(code_root, "claim_propagation")) == 10

    latest = _latest(code_root)
    for i in range(1, 11):
        assert latest[f"re{i}"]["origin_claim_id"] == "root", "产出方必须把转述链到根主张"
    assert latest["root"]["independent_evidence_count"] == 1, (
        "T-12：独立佐证基数（Ch6 §B.4 基数非权重）落到根主张"
    )


def test_producer_is_idempotent_and_append_only(code_root: Path) -> None:
    """产出方**幂等**（重跑 0 新增）且**只追加**（既有行逐字节保留，`Ch9 §3.4.2`）。"""
    claims = [_claim("root", source_id=_ANON_MESSAGE)] + [
        _claim(f"re{i}", source_id=f"article-{i}", capability_root=_ANON_MESSAGE) for i in range(1, 11)
    ]
    append_records(code_root, "claims", claims)
    before = (code_root / "facts" / "claims.jsonl").read_bytes()

    classify_and_record(code_root)
    after = (code_root / "facts" / "claims.jsonl").read_bytes()
    assert after.startswith(before), "追加式不可变：既有行必须逐字节保留"
    n_after_first = len(read_records(code_root, "claims"))
    prop_after_first = len(read_records(code_root, "claim_propagation"))

    classify_and_record(code_root)
    assert len(read_records(code_root, "claims")) == n_after_first, "重跑不得重复追加版本"
    assert len(read_records(code_root, "claim_propagation")) == prop_after_first, "重跑不得重复落传播行"


def test_reappend_dropping_derived_field_does_not_trigger_rewrite(code_root: Path) -> None:
    """★ `G-B10-07` 幂等硬化：上游**内容不变地再追加一版**且**不带派生字段** ⇒ 产出方**不得重写**。

    这正是 `Pipeline.run_daily` step 1 的行为（实测：每跑 +1 版、派生字段回 `None`）。
    若基线取"最新版本的值"，派生字段被这版抹掉 ⇒ 每次重写 ⇒ 非幂等（team-lead 实测复现）。
    硬化后基线取"该 `claim_id` **最近记录到的非空值**" ⇒ 值不变即 0 新增。
    """
    claims = [_claim("root", source_id=_ANON_MESSAGE)] + [
        _claim(f"re{i}", source_id=f"article-{i}", capability_root=_ANON_MESSAGE) for i in range(1, 4)
    ]
    append_records(code_root, "claims", claims)
    classify_and_record(code_root)                      # 首次：写入 count / origin
    n1 = len(read_records(code_root, "claims"))

    # 模拟上游：内容不变、追加一版，但**不带**派生字段（recorded_seq 更大）
    base = dict(_latest(code_root)["root"])
    base.pop("independent_evidence_count", None)
    base.pop("origin_claim_id", None)
    base["recorded_seq"] = 100
    append_records(code_root, "claims", [base])
    n2 = len(read_records(code_root, "claims"))
    assert n2 == n1 + 1, "前提：上游确实追加了一版"

    assert classify_and_record(code_root) is not None
    assert len(read_records(code_root, "claims")) == n2, (
        "上游丢派生字段不得触发重写（否则非幂等，G-B10-07）"
    )


def test_new_claim_still_gets_count_reverse_control(code_root: Path) -> None:
    """★ 反向对照（`G-05` 成对）：**真正的新主张**出现 ⇒ 产出方**必须**为其写入计数（不是"一律不写"）。"""
    claims = [_claim("root", source_id=_ANON_MESSAGE)]
    append_records(code_root, "claims", claims)
    classify_and_record(code_root)
    n1 = len(read_records(code_root, "claims"))

    # 一条**全新** claim_id（此前从未有过计数）→ 必须被写入其计数
    append_records(code_root, "claims", [_claim("late", source_id="late-src")])
    n2 = len(read_records(code_root, "claims"))
    assert n2 == n1 + 1

    classify_and_record(code_root)
    latest = _latest(code_root)
    assert len(read_records(code_root, "claims")) == n2 + 1, "新主张必须被写入计数（证不欠写）"
    assert latest["late"]["independent_evidence_count"] == 1, "新独立根：计数 = 1"


# ───────────────────────────── (b) 3 条真独立 ⇒ 3 ─────────────────────────────


def test_b_three_truly_independent_sources_count_three() -> None:
    """(b) 3 条**真独立**（根来源主张不在场）⇒ 产出方**不臆断** ⇒ 佐证 **3**（证不欠报）。"""
    rows = [_row(f"ind{i}", source_id=f"src-{i}", root_source_id=_ANON_MESSAGE) for i in range(3)]

    plan = plan_origin_attribution(rows)
    assert plan.links == {}, "根来源主张不在场 ⇒ 不得臆断补链"
    assert plan.residual_count == 1

    summary = classify_independence(rows)
    assert summary.independent_evidence_count["ind0"] == 3
    assert set(summary.independent_evidence_count.values()) == {3}


# ────────────────────────── (c) 同指纹无 origin + 根不在场 ⇒ 残留 ──────────────────────────


def test_c_same_fingerprint_without_origin_stays_overcounted_residual() -> None:
    """(c) 10 篇同指纹**但无** `origin_claim_id`、且**根来源主张不在场** ⇒ **现状如实登记**。

    **现状 = 仍算 10**：此时"真独立"（b）与"未标链的转述"（c）在 claim 字段上**同构**，
    产出方**不臆断**（`R-04`）⇒ 记为 `residual_groups`。**这是判定层产物，残余未闭合**（如实登记，不美化）。
    """
    rows = [
        _row(f"art{i}", source_id=f"article-{i}", root_source_id=_ANON_MESSAGE) for i in range(10)
    ]

    plan = plan_origin_attribution(rows)
    assert plan.links == {}, "根来源主张不在场 ⇒ 不臆断"
    assert plan.residual_count == 1, "整组登记为未闭合残余"
    assert plan.residual_groups and len(next(iter(plan.residual_groups.values()))) == 10

    summary = classify_independence(rows)
    assert summary.independent_evidence_count["art0"] == 10, "现状：仍算 10（残余，未闭合）"
    assert summary.propagation_count == 0


# ───────────────────────────── 错误路径 / 边界 ─────────────────────────────


def test_origin_cycle_is_loud_in_planner() -> None:
    """**错误路径**：`origin_claim_id` 成环 → 产出方**响亮失败**（不无限回溯）。"""
    rows = [_row("a", source_id="s1", origin="b"), _row("b", source_id="s2", origin="a")]
    with pytest.raises(IndependenceInputError, match="成环"):
        plan_origin_attribution(rows)


def test_empty_claims_is_vacuous() -> None:
    """**边界**：空 claims → 真空成立（`G-03` 显式 note），产出方不崩、无链。"""
    plan = plan_origin_attribution([])
    assert plan.links == {}
    assert plan.residual_count == 0
    assert any("NO_CLAIMS" in note for note in plan.notes)
