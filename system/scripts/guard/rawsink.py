"""`rawsink.py` —— 外部文本落 `raw/` 与解码边界（`Ch9 §3.4.6` 措施①·载体侧）。

把"外部文本"物理隔离进 `raw/`：外部文本**只**进 `raw/`（不进 `rules/`），
越界名（含路径分隔符 / `..`）**响亮拒绝**，非法编码**严格拒绝**（不做静默替换）。

★ 契约对齐设计 §2.1：失败语义**均不吞、不置 null**（AC-05）。
★ 不急切导入 pydantic、无全局副作用（规避 `D-21` / `D-23`）。
"""

from __future__ import annotations

import hashlib
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


def _content_addressed_sibling(target: Path, text: str) -> Path:
    """为"同名但内容不同"的原始物计算**内容哈希后缀**落点（`<stem>.<sha256前8位><suffix>`）。

    - 该哈希路径不存在，或已存在但内容一致 → 直接返回（幂等）。
    - 哈希前缀碰撞（极不可能）→ 逐步加长前缀，直至得到"不存在或内容一致"的路径。
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    for length in (8, 16, 32, 64):
        candidate = target.with_name(f"{target.stem}.{digest[:length]}{target.suffix}")
        if not candidate.exists() or read_external_text(candidate) == text:
            return candidate
    raise ValueError(f"同名不同内容且内容哈希前缀重复，无法落成新文件: {target}")


def store_raw(root: Path, name: str, text: str, *, dedup: bool = True) -> Path:
    """把外部文本**只**写入 `root/"raw"/<name>`（去路径穿越）；返回**实际**落盘路径。

    - `name` 含路径分隔符 … 允许法相对名；含 `..` / 绝对路径 → `ValueError`（越界，不静默改写）。
    - **永不覆盖**既有原始物：目标已存在且内容一致 → 幂等返回原路径（不重复写）；
      目标已存在但**内容不同** → 落成**内容哈希后缀**的新文件 `<stem>.<sha256前8位><suffix>`，
      并返回该实际路径（既有证据不被静默替换）。
    - 返回路径**必在 `raw/` 内**（断言落点相对 `raw/`，越界即抛）。
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

    if target.exists():
        if dedup and read_external_text(target) == text:
            return target  # 内容一致 → 幂等，不重复写
        # 同名不同内容 → 内容哈希后缀新文件（永不覆盖既有原始物）
        target = _content_addressed_sibling(target, text)

    # 落点再次确认在 raw/ 内（哈希后缀不改变父目录，此处为结构性复核）
    resolved_target_parent = target.parent.resolve()
    if (
        raw_dir.resolve() not in resolved_target_parent.parents
        and resolved_target_parent != raw_dir.resolve()
    ):
        raise ValueError(f"外部文本落点越出 raw/：{target}")

    if dedup and target.exists() and read_external_text(target) == text:
        return target  # 哈希路径已存在且内容一致 → 幂等

    target.write_text(text, encoding="utf-8")
    return target
