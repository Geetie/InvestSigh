"""注入防护 · 防御性降级与落盘不可变（批次 4 独立审计 `A-4` 的机器绑定）。

背景：第二轮独立审计 `A-4` 实测 —— `D-2`（异常逃逸 → 显式降级）与 `D-6`（`raw/` 同名不同内容
静默覆盖）的修复在 `tests/` 里**命中数为 0**（`SOURCE_MISSING` / `MISSING_PAYLOAD_FIELDS` /
`_content_addressed_sibling` 全无覆盖）。按本项目铁律「**没有机器绑定的规范等于不存在**」，
此处把这几条修复钉成回归 —— 后续任何重构删掉这些分支，这些用例都会红。

覆盖：
  1. `SOURCE_MISSING`：输入源缺失 → `blocked` + note，**不抛**异常；
  2. `MISSING_PAYLOAD_FIELDS`：`kind="data"` 缺必需字段 → `blocked` + note，**不抛** `KeyError`；
  3. `raw/` 同名不同内容 → 落两个不同路径、既有内容原样保留；同内容再写 → 幂等（同路径）；
  4. `A-2` 读侧路径穿越 → `blocked`，且 `raw/` 下无 `scope*` 产物、无新增 claim；
  5. `A-1` 读侧指向**目录** → `blocked`（`SOURCE_UNREADABLE`），**不抛** `IsADirectoryError`。

★ 断言取**真实落库事实 / 状态**，不取实现细节；
★ 走**真实执行器**（`scripts.guard.executor`），不替换决策函数、不断言伪造返回值。
"""

from __future__ import annotations

import itertools
from datetime import datetime, timezone
from pathlib import Path

_CLAIMS = "claims"

_SEQ_COUNTER = itertools.count(1)
"""逐调用递增的 `recorded_seq` 来源（执行器要求 system_time 三元组显式传入）。"""


def _now() -> datetime:
    """本次处理时刻（UTC）—— 满足执行器的 system_time 必填契约（`Ch9 §2.2`）。"""
    return datetime.now(timezone.utc)


def _count_claims(root: Path) -> int:
    """数 `facts/claims.jsonl` 有效行数（真实落库事实）。"""
    path = root / "facts" / f"{_CLAIMS}.jsonl"
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _process_raw_file(root: Path, relpath: str, **overrides):
    """走**真实入口** `process_raw_file`；system_time 三元组显式传入（执行器必填）。"""
    from scripts.guard.executor import process_raw_file
    from schema.models import ClaimForm, ClaimNature, SourceTier

    kwargs = dict(
        source_id="src-defensive",
        claim_nature=ClaimNature.interpretation,
        claim_form=ClaimForm.opinion,
        tier=SourceTier.secondary_tertiary,
        first_seen_at=_now(),
        analyzed_at=_now(),
        recorded_seq=next(_SEQ_COUNTER),
    )
    kwargs.update(overrides)
    return process_raw_file(root, relpath, **kwargs)


# ═════════════ D-2：缺输入源 → 显式降级（blocked/SOURCE_MISSING），不抛异常 ═════════════

def test_missing_source_is_blocked_not_raised(code_root: Path) -> None:
    """`raw/` 下无该文件 → `blocked` + note 含 `SOURCE_MISSING`，**不得**抛异常。"""
    from scripts.guard.executor import NOTE_SOURCE_MISSING

    before = _count_claims(code_root)
    result = _process_raw_file(code_root, "raw/__missing__.txt")
    assert result.status == "blocked", (
        f"缺输入源应显式降级为 blocked：status={result.status!r} note={result.note!r}"
    )
    assert NOTE_SOURCE_MISSING in result.note, f"note 应含来源缺失标记：{result.note!r}"
    assert result.claim_id is None, "缺输入源不得冒充成功落库"
    assert _count_claims(code_root) == before, "缺输入源不得新增 claim"


# ═════════════ D-2：kind="data" 缺必需字段 → blocked/MISSING_PAYLOAD_FIELDS，不抛 KeyError ═════════════

