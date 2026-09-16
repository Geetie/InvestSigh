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
    # ★ 本轮**行幂等命中**的对象引用（`Ch9 §3.5`）：存在、但**本轮未新写入**。
    #   与 `status == STATUS_SKIPPED`（**整步**被 `resume` 跳过）是**两个不同粒度**的
    #   概念，勿混：这里是**对象粒度**、且**整步确实执行了**。
    skipped: list[str] = field(default_factory=list)

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
    """步进处理器的返回值。

    - `produced` = **本轮真正新写入**的对象引用（非文件名）。
    - `skipped` = 本轮**行幂等命中**、确认已存在故未重复写入的对象引用。
    两者互斥、不得混同（详见 `skipped` 字段的注释）。
    """

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
    # ★ 本轮**行幂等命中**的对象引用（`Ch9 §3.5`）——存在、但**本轮未新写入**。
    #
    #   为什么必须有这个字段（批次 10 独立审计 `C-03` 的**同一问题**在 step 1 上重现）：
    #   把幂等命中折进 `produced` 会**同时**破坏两件事 ——
    #     ① `produced` 的语义：`tests/compute/test_step_wiring.py:48`
    #        （`幂等重跑未新增落库 → produced 必须为空`）已把 `produced` 钉死为
    #        **「本轮真正新增落库的集合」**。同一字段两套语义 ⇒ `G1-05` 在各步之间
    #        **不可比**，守卫台账失去意义。
    #     ② **恰好重新掩盖** `G-B10-07` 要暴露的信号：重跑与首跑的差别正是
    #        `produced` 由 N 变 0，若把命中折进 `produced` 则两轮观测量**完全相同**，
    #        "非幂等"与"幂等"在输出上再度不可区分。
    #   → `produced` 保持严格（只记本轮新写入）；幂等命中另走本字段。
    #   → `G1-05` 的「空执行」判据相应改为 `not produced and not skipped`：
    #      "读了 N 个对象、判定均无需追加"**不是**空执行，而是**已完成的检查**。
    #   缺省空列表 = 既有行为逐字不变（向后兼容）。
    skipped: list[str] = field(default_factory=list)


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
        from scripts.orchestrate.ingest_step import make_ingest_handler

        # ★ **必须**用 `make_ingest_handler(self.root)` 绑定 root（缺陷 `G-RC-05`）：
        #   `StepHandler = Callable[[date, str], StepOutcome]` 签名里**没有 root**，
        #   若直接注册裸函数，处理器只能从 `Path(__file__)` 解析路径 →
        #   **任何拿副本 `code_root` 调用 `run_daily` 的测试都会写进真仓库真源**
        #   （实测：11 次 `run_daily` 在真 `facts/claims.jsonl` 追加 12 行重复 claim）。
        #   这与 `P7-2`（`run_decide` 忽略 `root`）同类，但更隐蔽 —— 那是"参数被忽略"，这是"参数不存在"。
        self.register_step(1, make_ingest_handler(self.root))
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
                    # 直接属性访问（**不**用 `getattr(..., ())` 兜底）：`skipped` 是
                    # `StepOutcome` 的**声明字段**，缺失即"处理器返回了非本类型对象"，
                    # 属程序错误 → 必须响亮 `AttributeError`（铁律：静默兜底会把
                    # 参数写反的 bug 藏很久）。
                    skipped=list(outcome.skipped),
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
                if cfg.get("blocking"):
                    result.blocked = True
                continue
            outcome = handler(run_date, result.scope)
            # ★ 与 `run_daily` 保持**同一套语义**（批次 7 审计 `B2`）：
            #   实测两入口曾分歧 —— 同副本同 handler，`run_daily` = step2/3/4/5 gap + blocked=True + 11 gaps，
            #   而 `resume` = ok + blocked=False + 2 gaps。分歧根因就是下面这行**硬编码 STATUS_OK**：
            #   它不读 `incomplete_reason`、不传播 `degraded`、不把未完成的 blocking 步置 `blocked`。
            #   两个入口对同一次运行给出**相反结论**，属于必须消除的不一致（不是"resume 的另一套设计"）。
            status = STATUS_GAP if outcome.incomplete_reason else STATUS_OK
            result.steps.append(
                StepResult(
                    no,
                    str(cfg["name"]),
                    status,
                    produced=list(outcome.produced),
                    gap=outcome.incomplete_reason,
                    skipped=list(outcome.skipped),
                )
            )
            if outcome.incomplete_reason:
                result.gaps.append(f"step {no} ({cfg['name']}): {outcome.incomplete_reason}")
                if cfg.get("blocking"):
                    result.blocked = True
            result.signals_emitted += int(outcome.signals_emitted or 0)
            result.degraded = result.degraded or bool(outcome.degraded)
            for k, v in (outcome.judgment_change or {}).items():
                result.judgment_change[k] = bool(v) or result.judgment_change.get(k, False)

        # ── G1-05（`Ch1 §F`）：与 `run_daily` 一致地跑完整性判据（批次 7 审计 `B2`：
        #   此前 `resume` **从不调用**它，于是"跳过了但什么都没补"也会报成功）。 ──
        for viol in assert_steps_complete(result, self.hooks_registered()):
            result.gaps.append(f"G1-05 {viol.reason}")
            result.blocked = True

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

        ## ★ 本行同时是"降级保留上次有效结果"契约的**唯一写入点**（`Ch8 §E.4`）

        `Ch8 §E.1` 的共同红线：故障时**保留上次有效结果**、**不覆盖为无意义空值**、
        **不把旧数据标为最新**。落到本行就是两个字段必须**按设计**填：

        | 字段 | 填法 | 依据 |
        |---|---|---|
        | `last_valid_result_ref` | 本次运行**未产出有效结果**（`blocked` / `degraded`）时，指向**上一次成功运行**的 `check_id`（无 → `None`，**如实为空**，`G-03`）；本次运行成功时为 `None`（本次结果**就是**有效结果，无需保留旧引用） | `Ch8 §E.2`（"失败时指向旧结果"）/ `N9.2-13` |
        | `output_refs` | 本次运行的 `StepOutcome.produced` **并集**（= 本轮**真正新写入**的对象引用），**仅当本次运行产出有效结果时填写**；失败 / 阻断 / 降级时如实为空 —— 此时该任务的有效结果是 `last_valid_result_ref` 指向的旧结果，**不是**本次的部分写入 | `Ch8 §E.1` / `§E.4`（"不覆盖为无意义空值"） |

        ★★ **为什么必须在这里填**（缺陷 `G-43` / `G-45`，独立审计实证）：此前本方法
        **两个字段都不设**，于是 `facts/tasks.jsonl` 里每一行都恒为 `None` / `[]`，
        使阶段④ 的判据 `degrade_keeps_last_valid` 的首日豁免谓词（`stage_gate` 的
        `_holds_valid_result()`）**恒 False** ⇒ 每个失败行都被当"首日"豁免 ⇒
        判据**空转、从不报任何真违规**。且全仓库 `output_refs=` **零个生产赋值点**。

        ★★ **`last_valid_result_ref` 一律复用 `scripts.daily.degrade.last_valid_result_ref()`**
        （`G-06` 唯一真源 / 纪律 11）：本层**不重算第二套**判定 —— 那正是 `G-45`
        （同一批行两个模块口径相反）的成因。取值必须在 `append_records` **之前**读：
        本行尚未落库，故读到的天然是"上一次"。

        ★ 首日（此前**确实没有任何成功运行**）时 `last_valid_result_ref=None` 是**合法**的
        （`G-03`：如实为空，**不得**臆造一个）。
        """
        from schema.models import CheckRecord, CheckScope, Task, TaskStatus, TaskType
        from schema.store import append_records, read_records
        from scripts.daily.degrade import last_valid_result_ref

        base_key = f"check::check_{result.run_date}_{result.scope}"
        prior = sum(
            1 for row in read_records(self.root, "tasks")
            if str(row.get("idempotency_key", "")).startswith(base_key)
        )
        suffix = "" if prior == 0 else f"_r{prior}"
        check_id = f"check_{result.run_date}_{result.scope}{suffix}"

        # ★ 本次运行**是否产出有效结果**（`Ch8 §E.1`）：`blocked` 或 `degraded` 都意味着
        #   "本次结果不完整，须保留上一次的"。二者任一为真，则本行的有效结果 =
        #   `last_valid_result_ref` 指向的旧结果，且不得把自己本轮的部分写入
        #   冒充成有效产出（`§E.4`：不得覆盖为无意义空值 / 不得标最新）。
        valid_run = not (result.blocked or result.degraded)
        # 追加序里的"上一次成功运行"—— **复用**唯一真源，不重算（见 docstring）。
        last_ref = last_valid_result_ref(self.root, scope=result.scope)
        produced: list[str] = []
        for step in result.steps:
            for ref in step.produced:
                if ref not in produced:
                    produced.append(str(ref))

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
            output_refs=produced if valid_run else [],
            last_valid_result_ref=None if valid_run else last_ref,
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
            if step.status == STATUS_SKIPPED:
                # ★ 断点续跑（`resume`）语义（批次 7 审计 `B2`）：该步在**上一轮已 `ok`**，
                #   本轮按设计跳过 —— 它不是"本轮未产出"，故**不计** G1-05 违例
                #   （否则 `resume` 在补跑任何一步时都会恒红，把真违规淹没在噪声里）。
                #   注意：这是**语义澄清**，不是放宽 —— `run_daily` 永不产生 SKIPPED，
                #   故它的判据强度**完全不变**。
                continue
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
            # ★ 「空执行」判据 = **既没有新写入、也没有幂等命中**。
            #
            #   为什么把 `skipped` 一并算作"非空"（批次 10 审计 `C-03` 裁定的推论）：
            #   `produced` 已被钉死为「本轮**新写入**的集合」（`tests/compute/test_step_wiring.py:48`），
            #   于是"同源同 quote_hash 重跑"必然 `produced=[]`。若此处仍只看 `produced`，
            #   则**正常的幂等重跑会被判成空执行违例** —— 一条天天误报的门禁，
            #   结局一定是被人关掉（`CONVENTIONS.md` 守卫铁律 1：降噪就是有效性）。
            #   而"读了 N 个对象、逐个判定均已存在、故无需追加"**不是**空执行，
            #   它是**已完成的检查**，其证据就是 `skipped` 非空。
            #
            #   ★ 判据强度**未削弱**：`produced` 与 `skipped` **双空**才判违例 ——
            #     一个"什么都不做"的桩处理器两者皆空，仍然被拦（反向对照见
            #     `tests/injection/test_idempotency_rows.py`）。
            #
            #   ★★ **边界如实登记（`G-42`，独立审计 2026-09-16 证伪了我的过强表述）**：
            #     我曾写"判据强度未削弱"，那只对**默认构造的桩**（`StepOutcome()`，两字段皆空）成立。
            #     审计构造了**对抗性桩**：`StepOutcome(produced=[], skipped=["我瞎编的"])`
            #     ⇒ `G1-05` 违例 **6 → 0**（实测）⇒ 本条**可被自报击穿**。
            #     ⇒ 准确表述：**`G1-05` 是"自报式不变量兜底"，能抓"忘记产出的意外"，
            #       不能抓"蓄意伪造的自报"**。后者只能由**换人审计 + 读代码**覆盖
            #       （这也正是 `§九 独立验收` 存在的理由）。
            #     ⇒ 本函数**拿不到 `root`**（签名是 `(result, registered_hooks)`），
            #       故无法在这里用真源校验 `skipped` 的 id 是否真实存在；要加那条需要改共享签名，
            #       已登记为缺口，**不在本次自裁范围**。
            #   ★ 下面这条**互斥校验**是我能在此处**可判定地**加的最强约束：
            #     同一个 id 不可能**既**是"本轮新写入"**又**是"已存在故未写入" ——
            #     违反即自相矛盾，必须响亮报出（也顺手堵住"把 produced 原样抄进 skipped"这种最偷懒的伪造）。
            elif set(step.produced) & set(step.skipped):
                v.append(
                    Violation(
                        "G1-05",
                        f"第 {step.step} 步（{step.name}）的 produced 与 skipped **相交**："
                        f"{sorted(set(step.produced) & set(step.skipped))} —— "
                        "同一对象不可能既'本轮新写入'又'已存在故未写入'（自报自相矛盾）",
                        "scripts/orchestrate/pipeline.py",
                    )
                )
            elif not step.produced and not step.skipped:
                v.append(
                    Violation(
                        "G1-05",
                        f"第 {step.step} 步（{step.name}）报 ok 但 produced 与 skipped 均为空（空执行）",
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
