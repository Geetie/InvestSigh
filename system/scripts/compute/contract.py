"""确定性计算层的公共契约（`Ch9 §3.4.4` / `§3.4.5` / `§3.5` 阶段④）。

本模块只提供**三类东西**，代码即契约：

1. **异常族** —— 用**类型**区分"缺口"与"硬错误"，而不是用返回值：
   `MissingInput` / `UndefinedComputation`（→ 缺口对象）；`CaliberViolation` / `OrderViolation`
   （→ 响亮失败，**不得**降级成缺口）。
2. **`ComputeGap`** —— 缺口对象。输入缺失时**输出它**，而不是 `None` / `0` / 估算值（`Ch9 §3.5`
   阶段④失败处理：**输入缺失 → 输出缺口对象，不出数值**）。
3. **`make_derived()`** —— 唯一构造 `DerivedValue` 的入口，强制携带
   `formula` + `operands[]` + `method_version`（`Ch9 §3.4.4`：**必须携带**）。

★ 为什么算术必须落程序层（`Ch9 §2.4.3`）：模型只做**抽取输入 / 提出假设 / 生成叙述**；
  同比、毛利率、CAGR、超额收益、含分红再投资总回报、FX、股本变化、企业价值、价格隐含增长率
  **一律由本层的确定性函数产出并单测**，落库数字必须能追到 operand。

★ 定位（在 `scripts/compute/**` 内）：本层是**纯函数式计算**，不联网、不读全网、不猜数——
  输入由调用方注入（`PricePoint` 序列 / `Decimal` 取值 / 引用串）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

from schema.models import DerivedValue

METHOD_VERSION = "compute-v1"
"""本计算层的方法版本（`Ch9 §3.4.4` 的 `method_version`）。

★ 变更语义（`Ch9 §2.3` / 纪律 4 追加式不可变）：`method_version` 一变，
  **必须产生新的 `DerivedValue` 行**，**不得**就地覆盖旧行。旧行在其期间内仍是
  "当时有效判断"。持久化层（`scripts.compute.store`）以
  `(derived_id, method_version)` 为幂等键实现"新增放行、重跑跳过"。
"""


class ComputeError(Exception):
    """计算层异常基类。携带结构化上下文，供上层决定"缺口"还是"硬错误"。"""

    def __init__(
        self,
        message: str,
        *,
        missing: Sequence[str] | None = None,
        formula: str = "",
        operands: Sequence[str] | None = None,
        subject: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.missing: list[str] = list(missing or [])
        self.formula = formula
        self.operands: list[str] = list(operands or [])
        self.subject = subject


class MissingInput(ComputeError):
    """必需输入缺失 → 上层须输出**缺口对象**（`Ch9 §3.5` 阶段④）。"""


class UndefinedComputation(ComputeError):
    """输入存在但**该计算在此输入上无定义**（除零 / 空序列 / 非正股本）→ 缺口对象。"""


class CaliberViolation(ComputeError):
    """口径违例（如基准收益来源非基金行情）→ **响亮失败**，不降级成缺口。"""


class OrderViolation(ComputeError):
    """时间顺序倒置（倒填）→ **拒绝**（`Ch5 §D.3` / `§D.4` 第四条规则）。"""


# ─────────────────────────── 缺口对象（Ch9 §3.5 阶段④） ───────────────────────────


@dataclass(frozen=True)
class ComputeGap:
    """计算缺口对象 —— "输入缺失"的**显式**表达（≠ 0，≠ None，≠ 估算值）。

    字段刻意保持最小且可序列化（落 `derived/compute_gaps.jsonl`）：

    | 字段 | 语义 |
    |---|---|
    | `gap_id` | 稳定缺口键（幂等重跑不重复） |
    | `subject` | 被算对象（`security_id` / `company_id` / `derived_id` 语境） |
    | `missing` | 缺失输入名列表（**非空** —— 空表示这不是缺口，是 bug） |
    | `reason` | 人类可读原因（含节号锚点） |
    | `method_version` | 企图使用的方法版本 |
    | `recorded_at` | 记录时间（system_time，**永远可知**，不得为 None） |
    """

    gap_id: str
    subject: str
    missing: list[str]
    reason: str
    method_version: str
    recorded_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSONL 行（`recorded_at` → ISO8601 字符串）。"""
        return {
            "gap_id": self.gap_id,
            "subject": self.subject,
            "missing": list(self.missing),
            "reason": self.reason,
            "method_version": self.method_version,
            "recorded_at": self.recorded_at.isoformat(),
        }


