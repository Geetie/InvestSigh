#!/usr/bin/env python3
"""`conflict_scan.py` —— **L1–L5 聚合入口**（`Ch2 §B.3` Checker-1~5 / `§B.4` 4 个时机）。

```
python system/scripts/checks/conflict_scan.py [code_root] [--timing pre_commit|ci|daily_pre_publish|nightly]
```

| 时机 | 机制 | 跑哪些层 |
|---|---|---|
| `pre_commit`        | Git `pre-commit` hook 调用 | L1–L5 |
| `ci`                | GitHub Actions（push 时全量） | L1–L5 |
| `daily_pre_publish` | 每日跑第 7 步（发布）**之前** | L4 + L5 |
| `nightly`           | WorkBuddy Automation（`rrule` 每日）全量 + 差异报告 | L1–L5 |

★ **命中即 fail（非零退出），禁止 warn-only**（纪律 2 / `Ch2 §B.3`）。
★ 退出码：0 放行 / 1 阻断 / 2 输入异常（`00_开发Agent开工提示词 §八 N-2`）。
★ 被检目标（`Ch2 §B.4「被检目标清单（含新层配置）」`）：
  `scripts/**/*.py` · `rules/**/*.yaml|json` · schema · gate 输入结构 ·
  `views/**` 渲染配置 · `rules/trigger.yaml` · `rules/notification.yaml` ·
  三入口展示配置 · **`rules/freeze.yaml`（含 `freeze_param[p10].caliber_terms`）** ·
  `registry/delivery.yaml`。
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import (  # noqa: E402
    EXIT_INPUT_ERROR,
    EXIT_OK,
    EXIT_VIOLATION,
    CheckReport,
    Violation,
    decision_scope_config,
    is_checker_namespace,
    is_decision_scope_module,
    is_freeze_param_reader,
    load_banned_tokens,
    matches_call_chain,
    rel,
    walk_files,
    write_report,
)

# ── L3 被检目标清单（Ch2 §B.4）────────────────────────────────────────────
# 不止既有 rules/**/*；第八/十/十一章新引入的配置一并纳入，
# 以守卫"不得把待定项补成新门槛"这条源稿红线在新层不失效。
CONFIG_SCAN_TARGETS = (
    "rules",
    "registry",
)

# ★ L3 自命中豁免：禁词表**自己就是禁词的唯一真源**——它的 `tokens[*].token`
#   按定义必然逐条等于禁词。若不豁免，L3 会稳定产出「每条禁词都命中自己」，
#   门禁永远红 → 最后一定有人把它关掉。**降噪就是有效性**（发现于实测：
#   首次真跑 L3 报 7 条自命中）。
L3_SELF_EXEMPT = ("rules/banned_tokens.yaml",)


def _layer_tokens(banned: dict[str, Any], layer: str) -> list[dict[str, Any]]:
    return [t for t in banned.get("tokens", []) if layer in (t.get("layers") or [])]


def _normalize(text: str) -> str:
    return text.strip().strip("\"'").lower()


# ───────────────────────────────── L1：schema 字段存在性断言 ─────────────────────────────────

SCHEMA_PATH = Path("schema") / "jsonschema" / "facts.schema.json"


def check_L1(root: Path, report: CheckReport) -> None:
    """P-03 / P-04 / P-05 / P-07 —— **作用域 = `Recommendation` 的字段名集合**。

    ★ 禁止扩展成全仓 token 遍历：`assert_absent(rec, ...)` 只对 `Recommendation` 字段名生效。
      合法同名词 `position_listed` / `business_positions`（"产业链位置"语义）**不得误报**。
    """
    from schema.assertions import assert_absent, assert_present, enum_of

    path = root / SCHEMA_PATH
    if not path.exists():
        raise FileNotFoundError(f"L1: 缺少聚合 schema（先跑 system/schema/build_jsonschema.py）: {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    defs = doc.get("defs") or {}
    if "Recommendation" not in defs:
        raise ValueError("L1: schema 缺少 defs.Recommendation")
    rec = defs["Recommendation"]["properties"]      # ← 作用域边界
    report.scanned["l1_recommendation_field_count"] = len(rec)

    try:
        assert_absent(
            rec,
            [
                "stop_loss", "stop_price", "price_stop",                       # P-03
                "quantity", "position", "shares_held", "cost_basis",            # P-04
                "portfolio_weight",                                            # P-04
                "consensus", "market_view", "average_forecast",                # P-07
            ],
        )
    except AssertionError as exc:
        report.violations.append(Violation("P-03/P-04/P-07", str(exc), SCHEMA_PATH.as_posix()))

    # P-05：action 枚举不得含做空。★ 断言**全 schema 任何枚举**都不含 `short` /
    # `short_sell`——不只 `Recommendation.action` 那一处。
    # 原因（实测暴露）：`build_jsonschema.py` 为便于读取把 `$ref` **内联**进
    # `Recommendation.properties.action`，于是同一枚举在 schema 里出现两份
    # （`$ref` 目标 + 内联副本）。只查内联副本时，改 `$ref` 目标不会被发现——
    # 稀疏点全量扫描把这个"双写漂移"窗口关掉。
    try:
        action_enum = set(enum_of(rec, "action"))
        if action_enum != {"buy", "sell", "pending", "maintain"}:
            report.violations.append(
                Violation(
                    "P-05",
                    f"action 枚举非法: {sorted(action_enum)}（不得含 short / short_sell）",
                    SCHEMA_PATH.as_posix(),
                )
            )
    except AssertionError as exc:
        report.violations.append(Violation("P-05", str(exc), SCHEMA_PATH.as_posix()))

    shorting = {"short", "short_sell"} & _collect_enum_values(defs)
    if shorting:
        report.violations.append(
            Violation(
                "P-05",
                f"schema 中存在做空枚举值 {sorted(shorting)}（任何对象上都不得有）",
                SCHEMA_PATH.as_posix(),
            )
        )

    # Ch2 §C.1 / §D.2 修复项必须存在
    try:
        assert_present(rec, ["opportunity_types", "horizon", "start_date"])
    except AssertionError as exc:
        report.violations.append(Violation("Ch2 §C.1/§D.2", str(exc), SCHEMA_PATH.as_posix()))

    # 合法同名词不得被 L1 误报（回归断言：它们不在 `Recommendation` 上，但必须以
    # **正确的形态**存在 —— `business_positions` 是 **JSONL 对象名**（顶层 `objects`
    # 映射），`position_listed` 是**枚举值**。初版把两个都当"属性名"找，于是稳定
    # 报一条**假警报**（"schema 可能遗漏"）—— 噪声会稀释真信号，故按真实归属校验。）
    enum_values = _collect_enum_values(defs)
    objects = doc.get("objects") or {}
    if "business_positions" not in objects:
        report.violations.append(
            Violation(
                "Ch2 §B.1 通则",
                "回归断言失败：JSONL 对象 business_positions 不在 schema.objects 中"
                "（P-04 的合法同义词豁免将失去落点）",
                SCHEMA_PATH.as_posix(),
            )
        )
    if "position_listed" not in enum_values:
        report.violations.append(
            Violation(
                "Ch2 §B.1 通则",
                "回归断言失败：枚举值 position_listed 不在 schema 任何枚举中"
                "（研究深度枚举缺失，未研究/待判断无法区分）",
                SCHEMA_PATH.as_posix(),
            )
        )


def _collect_enum_values(defs: dict[str, Any]) -> set[str]:
    """收集 schema 中所有 `enum` 列表的取值（用于合法同义词回归断言）。"""
    found: set[str] = set()

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                if key == "enum" and isinstance(val, list):
                    found.update(str(v) for v in val)
                else:
                    _walk(val)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(defs)
    return found


# ───────────────────────── L2：AST + 禁词表扫描（P-01 / P-02 / P-09） ─────────────────────────

def _iter_tokens(nodes: Iterable[ast.AST]) -> Iterator[tuple[str, int]]:
    """单遍产出 `(token, 行号)`。

    ★ 为什么不用 `ast.walk(node)` 包一层：初版对"每个被访问节点"又调一次
      `ast.walk`，叠加外层的 scope 遍历 → **O(n²)**（`check_L2` 实测 4.57s，
      占整个检查器 1.36s×多次调用里的大头）。
      现在遍历一次树、就地取 token，复杂度回到 O(n)。
    """
    for node in nodes:
        if isinstance(node, ast.Name):
            yield node.id, node.lineno
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name, node.lineno
        elif isinstance(node, ast.Attribute):
            yield node.attr, node.lineno
        elif isinstance(node, ast.arg):
            yield node.arg, node.lineno
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value, getattr(node, "lineno", 0)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                yield alias.name, getattr(node, "lineno", 0)
                if alias.asname:
                    yield alias.asname, getattr(node, "lineno", 0)


def _outer_functions(tree: ast.AST) -> list[ast.AST]:
    """所有"**不在另一个函数体内**"的函数（含类方法）—— 各自成作用域。

    嵌套函数的 token 归其**外层函数**的作用域（与"函数级"语义一致），
    不重复开作用域，避免同一处命中被报两遍。
    """
    out: list[ast.AST] = []

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.append(child)          # 不深入它的体
            else:
                visit(child)

    visit(tree)
    return out


def _module_scope_nodes(tree: ast.AST) -> Iterator[ast.AST]:
    """模块作用域的节点：整棵树，但**不进入函数体**。

    ★ 这个划分同时修了一个**语义缺陷**（与性能问题同源）：
      初版的"模块作用域"会穿透进**所有**函数体，于是
      `is_freeze_param_reader()` 的排除（`Ch11 §E.1`：参数读口不属决策作用域）
      在**决策目录内的文件上完全失效** —— 排除发生在函数作用域层，
      而模块作用域早已把函数体扫过一遍。
      现在函数体只由它自己的作用域扫，排除才真的生效。
    """
    stack = list(reversed(tree.body))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue                       # 函数体交给它自己的作用域
        for child in reversed(list(ast.iter_child_nodes(node))):
            stack.append(child)


def _scope_in_decision(scope_node: ast.AST, is_module: bool, module_in_decision: bool, root: Path) -> bool:
    """该作用域是否属决策作用域（`Ch2 §B.3` Checker-1 判定）。

    顺序即优先级：**调用链纳入优先** → 再判排除项 → 最后按目录归属。
    """
    if is_module:
        return module_in_decision
    name = getattr(scope_node, "name", "")
    if name and matches_call_chain(name, root):
        return True                        # `classify_*` / `assert_*`：无论置于何处均纳入
    if is_freeze_param_reader(scope_node, root):
        return False                       # 参数读口：不属决策作用域（`Ch11 §E.1`）
    return module_in_decision


def check_L2(root: Path, report: CheckReport) -> None:
    """P-01 / P-02 为**全局**扫描；P-09 通用词**仅在决策函数内**命中才 fail。

    检查器命名空间（`scripts/checks/**`、`tests/**`）**免扫**（`Ch2 §B.1` 通则第 4 点）。
    """
    banned = load_banned_tokens(root)
    l2 = _layer_tokens(banned, "L2")
    # ★ token → entry 建索引：初版对每个出现过的名字线性扫 12 条禁词
    by_token = {t["token"]: t for t in l2}
    scoped = {t["token"]: (t.get("scope") or {}).get("kind") for t in l2}
    # 禁词都是标识符；比最长禁词还长的字符串**不可能**等于任何禁词，
    # 直接跳过。这是**精确**剪枝（不是近似）：docstring 动辄数 KB，
    # 对它们做 strip/lower 纯属浪费。
    max_token_len = max((len(t) for t in by_token), default=0)
    py_files = walk_files(root, "scripts", (".py",)) + walk_files(root, "tests", (".py",))
    report.scanned["l2_py_files"] = len(py_files)
    report.scanned["l2_token_count"] = len(l2)

    seen: set[tuple[str, str, int]] = set()
    for path in py_files:
        relpath = rel(path, root)
        if is_checker_namespace(relpath, root):
            continue                                   # ★ 免扫
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            report.violations.append(
                Violation("L2-parse", f"Python 语法错误: {exc}", relpath, exc.lineno or 0)
            )
            continue

        module_in_decision = is_decision_scope_module(relpath, root)
        scopes: list[tuple[ast.AST, bool]] = [(tree, True)]
        scopes += [(fn, False) for fn in _outer_functions(tree)]

        for scope_node, is_module in scopes:
            nodes = _module_scope_nodes(tree) if is_module else ast.walk(scope_node)
            in_decision = _scope_in_decision(scope_node, is_module, module_in_decision, root)
            for raw, lineno in _iter_tokens(nodes):
                if len(raw) > max_token_len:
                    continue                   # 精确剪枝：不可能等于任何禁词
                entry = by_token.get(_normalize(raw))
                if entry is None:
                    continue
                if scoped[entry["token"]] == "decision_scope_only" and not in_decision:
                    continue                   # P-09：非决策函数内不触发
                if raw in _legit_homonyms(entry):
                    continue                   # 合法同名词（如 position_listed）不误报
                key = (entry["rule"], relpath, lineno)
                if key in seen:                # 去重：嵌套/多作用域可能覆盖同一行
                    continue
                seen.add(key)
                report.violations.append(
                    Violation(
                        entry["rule"],
                        f"命中禁词 {entry['token']!r}"
                        + ("" if in_decision else "（全局作用域）"),
                        relpath,
                        lineno,
                    )
                )


def _legit_homonyms(entry: dict[str, Any]) -> set[str]:
    return set((entry.get("scope") or {}).get("legit_homonyms") or [])


# ───────────────────────── L3：配置扫描（P-01 / P-02） ─────────────────────────

def _flatten_mapping(node: Any, prefix: str = "") -> Iterator[tuple[str, Any, str]]:
    """展开嵌套键 → (key, value, dotted_path)。"""
    if isinstance(node, dict):
        for key, val in node.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield str(key), val, path
            yield from _flatten_mapping(val, path)
    elif isinstance(node, list):
        for i, val in enumerate(node):
            yield from _flatten_mapping(val, f"{prefix}[{i}]")


def check_L3(root: Path, report: CheckReport) -> None:
    """扫描 `rules/**` 与 `registry/**` 的 `*.yaml|*.yml|*.json` **键名 / 标量值**。

    `Ch2 §B.4` 明确把第八/十/十一章**新引入的配置**一并纳入被检目标。
    """
    import yaml

    banned = load_banned_tokens(root)
    l3_tokens = {t["token"] for t in _layer_tokens(banned, "L3")}
    files: list[Path] = []
    for sub in CONFIG_SCAN_TARGETS:
        files += walk_files(root, sub, (".yaml", ".yml", ".json"))
    report.scanned["l3_config_files"] = len(files)
    report.scanned["l3_token_count"] = len(l3_tokens)
    report.scanned["l3_self_exempt"] = len(L3_SELF_EXEMPT)

    for path in files:
        relpath = rel(path, root)
        if relpath.replace("\\", "/") in L3_SELF_EXEMPT:
            report.notes.append(f"L3 自命中豁免（禁词唯一真源）: {relpath}")
            continue
        try:
            if path.suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:                       # 解析失败 → 响亮失败（不静默跳过）
            report.violations.append(Violation("L3-parse", f"配置解析失败: {exc}", relpath))
            continue
        if data is None:
            continue
        for key, val, dotted in _flatten_mapping(data):
            if _normalize(key) in l3_tokens:
                report.violations.append(
                    Violation("P-01/P-02", f"配置键命中禁词: {dotted}", relpath)
                )
            elif isinstance(val, str) and _normalize(val) in l3_tokens:
                report.violations.append(
                    Violation("P-01/P-02", f"配置值命中禁词: {dotted} = {val!r}", relpath)
                )


# ───────────────────────── L4：决策门输入结构断言（P-06） ─────────────────────────

def check_L4(root: Path, report: CheckReport, *, require: bool = False) -> None:
    """对 gate 的输入 dataclass / 签名做字段集合断言（`Ch2 §B.3` Checker-3）。

    ⚠️ 阶段① 尚无 `scripts/decision/gate.py`（`Ch7 §D.1` 于阶段③ 交付）。
    缺被检对象时**显式记 note**，不冒充"已通过结构断言"。
    加 `--require-l4` 时缺对象 → **fail**（供阶段③ 阶段门使用）。
    """
    from scripts.checks.assert_gate_input import (
        NO_GATE_NOTE,
        assert_gate_inputs_in_tree,
    )

    candidates = [
        p for p in walk_files(root, "scripts/decision", (".py",)) if p.name != "__init__.py"
    ]
    report.scanned["l4_gate_files"] = len(candidates)
    if not candidates:
        msg = "L4_SKIPPED_NO_GATE_MODULE（`Ch7 §D.1` gate 于阶段③ 交付）"
        if require:
            report.violations.append(Violation("P-06", msg + "；--require-l4 要求必须存在", "scripts/decision"))
        else:
            report.notes.append(msg)
        return
    any_gate = False
    for path in candidates:
        v, found = assert_gate_inputs_in_tree(path, root, rel(path, root))
        report.violations.extend(v)
        any_gate = any_gate or found
    report.scanned["l4_gate_objects_declared"] = int(any_gate)
    if not any_gate:
        if require:
            report.violations.append(Violation("P-06", NO_GATE_NOTE + "；--require-l4 要求必须存在", "scripts/decision"))
        else:
            report.notes.append(NO_GATE_NOTE)


# ───────────────────────── L5：展示层渲染规则检查（P-10） ─────────────────────────

def check_L5(root: Path, report: CheckReport, *, require: bool = False) -> None:
    """渲染配置 / 组件排序·颜色·折叠策略断言（`Ch2 §B.3` Checker-5 / `Ch3 §D.1`）。

    ⚠️ 阶段① 尚无 `views/**` 渲染配置（`Ch8 §B` 三入口于阶段④ 交付）。
    缺被检对象时**显式记 note**，不冒充"已通过展示层中立检查"。
    """
    from scripts.views.neutrality_check import check_view_config_file

    view_dir = root / "views"
    configs = walk_files(root, "views", (".yaml", ".yml", ".json"))
    report.scanned["l5_view_configs"] = len(configs)
    if not configs:
        msg = "L5_SKIPPED_NO_VIEW_CONFIG（`views/**` 三入口于阶段④ 交付）"
        if require:
            report.violations.append(Violation("P-10", msg + "；--require-l5 要求必须存在", "views"))
        else:
            report.notes.append(msg)
        return
    for path in configs:
        report.violations.extend(check_view_config_file(path, root))


# ───────────────────────── 主流程 ─────────────────────────

TIMING_LAYERS = {
    "pre_commit": ("L1", "L2", "L3", "L4", "L5"),
    "ci": ("L1", "L2", "L3", "L4", "L5"),
    "daily_pre_publish": ("L4", "L5"),
    "nightly": ("L1", "L2", "L3", "L4", "L5"),
}


def run(root: Path, timing: str = "ci", *, require_l4: bool = False, require_l5: bool = False) -> CheckReport:
    if timing not in TIMING_LAYERS:
        raise ValueError(f"未知 timing: {timing!r}；合法值 {sorted(TIMING_LAYERS)}")
    report = CheckReport(checker="conflict_scan")
    report.notes.append(f"timing={timing}；layers={list(TIMING_LAYERS[timing])}")
    layers = TIMING_LAYERS[timing]
    if "L1" in layers:
        check_L1(root, report)
    if "L2" in layers:
        check_L2(root, report)
    if "L3" in layers:
        check_L3(root, report)
    if "L4" in layers:
        check_L4(root, report, require=require_l4)
    if "L5" in layers:
        check_L5(root, report, require=require_l5)
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="conflict_scan.py", description="L1–L5 聚合门禁（命中即 fail）")
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--timing", default="ci", choices=sorted(TIMING_LAYERS))
    parser.add_argument("--require-l4", action="store_true", help="阶段③：gate 模块必须存在")
    parser.add_argument("--require-l5", action="store_true", help="阶段④：views 配置必须存在")
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.code_root) if args.code_root else _ROOT
    if not root.exists():
        print(f"[INPUT-ERROR] code_root 不存在: {root}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    try:
        report = run(root, args.timing, require_l4=args.require_l4, require_l5=args.require_l5)
    except (FileNotFoundError, ValueError, KeyError, OSError) as exc:
        print(f"[INPUT-ERROR] conflict_scan: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    print(f"== conflict_scan.py（timing={args.timing}）==")
    for k, v in sorted(report.scanned.items()):
        print(f"  scanned {k}: {v}")
    for n in report.notes:
        print(f"  note: {n}")
    if report.passed:
        print("RESULT: PASS（0 violations）")
        if not args.no_report:
            print(f"  report: {write_report(root, report)}")
        return EXIT_OK
    for v in report.violations:
        print(f"  {v.render()}")
    print(f"RESULT: FAIL（{len(report.violations)} violations）")
    if not args.no_report:
        print(f"  report: {write_report(root, report)}")
    return EXIT_VIOLATION


if __name__ == "__main__":
    sys.exit(main())
