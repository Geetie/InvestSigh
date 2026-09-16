#!/usr/bin/env python3
"""`pipeline.py` —— **8 步闭环状态机 + 断点续跑**（`Ch1 §D.1` / `§E` / `§F` G1-05）。

```
python system/scripts/orchestrate/pipeline.py [code_root] [--date YYYY-MM-DD] [--scope full]
```

职责边界（`Ch1 §D.1`，逐字）：
> **编排器只负责"把 1–6 步串成可断点续跑的状态机"**，并对第 7/8 步**预留接口**
> （`publish_hook` / `verify_hook`），第八章 / 第十章**已拆解**，接口**即插即用**；
> **不在本章伪造第 7/8 步实现**。

反 KPI（`Ch1 §D.3`）：
- 每日运行**必写** `check_record`（无论有无变化）
- `judgment_change` 全 False → **不写新版本、不发信号**
- 仅有变化时才触发第 7 步发布

G1-05（8 步完整性守卫）：1–6 步产物对象齐备；7/8 步接口已注册（**未实现时显式标 gap，
不得静默跳过**）；缺产物 → 编排器置 `blocked`，**不得报成功**。

★ 为什么不做成纯 Prompt（`Ch1 §B`）：8 步闭环需要**断点续跑、幂等、可回放**，
  纯提示词无法保证跨天失败恢复与去重，故列 C 档。
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402

STATE_FILENAME = "state.json"

STATUS_OK = "ok"
STATUS_GAP = "gap"           # 显式缺口（未实现）——**不得**当作成功
STATUS_BLOCKED = "blocked"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


class StepNotImplemented(RuntimeError):
    """步进处理器未注册 —— 必须显式记 gap，不得静默跳过。"""


@dataclass
class StepResult:
    step: int
    name: str
    status: str
    produced: list[str] = field(default_factory=list)
    gap: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK


@dataclass
class RunResult:
    run_date: str
    scope: str
    steps: list[StepResult] = field(default_factory=list)
    judgment_change: dict[str, bool] = field(default_factory=dict)
    signals_emitted: int = 0
    degraded: bool = False
    blocked: bool = False
    published: bool = False
    verified: bool = False
    gaps: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return any(self.judgment_change.values())


StepHandler = Callable[[date, str], "StepOutcome"]


@dataclass
class StepOutcome:
    """步进处理器的返回值。`produced` = 本次产出的**对象引用**（非文件名）。"""

    produced: list[str] = field(default_factory=list)
    judgment_change: dict[str, bool] = field(default_factory=dict)
    signals_emitted: int = 0
    degraded: bool = False
    # ★ 批次 7 · 集成 `I-1`（张力 `T-08` 的 **A 方案**）新增：
    #   处理器**已注册**、但其**模型侧 / 上游组件**尚未实现（属阶段②③）时，
    #   用它**显式声明本步未完成**；编排器据此把该步记为 `STATUS_GAP`（**不是** `ok`）。
    #
    #   为什么必须新增这个字段：`StepOutcome` 原先**没有**任何"本步未完成"的表达力 ——
    #   `run_daily` 对**所有**返回的 outcome 一律记 `STATUS_OK`。于是"注册了一个什么都不做的
    #   处理器"只能靠 `assert_steps_complete` 的"报 ok 但 produced 为空（空执行）"兜住，
    #   而那是一条**语义错误**的记录（本步并没有 ok）。A 方案要求"模型侧缺口**显式**标 gap、
    #   **不静默**"，故必须让处理器自己能说"我没做完，原因是 X"。
    #
    #   缺省 `None` = 本步自认完成（既有行为不变，向后兼容）。
    incomplete_reason: str | None = None


# ───────────────────────── 注册表（1–6 步实现 + 7/8 步 hook 预留） ─────────────────────────

class Pipeline:
    """8 步闭环状态机。**步骤实现由后续阶段注册**；未注册即显式记 gap。"""

    def __init__(self, root: Path, *, config: Mapping[str, Any] | None = None):
        self.root = root
        self.config = dict(config) if config is not None else self._load_config()
        self._step_handlers: dict[int, StepHandler] = {}
        self._publish_hook: Callable[[RunResult], None] | None = None
        self._verify_hook: Callable[[RunResult], None] | None = None
        self._register_default_steps()

    def _register_default_steps(self) -> None:
        """**默认注册**首版已实现的步进处理器（`rules/pipeline.yaml::steps[1..6]`）。

        ★ 为什么必须**默认注册**（不要求调用方额外注册）：`rules/pipeline.yaml`（0444 锁定的
          设计真相源）声明 step 1–6 `implemented_in_first_version: true`、`blocking: true`。
          若靠调用方自觉注册，"编排器能真干活"就不成立（`G-13` 的症结）。

        ★ **批次 7 · 集成 `I-1`（张力 `T-08` 的 A 方案）**：`rules/pipeline.yaml` 声明 step 1–6
          首版已实现，而 step 2–6 的**模型侧**组件（核验七步 / 关系抽取 / 增长护城河判断）按
          施工图属阶段②③。A 方案的裁决是：**注册 1–6，算术 / 图 / 决策部分接真实实现，
          模型侧缺口由处理器显式声明（`StepOutcome.incomplete_reason`）→ 记 `gap` + 置 `blocked`，
          绝不静默、绝不伪造产物**。注册动作本身不再是免责理由。

          模块归属与设计锚点见 `scripts/orchestrate/chain_steps.py` 的模块 docstring。
        """
        from scripts.orchestrate.chain_steps import register_chain_steps
        from scripts.orchestrate.ingest_step import ingest_public_information

        self.register_step(1, ingest_public_information)
        register_chain_steps(self)

    def _load_config(self) -> dict[str, Any]:
        from config.rules import load_yaml

        return load_yaml("rules/pipeline.yaml", self.root)

    # ── 注册面（`Ch1 §E` 签名逐字） ──
    def register_step(self, step: int, fn: StepHandler) -> None:
        self._step_handlers[step] = fn

    def register_publish_hook(self, fn: Callable[[RunResult], None]) -> None:
        """第 7 步预留接口（第八章交付）。"""
        self._publish_hook = fn

    def register_verify_hook(self, fn: Callable[[RunResult], None]) -> None:
        """第 8 步预留接口（第十章交付）。"""
        self._verify_hook = fn

    def hooks_registered(self) -> dict[str, bool]:
        return {"publish_hook": self._publish_hook is not None, "verify_hook": self._verify_hook is not None}

    # ── 主流程 ──
    def run_daily(self, run_date: date, scope: str = "full") -> RunResult:
        result = RunResult(run_date=run_date.isoformat(), scope=scope)
        steps_cfg = self.config.get("steps") or []
        if not steps_cfg:
            raise ValueError("rules/pipeline.yaml 未声明任何步骤（8 步闭环缺失）")

        for cfg in steps_cfg:
            no = int(cfg["step"])
            name = str(cfg["name"])
            handler = self._step_handlers.get(no)
            if handler is None:
                gap = (
                    f"step {no} ({name}) 未注册处理器"
                    + (f"；预留 hook = {cfg['hook']}" if cfg.get("hook") else "")
                )
                result.steps.append(
                    StepResult(no, name, STATUS_GAP, gap=gap)
                )
                result.gaps.append(gap)
                if cfg.get("blocking"):
                    result.blocked = True
                continue
            try:
                outcome = handler(run_date, scope)
            except Exception as exc:  # 不吞异常：记失败 + 保留上次有效结果
                result.steps.append(
                    StepResult(no, name, STATUS_FAILED, error=f"{type(exc).__name__}: {exc}")
                )
                result.degraded = True
                if cfg.get("blocking"):
                    result.blocked = True
                continue
            # ★ `incomplete_reason` 非空 = 处理器已注册但**模型侧 / 上游组件未实现**（阶段②③）。
            #   记 `STATUS_GAP`（**不是** `ok`）并把原因写进 `gap` 与 `result.gaps`。
            #   若记成 `ok` + 空 `produced`，`assert_steps_complete` 虽仍会拦住（"空执行"），
            #   但那是**语义错误**的记录 —— 本步并没有 ok。此处据实记 `gap`。
            status = STATUS_GAP if outcome.incomplete_reason else STATUS_OK
            result.steps.append(
                StepResult(
                    no,
                    name,
                    status,
                    produced=list(outcome.produced),
                    gap=outcome.incomplete_reason,
                )
            )
            if outcome.incomplete_reason:
                result.gaps.append(f"step {no} ({name}): {outcome.incomplete_reason}")
                if cfg.get("blocking"):
                    result.blocked = True
            for k, v in (outcome.judgment_change or {}).items():
                result.judgment_change[k] = bool(v) or result.judgment_change.get(k, False)
            result.signals_emitted += int(outcome.signals_emitted or 0)
            result.degraded = result.degraded or bool(outcome.degraded)

        # ── G1-05（`Ch1 §F`）：8 步完整性 —— **在编排器里真的调用它** ──
        # 阶段① 缺口登记 `D-14` 指出：本函数此前**零调用**，而
        # `rules/pipeline.yaml::completeness.guard` 与 `skills/aichain-daily/SKILL.md`
        # 都把它写成"承载 G1-05 的守卫" → 声明存在、事实不存在（假接线）。
        # 现在它就在主流程里：步不全 → 记 gap + 置 blocked（不得报成功）。
        for viol in assert_steps_complete(result, self.hooks_registered()):
            result.gaps.append(f"G1-05 {viol.reason}")
            result.blocked = True

        # ── 反 KPI（Ch1 §D.3 / §F G1-02）──
        if not result.blocked and result.changed:
            if self._publish_hook is not None:
                self._publish_hook(result)
                result.published = True
            else:
                result.gaps.append("publish_hook 未注册（第八章交付）→ 本日有变化但未发布")
        if not result.blocked and self._verify_hook is not None:
            self._verify_hook(result)
            result.verified = True

        self._write_state(result)
        self._write_check_record(result)
        return result

    def resume(self, task_id: str) -> RunResult:
        """断点续跑：从 `state.json` 恢复，跳过已 `ok` 的步（`Ch1 §E`）。"""
        state = self._read_state()
        run = state.get("runs", {}).get(task_id)
        if run is None:
            raise KeyError(f"state.json 中无该 task_id: {task_id}（不得凭空重建）")
        done_steps = {s["step"] for s in run.get("steps", []) if s.get("status") == STATUS_OK}
        run_date = date.fromisoformat(run["run_date"])
        result = RunResult(run_date=run["run_date"], scope=run.get("scope", "full"))
        steps_cfg = self.config.get("steps") or []
        for cfg in steps_cfg:
            no = int(cfg["step"])
            if no in done_steps:
                result.steps.append(
                    StepResult(no, str(cfg["name"]), STATUS_SKIPPED, gap=None)
                )
                continue
            handler = self._step_handlers.get(no)
            if handler is None:
                gap = f"step {no} 未注册处理器（断点续跑）"
                result.steps.append(StepResult(no, str(cfg["name"]), STATUS_GAP, gap=gap))
                result.gaps.append(gap)
                continue
            outcome = handler(run_date, result.scope)
            result.steps.append(StepResult(no, str(cfg["name"]), STATUS_OK, produced=list(outcome.produced)))
            result.signals_emitted += int(outcome.signals_emitted or 0)
            for k, v in (outcome.judgment_change or {}).items():
                result.judgment_change[k] = bool(v) or result.judgment_change.get(k, False)
        self._write_state(result)
        self._write_check_record(result)
        return result

    # ── 反 KPI：**每日运行必写 check_record**（`Ch1 §D.3` / `rules/pipeline.yaml` anti_kpi） ──
    def _write_check_record(self, result: RunResult) -> None:
        """写 `check_record` 到 `facts/tasks.jsonl`（控制面**子记录**，`Ch1 §C.2`）。

        无论有无变化**都写** —— 这才是"每日维护 ≠ 每日产信号"的落地。
        消费方：`scripts/checks/no_signal_day.py`（G1-02 三条断言）。

        断点续跑（`resume`）会**再写一条**并带 `_r<n>` 修订号：追加式不可变，
        且幂等键保持唯一（重跑同日不产生**重复事件/建议**，但运行记录本身如实追加）。
        """
        from schema.models import CheckRecord, CheckScope, Task, TaskStatus, TaskType
        from schema.store import append_records, read_records

        base_key = f"check::check_{result.run_date}_{result.scope}"
        prior = sum(
            1 for row in read_records(self.root, "tasks")
            if str(row.get("idempotency_key", "")).startswith(base_key)
        )
        suffix = "" if prior == 0 else f"_r{prior}"
        check_id = f"check_{result.run_date}_{result.scope}{suffix}"
        record = CheckRecord(
            check_id=check_id,
            run_date=date.fromisoformat(result.run_date),
            scope=CheckScope(result.scope),
            changed=result.changed,
            judgment_change=dict(result.judgment_change),
            signals_emitted=result.signals_emitted,
            degraded=result.degraded,
        )
        task = Task(
            task_id=f"task_{check_id}",
            task_type=TaskType.verify,
            status=TaskStatus.failed if result.blocked else TaskStatus.done,
            idempotency_key=f"check::{check_id}",
            parent_context={"orchestrator": "pipeline.run_daily"},
            check_record=record,
        )
        append_records(self.root, "tasks", [task])

    # ── 状态持久化（断点续跑；`state.json` 游标） ──
    def _state_path(self) -> Path:
        return self.root / STATE_FILENAME

    def _read_state(self) -> dict[str, Any]:
        p = self._state_path()
        if not p.exists():
            return {"runs": {}}
        return json.loads(p.read_text(encoding="utf-8"))

    def _write_state(self, result: RunResult) -> None:
        state = self._read_state()
        task_id = f"run_{result.run_date}_{result.scope}"
        state.setdefault("runs", {})[task_id] = {
            **asdict(result),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        state["cursor"] = {"last_run_date": result.run_date, "scope": result.scope}
        self._state_path().write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


# ───────────────────────── G1-05：8 步完整性守卫 ─────────────────────────

def assert_steps_complete(result: RunResult, registered_hooks: Mapping[str, bool]) -> list[Violation]:
    """G1-05（`Ch1 §F`）：1–6 步产物对象齐备；7/8 步接口已注册（未实现则显式 gap）。"""
    v: list[Violation] = []
    for step in result.steps:
        if step.step <= 6:
            if step.status != STATUS_OK:
                v.append(
                    Violation(
                        "G1-05",
                        f"第 {step.step} 步（{step.name}）未产出：status={step.status}"
                        + (f"，gap={step.gap}" if step.gap else "")
                        + (f"，error={step.error}" if step.error else ""),
                        "scripts/orchestrate/pipeline.py",
                    )
                )
            elif not step.produced:
                v.append(
                    Violation(
                        "G1-05",
                        f"第 {step.step} 步（{step.name}）报 ok 但 produced 为空（空执行）",
                        "scripts/orchestrate/pipeline.py",
                    )
                )
    for name, ok in registered_hooks.items():
        if not ok:
            # 未注册**允许**，但必须显式标 gap（已在上方记入 result.gaps）
            if not any(name in g for g in result.gaps):
                v.append(
                    Violation(
                        "G1-05",
                        f"{name} 未注册且未显式记 gap（不得静默跳过）",
                        "scripts/orchestrate/pipeline.py",
                    )
                )
    if result.blocked and result.published:
        v.append(Violation("G1-05", "编排器置 blocked 却仍发布了建议（不得报成功）"))
    return v


def check(root: Path) -> CheckReport:
    """守卫入口：校验 `rules/pipeline.yaml` 的步骤声明完整 + 已有 `state.json` 自洽。

    ★ 本 docstring 曾在**未实现**的情况下声称"校验 `state.json` 一致" ——
      第二轮独立审计把它列为"docstring 声称 vs 函数体"脱节。现在两者对齐：
      `state.json` 存在时，其各次运行的步骤号必须与声明一致（否则续跑会跳错步）。
    """
    report = CheckReport(checker="pipeline")
    from config.rules import load_yaml

    cfg = load_yaml("rules/pipeline.yaml", root)
    steps = cfg.get("steps") or []
    report.scanned["declared_steps"] = len(steps)
    numbers = [int(s["step"]) for s in steps]
    if numbers != list(range(1, 9)):
        report.violations.append(
            Violation("G1-05", f"8 步闭环声明必须严格为 1..8，实为 {numbers}", "rules/pipeline.yaml")
        )
    for s in steps:
        for key in ("name", "produces", "blocking", "chapter_ref"):
            if key not in s:
                report.violations.append(
                    Violation("G1-05", f"step {s.get('step')} 缺字段 {key}", "rules/pipeline.yaml")
                )
    if cfg.get("anti_kpi", {}).get("always_write_check_record") is not True:
        report.violations.append(
            Violation("G1-02", "anti_kpi.always_write_check_record 必须为 true", "rules/pipeline.yaml")
        )

    # `state.json` 自洽（存在才校验：阶段① 尚未跑过每日运行是正常的）
    state_path = root / STATE_FILENAME
    if not state_path.exists():
        report.notes.append("NO_STATE_JSON：尚无运行游标（阶段④ 起产生），本次不校验自洽性")
        return report
    state = json.loads(state_path.read_text(encoding="utf-8"))
    runs = state.get("runs") or {}
    report.scanned["runs_in_state"] = len(runs)
    for task_id, run in runs.items():
        seen = sorted(int(s["step"]) for s in (run.get("steps") or []))
        if seen and seen != list(range(1, len(seen) + 1)):
            report.violations.append(
                Violation(
                    "G1-05",
                    f"state.json run={task_id} 的步骤号不连续/不匹配声明: {seen}"
                    "（续跑会跳错步）",
                    STATE_FILENAME,
                )
            )
    return report


if __name__ == "__main__":
    sys.exit(run_checker("pipeline.py", check))
