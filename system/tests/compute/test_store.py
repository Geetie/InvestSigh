"""`store` 单测（`Ch9 §3.3.3` `derived/` / `§3.4.2` 追加式不可变 / `§3.5` 阶段④幂等）。

覆盖 AC-02（write-read-reload：写 `derived/` → 删 `index/` → 重建 → 仍在）
＋ `method_version` 变更**必须产生新行**（不得就地覆盖）。
"""

from __future__ import annotations

import shutil
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.compute import store
from scripts.compute.contract import ComputeGap, make_derived
from schema.store import rebuild_index


def _derived(derived_id: str, value: str, method_version: str = "compute-v1"):
    return make_derived(
        derived_id,
        Decimal(value),
        f"formula({derived_id})",
        [f"op({derived_id})"],
        method_version=method_version,
        computed_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )


def test_append_and_read_values(scratch: Path) -> None:
    written = store.append_derived_values(scratch, [_derived("dv-a", "0.1"), _derived("dv-b", "0.2")])
    assert written == 2
    rows = store.read_rows(scratch, store.DERIVED_VALUES_STEM)
    assert {r["derived_id"] for r in rows} == {"dv-a", "dv-b"}
    assert store.current_value(scratch, "dv-a")["value"] == "0.1"


def test_append_is_idempotent_for_same_method_version(scratch: Path) -> None:
    """重跑同日不重复（幂等键 `(derived_id, method_version)`，`Ch9 §3.5` 阶段④）。"""
    assert store.append_derived_values(scratch, [_derived("dv-a", "0.1")]) == 1
    assert store.append_derived_values(scratch, [_derived("dv-a", "0.1")]) == 0
    assert len(store.read_rows(scratch, store.DERIVED_VALUES_STEM)) == 1


def test_method_version_change_creates_new_row_not_overwrite(scratch: Path) -> None:
    """`Ch9 §2.3` / 纪律 4：`method_version` 变更 → **新增行**，旧行保留（不就地覆盖）。"""
    store.append_derived_values(scratch, [_derived("dv-a", "0.1", "compute-v1")])
    store.append_derived_values(scratch, [_derived("dv-a", "0.12", "compute-v2")])
    history = store.history_for(scratch, "dv-a")
    assert len(history) == 2
    assert [h["method_version"] for h in history] == ["compute-v1", "compute-v2"]
    assert store.current_value(scratch, "dv-a")["value"] == "0.12"
    assert store.current_value(scratch, "dv-a", method_version="compute-v1")["value"] == "0.1"


def test_gaps_are_persisted_and_idempotent(scratch: Path) -> None:
    gap = ComputeGap(
        gap_id="dv-gap-x-v1", subject="x", missing=["prices"], reason="缺行情",
        method_version="compute-v1", recorded_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )
    assert store.append_gaps(scratch, [gap]) == 1
    assert store.append_gaps(scratch, [gap]) == 0
    rows = store.read_rows(scratch, store.DERIVED_GAPS_STEM)
    assert rows[0]["missing"] == ["prices"]


def test_write_read_reload_survives_index_deletion(scratch: Path) -> None:
    """AC-02：写 `derived/` → 删 `index/` → `rebuild_index()` → 数据**仍在**。

    `derived/` 是**真源**，`index/` 只是可重建索引（`Ch9 §3.3.2`）。
    """
    store.append_derived_values(scratch, [_derived("dv-a", "0.1")])
    index_dir = scratch / "index"
    shutil.rmtree(index_dir, ignore_errors=True)   # 连 `.locks/` 子目录一并删（真"删索引"）
    rebuild_index(scratch)                       # 从 facts/ 全量重建索引（不碰 derived/）
    assert (scratch / "index" / "facts.sqlite").exists()
    assert store.read_rows(scratch, store.DERIVED_VALUES_STEM), "derived/ 数据不应随索引删除而丢失"


def test_corrupt_line_fails_loudly(scratch: Path) -> None:
    path = store.values_path(scratch)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        store.read_rows(scratch, store.DERIVED_VALUES_STEM)


def test_current_value_missing_returns_none(scratch: Path) -> None:
    """"没算过" → `None`（≠ "算出来是空"；缺口请查 `compute_gaps.jsonl`）。"""
    assert store.current_value(scratch, "dv-never") is None
