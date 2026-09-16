"""`tests/pricelayer/` 夹具：轻量临时工程根 + 子进程跑**真 CLI**（退出码即判据）。

设计取舍（对齐 `tests/conftest.py` 两条原则 + `tests/compute/conftest.py` 的轻量取舍）：

1. **真代码 + 污染数据**：跑的永远是仓库里的真脚本（`scripts/pricelayer/**`），
   只把 `code_root` 指向 `tests/.work/pricelayer/` 下的**轻量副本**
   （只建 `facts/ derived/ rules/ registry/ index/ reports/`）。
2. **子进程级断言**：本卡 DoD 要求"每个守卫**注入违例 → exit 非零**"，
   故关键路径用 `subprocess` 跑**真进程**断言**进程退出码**，而不是"函数返回了违例列表"。
3. **夹具可写**：`rules/` 在副本里是**可写的候选 YAML**（真 `rules/**` 是 0444 + SHA256 锁，
   任何流都不得写；测试自备候选是任务卡明令的做法）。
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import pytest

SYSTEM_ROOT = Path(__file__).resolve().parents[2]      # .../InvestSigh/system
WORK_DIR = SYSTEM_ROOT / "tests" / ".work" / "pricelayer"


def make_minimal_root() -> Path:
    """建一个只含价格层所需目录的轻量工程根（不复制整棵树）。"""
    root = WORK_DIR / f"{uuid.uuid4().hex[:8]}" / "system"
    for sub in ("facts", "derived", "rules", "registry", "index", "reports"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture()
def scratch() -> Iterable[Path]:
    """轻量工程根；测试内可随写随改（`rules/` 与 `facts/` 在这里都是可写副本）。"""
    root = make_minimal_root()
    try:
        yield root
    finally:
        import shutil

        shutil.rmtree(root.parent, ignore_errors=True)


@pytest.fixture()
def write_jsonl() -> Callable[[Path, str, list[Mapping[str, Any]]], Path]:
    """写 `facts/<stem>.jsonl`（`derived/` 用 `write_derived_jsonl`）。"""

    def _write(root: Path, stem: str, rows: list[Mapping[str, Any]]) -> Path:
        path = root / "facts" / f"{stem}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = "\n".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) for row in rows)
        path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")
        return path

    return _write


@pytest.fixture()
def write_derived_jsonl() -> Callable[[Path, list[Mapping[str, Any]]], Path]:
    """写 `derived/derived_values.jsonl`（`DerivedValue` 的真源**不在** `facts/`）。"""

    def _write(root: Path, rows: list[Mapping[str, Any]]) -> Path:
        path = root / "derived" / "derived_values.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = "\n".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) for row in rows)
        path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")
        return path

    return _write


@pytest.fixture()
def write_rules() -> Callable[[Path, str, Mapping[str, Any]], Path]:
    """在夹具副本里自备候选 `rules/<name>.yaml`（真 `rules/**` 一律不写）。"""
    import yaml

    def _write(root: Path, name: str, content: Mapping[str, Any]) -> Path:
        path = root / "rules" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(dict(content), allow_unicode=True), encoding="utf-8")
        return path

    return _write


REAL_RULES_DIR = SYSTEM_ROOT / "rules"
"""真 `rules/`（0444 + SHA256 锁，**只读**）。"""


def copy_real_rules(root: Path, *names: str) -> list[Path]:
    """把真 `rules/<name>` **原样复制**进夹具副本（**只读真文件**，不写它们）。

    ★ 为什么必须有：`G-43`/`G-45` 的病灶是"夹具形状 = 生产代码写不出来的形状"。
      只用手写 YAML 夹具，会让"代码读一个真文件里不存在的键"这种缺陷在夹具上**永远绿**。
      故凡涉及规则解析的用例，一律优先用**真文件内容**。
    """
    import shutil

    out: list[Path] = []
    target_dir = root / "rules"
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        src = REAL_RULES_DIR / name
        if not src.exists():
            raise FileNotFoundError(f"真规则文件不存在: {src}")
        dst = target_dir / name
        shutil.copyfile(src, dst)
        out.append(dst)
    return out


@pytest.fixture()
def real_rules() -> Callable[[Path, str], list[Path]]:
    """把**真** `rules/<name>.yaml` 复制进夹具副本（真文件只读；副本可写）。"""

    def _copy(root: Path, *names: str) -> list[Path]:
        return copy_real_rules(root, *(names or ("scenario.yaml",)))

    return _copy



@pytest.fixture()
def run_script() -> Callable[..., subprocess.CompletedProcess]:
    """跑仓库里的**真脚本**（真子进程）—— 断言退出码用。"""

    def _run(
        script_rel: str,
        root: Path,
        *args: str,
        timeout: float = 90.0,
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
