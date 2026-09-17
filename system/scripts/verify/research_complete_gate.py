#!/usr/bin/env python3
"""`research_complete_gate.py` —— 「研究完成」判定器 + 反 KPI 断言 `S-01`。

```
python system/scripts/verify/research_complete_gate.py [code_root] [--no-report]
```

## 它是什么（`10_验收与持续复盘/02_实现方案.md §B.4` 逐字）

> 需求 N10.2-04 要禁「把**生成了日报 / 页面能打开 / 问答听起来合理**当作研究完成的充分条件」。
> **判定器不得新增门槛** —— 直接复用 `Ch7 §D` 前置门
> （`research_complete` + `has_explainable_forecast` + `DerivedValue`），**不新增一把门**
> （`C10-6` / `S-07` 红线）。

⇒ 本模块**只有一把尺**：`scripts/decision/gate.py`（`Ch7 §D`）的三个门函数。
  **绝不**在这里定义第二套"研究完成"标准（`G-06` 唯一真源）。

| 组成 | 复用点 |
|---|---|
| `is_research_complete()` | 调用 `Ch7 §D` 的 `research_complete()` / `has_explainable_forecast()` / `require_derived_worksheet()` —— **三者缺一不可**，**不新增门槛** |
| `assert_not_fake_complete()` | 反 KPI（`S-01`）：三假完成信号（载体 / 展示 / 通顺）**不得**作为完成充分条件 |

## 为什么本检查器要**自证**「真调用了 gate」（`AC-05`：零新增门槛）

「复用了 gate」如果只写在注释里，就**没有任何东西在守它** —— 把 `is_research_complete`
的体换成 `return True`，测试照样能写、文档照样自洽。故 `check()` 用 **AST 扫本文件**
证明 `is_research_complete` 的**函数体**真的调用了那三个门函数（`G-02`：函数体级绑定），
并**逐条探针**证明三假信号都会 `assert_not_fake_complete` 拒绝。
「换成 `return True`」会**当场变红**，而改一行数据**改不出来**。

## 边界（`AC-06`：不假绿，`G-03`）

数据侧**无被检对象**（`facts/tasks.jsonl` 无 `eval_result`）时，本检查器**不判通过也不判违例** ——
它把"无被检对象"作为 `note` + 计数**显式报出**（`G-03`：无被检对象 ≠ 已验证）。
「缺 `derived`」（底稿非 `DerivedValue`）由 `is_research_complete` 返回 `False`（**不假绿**）。

★ 退出码（`Ch2 §B.3`，命中即 fail）：`0` 放行 / `1` 命中违例 / `2` 输入异常。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any, Mapping

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import (  # noqa: E402
    CheckReport,
    Violation,
    run_checker,
)

#: 本文件的相对路径（被检 root 之下）。用于 AST 自证「判定器真的调用了 gate」。
SELF_RELPATH = "scripts/verify/research_complete_gate.py"

#: `Ch7 §D` 的**唯一真源**模块（判定器复用它，不另立第二把尺）。
GATE_MODULE_RELPATH = "scripts/decision/gate.py"

#: 判定器**必须**调用的三个 `Ch7 §D` 门函数（`§B.4` 逐字：三者缺一不可）。
REQUIRED_GATE_CALLS: tuple[str, ...] = (
    "research_complete",
    "has_explainable_forecast",
    "require_derived_worksheet",
)

#: 反 KPI（`S-01`，`§B.4` 的三假完成信号）：**载体 / 展示 / 通顺**都不是"研究完成"。
FAKE_COMPLETION_SIGNALS: frozenset[str] = frozenset(
    {"generated_daily_report", "page_opens", "answer_sounds_ok"}
)


class FakeCompletionError(ValueError):
    """以凡尔载体/展示/通顺冒充研究完成 —— **响亮拒绝**（`S-01`）。"""


def is_research_complete(inp: Any) -> bool:
    """「研究完成」= **`Ch7 §D` 门（唯一）**。三假信号**不参与**（`§B.4` 逐字）。

    ★ 判定 = `research_complete(inp)` **且** `has_explainable_forecast(inp)` **且**
      底稿是 `DerivedValue`（经 `require_derived_worksheet()`）。**不新增任何门槛**
      （不引入最低收益 / 置信度 / 覆盖阈值等 —— `§B.4` / `S-07` 红线）。

    ★ 「缺 `derived`」的处理（`AC-06`）：底稿非 `DerivedValue` → `require_derived_worksheet()`
      抛 `RawNumberRejected` → 本函数捕获并返回 `False`（**不假绿**：缺底稿 ≠ 完成）。
    """
    # ★ **就地导入**（模块顶层不 import）：`scripts.decision.gate` 依赖 `schema.models`
    #   （pydantic，首次导入 ≈1.2s），而本模块的 `check()` 路径**不需要**它 ⇒
    #   不该让检查器替它付这份开销（与 `pipeline` 的按需取用同一纪律）。
    from scripts.decision.gate import (  # noqa: PLC0415
        RawNumberRejected,
        has_explainable_forecast,
        require_derived_worksheet,
        research_complete,
    )

    if not research_complete(inp):  # ① 研究深度 ≥ baseline_done 且基线齐备
        return False
    if not has_explainable_forecast(inp):  # ② 个股与基准预测均可解释
        return False
    try:  # ③ 底稿**必须**是 DerivedValue（复用 §D.2 的响亮判定器，不新立标准）
        require_derived_worksheet(inp.stock_forecast)
    except RawNumberRejected:
        return False
    return True


def assert_not_fake_complete(signals: Mapping[str, Any] | Any) -> None:
    """反 KPI（`S-01`）：三假完成信号**不得**作为完成的充分条件。

    `signals` 是**被声称为"研究已完成"的证据键集合**（dict 的键 / 可迭代的名字）。
    命中任一假信号 ⇒ `FakeCompletionError`（**命中即 fail**，禁 warn-only）。
    """
    keys = set(signals.keys()) if isinstance(signals, Mapping) else set(signals)
    offending = FAKE_COMPLETION_SIGNALS & keys
    if offending:
        raise FakeCompletionError(
            f"以载体/展示/通顺冒充研究完成：{sorted(offending)} —— "
            "日报是**载体**、页面是**展示层**、问答通顺**无法追溯**，均**不构成**「研究完成」"
            "（`S-01` / N10.2-04）；唯一判据 = `Ch7 §D` 门（§B.4）"
        )


# ───────────────────────── 检查器（自证「零新增门槛」+ 反 KPI） ─────────────────────────


def _gate_calls_in_judge(self_path: Path) -> set[str]:
    """AST 扫本文件：`is_research_complete` **函数体**里调用的门函数名集合（`G-02`）。

    ★ 必须按**函数体**取（不看整文件）：否则在别处写一个 `research_complete` 字符串
      就能冒充"复用了 gate"。
    """
    tree = ast.parse(self_path.read_text(encoding="utf-8"), filename=str(self_path))
    target = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "is_research_complete"
        ),
        None,
    )
    if target is None:
        raise ValueError(
            f"{SELF_RELPATH} 里找不到 is_research_complete() —— 判定器本体缺失，"
            "不得据此判通过（`G-03`）"
        )
    names: set[str] = set()
    for node in ast.walk(target):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names


def _is_fake_rejected(token: str) -> bool:
    """`assert_not_fake_complete` 是否**拒绝**该信号（被拒 = 正确行为 ⇒ 返回 `True`）。

    ★ 用**带返回值的判定**表达"拒/未拒"，而**不是** `except …: continue` ——
      后者会被 `no_placeholder_guard` 判为"吞异常"（`SWALLOW_EXCEPTION_CONTINUE`）：
      异常在此被**读成决定**（`True`），而不是被无声丢弃。
    """
    try:
        assert_not_fake_complete({token: True})
    except FakeCompletionError:
        return True  # 命中假信号 ⇒ 被拒 ⇒ 正确
    return False  # 未被拒 ⇒ 该信号会冒充「研究完成」（`S-01` 违例）


def _fake_signals_rejected() -> list[str]:
    """逐条探针：每个假完成信号**必须**被 `assert_not_fake_complete` 拒 —— 返回**未被拒**的。"""
    return [token for token in sorted(FAKE_COMPLETION_SIGNALS) if not _is_fake_rejected(token)]


def _completion_candidates(root: Path) -> int:
    """`facts/tasks.jsonl` 里带 `eval_result` 的行数（数据侧被检对象计数，`G-03`）。"""
    import json

    path = root / "facts" / "tasks.jsonl"
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: 非法 JSON 行，无法统计完成判定对象: {exc}") from exc
        if isinstance(row, dict) and row.get("eval_result"):
            count += 1
    return count


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="research_complete_gate")
    report.scanned["fake_completion_signals"] = len(FAKE_COMPLETION_SIGNALS)
    report.scanned["required_gate_calls"] = len(REQUIRED_GATE_CALLS)

    # ── ① 零新增门槛（`AC-05`）：判定器**函数体**必须真的调用 Ch7 §D 的三个门函数 ──
    calls = _gate_calls_in_judge(root / SELF_RELPATH)
    report.scanned["gate_calls_in_judge"] = len(calls & set(REQUIRED_GATE_CALLS))
    for missing in sorted(set(REQUIRED_GATE_CALLS) - calls):
        report.violations.append(
            Violation(
                "N10.2-04",
                f"判定器 is_research_complete() **未调用** Ch7 §D 的门函数 {missing}() ⇒ "
                "可能另立了第二把尺（`§B.4` 禁新增门槛；`G-06` 唯一真源）。"
                f"唯一合法来源 = {GATE_MODULE_RELPATH}",
                SELF_RELPATH,
            )
        )

    # ── ② 反 KPI（`S-01`）：三假完成信号逐条**必须**被拒 ──
    not_rejected = _fake_signals_rejected()
    report.scanned["fake_signals_rejected"] = len(FAKE_COMPLETION_SIGNALS) - len(not_rejected)
    for token in not_rejected:
        report.violations.append(
            Violation(
                "N10.2-04",
                f"假完成信号 {token!r} **未被判定器拒绝** ⇒ 以载体/展示/通顺冒充研究完成"
                "（`S-01`；`§B.4` 三假信号表）",
                SELF_RELPATH,
            )
        )

    # ── ③ 边界（`AC-06` / `G-03`）：数据侧无被检对象 ⇒ **显式可见**，不判通过也不判违例 ──
    candidates = _completion_candidates(root)
    report.scanned["completion_candidates"] = candidates
    report.notes.append(
        "零新增门槛：判定器**只**复用 Ch7 §D 门"
        f"（{GATE_MODULE_RELPATH} 的 research_complete / has_explainable_forecast / "
        "require_derived_worksheet），本模块**不定义**任何'研究完成'阈值。"
    )
    if candidates == 0:
        report.notes.append(
            "无被检对象（`G-03`）：facts/tasks.jsonl 无 `eval_result` ⇒ 数据侧**没有**"
            "「研究完成」判定对象；**不得据『为空』判通过**（`AC-06`：不假绿）。"
            "本检查器对**判定器本体**（是否复用 gate + 是否拒三假信号）作断言，"
            "与『数据侧是否有对象』相互独立、各自可见。"
        )
    return report


if __name__ == "__main__":
    sys.exit(run_checker("research_complete_gate.py", check))
