"""`tests/decision/` 夹具：轻量临时工程根 + 真子进程跑 CLI。

设计取舍（对齐 `tests/conftest.py` 与 `tests/compute/conftest.py` 的两条原则）：

1. **真代码 + 受控输入**：测试跑的永远是**仓库里的真实模块**（`scripts/decision/**`），
   只把 `code_root` 指向 `tests/.work/decision/` 下的**轻量副本**（只建
   `facts/ index/ rules/ derived/ registry/`），不复制整个 `system/`。
2. **真 `DerivedValue`，不是裸数字**：预测底稿一律经 `scripts.compute.contract.make_derived`
   构造（见 `decision_builders.py`），从而测的是"真的能追到底稿"（`Ch7 §D.2`）。

★ 临时目录一律落在**工作区内**的 `tests/.work/decision/`，用完即删（`tmp_path` 在沙箱下
  会因 broker 走 IPC 抛 `PermissionError`，见 `tests/conftest.py` 的说明）。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Callable

import pytest

SYSTEM_ROOT = Path(__file__).resolve().parents[2]      # .../InvestSigh/system
if str(SYSTEM_ROOT) not in sys.path:
    sys.path.insert(0, str(SYSTEM_ROOT))

WORK_DIR = SYSTEM_ROOT / "tests" / ".work" / "decision"


def _make_scratch_root() -> Path:
    """建一个只含决策层所需目录的轻量工程根（不复制整棵树）。"""
    root = WORK_DIR / f"{uuid.uuid4().hex[:8]}" / "system"
    for sub in ("facts", "index", "rules", "derived", "registry"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture()
def scratch() -> Path:
    """轻量工程根；测试内可随写随改（落 `facts/recommendations.jsonl` 用）。"""
    root = _make_scratch_root()
    try:
        yield root
    finally:
        shutil.rmtree(root.parent, ignore_errors=True)


@pytest.fixture()
def cli() -> Callable[..., subprocess.CompletedProcess]:
    """跑真实脚本的**真子进程**（断言进程退出码用）。"""

    def _run(
        script_rel: str, root: Path, *args: str, timeout: float = 60.0
    ) -> subprocess.CompletedProcess:
        script = SYSTEM_ROOT / script_rel
        if not script.exists():
            raise FileNotFoundError(f"脚本不存在: {script}")
        return subprocess.run(
            [sys.executable, str(script), str(root), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    return _run
