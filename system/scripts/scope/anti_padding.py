#!/usr/bin/env python3
"""`anti_padding.py` —— **反凑数三件套**（`Ch3 §D.4` / N3.1-01/08/09/10 / C123-8）。

```
python system/scripts/checks/anti_padding.py [code_root]
```

① **系统内不存在目标数量配置**（denylist 扫描）
   —— 禁 `target_company_count` / `expected_list_size` / `companies_to_include`
② **正式名单入选须三字段非空**：`raw_source` + `inclusion_reason` + `evidence_strength`
   —— 无出处 / 无理由 → **拒入正式名单**
③ **名单规模 = 过门槛对象数**：核验后**仅 8 家即收录 8 家**，不补凑、也不为凑数降门槛
   （门槛变更须版本化 + 留痕）。

边界情形（`Ch3 §D.4`）：「重要性高但证据弱」→ **不入选正式名单**，
可进"研究线索 / 待核验"队列（承 Ch6 gap 语义），**不占首批名额**。

★ 命中即 fail，禁 warn-only（纪律 2）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, rel, run_checker, walk_files  # noqa: E402

# `Ch3 §D.4` 的 denylist（逐字）
BANNED_COUNT_KEYS = frozenset({"target_company_count", "expected_list_size", "companies_to_include"})

# `Ch3 §D.4` ② 的入选三字段（逐字）
ADMISSION_REQUIRED_FIELDS = ("raw_source", "inclusion_reason", "evidence_strength")

# 正式名单的落位（`Ch11 §D.2 p02` → registry/ 名单版本化）
ADMISSION_FILES = ("registry/shortlist.yaml", "registry/admission_list.yaml")

CONFIG_SCAN_DIRS = ("rules", "registry")


class AdmissionRejected(RuntimeError):
    """无出处 / 无理由 → 拒入正式名单。"""


def check_no_target_count(flat_keys: Iterable[str], relpath: str = "") -> list[Violation]:
    """① denylist：不得存在目标数量配置。"""
    hits = sorted({k for k in flat_keys if k in BANNED_COUNT_KEYS})
    return [
        Violation("N3.1-01/09", f"存在目标数量配置: {k}（名单规模 = 过门槛对象数，不补凑）", relpath)
        for k in hits
    ]


def assert_admission(obj: Mapping[str, Any]) -> None:
    """② 正式名单入选须三字段非空。"""
    for f in ADMISSION_REQUIRED_FIELDS:
        if not str(obj.get(f) or "").strip():
            raise AdmissionRejected(f"缺收录字段: {f}")


def check_shortlist(
    admitted: list[Mapping[str, Any]], configured_target: int | None
) -> list[Violation]:
    """③ 名单规模必须 = 过门槛对象数；任何"目标数量"都不得参与。"""
    v: list[Violation] = []
    if configured_target is not None:
        v.append(
            Violation(
                "N3.1-01/09",
                f"名单规模不得由目标数量决定（configured_target={configured_target}）",
            )
        )
    for obj in admitted:
        try:
            assert_admission(obj)
        except AdmissionRejected as exc:
            v.append(Violation("N3.1-08/10", f"{exc}（不得为凑数降门槛）"))
    return v


def _flatten_keys(node: Any) -> Iterator[str]:
    if isinstance(node, Mapping):
        for k, val in node.items():
            yield str(k)
            yield from _flatten_keys(val)
    elif isinstance(node, (list, tuple)):
        for val in node:
            yield from _flatten_keys(val)


def check(root: Path) -> CheckReport:
    import yaml

    report = CheckReport(checker="anti_padding")
    files: list[Path] = []
    for sub in CONFIG_SCAN_DIRS:
        files += walk_files(root, sub, (".yaml", ".yml", ".json"))
    report.scanned["config_files"] = len(files)
    report.scanned["banned_count_keys"] = len(BANNED_COUNT_KEYS)

    for path in files:
        relpath = rel(path, root)
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            report.violations.append(Violation("anti_padding-parse", f"解析失败: {exc}", relpath))
            continue
        if data is None:
            continue
        report.violations += check_no_target_count(_flatten_keys(data), relpath)

    # 正式名单文件（阶段① 尚未生成 → 显式说明，不冒充"已验证"）
    shortlists = [root / p for p in ADMISSION_FILES if (root / p).exists()]
    report.scanned["shortlist_files"] = len(shortlists)
    if not shortlists:
        report.notes.append(
            "NO_SHORTLIST_YET：正式名单（registry/shortlist.yaml）由 `p02` 证据核验后生成"
            "（阶段① 退出物为 sources.yaml + 口径表）；②③ 条的入选断言已就绪，"
            "本次**无被检对象**，不构成‘已验证不凑数’"
        )
        return report

    for path in shortlists:
        relpath = rel(path, root)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        admitted = list(data.get("admitted") or [])
        report.scanned.setdefault("admitted_objects", 0)
        report.scanned["admitted_objects"] += len(admitted)
        report.violations += check_shortlist(admitted, data.get("target_count"))
        # 名单规模不得被显式"配平"到某个数
        if "list_size" in data and data["list_size"] != len(admitted):
            report.violations.append(
                Violation(
                    "N3.1-01",
                    f"list_size({data['list_size']}) != 实际过门槛对象数({len(admitted)})",
                    relpath,
                )
            )
    return report


if __name__ == "__main__":
    sys.exit(run_checker("anti_padding.py", check))
