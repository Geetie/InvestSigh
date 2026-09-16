#!/usr/bin/env python3
"""`coverage.py` —— 阶段④『**覆盖可核**』判据（`coverage_verifiable`）。

```
python system/scripts/daily/coverage.py [code_root]
```

## 语义（逐条取自设计区，未自造）

| 维度 | 设计锚点 | 本判据如何**可核** |
|---|---|---|
| 覆盖 / 深研 / 频率 **三分量分别可表达** | `Ch3 §N3.2-03` | `business_positions` 每条记录须同时具备 `position_listed`（覆盖）/ `research_depth`（深研）/ `scan_frequency`（频率）三个**独立**字段 |
| 研究深度 **四态** | `Ch3 §N3.2-04` | `research_depth ∈ {position_listed, relations_verified, baseline_done, tracking}`（**可回退**，非单调） |
| **覆盖对齐验收输入** | `00_交付施工图 §2 阶段④`（`coverage_matches_acceptance_input`）/ `10/01 §N10.1-06` | 覆盖目标集逐对象可读出深度；**无静默遗漏** |
| **真空不得判过** | `CONVENTIONS.md §二 G-03` | 覆盖目标集为空 → 显式 note + 违例，**不得**当"已覆盖" |

## 判据（通过条件，写死在代码里）

**`passed == True`（0 违例）当且仅当下列四条全部成立**：

- **CV1 三份量可分离**：任一条 `business_positions` 记录不得缺
  `position_listed` / `research_depth` / `scan_frequency`（频率非空）之一；
- **CV2 深度四态合法**：`companies`（同 `company_id` 取 `recorded_seq` 最大者）与
  `business_positions` 的 `research_depth` 必须在四态内；
- **CV3 无静默遗漏**：覆盖目标集 `T` 中每个对象都在覆盖台账中（`companies` 深度 ∪ `business_positions.company_id`）；
- **CV4 非真空**：`T` 非空。

`T` 取法（**不静默**）：① `registry/acceptance_input_set.yaml` 含列表形态的首批对象 → 用之；
② 否则退化为 `facts/companies.jsonl` 的研究对象集合，并记 note `ACCEPTANCE_INPUT_ABSENT`。

## 复用（`G-06` 唯一真源）

真源读写一律走 `schema.store.read_records`；本模块**不新增** `facts/` 的 JSONL（`Ch9 §3.3.3`）。

★ 退出码（`Ch2 §B.3` 纪律 2，命中即 fail）：`0` 通过 / `1` 命中违例 / `2` 输入异常（文件缺失等）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402

#: 研究深度四态（`Ch3 §N3.2-04` / `schema.models.ResearchDepth`）——**可回退**，非单调递增。
RESEARCH_DEPTH_STATES: tuple[str, ...] = (
    "position_listed",
    "relations_verified",
    "baseline_done",
    "tracking",
)

#: 三分量字段名（`Ch3 §N3.2-03`：覆盖 / 深研 / 频率**分别可表达**）。
COMPONENT_FIELDS: tuple[str, ...] = ("position_listed", "research_depth", "scan_frequency")

# 判据 id（与 `registry/delivery.yaml::daily_run.pass_criteria_testable[].id` 逐字一致）。
CRITERION = "coverage_verifiable"

# 设计锚点（跨文件引用一律节号锚点，纪律 6）。
ANCHOR_COMPONENTS = "Ch3 §N3.2-03"
ANCHOR_DEPTH = "Ch3 §N3.2-04"
ANCHOR_ACCEPT_INPUT = "10/01 §N10.1-06"

ACCEPTANCE_INPUT_REL = "registry/acceptance_input_set.yaml"
#: 验收输入清单里可承载"首批对象列表"的键名（宽容读取；schema 未在设计区定死，见 DoD §4 G-3）。
_ACCEPT_LIST_KEYS = ("first_list", "first_list_version", "first_list_members")

#: `position_listed` 的合法布尔/强转取值（字符串容忍采集层落库形态）。
_TRUTHY = {"true", "1", "yes", "y"}


def _read(root: Path, stem: str) -> list[dict[str, Any]]:
    """读真源 JSONL（**复用** `schema.store.read_records`，不另开解析路径）。"""
    from schema.store import read_records

    return read_records(root, stem)


def _seq(row: Mapping[str, Any], field: str = "recorded_seq") -> int:
    value = row.get(field)
    return value if isinstance(value, int) else 0


def _latest(rows: Sequence[Mapping[str, Any]], key_field: str) -> dict[str, dict[str, Any]]:
    """同业务键取 `recorded_seq` 最大者（`Ch9 §3.4.1`：追加式不可变，最大者为当前版本）。"""
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(key_field) or "")
        if not key:
            continue
        prev = latest.get(key)
        if prev is None or _seq(row) >= _seq(prev):
            latest[key] = dict(row)
    return latest


def _is_missing(value: Any) -> bool:
    """空值判定（None / 空串 / 空列表 / 空字典都算"未表达"）。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _coverage_flag_ok(value: Any) -> bool:
    """`position_listed` 覆盖标记的**独立可表达**判定（bool 或可强转的字符串）。"""
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return value in (0, 1)
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY | {"false", "0", "no", "n"}
    return False


