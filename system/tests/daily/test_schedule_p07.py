"""AC-4：**调度配置化（`p07`）**—— 运行时刻/时区/频率**不得写死**（`Ch8 §D` / `Ch9 §3.10 J3`）。

锚点：`Ch11 §D.2`（参数值唯一真源 = `rules/freeze.yaml`）/ `Ch9 §3.10 J3`（运行时刻 = 参数 `p07`）/
`Ch8 §D`（调度，`rules/schedule.yaml` 只指针不双写）。

★ 关键证据：**改配置 → 输出随之改变**。若把时刻写死在代码里，本用例必红。
★ 缺 `rules/schedule.yaml` → **响亮失败**（不静默兜底）；`tbd` → `to_rrule()` **响亮失败**。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from scripts.daily import schedule


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _dump(path: Path, doc: dict) -> None:
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _patch_p07(root: Path, **fields: object) -> None:
    """改 `rules/freeze.yaml` 的 `p07.suggested_value`（模拟"需求方拍板把值定下来"）。"""
    path = root / "rules" / "freeze.yaml"
    doc = _load(path)
    for row in doc["freeze_params"]:
        if row.get("param_id") == "p07":
            row.setdefault("suggested_value", {}).update(fields)
    _dump(path, doc)


def _patch_schedule_top(root: Path, **fields: object) -> None:
    path = root / "rules" / "schedule.yaml"
    doc = _load(path)
    doc.update(fields)
    _dump(path, doc)


def _patch_schedule_cadence(root: Path, **fields: object) -> None:
    path = root / "rules" / "schedule.yaml"
    doc = _load(path)
    doc.setdefault("cadence", {}).update(fields)
    _dump(path, doc)


# ── 正向：值来自配置，改配置则输出改变（证明非硬编码） ──────────────────────

def test_spec_value_comes_from_config_not_hardcoded(code_root: Path) -> None:
    _patch_p07(code_root, time_value="21:15")
    _patch_schedule_cadence(code_root, timezone="America/New_York", non_trading_day_policy="skip")

    spec = schedule.resolve_schedule(code_root)
    assert spec.time_value == "21:15"
    assert spec.timezone == "America/New_York"
    assert spec.non_trading_day_policy == "skip"
    assert spec.resolved is True
    assert schedule.to_rrule(spec) == "FREQ=DAILY;BYHOUR=21;BYMINUTE=15"

    # ★ 改配置 → rrule 随之变化（写死则此处必红）
    _patch_p07(code_root, time_value="06:05")
    spec2 = schedule.resolve_schedule(code_root)
    assert schedule.to_rrule(spec2) == "FREQ=DAILY;BYHOUR=6;BYMINUTE=5"


def test_value_source_marks_suggested_baseline(code_root: Path) -> None:
    """`freeze_status: tbd` → 值来自 `suggested_value`，来源显式标注（`Ch11 §D.2`）。"""
    spec = schedule.resolve_schedule(code_root)
    assert spec.value_source == "suggested_baseline"
    assert spec.freeze_status == "tbd"
    assert spec.schedule_pointer == "rules/schedule.yaml"


# ── 边界：`tbd` 时 to_rrule 响亮失败（不得为"让 rrule 好看"补时刻） ──────────

def test_tbd_time_value_is_loud(code_root: Path) -> None:
    spec = schedule.resolve_schedule(code_root)
    assert spec.resolved is False

    with pytest.raises(schedule.ScheduleUnresolvedError):
        schedule.to_rrule(spec)

    # 显式允许时退化为"仅频率"（不含时刻）—— 调用方须为此负责（不静默）
    assert schedule.to_rrule(spec, allow_time_free=True) == "FREQ=DAILY"


def test_unsupported_cadence_is_loud(code_root: Path) -> None:
    _patch_p07(code_root, cadence="hourly", time_value="09:00")
    _patch_schedule_cadence(code_root, timezone="Asia/Shanghai")
    spec = schedule.resolve_schedule(code_root)
    with pytest.raises(schedule.ScheduleUnresolvedError):
        schedule.to_rrule(spec)


# ── 错误路径：缺 `rules/schedule.yaml` → 响亮失败（不静默兜底） ──────────────

def test_missing_schedule_file_is_loud(code_root: Path) -> None:
    (code_root / "rules" / "schedule.yaml").unlink()

    with pytest.raises(schedule.ScheduleFileMissingError):
        schedule.load_schedule_yaml(code_root)
    with pytest.raises(schedule.ScheduleFileMissingError):
        schedule.resolve_schedule(code_root)

    # 仅当**显式**要求缺省时才不抛，且时区如实回落为 tbd（不臆造）
    spec = schedule.resolve_schedule(code_root, on_missing="explicit_default")
    assert spec.timezone == schedule.TBD


def test_param_ref_mismatch_is_loud(code_root: Path) -> None:
    """`schedule.yaml::param_ref` 与权威参数 `p07` 不一致 → 违反单一真源纪律 → 响亮失败。"""
    _patch_schedule_top(code_root, param_ref="p08")
    with pytest.raises(schedule.ScheduleUnresolvedError):
        schedule.resolve_schedule(code_root)


# ── 静态：源码内不得出现写死的时刻 / 时区 ───────────────────────────────────

def test_no_hardcoded_clock_or_timezone_in_source() -> None:
    src = Path(schedule.__file__).read_text(encoding="utf-8")
    assert re.search(r"\b\d{1,2}:\d{2}\b", src) is None, "源码含写死的时刻字面量"
    for token in ("Asia/", "America/", "Europe/", "UTC", "GMT"):
        assert token not in src, f"源码含写死的时区字面量: {token}"
