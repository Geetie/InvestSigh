#!/usr/bin/env python3
"""`run.py` —— **每日运行薄封装**（`Ch1 §D.1` 编排器 + `Ch8 §D` 调度 / `§E` 降级 / `§F` 幂等）。

```
python system/scripts/daily/run.py [code_root] --date YYYY-MM-DD --scope full
```

★ **不重造状态机**（`G-06` 唯一真源 / 纪律 11）：8 步闭环与断点续跑一律由
  `scripts.orchestrate.pipeline.Pipeline.run_daily` 承载；本模块**只**在其上补三件事：

1. **降级可见 + 保留上次有效结果**（`degrade.mark_degraded`，`Ch8 §E`）；
2. **覆盖可核**（`coverage.check`，阶段④ 硬判据）；
3. **同日重跑幂等自检**（`idempotency.duplicates`，`Ch8 §N8.4-08`）。

★ **反 KPI**（`Ch1 §D.3`）：本模块**如实回传** `changed` / `signals_emitted` / `degraded` /
  `blocked` / `gaps`，**不做**任何乐观改写 —— "每天维护 ≠ 每天必须产生新买卖信号"。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


@dataclass(frozen=True)
class DailyRunReport:
    """一次每日运行的**如实**结果（字段与编排器语义一一对应）。"""

    run_date: str
    scope: str
    blocked: bool
    degraded: bool
    changed: bool
    signals_emitted: int
    gaps: tuple[str, ...] = field(default_factory=tuple)
    coverage_violations: tuple[str, ...] = field(default_factory=tuple)
    coverage_notes: tuple[str, ...] = field(default_factory=tuple)
    degradation_visible: bool = False
    last_valid_result_ref: str | None = None
    degradation_task_id: str | None = None
    duplicate_events: tuple[str, ...] = field(default_factory=tuple)
    duplicate_recommendations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def coverage_ok(self) -> bool:
        """覆盖可核（阶段④ 硬判据 `coverage_verifiable`）是否通过。"""
        return not self.coverage_violations

    @property
    def idempotent(self) -> bool:
        """同日重跑是否无重复事件 / 建议。"""
        return not self.duplicate_events and not self.duplicate_recommendations


def run_daily(root: str | Path, run_date: date, scope: str = "full") -> DailyRunReport:
    """跑一次每日运行并**如实**汇总（复用 `Pipeline.run_daily`）。"""
    from scripts.daily import coverage, degrade, idempotency
    from scripts.orchestrate.pipeline import Pipeline

    pipeline = Pipeline(Path(root))
    result = pipeline.run_daily(run_date, scope)

    mark = degrade.mark_degraded(root, result, run_date=run_date, scope=scope)
    cov = coverage.check(Path(root))
    dup_events = idempotency.duplicates(root, "events", idempotency.event_key_of)
    dup_recs = idempotency.duplicates(root, "recommendations", idempotency.recommendation_key_of)

    return DailyRunReport(
        run_date=result.run_date,
        scope=result.scope,
        blocked=bool(result.blocked),
        degraded=bool(result.degraded),
        changed=bool(result.changed),
        signals_emitted=int(result.signals_emitted),
        gaps=tuple(result.gaps),
        coverage_violations=tuple(v.render() for v in cov.violations),
        coverage_notes=tuple(cov.notes),
        degradation_visible=mark.visible,
        last_valid_result_ref=mark.last_valid_ref,
        degradation_task_id=mark.task_id,
        duplicate_events=tuple(dup_events),
        duplicate_recommendations=tuple(dup_recs),
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="run.py", description="每日运行薄封装（Ch8 §D/§E/§F）")
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--date", default=None, help="运行日 YYYY-MM-DD（默认今天）")
    parser.add_argument("--scope", default="full")
    args = parser.parse_args(argv)
    root = Path(args.code_root) if args.code_root else _ROOT
    run_day = date.fromisoformat(args.date) if args.date else date.today()

    report = run_daily(root, run_day, args.scope)
    print("== daily_run ==")
    print(f"  run_date={report.run_date} scope={report.scope}")
    print(f"  changed={report.changed} signals_emitted={report.signals_emitted}")
    print(f"  degraded={report.degraded} blocked={report.blocked} gaps={len(report.gaps)}")
    print(f"  coverage_ok={report.coverage_ok} violations={len(report.coverage_violations)}")
    print(f"  degradation_visible={report.degradation_visible}")
    print(f"  duplicate_events={len(report.duplicate_events)} "
          f"duplicate_recommendations={len(report.duplicate_recommendations)}")
    for note in report.coverage_notes:
        print(f"  note: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