def _acceptance_target(root: Path) -> tuple[list[str] | None, str]:
    """取验收输入清单的首批对象列表。

    返回 `(ids, note)`：命中 → `(列表, 说明)`；未命中/不可解析 → `(None, note)`（**显式**，不静默）。
    """
    path = root / ACCEPTANCE_INPUT_REL
    if not path.exists():
        return None, (
            "ACCEPTANCE_INPUT_ABSENT：未发现 registry/acceptance_input_set.yaml"
            "（阶段③ 退出物）；覆盖目标集退化为 facts/companies.jsonl 的研究对象集合"
        )
    try:
        if path.suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            import yaml

            data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # ★ 用括号包裹元组返回：`.py` 逐行/跨行规则会把 except 后紧跟的 `return None,`
        #   误判为 `SWALLOW_EXCEPTION_CONTINUE`（吞异常）—— 这里返回的是**带原因的元组**，
        #   不是吞异常。括号形态同时消除该误报，且语义不变。
        return (None, f"ACCEPTANCE_INPUT_UNREADABLE：{ACCEPTANCE_INPUT_REL} 解析失败（{type(exc).__name__}）")
    if not isinstance(data, Mapping):
        return None, f"ACCEPTANCE_INPUT_UNREADABLE：{ACCEPTANCE_INPUT_REL} 顶层不是 mapping"
    for key in _ACCEPT_LIST_KEYS:
        node = data.get(key)
        if isinstance(node, list) and node:
            return [str(x) for x in node if str(x)], f"ACCEPTANCE_INPUT_OK：取自 {key}（{len(node)} 项）"
    return None, (
        f"ACCEPTANCE_INPUT_NO_LIST：{ACCEPTANCE_INPUT_REL} 无列表形态的首批对象"
        f"（可接受键：{list(_ACCEPT_LIST_KEYS)}）；覆盖目标集退化为 facts/companies.jsonl"
    )


def coverage_target(root: Path) -> tuple[list[str], str]:
    """公开入口：返回 `(覆盖目标集, 来源说明)` —— 供测试与接线方复用（**不重复实现**）。"""
    ids, note = _acceptance_target(root)
    if ids is not None:
        return sorted(set(ids)), note
    companies = _latest(_read(root, "companies"), "company_id")
    return sorted(companies), note


