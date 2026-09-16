"""`tests/compute/` 夹具：轻量临时工程根 + 真实基准规则拷贝 + 子进程跑 CLI。

设计取舍（对齐 `tests/conftest.py` 的两条原则）：

1. **真代码 + 污染数据**：测试跑的永远是**仓库里的真实脚本**（`scripts/compute/**`），
   只把 `code_root` 指向 `tests/.work/` 下的**轻量副本**（只建 `derived/ facts/ rules/ index/`），
   不复制整个 `system/` —— 计算层测试不需要夹具携带 130 个文件（省时且避开 broker 累积）。
2. **子进程级断言**：AC-04 要求"注入违例 → **exit 1**（不是 warn）"，故关键路径用
   `subprocess` 跑**真进程**，断言的是**进程退出码**，不是"函数返回了违例列表"。

★ 临时目录一律落在**工作区内**的 `tests/.work/compute/`，用完即删（`tmp_path` 在沙箱下
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
WORK_DIR = SYSTEM_ROOT / "tests" / ".work" / "compute"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
AGIX_PRICES = FIXTURES / "agix_prices.jsonl"
BENCHMARK_RULES = SYSTEM_ROOT / "rules" / "benchmark.yaml"


def _make_minimal_root() -> Path:
    """建一个只含计算层所需目录的轻量工程根（不复制整棵树）。"""
    root = WORK_DIR / f"{uuid.uuid4().hex[:8]}" / "system"
    for sub in ("derived", "facts", "rules", "registry", "index"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture()
def scratch() -> Path:
    """轻量工程根；测试内可随写随改（`rules/` 在这里是可写的副本，便于注入违例）。"""
    root = _make_minimal_root()
    # 拷贝**真实**基准规则（真数据，供基准收益口径路径使用）
    shutil.copyfile(BENCHMARK_RULES, root / "rules" / "benchmark.yaml")
    try:
        yield root
    finally:
        shutil.rmtree(root.parent, ignore_errors=True)


@pytest.fixture()
def cli() -> Callable[..., subprocess.CompletedProcess]:
    """跑真实脚本的**真子进程**（断言退出码用）。"""

    def _run(script_rel: str, root: Path, *args: str, timeout: float = 60.0) -> subprocess.CompletedProcess:
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
