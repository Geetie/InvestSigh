"""`toolwatch.py` —— 工具调用收口点与账本（`Ch9 §3.4.6` 措施③）。

工具调用的**唯一**收口点 `request_tool(origin=...)`：
`origin="external_text"` **必拒**；其余 origin 记入账本，使"零工具调用"可被**观测**
而非靠"我们没写"。

★ 账本是**局部**对象；不修改 `sys.path` / `sys.modules` / 全局审计钩子（规避 `D-23`）。
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, NoReturn

__all__ = [
    "ORIGIN_EXTERNAL",
    "ORIGIN_SYSTEM",
    "ToolCallLedger",
    "ToolInvocationBlocked",
    "request_tool",
    "tool_call_ledger",
]

ORIGIN_EXTERNAL = "external_text"
"""外部文本来源 —— 该来源不得触发任何工具调用。"""

ORIGIN_SYSTEM = "system"
"""系统侧来源 —— 记入账本（本批次无系统侧调用方，属阶段②起的接线口）。"""


class ToolInvocationBlocked(PermissionError):
    """工具调用被拒 —— 外部文本越出工具白名单，或本批次尚未接线系统侧调用。"""


@dataclass
class ToolCallLedger:
    """一次"处理外部文本"过程的**局部**工具调用账本。"""

    calls: list[tuple[str, str]] = field(default_factory=list)   # (tool_name, origin)

    def record(self, name: str, origin: str) -> None:
        """记一次工具调用尝试（含被拒尝试），使调用可被观测。"""
        self.calls.append((name, origin))

    @property
    def tool_calls(self) -> int:
        """本过程记录到的工具调用尝试总数。"""
        return len(self.calls)


@contextmanager
def tool_call_ledger() -> Iterator[ToolCallLedger]:
    """一次"处理外部文本"过程的作用域账本（局部对象，**不改全局进程状态**）。"""
    ledger = ToolCallLedger()
    yield ledger


def request_tool(name: str, *, origin: str, ledger: ToolCallLedger) -> NoReturn:
    """工具调用的**唯一**收口点。**恒抛** `ToolInvocationBlocked`（签名 `NoReturn`）。

    - `origin == ORIGIN_EXTERNAL` → **先**记录一次"被拒尝试"（计数 +1，使外部文本触发工具的
      事实可被观测），**再**抛 `ToolInvocationBlocked`（**必拒**）。
    - 其余 origin → 同样**先**记入账本（本批次**未授权任何工具调用**，故亦不返回），
      再抛 `ToolInvocationBlocked`。

    两种来源都记录进 `ledger`（§2.4 可观测性说明：正面控制会让 `tool_calls` 真的 +1，
    反向对照证明账本是活的）；差别仅在于 note/语义由调用方据 `origin` 判定。
    """
    ledger.record(name, origin)
    if origin == ORIGIN_EXTERNAL:
        raise ToolInvocationBlocked(
            f"外部文本不得触发工具调用（Ch9 §3.4.6 措施③）：拒绝 {name!r}"
        )
    raise ToolInvocationBlocked(
        f"本批次未接线任何工具调用（Ch9 §3.4.6 措施③；系统侧接线属阶段②+）：拒绝 {name!r}"
    )
