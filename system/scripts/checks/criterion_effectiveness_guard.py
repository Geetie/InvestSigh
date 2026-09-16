#!/usr/bin/env python3
"""`criterion_effectiveness_guard.py` —— **判据有效性门禁**（缺口 `G9`）。

```
python system/scripts/checks/criterion_effectiveness_guard.py [code_root] [--no-report]
```

## 为什么需要它（`G9`：绑定 ≠ 会拦）

`stage_gate.bound_criteria()` 用 AST 证明"**判据声明**与**函数体**连上了线"
（删掉一行 `criterion(...)` → `criteria_bound` 4→3，审计已验证）。
但独立审计同时证明：**把 `cv = coverage_check(root)` 换成空 `CheckReport`，
`bound` 仍是 4，而不达标数据照样变绿**。

⇒ 绑定只证明"**接了**"，**不证明"真的在查"**。本门禁把义务从「接了」强化到
「**有一条可执行的、证明它会拦的反例**」。

## 断言（每条都是封闭集合判定，`R-06` allowlist 式）

| # | 断言 | 依据 |
|---|---|---|
| A | **已绑定 ⊆ 已登记反例**：`stage_gate` 函数体内已绑定的每条 automated 判据，都必须在 `registry/criterion_counterexamples.yaml` 有登记 —— 新绑一条却不登记 → **FATAL** | `G9` / `R-06` / 铁律 5 |
| B | **登记 ⊆ 已绑定**：登记里出现"未绑定 / 未声明"的 (stage, criterion) → **FATAL**（防预登记绕过 A） | `R-06` allowlist |
| C | 每条登记指向的测试**真的存在**：用 **AST** 扫 `tests/**` 收集 `def test_*` 比对；且**测试函数名必须含判据 id**（防把反例改指向一个无关的、恒过的用例） | `G-02` / `G-06` |
| D | `counterexample` 条目必须带非空 `blocked_hint`（判据专属拦截标记）；`ineffective` 条目必须带非空 `reason` + 其测试必须**实测**该判据无判别力 | `G-03` / `R-02` |
| E | **唯一真源自校**：本门禁算出的 `声明 automated 但未绑定` 必须与 `stage_gate.criteria_not_implemented()` **逐阶段相等** —— 否则说明出现了第二套解析/谓词 | `G-06` |
| F | **不可见不得当已核**：`ineffective`（实测无判别力）的判据、以及"只有 ineffective 条目"的判据（`criteria_without_counterexample`）逐条进 `note` 并计数；未绑定（阶段②③待交付）的判据显式计数 | `G-03` |

★ 一个判据**可以有多条**条目（并允许同时有 `counterexample` 与 `ineffective`）：
  一条判据本来就可能有多条**互不重叠的违反轴**，压成一条会丢失证据。
  去重口径是「**测试路径全局唯一**」（防同一测试冒充多条证据），而**不是**判据级唯一。
  典型例子：`expansion::review_append_only` 有 3 条 `counterexample`
  （三层缺层 / 已声明层消失 / append-only 守卫没罩住本真源）+ 1 条 `ineffective`
  （`(success, failure, pending)` 三类记录**无载体**，按 `G-03` 显式记账）。

★ 为什么 `ineffective` 不是一个"手改一行就绕过"的口子：该条目的测试必须
  **断言"不合规输入下门禁仍然不红"**（即"违例集合与合规输入完全相同"）。
  若该判据其实有判别力，这个测试**当场就红** —— 于是"谎报 ineffective"
  需要写一个**必然失败**的测试，而不是改一行数据（铁律 5）。

★ 退出码（`Ch2 §B.3`，命中即 fail）：`0` 放行 / `1` 命中违例 / `2` 输入异常。
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import (  # noqa: E402
    CheckReport,
    Violation,
    _cached_yaml,
    run_checker,
)

#: 判据绑定的**唯一真源**（`G-06`）：本门禁不另写解析，直接复用它的 `bound_criteria()`。
STAGE_GATE_RELPATH = "scripts/delivery/stage_gate.py"
DELIVERY_RELPATH = "registry/delivery.yaml"
REGISTRY_RELPATH = "registry/criterion_counterexamples.yaml"
TESTS_DIR = "tests"

KIND_COUNTEREXAMPLE = "counterexample"
KIND_INEFFECTIVE = "ineffective"
KINDS = (KIND_COUNTEREXAMPLE, KIND_INEFFECTIVE)

#: `check_kind` 含该子串即视为 automated（与 `stage_gate.criteria_not_implemented()` **同一谓词**，
#: 由断言 E 逐阶段比对两者结果，故不存在"第二套判定"）。
AUTOMATED_MARK = "automated"


def _load_stage_gate(root: Path) -> Any:
    """按**文件路径**加载被检 `code_root` 的 `stage_gate.py`。

    ★ 必须加载**被检 root 的那一份**：`bound_criteria()` 用 `Path(__file__)` 定位自身，
      加载副本的那一份才能让"往副本里加一行 `criterion(...)`"真的改变绑定集合
      （`verification_policy_guard._load_verify()` 同源理由）。

    ★ 全局副作用必须复原（`P-04`）：`stage_gate.py` 模块级会 `sys.path.insert`，
      且在 `scripts` 尚未入 `sys.modules` 时会把它指向被检 root —— 用 `try/finally`
      把 `sys.path` 与**新引入的** `scripts*` 模块全部还原，否则同进程内后续检查器
      会加载到副本的 `scripts`。
    """
    path = root / STAGE_GATE_RELPATH
    if not path.exists():
        raise FileNotFoundError(f"缺少判据绑定的唯一真源: {path}")
    name = "_stage_gate_under_audit"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载 {path}")
    module = importlib.util.module_from_spec(spec)
    before_modules = set(sys.modules)
    before_path = list(sys.path)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = before_path
        sys.modules.pop(name, None)
        for extra in set(sys.modules) - before_modules:
            if extra == "scripts" or extra.startswith("scripts."):
                sys.modules.pop(extra, None)
    return module


def _declared_automated(stage_gate: Any, root: Path) -> dict[str, set[str]]:
    """各阶段**声明为 automated** 的判据 id（取自 `registry/delivery.yaml`）。"""
    out: dict[str, set[str]] = {}
    for stage, crits in stage_gate.declared_criteria(root).items():
        out[stage] = {
            str(c.get("id")) for c in crits if AUTOMATED_MARK in str(c.get("check_kind", ""))
        }
    return out


def _test_index(root: Path) -> dict[str, set[str]]:
    """`tests/**/test_*.py` → 文件内 `def test_*` 函数名集合（**AST**，非 grep/字符串包含）。

    单文件一次 `ast.parse` + 一遍 `ast.walk`（`P-01`：不对每个节点再 walk）。
    """
    tests_dir = root / TESTS_DIR
    if not tests_dir.is_dir():
        raise FileNotFoundError(f"缺少 tests/ 目录: {tests_dir}")
    index: dict[str, set[str]] = {}
    for path in sorted(tests_dir.rglob("test_*.py")):
        rel = path.relative_to(root)
        if any(part.startswith(".") or part == "__pycache__" for part in rel.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            raise ValueError(f"{rel}: 语法错误，无法核对登记的反例测试: {exc}") from exc
        names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        }
        index[rel.as_posix()] = names
    return index


def _entries(root: Path, report: CheckReport) -> list[dict[str, Any]]:
    """读登记表（`P-02`：走 `_cached_yaml`，不在循环里读盘）。"""
    path = root / REGISTRY_RELPATH
    if not path.exists():
        report.violations.append(
            Violation(
                "G9",
                f"缺少判据反例登记表 {REGISTRY_RELPATH} —— 「已绑定判据必须有可执行反例」"
                "这项义务因此无法被强制（铁律 5：手工台账之外的义务等于不存在）",
                REGISTRY_RELPATH,
            )
        )
        return []
    doc = _cached_yaml(path) or {}
    if not isinstance(doc, dict):
        raise ValueError(f"{REGISTRY_RELPATH} 顶层不是 mapping")
    rows = doc.get("counterexamples")
    if not isinstance(rows, list):
        raise ValueError(f"{REGISTRY_RELPATH} 缺 counterexamples 列表")
    return [r for r in rows if isinstance(r, dict)]


def _check_registry_shape(
    entries: list[dict[str, Any]], stages: set[str], declared: dict[str, set[str]]
) -> list[Violation]:
    """登记表自身的形状与归属校验（A/B 的前置）。"""
    v: list[Violation] = []
    seen_tests: dict[str, str] = {}
    for idx, row in enumerate(entries, start=1):
        stage = str(row.get("stage") or "")
        cid = str(row.get("criterion_id") or "")
        kind = str(row.get("kind") or "")
        where = f"{REGISTRY_RELPATH}#{idx}"
        if stage not in stages:
            v.append(Violation("G9", f"{where}: 非法 stage {stage!r}（合法：{sorted(stages)}）", REGISTRY_RELPATH))
        if not cid:
            v.append(Violation("G9", f"{where}: criterion_id 为空", REGISTRY_RELPATH))
        if kind not in KINDS:
            v.append(
                Violation("G9", f"{where}: kind={kind!r} 非法（须 one of {list(KINDS)}）", REGISTRY_RELPATH)
            )
        if stage in declared and cid and cid not in declared[stage]:
            v.append(
                Violation(
                    "G9",
                    f"{where}: 判据 {cid!r} 未在 {DELIVERY_RELPATH} 的 {stage} 阶段声明为 automated "
                    "→ 登记了一条不存在的判据（不得据自造条目充数）",
                    REGISTRY_RELPATH,
                )
            )
        # ★ 同一判据**允许多条** `counterexample`（也允许多条 `ineffective`）：一条判据本来
        #   就可能有多条**互不重叠**的违反轴（例：`expansion::review_append_only` 有
        #   ① 三层缺层、② 已声明层消失、③ append-only 守卫没罩住本真源 三个独立被检面），
        #   把它们压成一条会**丢失证据**。
        #   故唯一的去重口径改为「**测试路径全局唯一**」—— 防的是同一测试被登记多次冒充多条
        #   证据（灌水），而不是防同判据多轴。
        #   义务本身（A：已绑定判据 ≥1 条 counterexample）不受影响。
        test_ref = str(row.get("test") or "").strip()
        if test_ref:
            if test_ref in seen_tests:
                v.append(
                    Violation(
                        "G9",
                        f"{where}: 测试 {test_ref} 被重复登记（已在 {seen_tests[test_ref]}）"
                        " —— 同一条测试不得冒充多条反例证据",
                        REGISTRY_RELPATH,
                    )
                )
            else:
                seen_tests[test_ref] = where
        if kind == KIND_COUNTEREXAMPLE and not str(row.get("blocked_hint") or "").strip():
            v.append(
                Violation(
                    "G9",
                    f"{where}: counterexample 条目缺 blocked_hint —— 反例必须给出该判据**专属**的"
                    "拦截标记（否则「门禁红了」可能来自任何别的判据，不构成判别力证据）",
                    REGISTRY_RELPATH,
                )
            )
        if kind == KIND_INEFFECTIVE and not str(row.get("reason") or "").strip():
            v.append(
                Violation(
                    "G9",
                    f"{where}: ineffective 条目缺 reason —— 断言「该判据无判别力」必须给出可复核理由（`R-02`/`G-03`）",
                    REGISTRY_RELPATH,
                )
            )
    return v


def _check_entry_tests(
    entries: list[dict[str, Any]], index: dict[str, set[str]]
) -> tuple[list[Violation], int]:
    """C：登记指向的测试必须真实存在，且函数名必须含判据 id（防改指向无关用例）。"""
    v: list[Violation] = []
    resolved = 0
    for idx, row in enumerate(entries, start=1):
        node = str(row.get("test") or "").strip()
        cid = str(row.get("criterion_id") or "")
        where = f"{REGISTRY_RELPATH}#{idx}"
        if not node:
            v.append(Violation("G9", f"{where}: 缺 test（pytest 节点 id）", REGISTRY_RELPATH))
            continue
        rel, _, func = node.partition("::")
        if not rel or not func:
            v.append(
                Violation(
                    "G9",
                    f"{where}: test={node!r} 不是 `tests/...py::test_xxx` 形态的 pytest 节点 id",
                    REGISTRY_RELPATH,
                )
            )
            continue
        names = index.get(rel)
        if names is None:
            v.append(
                Violation(
                    "G9",
                    f"{where}: 反例测试文件不存在或不可收集: {rel!r} —— 登记了一个不存在的测试，"
                    "义务等于没履行（AST 扫 tests/** 比对，非字符串包含）",
                    REGISTRY_RELPATH,
                )
            )
            continue
        if func not in names:
            v.append(
                Violation("G9", f"{where}: {rel} 内不存在测试函数 {func!r}", REGISTRY_RELPATH)
            )
            continue
        if cid and cid not in func:
            v.append(
                Violation(
                    "G9",
                    f"{where}: 测试函数名 {func!r} 未含判据 id {cid!r} —— 无法阻止把登记改指向一个"
                    "与本案无关的用例（`G-02` 函数级绑定）",
                    REGISTRY_RELPATH,
                )
            )
            continue
        resolved += 1
    return v, resolved


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="criterion_effectiveness_guard")
    stage_gate = _load_stage_gate(root)

    stages = set(stage_gate.STAGES)
    bound = {key: set(ids) for key, ids in stage_gate.bound_criteria().items()}
    declared = _declared_automated(stage_gate, root)
    entries = _entries(root, report)
    index = _test_index(root)

    report.scanned["stages"] = len(stages)
    report.scanned["criteria_declared_automated"] = sum(len(s) for s in declared.values())
    report.scanned["criteria_bound"] = sum(len(s) for s in bound.values())

    # ── E. 唯一真源自校：本门禁的谓词必须与 `stage_gate.criteria_not_implemented()` 逐阶段一致 ──
    for key in sorted(stages):
        mine = sorted(declared.get(key, set()) - bound.get(key, set()))
        theirs = stage_gate.criteria_not_implemented(root, key)
        if mine != theirs:
            report.violations.append(
                Violation(
                    "G-06",
                    f"阶段 {key} 的「声明 automated 但未绑定」两侧不一致：本门禁算得 {mine}，"
                    f"stage_gate.criteria_not_implemented() 算得 {theirs} —— 出现了第二套解析/谓词",
                    REGISTRY_RELPATH,
                )
            )

    registered = {
        (str(r.get("stage") or ""), str(r.get("criterion_id") or "")) for r in entries
    }
    report.scanned["criteria_registry_entries"] = len(entries)
    report.scanned["counterexample_entries"] = sum(
        1 for r in entries if str(r.get("kind")) == KIND_COUNTEREXAMPLE
    )
    report.scanned["ineffective_entries"] = sum(
        1 for r in entries if str(r.get("kind")) == KIND_INEFFECTIVE
    )

    # ── A. 已绑定 ⊆ 已登记（H2 的核心义务） ──
    for key in sorted(stages):
        for cid in sorted(bound.get(key, set())):
            if (key, cid) not in registered:
                report.violations.append(
                    Violation(
                        "G9",
                        f"阶段 {key} 的判据 {cid!r} **已在 {STAGE_GATE_RELPATH} 函数体内绑定**，"
                        f"但 {REGISTRY_RELPATH} 无对应登记 → 没有任何可执行反例证明它**真的会拦**。"
                        "（绑定只证明「接了」，不证明「真的在查」；新绑一条判据就必须同时登记反例）",
                        REGISTRY_RELPATH,
                    )
                )

    # ── B. 登记 ⊆ 已绑定（防预登记 / 陈旧登记绕过 A） ──
    for stage, cid in sorted(registered):
        if stage in stages and cid not in bound.get(stage, set()):
            report.violations.append(
                Violation(
                    "G9",
                    f"{REGISTRY_RELPATH} 登记了 {stage}::{cid}，但它**未被绑定**"
                    "（函数体内无 criterion() 声明）→ 陈旧/预登记条目，不得据它拒绝 A 的义务",
                    REGISTRY_RELPATH,
                )
            )

    report.violations += _check_registry_shape(entries, stages, declared)
    test_violations, resolved = _check_entry_tests(entries, index)
    report.violations += test_violations
    report.scanned["registry_entry_tests_resolved"] = resolved

    # ── F. G-03：不可见/无判别力的事实必须显式列出，不得当"已验证" ──
    ineffective_rows = [r for r in entries if str(r.get("kind")) == KIND_INEFFECTIVE]
    for row in sorted(ineffective_rows, key=lambda r: (str(r.get("stage")), str(r.get("criterion_id")))):
        label = f"{row.get('stage')}::{row.get('criterion_id')}"
        has_counterexample = (str(row.get("stage")), str(row.get("criterion_id"))) in {
            (str(r.get("stage")), str(r.get("criterion_id")))
            for r in entries
            if str(r.get("kind")) == KIND_COUNTEREXAMPLE
        }
        tail = (
            "该判据另有 counterexample 条目（证明**所绑定的那个检查**会拦），"
            "本条只针对其**字面语义中未被绑定的方面**"
            if has_counterexample
            else "反例义务改由「该判据无判别力」的探针测试承担"
        )
        report.notes.append(
            f"判据有效性缺口[{label}]：{tail} —— 实测无可判别检查（{row.get('reason')}）；"
            "实现检查后该探针测试会红，从而强制更新本登记"
        )
    without_counterexample = sorted(
        f"{stage}::{cid}"
        for stage in sorted(stages)
        for cid in sorted(bound.get(stage, set()))
        if (stage, cid)
        not in {
            (str(r.get("stage")), str(r.get("criterion_id")))
            for r in entries
            if str(r.get("kind")) == KIND_COUNTEREXAMPLE
        }
    )
    report.scanned["criteria_without_counterexample"] = len(without_counterexample)
    report.notes.append(
        f"无反例判据（已绑定但只有 ineffective 条目）：{len(without_counterexample)} 条"
        f"（{without_counterexample}）—— 逐条见上面的缺口 note，**不计为已验证**（`G-03`）"
    )
    not_implemented = {
        key: sorted(declared.get(key, set()) - bound.get(key, set())) for key in sorted(stages)
    }
    for key, ids in not_implemented.items():
        report.notes.append(
            f"未绑定判据[{key}]：{len(ids)} 条（{ids}）—— 属后续阶段待交付，**不计为已验证**"
            "（`G-03`：无被检对象不得当成已核）"
        )
    report.scanned["criteria_not_implemented"] = sum(len(v) for v in not_implemented.values())
    return report


if __name__ == "__main__":
    sys.exit(run_checker("criterion_effectiveness_guard.py", check))
