---
name: aichain-daily
description: 每日运行的编排契约——按 8 步顺序跑完整链路，写 check_record 与 state.json 游标，无变化日不得产出信号。用于「今天跑一遍研究链路」。
---

# `aichain-daily` —— 每日运行编排

> **权威出处**
> - 名称与职责：`00_交付施工图 §3.2`（`skills/aichain-daily`，出处 `Ch8 §H`）
> - 8 步顺序与反 KPI：`Ch1 §B` / `§F`，声明落 `rules/pipeline.yaml`
> - 模块 I/O 契约：`Ch9 §3.5`（①–⑥ 全链）
> - 降级契约：`Ch8 §E`
> - 交付阶段：`registry/delivery.yaml::daily_run`（阶段④）

---

## 1. 编排实现（唯一入口）

`scripts/orchestrate/pipeline.py` 的 `Pipeline`：

| 能力 | 说明 |
|---|---|
| `register_step` | 声明 8 步中每一步 |
| `register_publish_hook` / `register_verify_hook` | 第 7/8 步的钩子（阶段① 尚未实现 → 落到 `gap`） |
| `run_daily` | 跑一次完整链路，返回 `RunResult` |
| `resume(task_id)` | 从 `state.json` 游标续跑 |
| `assert_steps_complete`（G1-05） | 步不全 → **fail**，不得"跳过某步但算成功" |

`StepResult.status ∈ {ok, gap, blocked, failed, skipped}`。
`blocked` / `failed` **必须**带原因；`skipped` 必须有显式声明。

## 2. 8 步闭环（`rules/pipeline.yaml` 声明）

`rules/pipeline.yaml` 是本流程的**声明式真源**：每步含
`implemented_in_first_version` 与（未实现时）`gap_behavior`。

★ **首版未实现的步骤必须显式标 `gap`**，不得静默跳过
（纪律 12：阶段未过即阻塞，不得静默跳过）。

## 3. 幂等：重跑同日不重复（`Ch9 §N9.2-11`）

| 对象 | 幂等键 |
|---|---|
| 采集 | (`source_id`, `content_hash`) |
| 核验 | (`source_id`, `quote_hash`) |
| 传导 | `event fingerprint` |
| 估值 | (`company_id`, `version`, `method_version`) |
| 决策 | (`security_id`, `issued_at`, `version`) |
| 发布 | (`view_target`, `source_version`) |

**重跑同日不得重复生成事件 / 建议**。实现上还有一个易错点：`check_record`
的幂等键也必须唯一 —— `Pipeline._write_check_record` 用 `_r<n>` 后缀保证
同一天多次运行不会写重复键（追加式不可变下，重复键 = 脏数据）。

## 4. 反 KPI / 反拖延（`Ch1 §F`）

| 规则 | 断言 | 违反 |
|---|---|---|
| **反 KPI** | **无变化日产出信号数必须 = 0** | 硬凑信号充数 |
| `change_reason` | 每条变化**必填** | 空理由 |
| 反拖延 | 阈值 `N` 只在 `rules/review.yaml::anti_delay` | 把 `N` 抄进 `freeze.yaml`（双写） |
| 强制复查 | 单日 ≤ −7% 或 3 日累计 ≤ −12% → 强制复查；`is_stop_loss: false` | 把它当止损 |

守卫：`scripts/checks/no_signal_day.py`（三条断言，从 `facts/tasks.jsonl` 的
`check_record` 子记录读）。

## 5. 时点与覆盖可核（阶段④ 通过判据）

| 可核项 | 手段 |
|---|---|
| 时点可核 | 五类时间 + 双时间轴 `store.as_of` |
| 覆盖可核 | `research_coverage_set ⊇ recommended_security_scope_set`（`rules/scope.yaml`） |
| 任务状态可核 | `facts/tasks.jsonl` 五态 + `check_record` |
| **降级保留上次有效结果** | `last_valid_result_ref` + `stale_since`；**不置 null / 不标最新** |

## 6. 调度与通知（阶段④ 前置，现在留 `tbd`）

- `rules/schedule.yaml`（运行时刻 / 时区 = `freeze_param p07`）、`rules/trigger.yaml`（五类触发）
- `rules/notification.yaml`、`rules/publish.yaml`
- **值一律 `tbd`，只存指针**：值只在 `rules/freeze.yaml`（纪律 5）
- Automation 承担周期触发；时区随阶段④ 前置冻结（`§十二 N-05`）

## 7. 本流程**不得**做的事

- ❌ 无变化日产出信号（反 KPI）
- ❌ 跳过某一步却报告"运行成功"
- ❌ 失败时置 `null` / 标"最新" / 丢弃上次有效结果
- ❌ 重跑同日写出重复事件或重复建议
- ❌ 把 `rules/review.yaml` 的阈值抄进第二份文件
