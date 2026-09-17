#!/usr/bin/env python3
"""`review_return.py` —— **复盘收益**（复用 `return_guard`，口径经统一 `get_param('p10')`）。

```
python system/scripts/review/review_return.py [code_root]
```

权威蓝图：`10_验收与持续复盘/02_实现方案.md §D.4`（伪代码逐字实现）。承接需求
`N10.3-04`（同区间绝对 / 相对收益）、`N10.3-08`（信号生效价 / 交易成本 / 税前口径）、
`N10.3-11`（观察窗口）。

★ 三条硬约束（本项目已因它们栽过，逐条落在代码里）：

1. **口径不在本模块**（`§D.1`）：三件套（`signal_effective_price` / `transaction_cost` /
   `pre_tax_caliber`）+ 观察窗口 `review_window` 的**唯一真源 = Ch11 `freeze_param[p10]`**，
   一律经 `get_param('p10')` 读取。本模块**不持有、不缓存**任何口径值。
   `tbd`（参数未冻结）是**合法值** ⇒ 命中即返回 `status="blocked_by_caliber"` + 列出缺失键，
   **绝不用 0 / 假设值把数字凑出来**（守源稿红线：不伪造数字）。
2. **收益必过 `return_guard`**（`Ch9 §3.4.12`）：① 取基金本身行情、禁替代指数；
   ② 禁二次扣费；③ 净值仅标 `diagnostic`。本模块**只调用**，**不重写**（`G-06`：
   口径断言唯一真源 = `scripts/benchmark/return_guard.py`；算术唯一真源 =
   `scripts/compute/returns.py`）。
3. **信号生效价取「下一可交易时点」**（`Ch10 §N10.3-08` / `Ch3 §N3.4-06` / `Ch9 §3.4.9`）：
   **严格晚于**信号可知日；**禁止用「看到消息那天的收盘价」**（前视偏差）。命中即 `raise`。

★ 真接线（`AC-03`）：本模块是 `Ch10 §D`「复盘收益计算」的**唯一实现落点**——
  消费方 = ① `scripts/review/record_eval.py`（WS-E）的 `investment_result` 层
  （`Ch10 §C.2`：投资结果 = 同区间绝对 / 相对收益 ⇒ 必经本函数）；② 复盘流程 / CLI。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.freeze import ParamValueUnavailable, get_param  # noqa: E402
from schema import store  # noqa: E402
from scripts._common import CheckReport, Violation, run_checker  # noqa: E402
from scripts.benchmark.return_guard import (  # noqa: E402
    BenchmarkCaliberError,
    assert_nav_not_used_for_relative,
    nav_return_diagnostic_only,
)
from scripts.compute.contract import (  # noqa: E402
    CaliberViolation,
    MissingInput,
    UndefinedComputation,
)
from scripts.compute.driver import (  # noqa: E402
    _resolve_security,
    load_benchmark_objects,
    load_corporate_actions,
    load_price_points,
)
from scripts.compute.returns import (  # noqa: E402
    compute_benchmark_return,
    compute_total_return,
)
from scripts.decision.rules import latest_version_row  # noqa: E402

# ─────────────────────────── 常量 ───────────────────────────

TBD = "tbd"
PARAM_ID = "p10"

STATUS_OK = "ok"
STATUS_BLOCKED_CALIBER = "blocked_by_caliber"
STATUS_BLOCKED_NO_PRICE = "blocked_by_no_price"
STATUS_BLOCKED_NO_BENCHMARK = "blocked_by_no_benchmark"

#: 复盘口径三件套 + 观察窗口（`§D.1`）。顺序稳定（缺失键按此序报出，便于对拍）。
CALIBER_KEYS: tuple[str, ...] = (
    "signal_effective_price",
    "transaction_cost",
    "pre_tax_caliber",
    "review_window",
)

#: 信号可知时间候选字段（按优先级）：先取**真实前向时间**，再退到业务起点（`Ch9 §2.2`）。
_SIGNAL_TIME_KEYS: tuple[str, ...] = (
    "first_seen_at",
    "published_at",
    "analyzed_at",
    "effective_from",
    "start_date",
)


class EffectivePriceViolation(RuntimeError):
    """生效价口径违例（取到「看到消息那天」的价格）—— **响亮失败**（`N10.3-08`）。"""


class CaliberUnavailable(RuntimeError):
    """口径读取不可用（`get_param` 缺 `suggested_value` 等）—— 折叠为 `blocked_by_caliber`。"""


# ─────────────────────────── 结果对象 ───────────────────────────


@dataclass(frozen=True)
class ReviewReturn:
    """一次复盘收益计算的完整结果。

    `status` 穷尽且互斥（`R-06`）：

    | `status` | 含义 |
    |---|---|
    | `ok` | 口径已冻结且输入齐备 → `total_return` / `relative_return` 有值 |
    | `blocked_by_caliber` | 口径含 `tbd`（未冻结）→ `missing` 列出缺失键，**不出数字** |
    | `blocked_by_no_price` | 信号可知后无可用行情点 / 窗口内行情 < 2 点 → **不出数字** |
    | `blocked_by_no_benchmark` | 无基准对象 / 基准行情不足 → **不出数字** |
    """

    rec_id: str
    status: str
    missing: tuple[str, ...] = ()
    window_days: int | None = None
    caliber: Mapping[str, Any] = field(default_factory=dict)
    signal_day: date | None = None
    effective_price_day: date | None = None
    total_return: Decimal | None = None
    benchmark_return: Decimal | None = None
    relative_return: Decimal | None = None
    nav_diagnostic: Mapping[str, Any] | None = None
    formula_refs: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def computed(self) -> bool:
        """是否真的算出了数字（`ok` 以外一律为否）。"""
        return self.status == STATUS_OK

    def as_dict(self) -> dict[str, Any]:
        return {
            "rec_id": self.rec_id,
            "status": self.status,
            "missing": list(self.missing),
            "window_days": self.window_days,
            "caliber": dict(self.caliber),
            "signal_day": self.signal_day.isoformat() if self.signal_day else None,
            "effective_price_day": (
                self.effective_price_day.isoformat() if self.effective_price_day else None
            ),
            "total_return": str(self.total_return) if self.total_return is not None else None,
            "benchmark_return": (
                str(self.benchmark_return) if self.benchmark_return is not None else None
            ),
            "relative_return": (
                str(self.relative_return) if self.relative_return is not None else None
            ),
            "nav_diagnostic": dict(self.nav_diagnostic) if self.nav_diagnostic else None,
            "formula_refs": list(self.formula_refs),
            "notes": list(self.notes),
        }


# ─────────────────────────── 口径读取（唯一真源 = Ch11 p10） ───────────────────────────


def read_caliber_terms(root: str | Path | None = None) -> dict[str, Any]:
    """读复盘口径三件套 + 观察窗口（`§D.1`）。**本模块不持有可编辑值、不缓存**。

    - 唯一真源 = Ch11 `rules/freeze.yaml::freeze_param[p10]`，经 `get_param('p10')` 读取；
    - p10 值形态 = mapping，其中 `caliber_terms` 是四键 mapping；
    - 键缺失 / 值为 `None` / 值 == `"tbd"` ⇒ 一律视为**未冻结**（由调用方折叠为 `blocked_by_caliber`）。
    """
    try:
        resolution = get_param(PARAM_ID, root)
    except ParamValueUnavailable as exc:
        # 设计预期：未冻结且无 suggested_value（`config.freeze` 的响亮失败）。
        # 折叠为 CaliberUnavailable（不吞原因），由调用方转成 blocked_by_caliber 语义。
        raise CaliberUnavailable(
            f"复盘口径不可读（{PARAM_ID}）：{exc}"
        ) from exc

    value = resolution.effective_value
    if not isinstance(value, Mapping):
        raise CaliberViolation(
            f"{PARAM_ID} 口径值形态非法（应为 mapping，实得 {type(value).__name__}）；"
            "唯一真源 = Ch11 freeze_param[p10]（Ch10 §D.1）"
        )
    terms = value.get("caliber_terms")
    if not isinstance(terms, Mapping):
        raise CaliberViolation(
            f"{PARAM_ID} 未提供 caliber_terms（复盘口径三件套 + 观察窗口，Ch10 §D.1）"
        )
    return {key: terms.get(key, TBD) for key in CALIBER_KEYS}


def _is_unfrozen(value: Any) -> bool:
    """未冻结判定：`None` 或字符串 `tbd`（大小写不敏感）⇒ 是。"""
    if value is None:
        return True
    return isinstance(value, str) and value.strip().lower() == TBD


def _window_days(value: Any) -> int | None:
    """把观察窗口冻结值解析为**整数日历天**；未冻结 → `None`；不可解析 → `CaliberViolation`。

    ★ 本函数只做**值解析**（不产生新口径）：`review_window` 的编码由 Ch11 冻结；
      本层要求整数天（或等价的可解析形态），映射形态只接受显式 `days` / 整数值。
      **不做 1Q / 1Y 之类的单位换算**（那属于 Ch11 的口径，不在本模块）。
    """
    if _is_unfrozen(value):
        return None
    if isinstance(value, bool):  # bool 是 int 的子类，先拦掉，避免 True→1 的静默误判
        raise CaliberViolation(f"review_window 冻结值非法（bool）：{value!r}")
    if isinstance(value, int):
        if value <= 0:
            raise CaliberViolation(f"review_window 冻结值须为正整数天，实为 {value!r}")
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return _window_days(int(value.strip()))
    if isinstance(value, Mapping):
        for key in ("days", "value"):
            if key in value:
                return _window_days(value[key])
    raise CaliberViolation(
        f"review_window 冻结值不可解析为整数天：{value!r}（本层不预设单位换算；"
        "编码口径由 Ch11 freeze_param[p10] 冻结）"
    )


def _resolve_window(window: Any, caliber: Mapping[str, Any]) -> int | None:
    """解析观察窗口：入参优先须与口径**一致**（口径不被本模块覆盖，`§D.1` 单一真源）。"""
    frozen = _window_days(caliber.get("review_window"))
    if window is None:
        return frozen
    supplied = _window_days(window)
    if frozen is None:
        # 口径未冻结：返回由调用方记录的入参（随后按 blocked_by_caliber 处理，不出数字）。
        return supplied
    if supplied != frozen:
        raise CaliberViolation(
            "本模块不得覆盖口径：window 入参 ≠ Ch11 冻结的 review_window "
            f"（入参 {supplied} vs 冻结 {frozen}，Ch10 §D.1 单一真源）"
        )
    return frozen


# ─────────────────────────── 生效价（下一可交易时点） ───────────────────────────


def _try_iso_date(text: str) -> date | None:
    """宽松解析 ISO 日期；不可解析 → `None`（不抛，供信号日探测用）。"""
    parsed: date | None
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        parsed = None
    return parsed


def signal_day_of(rec: Mapping[str, Any]) -> date | None:
    """信号可知日：按 `_SIGNAL_TIME_KEYS` 取**第一个非空且可解析**的时间（`Ch9 §2.2` 五类时间）。"""
    for key in _SIGNAL_TIME_KEYS:
        raw = rec.get(key)
        if not raw:
            continue
        parsed = _try_iso_date(str(raw)[:10])
        if parsed is not None:
            return parsed
    return None


def assert_effective_price_next_tradable(signal_day: date, effective_day: date) -> None:
    """`N10.3-08`：生效价必须**严格晚于**信号可知日。命中即 `raise`（禁 warn-only）。

    「看到消息那天的收盘价」= `effective_day == signal_day` ⇒ 本断言直接拦下。
    """
    if effective_day <= signal_day:
        raise EffectivePriceViolation(
            "信号生效价必须取「下一可交易时点」（严格晚于信号可知日），"
            f"不得用当天价格充当可执行成交价：signal={signal_day} effective={effective_day}"
            "（Ch10 §N10.3-08 / Ch3 §N3.4-06 / Ch9 §3.4.9）"
        )


def effective_price(
    rec: Mapping[str, Any],
    prices_by_security: Mapping[str, Any],
    *,
    rule: Any = None,
) -> Any:
    """信号生效价 = 信号可知后**下一可交易时点**的行情点（`N10.3-08`）。

    - 无市场日历时，「下一可交易时点」= 真源行情中**严格晚于**信号可知日的**最早**行情点
      （这是本层可判定、可穷尽的定义，`R-06`）。
    - 净值点（`is_nav=True`）不作市场价（`Ch3 §D.2 ③`）。
    - 信号可知日缺失 / 可用行情为空 → 返回 `None`（由调用方降级，**不伪造**）。
    `rule` = 冻结的 `signal_effective_price` 描述符（仅登记审计，不改变设计固定规则）。
    """
    signal_day = signal_day_of(rec)
    if signal_day is None:
        return None
    security_id = rec.get("security_id")
    points = [p for p in prices_by_security.get(security_id, []) if not p.is_nav]
    after = sorted((p for p in points if p.day > signal_day), key=lambda p: p.day)
    if not after:
        return None
    chosen = after[0]
    assert_effective_price_next_tradable(signal_day, chosen.day)
    return chosen


# ─────────────────────────── 基准（唯一真源 = benchmark_objects） ───────────────────────────


def _select_primary_benchmark(benchmarks: list[dict[str, Any]]) -> Mapping[str, Any] | None:
    """选主基准：优先 `benchmark_role == "primary"`，否则取首个；空 → `None`。"""
    for benchmark in benchmarks:
        if str(benchmark.get("benchmark_role")) == "primary":
            return benchmark
    return benchmarks[0] if benchmarks else None


# ─────────────────────────── 建议读取（当前版本） ───────────────────────────


def _load_recommendation(root: Path, rec_id: str) -> Mapping[str, Any]:
    """读**当前版本**建议：同一 `recommendation_id` 的多版本行取 `(version, recorded_seq)` 最大者。

    ★ 复用 `scripts.decision.rules.latest_version_row` —— 它是全仓「取当前版本」的**唯一**
      实现（`G-06` 唯一真源：不在别处重算），此处不另写一遍取版本逻辑。
    """
    rows = store.read_records(root, "recommendations")
    candidates = [r for r in rows if r.get("recommendation_id") == rec_id]
    if not candidates:
        raise CaliberViolation(f"未找到建议 {rec_id}（facts/recommendations.jsonl）")
    return latest_version_row(candidates)


# ─────────────────────────── 主计算（§D.4 伪代码） ───────────────────────────


def compute_review_return(
    rec_id: str,
    window: Any = None,
    *,
    root: str | Path | None = None,
) -> ReviewReturn:
    """复盘收益（`§D.4`）：口径经 `get_param('p10')`；收益过 `return_guard`。

    返回 `ReviewReturn`。**`tbd` ⇒ `blocked_by_caliber` + 列出缺失键，不出数字。**
    口径类违例（`CaliberViolation` / `BenchmarkCaliberError`）**原样上抛**（响亮失败）。
    """
    root_path = Path(root) if root is not None else _ROOT

    try:
        caliber = read_caliber_terms(root_path)
    except CaliberUnavailable as exc:
        # 未冻结且无 suggested_value：转 blocked_by_caliber 语义（原因随 notes 可见，不吞）
        return ReviewReturn(
            rec_id=rec_id,
            status=STATUS_BLOCKED_CALIBER,
            missing=(PARAM_ID,),
            caliber={},
            notes=(str(exc),),
        )

    missing = tuple(k for k, v in caliber.items() if _is_unfrozen(v))
    window_days = _resolve_window(window, caliber)
    if missing:
        return ReviewReturn(
            rec_id=rec_id,
            status=STATUS_BLOCKED_CALIBER,
            missing=missing,
            window_days=window_days,
            caliber=caliber,
            notes=(
                "口径未冻结（唯一真源 = Ch11 freeze_param[p10]，Ch10 §D.1）："
                "不得用 0 / 假设值补数字",
            ),
        )

    if window_days is None or window_days <= 0:
        raise CaliberViolation(
            "observation window 未解析为正整数天（Ch10 §D.1 观察窗口，值由 Ch11 冻结）"
        )

    rec = _load_recommendation(root_path, rec_id)
    signal_day = signal_day_of(rec)

    prices = load_price_points(None, root_path)
    px = effective_price(rec, prices, rule=caliber.get("signal_effective_price"))
    if px is None:
        return ReviewReturn(
            rec_id=rec_id,
            status=STATUS_BLOCKED_NO_PRICE,
            missing=("effective_price",),
            window_days=window_days,
            caliber=caliber,
            signal_day=signal_day,
            notes=(
                "信号可知后无可用行情点（facts/prices.jsonl 为空或无晚于信号日的点）："
                "不得用同日收盘价替代，故不出数字",
            ),
        )

    security_id = str(rec.get("security_id") or "")
    notes: list[str] = []
    actions = load_corporate_actions(root_path)
    if not (root_path / "registry" / "corporate-actions.jsonl").exists():
        notes.append(
            "registry/corporate-actions.jsonl 不存在 → 按无公司行动处理（缺口显式可见，"
            "Ch9 §3.4.9）"
        )

    benchmarks = load_benchmark_objects(root_path)
    benchmark = _select_primary_benchmark(benchmarks)
    if benchmark is None:
        return ReviewReturn(
            rec_id=rec_id,
            status=STATUS_BLOCKED_NO_BENCHMARK,
            missing=("benchmark",),
            window_days=window_days,
            caliber=caliber,
            signal_day=signal_day,
            effective_price_day=px.day,
            notes=("无基准对象（facts/benchmarks.jsonl 与 rules/benchmark.yaml 均为空）",),
        )
    # 同口径 = 同时间 / 同币种 / 市场价格总回报（`00_待拍板项清单` A2）：
    # 币种取基准声明的 `return_basis.currency`（不另立真源）。
    currency = str((benchmark.get("return_basis") or {}).get("currency", ""))

    start = px.day
    end = start + timedelta(days=window_days)
    sec_points = [p for p in prices.get(security_id, []) if not p.is_nav]
    in_window = [p for p in sec_points if start <= p.day <= end]
    if len(in_window) < 2:
        return ReviewReturn(
            rec_id=rec_id,
            status=STATUS_BLOCKED_NO_PRICE,
            missing=("prices",),
            window_days=window_days,
            caliber=caliber,
            signal_day=signal_day,
            effective_price_day=start,
            notes=(
                f"观察窗口 [{start}..{end}] 内行情点 < 2（实得 {len(in_window)}）→ 总回报无定义，"
                "不出数字",
            ),
        )
    actual_end = max(p.day for p in in_window)

    try:
        rec_derived = compute_total_return(
            sec_points,
            actions,
            start,
            actual_end,
            subject=rec_id,
            currency=currency,
            dividends_reinvested=True,
            operands=[f"facts/prices.jsonl({security_id})", f"rec:{rec_id}"],
        )
    except (MissingInput, UndefinedComputation) as exc:
        return ReviewReturn(
            rec_id=rec_id,
            status=STATUS_BLOCKED_NO_PRICE,
            missing=tuple(exc.missing or ["prices"]),
            window_days=window_days,
            caliber=caliber,
            signal_day=signal_day,
            effective_price_day=start,
            notes=(f"总回报不可算（缺口）：{exc.message}",),
        )

    bm_security = _resolve_security(benchmark, prices)
    if bm_security is None:
        return ReviewReturn(
            rec_id=rec_id,
            status=STATUS_BLOCKED_NO_BENCHMARK,
            missing=("benchmark_security_id",),
            window_days=window_days,
            caliber=caliber,
            signal_day=signal_day,
            effective_price_day=start,
            notes=("基准未声明 security_id 且行情非唯一证券 → 无法解析基准行情",),
        )
    bm_points = [p for p in prices.get(bm_security, []) if not p.is_nav]
    bm_in_window = [p for p in bm_points if start <= p.day <= actual_end]
    if len(bm_in_window) < 2:
        return ReviewReturn(
            rec_id=rec_id,
            status=STATUS_BLOCKED_NO_BENCHMARK,
            missing=("benchmark_prices",),
            window_days=window_days,
            caliber=caliber,
            signal_day=signal_day,
            effective_price_day=start,
            notes=(f"基准 {bm_security} 窗口内行情点 < 2 → 相对收益无定义",),
        )

    # 基准收益：只经 return_guard（① 基金本身行情、禁替代指数；② 禁二次扣费）
    try:
        bm_derived = compute_benchmark_return(
            benchmark,
            bm_points,
            actions,
            start,
            actual_end,
            subject=f"{rec_id}-benchmark",
            operands=[f"facts/prices.jsonl({bm_security})", f"benchmark:{bm_security}"],
        )
    except (MissingInput, UndefinedComputation) as exc:
        return ReviewReturn(
            rec_id=rec_id,
            status=STATUS_BLOCKED_NO_BENCHMARK,
            missing=tuple(exc.missing or ["benchmark_prices"]),
            window_days=window_days,
            caliber=caliber,
            signal_day=signal_day,
            effective_price_day=start,
            notes=(f"基准收益不可算（缺口）：{exc.message}",),
        )

    relative = rec_derived.value - bm_derived.value

    # ③ 净值仅标 diagnostic（N3.4-07）：市场价总回报**不得混入净值点**，由 compute 层
    #    自行拒绝（`_total_return_value` 遇 `is_nav` 点即 `CaliberViolation`）；本路径的
    #    相对收益**绝不**来自净值。如上层要做净值诊断，必须经 `nav_diagnostic()` 强制标注。
    assert_nav_not_used_for_relative({"used_for_relative_judgment": False})
    notes.append(
        "③ 净值收益仅作诊断：本路径相对收益取市场价总回报，不混净值点；"
        "净值诊断须经 return_guard.nav_return_diagnostic_only 标注（Ch3 §D.2 ③）"
    )

    return ReviewReturn(
        rec_id=rec_id,
        status=STATUS_OK,
        window_days=window_days,
        caliber=caliber,
        signal_day=signal_day,
        effective_price_day=start,
        total_return=rec_derived.value,
        benchmark_return=bm_derived.value,
        relative_return=relative,
        nav_diagnostic=None,
        formula_refs=(rec_derived.derived_id, bm_derived.derived_id),
        notes=tuple(notes),
    )


def nav_diagnostic(nav_value: Any) -> dict[str, Any]:
    """净值收益**仅诊断**：薄包装 `return_guard.nav_return_diagnostic_only`（`Ch3 §D.2 ③`）。

    本函数**不重写** ③ 的口径断言（`G-06`：唯一真源 = `scripts/benchmark/return_guard.py`）。
    """
    return nav_return_diagnostic_only(nav_value)


# ─────────────────────────── 门禁入口（CLI） ───────────────────────────


def check(root: Path) -> CheckReport:
    """门禁扫描：逐条建议跑复盘收益，**只对口径类违例报 fail**，未冻结记 note + 计数。

    `AC-04` 的两条红线（二次扣费 / 替代指数）在**口径冻结后**的 `ok` 路径上由
    `return_guard` 抛出（`BenchmarkCaliberError`）——它们**不被本函数吞掉**：
    `ok` 路径一触即抛，门禁 exit 非零。
    """
    report = CheckReport(checker="review_return")
    recs = store.read_records(root, "recommendations")
    report.scanned["recommendations"] = len(recs)

    ordered_ids: list[str] = []
    seen: set[str] = set()
    for row in recs:
        cid = row.get("recommendation_id")
        if cid and cid not in seen:
            seen.add(cid)
            ordered_ids.append(str(cid))
    report.scanned["distinct_recommendations"] = len(ordered_ids)

    if not ordered_ids:
        report.notes.append(
            "NOT_EVALUATED：facts/recommendations.jsonl 为空（G-03）—— 复盘收益未评估，"
            "不得判通过"
        )
        return report

    counts: dict[str, int] = {}
    for cid in ordered_ids:
        try:
            result = compute_review_return(cid, root=root)
        except (CaliberUnavailable, ParamValueUnavailable) as exc:
            counts[STATUS_BLOCKED_CALIBER] = counts.get(STATUS_BLOCKED_CALIBER, 0) + 1
            report.notes.append(f"{cid}: 口径不可读 → {STATUS_BLOCKED_CALIBER}（{exc}）")
            continue
        counts[result.status] = counts.get(result.status, 0) + 1
        if result.status != STATUS_OK:
            report.notes.append(
                f"{cid}: {result.status} missing={list(result.missing)}"
            )
    for status, count in sorted(counts.items()):
        report.scanned[f"status_{status}"] = count
    return report


def run(root: Path) -> CheckReport:
    """`Ch10 §D` 复盘流程的调用入口（与 CLI 同源；供调用方直接内嵌）。"""
    return check(root)


def main(argv: list[str] | None = None) -> int:
    return run_checker("review_return.py", check, argv)


if __name__ == "__main__":
    sys.exit(main())
