"""`step.py` —— 决策层对编排器的**接线接缝**（`Ch9 §3.5` 阶段③/④）。

`rules/pipeline.yaml`（0444 锁定，属设计真相源）声明：

- step 6 `compare_company_vs_benchmark_expected_return`（`Ch5 §5.4 + Ch7 §7.3`，
  产物 `benchmarks, recommendations`）—— 本层承担的正是该步的**决策部分**
  （收益比较 → 前置门 → 5 规则 → 落 `facts/recommendations.jsonl`）。

本模块提供**可插拔处理器工厂** `make_decision_handler(root)`，其签名与
`scripts/orchestrate/pipeline.py::StepHandler`（`(run_date: date, scope: str) -> StepOutcome`）
**逐字一致**，故编排器一行即可接入。

★ **诚实标注**：step 6 的**完整**处理器（含模型侧假设生成 / 基准选取 / 价格抓取）
  属阶段②③，**本批次未实现**；本批次**不改**共享文件 `pipeline.py`。故此处只提供
  接缝与注册函数，真实注册动作由主理人在集成时执行：

```python
from scripts.decision.step import register_into
register_into(pipeline)          # 默认注册到 step 6（公司 vs 基准预期收益比较）
```

★ **不产交易信号时也如实回传**：`StepOutcome.signals_emitted` = 本次**新交易信号**数
  （仅 `buy` / `sell` 计入；`maintain` / `pending` 不产新信号，`Ch7 §D.4`）。
  门拒绝（不出建议）或输入缺失时 `degraded=True` + `produced=[]`，**不伪造**结论。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any


def make_decision_handler(root: str | Path, *, step_no: int = 6) -> Any:
    """构造 step ⑥ 的处理器：跑 `run_decide.run_default(root)`，把产物引用回传编排器。

    - `produced` = 本次落库的 `recommendation_id`（**对象引用**，非文件名）；
    - `signals_emitted` = 新交易信号数（`buy` / `sell`）；
    - `degraded` = 门拒绝 / 输入缺失 / 未出建议 → **显式**标记，不静默。

    返回类型为 `StepHandler`（从 `scripts.orchestrate.pipeline` **惰性导入**，避免
    包级急切依赖与循环导入）。
    """
    root_path = Path(root)

    def handler(_run_date: date, _scope: str) -> Any:
        from scripts.orchestrate.pipeline import StepOutcome

        from .run_decide import run_default

        report = run_default(root_path)
        return StepOutcome(
            produced=list(report.recommendation_ids),
            judgment_change={},
            signals_emitted=int(report.signals_emitted),
            degraded=bool(report.degraded) or not report.recommendation_ids,
        )

    handler.__name__ = f"decision_recommendation_step_{step_no}"
    handler.__doc__ = (
        f"决策层 step {step_no} 处理器（`Ch7 §F` 端到端时序；"
        f"run_date 由行情输入窗口决定，本函数不按 run_date 筛选输入）"
    )
    return handler


def register_into(pipeline: Any, *, step_no: int = 6) -> None:
    """把决策层处理器注册进编排器（一行接线）。

    `pipeline` 须暴露 `root` 属性与 `register_step(no, fn)`（`Ch9 §D.1` 签名）。
    """
    pipeline.register_step(step_no, make_decision_handler(pipeline.root, step_no=step_no))
