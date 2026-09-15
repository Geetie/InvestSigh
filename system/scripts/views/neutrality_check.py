#!/usr/bin/env python3
"""`neutrality_check.py` —— **展示层中立守卫**（`Ch2 §B.2 P-10` / `§B.3` Checker-5 / `Ch3 §D.1`）。

```
python system/scripts/views/neutrality_check.py [code_root]
```

覆盖：
- **P-10**（`Ch2 §B.2`）展示层不得有"买入置顶 / 紧迫色 / 隐藏反证"等隐性引导
- **N3.2-05 / N2.3-01**（`Ch3 §D.1`）未完成研究**禁止**渲染为"中性评级"或"无投资机会"

**待判断 ≠ 未完成研究**：前者 = 已研究但不足以定论；后者 = 尚未研究。

★ 命中即 fail，禁 warn-only（纪律 2）。
★ 与 `Ch2 §B.3` Checker-5 共用同一实现（`00_交付施工图 §2 阶段①`：「与 Ch3 §D.1 共用」）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import (  # noqa: E402
    CheckReport,
    Violation,
    rel,
    run_checker,
    walk_files,
)

# 隐性引导的渲染标签（禁词域 = 展示层标签，与 P-09 决策词无关）
NEUTRAL_LOOKING_LABELS = ("中性", "neutral", "no_opportunity", "无投资机会", "无机会")
UNRESEARCHED_DEPTHS = ("position_listed",)


def check_view_config(view_config: Mapping[str, Any]) -> list[Violation]:
    """`Ch2 §B.3` Checker-5 的四条断言（逐条对应）。"""
    v: list[Violation] = []

    # ① 默认排序不得以 buy 置顶（排序须走 priority_order 字典序，不得按买卖倾向）
    default_sort = view_config.get("default_sort") or []
    if isinstance(default_sort, Sequence) and default_sort:
        first = default_sort[0]
        field = first.get("field") if isinstance(first, Mapping) else None
        if field in ("action", "recommendation", "signal"):
            v.append(Violation("P-10", f"默认排序按买入倾斜: default_sort[0].field={field!r}"))

    # ② 不得用紧迫色 / 涨跌色暗示
    if view_config.get("urgency_color"):
        v.append(Violation("P-10", "使用紧迫色隐性引导 (urgency_color)"))
    if view_config.get("red_green_bias"):
        v.append(Violation("P-10", "使用涨跌色隐性引导 (red_green_bias)"))

    # ③ 反证与缺口必须与支持证据同等可见（不得默认折叠）
    panel = view_config.get("evidence_panel") or {}
    if isinstance(panel, Mapping) and panel.get("collapsed_default"):
        v.append(Violation("P-10", "默认折叠反证/缺口 (evidence_panel.collapsed_default)"))

    # ④ 未完成研究不得渲染为"中性 / 无机会"（承 Ch3 N3.2-05）
    for mapping in view_config.get("render_mappings") or []:
        if not isinstance(mapping, Mapping):
            continue
        src = str(mapping.get("from", ""))
        to = str(mapping.get("to", ""))
        if any(k in src for k in ("未完成研究", "unresearched", "position_listed")) and any(
            k in to for k in NEUTRAL_LOOKING_LABELS
        ):
            v.append(
                Violation(
                    "N3.2-05",
                    f"未研究伪装中性/无机会: {src!r} → {to!r}",
                )
            )
    return v


def check_neutral(ctx: Mapping[str, Any]) -> list[Violation]:
    """`Ch3 §D.1` 的上下文式断言（供展示层渲染前调用）。"""
    v: list[Violation] = []
    depth = str(ctx.get("research_depth", ""))
    label = str(ctx.get("render_label", ""))
    if depth in UNRESEARCHED_DEPTHS and any(k in label for k in NEUTRAL_LOOKING_LABELS):
        v.append(
            Violation(
                "N3.2-05",
                f"research_depth={depth!r} 却渲染为 {label!r}（未研究 ≠ 中性）",
            )
        )
    if ctx.get("rendered_as_neutral_without_research"):
        v.append(Violation("N3.2-05", "无研究却输出中性结论"))
    return v


def check_view_config_file(path: Path, root: Path) -> list[Violation]:
    import yaml

    relpath = rel(path, root)
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    except Exception as exc:
        return [Violation("P-10-parse", f"视图配置解析失败: {exc}", relpath)]
    if not isinstance(data, Mapping):
        return [Violation("P-10", "视图配置顶层必须是 mapping", relpath)]
    return [
        Violation(x.rule, x.reason, relpath, x.line, x.severity)
        for x in check_view_config(data)
    ]


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="neutrality_check")
    configs = walk_files(root, "views", (".yaml", ".yml", ".json"))
    report.scanned["view_configs"] = len(configs)
    if not configs:
        report.notes.append(
            "SKIPPED_NO_VIEW_CONFIG：views/** 三入口展示配置于阶段④ 交付（Ch8 §B）；"
            "本守卫已就绪并可被单测注入验证"
        )
        return report
    for path in configs:
        report.violations.extend(check_view_config_file(path, root))
    return report


if __name__ == "__main__":
    sys.exit(run_checker("neutrality_check.py", check))