def test_data_request_missing_fields_is_blocked_not_keyerror(code_root: Path) -> None:
    """`kind="data"` 缺必需字段 → `blocked` + note 含 `MISSING_PAYLOAD_FIELDS`，**不得**抛 `KeyError`。"""
    from scripts.guard.executor import NOTE_MISSING_PAYLOAD_FIELDS, handle_external_request
    from scripts.guard.toolwatch import ToolCallLedger

    before = _count_claims(code_root)
    result = handle_external_request(
        code_root,
        kind="data",
        payload={"text": "x"},
        ledger=ToolCallLedger(),
    )
    assert result.status == "blocked", (
        f"缺必需字段应显式降级：status={result.status!r} note={result.note!r}"
    )
    assert NOTE_MISSING_PAYLOAD_FIELDS in result.note, f"note 应含缺字段标记：{result.note!r}"
    assert result.claim_id is None
    assert _count_claims(code_root) == before


# ═════════════ D-6：raw/ 同名不同内容 → 永不覆盖；同内容 → 幂等 ═════════════

def test_store_raw_same_name_different_content_never_overwrites(code_root: Path) -> None:
    """同名不同内容 → **两个不同路径**、**先写的原件原样保留**；同内容再写 → 幂等（同路径）。"""
    from scripts.guard.rawsink import store_raw

    first = store_raw(code_root, "note.txt", "版本A")
    assert first.read_text(encoding="utf-8") == "版本A"

    second = store_raw(code_root, "note.txt", "版本B")
    assert second != first, "同名不同内容必须落不同路径（不得覆盖既有原始物）"
    assert first.read_text(encoding="utf-8") == "版本A", "先写的原件必须原样保留（未被覆盖）"
    assert second.read_text(encoding="utf-8") == "版本B"

    # 同内容再写 → 幂等：返回同一路径，不新增副本
    assert store_raw(code_root, "note.txt", "版本B") == second
    assert store_raw(code_root, "note.txt", "版本A") == first

    raw_files = sorted(p.name for p in (code_root / "raw").glob("note*.txt"))
    assert len(raw_files) == 2, f"应恰有两份不同内容的原始物，实得 {raw_files}"


# ═════════════ A-2：读侧路径穿越 → blocked，且无 raw/ 产物、无新增 claim ═════════════

def test_read_side_traversal_is_blocked(code_root: Path) -> None:
    """`raw/../rules/scope.yaml` → 必须被拦（`blocked`），**不得**把内部文件当外部文本摄入。

    断言三件事：① 状态 `blocked`；② `raw/` 下**没有**生成 `scope*` 文件；
    ③ **没有**新增 claim（内部文件未被主张化）。
    """
    from scripts.guard.executor import NOTE_RAW_PATH_REJECTED

    before = _count_claims(code_root)
    result = _process_raw_file(code_root, "raw/../rules/scope.yaml")
    assert result.status == "blocked", (
        f"读侧路径穿越必须被拦：status={result.status!r} note={result.note!r}"
    )
    assert NOTE_RAW_PATH_REJECTED in result.note, f"note 应含路径拒绝标记：{result.note!r}"
    assert not list((code_root / "raw").glob("scope*")), "raw/ 下不得出现 scope* 产物"
    assert _count_claims(code_root) == before, "路径穿越不得新增 claim"


# ═════════════ A-1：读侧指向目录 → blocked/SOURCE_UNREADABLE，不抛 IsADirectoryError ═════════════

def test_read_side_directory_is_blocked_not_isdirectory_error(code_root: Path) -> None:
    """`raw/adir.txt` 是**目录** → `blocked` + note 含 `SOURCE_UNREADABLE`，**不得**抛 `IsADirectoryError`。"""
    from scripts.guard.executor import NOTE_SOURCE_UNREADABLE

    (code_root / "raw" / "adir.txt").mkdir(parents=True, exist_ok=True)
    before = _count_claims(code_root)
    result = _process_raw_file(code_root, "raw/adir.txt")
    assert result.status == "blocked", (
        f"目录路径应显式降级为 blocked：status={result.status!r} note={result.note!r}"
    )
    assert NOTE_SOURCE_UNREADABLE in result.note, f"note 应含不可读标记：{result.note!r}"
    assert result.claim_id is None
    assert _count_claims(code_root) == before
