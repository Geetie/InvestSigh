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

    def missing(self) -> list[str]:
        """返回**缺失**的要素名。"""
        out: list[str] = []
        if not self.evidence:
            out.append("evidence")
        if not self.assumptions:
            out.append("assumptions")
        if not self.computation:
            out.append("computation")
        if not self.prev_version_id:
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

    computation = _find_derived(root, conclusion_id)
    return TraceabilityResult(
        conclusion_id=conclusion_id,
        evidence=evidence,
        assumptions=assumptions,
        computation=computation,
        prev_version_id=target.get("supersedes"),
    )


def _find_derived(root: Path, conclusion_id: str) -> dict[str, Any] | None:
    """在 `derived/` 里找该结论的计算底稿（`DerivedValue`：formula + operands + method_version）。"""
    ddir = root / "derived"
    if not ddir.exists():
        return None
    for path in sorted(ddir.rglob("*.jsonl")):
        for row in _load_jsonl(path):
            if row.get("conclusion_id") == conclusion_id or row.get("derived_id") == conclusion_id:
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
                Violation("G1-03", f"{cid} 四要素缺失: {missing}", "facts/recommendations.jsonl")
            )
    coverage = traceback_coverage(root, sample)
    report.scanned["coverage_x100"] = int(round(coverage * 100))
    if coverage < 1.0:
        report.violations.append(
            Violation("G1-03", f"四要素覆盖率 {coverage:.4f} < 1.0", "facts/recommendations.jsonl")
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