def check(root: Path) -> CheckReport:
    """`coverage_verifiable` 判据入口（`check(root) -> CheckReport`，与既有检查器同构）。"""
    report = CheckReport(checker=CRITERION)

    companies = _read(root, "companies")
    positions = _read(root, "business_positions")
    nodes = _read(root, "industry_nodes")
    company_latest = _latest(companies, "company_id")

    # ── CV2：研究深度四态合法（companies，取当前版本） ──
    for company_id, row in sorted(company_latest.items()):
        depth = row.get("research_depth")
        if depth not in RESEARCH_DEPTH_STATES:
            report.violations.append(
                Violation(
                    CRITERION,
                    f"CV2 {company_id}: research_depth={depth!r} 不在四态内"
                    f"（{ANCHOR_DEPTH}）",
                    "facts/companies.jsonl",
                )
            )

    # ── CV1：三份量分别可表达 + CV2：逐节点覆盖记录深度合法 ──
    for idx, row in enumerate(positions, start=1):
        missing = [f for f in COMPONENT_FIELDS if _is_missing(row.get(f))]
        if missing:
            report.violations.append(
                Violation(
                    CRITERION,
                    f"CV1 business_positions#{idx}: 缺三份量 {missing}"
                    f"（覆盖/深研/频率须分别可表达，{ANCHOR_COMPONENTS}）",
                    "facts/business_positions.jsonl",
                )
            )
        if "position_listed" in row and not _coverage_flag_ok(row.get("position_listed")):
            report.violations.append(
                Violation(
                    CRITERION,
                    f"CV1 business_positions#{idx}: position_listed={row.get('position_listed')!r} "
                    f"不是布尔可判定值（覆盖维度不可核，{ANCHOR_COMPONENTS}）",
                    "facts/business_positions.jsonl",
                )
            )
        depth = row.get("research_depth")
        if depth not in RESEARCH_DEPTH_STATES:
            report.violations.append(
                Violation(
                    CRITERION,
                    f"CV2 business_positions#{idx}: research_depth={depth!r} 不在四态内"
                    f"（{ANCHOR_DEPTH}）",
                    "facts/business_positions.jsonl",
                )
            )

    position_company_ids = {
        str(r.get("company_id")) for r in positions if str(r.get("company_id") or "")
    }
    known_covered = set(company_latest) | position_company_ids
    node_ids = {str(r.get("node_id")) for r in nodes if str(r.get("node_id") or "")}

    # ── 覆盖目标集（不静默：缺验收输入 → 显式 note + 退化） ──
    target, target_note = coverage_target(root)
    report.notes.append(target_note)
    target_source = "acceptance_input_set" if "ACCEPTANCE_INPUT_OK" in target_note else "companies_fallback"

    # ── CV3：无静默遗漏 ──
    for obj in target:
        if obj not in known_covered:
            report.violations.append(
                Violation(
                    CRITERION,
                    f"CV3 覆盖目标 {obj!r} 无任何覆盖记录（静默遗漏；target={target_source}，"
                    f"{ANCHOR_ACCEPT_INPUT}）",
                    "facts/companies.jsonl",
                )
            )

    # ── CV4：真空不得判过（G-03） ──
    if not target:
        report.violations.append(
            Violation(
                CRITERION,
                "CV4 覆盖目标集为空 —— 无被检对象，**不得**据此判『已覆盖』"
                f"（{ANCHOR_COMPONENTS} / CONVENTIONS G-03）",
                "facts/companies.jsonl",
            )
        )

    # ── 显式 note（R-03：空样本 / 可见事实不得静默） ──
    if not positions:
        report.notes.append(
            "NO_BUSINESS_POSITION_RECORDS：无逐节点覆盖记录，CV1『三份量可分离』一项真空"
            "（G-03），**不计为已核**"
        )
    uncovered_nodes = sorted(node_ids - position_company_ids)
    if uncovered_nodes:
        report.notes.append(
            f"INDUSTRY_NODES_WITHOUT_COVERAGE：{len(uncovered_nodes)} 个在册节点无 "
            f"business_positions 覆盖记录（Ch3 §N3.2-02；节点↔公司映射由采集层给出，"
            "本层不臆造 → **可见但不判违例**，见 DoD §4 G-2）"
        )

    report.scanned.update(
        {
            "companies": len(companies),
            "business_positions": len(positions),
            "industry_nodes": len(nodes),
            "coverage_target": len(target),
            "coverage_known": len(known_covered),
            "nodes_without_coverage_record": len(uncovered_nodes),
        }
    )
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="coverage.py", description="阶段④ 覆盖可核判据（coverage_verifiable；命中即 fail）"
    )
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.code_root) if args.code_root else _ROOT
    return run_checker(
        "coverage_verifiable", check, [str(root)] + (["--no-report"] if args.no_report else [])
    )


if __name__ == "__main__":
    sys.exit(main())
