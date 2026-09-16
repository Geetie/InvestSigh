"""包级惰性导入单测（`CONVENTIONS.md P-03` / PEP 562）。

★ `P-03`：包 `__init__` **惰性导入**；守卫/轻量模块**不得**在模块级急切导入 pydantic
  （pydantic ≈0.3s/次，会拖慢每次调用）。本测试用**真子进程**证明：
  `import scripts.compute` **不会**把 pydantic 带进 `sys.modules`。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SYSTEM_ROOT = Path(__file__).resolve().parents[2]

import scripts.compute as compute  # noqa: E402


def test_getattr_imports_submodule_on_demand() -> None:
    assert compute.core.__name__ == "scripts.compute.core"
    assert compute.returns.__name__ == "scripts.compute.returns"


def test_getattr_unknown_attribute_raises() -> None:
    with pytest.raises(AttributeError):
        _ = compute.does_not_exist


def test_dir_lists_submodules() -> None:
    names = dir(compute)
    for expected in ("contract", "core", "growth", "margin", "returns", "fx", "shares", "valuation", "store", "driver", "step"):
        assert expected in names


def test_package_import_does_not_eagerly_import_pydantic() -> None:
    """真子进程：`import scripts.compute` 后 `pydantic` **不在** `sys.modules`。"""
    env = {
        **os.environ,
        "CODEBUDDY_SAFE_DELETE_SANDBOX": "0",
        "CODEBUDDY_BROKERED_FS_HOOK_ENABLED": "0",
    }
    code = "import scripts.compute, sys; print('pydantic' in sys.modules)"
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
