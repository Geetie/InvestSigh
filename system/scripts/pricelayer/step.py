#!/usr/bin/env python3
"""`step.py` —— 价格层对编排器的**接线接缝**（`Ch9 §3.5` 阶段④/⑤；`Ch5 §5.3/§5.4`）。

## 接缝在哪（**如实说清**，不假装接上）

`rules/pipeline.yaml`（0444 锁定的设计真相源）把两步交给第五章：

- **step 5** `update_financial_and_valuation_assumptions`（`Ch4 §4.4 + Ch5 §5.3`，
  产物 `valuation` / `DerivedValue`）；
- **step 6** `compare_company_vs_benchmark_expected_return`（`Ch5 §5.4 + Ch7 §7.3`，
  产物 `benchmarks` / `recommendations`）。

`scripts/orchestrate/chain_steps.py` 目前给这两步注册的是
`scripts.compute.step` / `scripts.decision.step` 的处理器。**该文件是多方共享文件**
（批次 13 的 13-A / 13-B 都要往 step 4~6 上接线），故本卡**不改它**，
而是提供**两种**接法，任选其一（由主理人集成时决定）：

1. **一行调用（推荐）**：在既有 step 5 / step 6 处理器体内调用
   `run_price_guards(root)` —— 它与既有处理器**不抢注册位**，只加一道**确定性前置门**。
2. **整步注册**：`register_into(pipeline, step_no=5|6)` —— 用本模块的处理器**替换**该步
   （`pipeline.register_step` 是覆盖语义）。★ 这会**顶掉**既有处理器，仅在主理人确认
   "价格层守卫即为该步的首版实现"时使用。

## 本模块**真的**调到哪些确定性部分（生产调用方，`G-02` 函数体级）

| 被调 | 设计锚点 | 用途 |
|---|---|---|
| `valuation.check` | `Ch5 §D.1/§D.2` | 估值追溯链 + 方法注册表 |
| `order_guard.check` | `Ch5 §B.1/§B.5` | 多解不变式 + 反解回灌 baseline |
| `scenario_guard.load_scenario_policy` | `Ch5 §E.4` | `scenario_method_status`（默认 `pending`） |
| `scenario_guard.assert_relative_judgment_allowed` | `Ch5 §E.4` | `pending` ⇒ **阻塞**相对判断生成 |
| `history_guard.check` | `Ch5 §E.1/§E.5` | 非上市资产 / 覆盖率（step 6 的基准侧） |
| `daily_explain.check` | `Ch5 §F.1` | 行情口径（step 6 的收益计算前置） |

★ `produced` **恒为空**：价格层是**诊断**（`Ch5 §B.5` 裁决 `C45-1`："反解 = 诊断（不产建议）"），
  本步**不写**任何真源；`skipped` 记"考察过但无需写入"的对象引用（`pipeline.StepOutcome` 契约），
  故本步在**有数据**时不会被判成"报 ok 但 produced 为空（空执行）"。

## 模型侧缺口（显式声明，不静默）

`Ch5 §5.3/§5.4` 的**假设生成**（候选假设组合 / 假设空间边界 / 替代解释）与
**基准选取与价格抓取**属阶段②③，本批次未交付 —— 经 `incomplete_reason` 报出。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_T08 = "张力 T-08（A 方案：注册 1–6，模型侧缺口显式标 gap）"


@dataclass
class PriceGuardReport:
    """价格层确定性守卫的一次汇总运行结果。"""

    checked_ids: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    guards_run: list[str] = field(default_factory=list)
    scenario_status: str = "pending"
    scenario_value_source: str = "design_default"
    scenario_blocked: bool = False

    @property
    def passed(self) -> bool:
        return not self.violations


def run_price_guards(root: str | Path) -> PriceGuardReport:
    """跑价格层的**确定性守卫**并汇总（**纯读**，不写任何真源）。

    逐项都调**既有公开入口**（`G-06`：本模块不重实现任何判定）：

    - `valuation.check(root)`（`Ch5 §D.1/§D.2`）；
    - `order_guard.check(root)`（`Ch5 §B.1/§B.5`）；
    - `scenario_guard.load_scenario_policy(root)` + `assert_relative_judgment_allowed(...)`
      （`Ch5 §E.4`：`pending` ⇒ 阻塞相对判断）；
    - `history_guard.check(root)`（`Ch5 §E.1/§E.5`）；
    - `daily_explain.check(root)`（`Ch5 §F.1`）。

    `checked_ids` = 本次**考察过**的对象引用（baseline / benchmark / price snapshot / 解集），
    供 `StepOutcome.skipped` 使用（"读了 N 个对象、判定均无需追加"不是空执行）。
    """
    from schema.store import read_records

    if __package__:
        from . import ScenarioMethodPending, daily_explain, history_guard, order_guard, scenario_guard, valuation
    else:  # 直接以脚本方式运行（CLI 出口；仓库既有守卫都是这种调用方式）
        from scripts.pricelayer import (
            ScenarioMethodPending,
            daily_explain,
            history_guard,
            order_guard,
            scenario_guard,
            valuation,
        )

    root_path = Path(root)
    report = PriceGuardReport()
    for name, checker in (
        ("valuation", valuation.check),
        ("order_guard", order_guard.check),
        ("history_guard", history_guard.check),
        ("daily_explain", daily_explain.check),
    ):
        result = checker(root_path)
        report.guards_run.append(name)
        report.violations.extend(v.render() for v in result.violations)
        report.notes.extend(result.notes)

    policy = scenario_guard.load_scenario_policy(root_path)
    report.scenario_status = policy.status
    report.scenario_value_source = policy.value_source
    report.guards_run.append("scenario_guard")
    report.notes.extend(policy.notes)
    try:
        scenario_guard.assert_relative_judgment_allowed(policy)
    except ScenarioMethodPending as exc:
        # `Ch5 §E.4`：pending ⇒ **阻塞**相对判断生成（下游输出"待判断"而非建议）。
        report.scenario_blocked = True
        report.notes.append(f"SCENARIO_METHOD_PENDING: {exc}")

    report.checked_ids = sorted(
        {
            str(row.get(key))
            for stem, key in (
                ("baselines", "baseline_id"),
                ("benchmarks", "benchmark_id"),
                ("prices", "snapshot_id"),
                ("implied_requirements", "implied_id"),
            )
            for row in read_records(root_path, stem)
            if row.get(key)
        }
    )
    return report


def make_price_guard_handler(root: str | Path, *, step_no: int = 6) -> Callable[[date, str], Any]:
    """构造价格层守卫的**步进处理器**（签名 = `orchestrate.pipeline.StepHandler`）。

    - `produced` **恒为空**（本层不写真源；`Ch5 §B.5`：诊断不产建议）；
    - `skipped` = `run_price_guards` 回传的 `checked_ids`（幂等命中语义）；
    - `degraded` = 有违例 **或** 无被检对象（`G-03`：无被检对象不得当"已验证"）；
    - `incomplete_reason` = 模型侧缺口（假设生成 / 基准选取与价格抓取，属阶段②③），
      并附本轮守卫计数 —— **绝不报 ok 却什么都没做**。
    """
    root_path = Path(root)

    def handler(_run_date: date, _scope: str) -> Any:
        from scripts.orchestrate.pipeline import StepOutcome

        report = run_price_guards(root_path)
        degraded = bool(report.violations) or not report.checked_ids or report.scenario_blocked
        detail = (
            f"违例 {len(report.violations)} 条" if report.violations else "无违例"
        )
        return StepOutcome(
            produced=[],
            skipped=list(report.checked_ids),
            degraded=degraded,
            signals_emitted=0,
            incomplete_reason=(
                f"价格层确定性守卫已跑（{', '.join(report.guards_run)}；{detail}；"
                f"scenario_method_status={report.scenario_status}"
                f"{'（阻塞相对判断）' if report.scenario_blocked else ''}）；"
                "`Ch5 §5.3/§5.4` 的**假设生成**（候选假设组合 / 假设空间边界 / 替代解释）"
                "与**基准选取与价格抓取**属模型侧、阶段②③，本批次未交付 ⇒ 本步未完成。"
                f"{_T08}"
            ),
        )

    handler.__name__ = f"price_layer_guard_step_{step_no}"
    handler.__doc__ = f"step {step_no} 价格层守卫（Ch5 §B/§D/§E/§F）—— 只读诊断 + 显式模型侧缺口"
    return handler


def register_into(pipeline: Any, *, step_no: int = 6) -> None:
    """把价格层守卫处理器注册进编排器（**覆盖**该步的既有处理器，慎用；见模块 docstring）。"""
    pipeline.register_step(step_no, make_price_guard_handler(pipeline.root, step_no=step_no))


def main(argv: Sequence[str] | None = None) -> int:
    """CLI：跑一遍价格层守卫并打印汇总；有违例 → `exit 1`，输入异常 → `exit 2`。

    ```
    python system/scripts/pricelayer/step.py <code_root>
    ```
    """
    parser_argv = list(argv) if argv is not None else sys.argv[1:]
    root = Path(parser_argv[0]) if parser_argv else _ROOT
    if not root.exists():
        print(f"[INPUT-ERROR] code_root 不存在: {root}", file=sys.stderr)
        return 2
    try:
        report = run_price_guards(root)
    except (FileNotFoundError, ValueError, KeyError, OSError) as exc:
        print(f"[INPUT-ERROR] pricelayer_step: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print("== pricelayer_step ==")
    print(f"  guards_run: {', '.join(report.guards_run)}")
    print(f"  checked_ids: {len(report.checked_ids)}")
    print(f"  scenario_method_status: {report.scenario_status}（{report.scenario_value_source}）")
    for note in report.notes:
        print(f"  note: {note}")
    for violation in report.violations:
        print(f"  [FATAL] {violation}")
    if report.violations:
        print(f"RESULT: FAIL（{len(report.violations)} violations）")
        return 1
    print("RESULT: PASS（0 violations）")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI 出口
    raise SystemExit(main())
