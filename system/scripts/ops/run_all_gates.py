#!/usr/bin/env python3
"""统一门禁跑测（`00_开发Agent开工提示词 §八 N-3` / `§十三 第 10 问`）。

真跑全部检查器与守卫，**逐个记录真实退出码与耗时**，任何一个非 0 都不得被吞掉。

```
python system/scripts/ops/run_all_gates.py [code_root] [--timing ci] [--timeout 30]
```

退出码：`0` 全部放行 / `1` 至少一个检查器阻断或超时 / `2` 环境异常。

★ 为什么不用 shell：上一版 `run_all_gates.sh` 在某个检查器**卡死**时整条
  流水线被 SIGTERM 掐掉（exit 137），**卡死与"跑得慢"无法区分**。本脚本给
  每个检查器加硬超时，超时即记为 `TIMEOUT` 并计入失败——**卡死也算不合格**。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (显示名, 模块相对路径, 额外参数)
GATES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("conflict_scan.py", "scripts/checks/conflict_scan.py", ("--timing", "{timing}")),
    ("append_only_guard.py", "scripts/checks/append_only_guard.py", ()),
    ("rules_lock_guard.py", "scripts/checks/rules_lock_guard.py", ()),
    ("registry_schema_guard.py", "scripts/checks/registry_schema_guard.py", ()),
    ("schema_sync_guard.py", "scripts/checks/schema_sync_guard.py", ()),
    ("assert_gate_input.py", "scripts/checks/assert_gate_input.py", ()),
    ("freeze_guard.py", "scripts/checks/freeze_guard.py", ()),
    ("launch_guard.py", "scripts/checks/launch_guard.py", ()),
    ("module_denylist.py", "scripts/checks/module_denylist.py", ()),
    ("no_signal_day.py", "scripts/checks/no_signal_day.py", ()),
    ("no_placeholder_guard.py", "scripts/checks/no_placeholder_guard.py", ("--fail-on", "warn")),
    ("neutrality_check.py", "scripts/views/neutrality_check.py", ()),
    ("return_guard.py", "scripts/benchmark/return_guard.py", ()),
    ("anti_padding.py", "scripts/scope/anti_padding.py", ()),
    ("gap_to_task.py", "scripts/tasks/gap_to_task.py", ()),
    ("traceback.py", "scripts/trace/traceback.py", ()),
    ("pipeline.py", "scripts/orchestrate/pipeline.py", ()),
    ("stage_gate.py --stage prep", "scripts/delivery/stage_gate.py", ("--stage", "prep")),
    ("injection_guard.py", "scripts/checks/injection_guard.py", ()),
)

TIMEOUT_MARK = "TIMEOUT"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_all_gates.py")
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--timing", default="ci")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("-v", "--verbose", action="store_true", help="透传子进程完整输出")
    args = parser.parse_args(argv)

    code_root = Path(args.code_root).resolve() if args.code_root else ROOT
    if not code_root.exists():
        print(f"[INPUT-ERROR] code_root 不存在: {code_root}", file=sys.stderr)
        return 2

    results: list[tuple[str, object, float]] = []
    failed = 0

    for name, relscript, extra in GATES:
        script = code_root / relscript
        if not script.exists():
            print(f"\n\033[1m── {name} ──\033[0m")
            print(f"  [INPUT-ERROR] 脚本不存在: {script}")
            results.append((name, "MISSING", 0.0))
            failed += 1
            continue

        cmd = [sys.executable, str(script), str(code_root), "--no-report"]
        cmd += [a.format(timing=args.timing) for a in extra]

        print(f"\n\033[1m── {name} ──\033[0m")
        t0 = time.monotonic()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
            code: object = proc.returncode
            out = (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired as exc:
            code = TIMEOUT_MARK
            out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            out = out + f"\n  [TIMEOUT] 超过 {args.timeout}s 未返回 —— 卡死视为不合格"
        elapsed = time.monotonic() - t0

        if args.verbose or code != 0:
            print(out.rstrip() if out.strip() else "  (无输出)")
        print(f"  → exit={code}  用时={elapsed:.2f}s")

        results.append((name, code, elapsed))
        if code != 0:
            failed += 1

    print("\n\033[1m════════ 退出码汇总 ════════\033[0m")
    for name, code, elapsed in results:
        print(f"  {name:<34} exit={code!s:<8} {elapsed:.2f}s")
    print(f"  {'非零计数':<34} {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
