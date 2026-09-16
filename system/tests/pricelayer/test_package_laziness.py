"""包级惰性导入单测（`CONVENTIONS.md §三 P-03` / PEP 562）。

★ `P-03`：包 `__init__` **惰性导入**；守卫 / 轻量模块**不得**在模块级急切导入 pydantic
  （pydantic ≈0.3s/次，会拖慢每次调用）。本测试用**真子进程**证明：
  `import scripts.pricelayer` **不会**把 pydantic 带进 `sys.modules`。

★ 本包带 5 个守卫 CLI（`pre-commit` 候选），故这条不是形式要求 ——
  模块级急切导入会让每个守卫白付 ≈0.3s（`P-05`：新守卫单次耗时 < 0.5s）。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SYSTEM_ROOT = Path(__file__).resolve().parents[2]

import scripts.pricelayer as pricelayer  # noqa: E402


def test_getattr_imports_submodule_on_demand() -> None:
    assert pricelayer.solver.__name__ == "scripts.pricelayer.solver"
    assert pricelayer.order_guard.__name__ == "scripts.pricelayer.order_guard"


def test_getattr_unknown_attribute_raises() -> None:
    with pytest.raises(AttributeError):
        _ = pricelayer.does_not_exist


def test_dir_lists_submodules() -> None:
    names = dir(pricelayer)
    for expected in (
        "solver",
        "valuation",
        "order_guard",
        "scenario_guard",
        "history_guard",
        "daily_explain",
        "step",
    ):
        assert expected in names


def test_exception_family_is_exported() -> None:
    """拒绝类异常是包级公开面（`G-06`：本层自有异常集中一处，不散落各模块）。"""
    for name in (
        "PriceLayerError",
        "ScenarioMismatch",
        "ScenarioMethodPending",
        "ProbabilityWithoutBasis",
        "HistoricalExtrapolation",
        "MoatPriceContamination",
        "QuoteCaliberViolation",
        "SingleSolutionError",
        "order_violation",
    ):
        assert name in pricelayer.__all__, name


def test_package_import_does_not_eagerly_import_pydantic() -> None:
    """真子进程：`import scripts.pricelayer` 后 `pydantic` **不在** `sys.modules`。"""
    env = {
        **os.environ,
        "CODEBUDDY_SAFE_DELETE_SANDBOX": "0",
        "CODEBUDDY_BROKERED_FS_HOOK_ENABLED": "0",
    }
    code = "import scripts.pricelayer, sys; print('pydantic' in sys.modules)"
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(SYSTEM_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "False", "包级 __init__ 急切导入了 pydantic（违反 P-03）"
