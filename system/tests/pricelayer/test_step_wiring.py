"""价格层对编排器的**接线接缝**单测（`Ch9 §3.5` 阶段④/⑤；`Ch5 §5.3/§5.4`）。

★ 诚实标注：`scripts/orchestrate/chain_steps.py` 是**多方共享文件**（13-A / 13-B 都要接线），
  本卡**不改它**。故这里证明的是**接缝本身成立**：

1. `run_price_guards(root)` 真的调到 §B/§D/§E/§F 的五个确定性入口（**函数体级 AST 绑定**，`G-02`，
   不是全文件字符串匹配 —— 后者一行注释就能骗过）；
2. 处理器返回的 `StepOutcome` 语义正确（`produced` 恒空 = 诊断不产建议；`skipped` = 考察过的对象）；
3. `register_into` 能真的把处理器注册进（真/桩）编排器。
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
from typing import Any

from scripts.pricelayer import step as pricelayer_step

SYSTEM_ROOT = Path(__file__).resolve().parents[2]
STEP_SOURCE = SYSTEM_ROOT / "scripts" / "pricelayer" / "step.py"

#: `run_price_guards` **必须**调到的五个模块名（设计锚点见 `step.py` 的表）。
REQUIRED_MODULES = ("valuation", "order_guard", "history_guard", "daily_explain", "scenario_guard")


def _function_source(func_name: str) -> ast.FunctionDef:
    tree = ast.parse(STEP_SOURCE.read_text(encoding="utf-8"), filename=str(STEP_SOURCE))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return node
    raise AssertionError(f"step.py 中找不到函数 {func_name}")


def _name_ids(node: ast.AST) -> set[str]:
    return {sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name)}


def _attribute_pairs(node: ast.AST) -> set[tuple[str, str]]:
    """收集 `Name.attr` 形态的属性访问对（用于**函数体级**绑定断言，`G-02`）。"""
    return {
        (sub.value.id, sub.attr)
        for sub in ast.walk(node)
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name)
    }


def test_run_price_guards_calls_all_five_guard_modules() -> None:
    """★ `G-02`：函数体级绑定 —— 五个守卫模块必须**真的**出现在 `run_price_guards` 体内。"""
    body = _function_source("run_price_guards")
    names = _name_ids(body) | {sub.attr for sub in ast.walk(body) if isinstance(sub, ast.Attribute)}
    for module in REQUIRED_MODULES:
        assert module in names, f"run_price_guards 体内没有引用 {module!r}（接线不成立）"

    pairs = _attribute_pairs(body)
    for module in ("valuation", "order_guard", "history_guard", "daily_explain"):
        assert (module, "check") in pairs, f"{module}.check 未被引用（守卫没真的被接上）"
    # ★ `scenario_guard.check` 承载**规则↔代码机器绑定**判据 —— 与 `valuation.check` 对称，
    #   必须也在流水线里跑到（不能只在 CLI 上跑）。
    assert ("scenario_guard", "check") in pairs, "规则↔代码绑定判据未在流水线里跑"
    assert ("scenario_guard", "load_scenario_policy") in pairs, "§E.4 策略读取未接上"
    assert ("scenario_guard", "assert_relative_judgment_allowed") in pairs, (
        "§E.4 的阻塞必须真的被调用"
    )


def test_handler_body_calls_run_price_guards() -> None:
    """处理器必须**真的**去跑守卫（不是返回一个漂亮但空的 outcome）。"""
    factory = _function_source("make_price_guard_handler")
    inner = [n for n in ast.walk(factory) if isinstance(n, ast.FunctionDef) and n.name == "handler"]
    assert inner, "make_price_guard_handler 内应有 handler 闭包"
    called = {
        sub.func.id
        for sub in ast.walk(inner[0])
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
    }
    assert "run_price_guards" in called


def test_run_price_guards_is_read_only_and_reports_guards_run(scratch: Path) -> None:
    """`Ch5 §B.5`：本层是**诊断**（不产建议）—— 汇总运行**不写**任何真源。"""
    before = sorted(p.name for p in (scratch / "facts").iterdir())
    report = pricelayer_step.run_price_guards(scratch)
    after = sorted(p.name for p in (scratch / "facts").iterdir())
    assert before == after, "价格层守卫是只读的（不得写 facts/）"
    assert set(report.guards_run) >= set(REQUIRED_MODULES)
    assert report.scenario_status == "pending", "§E.4：默认 pending"
    assert report.scenario_blocking is True, "§E.4 逐字条件 pending ⇒ 阻塞（读规则文件判定）"

    # 有真源数据时：checked_ids 反映"考察过的对象"（供 StepOutcome.skipped）
    (scratch / "facts" / "baselines.jsonl").write_text(
        '{"baseline_id": "baseline-1", "version": 1, "business_mechanism": "x"}\n', encoding="utf-8"
    )
    report2 = pricelayer_step.run_price_guards(scratch)
    assert "baseline-1" in report2.checked_ids


def test_handler_outcome_semantics(scratch: Path) -> None:
    """`StepOutcome` 语义：`produced` 恒空 + `skipped` = 考察对象 + 显式 `incomplete_reason`。"""
    (scratch / "facts" / "baselines.jsonl").write_text(
        '{"baseline_id": "baseline-1", "version": 1, "business_mechanism": "x"}\n', encoding="utf-8"
    )
    handler = pricelayer_step.make_price_guard_handler(scratch, step_no=6)
    outcome = handler(date(2026, 9, 16), "full")
    assert outcome.produced == [], "价格层不写真源（诊断不产建议，Ch5 §B.5 / C45-1）"
    assert outcome.skipped == ["baseline-1"]
    assert outcome.signals_emitted == 0
    assert outcome.incomplete_reason, "模型侧缺口必须显式声明（不得报 ok 却什么都没做）"
    assert "Ch5" in outcome.incomplete_reason


def test_handler_degraded_when_no_subject_present(scratch: Path) -> None:
    """`G-03`：无被检对象 ⇒ `degraded=True`（不得把"没东西可检"当"已验证"）。"""
    handler = pricelayer_step.make_price_guard_handler(scratch)
    outcome = handler(date(2026, 9, 16), "full")
    assert outcome.degraded is True


def test_register_into_uses_pipeline_register_step(scratch: Path) -> None:
    """接缝可用：`register_into` 走编排器的公开注册面（真 `Pipeline` 签名一致）。"""

    class _StubPipeline:
        def __init__(self, root: Path) -> None:
            self.root = root
            self.registered: dict[int, Any] = {}

        def register_step(self, no: int, fn: Any) -> None:
            self.registered[no] = fn

    pipeline = _StubPipeline(scratch)
    pricelayer_step.register_into(pipeline, step_no=6)
    assert 6 in pipeline.registered
    outcome = pipeline.registered[6](date(2026, 9, 16), "full")
    assert outcome.produced == []


def test_cli_runs_guards_and_returns_zero_on_clean_root(scratch: Path, run_script) -> None:
    """CLI：干净根 → exit 0，并打印实际跑了哪些守卫（真实输出可核）。"""
    proc = run_script("scripts/pricelayer/step.py", scratch)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "scenario_method_status: pending" in proc.stdout
    assert "RESULT: PASS" in proc.stdout


def test_run_price_guards_surfaces_rule_binding_violations(
    scratch: Path, real_rules
) -> None:
    """★ 规则↔代码绑定违例必须**在流水线里**被拦到（不只 CLI）—— 与 `valuation.check` 对称。

    注入：真 `rules/valuation-methods.yaml` 的 `unregistered_fallback.method_class` 改名，
    而代码默认值没改 ⇒ `run_price_guards` 必须产出违例。
    """
    import yaml

    real_rules(scratch, "valuation-methods.yaml", "scenario.yaml")
    path = scratch / "rules" / "valuation-methods.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["unregistered_fallback"]["method_class"] = "misc"
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")

    report = pricelayer_step.run_price_guards(scratch)
    assert any("VALUATION-RULE-BINDING" in v for v in report.violations), report.violations
    assert report.passed is False


def test_run_price_guards_clean_on_real_rules_files(scratch: Path, real_rules) -> None:
    """反向对照：真 `rules/` 文件（`valuation-methods` + `scenario`）→ **无规则绑定违例**。"""
    real_rules(scratch, "valuation-methods.yaml", "scenario.yaml", "freeze.yaml")
    report = pricelayer_step.run_price_guards(scratch)
    binding = [v for v in report.violations if "RULE-BINDING" in v]
    assert binding == [], binding
    assert report.scenario_blocking is True
