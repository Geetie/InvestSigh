"""`step.py` —— 决策层对编排器的**接线接缝**（`Ch9 §3.5` 阶段③/④）。

`rules/pipeline.yaml`（0444 锁定，属设计真相源）声明：

- step 6 `compare_company_vs_benchmark_expected_return`（`Ch5 §5.4 + Ch7 §7.3`，
  产物 `benchmarks, recommendations`）—— 本层承担的正是该步的**决策部分**
  （收益比较 → 前置门 → 5 规则 → 落 `facts/recommendations.jsonl`）。

本模块提供**可插拔处理器工厂** `make_decision_handler(root)`，其签名与
`scripts/orchestrate/pipeline.py::StepHandler`（`(run_date: date, scope: str) -> StepOutcome`）
**逐字一致**，故编排器一行即可接入。

★ **`run_date` / `scope` 语义（`P7-3` 根因修复）** —— 二者**均被真实使用**：

- `run_date` = **as-of 上界**：只取行情真源中 `day ≤ run_date` 的点（`Ch9 §3.4.1` 双时间轴），
  故 `run_date` 落在数据窗口内不同位置 → **不同**的输入窗口 → 可能产出**不同**的建议；
  输入窗口**完全**由真源行情与 `run_date` 共同决定，**不**用任何仓库内夹具窗口冒充。
- `scope` = **目标证券选取**：命中真源证券时优先于默认选取。

★ **诚实标注**：step 6 的**完整**处理器（含模型侧假设生成 / 基准选取 / 价格抓取）
  属阶段②③，**本批次未实现**；本批次**不改**共享文件 `pipeline.py`。故此处只提供
  接缝与注册函数，真实注册动作由主理人在集成时执行：

```python
from scripts.decision.step import register_into
register_into(pipeline)          # 默认注册到 step 6（公司 vs 基准预期收益比较）
```

★ **不产交易信号时也如实回传**：`StepOutcome.signals_emitted` = 本次**新交易信号**数
  （仅 `buy` / `sell` 计入；`maintain` / `pending` 不产新信号，`Ch7 §D.4`）。
  门拒绝（不出建议）、**真源输入缺失**或**幂等命中**时 `degraded=True` + `produced=[]`，
  **不伪造**结论（`§一 底线 3`）。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any


def make_decision_handler(root: str | Path, *, step_no: int = 6) -> Any:
    """构造 step ⑥ 的处理器：跑 `run_decide.run_default(root, run_date=..., scope=...)`。

    - `produced` = 本次**真正新增落库**的 `recommendation_id`（**对象引用**，非文件名）。
      ★ 不是"本会产出的 id"：**幂等命中**（同窗口 + 同规则版本重跑）时为空 ——
      命中对象改走 `StepOutcome.skipped`（`pipeline.py` 的 G1-05 空执行守卫现为
      `not step.produced and not step.skipped`，双空才判违例）。
    - `skipped` = 本次**考察过、但幂等键已存在故未重复写入**的 `recommendation_id`
      （`Ch9 §3.5` 阶段⑤）——取自 `RunReport.skipped_recommendation_ids`。
      ★ 为什么必须有它（缺陷 `G-44`，实测）：本处理器被 `chain_steps` 的
        `_declare_incomplete_when_empty` **恰好**包装（step 5 / step 6 两步、`blocking: true`），
        其判据是 `not produced and not skipped and incomplete_reason is None`。
        原先本处理器**不设** `skipped` ⇒ **连续第二次 `run_daily`** 被补上 `incomplete_reason`
        ⇒ 记 `STATUS_GAP` ⇒ **整轮 `blocked`** —— 而这一轮其实**什么都没坏**：
        `facts/recommendations.jsonl` 一行未增，是**幂等按设计命中**。
    - `signals_emitted` = 新交易信号数（`buy` / `sell`）；
    - `degraded` = 门拒绝 / **真源输入缺失** / 未出建议 → **显式**标记，不静默。

    ★ **幂等判定不在本模块**（`G-06` 唯一真源）：本处理器只**转述**
      `run_decide.run_default` 从唯一写入口（`rules.persist_recommendation_detailed`）
      取回的 `written_ids` / `skipped_ids` 两个互斥集合，**不重算**任何"哪些算已存在"。

    ★ `run_date` 作为 **as-of 上界**、`scope` 作为**目标证券选取**，二者均经 `run_default`
      真实使用（见模块 docstring）；输入窗口来自**真源行情**（`<root>/facts/prices.jsonl`），
      **不**来自任何仓库内夹具。

    返回类型为 `StepHandler`（从 `scripts.orchestrate.pipeline` **惰性导入**，避免
    包级急切依赖与循环导入）。
    """
    root_path = Path(root)

    def handler(run_date: date, scope: str) -> Any:
        from scripts.orchestrate.pipeline import StepOutcome

        from .run_decide import run_default

        report = run_default(root_path, run_date=run_date, scope=scope)
        return StepOutcome(
            produced=list(report.recommendation_ids),
            skipped=list(report.skipped_recommendation_ids),
            # ★★ 2026-09-17 修复（缺陷 `G-RC-04` 的另一半）：**原为硬编码 `{}`**。
            #   后果：`check_record.judgment_change` 恒为空 ⇒ `no_signal_day` 的
            #   `G1-02①`（逐字："**无变化日**产了新信号"）对**合法买入日**同样判红（**假红**），
            #   同时对**违法**的无变化产信号日也写着 `False` ⇒ 判据在真数据上**无区分力**。
            #   ⇒ 改为**转述**决策层实际使用的那一组布尔（`RunReport.judgment_change`，
            #     其唯一真源 = `gate.JudgmentChange.as_mapping()`）。本层**不**重算、**不**硬编码。
            judgment_change=dict(report.judgment_change),
            signals_emitted=int(report.signals_emitted),
            degraded=bool(report.degraded) or not report.recommendation_ids,
        )

    handler.__name__ = f"decision_recommendation_step_{step_no}"
    handler.__doc__ = (
        f"决策层 step {step_no} 处理器（`Ch7 §F` 端到端时序）。"
        f"输入窗口由**真源行情**（`<root>/facts/prices.jsonl`）与 `run_date`（as-of 上界）共同决定，"
        f"`scope` 用于选取目标证券；真源缺输入 → 无产出 + 如实降级（不伪造）。"
    )
    return handler


def register_into(pipeline: Any, *, step_no: int = 6) -> None:
    """把决策层处理器注册进编排器（一行接线）。

    `pipeline` 须暴露 `root` 属性与 `register_step(no, fn)`（`Ch9 §D.1` 签名）。
    """
    pipeline.register_step(step_no, make_decision_handler(pipeline.root, step_no=step_no))
