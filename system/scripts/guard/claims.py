"""`claims.py` —— 主张构造口（`Ch9 §3.4.6` 措施④）。

构造 `schema.models.Claim` 的**唯一**口。

**两类必填关键字参数**（均**无默认值** → 调用方**无法省略**；即便绕过，pydantic 的
`Claim.claim_nature`（无默认）会在 `schema.store.append_records` 的 `model_validate`
处抛错 → **不写、不兜底**）：

- `claim_nature` / `claim_form` / `tier`：三字段维度不同，**不得互换、不得合并**
  （`Ch9 §3.4.6` R-17 / D-02）。
- 五类时间语义中的 **system_time 三元组**：`first_seen_at` / `analyzed_at` / `recorded_seq`
  （`Ch9 §2.2` / `§3.4.1`）。**system_time 永远可知** = 本次处理时间，**不得为 None**
  —— 为 None 会让 `schema.store.as_of` 的版本选取退化为"随便挑一个"，且使
  `first_seen_at` 不可复原（事后信息可能伪装成当时已知，`Ch9 §2.2` 行 915）。
  故此处除"函数签名无默认"外，另加**运行期** None 断言（`CONVENTIONS.md::R-06` ⑥：
  首选**运行时效果断言**）。
- valid_time（`occurred_at` / `published_at` / `effective_from`）与 `backfilled_at`：**可选**
  —— 来源未披露时间语义是合法的，保持 None。

★ 这些字段在 `schema.models.TimeMixin` 里**已存在**（`Ch9 §2.2`），本口只是把它们
  **真的填进去**，**不新增设计外字段**。
★ 本批次**不**实现 `claim_form` / `official_claim_kind` 的判定逻辑；仅要求由调用方给出、
  维度不互换（`Ch9 §3.4.6` R-17 / D-02）。
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
    first_seen_at: datetime,
    analyzed_at: datetime,
    recorded_seq: int,
    locator: str = "",
    occurred_at: datetime | None = None,
    published_at: datetime | None = None,
    effective_from: datetime | None = None,
    backfilled_at: datetime | None = None,
    **extra: Any,
) -> Claim:
    """构造 `schema.models.Claim` 的**唯一**口。

    ★ `claim_nature` 是必填关键字参数（**无默认**）→ 调用方**无法省略**：
      省略即 `TypeError`（构造口），非法取值/其它字段缺失即 pydantic `ValidationError`。
    ★ `claim_form` / `tier` 同样由调用方给出、维度不互换（R-17）。
    ★ **system_time 三元组**（`first_seen_at` / `analyzed_at` / `recorded_seq`）亦为必填、
      **无默认**：调用方**无法省略**（同 `claim_nature` 手法）。且此处再断 `None`
      （运行时效果断言）——`system_time` 永不未知，为 None 即**响亮失败**，不静默落库。
    ★ `occurred_at` / `published_at` / `effective_from` / `backfilled_at` 为**可选**
      （valid_time 未知合法）。
    ★ `**extra` 透传给 `Claim`（如 `tier_basis` / `official_claim_kind` 等），
      由 `Claim` 的 pydantic 校验兜底；`extra="forbid"` 时未知字段会抛错。

    ⚠️ 类型注解 `datetime` **不经运行期求值**（本模块 `from __future__ import annotations`，
      PEP 563）：数据路径模块（`scripts/guard/**`）受 `injection_guard.ALLOWED_IMPORTS`
      能力白名单约束，**不得** import `datetime`；由调用方传入的 `datetime` 值仍被正常接收。
    """
    missing_system_time = [
        name
        for name, value in (
            ("first_seen_at", first_seen_at),
            ("analyzed_at", analyzed_at),
            ("recorded_seq", recorded_seq),
        )
        if value is None
    ]
    if missing_system_time:
        raise ValueError(
            "system_time 永不未知，不得为 None："
            f"{missing_system_time}（Ch9 §2.2 / §3.4.1；为 None 会使版本选取退化）"
        )

    payload: dict[str, Any] = {
        "claim_id": claim_id,
        "source_id": source_id,
        "quote_hash": quote_hash,
        "claim_nature": claim_nature,
        "claim_form": claim_form,
        "tier": tier,
        "locator": locator,
        # ── 五类时间（Ch9 §2.2 / §3.4.1）：真的填进去，不新增字段 ──
        "first_seen_at": first_seen_at,
        "analyzed_at": analyzed_at,
        "recorded_seq": recorded_seq,
        "occurred_at": occurred_at,
        "published_at": published_at,
        "effective_from": effective_from,
        "backfilled_at": backfilled_at,
    }
    payload.update(extra)
    return Claim(**payload)
