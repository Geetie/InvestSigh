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
    ("verification_policy_guard.py", "scripts/checks/verification_policy_guard.py", ()),
    ("shell_var_guard.py", "scripts/checks/shell_var_guard.py", ()),
    # ── 批次 6 集成新增：并行工作流交付但当时无生产调用方的守卫（G-20 / G-21）──
    # 由主理人集成时注册（各 WS 按纪律不得自行改本文件）。
    ("graph_integrity_guard.py", "scripts/graph/graph_integrity_guard.py", ()),
    ("locator_check.py", "scripts/validators/locator_check.py", ()),
    # ── 缺口 G9：绑定 ≠ 会拦 —— "每条已绑定判据必须有可执行反例"这项义务的机器绑定 ──
    ("criterion_effectiveness_guard.py", "scripts/checks/criterion_effectiveness_guard.py", ()),
    # ── 批次 12-A：反编造引文溯源（缺口 G-B10-05）──
    # `locator_check.py` 判据 4 只在 `full_text_read=true` 时比 hash；
    # 真实主张全部是 `full_text_read=false`，故这类此前**没有任何**引文↔原文机械校验。
    # 本守卫**只**管辖 `false` 那支（互补而非重复，G-06 唯一真源）。
    ("quote_provenance_guard.py", "scripts/checks/quote_provenance_guard.py", ()),
    # ── 缺口 G-55：**同一语义、两种载体形态、零机器绑定** ──
    # `rules/scenario.yaml::scenario_tags`（YAML 列表）↔ `scenario_guard.py::ScenarioTag`（枚举）
    # 值相同、各自自洽，改一侧另一侧不会红 ⇒ 漂移可无限期存在。
    # ★ 这是**合并的产物**（两条流各自自洽），单流自检不可能发现 —— 故必须有一道**跨载体**的门。
    ("scenario_tag_binding_guard.py", "scripts/checks/scenario_tag_binding_guard.py", ()),
    # ── 批次 13-pre 方向 1：**代码读的 `rules/` 键必须存在** ──
    # 形态：`dict.get()` 读一个规则文件里**不存在**的键 ⇒ 静默返回 `None` ⇒ 被 `or ""` 洗成
    # 合法值 ⇒ "这条规则其实没被读"在任何输出里不可见（`T-18`/`G-50`/`G-55`/`G-57`/`G-58` 同族的第六种）。
    # 两条断言：① 代码**引用**的规则文件必须存在；② 代码**读**的键必须在实有键里。
    # ★ 白名单按 `口径 13` 逐条带 reason/owner/预期何时有消费者/review_by，且输出比值。
    # ── 批次 13-pre 方向 2（`WS-D` / 张力 `T-18`）：**`rules/` 声明的记录列必须有消费者** ──
    # 形态：`rules/` 里声明了语义、`scripts/**` 却零消费者 ⇒ 声明**在机器上零效力**（死列）。
    # 域 = 记录集合 × 列（纯遍历 YAML）；消费者 = `scripts/**` 的**非 docstring 字符串字面量**。
    # ★ 与方向 1 **共用同一守卫脚本**（不写第二份解析器，`G-06`）：故本处与 `pre-commit.sh`
    #   的登记**一次覆盖两个方向**（`G-07`：门禁必须两处同时登记 —— 本守卫已在两处）。
    ("rule_key_alignment_guard.py", "scripts/checks/rule_key_alignment_guard.py", ()),
    # ── 批次 13（`WS-G` / `S-07`）：**复盘标记字段不得进入决策函数** ──
    # `Ch10 §C.1` 逐字：「三个 `eval_result` 新字段（`eval_layer` / `error_axis` / `error_axis_note`）
    # 均为标记枚举/说明，**不进入决策函数**」。此前这条只写在文档里 ⇒ 把它们接进
    # `scripts/decision/**`（例如"按错误方向加权"）**没有任何门禁会响**。
    # 本守卫把 `Ch2 §B.3` Checker-1 的 `is_decision_scope` **排除项**变成可执行断言（函数体级 AST）。
    # ★ 与 `pre-commit.sh` **同时**登记（`G-07`）。
    ("error_axis_guard.py", "scripts/checks/error_axis_guard.py", ()),
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
