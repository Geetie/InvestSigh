#!/usr/bin/env python3
"""`traceback_coverage.py` —— **六结果追溯覆盖率**（复用 `Ch1 §E`，不另立第二把尺）。

```
python system/scripts/trace/traceback_coverage.py [code_root]
```

权威蓝图：`10_验收与持续复盘/02_实现方案.md §B.2`（伪代码逐字实现）。承接需求
`N10.1-01`（六结果齐备且每环可追溯）、`N10.1-02`（原基线 + 新结果可 diff）。

★ 复用而非新立（`§B.2` / `G-06`）：

- **四要素覆盖率**（证据 / 假设 / 计算 / 上一版本）的解析**只在** `scripts/trace/traceback.py`
  里实现一次（`Ch1 §E`，主干既有、当前 exit 0）。本模块**薄包装调用它**——
  要么调 `traceback()` 函数，要么调 `traceback_coverage()`，**绝不复制一套四要素解析**。
- 本模块**唯一新增的维度** = **六结果**（`change` / `company_impact` / `transmission` /
  `price_reflection` / `recommendation` / `verification`，`§B.1`）。

★ 判据纪律：

- **覆盖率判据可判定且穷尽**（`R-06`）：六结果齐备 = 「要求的六环集合 ⊆ 有非空引用的环集合」，
  是**对象的集合关系**，不是「检查了哪些关键词」。
- **空样本不得判通过**（`G-03`）：无可核对象时记 `not_evaluated` + 显式 note + 计数，
  **不得**返回「覆盖率 = 1.0 已达成」。

★ 真接线（`AC-03`）：本模块是 `Ch1 §E` 第 8 步 `verify_hook` 的**实现落点**（`Ch10 §A.3`
  「验证归第十章」）；门禁入口 = `check()`（`verify_hook_step8()` 同源别名）。
  消费方 = `stage_gate`（`nvidia_sample` 的 `derivation_reviewable` 判据同源）与每日运行后钩子。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402
from scripts.trace.traceback import (  # noqa: E402
    TraceabilityGap,
    traceback as four_element_traceback,
    traceback_coverage as four_element_coverage,
)

#: 六结果（`§B.1` 逐字，①..⑥）。`SIX_RESULTS` 是**要求的环集合**（穷尽判据的一侧）。
SIX_RESULTS: tuple[str, ...] = (
    "change",              # ① 发生了什么新变化
    "company_impact",      # ② 改变公司的什么
    "transmission",        # ③ 影响怎样传导
    "price_reflection",    # ④ 价格反映多少
    "recommendation",      # ⑤ 当前建议是什么
    "verification",        # ⑥ 后续怎样验证
)

#: 事件研究视图（**视图层**，`Ch10 §A.2`；非真源 stem，不落 `facts/`）。
EVENT_STUDIES_REL = ("views", "event_studies.jsonl")


class TraceIncomplete(RuntimeError):
    """四要素追溯不完整（任一要素 < 1.0）—— **命中即 fail**（`Ch1 §F G1-03`）。"""

    def __init__(self, conclusion_id: str, missing: Sequence[str]) -> None:
        self.conclusion_id = conclusion_id
        self.missing = list(missing)
        super().__init__(
            f"{conclusion_id} 四要素（适用项）缺失: {self.missing}"
            "（Ch1 §F G1-03：覆盖率须 = 1.0）"
        )


class TraceEvaluationGap(RuntimeError):
    """无可核对象 → 覆盖率无定义（`G-03`：不得返回 `True` 冒充通过）。"""


# ─────────────────────────── 视图读取（六结果引用） ───────────────────────────


def _read_view_jsonl(path: Path) -> list[dict[str, Any]]:
    """读视图层 JSONL（非真源 stem）。缺失 → `[]`；坏行 → 响亮失败。"""
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno} 不是合法 JSON: {exc}") from exc
    return out


def load_event_studies(root: str | Path | None = None) -> list[dict[str, Any]]:
    """加载事件研究视图（`views/event_studies.jsonl`）。缺失 → `[]`（`G-03` 边界）。"""
    base = Path(root) if root is not None else _ROOT
    return _read_view_jsonl(base.joinpath(*EVENT_STUDIES_REL))


def load_six_results_ref(
    event_study_id: str,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """取某事件研究的 `six_results_ref`（六环 → 对象/字段引用集合，`§B.1` / `§A.4`）。"""
    for row in load_event_studies(root):
        if row.get("event_study_id") == event_study_id:
            refs = row.get("six_results_ref")
            return dict(refs) if isinstance(refs, Mapping) else {}
    return {}


def missing_six_results(refs: Mapping[str, Any]) -> list[str]:
    """六结果**缺失的环**（可判定且穷尽：要求的环集 − 有非空引用的环集）。"""
    return [name for name in SIX_RESULTS if not refs.get(name)]


def six_results_complete(event_study_id: str, root: str | Path | None = None) -> bool:
    """六结果齐备（`N10.1-01`）：每一环都有 `six_results_ref` 指向的对象。

    找不到 `event_study_id` / 引用集合为空 ⇒ `False`（**不判通过**）。
    """
    return not missing_six_results(load_six_results_ref(event_study_id, root))


# ─────────────────────────── 四要素覆盖率（复用 Ch1 §E） ───────────────────────────


def traceback_coverage_ok(
    conclusion_ids: Sequence[str],
    root: str | Path | None = None,
) -> bool:
    """四要素覆盖率 = 1.0（承 `Ch1 §F G1-03`）。任一 < 1.0 ⇒ `raise TraceIncomplete`。

    - 逐条调 **`Ch1 §E` 的 `traceback()`**（复用，不重解析）；
    - 空样本 ⇒ `raise TraceEvaluationGap`（`G-03`：覆盖率无定义，**不得返回 `True`**）。
    """
    if not conclusion_ids:
        raise TraceEvaluationGap(
            "样本为空：覆盖率无定义（G-03，不得返回 True 冒充通过）"
        )
    base = Path(root) if root is not None else _ROOT
    for cid in conclusion_ids:
        result = four_element_traceback(base, cid)
        missing = result.missing()
        if missing:
            raise TraceIncomplete(cid, missing)
    return True


def four_elements_coverage(
    conclusion_ids: Sequence[str],
    root: str | Path | None = None,
) -> float:
    """四要素覆盖率（**薄包装** `Ch1 §E` 既有 `traceback_coverage`，不重解析）。"""
    base = Path(root) if root is not None else _ROOT
    return four_element_coverage(base, list(conclusion_ids))


# ─────────────────────────── 门禁入口（Ch1 §E 第 8 步落点） ───────────────────────────


def check(root: Path) -> CheckReport:
    """六结果齐备（本模块新增维度）+ 四要素覆盖率（复用 Ch1 §E）——`Ch1 §E` 第 8 步落点。"""
    report = CheckReport(checker="traceback_coverage")

    studies = load_event_studies(root)
    report.scanned["event_studies"] = len(studies)
    if not studies:
        report.notes.append(
            "NOT_EVALUATED：无可核事件研究视图（views/event_studies.jsonl 为空，G-03）——"
            "不得判「六结果齐备已达成」"
        )
    else:
        for study in studies:
            study_id = str(study.get("event_study_id") or "<unnamed>")
            refs = study.get("six_results_ref")
            refs_map = dict(refs) if isinstance(refs, Mapping) else {}
            missing = missing_six_results(refs_map)
            if missing:
                report.violations.append(
                    Violation(
                        "N10.1-01",
                        f"{study_id} 六结果缺环: {missing}（要求 {list(SIX_RESULTS)}）",
                        "views/event_studies.jsonl",
                    )
                )

    # 四要素维度：薄包装 Ch1 §E 的既有检查器（不重解析；违例在其自身检查器逐条给出）
    from scripts.trace.traceback import check as _four_element_check

    four_report = _four_element_check(root)
    report.scanned["four_element_violations"] = len(four_report.violations)
    report.notes.append(
        "四要素覆盖率复用 Ch1 §E `traceback`（违反 "
        f"{len(four_report.violations)} 条，逐条见该检查器）"
    )
    return report


def verify_hook_step8(root: Path) -> CheckReport:
    """`Ch1 §E` 第 8 步 `verify_hook` 的**落点**（`Ch10 §A.3`）：六结果 + 追溯覆盖。"""
    return check(root)


def run(root: Path) -> CheckReport:
    """调用入口（与 CLI 同源；供调用方直接内嵌）。"""
    return check(root)


def main(argv: list[str] | None = None) -> int:
    return run_checker("traceback_coverage.py", check, argv)


if __name__ == "__main__":
    sys.exit(main())
