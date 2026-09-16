#!/usr/bin/env python3
"""`verify.py` —— **分批验证器**（**禁止一条命令全量验证**）。

> 用户的硬要求：**「以后不许一条命令全量验证。必须分批验证，每批还要设定适合的超时时间。」
> 且「若有超时，说明这批验证有问题，极大概率还是测试本身的问题」。**

```
python system/scripts/ops/verify.py --list                 # 看有哪些批次与超时
python system/scripts/ops/verify.py --batch injection      # 只跑一批（推荐用法）
python system/scripts/ops/verify.py --batch all            # 逐批跑，每批独立超时，超时即停
```

## 为什么必须分批（上一版的真实故障）

旧版把 `pytest tests`（全量） + 19 项门禁 + 阶段判据塞进**一条命令、一个超时**。
后果：任一处卡住 → **整条命令无任何输出**、退出码只有 `137`（SIGTERM），
既看不出卡在哪一批，也拿不到任何证据。

分批之后：**卡住的那一批会自己超时并报出批次名**；其余批次照常跑完。
超时＝**该批有问题**（极大概率是测试本身），不是"跑得慢"。

## 批次设计（每批一个独立子进程 + 独立超时）

| 批次 | 内容 | 超时 |
|---|---|---|
| `unit`       | `tests/unit/`（契约 + 作用域匹配器） | 60s |
| `conflict`   | `tests/conflict/`（P-03/P-05/P-07 schema 断言） | 30s |
| `guards`     | `tests/guards/`（18 守卫 × 退出码契约矩阵） | 60s |
| `injection`  | `tests/injection/`（注入 / 接线 / 审计回归） | 120s |
| `root`       | `tests/test_ch11_invariants.py` | 30s |
| `gates`      | `run_all_gates.py`（19 项门禁） | 60s |
| `stage`      | `stage_gate.py --stage all`（预期：①PASS + ②–⑤BLOCKED） | 30s |

超时值按**实测典型耗时的 8~30 倍**设定 —— 足够宽松（不会因偶发抖动误报），
又紧到能在"真的卡住"时快速暴露。

## 退出码
`0` 该批通过 / `1` 该批不合格（含超时）/ `2` 环境异常（批次名非法等）。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping

ROOT = Path(__file__).resolve().parents[2]          # .../system
KEEP_LOGS = 3

Verdict = Callable[[int, str], tuple[bool, str]]


@dataclass(frozen=True)
class Batch:
    name: str
    label: str
    argv: tuple[str, ...]           # 追加到 [sys.executable] 之后
    timeout: float
    verdict: Verdict
    note: str = ""


def _exit_zero(code: int, out: str) -> tuple[bool, str]:
    if code == 0:
        return True, "exit=0"
    if code == 124:
        return False, "**超时** —— 该批有问题（极大概率是测试本身）"
    return False, f"exit={code}"


def _stage_gate_verdict(code: int, out: str) -> tuple[bool, str]:
    """`stage_gate --stage all` 的**设计预期**：① PASS + ②–⑤ 逐个 BLOCKED + exit=1。

    不能笼统放过 exit=1（那会掩盖"① 也失败了"），也不能要求 exit=0（那是不可能的）。
    故显式要求两件事同时成立。
    """
    if code == 124:
        return False, "**超时** —— 该批有问题（极大概率是测试本身）"
    if "prep: PASS" not in out:
        return False, "阶段① 未 PASS（`prep: PASS` 缺失）—— 不是预期的阻塞"
    missing = [
        s for s in ("nvidia_sample", "core_chain", "daily_run", "expansion")
        if f"{s}: BLOCKED" not in out
    ]
    if missing:
        return False, f"以下阶段未显式标记 BLOCKED（可能静默跳过）：{missing}"
    if code == 0:
        return False, "后续阶段未开工却 exit=0 —— 疑似把阻塞阶段判成通过"
    return True, "阶段① PASS + 阶段②–⑤ 全部阻塞（纪律 12 预期行为）"


def _pytest(*targets: str) -> tuple[str, ...]:
    return ("-m", "pytest", *targets, "-q", "-p", "no:cacheprovider")


BATCHES: Mapping[str, Batch] = {
    "unit": Batch(
        "unit", "tests/unit/（契约 + 作用域匹配器）",
        _pytest("tests/unit"), 60.0, _exit_zero,
    ),
    "conflict": Batch(
        "conflict", "tests/conflict/（P-03/P-05/P-07 schema）",
        _pytest("tests/conflict"), 30.0, _exit_zero,
    ),
    "guards": Batch(
        # ★ 不写"多少项"（批次 7 审计）：本批跑的是 `tests/guards/`，其契约矩阵**自带真源**
        #   （`test_exit_code_contract.py::GUARDS` 并 `assert len(GUARDS) == <它自己的数>`），
        #   与 `run_all_gates.GATES` 的项数是**两个不同的数**。此前我在描述里写过 18 / 19 / 20 / 23
        #   四种值 —— 同一事实四个数字，且"由对改错"过一次（把 20 改成 23，而 23 是另一批的数）。
        #   **根治办法 = 不在描述里重复真源**：数字只留在各自的真源里。
        "guards", "tests/guards/（门禁退出码契约 + 验证规范）",
        _pytest("tests/guards"), 60.0, _exit_zero,
    ),
    "injection": Batch(
        "injection", "tests/injection/（注入 / 接线 / 审计回归）",
        _pytest("tests/injection"), 120.0, _exit_zero,
    ),
    "root": Batch(
        "root", "tests/test_ch11_invariants.py（Ch11 不变量）",
        _pytest("tests/test_ch11_invariants.py"), 30.0, _exit_zero,
    ),
    # ── 并行工作流（ws/compute · ws/graph · ws/claim · ws/decision）交付的批次 ──
    # 由主理人在集成时统一加入（`reports/parallel_workstreams.md §5 I-3`）：
    # 各 WS **不得**自行改本文件（多方同改必冲突），只报"需新增批次"。
    "compute": Batch(
        "compute", "tests/compute/（确定性计算层）",
        _pytest("tests/compute"), 60.0, _exit_zero,
    ),
    "graph": Batch(
        "graph", "tests/graph/（依赖图与 T12 传播）",
        _pytest("tests/graph"), 60.0, _exit_zero,
    ),
    "validators": Batch(
        "validators", "tests/validators/（locator 定位校验器）",
        _pytest("tests/validators"), 30.0, _exit_zero,
    ),
    "claim": Batch(
        "claim", "tests/claim/（主张五态状态机）",
        _pytest("tests/claim"), 30.0, _exit_zero,
    ),
    "decision": Batch(
        "decision", "tests/decision/（决策层 triage / gate / rules）",
        _pytest("tests/decision"), 30.0, _exit_zero,
    ),
    "transmit": Batch(
        # 由主理人在集成时加入（`reports/batch8_parallel_taskbook.md`）：
        # 新测试目录必须同时加批次，否则 `V-06` 会把新目录判成"未覆盖"（`CONVENTIONS.md::V-06`）。
        "transmit", "tests/transmit/（Ch7 传导编排引擎）",
        _pytest("tests/transmit"), 60.0, _exit_zero,
    ),
    "evidence": Batch(
        # 新增测试目录必须同时加批次，否则 `V-06` 会把新目录判成"未覆盖"（`CONVENTIONS.md::V-06`）。
        # 由主理人在集成时加入（`reports/batch9_stage3_4_taskbook.md §3 I-1`）。
        "evidence", "tests/evidence/（Ch6 证据层：去重/独立判定/预算闸门）",
        _pytest("tests/evidence"), 60.0, _exit_zero,
    ),
    "daily": Batch(
        # 新增测试目录必须同时加批次，否则 `V-06` 会把新目录判成"未覆盖"（`CONVENTIONS.md::V-06`）。
        # 由主理人在集成时加入（`reports/batch9_stage3_4_taskbook.md §3 I-1`）。
        "daily", "tests/daily/（阶段④每日运行：覆盖可核/降级/幂等/调度）",
        _pytest("tests/daily"), 60.0, _exit_zero,
    ),
    "gates": Batch(
        # ★ 不写"多少项"（批次 7 审计）：数字的真源在 `run_all_gates.GATES`，
        #   描述里重复它必然漂移（同一事实曾出现 18/19/20/23 四个值）。
        "gates", "run_all_gates.py（全部门禁逐项退出码）",
        ("scripts/ops/run_all_gates.py", "{root}", "--timeout", "30"), 60.0, _exit_zero,
        note="门禁内部已有逐项 30s 硬超时（卡死也算不合格）",
    ),
    "stage": Batch(
        "stage", "stage_gate.py --stage all（①PASS + ②–⑤BLOCKED）",
        ("scripts/delivery/stage_gate.py", "{root}", "--stage", "all", "--no-report"),
        30.0, _stage_gate_verdict,
    ),
}

ORDER = (
    "unit", "conflict", "guards", "injection", "root",
    "compute", "graph", "validators", "claim", "decision", "transmit", "evidence", "daily",
    "gates", "stage",
)


def _child_env() -> dict[str, str]:
    """给验证子进程的**环境**：关闭 Python 层的 FS broker hook。

    ★ 实测根因（本批次的真实故障）：WorkBuddy 的 `sitecustomize.py` shim 会在
      **每一次文件操作**上 brokered 到宿主进程走 IPC —— 触发条件是
      `CODEBUDDY_SAFE_DELETE_SANDBOX=1` 或 `CODEBUDDY_BROKERED_FS_HOOK_ENABLED=1`
      （见 shim 的「触发条件」区段）。Bash 工具的沙箱开关**关不掉它**。

      后果：测试夹具的 `copytree` 每次要复制 130 个文件 ⇒ 每个用例数百次 IPC 往返
      ⇒ 数百个用例累积数万次 ⇒ **在某个点 broker 阻塞，进程卡死且卡点漂移**
      （实测 `tests/unit/test_contracts.py` 卡在第 15/17/19 条不等）。

      实测对照（同一台机器、同一份代码）：

      | broker | 12 次 copytree |
      |---|---|
      | 开 | **卡死**（faulthandler 堆栈落在 `_brokered_shutil_copytree`） |
      | 关 | 每次 **0.026s**，12/12 全过 |

      故**验证子进程一律在沙箱外跑**（用户要求），只影响本进程派生的验证子进程。
    """
    return {
        **os.environ,
        "CODEBUDDY_SAFE_DELETE_SANDBOX": "0",
        "CODEBUDDY_BROKERED_FS_HOOK_ENABLED": "0",
    }


def _run(batch: Batch, root: Path) -> tuple[int, str, float]:
    argv = [sys.executable] + [a.format(root=str(root)) for a in batch.argv]
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=batch.timeout,
            env=_child_env(),
        )
        code, out = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        code = 124
        partial = exc.stdout or ""
        head = partial if isinstance(partial, str) else ""
        out = (
            head
            + f"\n[TIMEOUT] 批次 {batch.name!r} 超过 {batch.timeout:.0f}s 未返回 —— "
            "**该批有问题**（极大概率是测试本身，不是「跑得慢」）。\n"
            "排查建议：只跑该批内的单个文件 / 单条用例，定位卡在哪一个用例。\n"
        )
    return code, out.rstrip(), time.monotonic() - t0


def _prune(out_dir: Path) -> None:
    """每个批次只保留最近 KEEP_LOGS 份带时间戳的日志（避免仓里日志堆积）。"""
    for name in ORDER:
        for old in sorted(out_dir.glob(f"verify_{name}_2*.log"), reverse=True)[KEEP_LOGS:]:
            old.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify.py", description="分批验证器（禁止一条命令全量验证）"
    )
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--batch", default=None, help="批次名或 all")
    parser.add_argument("--list", action="store_true", help="列出批次与超时")
    parser.add_argument("--quiet", action="store_true", help="只打印摘要与失败批次的输出")
    args = parser.parse_args(argv)

    if args.list or args.batch is None:
        print("可用批次（每批独立子进程 + 独立超时）：")
        for name in ORDER:
            b = BATCHES[name]
            print(f"  {name:<10} {b.label:<46} 超时 {b.timeout:>5.0f}s")
            if b.note:
                print(f"             └ {b.note}")
        print("\n用法：--batch <名>（推荐，一次一批） 或 --batch all（逐批跑，超时即停）")
        return 0 if args.list else 2

    code_root = Path(args.code_root).resolve() if args.code_root else ROOT
    if not code_root.exists():
        print(f"[INPUT-ERROR] code_root 不存在: {code_root}", file=sys.stderr)
        return 2

    names = ORDER if args.batch == "all" else (args.batch,)
    unknown = [n for n in names if n not in BATCHES]
    if unknown:
        print(f"[INPUT-ERROR] 未知批次 {unknown}；可用: {list(ORDER)}", file=sys.stderr)
        return 2

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_dir = code_root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for name in names:
        batch = BATCHES[name]
        code, out, elapsed = _run(batch, code_root)
        ok, why = batch.verdict(code, out)

        lines = [
            f"# 分批验证留档 · {stamp} · 批次 {name}",
            f"# code_root = {code_root}",
            f"# python    = {sys.executable}",
            f"# 耗时 {elapsed:.2f}s ｜ 超时上限 {batch.timeout:.0f}s ｜ 退出码 {code}",
            f"# 判定: {'合格' if ok else '不合格'} —— {why}",
            "=" * 78,
            out,
        ]
        log = out_dir / f"verify_{name}_{stamp}.log"
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
        shutil.copyfile(log, out_dir / f"verify_{name}_latest.log")

        mark = "✓" if ok else "✗"
        print(f"{mark} [{name}] {batch.label}  exit={code}  {elapsed:.2f}s/{batch.timeout:.0f}s  {why}")
        if not ok or (not args.quiet):
            print("-" * 78)
            print(out)
            print("-" * 78)

        if not ok:
            failures += 1
            if args.batch == "all":
                print(f"✗ 批次 {name!r} 不合格 —— **停止后续批次**（fail-fast，不让问题批次拖垮整轮）")
                break

    if len(names) == 1:
        print(f"证据留档: reports/verify_{names[0]}_latest.log")
    _prune(out_dir)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
