#!/usr/bin/env python3
"""`capability_source.py` —— **投资能力结论的唯一来源 = 前向记录流**（`Ch10 §E.3`）。

```
python system/scripts/review/capability_source.py [code_root]
```

权威蓝图：`10_验收与持续复盘/02_实现方案.md §E.3`（伪代码逐字实现）。承接需求
`N10.3-10`（回放收益不得作为投资能力结论）、`N10.3-11`（前向流真实时间戳、不可回填）、
`N10.3-09`（`replay_usage` 只读枚举）。

★ 三条硬约束：

1. **投资能力结论只能来自前向记录流**（`N10.3-10`）：任何 `source != "forward_advice_stream"`
   的能力结论（尤其「回放收益」）⇒ **命中即 `raise`**（`G-01`），**禁 warn-only**。
2. **`replay_usage ∈ {process, data_timing, update_logic}`**（只读枚举，`N10.3-09`）：
   回放产出结论**只限**这三类用途；越界即 `raise`。
3. **取版本防前视**（`§E.2`）：按业务键取 `recorded_seq` 最大 **且** `first_seen_at ≤ asof`
   的版本；补入资料记 `backfilled_at`，其**不得**出现在发生期 —— 命中即 `raise`（`N10.3-11`）。

★ 真接线（`AC-03`）：能力结论/回放产物在**展示层**与**验收层**消费本模块的断言
  （`Ch10 §F.3 test_replay_not_capability` / `§E.3`）；门禁入口 = `check()`（CLI 同源）。
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from schema import store  # noqa: E402
from scripts._common import CheckReport, Violation, run_checker  # noqa: E402

#: 回放用途**只读枚举**（`§E.1` / `N10.3-09`）。回放产出结论只限这三类。
REPLAY_USAGE_ALLOWED: frozenset[str] = frozenset({"process", "data_timing", "update_logic"})

#: 投资能力结论的**唯一**合法来源（`§E.3` / `N10.3-10`）。
FORWARD_STREAM_SOURCE = "forward_advice_stream"

#: 前向建议流的业务键（`§E.2` 取版本按业务键分组）。
FORWARD_BUSINESS_KEY: tuple[str, ...] = ("recommendation_id",)

#: 能力结论对象文件（**视图 / 结论层**，`Ch10 §A.2`；非真源 stem，**不落 `facts/`** ——
#: `facts/` 下的 JSONL 不得增删改名，`Ch9 §3.3.3`。故不走 `schema.store.read_records`）。
CONCLUSIONS_REL = ("views", "capability_conclusions.jsonl")


class CapabilitySourceViolation(RuntimeError):
    """能力结论来源非法（回放收益被当作投资能力结论）—— **响亮失败**（`N10.3-10`）。"""


class ReplayUsageViolation(RuntimeError):
    """`replay_usage` 越界 —— **响亮失败**（`N10.3-09`）。"""


class ForwardStreamViolation(RuntimeError):
    """前向记录流被回填 / 时间戳不可核 —— **响亮失败**（`N10.3-11`）。"""


# ─────────────────────────── 只读枚举：replay_usage ───────────────────────────


def is_allowed_replay_usage(value: Any) -> bool:
    """`replay_usage` 是否落在只读枚举内（`N10.3-09`）。"""
    return isinstance(value, str) and value in REPLAY_USAGE_ALLOWED


def assert_replay_usage_allowed(value: Any) -> None:
    """越界即 `raise`（命中即 fail，`G-01`）。"""
    if not is_allowed_replay_usage(value):
        raise ReplayUsageViolation(
            f"replay_usage 越界: {value!r}；合法（只读枚举）= {sorted(REPLAY_USAGE_ALLOWED)}"
            "（Ch10 §E.1 / N10.3-09）"
        )


# ─────────────────────────── 读取 ───────────────────────────


def _read_view_jsonl(path: Path) -> list[dict[str, Any]]:
    """读**视图 / 结论层** JSONL（非真源 stem）。文件缺失 → 空列表；坏行 → 响亮失败。"""
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno} 不是合法 JSON: {exc}") from exc
    return out


def load_capability_conclusions(root: str | Path | None = None) -> list[dict[str, Any]]:
    """加载「投资能力结论」对象（`§E.3`）。

    来源 = `views/capability_conclusions.jsonl`（**结论层**，非真源 stem）；缺失 → `[]`
    （由 `check()` 记为 `not_evaluated`，**不判通过**，`G-03`）。
    """
    base = Path(root) if root is not None else _ROOT
    return _read_view_jsonl(base.joinpath(*CONCLUSIONS_REL))


def load_forward_stream(root: str | Path | None = None) -> list[dict[str, Any]]:
    """加载前向建议流的**真源子集** = `facts/recommendations.jsonl`（`§E.3`）。

    真实时间戳、不可回填（`N10.3-07/11`）。经 `schema.store.read_records` 读真源
    （**不另立解析路径**，`G-06`）。
    """
    base = Path(root) if root is not None else _ROOT
    return store.read_records(base, "recommendations")


# ─────────────────────────── 断言 ①：能力结论只来自前向流 ───────────────────────────


def assert_capability_from_forward_only(root: str | Path | None = None) -> None:
    """投资能力结论**只能**读 `forward_advice_stream`（`N10.3-10`）。

    逐条检查 `load_capability_conclusions()`：`source != FORWARD_STREAM_SOURCE` ⇒ `raise`。
    空结论集 → 不 `raise`（无可核对象由 `check()` 记 `not_evaluated`，`G-03`）。
    """
    for conclusion in load_capability_conclusions(root):
        source = conclusion.get("source")
        if source != FORWARD_STREAM_SOURCE:
            raise CapabilitySourceViolation(
                "回放收益不得作为投资能力结论（N10.3-10）："
                f"conclusion={conclusion.get('conclusion_id')!r} "
                f"source={source!r}（合法来源 = {FORWARD_STREAM_SOURCE!r}）"
            )


# ─────────────────────────── 断言 ②：前向流不可回填（§E.2 取版本防前视） ───────────────────────────


def _parse_ts(value: Any) -> datetime | None:
    """解析 ISO 时间戳；None / 空 / 非法 → `None`（不可核，不抛）。"""
    if not value:
        return None
    parsed: datetime | None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        parsed = None
    return parsed


def _business_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(row.get(k) for k in FORWARD_BUSINESS_KEY)


def max_seq_upto(
    stream: Sequence[Mapping[str, Any]],
    row: Mapping[str, Any],
    *,
    business_key: tuple[str, ...] = FORWARD_BUSINESS_KEY,
) -> int | None:
    """`§E.2` 取版本的机器化：**同一业务键**内、`first_seen_at ≤ 该行 first_seen_at` 的
    行里 `recorded_seq` 的最大值。

    ★ **必须按业务键分组**：若不分键，「后插入却给早时间戳」的回填行会把自己的高 `seq`
      算进上界，从而**自证合法**（判据形同虚设）。按业务键分组后，回填行会抬高**同期真行**
      的上界 ⇒ 真行的 `recorded_seq != 上界` ⇒ 被抓（`R-06` 可判定且穷尽）。

    行本身无 `first_seen_at`（不可核）→ 返回 `None`。
    """
    key = tuple(row.get(k) for k in business_key)
    asof = _parse_ts(row.get("first_seen_at"))
    if asof is None:
        return None
    best: int | None = None
    for other in stream:
        if tuple(other.get(k) for k in business_key) != key:
            continue
        other_ts = _parse_ts(other.get("first_seen_at"))
        if other_ts is None or other_ts > asof:
            continue
        seq = other.get("recorded_seq")
        if isinstance(seq, int) and (best is None or seq > best):
            best = seq
    return best


def iter_forward_violations(
    stream: Sequence[Mapping[str, Any]],
) -> tuple[list[str], int]:
    """把前向流分成「**确定违例**」与「**不可核（未评估）**」两类。

    - 返回 `(violations, unverifiable_count)`：
      - `violations`：`backfilled_at` 非空、或 `recorded_seq != max_seq_upto` 的人读说明；
      - `unverifiable_count`：无真实 `first_seen_at` 的行数（`G-03`：不可核 ⇒ 不计通过）。
    """
    violations: list[str] = []
    unverifiable = 0
    for row in stream:
        label = row.get("recommendation_id") or row.get("recorded_seq")
        if row.get("backfilled_at") is not None:
            violations.append(
                f"{label}: 前向流被回填（backfilled_at={row.get('backfilled_at')!r}，N10.3-11）"
            )
            continue
        asof = _parse_ts(row.get("first_seen_at"))
        if asof is None:
            unverifiable += 1
            continue
        expected = max_seq_upto(stream, row)
        actual = row.get("recorded_seq")
        if expected is None or not isinstance(actual, int) or actual != expected:
            violations.append(
                f"{label}: 前向流版本错序（recorded_seq={actual!r} ≠ 同键上界 {expected!r}，"
                "疑似事后回填，N10.3-11）"
            )
    return violations, unverifiable


def assert_forward_not_backfilled(stream: Sequence[Mapping[str, Any]]) -> None:
    """前向建议流真实时间戳、不可回填（`N10.3-11`，承 `Ch9 §3.4.2`）——**严格的公开断言**。

    逐行断言（`§E.3` 伪代码）：
      - `row.backfilled_at is None`（否则 `raise`）；
      - `row.recorded_seq == max_seq_upto(同业务键, row.first_seen_at)`（否则 `raise`）；
      - 无真实 `first_seen_at` ⇒ **不可核** ⇒ `raise`（`N10.3-11` 要求真实时间戳）。

    ★ 与 `check()` 的分工：`check()` 把「不可核」记为 `not_evaluated`（`G-03`，不误报为违例），
      而本**断言**对调用方是**严格**的（命中即可核性问题一律 fail）。
    """
    for row in stream:
        if row.get("backfilled_at") is not None:
            raise ForwardStreamViolation(
                f"前向流被回填：recommendation_id={row.get('recommendation_id')!r} "
                f"backfilled_at={row.get('backfilled_at')!r}（N10.3-11）"
            )
        if _parse_ts(row.get("first_seen_at")) is None:
            raise ForwardStreamViolation(
                f"前向流缺真实时间戳（first_seen_at 为空），不可核："
                f"recommendation_id={row.get('recommendation_id')!r}（N10.3-11）"
            )
        expected = max_seq_upto(stream, row)
        actual = row.get("recorded_seq")
        if expected is None or not isinstance(actual, int) or actual != expected:
            raise ForwardStreamViolation(
                f"前向流版本错序 / 疑似回填：recommendation_id={row.get('recommendation_id')!r} "
                f"recorded_seq={actual!r} ≠ 同键上界 {expected!r}（N10.3-11）"
            )


# ─────────────────────────── 报告对象 + 门禁入口 ───────────────────────────


@dataclass
class CapabilitySourceReport:
    """一次来源核查的摘要（供 CLI / 测试断言）。"""

    conclusions: int = 0
    forward_rows: int = 0
    replay_as_capability: int = 0
    backfilled_rows: int = 0
    unverifiable_rows: int = 0
    conclusions_evaluated: bool = False
    stream_evaluated: bool = False
    notes: list[str] = field(default_factory=list)


def evaluate_capability_source(root: str | Path | None = None) -> CapabilitySourceReport:
    """核查能力结论来源 + 前向流（`G-03` 感知）：空集 → `not_evaluated`（不判通过）。"""
    report = CapabilitySourceReport()
    conclusions = load_capability_conclusions(root)
    stream = load_forward_stream(root)
    report.conclusions = len(conclusions)
    report.forward_rows = len(stream)

    if not conclusions:
        report.notes.append(
            "NOT_EVALUATED：无能力结论对象（views/capability_conclusions.jsonl 为空，G-03）"
        )
    else:
        report.conclusions_evaluated = True
        for conclusion in conclusions:
            if conclusion.get("source") != FORWARD_STREAM_SOURCE:
                report.replay_as_capability += 1

    if not stream:
        report.notes.append(
            "NOT_EVALUATED：前向建议流为空（facts/recommendations.jsonl 为空，G-03）"
        )
    else:
        report.stream_evaluated = True
        violations, unverifiable = iter_forward_violations(stream)
        report.backfilled_rows = len(violations)
        report.unverifiable_rows = unverifiable
        if unverifiable:
            report.notes.append(
                f"{unverifiable} 行缺真实时间戳（first_seen_at 为空）→ 记为未评估，"
                "不判通过（G-03）"
            )
    return report


def check(root: Path) -> CheckReport:
    """门禁：① 回放收益当能力结论 → fail；② 前向流被回填 → fail；空集 → `not_evaluated`。"""
    report = CheckReport(checker="capability_source")
    source_report = evaluate_capability_source(root)

    report.scanned["conclusions"] = source_report.conclusions
    report.scanned["forward_rows"] = source_report.forward_rows
    report.scanned["unverifiable_rows"] = source_report.unverifiable_rows

    if source_report.replay_as_capability:
        report.violations.append(
            Violation(
                "N10.3-10",
                f"{source_report.replay_as_capability} 条能力结论来源非 {FORWARD_STREAM_SOURCE!r}"
                "（回放收益不得作为投资能力结论）",
                "views/capability_conclusions.jsonl",
            )
        )
    if source_report.stream_evaluated:
        violations, _ = iter_forward_violations(load_forward_stream(root))
        for detail in violations:
            report.violations.append(
                Violation("N10.3-11", detail, "facts/recommendations.jsonl")
            )

    report.notes.extend(source_report.notes)
    return report


def run(root: Path) -> CheckReport:
    """能力来源核查的调用入口（与 CLI 同源；供调用方直接内嵌）。"""
    return check(root)


def main(argv: list[str] | None = None) -> int:
    return run_checker("capability_source.py", check, argv)


if __name__ == "__main__":
    sys.exit(main())
