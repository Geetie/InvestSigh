"""`step.py` —— 计算层对编排器的**接线接缝**（`Ch9 §3.5` 阶段④/⑤/⑥）。

`rules/pipeline.yaml`（0444 锁定，属设计真相源）声明：

- step 4 `revise_growth_and_moat_judgment`（`Ch4 §4.1~4.3`，产物 `baselines`）；
- step 5 `update_financial_and_valuation_assumptions`（`Ch4 §4.4 + Ch5 §5.3`，产物 `baselines, expectations`）；
- step 6 `compare_company_vs_benchmark_expected_return`（`Ch5 §5.4 + Ch7 §7.3`，产物 `benchmarks, recommendations`）。

这些步的"**算术部分**"由本层承担（`Ch9 §2.4.3`：模型不做算术）。本模块提供**可插拔处理器工厂**
`make_derived_handler(root)`，其签名与 `scripts/orchestrate/pipeline.py::StepHandler`
（`(run_date: date, scope: str) -> StepOutcome`）**逐字一致**，故编排器一行即可接入。

★ **诚实标注**：step 4/5/6 的**完整**处理器（含模型侧假设生成）属阶段②③（张力 `T-08`），
  **本批次未实现**；本批次**不改**共享文件 `pipeline.py`。故此处只提供接缝与注册函数，
  真实注册动作待主理人集成时执行：

```python
from scripts.compute.step import register_into
register_into(pipeline)          # 默认注册到 step 5（估值假设）
```
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any


def make_derived_handler(root: str | Path, *, step_no: int = 5) -> Any:
    """构造 step ⑤/⑥ 的处理器：跑 `driver.run_derived(root)`，把产物引用回传编排器。

    - `produced` = 本次落库的 `DerivedValue.derived_id`（**对象引用**，非文件名）；
    - `degraded` = 是否存在缺口对象（缺口是正常态，但**显式**标记，不静默）；
    - `signals_emitted` 恒为 `0`（计算不产交易信号，信号由 step 6 的建议产生）。

    返回类型为 `StepHandler`（从 `scripts.orchestrate.pipeline` **惰性导入**，避免
    包级急切依赖与循环导入）。
    """
    root_path = Path(root)

    def handler(run_date: date, scope: str) -> Any:
        from scripts.orchestrate.pipeline import StepOutcome

        from .driver import run_derived

        report = run_derived(root_path)
        return StepOutcome(
            produced=list(report.derived_ids),
            degraded=bool(report.gap_ids),
            signals_emitted=0,
        )

    handler.__name__ = f"compute_derived_step_{step_no}"
    handler.__doc__ = f"计算层 step {step_no} 处理器（`Ch9 §3.5` 阶段④；run_date={date.min} 语义不筛选输入）"
    return handler


def register_into(pipeline: Any, *, step_no: int = 5) -> None:
    """把计算层处理器注册进编排器（一行接线）。

    `pipeline` 须暴露 `root` 属性与 `register_step(no, fn)`（`Ch9 §D.1` 签名）。
    """
    pipeline.register_step(step_no, make_derived_handler(pipeline.root, step_no=step_no))
