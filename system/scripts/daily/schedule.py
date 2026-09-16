#!/usr/bin/env python3
"""`schedule.py` —— **`p07` 配置化调度**（`Ch8 §D` / `Ch9 §3.10 J3` / `Ch11 §D.2`）。

```
python system/scripts/daily/schedule.py [code_root]
```

## 单一真源纪律（★ 值不得写死）

> `Ch11 §D.2`：**参数值唯一真源 = `rules/freeze.yaml::freeze_param`**；
> `rules/schedule.yaml`（p07）由对应 `freeze_param` **指向**，**不另存第二份值**。

因此本模块**不写死**任何运行时刻 / 时区 / 频率：
- **运行时刻与频率**：一律经 `config.freeze.get_param("p07", root)` 读取
  （`Ch9 §3.10 J3`：运行时刻 = 参数 `p07`；`rules/freeze.yaml` 里 `freeze_status: tbd`、
  `time_value: tbd`）。
- **时区**：取 `rules/schedule.yaml::cadence.timezone`（**结构位**，同样 `tbd`）。
- **缺 `rules/schedule.yaml`** → **响亮失败**（`ScheduleFileMissingError`），**不静默兜底**；
  如需显式缺省，调用方须**显式**传 `on_missing="explicit_default"`。
- **`time_value == "tbd"`** → `to_rrule()` **响亮失败**（`ScheduleUnresolvedError`），
  **不得**为"让 rrule 好看"而补一个时刻。

★ 退出码：`0` 解析成功 / `1` 命中违例（缺文件）/ `2` 输入异常。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation  # noqa: E402

SCHEDULE_REL = "rules/schedule.yaml"
P07 = "p07"
TBD = "tbd"
ANCHOR_SCHEDULE = "Ch8 §D"
ANCHOR_P07 = "Ch9 §3.10 J3"

#: `cadence` → rrule 频率（**结构映射**，非时刻/时区值）。
_CADENCE_FREQ: dict[str, str] = {"daily": "DAILY", "daily_and_event": "DAILY"}


class ScheduleFileMissingError(FileNotFoundError):
    """`rules/schedule.yaml` 缺失 —— **响亮失败**，不静默兜底。"""


class ScheduleUnresolvedError(RuntimeError):
    """参数仍为 `tbd` —— 不得为其编造具体值（`Ch9 §3.10 J3`）。"""


@dataclass(frozen=True)
class ScheduleSpec:
    """一次调度解析的结果。**带来源标注**，使"值从哪来"可审计。"""

    cadence: str
    anchor: str
    timezone: str
    time_value: str
    non_trading_day_policy: str
    value_source: str                 # "frozen" | "suggested_baseline"
    freeze_status: str                # tbd / frozen
    timezone_explicitly_recorded: bool
    schedule_pointer: str

    @property
    def resolved(self) -> bool:
        """时刻/时区均已解析（非 `tbd`）。"""
        return self.time_value != TBD and self.timezone != TBD


def load_schedule_yaml(root: str | Path | None = None, *, on_missing: str = "raise") -> dict[str, Any] | None:
    """读 `rules/schedule.yaml`（**复用** `config.rules.load_yaml`，不另开读口）。

    `on_missing="raise"`（默认）→ 缺失即抛 `ScheduleFileMissingError`；
    `on_missing="explicit_default"` → 返回 `None`（**显式缺省**，调用方须记录）。
    """
    from config.rules import load_yaml

    path = (Path(root) if root else _ROOT) / SCHEDULE_REL
    if not path.exists():
        if on_missing == "raise":
            raise ScheduleFileMissingError(
                f"缺少调度文件 {SCHEDULE_REL} —— 不得静默兜底（{ANCHOR_SCHEDULE}）"
            )
        if on_missing == "explicit_default":
            return None
        raise ValueError(f"on_missing 非法取值 {on_missing!r}（raise | explicit_default）")
    return load_yaml(SCHEDULE_REL, root)


def resolve_schedule(
    root: str | Path | None = None, *, on_missing: str = "raise"
) -> ScheduleSpec:
    """解析运行时刻 / 频率 / 时区 —— **一律走配置**，不写死。

    值来源（**逐项标注**）：
    - `cadence` / `anchor` / `time_value` / `timezone_explicitly_recorded` / `schedule_pointer`
      ← `get_param("p07")`（**权威读口**）；
    - `timezone` / `non_trading_day_policy` ← `rules/schedule.yaml::cadence`（结构位）。
    """
    from config.freeze import get_param

    p07 = get_param(P07, root)
    values: Mapping[str, Any] = p07.effective_value if isinstance(p07.effective_value, Mapping) else {}
    schedule = load_schedule_yaml(root, on_missing=on_missing)

    if schedule is not None:
        ref = schedule.get("param_ref")
        if ref not in (None, P07):
            raise ScheduleUnresolvedError(
                f"{SCHEDULE_REL}::param_ref={ref!r} 与权威参数 {P07!r} 不一致（单一真源纪律，Ch11 §D.2）"
            )

    cadence_block = (schedule or {}).get("cadence") or {}
    timezone = str(cadence_block.get("timezone") or values.get("timezone") or TBD)
    pointer = str(values.get("schedule_pointer") or (SCHEDULE_REL if schedule is not None else ""))
    return ScheduleSpec(
        cadence=str(values.get("cadence") or TBD),
        anchor=str(values.get("anchor") or TBD),
        timezone=timezone,
        time_value=str(values.get("time_value") or TBD),
        non_trading_day_policy=str(cadence_block.get("non_trading_day_policy") or TBD),
        value_source=str(p07.value_source),
        freeze_status=str(p07.freeze_status),
        timezone_explicitly_recorded=bool(values.get("timezone_explicitly_recorded")),
        schedule_pointer=pointer,
    )


def to_rrule(spec: ScheduleSpec, *, allow_time_free: bool = False) -> str:
    """由 `ScheduleSpec` 生成 rrule。

    - 时刻 / 时区已解析 → `FREQ=...;BYHOUR=H;BYMINUTE=M`；
    - 任一为 `tbd` → 默认**响亮失败**；`allow_time_free=True` 时**显式**退化为
      仅频率（`FREQ=...`，**不含时刻**）—— 调用方须为此负责（**不静默**）。
    """
    freq = _CADENCE_FREQ.get(spec.cadence)
    if freq is None:
        raise ScheduleUnresolvedError(
            f"cadence={spec.cadence!r} 无法映射为 rrule 频率（{ANCHOR_SCHEDULE} / {P07}）"
        )
    if spec.time_value == TBD or spec.timezone == TBD:
        if not allow_time_free:
            raise ScheduleUnresolvedError(
                f"time_value={spec.time_value!r} / timezone={spec.timezone!r} 仍为 tbd —— "
                f"不得写死运行时刻/时区（{ANCHOR_P07} / {P07}）"
            )
        return f"FREQ={freq}"
    hour, minute = _parse_hhmm(spec.time_value)
    return f"FREQ={freq};BYHOUR={hour};BYMINUTE={minute}"


def _parse_hhmm(value: str) -> tuple[int, int]:
    """把配置里的时刻字符串解析成 `(hour, minute)`；非法 → 响亮失败。"""
    parts = str(value).split(":")
    if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
        raise ScheduleUnresolvedError(f"time_value={value!r} 不是合法时刻（HH:MM）")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ScheduleUnresolvedError(f"time_value={value!r} 越界（{ANCHOR_P07}）")
    return hour, minute


def describe(spec: ScheduleSpec) -> str:
    """人类可读摘要（供报告 / CLI；**不隐藏 tbd**）。"""
    return (
        f"cadence={spec.cadence} anchor={spec.anchor} timezone={spec.timezone} "
        f"time_value={spec.time_value} non_trading_day_policy={spec.non_trading_day_policy} "
        f"value_source={spec.value_source} freeze_status={spec.freeze_status} "
        f"pointer={spec.schedule_pointer}"
    )


def check(root: Path) -> CheckReport:
    """守卫：调度文件存在且可解析（缺文件 → 命中断言）。`tbd` → note（冻结前为正常态）。"""
    report = CheckReport(checker="daily_schedule")
    try:
        spec = resolve_schedule(root)
    except ScheduleFileMissingError as exc:
        report.violations.append(Violation("daily_schedule", str(exc), SCHEDULE_REL))
        return report
    report.scanned["cadence_freq"] = 1 if spec.cadence in _CADENCE_FREQ else 0
    report.notes.append(f"SCHEDULE_CONTEXT：{describe(spec)}")
    if not spec.resolved:
        report.notes.append(
            "SCHEDULE_UNRESOLVED：time_value/timezone 为 tbd（拍板前正常态）→ "
            "to_rrule() 将响亮失败，不写死时刻（AC-4d）"
        )
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="schedule.py", description="p07 配置化调度（Ch8 §D）")
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--no-report", action="store_true")
    parser.add_argument("--allow-time-free", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.code_root) if args.code_root else _ROOT

    print("== daily_schedule ==")
    try:
        spec = resolve_schedule(root)
    except ScheduleFileMissingError as exc:
        print(f"  [FATAL] {exc}")
        print("RESULT: FAIL（1 violations）")
        return 1
    print(f"  note: {describe(spec)}")
    try:
        print(f"  rrule: {to_rrule(spec, allow_time_free=args.allow_time_free)}")
    except ScheduleUnresolvedError as exc:
        print(f"  note: {exc}")
        print("RESULT: PASS（时刻未冻结；rrule 未解析，未写死）")
        return 0
    print("RESULT: PASS（0 violations）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
