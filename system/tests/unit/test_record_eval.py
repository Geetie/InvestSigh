"""`tests/unit/test_record_eval.py` —— 三层复盘记录器契约（`Ch10 §C.4`）。

覆盖 DoD：

| 用例 | 对应 AC |
|---|---|
| 正路 + 持久化（write-read-reload）+ 复用字段落位 | AC-01 / AC-02 / AC-08 |
| 非法 `eval_layer` / 非法 `error_axis` 被拒（且不留半截数据） | AC-04 |
| `assert_no_composite_score` 拦下"带综合评分/置信度"的对象（**正向**） | AC-04 |
| `assert_no_composite_score` **不**误伤合法对象（**反向对照**，`G-05`） | AC-04 |
| 空 axis 合法 / 一条错误跨多方向合法 / 三层被合并必失败 | AC-05 · AC-06 |

★ 走 `code_root` 夹具（真源为空的 `system/` 副本）—— 断言不依赖仓库里恰好有什么数据（`G-RC-02`）。
★ 夹具昂贵（每例一次 `copytree`），故**合并**断言到少量用例：宿主对删除调用计费，
  `unit` 批的时序本就不稳（`CONVENTIONS.md::V-05`）；合并**不降低**断言覆盖。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from schema.store import read_records
from scripts.review.record_eval import (
    TASK_TYPE,
    VALID_AXES,
    VALID_LAYERS,
    CompositeScoreError,
    ErrorAxisError,
    EvalLayerError,
    EvalResult,
    assert_no_composite_score,
    record_eval,
)

_AT = datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)


# ── AC-01 / AC-02 / AC-08：正路 + 持久化 + 字段落位 ──────────────────────────


def test_record_eval_happy_path_persist_and_reuse_fields(code_root):
    rec = record_eval(
        "research_quality",
        "baseline-nvda-001",
        note="六项复核通过",
        reason="初次建立复盘基线",
        version="v1",
        code_root=code_root,
        recorded_at=_AT,
        recorded_seq=1,
    )
    assert rec.eval_layer == "research_quality"
    assert rec.eval_target_ref == "baseline-nvda-001"
    assert rec.error_axis == []

    rows = read_records(code_root, "tasks")          # write → read（reload）
    assert len(rows) == 1
    row = rows[0]
    assert row["task_type"] == TASK_TYPE.value
    assert row["input_refs"] == ["baseline-nvda-001"]
    # 三个新字段落在 eval_result 上（Ch10 §C.1）
    assert row["eval_result"]["eval_layer"] == rec.eval_layer
    assert row["eval_result"]["error_axis"] == rec.error_axis
    assert row["eval_result"]["error_axis_note"] == "六项复核通过"
    # eval_target_ref / reason / version 走复用字段（parent_context），**不改 schema**
    assert row["parent_context"]["eval_target_ref"] == "baseline-nvda-001"
    assert row["parent_context"]["reason"] == "初次建立复盘基线"
    assert row["parent_context"]["version"] == "v1"
    # 事前时点可反查
    assert row["recorded_seq"] == 1
    assert row["first_seen_at"] is not None


def test_apply_false_writes_nothing_and_idempotent(code_root):
    record_eval("forecast_quality", "rec-nvda-001", code_root=code_root, apply=False)
    assert read_records(code_root, "tasks") == []    # apply=False → 纯校验

    record_eval("investment_result", "rec-nvda-001", code_root=code_root)
    record_eval("investment_result", "rec-nvda-001", code_root=code_root)   # 同幂等键
    assert len(read_records(code_root, "tasks")) == 1                       # 不重复追加


# ── AC-04：守卫真拦得住（抛异常，不是 warn；拒绝后不留半截数据）──────────────


def test_illegal_layer_and_axis_rejected_without_halfwrite(code_root):
    with pytest.raises(EvalLayerError):
        record_eval("composite", "x", code_root=code_root)
    with pytest.raises(ErrorAxisError):
        record_eval("research_quality", "x", axis=["not_an_axis"], code_root=code_root)
    assert read_records(code_root, "tasks") == []    # 两次都拒绝 → 真源仍为空


@dataclass
class _MergedWithScore:
    eval_layer: str = "research_quality"
    score: float = 0.9


@dataclass
class _MergedWithConfidence:
    eval_layer: str = "research_quality"
    confidence: float = 0.5


def test_assert_no_composite_score_blocks_and_passes():
    # 正向：带综合评分 / 置信度字段的对象 → **命中即 fail**
    with pytest.raises(CompositeScoreError):
        assert_no_composite_score([_MergedWithScore()])
    with pytest.raises(CompositeScoreError):
        assert_no_composite_score([_MergedWithConfidence()])

    # 反向对照（G-05）：合法对象 / 空序列 → **不**误伤
    clean = EvalResult("research_quality", "x", [], "", "", "")
    assert assert_no_composite_score([clean]) is None
    assert assert_no_composite_score([]) is None


# ── AC-05 / AC-06：边界（空 axis / 跨多方向 / 三层合并）──────────────────────


def test_boundary_empty_axis_and_multi_axis_are_valid(code_root):
    # 空 axis = 未定位到错误（合法）
    assert record_eval("forecast_quality", "rec-nvda-001", code_root=code_root).error_axis == []
    # 一条错误跨多个方向（合法）
    rec = record_eval(
        "investment_result",
        "rec-nvda-001",
        axis=["benchmark_forecast", "price_expectation"],
        code_root=code_root,
    )
    assert rec.error_axis == ["benchmark_forecast", "price_expectation"]

    rows = read_records(code_root, "tasks")
    assert rows[0]["eval_result"]["error_axis"] == []
    assert rows[1]["eval_result"]["error_axis"] == ["benchmark_forecast", "price_expectation"]


def test_three_layers_merged_must_fail():
    @dataclass
    class _Combined:
        eval_layer: str = "research_quality"
        confidence: float = 0.5

    with pytest.raises(CompositeScoreError):
        assert_no_composite_score([_Combined()])


def test_valid_sets_match_design_enums():
    """常量派生自 schema 枚举 —— 与 `Ch10 §C.1/C.3` 三层 / 七方向一致（防手抄漂移）。"""
    assert VALID_LAYERS == {"research_quality", "forecast_quality", "investment_result"}
    assert VALID_AXES == {
        "source",
        "business_mechanism",
        "relation_transmission",
        "financial_forecast",
        "price_expectation",
        "benchmark_forecast",
        "timing",
    }


# ── AC-03 真接线（`Ch10 §C.2`）：投资结果层**真调用**复盘收益（`review_return`）────
#
# ★ 三条断言合并在**一个**用例里：夹具昂贵（每例一次 `copytree`），
#   `CONVENTIONS.md::V-05` 明说 `unit` 批时序本就不稳；合并**不降低**覆盖（本文件既有约定）。


def test_investment_result_layer_is_wired_to_review_return(code_root):
    """`investment_result` 层 → 真调用 `compute_review_return()`（`Ch10 §C.2` / `AC-03`）。

    接线依据（此前**只有声明、没有调用** —— 本项目第三次「有声明、零消费者」事故，
    前两次 `G-50` / `G-RC-12`、第三次 `T-18`）：

    - `Ch10 §C.2` 三层表「投资结果」行的可测判据 = 「同区间绝对 / 相对收益**可算**」；
    - `review_return.py` 模块 docstring「★ 真接线（AC-03）」逐字声明消费方 = 本模块该层。

    三段断言：

    ① **真接线**（不是 stub / 硬编码）：落进记录的 dict 与**直接调用**同源 —— 逐字段相等；
    ② **如实落账**（源稿红线：不伪造数字）：口径未冻结 ⇒ `blocked_by_caliber` + 四个缺失键，
       两个数值均为 `None`（**不许**用 0 / 假设值把数字凑出来）；
    ③ **反向对照**（`G-05`：证明**不误伤**）：另两层**不得**被顺带算一遍收益 ——
       既无设计依据（`§C.2` 只对投资结果层要求收益可算），也会把"口径未冻结"的缺口
       扩散进另两层的记录、制造噪声。
    """
    from scripts.review.review_return import compute_review_return

    # ① 真接线 + ② 如实落账
    record_eval("investment_result", "rec-nvda-001", code_root=code_root)
    row = read_records(code_root, "tasks")[0]
    recorded = row["parent_context"]["investment_result"]

    assert recorded == compute_review_return("rec-nvda-001", root=code_root).as_dict(), (
        "记录里的投资结果与直接调用 compute_review_return() 不同源 —— "
        "接线被换成了 stub / 硬编码（AC-03 真接线失效）"
    )
    assert recorded["status"] == "blocked_by_caliber", recorded["status"]
    assert set(recorded["missing"]) == {
        "signal_effective_price",
        "transaction_cost",
        "pre_tax_caliber",
        "review_window",
    }, recorded["missing"]
    assert recorded["total_return"] is None and recorded["relative_return"] is None, (
        "口径未冻结却出了数字 —— 违反源稿红线（不伪造数字）"
    )

    # 三层不可合并（`N10.3-01`）：落的是**两个独立可追溯数值**，不是综合分
    assert not ({"score", "confidence"} & set(recorded)), sorted(recorded)
    assert {"total_return", "relative_return", "formula_refs"} <= set(recorded), sorted(recorded)

    # ③ 反向对照：另两层不落该键
    record_eval("research_quality", "baseline-nvda-001", code_root=code_root)
    record_eval("forecast_quality", "rec-nvda-001", code_root=code_root)
    rows = read_records(code_root, "tasks")
    assert len(rows) == 3, [r["task_id"] for r in rows]
    by_layer = {r["eval_result"]["eval_layer"]: r for r in rows}
    assert "investment_result" in by_layer["investment_result"]["parent_context"]
    for layer in ("research_quality", "forecast_quality"):
        assert "investment_result" not in by_layer[layer]["parent_context"], layer
