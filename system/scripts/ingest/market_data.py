#!/usr/bin/env python3
"""`market_data.py` —— 行情与基准的**确定性落库**（MCP 取数之后）。

## 分工（`00_交付施工图.md §1.3`）

- 「**取数动作**」= 阶段④ **A 档（零代码，直接复用 WorkBuddy）** —— 由会话里的 MCP 连接器做；
- 「**落库逻辑**」= **本模块**，在版本库里、可复跑、可测试。

⇒ **接缝在投递侧**（与 `ingest_step.py` 同一条纪律）：会话把 MCP 的原始返回写成
`raw/inbox/market_data_<date>.json`，本模块负责**校验 → 过滤 → 落库**。
**本模块自己不调 MCP**（脚本跑在 shell 里，没有宿主能力）。

## 本模块要拦的三类取数陷阱

三类都是 2026-09-17 实测到的，**每一条都配了机器校验**（不是靠注释提醒人）：

### ① 静默取错标的
`search_securities(market="美股", query="AGIX")` 实测返回
`{代码: AGIX.O, 简称: "人工智能通用智能指数"}` —— 简称是**它的跟踪指数**、不是基金名；
且 `dataTotalVolume: 2` 而 `selectedSecuritiesCount: 1` ⇒ **静默丢弃了一条候选**。
⇒ 对策：输入的 `resolved` 必须与 `expect` **逐字段比对**（代码前缀、名称子串、币种），
不符即 `MarketDataError` —— **宁可拒，不许猜**。

### ② 非交易日前值填充
iFinD 日频序列**含非交易日并按前值填充**。实测
`get_security_indicators(market="美股", query="…NVDA 2026年9月4日至9月15日 每日收盘价")`
返回 **12 行**，其中 `230.36` 连续 4 行（含 **09-07 美国劳动节**）、`218.29` 连续 3 行（含周末），
**真交易日仅 7 个（虚增 71%）**。
⇒ 对策：**用独立来源的 `calendar` 过滤**，**不许信序列自己的日期**；
并把"剔除了哪些日期"作为**必报项**（`excluded_dates`）。

### ③ 复权口径请求了但没生效
自然语言型工具在**同时指定多个口径**时会退化 —— 实测请求"三种复权方式"只回两列且**都变成不复权**。
⇒ 对策：必须回读 `indicators_params` **自证**请求的口径真的落在里面；未生效即拒。

## 落库口径

- **只落 `calendar ∩ points.date`**（陷阱②）；
- `adjustment_caliber_version` 必须显式给出且非 `tbd`（`PriceSnapshot` 的默认值是 `tbd`，
  静默沿用即"口径未声明"，`Ch9 §N9.3-08` P0）；
- 五类时间：`occurred_at` = 交易日收盘时刻（由输入 `session_close_utc` 给，缺省 `20:00Z`
  = 美东 16:00 EDT）；`first_seen_at` = `analyzed_at` = `fetched_at`；
  资料日期早于补入日 ⇒ `backfilled_at` = `fetched_at`（`Ch9 §N9.1-31/32`）；
- `recorded_seq` 从现有 `facts/prices.jsonl` 最大者 **+1** 递增（追加式真源的版本序，`Ch9 §3.4.1`）；
- **幂等**：`snapshot_id` 已存在则跳过（走 `skipped`，**不是降级**，`Ch9 §N9.2-11`）。

## 与 `securities` 的关系

`PriceSnapshot.security_id` 必须指向一个证券。若该证券**未在 `facts/securities.jsonl` 注册**，
本模块**不阻断**，但**必须**在报告里显式记悬挂引用及其根因
（已知：`Security.company_id` 必填 ⇒ ETF 无处注册）。
⇒ 把"缺"变成**可见的缺**，而不是悄悄写进去（`G-03`：0 行 ≠ 已验证，悬挂 ≠ 无问题）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from schema.models import Benchmark, BenchmarkRole, PriceSnapshot
from schema.store import append_records, read_records

__all__ = [
    "MARKET_INBOX_PREFIX",
    "MARKET_INBOX_SUFFIX",
    "BENCHMARK_RULES_REL",
    "MarketDataError",
    "MarketIngestReport",
    "BenchmarkIngestReport",
    "market_inbox_files",
    "plan_market_rows",
    "plan_benchmark_row",
    "ingest_market_file",
    "ingest_market_inbox",
]

MARKET_INBOX_PREFIX = "market_data_"
"""投递口里**行情清单**的文件名前缀（与 `ingest_step.py` 的文本投递物区分）。"""

MARKET_INBOX_SUFFIX = ".json"
"""行情清单扩展名。**只有**「前缀 + .json」的文件走本模块，其余一律归文本处理器。"""

DEFAULT_SESSION_CLOSE_UTC = "20:00"
"""美股常规时段收盘 = 美东 16:00；夏令时（EDT=UTC−4）⇒ `20:00Z`。

