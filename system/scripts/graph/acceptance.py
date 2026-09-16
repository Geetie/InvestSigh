#!/usr/bin/env python3
"""`acceptance.py` —— **T01–T14 判定**（阶段③ `t01_t14_all_pass` 的唯一真源）。

```
python system/scripts/graph/acceptance.py [code_root] [--no-report]
```

## 权威表与台账

T01–T14 的**唯一权威表** = `10_验收与持续复盘/01_需求拆解.md §2.1`
（「T01–T14 权威定义表（唯一权威出处）」）。本模块不复制该表的语义，而是读
`registry/acceptance_input_set.yaml`（**台账**：逐字场景 / 预期行为 / 权威锚点 /
责任章 / 判定载体），并**逐条执行** `scripts/graph/acceptance_checks.py` 的判定器。

> ★ `10/02 §I.2` 把 T 表指向写成"本章 §B.1"是**错的**（`N-01`，需求方侧待修正）——
> 实现侧一律以 `10/01 §2.1` 为准（`authority_anchor`）。

## 判据（可判定、穷尽）

| # | 断言 | 依据 |
|---|---|---|
| A | 台账 `authority_anchor == "10/01 §2.1"` | 权威指向唯一 |
| B | 恰好 **14** 条、`t_id` 集合 == {T01..T14}（缺 / 多 / 重 → 违例） | `10/01 §N10.2-01`（14 项逐项有记录） |
| C | 每条 `scenario` / `expected_behavior` / `responsible_chapter` 非空 | `10/01 §2.1` 收口视图 |
| D | 每条 `programmatic` 的 `adjudicator` 与**代码里的判定器**机器绑定（函数名一致） | 铁律 5（声明 ↔ 实现机器绑定） |
| E | **每一 T 都真跑判定器**；任一 ❌ → 违例（携 T 号） | `10/01 §N10.2-01`（任一 ❌ 即整体不通过） |

★ `delegated` 条（责任章尚未提供可执行载体）**据实报 ❌**，绝不冒充当通过（`G-03`）。

退出码：`0` 放行（14/14 ✅）/ `1` 任一 ❌ / `2` 输入异常。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402
from scripts.graph import acceptance_checks  # noqa: E402

LEDGER_RELPATH = "registry/acceptance_input_set.yaml"
AUTHORITY_ANCHOR = "10/01 §2.1"
T_IDS: tuple[str, ...] = tuple(f"T{i:02d}" for i in range(1, 15))
_VALID_KINDS = ("programmatic", "delegated")


def load_ledger(root: str | Path) -> dict[str, Any]:
    """读台账（缺失 → `FileNotFoundError`，响亮失败，不静默当"无 T01–T14"）。"""
    import yaml

    path = Path(root) / LEDGER_RELPATH
    if not path.exists():
        raise FileNotFoundError(f"缺少 T01–T14 验收台账: {path}")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{LEDGER_RELPATH} 顶层不是 mapping")
    return doc


def t_case_rows(root: str | Path) -> list[dict[str, Any]]:
    rows = load_ledger(root).get("t_cases")
    if not isinstance(rows, list):
        raise ValueError(f"{LEDGER_RELPATH} 缺 t_cases 列表")
    return [r for r in rows if isinstance(r, dict)]


def _ledger_shape_violations(root: str | Path) -> list[Violation]:
    """台账自身的形状 / 权威 / 逐字内容校验（A / B / C / D）。"""
    doc = load_ledger(root)
    rows = t_case_rows(root)
    v: list[Violation] = []

    anchor = str(doc.get("authority_anchor") or "")
    if anchor != AUTHORITY_ANCHOR:
        v.append(
            Violation(
                "ACC-AUTHORITY",
                f"台账 authority_anchor={anchor!r} 必须为 {AUTHORITY_ANCHOR!r}"
                "（T01–T14 的唯一权威表；`10/02 §I.2` 的指向是错的 `N-01`）",
                LEDGER_RELPATH,
            )
        )

    seen: list[str] = [str(r.get("t_id")) for r in rows]
    duplicated = sorted({t for t in seen if seen.count(t) > 1})
    missing = sorted(set(T_IDS) - set(seen))
    extra = sorted(set(seen) - set(T_IDS))
    if duplicated:
        v.append(Violation("ACC-T-DUP", f"台账 t_id 重复：{duplicated}", LEDGER_RELPATH))
    if missing:
        v.append(
            Violation("ACC-T-MISSING", f"T 表不完整：缺 {missing}（须 14 项 T01–T14）", LEDGER_RELPATH)
        )
    if extra:
        v.append(Violation("ACC-T-EXTRA", f"台账出现越界 t_id：{extra}", LEDGER_RELPATH))

    for row in rows:
        t_id = str(row.get("t_id"))
        for field in ("scenario", "expected_behavior", "responsible_chapter"):
            if not str(row.get(field) or "").strip():
                v.append(
                    Violation("ACC-T-EMPTY", f"{t_id} 缺 {field}（权威表收口视图不完整）", LEDGER_RELPATH)
                )
        kind = str(row.get("adjudication") or "")
        if kind not in _VALID_KINDS:
            v.append(
                Violation(
                    "ACC-T-KIND",
                    f"{t_id} 的 adjudication={kind!r} 非法（须 {list(_VALID_KINDS)}）",
                    LEDGER_RELPATH,
                )
            )
            continue
        if kind == "programmatic":
            fn = acceptance_checks.ADJUDICATORS.get(t_id)
            carrier = str(row.get("adjudicator") or "")
            if fn is None:
                v.append(
                    Violation(
                        "ACC-T-CARRIER",
                        f"{t_id} 声明 programmatic，但代码里无判定器 "
                        f"（acceptance_checks.ADJUDICATORS 无此项）→ 声明与实现脱节",
                        LEDGER_RELPATH,
                    )
                )
            elif not carrier.endswith(f"::{fn.__name__}"):
                v.append(
                    Violation(
                        "ACC-T-CARRIER",
                        f"{t_id} 的 adjudicator={carrier!r} 与代码里的判定器 {fn.__name__} 不绑定"
                        "（须以 `::<函数名>` 结尾）",
                        LEDGER_RELPATH,
                    )
                )
        else:  # delegated
            if not str(row.get("delegated_to") or "").strip():
                v.append(
                    Violation(
                        "ACC-T-DELEGATED",
                        f"{t_id} 标 delegated 但未写明 delegated_to（责任章）",
                        LEDGER_RELPATH,
                    )
                )
    return v


def t01_t14_verdicts(root: str | Path) -> dict[str, bool]:
    """逐条 T 的判定结果（`True` = ✅）。**真跑** `acceptance_checks` 的判定器。"""
    return {
        t_id: not acceptance_checks.adjudicate(t_id, Path(root))
        for t_id in T_IDS
    }


def t01_t14_violations(root: str | Path) -> tuple[list[Violation], dict[str, int]]:
    """`t01_t14_all_pass` 判据的违例（含台账形状 + 逐条判定）。"""
    v = _ledger_shape_violations(root)

    # E：逐条真跑判定器；任一 ❌ → 违例（携 T 号与原因）
    passed = 0
    failed_ids: list[str] = []
    for t_id in T_IDS:
        violations = acceptance_checks.adjudicate(t_id, Path(root))
        if violations:
            failed_ids.append(t_id)
            v.extend(violations)
        else:
            passed += 1
    scanned = {"t_cases": len(T_IDS), "t_passed": passed, "t_failed": len(failed_ids)}
    return v, scanned


def t01_t14_check(root: Path) -> CheckReport:
    """`t01_t14_all_pass` 的唯一真源（供 `stage_gate` 复用）。"""
    report = CheckReport(checker="acceptance_t01_t14")
    violations, scanned = t01_t14_violations(root)
    report.violations += violations
    report.scanned.update(scanned)
    report.notes.append(
        f"T01–T14 判定：{scanned['t_passed']}/{scanned['t_cases']} ✅"
        f"（❌ = {scanned['t_failed']}）— 任一 ❌ 即阶段③ 整体不通过（`10/01 §2.1`）"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    return run_checker("acceptance_t01_t14", t01_t14_check, argv)


if __name__ == "__main__":
    sys.exit(main())
