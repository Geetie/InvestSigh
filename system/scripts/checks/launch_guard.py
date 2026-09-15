#!/usr/bin/env python3
"""`launch_guard.py` —— **付费非首版条件守卫**（`Ch11 §E.2` 红线二 / N11.1-07 / 源稿第 368 行）。

```
python system/scripts/checks/launch_guard.py [code_root]
```

① `registry/launch_criteria.yaml` 的 `required`（首版启动条件）**不含任何付费订阅**；
② D-01 校验：`available_sources` 中 `iFinD` / `pandadata` 必须
   `license_tier=free_quota` 且 `cost == 0`；
③ `optional` 中的付费项必须 `deferred: true`（可后置、不阻塞）。

★ 命中即 fail，禁 warn-only（纪律 2）。
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
