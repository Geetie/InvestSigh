#!/usr/bin/env python3
"""`launch_guard.py` —— **付费非首版条件守卫**（`Ch11 §E.2` 红线二 / N11.1-07 / 源稿第 368 行）。

```
python system/scripts/checks/launch_guard.py [code_root]
```

① `registry/launch_criteria.yaml` 的 `required`（首版启动条件）**不含任何付费订阅**；
② D-01 校验：`available_sources` 中 `iFinD` / `pandadata` 必须
   `license_tier=free_quota` 且 `cost == 0`；
③ `optional` 中的付费项必须 `deferred: true`（可后置、不阻塞）；
④ ★ **新增（2026-09-17）：`available_sources` 的「每一项」都须可判定许可** ——
   不得只校验 D-01 那两项。理由：`tdx` 于 2026-09-17 按 `N6.1-13` 补入白名单后，
   若沿用旧的"只认 `D01_SOURCE_IDS`"写法，它填的 `license_tier` / `cost` **将无人校验**
   —— 即本仓反复出现的「**有声明、无消费者**」（`G-13` / `G-50` / `G-RC-12` 同族）。
   ④ 的三条子判据：**缺 `license_tier`** → 红（无法判定即拒，`R-06` ⑤ allowlist 语义）；
   `license_tier=free_quota` 但 `cost != 0` → 红；`requires_paid_subscription: true` 出现在
   `available_sources` → 红（付费源只能出现在 `optional` 且 `deferred`）。

★ 命中即 fail，禁 warn-only（纪律 2）。
★ 本文件**不是为了拦住内部人**做外部探测：它只做**静态清单校验**，**不探活**
   （"声明 free_quota 但实际不可用"这类事实，静态守卫无法发现 —— 见
   `system/reports/mcp_setup_brief.md` §八-1 与 `platform_defects_ledger`）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402

D01_SOURCE_IDS = ("iFinD", "pandadata")


def assert_no_paid_in_launch(criteria: Mapping[str, Any]) -> list[Violation]:
    """`Ch11 §E.2` 的可执行断言（逐字对应伪代码）。"""
    v: list[Violation] = []

    paid = [
        c
        for c in criteria.get("required") or []
        if isinstance(c, Mapping) and c.get("requires_paid_subscription") is True
    ]
    for c in paid:
        v.append(
            Violation(
                "N11.1-07",
                f"首版启动条件含付费订阅: {c.get('id')}（付费项只能出现在 optional）",
                "registry/launch_criteria.yaml",
            )
        )

    # D-01：免费额度连接器标 cost=0 / license_tier=free_quota
    for s in criteria.get("available_sources") or []:
        if not isinstance(s, Mapping) or s.get("id") not in D01_SOURCE_IDS:
            continue
        if s.get("license_tier") != "free_quota":
            v.append(
                Violation(
                    "D-01",
                    f"{s['id']}: license_tier 应为 free_quota，实为 {s.get('license_tier')!r}",
                    "registry/launch_criteria.yaml",
                )
            )
        if s.get("cost") != 0:
            v.append(
                Violation("D-01", f"{s['id']}: cost 应为 0，实为 {s.get('cost')!r}", "registry/launch_criteria.yaml")
            )

    # ★ ④ 全量校验（不限于 D-01 两项）：每一项都须可判定许可 —— 见模块 docstring ④。
    for s in criteria.get("available_sources") or []:
        if not isinstance(s, Mapping):
            v.append(
                Violation(
                    "N6.1-13",
                    f"available_sources 含非 mapping 项：{s!r} —— 无法判定许可",
                    "registry/launch_criteria.yaml",
                )
            )
            continue
        sid = s.get("id")
        tier = s.get("license_tier")
        if tier is None:
            # ★ 缺字段即拒（allowlist 语义）："没写"不等于"免费"。
            v.append(
                Violation(
                    "N6.1-13",
                    f"{sid}: available_sources 项缺 license_tier —— 无法判定是否属付费源（缺字段即拒）",
                    "registry/launch_criteria.yaml",
                )
            )
            continue
        if tier == "free_quota" and s.get("cost") != 0:
            v.append(
                Violation(
                    "N6.1-13",
                    f"{sid}: license_tier=free_quota 但 cost={s.get('cost')!r} ≠ 0",
                    "registry/launch_criteria.yaml",
                )
            )
        if s.get("requires_paid_subscription") is True:
            v.append(
                Violation(
                    "N11.1-07",
                    f"{sid}: 付费源出现在 available_sources（应只在 optional 且标 deferred）",
                    "registry/launch_criteria.yaml",
                )
            )

    for c in criteria.get("optional") or []:
        if isinstance(c, Mapping) and c.get("requires_paid_subscription") is True and not c.get("deferred"):
            v.append(
                Violation(
                    "N11.1-07",
                    f"optional 付费项 {c.get('id')} 未标 deferred: true（必须可后置、不阻塞首版）",
                    "registry/launch_criteria.yaml",
                )
            )
    return v


def check(root: Path) -> CheckReport:
    import yaml

    report = CheckReport(checker="launch_guard")
    path = root / "registry" / "launch_criteria.yaml"
    if not path.exists():
        raise FileNotFoundError(f"缺少首版启动条件清单: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("registry/launch_criteria.yaml 顶层必须是 mapping")
    report.scanned["required"] = len(data.get("required") or [])
    report.scanned["optional"] = len(data.get("optional") or [])
    report.scanned["available_sources"] = len(data.get("available_sources") or [])
    report.violations += assert_no_paid_in_launch(data)
    return report


if __name__ == "__main__":
    sys.exit(run_checker("launch_guard.py", check))
