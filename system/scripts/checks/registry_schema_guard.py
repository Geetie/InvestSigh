#!/usr/bin/env python3
"""`registry_schema_guard.py` —— **登记层真源的结构守卫**（`Ch9 §3.4.9` / `§N9.3-11` / `Ch1 §G`）。

```
python system/scripts/checks/registry_schema_guard.py [code_root]
```

职责：让 `schema/registry_models.py` **真的被使用**，并保证登记层真源**不漂移**。

三条断言：

| # | 断言 | 依据 |
|---|---|---|
| ① | `REGISTRY_MODELS` 声明的每个 JSONL **文件存在**（缺 → 真源缺失） | `Ch9 §3.4.9` |
| ② | 每一行都能**校验**为该 stem 对应的对象模型（`extra="forbid"` 生效） | 同上 |
| ③ | `registry/*.jsonl` **没有未登记的文件**（新增真源必须先登记模型） | `§一 底线 2` 真接线 |

★ 这是 `registry_models.py` 的**唯一读取方**。没有它，那四个模型就是孤儿模块 ——
  而 `registry/prep_deliverables.yaml` 却声称 `QualityLabel` 是"人工核验 ground
  truth"的载体。**声明了载体却没人调用**是 `§一 底线 2` 点名的第 2 类假交付
  （Incomplete Implementation / Wiring Failure / Production-Readiness Cliff 中的
  Wiring Failure，**能通过 100% 覆盖率测试**）。

★ 空真源**不算通过**：报告里必须出现 `scanned` 计数与"空文件"note，
  不得把"文件为空"当成"已验证结构合规"。

★ 命中即 fail，禁 warn-only（纪律 2）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from schema.registry_models import REGISTRY_MODELS, registry_model_for  # noqa: E402
from scripts._common import (  # noqa: E402
    CheckReport,
    Violation,
    run_checker,
)

REGISTRY_DIR = "registry"


def _read_lines(path: Path) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = raw.strip()
        if raw:
            out.append((lineno, raw))
    return out


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="registry_schema_guard")
    total_lines = 0
    empty: list[str] = []

    for stem in sorted(REGISTRY_MODELS):
        rel = f"{stem}.jsonl"
        path = root / rel
        if not path.exists():
            report.violations.append(
                Violation("N9.3-09", f"登记层真源缺失: {rel}（模型已登记，文件不存在）", rel)
            )
            continue

        model = registry_model_for(stem)
        rows = _read_lines(path)
        total_lines += len(rows)
        if not rows:
            empty.append(rel)

        for lineno, raw in rows:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                report.violations.append(
                    Violation("N9.3-09", f"{rel}:{lineno} 不是合法 JSON: {exc}", rel, lineno)
                )
                continue
            try:
                model.model_validate(payload)
            except Exception as exc:                      # pydantic ValidationError
                report.violations.append(
                    Violation(
                        "N9.3-09",
                        f"{rel}:{lineno} 不满足 {model.__name__} 契约: {str(exc).splitlines()[0]}",
                        rel,
                        lineno,
                    )
                )

    # ③ 未登记文件：registry/ 下出现新 JSONL 但没登记模型
    #    ★ 必须比 **basename**：`REGISTRY_MODELS` 的键是**相对 code_root 的路径**
    #      （`registry/corporate-actions`），而 `glob` 出来的是文件名。
    #      用全路径比 basename 会同时产生"假未登记"与"假缺失"两条错报 ——
    #      本守卫第一次真跑就自己报了这一对（响亮失败，没有静默放行）。
    declared = {
        Path(f"{stem}.jsonl").name for stem in REGISTRY_MODELS if stem.startswith(REGISTRY_DIR)
    }
    registry_dir = root / REGISTRY_DIR
    on_disk = {p.name for p in sorted(registry_dir.glob("*.jsonl"))} if registry_dir.exists() else set()
    for name in sorted(on_disk - declared):
        report.violations.append(
            Violation(
                "底线 2 真接线",
                f"registry/{name} 未在 REGISTRY_MODELS 登记（新增真源必须先登记模型，"
                "否则它是没人读的数据）",
                f"{REGISTRY_DIR}/{name}",
            )
        )
    for name in sorted(declared - on_disk):
        report.violations.append(
            Violation("N9.3-09", f"registry/{name} 已登记但文件不存在", f"{REGISTRY_DIR}/{name}")
        )

    report.scanned["declared_models"] = len(REGISTRY_MODELS)
    report.scanned["lines_validated"] = total_lines
    report.scanned["registry_jsonl_on_disk"] = len(on_disk)
    if empty:
        report.notes.append(
            "EMPTY_REGISTRY_SOURCE：以下真源当前为空行 —— **空不等于已验证**，"
            f"只表示本阶段尚无该事件：{', '.join(empty)}"
        )
    report.notes.append(
        "本检查器是 schema/registry_models.py 的唯一读取方（防孤儿模块，§一 底线 2）"
    )
    return report


if __name__ == "__main__":
    sys.exit(run_checker("registry_schema_guard.py", check))
