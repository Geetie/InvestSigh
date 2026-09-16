"""T-11 / T-12 契约变更测试（`ws/evidence-fix` · 批次 10 收口）。

- **T-11**：`ClaimPropagation.kind` 承载 `Ch6 §C.3` 人工别名覆盖（`manual_alias_override`），
  且 **旧行（无 `kind` 字段）仍合法**；不新增第 19 个 JSONL（`Ch9 §3.3.3`）。
- **T-12**：`Claim.independent_evidence_count` 可选字段（默认 `None` = 未计算），
  且 **真仓库既有 claim 行仍合法**（`Ch9 §3.4.2` 追加式不可变）。
- **生成物一致**：`schema_sync_guard` 绿（改模型不改生成物会被逮）。

★ 依据：需求方 2026-09-16 授权的两处契约变更；`06_公开信息与证据筛选/02_实现方案.md §C.2/§C.3/§C.4/§B.4`。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from conftest import SYSTEM_ROOT, run_gate  # noqa: F401
from schema.models import (
    JSONL_MODELS,
    AliasOverride,
    Claim,
    ClaimPropagation,
    PropagationKind,
)
from schema.store import append_records, read_records

_AT = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

# pre-change 形状：真仓库里"历史行"会长成什么样（无 kind / 无 alias_override）
_LEGACY_PROPAGATION_ROW = {
    "propagation_id": "prop-legacy",
    "root_claim_id": "root",
    "propagated_claim_id": "re0",
    "publisher_entity": "KOL",
    "carrier_platform": "x",
    "independent_evidence": False,
}

# pre-change 形状的 claim 行（无 independent_evidence_count）
_LEGACY_CLAIM_ROW = {
    "claim_id": "claim-legacy",
    "source_id": "s-legacy",
    "quote_hash": "q-legacy",
    "claim_nature": "fact",
    "claim_form": "citation",
    "tier": "primary",
}


# ───────────────────────── T-11 · `claim_propagation.kind` ─────────────────────────


def test_t11_manual_alias_override_roundtrips(code_root: Path) -> None:
    """T-11 正向：`kind=manual_alias_override` + 四要素载荷可落库读回（`Ch6 §C.3`）。"""
    row = ClaimPropagation(
        propagation_id="prop-alias",
        root_claim_id="root",
        propagated_claim_id="other",
        kind=PropagationKind.manual_alias_override,
        alias_override=AliasOverride(
            is_independent=True, reason="人工确认两条实为同一事件", operator="ops-1", at=_AT
        ),
    )
    assert append_records(code_root, "claim_propagation", [row]) == 1
    back = read_records(code_root, "claim_propagation")
    assert back[0]["kind"] == "manual_alias_override"
    assert back[0]["alias_override"] == {
        "is_independent": True,
        "reason": "人工确认两条实为同一事件",
        "operator": "ops-1",
        "at": "2026-09-16T12:00:00Z",
    }


def test_t11_default_kind_is_restatement(code_root: Path) -> None:
    """T-11 正向：默认构造（不显式给 kind）⇒ `restatement`（自动去重判定的转述，`§C.2` 步骤④）。"""
    row = ClaimPropagation(
        propagation_id="prop-auto", root_claim_id="root", propagated_claim_id="re1"
    )
    assert row.kind is PropagationKind.restatement
    append_records(code_root, "claim_propagation", [row])
    assert read_records(code_root, "claim_propagation")[0]["kind"] == "restatement"


def test_t11_legacy_row_without_kind_still_valid() -> None:
    """★ T-11 向后兼容（硬约束）：**旧行**（无 `kind`/`alias_override`）仍合法，取默认值。

    依据 `Ch9 §3.4.2`（追加式不可变 —— 既有行不得因新字段失效）。
    """
    obj = ClaimPropagation.model_validate(_LEGACY_PROPAGATION_ROW)
    assert obj.kind is PropagationKind.restatement
    assert obj.alias_override is None


def test_t11_override_kind_requires_payload() -> None:
    """T-11 错误路径：`kind=manual_alias_override` **缺**载荷 ⇒ 响亮失败（不得有半截人工覆盖）。"""
    with pytest.raises(ValueError, match="必须携带 alias_override"):
        ClaimPropagation(
            propagation_id="p",
            root_claim_id="r",
            propagated_claim_id="c",
            kind=PropagationKind.manual_alias_override,
        )


def test_t11_payload_forbidden_for_plain_restatement() -> None:
    """T-11 错误路径（反向）：非覆盖 `kind` **不得**携带载荷（防"标了转述却藏人工判定"）。"""
    with pytest.raises(ValueError, match="仅在 kind=manual_alias_override 时允许"):
        ClaimPropagation(
            propagation_id="p",
            root_claim_id="r",
            propagated_claim_id="c",
            kind=PropagationKind.restatement,
            alias_override=AliasOverride(
                is_independent=False, reason="x", operator="ops", at=_AT
            ),
        )


def test_t11_no_19th_jsonl() -> None:
    """★ T-11 硬约束：`facts/` 仍恰好 **18** 个 JSONL（`Ch9 §3.3.3` 不得增删改名）。"""
    assert len(JSONL_MODELS) == 18
    assert "claim_propagation" in JSONL_MODELS
    assert "claim_alias" not in JSONL_MODELS, "不得新增第 19 个 JSONL（并入 claim_propagation）"


# ───────────────────────── T-12 · `Claim.independent_evidence_count` ─────────────────────────


def test_t12_field_roundtrips(code_root: Path) -> None:
    """T-12 正向：去重步骤写入的**独立佐证基数**（`Ch6 §B.4`：基数非权重）可落库读回。"""
    append_records(
        code_root,
        "claims",
        [
            Claim(
                claim_id="root",
                source_id="anon-order-msg",
                quote_hash="q-root",
                claim_nature="fact",
                claim_form="original_investigation",
                tier="secondary_tertiary",
                independent_evidence_count=1,
            )
        ],
    )
    back = read_records(code_root, "claims")
    assert back[0]["independent_evidence_count"] == 1


def test_t12_legacy_claim_row_defaults_to_none() -> None:
    """★ T-12 向后兼容（硬约束）：无该字段的旧行仍合法，取默认 `None`（= 未计算）。"""
    obj = Claim.model_validate(_LEGACY_CLAIM_ROW)
    assert obj.independent_evidence_count is None


def test_t12_real_repo_claims_still_valid() -> None:
    """★ T-12 向后兼容（**真实数据**）：真仓库现有 `facts/claims.jsonl` 逐行仍合法，且默认 `None`。

    `Ch9 §3.4.2` 追加式不可变 ⇒ 契约变更**不得**让真仓库既有行失效。
    """
    rows = read_records(SYSTEM_ROOT, "claims")
    assert rows, "真仓库 claims 不应为空（否则该用例真空，G-03）"
    for row in rows:
        obj = Claim.model_validate(row)
        assert obj.independent_evidence_count is None, "既有行未被写入过该字段 ⇒ 默认 None"


# ───────────────────────── 生成物一致（改模型不改生成物会被逮）─────────────────────────


def test_schema_generated_matches_models() -> None:
    """`schema_sync_guard` 绿：生成物 `facts.schema.json` == 由 `models.py` 现算（`Ch9 §3.3.3`）。"""
    result = run_gate("scripts/checks/schema_sync_guard.py", SYSTEM_ROOT)
    assert result.returncode == 0, result.stdout
    assert "scanned objects: 18" in result.stdout
