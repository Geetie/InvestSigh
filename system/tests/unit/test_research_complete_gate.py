"""`research_complete_gate`（「研究完成」判定器 + 反 KPI `S-01`）的可执行证据。

被检对象：`scripts/verify/research_complete_gate.py`
权威：`10_验收与持续复盘/02_实现方案.md §B.4`（**复用 `Ch7 §D` gate，零新增门槛**）+ `§E.3`
      + `01_产品目标与核心闭环/02_实现方案.md §D.3`（反 KPI：每日维护 ≠ 每日产信号）。

## 为什么这些用例必须存在（`G-05`：不测它就只是"写了"）

| 断言 | 含义 |
|---|---|
| `gate_calls_in_judge == 3` | **零新增门槛**的机器绑定（`AC-05`）：判定器**函数体**真的调用了 `Ch7 §D` 的三个门函数 |
| 把三处调用掏空 ⇒ 门禁 `exit 1` | ★ **判别力**：证明上面那条"自证复用"不是恒真的一句文本 |
| 三假信号逐条被拒 | 反 KPI（`S-01`）：载体 / 展示 / 通顺不得冒充研究完成 |
| 缺 `derived` ⇒ `is_research_complete` 返回 `False` | `AC-06`：不假绿 |
| 无 `eval_result` ⇒ `note` + 计数 | `G-03`：无被检对象 ≠ 已验证 |

## 为什么落 `tests/unit/`

`criterion_effectiveness_guard._test_index()` 用 AST 扫 **`tests/**`**，本文件**无需**入
`verify.py::BATCHES` 的注入片（`tests/unit/` 的批次目标是一个**目录**，新文件自动被覆盖）。
"""

from __future__ import annotations

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from conftest import run_gate_inproc

GATE = "scripts/verify/research_complete_gate.py"


def _inject(path: Path, *, old: str, new: str) -> None:
    """把 `old` 换成 `new` 并★**自证注入已生效**（锚点写错 ⇒ `write_text` 写回原文 ⇒ no-op）。"""
    text = path.read_text(encoding="utf-8")
    assert old in text, f"注入点未找到（上游文本已变？）：{old!r}"
    mutated = text.replace(old, new)
    assert mutated != text, "注入是 no-op —— 替换前后文本相同，本用例将毫无判别力"
    path.write_text(mutated, encoding="utf-8")
    assert path.read_text(encoding="utf-8") == mutated, "注入未落盘"


# ─────────────────────── ① 干净输入：复用门 + 反 KPI + 被检域可见 ───────────────────────


def test_cli_passes_and_proves_reuse_and_anti_kpi(code_root: Path) -> None:
    """干净副本上 `exit 0`，且**报出**"复用了三个门 + 拒了三假信号 + 被检对象计数"。"""
    code, out = run_gate_inproc(GATE, code_root)

    assert code == 0, f"干净副本上应 exit 0，实得 {code}\n{out}"
    assert "scanned required_gate_calls: 3" in out, out
    assert "scanned gate_calls_in_judge: 3" in out, (
        f"判定器函数体**未**检测到三个 Ch7 §D 门调用 ⇒ 可能另立了第二把尺（§B.4）\n{out}"
    )
    assert "scanned fake_signals_rejected: 3" in out, f"三假完成信号应全部被拒（S-01）\n{out}"
    assert "scanned completion_candidates:" in out, f"未报被检对象计数（G-03）\n{out}"
    assert "零新增门槛" in out, f"应说明判定器只复用 Ch7 §D 门\n{out}"


# ─────────────────────── ② 判别力：掏空复用 ⇒ 当场红（AC-05） ───────────────────────


def test_reuse_assertion_is_load_bearing(code_root: Path) -> None:
    """★ 把判定器里三处 `Ch7 §D` 调用**掏空** ⇒ 复用断言必须红（证明它不是恒真）。

    ★ 若不掏空而只是"把 `is_research_complete` 换成 `return True`"，绑定仍会红 ——
      但那种改法要整块替换函数体、锚点更脆；改成**逐个摘掉调用名**等价且更稳：
      `research_complete(inp)` / `has_explainable_forecast(inp)` / `require_derived_worksheet(...)`
      三处调用消失 ⇒ `gate_calls_in_judge` 由 3 → 0。
    """
    path = code_root / GATE

    code, out = run_gate_inproc(GATE, code_root)
    assert code == 0, f"未注入时应 exit 0，实得 {code}\n{out}"

    _inject(path, old="research_complete(inp)", new="False")
    _inject(path, old="has_explainable_forecast(inp)", new="False")
    _inject(path, old="require_derived_worksheet(inp.stock_forecast)", new="None")

    code, out = run_gate_inproc(GATE, code_root)
    assert code == 1, f"掏空 Ch7 §D 调用后应 exit 1（复用断言有判别力），实得 {code}\n{out}"
    assert "scanned gate_calls_in_judge: 0" in out, f"应如实报 0 次门调用\n{out}"
    assert "未调用" in out, f"应说清『未复用 gate』这一后果\n{out}"


