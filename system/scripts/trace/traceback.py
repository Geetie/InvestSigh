#!/usr/bin/env python3
"""`traceback.py` —— **四要素结构化反查 + 覆盖率自检**（`Ch1 §E` / G1-03）。

```
python system/scripts/trace/traceback.py [code_root] [--sample N]
```

四要素（`Ch1 §A` / `§E`）：

```python
@dataclass
class TraceabilityResult:
    evidence: list[str]        # claim_id[]
    assumptions: list[str]     # baseline.driver_model / valuation_inputs(three-source)
    computation: DerivedValue  # formula + operands + method_version (承 Ch9 N9.2-02/03)
    prev_version_id: str | None
```

判据：**任一结论/建议都能反查到【证据 / 假设 / 计算 / 上一版本】四要素**
（四要素反查成功率 = **100%**）。

★ G1-03：抽样结论 `traceback_coverage == 1.0`；删掉某结论的 `prev_version_id` →
  覆盖率 < 1.0 → **拦截**。
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402

ELEMENTS = ("evidence", "assumptions", "computation", "prev_version_id")


class TraceabilityGap(RuntimeError):
    """四要素反查失败。"""


@dataclass
class TraceabilityResult:
    conclusion_id: str
    evidence: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    computation: dict[str, Any] | None = None
    prev_version_id: str | None = None
    #: 该建议的版本号（取自真源 `version`）。**缺省 `None` = 未知** → 按**最严**处理（见 `applicable`）。
    version: int | None = None

    def applicable(self) -> tuple[str, ...]:
        """**本结论适用的**要素名（`T-10` 裁决 ①，需求方 2026-09-16）。

        ★ 为什么要有"适用性"这一层：`Ch1 §E` 的四要素要求**任一结论都能反查到**四项。
          但**第一条**建议**结构上不存在**"上一版本"（它就是第一条）。
          原先的判据把"结构上不适用"与"真漏填"**混为一谈** → 覆盖率**永远到不了 1.0**
          → 门禁**恒红**（实测 `rec-nvda-001` 报 `['assumptions','computation','prev_version_id']`）。

        ★ 判据**可判定 + 穷尽**（`R-06`）：
            `prev_version_id` 适用 ⟺ 有前身可指。判定 = **版本号存在且 > 1**，或**已显式给出 `supersedes`**。
            版本号**未知**（`None`）时**按适用处理** —— **不得**靠"不知道版本"来豁免（保守侧）。
        """
        names: list[str] = ["evidence", "assumptions", "computation"]
        has_prev = bool(self.prev_version_id) or (self.version is not None and self.version > 1)
        if has_prev:
            names.append("prev_version_id")
        return tuple(names)

    def missing(self) -> list[str]:
        """返回**适用的**要素里**缺失**的那些（不适用的要素**不计入**，见 `applicable`）。"""
        applicable = set(self.applicable())
        out: list[str] = []
        if "evidence" in applicable and not self.evidence:
            out.append("evidence")
        if "assumptions" in applicable and not self.assumptions:
            out.append("assumptions")
        if "computation" in applicable and not self.computation:
            out.append("computation")
        if "prev_version_id" in applicable and not self.prev_version_id:
            out.append("prev_version_id")
        return out

    @property
    def complete(self) -> bool:
        return not self.missing()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"缺少真源: {path}")
    out: list[dict[str, Any]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = raw.strip()
        if raw:
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno} 非法 JSON: {exc}") from exc
    return out


def traceback(root: Path, conclusion_id: str) -> TraceabilityResult:
    """对一条建议/结论做结构化反查。

    - `evidence`：`recommendations.evidence_version_ids` / `baselines.evidence_claim_ids`
    - `assumptions`：`baselines.driver_model[].assumptions`
    - `computation`：`derived/` 中该结论的 `DerivedValue`（需带 formula + operands + method_version）
    - `prev_version_id`：版本链上一个版本（`supersedes`）
    """
    recs = _load_jsonl(root / "facts" / "recommendations.jsonl")
    baselines = _load_jsonl(root / "facts" / "baselines.jsonl")
    target = next((r for r in recs if r.get("recommendation_id") == conclusion_id), None)
    if target is None:
        raise TraceabilityGap(f"未找到结论/建议: {conclusion_id}")

    evidence = list(target.get("evidence_version_ids") or [])
    company_id = target.get("company_id")
    assumptions: list[str] = []
    for b in baselines:
        if b.get("company_id") == company_id:
            for driver in b.get("driver_model") or []:
                assumptions.extend(driver.get("assumptions") or [])

    computation = _find_derived(root, conclusion_id, evidence)
    return TraceabilityResult(
        conclusion_id=conclusion_id,
        evidence=evidence,
        assumptions=assumptions,
        computation=computation,
        prev_version_id=target.get("supersedes"),
        version=target.get("version"),
    )


def _find_derived(
    root: Path, conclusion_id: str, declared_refs: Sequence[str] = ()
) -> dict[str, Any] | None:
    """在 `derived/` 里找该结论的计算底稿（`DerivedValue`：formula + operands + method_version）。

    ★ **两条解析路径**（`T-10` 裁决 ① 的配套修复 —— 实测缺陷）：

      ① 按 `conclusion_id` 直接匹配 `derived_id` / `conclusion_id`（**原路径**）；
      ② ★ **按该建议声明的计算引用**（`Recommendation.evidence_version_ids` 里的 `dv-…`）解析。

    **为什么 ② 是必需的**：计算层的 id 形如 `dv-<kind>-<subject>-<method_version>`，
    而建议 id 形如 `rec-…` —— **两者永不可能相等**（实测：`_find_derived` 对**任何**建议都返回 `None`）
    ⇒ **"计算"这一要素原本没有任何可达链路**，四要素判据之一形同虚设。

    **② 的依据**：`Recommendation.evidence_version_ids` **既有数据形态**里就放 `dv-…` 引用
    （真实建议与那次伪造建议都是这么写的）→ 采用它**不新增任何字段**（`R-04`）。
    该口径解释已登记为**待需求方确认项**（属"契约解释"而非"新增设计"）。
    """
    wants = [conclusion_id, *[str(r) for r in declared_refs if str(r).startswith("dv-")]]
    ddir = root / "derived"
    if not ddir.exists():
        return None
    for path in sorted(ddir.rglob("*.jsonl")):
        for row in _load_jsonl(path):
            if row.get("conclusion_id") in wants or row.get("derived_id") in wants:
                if row.get("formula") and row.get("operands") is not None and row.get("method_version"):
                    return row
                return None
    return None


def traceback_coverage(root: Path, sample: Sequence[str]) -> float:
    """四要素覆盖率（应 = 1.0，`Ch1 §E` / G1-03）。空样本 → 抛错（不得返回 1.0 冒充通过）。"""
    if not sample:
        raise ValueError("样本为空：覆盖率无定义（不得返回 1.0 冒充通过）")
    ok = 0
    for cid in sample:
        if traceback(root, cid).complete:
            ok += 1
    return ok / len(sample)


def check(root: Path, sample_size: int = 20) -> CheckReport:
    report = CheckReport(checker="traceback")
    recs = _load_jsonl(root / "facts" / "recommendations.jsonl")
    report.scanned["recommendations"] = len(recs)
    if not recs:
        report.notes.append(
            "NO_RECOMMENDATION_DATA：阶段① 真源为空；四要素反查器已就绪，"
            "阶段②/③ 起作用于真数据；本条**不构成**‘覆盖率 = 1.0 已达成’"
        )
        return report

    sample = [r["recommendation_id"] for r in recs[:sample_size] if r.get("recommendation_id")]
    report.scanned["sample"] = len(sample)
    for cid in sample:
        result = traceback(root, cid)
        missing = result.missing()
        if missing:
            report.violations.append(
                Violation(
                    "G1-03",
                    f"{cid} 四要素（**适用项**）缺失: {missing}（适用={list(result.applicable())}，"
                    f"version={result.version}）",
                    "facts/recommendations.jsonl",
                )
            )
    coverage = traceback_coverage(root, sample)
    report.scanned["coverage_x100"] = int(round(coverage * 100))
    if coverage < 1.0:
        report.violations.append(
            Violation(
                "G1-03",
                f"四要素（适用项）反查成功率 {coverage:.4f} < 1.0 —— "
                f"分母 = 各结论**适用的**要素（首版建议的 `prev_version_id` 不适用，不计入；`T-10` 裁决 ①）",
                "facts/recommendations.jsonl",
            )
        )
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="traceback.py")
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--sample", type=int, default=20)
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.code_root) if args.code_root else _ROOT
    return run_checker("traceback.py", lambda r: check(r, args.sample), [str(root)] + (["--no-report"] if args.no_report else []))


if __name__ == "__main__":
    sys.exit(main())
