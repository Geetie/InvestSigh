"""作用域匹配器单测（`Ch2 §B.1 通则` / `§B.3` Checker-1）。

之所以**单独测匹配器本身**而不是只测"注入后 exit 1"：
本次实测发现 `is_decision_scope_module()` 因 glob 未剥离而**恒返回 False** ——
`decision_scope.include_paths` 的两条 `**` 路径整体失效，
P-09 在 `scripts/decision/**`、`scripts/graph/**` 上什么也没拦，
而**注入测试之外的一切都是绿的**。匹配器是作用域的根，必须被直测。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts._common import (
    is_checker_namespace,
    is_decision_scope_module,
    is_freeze_param_reader,
    matches_call_chain,
    strip_system_prefix,
)


@pytest.fixture()
def root() -> Path:
    return Path(__file__).resolve().parents[2]


# ───────────────────────── glob → 前缀 ─────────────────────────

@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        ("system/scripts/decision/**", "scripts/decision"),
        ("system/scripts/graph/**", "scripts/graph"),
        ("system/scripts/checks/**", "scripts/checks"),
        ("system/tests/**", "tests"),
        ("scripts/decision/", "scripts/decision"),
    ],
)
def test_strip_system_prefix(pattern: str, expected: str) -> None:
    assert strip_system_prefix(pattern) == expected


# ───────────────────────── 决策作用域 ─────────────────────────

@pytest.mark.parametrize(
    "relpath",
    [
        "scripts/decision/gate.py",
        "scripts/decision/nested/deep.py",
        "scripts/graph/propagate.py",
        "scripts/compute/notification_sort.py",     # include_modules 命中
    ],
)
def test_decision_scope_paths_are_inside(relpath: str, root: Path) -> None:
    assert is_decision_scope_module(relpath, root), f"{relpath} 应属决策作用域"


@pytest.mark.parametrize(
    "relpath",
    [
        "scripts/compute/aggregate.py",
        "scripts/ingest/seed_industry_nodes.py",
        "schema/models.py",
        "scripts/checks/conflict_scan.py",         # 检查器：免扫且非决策域
    ],
)
def test_non_decision_scope_paths_are_outside(relpath: str, root: Path) -> None:
    assert not is_decision_scope_module(relpath, root), f"{relpath} 不应属决策作用域"


def test_include_call_chain_matches_classify_and_assert(root: Path) -> None:
    assert matches_call_chain("classify_opportunity", root)
    assert matches_call_chain("assert_no_composite_score", root)
    assert not matches_call_chain("compute_return", root)


# ───────────────────────── 检查器命名空间免扫 ─────────────────────────

@pytest.mark.parametrize(
    "relpath",
    ["scripts/checks/nothing.py", "tests/unit/test_x.py", "scripts/checks/nested/deep.py"],
)
def test_checker_namespace_is_exempt(relpath: str, root: Path) -> None:
    assert is_checker_namespace(relpath, root)


@pytest.mark.parametrize(
    "relpath",
    ["scripts/compute/aggregate.py", "scripts/checksum/x.py", "schema/models.py"],
)
def test_non_checker_namespace_is_not_exempt(relpath: str, root: Path) -> None:
    assert not is_checker_namespace(relpath, root)


# ───────────────────────── freeze_param 读口排除 ─────────────────────────

def test_freeze_param_reader_is_excluded_but_call_chain_wins(root: Path) -> None:
    """`Ch11 §E.1` 排除项 vs `Ch2 §B.3` 调用链纳入：**调用链优先**。"""
    import ast

    plain_reader = ast.parse("def load_value():\n    return get_param('p03')\n").body[0]
    assert is_freeze_param_reader(plain_reader, root) is True

    # classify_* 即使读参数，也仍算决策作用域（调用链纳入优先）
    classifier = ast.parse("def classify_opportunity():\n    return get_param('p03')\n").body[0]
    assert is_freeze_param_reader(classifier, root) is False

    unrelated = ast.parse("def compute(x):\n    return x + 1\n").body[0]
    assert is_freeze_param_reader(unrelated, root) is False