# ─────────────────────── ③ 反 KPI（`S-01`）单元断言 ───────────────────────


def test_assert_not_fake_complete_rejects_each_fake_signal() -> None:
    """三假完成信号**逐条**必须被拒；**合法**信号（可核的完成证据）不得误伤（`G-05`）。"""
    from scripts.verify.research_complete_gate import (
        FAKE_COMPLETION_SIGNALS,
        FakeCompletionError,
        assert_not_fake_complete,
    )

    for token in sorted(FAKE_COMPLETION_SIGNALS):
        with pytest.raises(FakeCompletionError):
            assert_not_fake_complete({token: True})

    # ★ 反向对照（防误伤）：非三假的"可核完成证据"不得被拒。
    assert_not_fake_complete({"six_results_complete": True, "traceback_coverage": 1.0})


# ─────────────────────── ④ 边界：缺 `derived` ⇒ 不假绿（`AC-06`） ───────────────────────


def _completion_mapping(worksheet: object, depth: str = "baseline_done") -> dict:
    forecast = {
        "drivers": ["d1"],
        "horizon": "1Q",
        "return_range": {"low": "1", "high": "2"},
        "worksheet": worksheet,
        "method_version": "v1",
    }
    return {
        "company_id": "co_1",
        "baseline": {"company_id": "co_1", "research_depth": depth, "baseline_complete": True},
        "stock_forecast": dict(forecast),
        "benchmark_forecast": dict(forecast),
    }


def test_is_research_complete_gate_behavior() -> None:
    """判定器**只**走 `Ch7 §D` 门：缺底稿 ⇒ `False`；合规 ⇒ `True`；研究未完成 ⇒ `False`。

    ★ 「缺 `derived` ⇒ `False`」即 `AC-06` 的"不假绿"：缺底稿 ≠ 完成。
    ★ 正向（`True`）这一半必须有 —— 否则"恒 `False`"的退化实现也能让反向用例全绿。
    """
    from schema.models import DerivedValue

    from scripts.decision.gate import RecommendationInput
    from scripts.verify.research_complete_gate import is_research_complete

    derived = DerivedValue(
        derived_id="dv-1",
        value=Decimal("1"),
        formula="rev*margin",
        operands=["rev", "margin"],
        method_version="v1",
        computed_at=datetime(2026, 9, 16),
    )
    # ① 缺底稿（裸数字 / None）⇒ 不假绿
    assert is_research_complete(RecommendationInput.from_mapping(_completion_mapping(None))) is False
    # ② 合规（DerivedValue 底稿 + 深度达标）⇒ True
    assert is_research_complete(RecommendationInput.from_mapping(_completion_mapping(derived))) is True
    # ③ 研究深度不足 ⇒ False（复用 gate 的判定，不另立阈值）
    assert (
        is_research_complete(
            RecommendationInput.from_mapping(_completion_mapping(derived, depth="position_listed"))
        )
        is False
    )


# ─────────────────────── ⑤ 输入异常 ⇒ exit 2 ───────────────────────


def test_missing_code_root_is_input_error() -> None:
    """`code_root` 不存在 → 必须返回 `2`（**不得折叠成 0 = 静默通过**）。"""
    code, out = run_gate_inproc(GATE, Path("/nonexistent/code_root_for_rcg"))
    assert code == 2, f"对不存在的 code_root 应返回 2（输入异常），实得 {code}\n{out}"


# ─────────────────────── ⑥ 模块可导入（无全局副作用） ───────────────────────


def test_module_imports_without_global_side_effects() -> None:
    """★ 导入**不得**在模块级拉起 `schema.models`（pydantic ≈1.2s）——它是按需导入的。

    ★ 为什么值得单测：若有人在模块顶层 `from scripts.decision.gate import ...`，
      每次 `import scripts.verify.research_complete_gate` 都要付 pydantic 的建模成本；
      本断言把那笔成本钉成可执行的（`gate` 只在 `is_research_complete` **函数体内**导入）。
    """
    before = {n for n in sys.modules if n == "schema.models" or n.startswith("schema.")}
    import importlib

    importlib.reload(importlib.import_module("scripts.verify.research_complete_gate"))
    after = {n for n in sys.modules if n == "schema.models" or n.startswith("schema.")}
    # ★ 允许"之前已在别处导入过"，故只断言：**本模块的导入**不改变 `schema.*` 集合。
    assert after == before, (
        "导入 research_complete_gate 触发了 schema.* 的导入 —— 说明门被放到模块顶层了"
        f"（多出 {sorted(after - before)}）"
    )