★ 它是**缺省**，不是普适常量 —— 冬令时（EST=UTC−5）应为 `21:00Z`。
故输入可显式给 `session_close_utc` 覆盖；**不**在代码里按时令猜。
"""

_TICKER_SUFFIX = re.compile(r"^[A-Za-z0-9]+")
"""从 `NVDA.O` / `usNVDA.OQ` 这类带后缀代码里取主机名部分（只取前导字母数字段）。"""

_MARKET_PREFIXES = ("US", "HK", "SH", "SZ", "JP", "KR")
"""`ticker` 的市场前缀（westock 用 `usNVDA.OQ` / `usAGIX.OQ` 这种带前缀格式）。"""


class MarketDataError(RuntimeError):
    """行情清单**校验未通过** —— 响亮失败，不落库、不猜测、不降级成"部分可用"。"""


@dataclass
class MarketIngestReport:
    """一次行情落库的**如实回执**（判据只看这里的读数，不看过程叙述）。"""

    rows_written: int = 0
    snapshots_skipped: int = 0
    skipped_ids: list[str] = field(default_factory=list)
    """幂等命中的 `snapshot_id`（同 id 已存在）—— 走**独立**列表，不折进 `produced`
    （`Ch9 §N9.2-11`：重跑同日不重复落库是设计行为，首跑与重跑的观测量必须可区分）。"""

    excluded_dates: dict[str, list[str]] = field(default_factory=dict)
    """每个 `security_id` 被日历剔除的日期 —— 陷阱②的**必报项**（不静默）。"""

    repeated_value_runs: dict[str, list[str]] = field(default_factory=dict)
    """检测到的"相邻交易日同值"区间（前值填充**嫌疑**）—— 只报不拒（真同值也可能发生）。"""

    unregistered_securities: list[str] = field(default_factory=list)
    """有行情但未在 `facts/securities.jsonl` 注册的证券 ⇒ **悬挂引用**（显式记录）。"""

    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [
            f"落库 {self.rows_written} 行",
            f"幂等跳过 {self.snapshots_skipped}",
        ]
        if self.excluded_dates:
            total = sum(len(v) for v in self.excluded_dates.values())
            parts.append(f"按日历剔除 {total} 个非交易日")
        if self.repeated_value_runs:
            parts.append(f"相邻同值区间 {sum(len(v) for v in self.repeated_value_runs.values())} 处")
        if self.unregistered_securities:
            parts.append(f"悬挂证券 {sorted(self.unregistered_securities)}")
        return "；".join(parts)


def market_inbox_files(root: str | Path) -> list[Path]:
    """投递口下**属于本模块**的行情清单，按名排序保证可复现。

    ★ 只认「`market_data_` 前缀 + `.json`」—— 其余文件（含别的 `.json`）一律不碰，
      以免改变 `ingest_step.py` 既有文本处理的行为（`R-06`：只增不改）。
    """
    inbox = Path(root) / "raw" / "inbox"
    if not inbox.is_dir():
        return []
    return sorted(
        (
            p
            for p in inbox.iterdir()
            if p.is_file()
            and p.name.startswith(MARKET_INBOX_PREFIX)
            and p.name.endswith(MARKET_INBOX_SUFFIX)
        ),
        key=lambda p: p.name,
    )


def _load_spec(path: Path) -> Mapping[str, Any]:
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise MarketDataError(f"{path.name}: 读取失败（{type(exc).__name__}: {exc}）") from exc
    except json.JSONDecodeError as exc:
        raise MarketDataError(f"{path.name}: 不是合法 JSON（{exc}）") from exc
    if not isinstance(spec, Mapping):
        raise MarketDataError(f"{path.name}: 顶层必须是对象")
    return spec


def _require(spec: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in spec:
        raise MarketDataError(f"{where}: 缺必填字段 `{key}`")
    return spec[key]


def _normalize_ticker(code: str) -> str:
    """`NVDA.O` / `usNVDA.OQ` → `NVDA`（剥交易所后缀与市场前缀），用于与 `expect.ticker` 比对。

    ★ 它**只**解决"同一标的的不同写法"；**不**负责发现"同名但不同市场"
      —— `AGIX` 与 `AGIX.TV` 都会规范化成 `AGIX`，只比代码**区分不了它们**。
      那一层由 `_check_identity` 的**名称**与**币种**两项拦下（实测形态：
      `AGIX.TV` 是另一家加拿大的公司，名称 `Eastfield Resources`、币种 `CAD`）。
      ⇒ 陷阱① 的防线是**三项联合**，不是单看代码。
    """
    m = _TICKER_SUFFIX.match(code.strip())
    stem = (m.group(0) if m else code.strip()).upper()
    for prefix in _MARKET_PREFIXES:
        if stem.startswith(prefix) and len(stem) - len(prefix) >= 2:
            return stem[len(prefix):]
    return stem


def _iter_strings(obj: Any) -> list[str]:
    """递归收集嵌套结构里的**全部字符串**（用于在 `indicators_params` 里自证口径）。"""
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, Mapping):
        for k, v in obj.items():
            out.append(str(k))
            out.extend(_iter_strings(v))
    elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
        for v in obj:
            out.extend(_iter_strings(v))
    return out


def _parse_day(value: Any, where: str) -> date:
    text = str(value).strip()
    if re.fullmatch(r"\d{8}", text):  # iFinD 的 YYYYMMDD
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise MarketDataError(f"{where}: 日期无法解析（{value!r}）") from exc


def _check_identity(entry: Mapping[str, Any], where: str) -> dict[str, str]:
    """陷阱①：把 `resolved` 与 `expect` 逐字段比对 —— 不符即拒（**宁可拒，不许猜**）。"""
    expect = _require(entry, "expect", where)
    resolved = _require(entry, "resolved", where)
    for obj, tag in ((expect, "expect"), (resolved, "resolved")):
        if not isinstance(obj, Mapping):
            raise MarketDataError(f"{where}.{tag}: 必须是对象")

    want_ticker = str(_require(expect, "ticker", f"{where}.expect")).strip()
    got_code = str(_require(resolved, "code", f"{where}.resolved")).strip()
    if _normalize_ticker(want_ticker) != _normalize_ticker(got_code):
        raise MarketDataError(
            f"{where}: **标的身份不符** —— 期望 ticker={want_ticker!r}，"
            f"但连接器解析到 code={got_code!r}。"
            "（实测形态：`search_securities('AGIX')` 会返回同前缀的**另一只**证券，"
            "且 `dataTotalVolume` 与 `selectedSecuritiesCount` 不一致 ⇒ 静默取错标的。）"
        )

    name_contains = str(_require(expect, "name_contains", f"{where}.expect")).strip()
    got_name = str(_require(resolved, "name", f"{where}.resolved")).strip()
    if name_contains and name_contains not in got_name:
        raise MarketDataError(
            f"{where}: **标的名不符** —— 期望名称含 {name_contains!r}，实得 {got_name!r}。"
            "（实测形态：AGIX 的简称被返回成它的**跟踪指数**名。）"
        )

    want_ccy = str(_require(expect, "currency", f"{where}.expect")).strip().upper()
    got_ccy = str(_require(resolved, "currency", f"{where}.resolved")).strip().upper()
    if want_ccy != got_ccy:
        raise MarketDataError(
            f"{where}: **币种不符** —— 期望 {want_ccy}，实得 {got_ccy}。"
            "（实测形态：裸词 AGIX 曾被解析到一只 **CAD** 计价的证券。）"
        )
    return {"ticker": want_ticker, "name": got_name, "currency": got_ccy}


def _check_caliber(entry: Mapping[str, Any], where: str) -> str:
    """陷阱③：回读 `indicators_params` 自证请求的复权口径**真的生效**。"""
    request = entry.get("request")
    if request is not None and not isinstance(request, Mapping):
        raise MarketDataError(f"{where}.request: 必须是对象")
    request = request or {}
    wanted = str(request.get("adjustment") or "").strip()
    if not wanted:
        raise MarketDataError(f"{where}.request: 缺 `adjustment`（必须显式声明请求的复权口径）")

    params = entry.get("indicators_params")
    if params is None:
        raise MarketDataError(
            f"{where}: 缺 `indicators_params` —— 无法自证口径。"
            "（该字段是连接器回读的**实际查询参数**；不给就等于无法排除"
            "「请求后复权、实际按不复权返回」这一实测发生过的退化。）"
        )
    if wanted not in _iter_strings(params):
        raise MarketDataError(
            f"{where}: **复权口径未生效** —— 请求 {wanted!r}，"
            f"但连接器回读的参数里找不到它（{params!r}）。"
            "（实测形态：同时指定多个口径时工具会退化，全部按不复权返回。）"
        )

    caliber = str(entry.get("adjustment_caliber_version") or "").strip()
    if not caliber or caliber == "tbd":
        raise MarketDataError(
            f"{where}: `adjustment_caliber_version` 必须显式给出且不得为 `tbd`"
            "（`PriceSnapshot` 的字段默认值是 `tbd`，静默沿用即口径未声明；`Ch9 §N9.3-08` P0）"
        )
    return caliber


_CALIBERS_WITH_DIVIDEND_ADJUSTMENT = ("hfq", "adjusted", "reinvested")
"""口径**词元** —— 出现这些说明价格序列已含分红（再投资）调整。

