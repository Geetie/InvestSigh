---
name: aichain-ask
description: 研究提问入口——把一句自然语言问题变成可追溯的研究任务，产出三件输出（当前结论 / 依据链 / 缺口）。用于「问一下某公司某问题」。必须落库，不得只给一段听起来合理的回答。
---

# `aichain-ask` —— 提问入口

> **权威出处**
> - 名称与职责：`00_交付施工图 §3.2`（`skills/aichain-ask` + `scripts/tasks/ask_to_task.py`，出处 `Ch8 §C`）
> - 任务契约：`Ch8 §C`（`facts/tasks` 五字段 + 五态状态机 + `parent_context`）
> - 模块 I/O 契约：`Ch9 §3.5`
> - 反敷衍判据：源稿原话「**不能把……'问答听起来合理'作为研究完成的充分条件**」

---

## 1. 输入 / 输出

| 输入 | 输出（**三件，缺一不可**） |
|---|---|
| 一句自然语言问题（+ 可选 `parent_context`） | ① **当前结论**（含 `status`：可判断 / 待判断 / 无法判断）<br>② **依据链**（`claims` → `impacts` → `derived` → 规则版本 + 证据版本）<br>③ **缺口**（缺什么、什么条件下能补上） |

★ 输出**必须**落成对象：`facts/tasks.jsonl` 一条任务 + 缺口经
`scripts/tasks/gap_to_task.py` **幂等入队**。

## 2. 任务契约（`Ch8 §C`）

| 项 | 内容 |
|---|---|
| 五字段 | 见 `Ch8 §C`（`facts/tasks` 契约） |
| 状态机 | 五态；迁移必须经 `ALLOWED_TRANSITIONS` 断言 |
| `parent_context` | 承接上游任务上下文（提问可以是某条推荐的后续） |
| 幂等 | 重复提问 → **命中幂等键即跳过**，不得重复建任务 |

幂等键与入队实现：`scripts/tasks/gap_to_task.py`（`IdempotentTaskQueue`）。
`enqueue` 永远成功、`execute` 受 cap 约束 —— 保证"缺口不会因为队列满而丢失"。

## 3. 追溯：每个结论都必须能回答"凭什么"

`scripts/trace/traceback.py` 提供 `traceback()`，覆盖四要素：

| 要素 | 含义 |
|---|---|
| `evidence` | 证据（`claims` + 定位） |
| `assumptions` | 假设（显式列出） |
| `computation` | 计算（`Derivation`，含 `method_version`） |
| `prev_version_id` | 上一版本（为什么改了） |

`traceback_coverage()` 在**空样本**上**抛错**而不是返回 `1.0`——空样本返回满分是典型的"假通过"。

★ 覆盖不齐时**不得**输出"看起来合理"的结论；必须降为**待判断**并把缺项写成缺口任务。

## 4. 状态语义（`Ch7 §D` / `Ch2 §C.3`）

| 状态 | 含义 | 禁止 |
|---|---|---|
| `active` | 有依据、可判断 | — |
| `confident_underperform` | 有依据地判断"跑不赢" | 与 `boundary_unresolved` **并列，不并入** |
| `uncertain` | 已研究但不足以定论 | 不得渲染成"中性" |
| `boundary_unresolved` | 传导边界未解 | 不得渲染成"无投资机会" |
| `superseded` | 被新版本取代 | 追加式：旧版本保留、as-of 可查 |

★ **待判断 ≠ 未完成研究**（`Ch3 §D.1`）：前者=已研究但不足定论；后者=尚未研究。
**未研究禁止渲染为"中性/无机会"**（`scripts/views/neutrality_check.py` 真跑拦截）。

## 5. 守卫

| 守卫 | 拦什么 |
|---|---|
| `gap_to_task.py` | 状态机非法迁移；缺口静默丢失 |
| `traceback.py` | 追溯四要素不齐 |
| `neutrality_check.py` | 未研究伪装中性 / 默认折叠反证 |
| `no_signal_day.py` | 无变化日却产出信号；`change_reason` 缺失 |
| `no_placeholder_guard.py` | 用假数据把流程"跑通" |

## 6. 本流程**不得**做的事

- ❌ 不得把"问答听起来合理"当作研究完成（源稿明文禁止）
- ❌ 不得只输出一段散文而不落 `tasks` / 不写出缺口
- ❌ 不得用推测补齐缺失证据（缺就记缺口）
- ❌ 不得因为有下游压力就跳过 `traceback` 覆盖检查
