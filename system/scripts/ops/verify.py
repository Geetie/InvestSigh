#!/usr/bin/env python3
"""`verify.py` —— **一次跑完全部验证，并把真实输出留档**。

```
python system/scripts/ops/verify.py [code_root] [--no-tests] [--quiet]
```

**为什么要有这个脚本**（来自实际痛点）：
每贴一次"完成证据"就要重跑一遍测试与门禁（原来 49s + 若干秒），
既慢又容易拿到**不同时刻**的输出。本脚本把三件事**一次做完并落盘**：

| # | 跑什么 | 落盘内容 |
|---|---|---|
| 1 | `pytest tests -q` | 完整 stdout + 退出码 + 耗时 |
| 2 | `run_all_gates.py`（18 项门禁） | 完整 stdout（含每项退出码汇总） |
| 3 | `stage_gate.py --stage all` | 完整 stdout（五阶段判据） |

产物（都在 `system/reports/`）：
- `verify_<YYYY-MM-DD_HHMMSS>.log` —— 本次完整证据
- `verify_latest.log` —— 同一内容的最新副本（引用证据时固定读它）
- 只保留最近 3 份带时间戳的日志，避免仓库里日志堆积

退出码：`0` 全绿 / `1` 有失败 / `2` 环境异常（**不静默**）。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from datetime import datetime
from typing import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # .../system
KEEP_TIMESTAMPED_LOGS = 3


def _run(cmd: list[str], cwd: Path, timeout: float) -> tuple[int, str, float]:
    t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        code, out = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        code = 124
        partial = exc.stdout or ""
        out = (partial if isinstance(partial, str) else "") + f"\n[TIMEOUT] 超过 {timeout}s 未返回"
    return code, out.rstrip(), time.monotonic() - t0


def _stage_gate_verdict(code: int, out: str) -> tuple[bool, str]:
    """判定 `stage_gate --stage all` 的结果是否符合**设计预期**。

    `--stage all` 在阶段②–⑤ 未开工时**本来就该 exit=1**（纪律 12：阶段未过即阻塞）。
    但**不能因此笼统放过 exit=1** —— 那会把"① 也失败了"一起掩盖掉。
    所以显式要求两件事同时成立：

    ① `prep: PASS`（阶段① 判据真的过了）
    ② 四个后续阶段**逐个**出现 `BLOCKED`（不是静默跳过、不是返回 True 冒充通过）
    """
    if "prep: PASS" not in out:
        return False, "阶段① 未 PASS（`prep: PASS` 缺失）—— 这不是预期的阻塞"
    missing = [s for s in ("nvidia_sample", "core_chain", "daily_run", "expansion") if f"{s}: BLOCKED" not in out]
    if missing:
        return False, f"以下阶段未显式标记 BLOCKED（可能静默跳过）：{missing}"
    if code == 0:
        return False, "后续阶段未开工却 exit=0 —— 疑似把阻塞阶段判成通过"
    return True, "阶段① PASS + 阶段②–⑤ 全部阻塞（纪律 12 预期行为）"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify.py", description="一次跑完全部验证并留档")
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--no-tests", action="store_true", help="跳过 pytest（仅跑门禁与阶段判据）")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--quiet", action="store_true", help="只打印摘要，不打印完整输出")
    args = parser.parse_args(argv)

    code_root = Path(args.code_root).resolve() if args.code_root else ROOT
    if not code_root.exists():
        print(f"[INPUT-ERROR] code_root 不存在: {code_root}", file=sys.stderr)
        return 2

    # (标签, 命令, cwd, 判定函数) —— 判定函数返回 (是否合格, 说明)
    steps: list[tuple[str, list[str], Path, "Callable[[int, str], tuple[bool, str]]"]] = []

    def _exit_zero(code: int, out: str) -> tuple[bool, str]:
        return code == 0, "exit=0" if code == 0 else f"exit={code}"

    if not args.no_tests:
        steps.append((
            "pytest tests",
            [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
            code_root, _exit_zero,
        ))
    steps.append((
        "run_all_gates.py（18 项门禁）",
        [sys.executable, str(code_root / "scripts" / "ops" / "run_all_gates.py"), str(code_root), "--timeout", "30"],
        code_root, _exit_zero,
    ))
    steps.append((
        "stage_gate.py --stage all",
        [sys.executable, str(code_root / "scripts" / "delivery" / "stage_gate.py"), str(code_root), "--stage", "all", "--no-report"],
        code_root, _stage_gate_verdict,
    ))

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    lines: list[str] = [
        f"# 验证留档 · {stamp}",
        f"# code_root = {code_root}",
        f"# python    = {sys.executable}",
        f"# 目的：一次跑完全部验证；后续引用证据直接读本文件，**不必重跑**",
        "",
    ]

    failures = 0
    summary: list[tuple[str, int, float, bool, str]] = []
    for label, cmd, cwd, verdict in steps:
        code, out, elapsed = _run(cmd, cwd, args.timeout)
        ok, why = verdict(code, out)
        summary.append((label, code, elapsed, ok, why))
        lines += [
            f"{'=' * 78}", f"## {label}", f"## 命令: {' '.join(cmd)}",
            f"## 退出码: {code}  用时: {elapsed:.2f}s", f"## 判定: {'合格' if ok else '不合格'} —— {why}",
            f"{'=' * 78}", out, "",
        ]
        if not ok:
            failures += 1
        if not args.quiet:
            print(f"\n{'=' * 78}\n## {label}  → exit={code}  {elapsed:.2f}s\n{'=' * 78}\n{out}")

    out_dir = code_root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"verify_{stamp}.log"
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    shutil.copyfile(log_path, out_dir / "verify_latest.log")

    # 只保留最近 N 份带时间戳的日志，避免仓库里日志堆积
    for old in sorted(out_dir.glob("verify_2*.log"), reverse=True)[KEEP_TIMESTAMPED_LOGS:]:
        old.unlink(missing_ok=True)

    print(f"\n{'=' * 78}\n## 摘要\n{'=' * 78}")
    for label, code, elapsed, ok, why in summary:
        print(f"  {'✓' if ok else '✗'} {label:<34} exit={code:<4} {elapsed:>6.2f}s  {why}")
    print(f"  {'全绿' if failures == 0 else f'有 {failures} 项不合格'}")
    print(f"  证据留档: {log_path.relative_to(code_root)}（最新副本 verify_latest.log）")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
