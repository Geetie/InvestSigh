"""`annotate.py` —— 角色标注 + prompt 组装（`Ch9 §3.4.6` 措施①·prompt 侧）。

把外部文本包成"**待分析数据**"块（`role="untrusted_analysis_data"`）——
标注**由执行器施加**，不是文本自带；执行器**不解析**文本里的伪角色
（`[SYSTEM]` / `</system>` / `Human:` 等一律当作**不透明字符串**）。

★ 结构性保证（对齐 AC-09 / AC-20）："伪角色不产生角色升级"是因为**不查找、不识别**
  文本里的角色标记 —— 这是物理分离，**不是关键词拦截**。
★ `_escape_boundary`：只转义**执行器自己的块边界哨兵**（防外部文本伪造块边界）。
  这是结构转义（同 SQL 参数化 / HTML 转义），**不是关键词黑名单**，对正常文本零误报。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

__all__ = [
    "DATA_ROLE",
    "BOUNDARY_SENTINEL",
    "AnnotatedData",
    "annotate_as_data",
    "assemble_prompt_context",
]

DATA_ROLE = "untrusted_analysis_data"
"""外部文本数据块的角色标签（语义＝"待分析数据"）。全包**唯一定义**在本模块（设计 §7.2）。"""

BOUNDARY_SENTINEL = "<<<INVESTSIGH_DATA_BLOCK>>>"
"""执行器**自身**的数据块边界哨兵 —— 只有执行器能产出它，外部文本若含同名串则被转义。"""


def _escape_boundary(text: str) -> str:
    """转义**执行器自己的边界哨兵**（防外部文本伪造块边界）。

    ★ 结构性转义，非关键词黑名单：只针对 `BOUNDARY_SENTINEL` 这一个执行器协议串，
      对任何正常研究文本**零改动、零误报**。
    """
    if BOUNDARY_SENTINEL not in text:
        return text
    # 在哨兵内插入零宽替换符，使其不再与执行器自身的边界串逐字相等
    neutralized = BOUNDARY_SENTINEL.replace("<<<", "<\u200b<<").replace(">>>", ">>\u200b>")
    return text.replace(BOUNDARY_SENTINEL, neutralized)


@dataclass(frozen=True)
class AnnotatedData:
    """一段被标注为"待分析数据"的外部文本。"""

    role: str          # 恒 == DATA_ROLE
    source_ref: str    # 来源引用（source_id / raw 相对路径）
    locator: str       # 定位（页码/段落/表格/字幕时间点）
    body: str          # 外部文本（仅转义了执行器自身的块边界哨兵）

    def render(self) -> str:
        """渲染成一段带角色标注的数据块（标记 `role=untrusted_analysis_data`）。"""
        head = f"{BOUNDARY_SENTINEL} role={self.role}"
        meta = f"source_ref={self.source_ref} locator={self.locator}"
        return f"{head}\n{meta}\n{self.body}\n{BOUNDARY_SENTINEL}"


def annotate_as_data(text: str, *, source_ref: str, locator: str = "") -> AnnotatedData:
    """把一段外部文本包成"待分析数据"块。**执行器施加标注**，不解析文本内容。

    ★ 本函数**不查找、不识别**文本里的 `[SYSTEM]` / `</system>` / `Human:` 等伪角色 ——
      它只是把文本当**不透明字符串**放进数据块。因此"伪角色不产生角色升级"是
      **结构性保证**，不是关键词拦截。
    ★ `source_ref` 为空 → `ValueError`（来源可回溯是硬要求）。
    """
    if source_ref is None or str(source_ref).strip() == "":
        raise ValueError("source_ref 不得为空（来源可回溯是硬要求）")
    return AnnotatedData(
        role=DATA_ROLE,
        source_ref=str(source_ref),
        locator=str(locator),
        body=_escape_boundary(text),
    )


def assemble_prompt_context(items: Sequence[AnnotatedData]) -> str:
    """把若干数据块组装成 prompt 的**数据段**（每个块一个角色标注）。空序列 → 返回 `""`。"""
    return "\n".join(item.render() for item in items)
