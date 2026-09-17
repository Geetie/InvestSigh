"""`scripts/ingest/market_data.py` 的契约测试。

★ 本文件的设计原则：**每条陷阱都配一条能证伪的用例**，而不是只测"happy path"。
  三类取数陷阱（2026-09-17 实测）各有一组正/反例：

  | 陷阱 | 反例（必须拒） | 正例（不许误伤） |
  |---|---|---|
  | ① 静默取错标的 | 代码 / 名称 / 币种三项各自不符 | 带后缀代码 `NVDA.O` 与 `NVDA` 视为同一标的 |
  | ② 非交易日前值填充 | 空日历必须拒（不许退化成不过滤） | 真实 12 行输入 → **只落 7 行** |
  | ③ 复权口径未生效 | 请求"后复权"而回参里没有；caliber=`tbd` | 回参含"后复权" ⇒ 正常落库 |

★ 全部用例都断言**"拒的时候一行都没写"** —— 只断言抛异常是不够的
  （抛异常的下一行可能已经把脏数据落进去了）。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from schema.models import Security
from schema.store import append_records, read_records

from scripts.ingest.market_data import (
    MARKET_INBOX_PREFIX,
    MARKET_INBOX_SUFFIX,
    MarketDataError,
    ingest_market_file,
    ingest_market_inbox,
    market_inbox_files,
    plan_benchmark_row,
    plan_market_rows,
)
from scripts.pricelayer import history_guard

# ── 真实读数：iFinD 2026-09-04~09-15 的 NVDA 日频序列（含 5 个伪交易日）──────────────
# 实测形态：230.36 连续 4 行（09-04 五 / 09-05 六 / 09-06 日 / **09-07 劳动节**）、
#          218.29 连续 3 行（09-11 五 / 09-12 六 / 09-13 日）。
_IFIND_POINTS = [
    {"date": "20260904", "close": "230.36"},   # 真
    {"date": "20260905", "close": "230.36"},   # 伪（周六）
    {"date": "20260906", "close": "230.36"},   # 伪（周日）
    {"date": "20260907", "close": "230.36"},   # 伪（**美国劳动节**）
    {"date": "20260908", "close": "225.73"},   # 真
    {"date": "20260909", "close": "223.67"},   # 真
    {"date": "20260910", "close": "218.36"},   # 真
    {"date": "20260911", "close": "218.29"},   # 真
    {"date": "20260912", "close": "218.29"},   # 伪（周六）
    {"date": "20260913", "close": "218.29"},   # 伪（周日）
    {"date": "20260914", "close": "210.96"},   # 真
    {"date": "20260915", "close": "212.17"},   # 真
]
_TRUE_TRADING_DAYS = [
    "2026-09-04", "2026-09-08", "2026-09-09", "2026-09-10",
    "2026-09-11", "2026-09-14", "2026-09-15",
]
_FAKE_DAYS = ["2026-09-05", "2026-09-06", "2026-09-07", "2026-09-12", "2026-09-13"]


def _series(**over) -> dict:
    base = {
        "expect": {
            "security_id": "sec-nvda",
            "ticker": "NVDA",
            "name_contains": "英伟达",
            "currency": "USD",
        },
        "request": {"market": "美股", "symbol": "NVDA", "adjustment": "后复权"},
        "resolved": {"code": "NVDA.O", "name": "英伟达", "currency": "USD"},
        "indicators_params": {"收盘价": {"复权方式": "后复权", "货币币种": "原始币种"}},
        "adjustment_caliber_version": "ifind-hfq-v1",
        "delayed": True,
        "points": list(_IFIND_POINTS),
    }
    base.update(over)
    return base


def _spec(**over) -> dict:
    base = {
        "fetched_at": "2026-09-17T08:10:00Z",
        "connectors": {"series": "iFinD", "calendar": "westock"},
        "calendar": list(_TRUE_TRADING_DAYS),
        "series": [_series()],
    }
    base.update(over)
    return base


def _register_nvda(code_root: Path) -> None:
    append_records(
        code_root,
        "securities",
        [
            Security(
                security_id="sec-nvda",
                company_id="company-nvidia",
                ticker="NVDA",
                listing_venue="NASDAQ",
                currency="USD",
                trading_session="regular",
            )
        ],
    )


def _write_spec(code_root: Path, spec: dict, name: str = f"{MARKET_INBOX_PREFIX}t.json") -> Path:
    inbox = code_root / "raw" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    path = inbox / name
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return path


# ─────────────────────────── 陷阱②：非交易日前值填充 ───────────────────────────


def test_forward_filled_nontrading_days_are_filtered(code_root: Path) -> None:
    """★ **核心用例**：iFinD 式 12 行输入 → 只落 7 行日历日，且**被剔的日期逐条可见**。

    这条把 2026-09-17 的实测形态钉进契约：不过滤的话，32 个交易日的窗口会变约 55 行，
    每个周末都会被当成"价格不变的交易日"写进**追加式不可变真源**。
    """
    _register_nvda(code_root)
    rows, report = plan_market_rows(code_root, _spec(), filename="m.json")

    assert len(rows) == 7, f"12 行输入只应有 7 个真交易日，实得 {len(rows)}"
    got = [r.occurred_at.date().isoformat() for r in rows]  # type: ignore[union-attr]
    assert got == _TRUE_TRADING_DAYS, got
    assert report.excluded_dates["sec-nvda"] == _FAKE_DAYS, report.excluded_dates
    assert "2026-09-07" in report.excluded_dates["sec-nvda"], "劳动节必须被剔除"


def test_all_points_excluded_is_rejected(code_root: Path) -> None:
    """日历与序列**完全对不上** ⇒ 拒（不许落一个空标的，也不许"反正有几个就落几个"）。"""
    spec = _spec(calendar=["2026-01-05", "2026-01-06"])
    with pytest.raises(MarketDataError, match="全部"):
        plan_market_rows(code_root, spec, filename="m.json")


def test_empty_calendar_is_rejected(code_root: Path) -> None:
    """★ 空日历 ⇒ **拒**。这是防"退化成不过滤直接落库"的那一道闸。"""
    with pytest.raises(MarketDataError, match="calendar"):
        plan_market_rows(code_root, _spec(calendar=[]), filename="m.json")


def test_repeated_adjacent_values_are_reported_not_rejected(code_root: Path) -> None:
    """相邻交易日**同值** ⇒ **报**（前值填充嫌疑），**不拒**（真实同值也可能发生）。"""
    calendar = ["2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11"]
    points = [
        {"date": "20260908", "close": "100.0"},
        {"date": "20260909", "close": "100.0"},   # 与上一天同值
        {"date": "20260910", "close": "100.0"},   # 继续同值
        {"date": "20260911", "close": "101.0"},
    ]
    rows, report = plan_market_rows(
        code_root, _spec(calendar=calendar, series=[_series(points=points)]), filename="m.json"
    )
    assert len(rows) == 4, "同值不得被剔除（它可能真是停牌/低流动性的真实价）"
    assert report.repeated_value_runs["sec-nvda"] == ["2026-09-08..2026-09-10=100.0"]


# ─────────────────────────── 陷阱①：静默取错标的 ───────────────────────────


def test_wrong_resolved_code_is_rejected_and_writes_nothing(code_root: Path) -> None:
    """★ 解析到的代码与期望 ticker 不符 ⇒ 拒，**且一行都没写**。

    实测形态：`search_securities("AGIX")` 会返回同前缀的**另一只**证券，
    且 `dataTotalVolume` 与 `selectedSecuritiesCount` 不一致（静默丢候选）。
    """
    _register_nvda(code_root)
    bad = _series(resolved={"code": "AGIX.TV", "name": "Eastfield Resources", "currency": "CAD"})
    with pytest.raises(MarketDataError, match="标的身份不符"):
        ingest_market_file(code_root, _write_spec(code_root, _spec(series=[bad])))
    assert read_records(code_root, "prices") == [], "校验未通过时**不得**有部分写入"


def test_resolved_name_mismatch_is_rejected(code_root: Path) -> None:
    """名称不含期望子串 ⇒ 拒。实测形态：AGIX 的简称被返回成它的**跟踪指数**名。"""
    _register_nvda(code_root)
    bad = _series(resolved={"code": "NVDA.O", "name": "人工智能通用智能指数", "currency": "USD"})
    with pytest.raises(MarketDataError, match="标的名不符"):
        plan_market_rows(code_root, _spec(series=[bad]), filename="m.json")


def test_currency_mismatch_is_rejected(code_root: Path) -> None:
    """币种不符 ⇒ 拒。实测形态：裸词 AGIX 曾被解析到一只 **CAD** 计价的证券。"""
    _register_nvda(code_root)
    bad = _series(resolved={"code": "NVDA.O", "name": "英伟达", "currency": "CAD"})
    with pytest.raises(MarketDataError, match="币种不符"):
        plan_market_rows(code_root, _spec(series=[bad]), filename="m.json")


def test_suffixed_code_is_accepted(code_root: Path) -> None:
    """**反向对照**：`NVDA.O` / `usNVDA.OQ` 这类带后缀代码与 `NVDA` 视为同一标的（不误伤）。"""
    _register_nvda(code_root)
    for code in ("NVDA.O", "usNVDA.OQ", "NVDA"):
        rows, _ = plan_market_rows(
            code_root, _spec(series=[_series(resolved={"code": code, "name": "英伟达", "currency": "USD"})]),
            filename="m.json",
        )
        assert len(rows) == 7, code


def test_same_stem_different_market_is_still_rejected(code_root: Path) -> None:
    """★ **同名不同市场**（`AGIX` vs `AGIX.TV`）⇒ 仍被拦下 —— 证明防线是**三项联合**。

    这条是刻意造的最难形态：代码前段**逐字相同**（`AGIX`），只比代码区分不了。
    拦下它靠的是另外两项 —— 名称（`Eastfield Resources` ≠ 期望子串）与币种（`CAD` ≠ `USD`）。
    """
    bad = _series(
        expect={
            "security_id": "sec-agix",
            "ticker": "AGIX",
            "name_contains": "人工智能ETF",
            "currency": "USD",
        },
        resolved={"code": "AGIX.TV", "name": "Eastfield Resources Ltd.", "currency": "CAD"},
    )
    with pytest.raises(MarketDataError, match="标的名不符"):
        plan_market_rows(code_root, _spec(series=[bad]), filename="m.json")


# ─────────────────────────── 陷阱③：复权口径未生效 ───────────────────────────


def test_caliber_not_reflected_in_params_is_rejected(code_root: Path) -> None:
    """★ 请求"后复权"但回读参数里找不到它 ⇒ 拒。

    实测形态：自然语言同时指定多个口径时工具会退化，**全部按不复权返回**。
    """
    _register_nvda(code_root)
    bad = _series(indicators_params={"收盘价": {"复权方式": "不复权"}})
    with pytest.raises(MarketDataError, match="复权口径未生效"):
        plan_market_rows(code_root, _spec(series=[bad]), filename="m.json")


def test_missing_indicators_params_is_rejected(code_root: Path) -> None:
    """不给 `indicators_params` ⇒ 拒（等于无法自证口径）。"""
    _register_nvda(code_root)
    bad = _series()
    bad.pop("indicators_params")
    with pytest.raises(MarketDataError, match="indicators_params"):
        plan_market_rows(code_root, _spec(series=[bad]), filename="m.json")


def test_tbd_caliber_version_is_rejected(code_root: Path) -> None:
    """`adjustment_caliber_version` 是 `tbd`（或缺失）⇒ 拒 —— 那正是 `PriceSnapshot` 的字段默认值，
    静默沿用即"口径未声明"（`Ch9 §N9.3-08` P0）。"""
    _register_nvda(code_root)
    for value in ("tbd", "", None):
        bad = _series(adjustment_caliber_version=value)
        with pytest.raises(MarketDataError, match="caliber_version|tbd"):
            plan_market_rows(code_root, _spec(series=[bad]), filename="m.json")


# ─────────────────────────── 落库语义 ───────────────────────────


def test_ingest_writes_rows_with_caliber_and_backfill(code_root: Path) -> None:
    """落库行的**口径与补入标记**必须显式：caliber 非 tbd、资料日期早于补入日 ⇒ `backfilled_at`。"""
    _register_nvda(code_root)
    report = ingest_market_file(code_root, _write_spec(code_root, _spec()))
    assert report.rows_written == 7

    rows = read_records(code_root, "prices")
    assert len(rows) == 7
    for row in rows:
        assert row["adjustment_caliber_version"] == "ifind-hfq-v1"
        assert row["source_id"] == "iFinD"
        assert row["currency"] == "USD"
        assert row["delayed"] is True
        assert row["backfilled_at"], "资料日期早于补入日 ⇒ 必须显式标补入"
    seqs = [r["recorded_seq"] for r in rows]
    assert seqs == list(range(1, 8)), f"recorded_seq 必须递增，实得 {seqs}"


def test_rerun_is_idempotent_and_separates_produced_from_skipped(code_root: Path) -> None:
    """★ 重跑同日：**不重复落库**；`produced` 空、`skipped` 非空 —— 首跑与重跑**可区分**。"""
    _register_nvda(code_root)
    path = _write_spec(code_root, _spec())

    first = ingest_market_inbox(code_root)
    assert len(first[0]) == 7 and first[1] == [], "首跑：7 条新写入、0 条命中"
    assert len(read_records(code_root, "prices")) == 7

    second = ingest_market_inbox(code_root)
    assert second[0] == [], "重跑：**不得**再记新写入（否则首跑与重跑在输出上不可区分）"
    assert len(second[1]) == 7, "重跑：幂等命中应走独立列表"
    assert len(read_records(code_root, "prices")) == 7, "真源行数不得增长"
    assert path.exists()


def test_bad_spec_degrades_whole_batch_without_writing(code_root: Path) -> None:
    """★ 校验不过的清单 ⇒ **整批不落库** + `degraded=True` + 原因逐字可见（不静默略过）。"""
    _register_nvda(code_root)
    _write_spec(code_root, _spec(calendar=[]))
    produced, skipped, degraded, notes = ingest_market_inbox(code_root)
    assert produced == [] and skipped == []
    assert degraded is True
    assert any("校验未通过" in n for n in notes), notes
    assert read_records(code_root, "prices") == []


def test_unregistered_security_is_reported(code_root: Path) -> None:
    """证券未在 `facts/securities.jsonl` 注册 ⇒ **不阻断**，但必须记悬挂引用（缺要可见）。"""
    rows, report = plan_market_rows(code_root, _spec(), filename="m.json")
    assert len(rows) == 7, "悬挂不是拒绝的理由（已知根因：Security.company_id 必填 ⇒ ETF 无处注册）"
    assert report.unregistered_securities == ["sec-nvda"]


def test_dry_run_writes_nothing(code_root: Path) -> None:
    """`dry_run` 只算不写 —— 供"先看会发生什么"用。"""
    _register_nvda(code_root)
    report = ingest_market_file(code_root, _write_spec(code_root, _spec()), dry_run=True)
    assert report.rows_written == 0
    assert read_records(code_root, "prices") == []


def test_delay_minutes_forces_delayed_flag(code_root: Path) -> None:
    """连接器给出 `delay_minutes > 0` ⇒ 强制 `delayed=True`（不得标实时，反例 **T13**）。"""
    _register_nvda(code_root)
    entry = _series(delayed=False, delay_minutes=15)
    rows, report = plan_market_rows(code_root, _spec(series=[entry]), filename="m.json")
    assert all(r.delayed is True for r in rows)
    assert any("delay_minutes=15" in n for n in report.notes), report.notes


# ─────────────────────────── 投递口分派 ───────────────────────────


def test_inbox_matcher_only_takes_market_prefix_json(code_root: Path) -> None:
    """★ 只认「`market_data_` 前缀 + `.json`」。

    其余文件（含**别的** `.json`）一律不碰 —— 否则会改变 `ingest_step.py` 既有文本处理的行为
    （那些文件归 `process_raw_file`，进去就会被当文本解析成一条 claim）。
    """
    inbox = code_root / "raw" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    wanted = f"{MARKET_INBOX_PREFIX}2026-09-17{MARKET_INBOX_SUFFIX}"
    for name in (wanted, "report.json", f"{MARKET_INBOX_PREFIX}x.txt", "2026-01-01-note.txt"):
        (inbox / name).write_text("{}", encoding="utf-8")
    assert [p.name for p in market_inbox_files(code_root)] == [wanted]


def test_missing_inbox_is_not_an_error(code_root: Path) -> None:
    """投递口不存在 ⇒ 返回空列表（**不是**异常）—— 由调用方决定"无投递物"怎么记。"""
    assert market_inbox_files(code_root / "no_such_root") == []


def test_double_count_risk_is_reported(code_root: Path) -> None:
    """★ **重复计分红**的机器绑定：价格口径已含分红调整 + 公司行动表里有同区间 `div` ⇒ **必报**。

    该组合此前零机器绑定（2026-09-17 实测登记 `gap-hfq-vs-corporate-actions-double-count`）：
    `returns.py::_total_return_value` 按「先复权再总回报」会对 `div` **再投一次** ⇒ 分红计两次。
    ★ 只报不拒：两种口径并存也可能是刻意的，机器只保证"不可能悄悄发生"。
    """
    _register_nvda(code_root)
    reg = code_root / "registry"
    reg.mkdir(parents=True, exist_ok=True)
    (reg / "corporate-actions.jsonl").write_text(
        json.dumps(
            {"security_id": "sec-nvda", "action_type": "div", "effective_date": "2026-09-08"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    rows, report = plan_market_rows(code_root, _spec(), filename="m.json")
    assert len(rows) == 7, "报告这种风险**不得**阻断落库（信息不足时不替人做选择）"
    assert any("重复计" in n for n in report.notes), report.notes


def test_no_double_count_note_without_corporate_actions(code_root: Path) -> None:
    """**反向对照**：公司行动表为空 ⇒ 不得报该风险（否则是一条恒真的噪音）。"""
    _register_nvda(code_root)
    _, report = plan_market_rows(code_root, _spec(), filename="m.json")
    assert not any("重复计" in n for n in report.notes), report.notes


def test_no_double_count_note_for_plain_caliber(code_root: Path) -> None:
    """**反向对照**：口径**不含**分红调整标记（如 `close-unadjusted`）⇒ 不报。

    这条防"只要公司行动表非空就报"的粗判 —— 那样它会退化成噪音并被学会忽略。
    """
    _register_nvda(code_root)
    reg = code_root / "registry"
    reg.mkdir(parents=True, exist_ok=True)
    (reg / "corporate-actions.jsonl").write_text(
        json.dumps(
            {"security_id": "sec-nvda", "action_type": "div", "effective_date": "2026-09-08"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    entry = _series(adjustment_caliber_version="ifind-close-unadjusted-v1")
    _, report = plan_market_rows(code_root, _spec(series=[entry]), filename="m.json")
    assert not any("重复计" in n for n in report.notes), report.notes


def test_occurred_at_uses_session_close_and_excludes_weekends(code_root: Path) -> None:
    """`occurred_at` 取交易日 + 收盘时刻；落库集合内**不得**出现周末（端到端再核一次）。"""
    _register_nvda(code_root)
    ingest_market_file(code_root, _write_spec(code_root, _spec()))
    days = sorted({r["occurred_at"][:10] for r in read_records(code_root, "prices")})
    weekends = [d for d in days if date.fromisoformat(d).weekday() >= 5]
    assert weekends == [], f"落库集合里出现周末：{weekends}"
    assert "2026-09-07" not in days, "劳动节不得落库"


# ─────────────────────────── 基准（`facts/benchmarks.jsonl`，`Ch5 §E.1`） ──────────


def _bm_block(**over) -> dict:
    base = {
        "benchmark_id": "AGIX",
        "includes_non_listed_assets": True,
        "observed": {
            "unit_nav": "45.03",
            "unit_nav_date": "2026-09-16",
            "unit_nav_currency": "USD",
            "tracking_index": "Solactive Etna人工智能通用智能指数",
            "listing_date": "2024-07-18",
            "holdings_page": "https://kraneshares.com/etf/agix/",
            "holdings_as_of": "2026-09-16",
            "non_listed_assets": [
                {
                    "name": "ANTHROPIC, PBC",
                    "value": "12926025",
                    "weight": "0.0118",
                    "gap_note": "非上市；估值为公司自报，不可独立复核",
                },
                {
                    "name": "GENERAL INTUITION US INC",
                    "value": "9999948",
                    "weight": "0.0092",
                    "gap_note": "同上",
                },
            ],
        },
        "sensitivity": [{"basis": "非上市合计 4.35% NAV；按 ±50% 估值折让计敏感性"}],
        "unverifiable_forecasts": [],
        "modeled_coverage": None,
        "claims_complete_forecast": False,
    }
    base.update(over)
    return base


def _bm_spec(**over) -> dict:
    spec = _spec()
    spec["connectors"] = dict(spec["connectors"], benchmark="kraneshares_web")
    spec["benchmark"] = _bm_block(**over)
    return spec


def test_benchmark_row_passes_history_guard(code_root: Path) -> None:
    """★ **核心用例**：落库后的基准行必须**直接通过** `history_guard` 的真实判据。

    ★ 为什么调真判据而不是重写一份校验：`Ch5 §E.1` 的 ①②③④⑤ 五条已有唯一实现
      （`history_guard.check_benchmark_special_cases`）。重写一份 = 制造第二个口径，
      两处一旦漂移，落库脚本"自认为合规"而守卫判红（本项目栽过多次的同族）。
    """
    _register_nvda(code_root)
    report = ingest_market_file(code_root, _write_spec(code_root, _bm_spec()))
    assert report.rows_written == 7

    rows = read_records(code_root, "benchmarks")
    assert len(rows) == 1, "应落下 1 条基准行"
    row = rows[0]
    assert row["benchmark_id"] == "AGIX"
    assert row["includes_non_listed_assets"] is True
    assert row["non_listed_assets"], "非上市资产明细必须落库（实测可得，不再是缺口）"
    assert row["sensitivity"], "敏感性必须非空"
    assert row["unverifiable_forecasts"] == [], "显式空列表 ≠ 缺字段"
    lag = row["holdings_disclosure_lag"]
    assert lag and "2026-09-16" in lag and "滞后" in lag, f"披露延迟应为派生量：{lag!r}"

    guard = history_guard.check(code_root)
    assert guard.passed, f"落库的基准行未通过 history_guard 的真判据：{[v.reason for v in guard.violations]}"


def test_benchmark_declaration_must_match_rules(code_root: Path) -> None:
    """★ **交叉核对**：事实行声明的 `includes_non_listed_assets` 必须与 `rules/benchmark.yaml` 一致。

    两处都是真源；打架时必须**当场拒**，而不是默默二选一（那正是最难发现的漂移）。
    """
    _register_nvda(code_root)
    with pytest.raises(MarketDataError, match="不一致"):
        plan_benchmark_row(code_root, _bm_spec(includes_non_listed_assets=False), filename="m.json")
    assert read_records(code_root, "benchmarks") == []


def test_benchmark_missing_gap_note_is_rejected(code_root: Path) -> None:
    """判据②：某条非上市资产缺 `gap_note` ⇒ 拒（`Ch5 §E.1` 的 `{value, weight, gap_note}`）。"""
    block = _bm_block()
    del block["observed"]["non_listed_assets"][0]["gap_note"]
    with pytest.raises(MarketDataError, match="gap_note"):
        plan_benchmark_row(code_root, _bm_spec(**{k: block[k] for k in block}), filename="m.json")


def test_benchmark_empty_sensitivity_is_rejected(code_root: Path) -> None:
    """判据③：含非上市资产但 `sensitivity` 为空 ⇒ 拒（`Ch5 §E.1` / `§J8`）。"""
    with pytest.raises(MarketDataError, match="sensitivity"):
        plan_benchmark_row(code_root, _bm_spec(sensitivity=[]), filename="m.json")


def test_benchmark_missing_unverifiable_forecasts_is_rejected(code_root: Path) -> None:
    """判据⑤：`unverifiable_forecasts` **缺字段** ⇒ 拒（**可为空列表，但必须显式**）。

    ★ 注意这里**不能**用 `_bm_spec(**block)` —— 那个工厂会用 `_bm_block()` 的默认值重建，
      删掉的顶层键会被补回来（本用例第一次就是因此假绿）。必须显式传整块。
    """
    block = _bm_block()
    del block["unverifiable_forecasts"]
    spec = _spec()
    spec["benchmark"] = block
    with pytest.raises(MarketDataError, match="unverifiable_forecasts"):
        plan_benchmark_row(code_root, spec, filename="m.json")


def test_benchmark_empty_non_listed_assets_is_rejected(code_root: Path) -> None:
    """判据①：声明含非上市资产但清单为空 ⇒ 拒。"""
    block = _bm_block()
    block["observed"] = dict(block["observed"], non_listed_assets=[])
    with pytest.raises(MarketDataError, match="non_listed_assets"):
        plan_benchmark_row(code_root, _bm_spec(**block), filename="m.json")


def test_benchmark_rerun_is_idempotent(code_root: Path) -> None:
    """同一 `holdings_as_of` 重跑 ⇒ **不重复落库**（追加式真源不得堆同版行）。"""
    _register_nvda(code_root)
    path = _write_spec(code_root, _bm_spec())
    ingest_market_file(code_root, path)
    assert len(read_records(code_root, "benchmarks")) == 1
    ingest_market_file(code_root, path)
    assert len(read_records(code_root, "benchmarks")) == 1, "同 as-of 不得重复落库"


def test_privately_listed_state_comes_from_rules(code_root: Path) -> None:
    """★ 披露状态**取规则层声明**（单一真源），不在事实行里另写一份。

    实测：2026-09-17 已把 `rules/benchmark.yaml` 的 `disclosure_state` 由
    `undisclosed` 更正为 `disclosed`（官网逐条披露）；事实行应如实反映该值。
    """
    _register_nvda(code_root)
    ingest_market_file(code_root, _write_spec(code_root, _bm_spec()))
    row = read_records(code_root, "benchmarks")[0]
    assert row["coverage_profile"]["non_listed_disclosure_state"] == "disclosed"
    assert row["coverage_profile"]["tracking_index"] == "Solactive Etna人工智能通用智能指数"
    assert row["coverage_profile"]["holdings_page_as_of"] == "2026-09-16"
