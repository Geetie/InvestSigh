"""`rulewrite.py` —— 规则写收口点（`Ch9 §3.4.6` 措施② + `R-01`）。

外部文本触发"写规则内核"的**唯一**收口点：**永不落盘**。

★ 本函数给 `config.rules.refuse_write()`（此前**零调用**）一个**真实调用方**
  （`R-01` 附带收益 / 规避 `D-13` 孤儿）。
★ 这是**唯一**的规则写路径：不存在"先落盘后校验"的静默路径。
"""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

from config.rules import ReadOnlyRuleViolation, refuse_write

__all__ = ["write_rule"]


def write_rule(path: str | Path, content: str) -> NoReturn:
    """外部文本触发"写规则内核"的**唯一**收口点。**恒抛** `ReadOnlyRuleViolation`。

    步骤：
      1) 调 `config.rules.refuse_write(path)`：目标在 `rules/` 内 → 抛 `ReadOnlyRuleViolation`；
      2) 目标不在 `rules/` 内也**一律**抛 `ReadOnlyRuleViolation`
         （外部文本同样不得写任何"规则内核"文件）。

    `content` 只用于说明调用方**意图写入的内容**，**不参与落盘**（本函数无任何写盘副作用）。
    """
    # ① 先过"规则只读"收口点；`rules/` 目标在此即被拒。
    refuse_write(path)
    # ② 即便目标不在 `rules/` 内，外部文本也不得写任何规则内核文件 —— 一律拒绝。
    raise ReadOnlyRuleViolation(
        f"外部文本不得写入规则内核（Ch9 §3.4.6 措施②）：拒绝写入 {Path(path)}"
        f"（意图内容 {len(content)} 字符，不落盘）"
    )
