"""`fx.py` —— 汇率换算类确定性算术（`Ch9 §3.4.4` 目录 `fx`；`Ch9 §2.4.3` 排除清单含 FX 换算）。

模型**不得**口算 FX（`Ch9 §2.4.3`）；换算一律经本层，落库数字可追到汇率来源 operand。

- `convert_amount`: `amount * rate`（把 A 币种换算成 B 币种）。
- `compute_fx_adjusted_return`: 把本币收益折算为统一计价币的收益（同起止时间口径）。
- 缺汇率 / 汇率为 0 / 币种相同的误用 → **缺口对象**（不明智地返回原值冒充"已换算"）。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Sequence

from schema.models import DerivedValue

from .contract import MissingInput, UndefinedComputation, derived_id_for, make_derived, require_nonzero


def convert_amount(
    amount: Decimal,
    rate: Decimal,
    *,
    subject: str,
    from_currency: str,
    to_currency: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """金额换算：`amount * rate`（`rate` = 1 单位 `from_currency` 折 `to_currency`）。

    `from_currency == to_currency` → `UndefinedComputation`（**不是**"已换算"，
    静默返回原值会制造"两条不同口径被当成同口径"的假象）。
    """
    if not from_currency or not to_currency:
        raise MissingInput(
            f"{subject}: 币种未披露（from={from_currency!r}, to={to_currency!r}）",
            missing=["from_currency", "to_currency"],
            subject=subject,
        )
    if from_currency == to_currency:
        raise UndefinedComputation(
            f"{subject}: 源币种与目标币种相同（{from_currency}），无需换算",
            missing=["rate"],
            subject=subject,
        )
    require_nonzero(rate, "rate（汇率）", subject=subject)
    value = amount * rate
    formula = f"{amount} * fx_rate({from_currency}->{to_currency})"
    return make_derived(
        derived_id_for("fx_convert", f"{subject}-{from_currency}-{to_currency}"),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )


def compute_fx_adjusted_return(
    local_return: Decimal,
    rate_begin: Decimal,
    rate_end: Decimal,
    *,
    subject: str,
    operands: Sequence[str],
    computed_at: datetime | None = None,
) -> DerivedValue:
    """含汇率变动的总收益：`(1 + local_return) * (rate_end / rate_begin) - 1`。

    汇率起点为 0 → **缺口对象**（不得除零）。
    """
    require_nonzero(rate_begin, "rate_begin（期初汇率）", subject=subject)
    value = (Decimal(1) + local_return) * (rate_end / rate_begin) - Decimal(1)
    formula = f"(1 + {local_return}) * ({rate_end} / {rate_begin}) - 1"
    return make_derived(
        derived_id_for("fx_adjusted_return", subject),
        value,
        formula,
        operands,
        computed_at=computed_at,
    )
