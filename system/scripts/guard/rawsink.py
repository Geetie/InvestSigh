"""`rawsink.py` —— 外部文本落 `raw/` 与解码边界（`Ch9 §3.4.6` 措施①·载体侧）。

把"外部文本"物理隔离进 `raw/`：外部文本**只**进 `raw/`（不进 `rules/`），
越界名（含路径分隔符 / `..`）**响亮拒绝**，非法编码**严格拒绝**（不做静默替换）。

★ 契约对齐设计 §2.1：失败语义**均不吞、不置 null**（AC-05）。
★ 不急切导入 pydantic、无全局副作用（规避 `D-21` / `D-23`）。
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "ExternalTextDecodeError",
    "RAW_DIRNAME",
    "decode_external_bytes",
    "read_external_text",
    "store_raw",
]

RAW_DIRNAME = "raw"


class ExternalTextDecodeError(ValueError):
    """外部文本非 UTF-8 / 非法编码 —— 明确拒绝，不做静默替换。"""


def decode_external_bytes(data: bytes) -> str:
    """严格按 UTF-8 解码外部字节。非法 → `ExternalTextDecodeError`。"""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExternalTextDecodeError(
            f"外部文本非 UTF-8（偏移 {exc.start}）：不做静默替换，明确拒绝"
        ) from exc


def read_external_text(path: Path) -> str:
    """读 `raw/` 下单个外部文本文件（严格 UTF-8）。

    - 缺文件 → `FileNotFoundError`（响亮失败，不返回 "" 兜底）。
    - 非 UTF-8 → `ExternalTextDecodeError`。
    - 空文件 → 返回 `""`（**不报错**，交由调用方降级并记 note）。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"外部文本文件不存在: {p}")
    return decode_external_bytes(p.read_bytes())


def _validate_name(name: str) -> str:
    """校验 `raw/` 下的相对名，拒绝路径穿越（越界 → `ValueError`，不静默改写）。"""
    if not name or name.strip() == "":
        raise ValueError("外部文本名不得为空")
    normalized = name.replace("\\", "/")
    parts = [seg for seg in normalized.split("/") if seg != ""]
    if any(seg == ".." for seg in parts):
        raise ValueError(f"外部文本名含路径穿越（..）: {name!r}")
    if Path(normalized).is_absolute() or name.startswith("/"):
        raise ValueError(f"外部文本名不得为绝对路径: {name!r}")
    return "/".join(parts)


def store_raw(root: Path, name: str, text: str, *, dedup: bool = True) -> Path:
    """把外部文本**只**写入 `root/"raw"/<name>`（去路径穿越）；返回落盘路径。

    - `name` 含路径分隔符 … 允许法相对名；含 `..` / 绝对路径 → `ValueError`（越界，不静默改写）。
    - `dedup=True` 且同名文件内容一致 → 不重复写（幂等，避免刷屏）。
    - 返回路径**必在 `raw/` 内**（断言 `raw_dir in parents`，越界即抛）。
    """
    safe_name = _validate_name(name)
    raw_dir = Path(root) / RAW_DIRNAME
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / safe_name
    # 目标必须落在 raw/ 内（结构性保证，不靠调用方自觉）
    resolved_parent = target.parent.resolve()
    if raw_dir.resolve() not in resolved_parent.parents and resolved_parent != raw_dir.resolve():
        raise ValueError(f"外部文本落点越出 raw/：{target}")
    target.parent.mkdir(parents=True, exist_ok=True)

    if dedup and target.exists() and read_external_text(target) == text:
        return target  # 内容一致 → 幂等，不重复写

    target.write_text(text, encoding="utf-8")
    return target
