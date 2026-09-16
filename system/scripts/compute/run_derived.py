#!/usr/bin/env python3
"""`run_derived.py` —— 确定性计算层**真实运行**入口（`Ch9 §3.5` 阶段④）。

```
python system/scripts/compute/run_derived.py [code_root] \
    [--prices-file PATH] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--strict]
```

做什么（**真读真算真落**，非单测）：

1. 真读 `rules/benchmark.yaml`（或 `facts/benchmarks.jsonl`）的**基准对象**；
2. 真读行情（`facts/prices.jsonl` 或 `--prices-file`）与 `registry/corporate-actions.jsonl`；
3. 经 `returns.compute_benchmark_return` → `scripts/benchmark/return_guard.py` 的**口径断言**
   算基准市场价总回报（`Ch3 §D.2`）；
4. 真落 `derived/derived_values.jsonl`（`DerivedValue`）与 `derived/compute_gaps.jsonl`（缺口对象）；
5. 打印结果摘要（JSON）。

退出码：

- `0` 跑通（默认可含缺口对象 —— 缺口是**正常态**，如实入队）；
- `1` **完整性违例**（`derived/` 出现缺 `formula`/`operands`/`method_version` 的行）或 `--strict` 下存在缺口；
- `2` 输入异常（`code_root` 不存在 / 参数非法 / 输入文件缺字段）。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.compute.contract import ComputeError  # noqa: E402
from scripts.compute.driver import run_derived  # noqa: E402


def _parse_day(raw: str | None) -> date | None:
    if not raw:
        return None
    return date.fromisoformat(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_derived.py",
        description="确定性计算层真实运行（基准总回报 + 缺口对象，落 derived/）",
    )
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--prices-file", default=None, help="行情输入文件（默认 facts/prices.jsonl）")
    parser.add_argument("--start", default=None, help="区间起 YYYY-MM-DD（默认用行情首日）")
    parser.add_argument("--end", default=None, help="区间止 YYYY-MM-DD（默认用行情末日）")
    parser.add_argument("--strict", action="store_true", help="存在缺口对象 → exit 1")
    parser.add_argument("--no-persist", action="store_true", help="只算不落盘（供纯校验）")
    args = parser.parse_args(argv)

    root = Path(args.code_root).resolve() if args.code_root else _ROOT
    if not root.exists():
        print(f"[INPUT-ERROR] code_root 不存在: {root}", file=sys.stderr)
        return 2
    try:
        start = _parse_day(args.start)
        end = _parse_day(args.end)
    except ValueError as exc:
        print(f"[INPUT-ERROR] 日期参数非法: {exc}", file=sys.stderr)
        return 2

    try:
        report = run_derived(
            root,
            prices_file=args.prices_file,
            start=start,
            end=end,
            persist=not args.no_persist,
        )
    except (ComputeError, FileNotFoundError, ValueError) as exc:
        print(f"[INPUT-ERROR] run_derived: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("== run_derived.py（确定性计算层）==")
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))

    if report.integrity_violations:
        print("RESULT: FAIL（完整性违例）")
        for violation in report.integrity_violations:
            print(f"  {violation}")
        return 1
    if args.strict and report.gap_ids:
        print(f"RESULT: FAIL（--strict：存在 {len(report.gap_ids)} 个缺口对象）")
        return 1
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