★ **按词元全等匹配，不做子串判定**（`CONVENTIONS.md::R-06 ①` 明禁关键词式判据）：
  实测踩过 —— 口径 `ifind-close-**unadjusted**-v1` 含子串 `adjusted`，
  子串判定会把它误报成"已含分红调整"。按 `-`/`_` 切词后比对词元即可避免
  （`unadjusted` 是一个**独立词元**，与 `adjusted` 不相等）。

★ 与 `scripts/compute/returns.py::_total_return_value` 的组合风险
  （缺口 `gap-hfq-vs-corporate-actions-double-count`）：该函数 docstring 逐字写
  「**先复权再总回报**」，并对窗口内的 `div` 执行 `shares += cash_d / 当日价`。
  若 `prices` 里存的**已是后复权价**、而 `registry/corporate-actions.jsonl` 里又放了
  同一区间的 `div` ⇒ **分红被计两次**。
  该组合此前**没有任何机器绑定**（2026-09-17 实测登记）—— 本函数补上这一条。
"""


def _has_dividend_adjustment(caliber: str) -> bool:
    """口径标识里是否含"已做分红调整"的**词元**（全等，非子串）。"""
    tokens = {t for t in re.split(r"[^a-z0-9]+", caliber.lower()) if t}
    return bool(tokens & set(_CALIBERS_WITH_DIVIDEND_ADJUSTMENT))


def _load_dividend_actions(root: Path) -> list[tuple[str, date]]:
    """读 `registry/corporate-actions.jsonl` 的 `div` 行 → `[(security_id, effective_date)]`。

    ★ 坏行 ⇒ **响亮失败**，不静默跳过：该文件是**真源**，格式错误必须当场暴露。
      （`no_placeholder_guard::SWALLOW_EXCEPTION_CONTINUE` 明禁"except 后 continue"——
      那会把"真源里有一行烂数据"变成"这一行不存在"，正是最难发现的静默错。）
    """
    path = root / "registry" / "corporate-actions.jsonl"
    if not path.exists():
        return []
    out: list[tuple[str, date]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MarketDataError(
                f"registry/corporate-actions.jsonl:{lineno} 不是合法 JSON（{exc}）"
            ) from exc
        if not isinstance(row, Mapping) or str(row.get("action_type")) != "div":
            continue
        out.append(
            (
                str(row.get("security_id")),
                _parse_day(row.get("effective_date"), f"corporate-actions:{lineno}"),
            )
        )
    return out


def _double_count_notes(
    root: Path, security_id: str, caliber: str, days: Sequence[date]
) -> list[str]:
    """检测「已含分红调整的价格序列 + 公司行动表」的**重复计**风险。

    ★ 只报**不拒**：两种口径并存也可能是刻意的（例如用不含调整的序列配公司行动表）。
      机器能做的是**让这个组合不可能悄悄发生**，不是在信息不足时替人做选择。
    """
    if not _has_dividend_adjustment(caliber):
        return []

    dividends = [d for sid, d in _load_dividend_actions(root) if sid == security_id]
    lo, hi = min(days), max(days)
    hit_days = sorted(d.isoformat() for d in dividends if lo <= d <= hi)
    if not hit_days:
        return []
    return [
        f"{security_id}: 口径 {caliber!r} 表明价格**已含分红调整**，而 "
        f"`registry/corporate-actions.jsonl` 在同一区间另有 {len(hit_days)} 条 `div`"
        f"（{hit_days[:3]}{'…' if len(hit_days) > 3 else ''}）⇒ "
        "`returns.py` 按「先复权再总回报」会**再投一次分红**，即重复计。"
        "二选一：删掉公司行动，或改用不含分红调整的价格口径。"
    ]


def _repeated_value_runs(days: Sequence[date], closes: Sequence[str]) -> list[str]:
    """相邻交易日**同值**的区间（前值填充**嫌疑**）。

    ★ 只报不拒：真实交易里连续同值也可能发生（停牌、极低流动性）。
      把它变成"拒"会误伤；把它变成"不报"则等于放走陷阱②的漏网者。
    """
    runs: list[str] = []
    i = 0
    while i < len(days):
        j = i
        while j + 1 < len(days) and closes[j + 1] == closes[i]:
            j += 1
        if j > i:
            runs.append(f"{days[i].isoformat()}..{days[j].isoformat()}={closes[i]}")
        i = j + 1
    return runs


def plan_market_rows(
    root: str | Path,
    spec: Mapping[str, Any],
    *,
    filename: str = "<spec>",
) -> tuple[list[PriceSnapshot], MarketIngestReport]:
    """**纯计算**：校验清单 → 按日历过滤 → 产出待落行与回执（**不写盘**，便于测试）。"""
    root_path = Path(root)
    report = MarketIngestReport()

    fetched_at = _require(spec, "fetched_at", filename)
    if not isinstance(fetched_at, str):
        raise MarketDataError(f"{filename}: `fetched_at` 必须是 ISO 字符串")
    try:
        fetched_dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MarketDataError(f"{filename}: `fetched_at` 不是合法 ISO 时间（{fetched_at!r}）") from exc
    if fetched_dt.tzinfo is None:
        fetched_dt = fetched_dt.replace(tzinfo=timezone.utc)

    raw_calendar = _require(spec, "calendar", filename)
    if not isinstance(raw_calendar, Sequence) or isinstance(raw_calendar, (str, bytes)):
        raise MarketDataError(f"{filename}: `calendar` 必须是日期数组")
    calendar = {_parse_day(d, f"{filename}.calendar") for d in raw_calendar}
    if not calendar:
        raise MarketDataError(
            f"{filename}: `calendar` 为空 —— 无法过滤非交易日（陷阱②）。"
            "不许退化成「不过滤直接落库」。"
        )

    close_text = str(spec.get("session_close_utc") or DEFAULT_SESSION_CLOSE_UTC)
    try:
        hh, mm = (int(x) for x in close_text.split(":", 1))
        close_at = time(hh, mm, tzinfo=timezone.utc)
    except (ValueError, TypeError) as exc:
        raise MarketDataError(f"{filename}: `session_close_utc` 非法（{close_text!r}）") from exc

    registered = {
        str(row.get("security_id"))
        for row in read_records(root_path, "securities")
        if row.get("security_id")
    }
    existing = {
        str(row.get("snapshot_id"))
        for row in read_records(root_path, "prices")
        if row.get("snapshot_id")
    }
    seq = max(
        (int(r["recorded_seq"]) for r in read_records(root_path, "prices")
         if isinstance(r.get("recorded_seq"), int)),
        default=0,
    )

    series = _require(spec, "series", filename)
    if not isinstance(series, Sequence) or isinstance(series, (str, bytes)) or not series:
        raise MarketDataError(f"{filename}: `series` 必须是非空数组")

    rows: list[PriceSnapshot] = []
    for idx, entry in enumerate(series):
        where = f"{filename}.series[{idx}]"
        if not isinstance(entry, Mapping):
            raise MarketDataError(f"{where}: 必须是对象")
        identity = _check_identity(entry, where)
        caliber = _check_caliber(entry, where)
        security_id = str(_require(entry, "expect", where).get("security_id") or "").strip()
        if not security_id:
            raise MarketDataError(f"{where}.expect: 缺 `security_id`（落库必须指向一个证券对象）")

        points = _require(entry, "points", where)
        if not isinstance(points, Sequence) or isinstance(points, (str, bytes)) or not points:
            raise MarketDataError(f"{where}: `points` 必须是非空数组")

        kept: list[tuple[date, str]] = []
        excluded: list[str] = []
        for p_idx, point in enumerate(points):
            if not isinstance(point, Mapping):
                raise MarketDataError(f"{where}.points[{p_idx}]: 必须是对象")
            day = _parse_day(_require(point, "date", f"{where}.points[{p_idx}]"), where)
            if day not in calendar:
                excluded.append(day.isoformat())
                continue
            kept.append((day, str(_require(point, "close", f"{where}.points[{p_idx}]"))))

        if not kept:
            raise MarketDataError(
                f"{where}: 全部 {len(points)} 个点都被日历剔除 —— "
                "要么日历与序列对不上，要么序列根本不是该市场的交易日（不许落空标）"
            )
        if excluded:
            report.excluded_dates[security_id] = excluded

        kept.sort(key=lambda t: t[0])
        runs = _repeated_value_runs([d for d, _ in kept], [c for _, c in kept])
        if runs:
            report.repeated_value_runs[security_id] = runs

        report.notes.extend(
            _double_count_notes(root_path, security_id, caliber, [d for d, _ in kept])
        )

        delay_minutes = entry.get("delay_minutes")
        delayed = bool(entry.get("delayed", False))
        if isinstance(delay_minutes, int) and delay_minutes > 0 and not delayed:
            delayed = True
            report.notes.append(
                f"{security_id}: 连接器给出 `delay_minutes={delay_minutes}` ⇒ 强制 `delayed=True`"
            )

        slug = re.sub(r"[^A-Za-z0-9]+", "-", caliber).strip("-").lower() or "unknown"
        if security_id not in registered:
            report.unregistered_securities.append(security_id)

        for day, close in kept:
            snapshot_id = f"snap-{security_id}-{slug}-{day.strftime('%Y%m%d')}"
            if snapshot_id in existing:
                report.snapshots_skipped += 1
                report.skipped_ids.append(snapshot_id)
                continue
            seq += 1
            occurred = datetime.combine(day, close_at)
            rows.append(
                PriceSnapshot(
                    snapshot_id=snapshot_id,
                    security_id=security_id,
                    price=close,
                    currency=identity["currency"],
                    trading_session="regular",
                    delayed=delayed,
                    adjustment_caliber_version=caliber,
                    source_id=str((spec.get("connectors") or {}).get("series") or ""),
                    occurred_at=occurred,
                    first_seen_at=fetched_dt,
                    analyzed_at=fetched_dt,
                    backfilled_at=fetched_dt if occurred.date() < fetched_dt.date() else None,
                    recorded_seq=seq,
                )
            )
            existing.add(snapshot_id)

    return rows, report


def ingest_market_file(
    root: str | Path,
    spec_path: str | Path,
    *,
    dry_run: bool = False,
) -> MarketIngestReport:
    """校验并落库**一个**行情清单。校验不过 ⇒ 抛 `MarketDataError`（**一行都不写**）。"""
    root_path = Path(root)
    path = Path(spec_path)
    spec = _load_spec(path)
    rows, report = plan_market_rows(root_path, spec, filename=path.name)
    if not dry_run and rows:
        append_records(root_path, "prices", rows)
    report.rows_written = 0 if dry_run else len(rows)
    if dry_run:
        report.notes.append(f"dry-run：应落 {len(rows)} 行，未写盘")

    if spec.get("benchmark"):
        bm_row, bm_report = plan_benchmark_row(root_path, spec, filename=path.name)
        if not bm_report.skipped and not dry_run:
            append_records(root_path, "benchmarks", [bm_row])
        report.notes.append(f"benchmark: {bm_report.summary()}")
    return report


def ingest_market_inbox(
    root: str | Path,
    *,
    dry_run: bool = False,
) -> tuple[list[str], list[str], bool, list[str]]:
    """处理投递口下**全部**行情清单（供 `ingest_step.py` 调用）。

    返回 `(produced, skipped, degraded, notes)`：

    - `produced` = 本轮**真正新写入**的 `snapshot_id`（语义与 step 1 的 `produced` 一致：
      "本轮真正新写入的对象引用"）；
    - `skipped` = 幂等命中（同 `snapshot_id` 已存在）—— **不是降级**（`Ch9 §N9.2-11`）；
    - `degraded` = 有清单**校验未通过**（该文件的整批都不落库）⇒ **显式降级**，不静默略过；
    - `notes` = 每份清单的如实回执（剔除的非交易日、相邻同值嫌疑、悬挂证券）。
    """
    root_path = Path(root)
    produced: list[str] = []
    skipped: list[str] = []
    notes: list[str] = []
    degraded = False

    for path in market_inbox_files(root_path):
        try:
            spec = _load_spec(path)
            rows, report = plan_market_rows(root_path, spec, filename=path.name)
        except MarketDataError as exc:
            degraded = True
            notes.append(f"{path.name}: **校验未通过，整批未落库** —— {exc}")
            continue
        if not dry_run and rows:
            append_records(root_path, "prices", rows)
        if spec.get("benchmark"):
            bm_row, bm_report = plan_benchmark_row(root_path, spec, filename=path.name)
            if not bm_report.skipped and not dry_run:
                append_records(root_path, "benchmarks", [bm_row])
                produced.append(f"benchmark:{bm_row.benchmark_id}")
            report.notes.append(f"benchmark: {bm_report.summary()}")
        produced.extend(r.snapshot_id for r in rows)
        skipped.extend(report.skipped_ids)
        report.rows_written = 0 if dry_run else len(rows)
        notes.append(f"{path.name}: {report.summary()}")
        if report.unregistered_securities:
            notes.append(
                f"{path.name}: 悬挂引用 {sorted(report.unregistered_securities)} 未在 "
                "`facts/securities.jsonl` 注册（已知根因：`Security.company_id` 必填 ⇒ ETF 无处注册）"
            )
    return produced, skipped, degraded, notes


# ─────────────────────────── 基准（`facts/benchmarks.jsonl`） ───────────────────────────
#
# `Ch5 §E.1` 给 AGIX 这类 ETF 定了四个字段：`non_listed_assets{value, weight, gap_note}` /
# `holdings_disclosure_lag` / `unverifiable_forecasts[]` / `sensitivity[]`。
# 其中「披露延迟」与「非上市资产明细」都是**可从公开来源实测**的事实 —— 2026-09-17 实测：
# 官网持仓页逐条列出 7 家非上市资产（名称 / % of Net Assets / Shares Held / Market Value / % NAV）
# 并明示 `Private Holdings — Data as of <日期>`，另提供 `Full Holdings .CSV`。
# ⇒ 本模块把「规则声明（`rules/benchmark.yaml`，0444 锁定）+ 实测事实（清单）」**编译**成事实行，
#   并把「披露延迟」**派生**成可复算的量（as-of 与抓取日之差），**不硬编成一句"未披露"**。
#
# ★ 交叉核对：清单声明的 `includes_non_listed_assets` 必须与 `rules/benchmark.yaml` 一致 ——
#   否则**拒**（防"事实行与规则声明打架"这种最难发现的漂移）。

BENCHMARK_RULES_REL = Path("rules") / "benchmark.yaml"
"""基准对象声明的**唯一规则真源**（0444 锁定；本模块只读它、不写）。"""


@dataclass
class BenchmarkIngestReport:
    """一次基准落库的如实回执。"""

    written: int = 0
    skipped: bool = False
    disclosure_lag: str = ""
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.skipped:
            return "幂等命中（同 as-of 的行已存在，未重复落库）"
        return f"落库 {self.written} 行；披露延迟 = {self.disclosure_lag}"


def _primary_declaration(root: str | Path) -> Mapping[str, Any]:
    """取 `rules/benchmark.yaml` 里 `benchmark_role: primary` 的那条声明。"""
    path = Path(root) / BENCHMARK_RULES_REL
    if not path.exists():
        raise MarketDataError(f"缺 {BENCHMARK_RULES_REL}（基准声明的唯一规则真源）")
    from scripts._common import _cached_yaml   # 配置必走缓存（性能纪律②）

    doc = _cached_yaml(path) or {}
    for obj in doc.get("benchmark_objects") or []:
        if isinstance(obj, Mapping) and str(obj.get("benchmark_role")) == "primary":
            return obj
    raise MarketDataError(f"{BENCHMARK_RULES_REL} 里没有 `benchmark_role: primary` 的声明")


def _derive_disclosure_lag(observed: Mapping[str, Any], fetched: datetime) -> str:
    """★ **派生**「公开持仓披露延迟」—— 填**可复算的量**，不填一句"未披露"。

    依据 = 持仓页自述的 `holdings_as_of` 与本次抓取日之差（自然日）。
    """
    as_of = _parse_day(
        _require(observed, "holdings_as_of", "benchmark.observed"),
        "benchmark.observed.holdings_as_of",
    )
    lag_days = (fetched.date() - as_of).days
    parts = [
        f"持仓页自述 as-of {as_of.isoformat()}，本次抓取 {fetched.date().isoformat()}"
        f"（滞后 {lag_days} 个自然日）",
        "含非上市资产逐条明细（Private Holdings）并提供 Full Holdings .CSV",
    ]
    page = str(observed.get("holdings_page") or "").strip()
    if page:
        parts.append(f"来源 {page}")
    return "；".join(parts)


def plan_benchmark_row(
    root: str | Path,
    spec: Mapping[str, Any],
    *,
    filename: str = "<spec>",
) -> tuple[Benchmark, BenchmarkIngestReport]:
    """把「规则声明 + 实测事实」编译成一条 `benchmarks` 事实行（**不写盘**）。"""
    decl = _primary_declaration(root)
    bm = _require(spec, "benchmark", filename)
    if not isinstance(bm, Mapping):
        raise MarketDataError(f"{filename}.benchmark: 必须是对象")
    where = f"{filename}.benchmark"

    benchmark_id = str(_require(bm, "benchmark_id", where)).strip()
    if not benchmark_id:
        raise MarketDataError(f"{where}: `benchmark_id` 不得为空")

    declared = bool(decl.get("includes_non_listed_assets", False))
    claimed = bool(bm.get("includes_non_listed_assets", declared))
    if claimed != declared:
        raise MarketDataError(
            f"{where}: `includes_non_listed_assets={claimed}` 与 "
            f"{BENCHMARK_RULES_REL} 的声明（{declared}）**不一致** —— "
            "规则层与事实行不得打架（两者都是真源，冲突必须当场暴露而非二选一）"
        )

    observed = _require(bm, "observed", where)
    if not isinstance(observed, Mapping):
        raise MarketDataError(f"{where}.observed: 必须是对象")

    fetched_text = _require(spec, "fetched_at", filename)
    fetched = datetime.fromisoformat(str(fetched_text).replace("Z", "+00:00"))
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)

    report = BenchmarkIngestReport()
    notes: list[str] = []

    # ── `Ch5 §E.1` 四字段：**含非上市资产时全部必填**（与 history_guard 判据①②③④⑤ 同口径）──
    non_listed: list[dict[str, Any]] = []
    if claimed:
        entries = observed.get("non_listed_assets")
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)) or not entries:
            raise MarketDataError(
                f"{where}.observed: 声明含非上市资产但 `non_listed_assets` 为空 —— "
                "非上市资产无法独立建模，必须走缺口字段（`Ch5 §E.1`）"
            )
        for idx, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                raise MarketDataError(f"{where}.observed.non_listed_assets[{idx}]: 必须是对象")
            for key in ("name", "value", "weight", "gap_note"):
                if not entry.get(key):
                    raise MarketDataError(
                        f"{where}.observed.non_listed_assets[{idx}]: 缺 `{key}` —— "
                        "`Ch5 §E.1` 的 `non_listed_assets{value, weight, gap_note}`（此处另收 name）"
                    )
            non_listed.append(dict(entry))

        sensitivity = bm.get("sensitivity")
        if not isinstance(sensitivity, Sequence) or isinstance(sensitivity, (str, bytes)) or not sensitivity:
            raise MarketDataError(
                f"{where}: 含非上市资产但 `sensitivity` 为空 —— "
                "非上市资产走「缺口 + 敏感性」（`Ch5 §E.1` / `§J8`）"
            )

        lag = _derive_disclosure_lag(observed, fetched)
        report.disclosure_lag = lag

    if "unverifiable_forecasts" not in bm:
        raise MarketDataError(
            f"{where}: 缺 `unverifiable_forecasts` 字段 —— 可为空列表，但**必须显式**"
            "（`Ch5 §E.1`：无法独立核验的预测须有落点）"
        )

    coverage_profile: dict[str, Any] = dict(decl.get("coverage_profile") or {})
    for key, value in (
        # ★★ 2026-09-17 冷启动实测补（登记见 reports/cold_start_e2e_2026-09-17.md）：
        #   `Benchmark` 模型**没有** `security_id` 字段（`extra="forbid"`），而
        #   `compute/driver.py::_resolve_security` 与 `decision/run_decide.py::_resolve_benchmark_security`
        #   都以 `benchmark["security_id"]` 为**第一优先**解析基准证券 ——
        #   即"声明在代码里、字段不在契约里"。缺它 ⇒ 行情有 ≥2 个证券时基准**永远解析不出**
        #   ⇒ 阶段门 step 5/6 恒 gap。此处把清单声明的证券落进**开放字典** `coverage_profile`
        #   （与 `unit_nav` / `tracking_index` 同落位、同性质：观测到的事实），
        #   并让两个解析口把它作为回落 —— **不改 `Benchmark` 契约、不手工写真源行**。
        ("security_id", bm.get("security_id")),
        ("unit_nav", observed.get("unit_nav")),
        ("unit_nav_date", observed.get("unit_nav_date")),
        ("unit_nav_currency", observed.get("unit_nav_currency")),
        ("tracking_index", observed.get("tracking_index")),
        ("listing_date", observed.get("listing_date")),
        ("fetched_via", (spec.get("connectors") or {}).get("benchmark") or ""),
        # ★ 非上市资产的**披露状态**取规则层的声明（单一真源），不在这里另写一份。
        ("non_listed_disclosure_state", (decl.get("non_listed_assets") or {}).get("disclosure_state")),
        ("holdings_page_as_of", observed.get("holdings_as_of")),
    ):
        if value:
            coverage_profile[key] = value

    existing = [r for r in read_records(root, "benchmarks") if r.get("benchmark_id") == benchmark_id]
    same_as_of = any(
        (r.get("coverage_profile") or {}).get("holdings_page_as_of") == observed.get("holdings_as_of")
        for r in existing
    )
    if same_as_of:
        row = Benchmark(benchmark_id=benchmark_id)   # 占位，调用方据 `skipped` 忽略
        report.skipped = True
        return row, report

    # ★ 形态由 `schema.models.Benchmark` 决定：`non_listed_assets` / `sensitivity` 都是
    #   `dict[str, Any]`（**不是 list**）。而 `history_guard._as_entries()` 把 mapping 当作
    #   **一条**条目 ⇒ 逐条明细放在内层 `items`，最外层带 `gap_note`（判据② 只强制这一键）。
    non_listed_block: dict[str, Any] = {}
    if claimed:
        total = observed.get("non_listed_total_weight")
        non_listed_block = {
            "disclosure_state": (decl.get("non_listed_assets") or {}).get("disclosure_state"),
            "as_of": observed.get("holdings_as_of"),
            "total_weight": total,
            "gap_note": (
                f"非上市资产 {len(non_listed)} 条"
                + (f"，合计 {total} NAV" if total else "")
                + "；估值为**公司自报**、不可独立复核 ⇒ 只记缺口，不给独立估值"
            ),
            "items": non_listed,
        }

    row = Benchmark(
        benchmark_id=benchmark_id,
        benchmark_role=BenchmarkRole(str(decl.get("benchmark_role") or "primary")),
        coverage_profile=coverage_profile,
        includes_non_listed_assets=claimed,
        non_listed_assets=non_listed_block,
        sensitivity={
            "basis": str(bm.get("sensitivity_basis") or "非上市部分按估值折让计敏感性"),
            "items": list(bm.get("sensitivity") or []),
        },
        holdings_disclosure_lag=report.disclosure_lag or None,
        unverifiable_forecasts=list(bm.get("unverifiable_forecasts") or []),
        modeled_coverage=bm.get("modeled_coverage"),
        unmodeled_parts=list(bm.get("unmodeled_parts") or []),
        claims_complete_forecast=bool(bm.get("claims_complete_forecast", False)),
        freeze_status=decl.get("freeze_status") or "unfrozen",
        return_basis=decl.get("return_basis") or {},
        return_basis_version=str(decl.get("return_basis_version") or "v1"),
        benchmark_semantics=str(decl.get("benchmark_semantics") or ""),
        return_source=str(decl.get("return_source") or "fund_market_price"),
        proxy_index_used=bool(decl.get("proxy_index_used", False)),
        change_records=list(bm.get("change_records") or []),
        first_seen_at=fetched,
        analyzed_at=fetched,
    )
    for note in notes:
        report.notes.append(note)
    return row, report


if __name__ == "__main__":  # pragma: no cover - 手工入口
    import sys

    _root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("system")
    _files = market_inbox_files(_root)
    if not _files:
        print(f"[market_data] 投递口无行情清单（{_root}/raw/inbox/market_data_*.json）")
        raise SystemExit(0)
    _produced, _skipped, _degraded, _notes = ingest_market_inbox(_root)
    for _n in _notes:
        print(f"[market_data] {_n}")
    print(f"[market_data] produced={len(_produced)} skipped={len(_skipped)} degraded={_degraded}")
    raise SystemExit(1 if _degraded else 0)
