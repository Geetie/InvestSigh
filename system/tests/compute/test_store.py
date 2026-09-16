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


def test_version_change_creates_new_row_not_overwrite(scratch: Path) -> None:
    """★ C-02：上游重述（同 `derived_id`/`method_version`、**新 `version`**）→ **新增行**，旧行逐字节不变。

    `Ch9 §3.5` 阶段④ 幂等键 = `(company_id, version, method_version)`；缺 `version` 分量会把
    上游重述静默沿用旧值（实测审计复现：重述后 `values_written=0` 且落库值不变）。
    """
    store.append_derived_values(scratch, [_derived("dv-a", "0.3449")], version="v1")
    store.append_derived_values(scratch, [_derived("dv-a", "0.11325")], version="v2")  # 上游重述
    rows = store.read_rows(scratch, store.DERIVED_VALUES_STEM)
    assert len(rows) == 2, "上游重述必须新增行，新旧两行同时存在"
    assert rows[0]["value"] == "0.3449" and rows[0]["version"] == "v1"    # 旧行未变
    assert rows[1]["value"] == "0.11325" and rows[1]["version"] == "v2"   # 新行落库


def test_same_version_rerun_is_idempotent(scratch: Path) -> None:
    """反向对照：**同一** `version` 重跑 → `values_written = 0`（不重复追加）。"""
    assert store.append_derived_values(scratch, [_derived("dv-a", "0.3449")], version="v2") == 1
    assert store.append_derived_values(scratch, [_derived("dv-a", "0.3449")], version="v2") == 0
    assert len(store.read_rows(scratch, store.DERIVED_VALUES_STEM)) == 1


def test_append_derived_value_ids_returns_only_written(scratch: Path) -> None:
    """★ C-03：`append_derived_value_ids` 只回**本次真正写入**的 id（同键重跑 → 空列表）。"""
    first = store.append_derived_value_ids(scratch, [_derived("dv-a", "0.1"), _derived("dv-b", "0.2")])
    assert sorted(first) == ["dv-a", "dv-b"]
    second = store.append_derived_value_ids(scratch, [_derived("dv-a", "0.1"), _derived("dv-b", "0.2")])
    assert second == []


# ═══════════ `append_derived_value_ids_detailed`：写入口如实回传两个互斥集合 ═══════════
#
# 缺陷 `G-44`：`step.py` 的处理器原先只拿得到"写了什么"，拿不到"考察过、但已存在故没写"，
# 于是幂等重跑时 `produced=[]` 且无法说明"我确实考察过了" → `chain_steps` 的适配器
# 把它判成 `incomplete_reason` → `STATUS_GAP` → **整轮 blocked**。
# 本节的断言全部锚在**唯一写入口**的返回值上（`G-06`：判定只有一处）。


def test_detailed_reports_written_on_first_run_and_skipped_on_rerun(scratch: Path) -> None:
    """双跑判别式：首轮 `written` 非空 / `skipped` 空；重跑**反向**（`G-44` 的核心观测）。"""
    values = [_derived("dv-a", "0.1"), _derived("dv-b", "0.2")]
    first = store.append_derived_value_ids_detailed(scratch, values)
    assert sorted(first.written) == ["dv-a", "dv-b"], "首轮应真正写入"
    assert first.skipped == [], "首轮不该有幂等命中（否则本用例失去判别力）"
    assert len(store.read_rows(scratch, store.DERIVED_VALUES_STEM)) == 2

    second = store.append_derived_value_ids_detailed(scratch, values)
    assert second.written == [], "重跑未新写入 → written 必须为空"
    assert sorted(second.skipped) == ["dv-a", "dv-b"], (
        "★ 重跑必须把'考察过、已存在故未写入'的对象如实回报到 skipped —— "
        "缺了它，上层无法区分『空执行』与『幂等命中』（G-44）"
    )
    assert len(store.read_rows(scratch, store.DERIVED_VALUES_STEM)) == 2, "重跑不得新增行"


def test_detailed_written_and_skipped_are_disjoint(scratch: Path) -> None:
    """★ 互斥不变量：`written ∩ skipped = ∅`（同批内既有新键、又有旧键命中）。"""
    store.append_derived_value_ids_detailed(scratch, [_derived("dv-a", "0.1", "compute-v1")])
    # 同批：`dv-a@v2` 是**新键**（写入）；`dv-a@v1` 已存在（命中）→ 以**写入为准**，不得两边都有
    out = store.append_derived_value_ids_detailed(
        scratch, [_derived("dv-a", "0.12", "compute-v2"), _derived("dv-a", "0.1", "compute-v1")]
    )
    assert out.written == ["dv-a"], f"新键应写入：{out}"
    assert out.skipped == [], f"★ dv-a 已写入 ⇒ 不得同时出现在 skipped：{out}"
    assert set(out.written) & set(out.skipped) == set()


def test_detailed_reports_nothing_when_no_candidates(scratch: Path) -> None:
    """★ **反向对照**：上游一件都没得做（`values=[]`）→ 两个集合**都空**。

    这一条是整单的关键：证明"新增 skipped 出口"**没有**把"空执行"守卫洗成恒真 ——
    真的一件都没得做时，上层仍然只能看到 `written=[] skipped=[]` ⇒ 照样判"未完成"。
    """
    out = store.append_derived_value_ids_detailed(scratch, [])
    assert (out.written, out.skipped) == ([], []), f"无候选时不得回报任何命中：{out}"
    assert not (scratch / "derived" / "derived_values.jsonl").exists(), "无候选不得建空文件"


def test_detailed_reports_nothing_when_persist_disabled(scratch: Path) -> None:
    """`skip_existing=False`（纯写入、不做幂等判定）→ `skipped` 恒空（判定根本没做）。"""
    out = store.append_derived_value_ids_detailed(
        scratch, [_derived("dv-a", "0.1")], skip_existing=False
    )
    assert out.written == ["dv-a"] and out.skipped == []


def test_append_outcome_rejects_self_contradiction() -> None:
    """★ G-42 同源：`AppendOutcome` 自己就拒绝"同一 id 两边都有"的自相矛盾输入。"""
    with pytest.raises(ValueError, match="自相矛盾"):
        store.AppendOutcome(written=["dv-a"], skipped=["dv-a"])


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
