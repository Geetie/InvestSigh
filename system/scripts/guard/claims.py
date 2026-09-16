"""`claims.py` —— 主张构造口（`Ch9 §3.4.6` 措施④）。

构造 `schema.models.Claim` 的**唯一**口：`claim_nature` 为**必填无默认**形参
→ 调用方**无法省略**；即便绕过，pydantic 的 `Claim.claim_nature`（无默认）
也会在 `schema.store.append_records` 的 `model_validate` 处抛错 → **不写、不兜底**。

★ 本批次**不**实现 `claim_form` / `official_claim_kind` 的判定逻辑；
  仅要求三字段由调用方给出、维度不互换（`Ch9 §3.4.6` R-17 / D-02）。
"""

from __future__ import annotations

from typing import Any

from schema.models import Claim, ClaimForm, ClaimNature, SourceTier

__all__ = ["build_claim"]


def build_claim(
    *,
    claim_id: str,
    source_id: str,
    quote_hash: str,
    claim_nature: ClaimNature,
    claim_form: ClaimForm,
    tier: SourceTier,
    locator: str = "",
    **extra: Any,
) -> Claim:
    """构造 `schema.models.Claim` 的**唯一**口。

    ★ `claim_nature` 是必填关键字参数（**无默认**）→ 调用方**无法省略**：
      省略即 `TypeError`（构造口），非法取值/其它字段缺失即 pydantic `ValidationError`。
    ★ `claim_form` / `tier` 同样由调用方给出、维度不互换（R-17）。
    ★ `**extra` 透传给 `Claim`（如 `tier_basis` / `official_claim_kind` / 时间字段等），
      由 `Claim` 的 pydantic 校验兜底；`extra="forbid"` 时未知字段会抛错。
    """
    payload: dict[str, Any] = {
        "claim_id": claim_id,
        "source_id": source_id,
        "quote_hash": quote_hash,
        "claim_nature": claim_nature,
        "claim_form": claim_form,
        "tier": tier,
        "locator": locator,
    }
    payload.update(extra)
    return Claim(**payload)