# ─────────────────────────── DerivedValue 唯一构造入口 ───────────────────────────


def make_derived(
    derived_id: str,
    value: Decimal,
    formula: str,
    operands: Sequence[str],
    *,
    method_version: str = METHOD_VERSION,
    computed_at: datetime | None = None,
) -> DerivedValue:
    """构造 `DerivedValue`，**强制**三要件非空（`Ch9 §3.4.4`）。

    违例（`derived_id` 为空 / `formula` 为空 / `operands` 为空 / `method_version` 为空）
    → `CaliberViolation`：**必须能追到 operand**，追不到就不是确定性计算。
    这不是缺口（缺口是"输入没到"），是**契约被破坏** → 响亮失败。
    """
    if not derived_id:
        raise CaliberViolation("derived_id 不得为空（Ch9 §3.4.4）")
    if not formula:
        raise CaliberViolation(f"{derived_id}: formula 不得为空（必须存公式而非仅结果，Ch9 §3.4.5）")
    if not list(operands):
        raise CaliberViolation(f"{derived_id}: operands 不得为空（落库数字必须能追到 operand，Ch9 §2.4.3）")
    if not method_version:
        raise CaliberViolation(f"{derived_id}: method_version 不得为空（Ch9 §3.4.4）")
    return DerivedValue(
        derived_id=derived_id,
        value=value,
        formula=formula,
        operands=list(operands),
        method_version=method_version,
        computed_at=computed_at or datetime.now(timezone.utc),
    )


def derived_id_for(kind: str, subject: str, *, method_version: str = METHOD_VERSION) -> str:
    """稳定 `derived_id`：`dv-<kind>-<subject>-<method_version>`（同输入同输出 → 幂等）。"""
    safe_subject = subject.strip().replace(" ", "_") or "unknown"
    return f"dv-{kind}-{safe_subject}-{method_version}"


def require_present(values: Mapping[str, Any], names: Sequence[str], *, subject: str) -> None:
    """断言 `names` 在 `values` 中且非 None；缺任一 → `MissingInput`（列全部缺失名）。"""
    missing = [name for name in names if values.get(name) is None]
    if missing:
        raise MissingInput(
            f"{subject}: 缺必需输入 {missing}（Ch9 §3.5 阶段④：输入缺失 → 输出缺口对象）",
            missing=missing,
            subject=subject,
        )


def require_nonzero(value: Decimal, name: str, *, subject: str) -> None:
    """分母/股本为 0 → `UndefinedComputation`（缺口对象，不抛 `ZeroDivisionError`）。"""
    if value == 0:
        raise UndefinedComputation(
            f"{subject}: {name} 为 0，该计算无定义（Ch9 §2.4.3 边界）",
            missing=[name],
            subject=subject,
        )


def gap_for(exc: ComputeError, *, kind: str) -> ComputeGap:
    """把"缺口类"异常折叠成 `ComputeGap`；非缺口类异常由调用方拦下（不在此折叠）。"""
    missing = exc.missing or ["<unspecified>"]
    subject = exc.subject or "<unknown>"
    return ComputeGap(
        gap_id=derived_id_for(f"gap-{kind}", subject),
        subject=subject,
        missing=missing,
        reason=exc.message,
        method_version=METHOD_VERSION,
        recorded_at=datetime.now(timezone.utc),
    )


def safe_compute(
    computation: Callable[[], DerivedValue],
    *,
    kind: str,
    subject: str,
) -> DerivedValue | ComputeGap:
    """把"会抛缺口类异常"的计算包成 `DerivedValue | ComputeGap`。

    - `MissingInput` / `UndefinedComputation` → **缺口对象**（`Ch9 §3.5` 阶段④）。
    - `CaliberViolation` / `OrderViolation` → **原样抛出**（响亮失败，不当缺口吞掉，
      对齐 `AC-05`：不吞异常、不置 null）。
    """
    try:
        return computation()
    except (MissingInput, UndefinedComputation) as exc:
        if not exc.subject:
            exc.subject = subject
        return gap_for(exc, kind=kind)
