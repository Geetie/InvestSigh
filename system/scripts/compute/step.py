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

    - `produced` = **本次真正新增落库**的 `DerivedValue.derived_id`（对象引用，非文件名）。
      ★ 不是"本次重算的全部 id"：幂等重跑（`values_written=0`）时 `produced` **必须为空**，
      否则 `pipeline.py` 的 G1-05 空执行守卫（`elif not step.produced and not step.skipped`）
      会被击穿——一个什么都没落库的运行会被当成"这一步真干了活"。
      ★ 本步的这条语义是**全字段的锚**：`pipeline.StepOutcome.produced` 的对外契约由它钉死
      （`tests/compute/test_step_wiring.py:48`），其余各步**不得**另立一套 `produced` 语义
      （否则 G1-05 在步与步之间不可比）；幂等命中改走 `StepOutcome.skipped`。
    - `skipped` = 本次**考察过、但同键已在 `derived/` 中故未重复写入**的 `derived_id`
      （幂等命中，`Ch9 §3.5` 阶段④）——取自 `DriverReport.skipped_derived_ids`。
      ★ 为什么必须有它（缺陷 `G-44`，实测）：本处理器被 `chain_steps` 的
        `_declare_incomplete_when_empty` **恰好**包装（step 5 / step 6 两步、`blocking: true`），
        其判据是 `not produced and not skipped and incomplete_reason is None`。
        原先本处理器**不设** `skipped` ⇒ **连续第二次 `run_daily`**
        （`produced=[]`、`skipped=[]`）被适配器补上 `incomplete_reason`
        ⇒ 记 `STATUS_GAP` ⇒ **整轮 `blocked`** —— 而这一轮其实**什么都没坏**：
        `derived/derived_values.jsonl` 一行未增，是**幂等按设计命中**。
        `4f95c3d` 的 docstring 已逐字承诺要防这件事（"读了 N 个对象、判定均无需追加**不是**空执行"），
        但**机器上不生效**——因为承诺的字段从没有人填。本条修复就是"把承诺接上"。
    - `degraded` = 是否存在缺口对象（缺口是正常态，但**显式**标记，不静默）；
    - `signals_emitted` 恒为 `0`（计算不产交易信号，信号由 step 6 的建议产生）。

    ★ **幂等判定不在本模块**（`G-06` 唯一真源）：本处理器只**转述**
      `driver.run_derived` 从唯一写入口（`store.append_derived_value_ids_detailed`）
      取回的 `written` / `skipped` 两个互斥集合，**不重算**任何"哪些算已存在"。

    返回类型为 `StepHandler`（从 `scripts.orchestrate.pipeline` **惰性导入**，避免
    包级急切依赖与循环导入）。
    """
    root_path = Path(root)

    def handler(run_date: date, scope: str) -> Any:
        from scripts.orchestrate.pipeline import StepOutcome

        from .driver import run_derived

        report = run_derived(root_path)
        return StepOutcome(
            produced=list(report.written_derived_ids),
            skipped=list(report.skipped_derived_ids),
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
