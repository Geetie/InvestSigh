"""`registry/` 与 `audit/` 下 JSONL 的对象模型。

权威出处：
- `Ch9 §3.4.9` `registry/corporate-actions.jsonl`：`{security_id, type(div/split/spinoff),
  effective_date, pay_date, ratio/amount, confirmation_status, source}`
- `Ch9 §N9.3-09/10/11` 来源质量与作者表现**以人工核验样本为基准标签**，模型自评不得替代
- `Ch1 §G` / `Ch2 §E` `audit/rule_changes.jsonl`：任何影响买卖条件的改动（**含展示逻辑**）留痕
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from .models import CorporateActionType, TBD


class _RegBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UnknownRegistryJsonlError(KeyError):
    """未登记的 `registry/` / `audit/` JSONL —— **响亮失败**，不静默建新文件。"""


class ReverseSplitDirection(str, Enum):
    """公司行动方向（消歧：拆股比率的方向必须显式，否则"2:1"含义相反）。"""

    forward = "forward"
    reverse = "reverse"


class CorporateAction(_RegBase):
    """公司行动（`Ch9 §3.4.9` / `§N9.3-08`）。

    计算顺序：**先按公司行动复权价格序列 → 再走 `compute_total_return`**。
    T11 通过点：① 复权与再投资正确处理
                ② **盘后消息的信号生效价取下一交易日开盘**（不得用消息前报价）
    """

    action_id: str
    security_id: str
    type: CorporateActionType
    effective_date: date
    pay_date: date | None = None
    direction: ReverseSplitDirection | None = None    # 仅 split 适用
    split_ratio: str | None = None                    # 仅 split 适用（如 "4:1"）
    dividend_amount: Decimal | None = None            # 仅 div 适用
    currency: str | None = None
    confirmation_status: str = TBD                    # 公告 / 已生效 / 待确认
    source: str = ""                                  # 来源引用（source_id 或 URL）
    method_version: str = "v1"                        # 复权/总回报方法及版本（N9.3-08）

    @field_serializer("dividend_amount")
    def _ser_amount(self, v: Decimal | None) -> str | None:
        return None if v is None else str(v)


class QualityLabel(_RegBase):
    """来源 / 作者质量的**人工核验样本**（`Ch9 §N9.3-11`）。

    ★ 权威质量标签**必须由人工核验样本支撑**；模型自评只能作辅助且**不被当作事实**、
    **不得直接用于证据加权**（`Ch9 §2.5.3`）。
    """

    label_id: str
    subject_kind: str                 # source / author
    subject_id: str
    domain: str = TBD                 # 专业领域（领域划分粒度未定）
    human_verified: bool
    verified_by: str = ""
    verified_at: datetime | None = None
    label_value: str
    evidence_note: str = ""
    model_self_assessment: str | None = None
    """模型自评——**仅辅助信号**，不得作为 ground truth、不得用于证据加权。"""


class RuleChangeRecord(_RegBase):
    """规则变更审计（`Ch1 §G` / `Ch2 §E`）。

    任何**影响买卖条件的改动**（**含展示逻辑**）都要写一条。
    """

    change_id: str
    changed_at: datetime
    rule_version_before: str
    rule_version_after: str
    target_file: str
    target_anchor: str = ""           # **节号锚点**，禁绝对行号（纪律 6）
    reason: str
    affects_buy_sell_condition: bool
    affects_display_logic: bool = False
    approved_by: str = TBD


class IdempotencyRecord(_RegBase):
    """幂等键登记（`Ch1 §C.3` / `Ch9 §3.5`）。

    防重复建单；`enqueue` 永远成功，`execute` 受预算 cap 约束。
    """

    idempotency_key: str
    first_seen_at: datetime
    task_ref: str
    statement: str = ""


# ───────────────────────── 登记层真源映射（**接线的关键**） ─────────────────────────
#
# ★ 分工（两者**不得混用**）：
#   - `schema/models.py::JSONL_MODELS` = `facts/` 的**恰好 18 个**（不得增删改名）
#   - `REGISTRY_MODELS`                = `registry/` 与 `audit/` 的登记层真源
#
# ★ 为什么必须有这张表：这些模型曾被造出来但**无人导入**（孤儿模块）——
#   而 `registry/prep_deliverables.yaml` 却声明 `QualityLabel` 是"人工核验
#   ground truth"的载体。**声明了载体却没人用**正是 `§一 底线 2`「真接线」要抓的
#   第二类假交付（它能通过 100% 覆盖率测试：类写好了、字段齐了，但从不被触发）。
#   本表 + `scripts/checks/registry_schema_guard.py` 就是它的读取方。
REGISTRY_MODELS: dict[str, type[_RegBase]] = {
    "registry/corporate-actions": CorporateAction,
    "registry/quality-labels": QualityLabel,
    "registry/idempotency": IdempotencyRecord,
    "audit/rule_changes": RuleChangeRecord,
}


def registry_model_for(stem: str) -> type[_RegBase]:
    """取登记层模型。未知 stem → `UnknownRegistryJsonlError`（**不静默**）。"""
    if stem not in REGISTRY_MODELS:
        raise UnknownRegistryJsonlError(
            f"未登记的 registry/audit JSONL: {stem!r}；"
            f"合法值: {sorted(REGISTRY_MODELS)}。如需新增，先在此表登记模型。"
        )
    return REGISTRY_MODELS[stem]
