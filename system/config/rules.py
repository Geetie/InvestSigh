"""`rules/` 只读读取层。

★ 只读纪律：`rules/` 下所有文件 0444 + SHA256 锁；**模型无写权**（`Ch9 §3.10 J9` / 纪律 10）。

**本模块提供什么、不提供什么**（第二轮独立审计指出此处 docstring 曾与事实脱节）：

| 能力 | 谁在用 |
|---|---|
| `load_yaml` | 全包各检查器（读 `rules/*.yaml`） |
| `sha256_of` | `scripts/checks/rules_lock_guard.py`、`scripts/ops/lock_rules.py` |
| `is_read_only` | `scripts/checks/rules_lock_guard.py`（唯一调用方） |
| `refuse_write` | **暂无调用方** —— 它是留给"将来真要在 `rules/` 下写文件的代码"的
  运行时闸门；**当前真正的强制控制不是它**，而是 ① 文件系统 0444 ② `rules_lock_guard.py`
  在门禁里逐文件校验权限与 SHA256。故本模块**不提供任何写函数**，
  `rules/` 的写权限由操作系统与门禁共同保证，**不靠自觉**。
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import yaml


class RuleFileMissingError(FileNotFoundError):
    """规则文件缺失 —— **响亮失败**，不返回空 dict 兜底。"""


class ReadOnlyRuleViolation(PermissionError):
    """试图写 `rules/` —— 模型对 rules/ 无写权（硬要求）。"""


def code_root() -> Path:
    """代码工程根 = 本文件的上两级（`system/`）。"""
    return Path(__file__).resolve().parents[1]


def rules_dir(root: str | Path | None = None) -> Path:
    return (Path(root) if root else code_root()) / "rules"


def load_yaml(relpath: str, root: str | Path | None = None) -> dict[str, Any]:
    """按**相对 code_root 的路径**读 YAML（如 `rules/freeze.yaml`）。

    缺文件 → `RuleFileMissingError`；内容不是 mapping → `ValueError`。
    **不做任何兜底默认值**。
    """
    base = Path(root) if root else code_root()
    path = (base / relpath).resolve()
    # 目录穿越防护：必须落在 code_root 内
    if base.resolve() not in path.parents and path != base.resolve():
        raise ValueError(f"路径越出 code_root: {relpath}")
    if not path.exists():
        raise RuleFileMissingError(f"规则文件不存在: {path}")
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        raise ValueError(f"规则文件为空: {path}")
    if not isinstance(data, dict):
        raise ValueError(f"规则文件顶层必须是 mapping: {path}")
    return data


def sha256_of(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def is_read_only(path: str | Path) -> bool:
    """检查是否已锁为只读（0444 语义：组/其他不可写，且属主亦不可写）。"""
    mode = os.stat(path).st_mode & 0o777
    return mode == 0o444


def refuse_write(path: str | Path) -> None:
    """守卫函数：任何试图在 `rules/` 下写入的代码路径都应先调用它。"""
    p = Path(path).resolve()
    if rules_dir() in p.parents or (p.parent == rules_dir()):
        raise ReadOnlyRuleViolation(
            f"模型对 rules/ 无写权（Ch9 §3.10 J9 / 纪律 10）：拒绝写入 {p}"
        )
