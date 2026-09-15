---
name: aichain-claim-extract
description: 多源采集与主张核验编排——把原始物变成带定位的 claims。用于「抓取/核验某来源说了什么」「这条消息出自哪、原文在哪」。至少包含失败降级与备选切换。
---

# `aichain-claim-extract` —— 采集 + 核验

> **权威出处**
> - 名称与职责：`00_交付施工图 §3.3`（`skills/aichain-claim-extract`，出处 `Ch6 §D`）
> - 模块 I/O 契约：`Ch9 §3.5`（① 采集 / ② 核验 两行，逐字）
> - 详细设计：`06_公开信息与证据筛选/02_实现方案.md`
> - 模块化依据：`Ch9 §N9.2-09`（首版先明确模块输入输出；**不要求多 Agent 网络**）

**这不是"一个 Agent"，是一条流程契约。** 由 1 个编排器依次调用确定性模块即可
（`Ch9 §3.5` 前言：「每阶段的 I/O 均落为对象（可被 `task_id` 引用）；
跑一个或多个 Agent 均可，不强制多 Agent 网络」）。

---

## 1. I/O 契约（`Ch9 §3.5` 逐字）

| 阶段 | 输入 | 输出 | 幂等键 | 失败处理 | 依赖 |
|---|---|---|---|---|---|
| **① 采集** | 来源登记项、调度窗口 | `raw/*`（原始物）+ `sources` 记录 | (`source_id`, `content_hash`) | 主源失败 → 切备选；全失败 → 标 stale 并保留上次有效结果 | registry |
| **② 核验** | 原始物 | `claims`（含定位、主张性质）+ `claim_propagation` | (`source_id`, `quote_hash`) | 无法定位 → 保留待核验任务 | ① |

## 2. 落位

| 产物 | 落位 | 说明 |
|---|---|---|
| 原始物 | `raw/` | 页面快照 / PDF / 字幕 / 合法保留片段 |
| 来源记录 | `facts/sources.jsonl` | 每条来源**必须唯一分级**（`Ch6 §N6.2-01`） |
| 主张 | `facts/claims.jsonl` | `tier ∈ {primary, secondary_1_5, secondary_tertiary}`（`Ch6 §N6.2-03/04`） |
| 传播 | `facts/claim_propagation.jsonl` | 去重 / 传播 / 独立判定 |
| 来源登记 | `registry/sources.yaml` | 登记字段 + 时延策略 + 健康度 |
| 分级规则 | `rules/tiering.vN.yaml` | 版本化；改分级 = 新版本 |
| 定位校验 | `scripts/validators/locator_check.py` | **程序拦截**，不是模型自觉（`Ch6 §D`） |

## 3. 写入口与读出口（唯一真源纪律）

- **写**：一律经 `schema.store.append_records(code_root, "<stem>", [...])`。
  **不存在** UPDATE / DELETE 路径（`Ch9 §3.4.2` 追加式不可变）。
- **读**：`schema.store.read_records` / `read_models`；时点查询走 `store.as_of`（双时间轴）。
- **参数**：任何阈值 / 预算值一律 `config.freeze.get_param("<pid>")`，值只在
  `rules/freeze.yaml`（纪律 5）。本流程**不得**硬编码任何阈值。

## 4. 五类时间（`Ch9 §2.2`）

写入时必须同时给：`occurred_at` / `published_at` / `effective_from`（valid 轴）、
`first_seen_at` / `analyzed_at` / `recorded_seq`（system 轴）、
`backfilled_at`（事后补入标记）。

★ **事后补入的资料，`first_seen_at` 一律写"补入日"，不得回填为资料日期** ——
否则事后信息会伪装成"当时已知"，整套 as-of 重建失效。
（实例：44 个原型节点，`occurred_at = 2026-09-08` 而 `first_seen_at = 补入日`。）

## 5. 失败与降级（`AC-05`）

| 情形 | 必须的动作 | 禁止 |
|---|---|---|
| 主源不可用 | 切备选来源；记录切换事实 | 静默改用另一源而不留痕 |
| 全部来源失败 | 标 `stale_since` + **保留上次有效结果** | 置 `null` / 标"最新" / 返回空列表冒充成功 |
| 无法定位原文 | 生成**待核验任务**（`scripts/tasks/gap_to_task.py`） | 放弃定位但照常出 claim |
| 接口限流 | 明确降级状态 + 退避 | 吞异常 `except: pass` |

## 6. 守卫（本流程必须过的门）

| 守卫 | 位置 | 拦什么 |
|---|---|---|
| `no_placeholder_guard.py` | `scripts/checks/` | 空函数体 / 假数据 / 吞异常 / 硬编码兜底 |
| `conflict_scan.py --timing ci` | `scripts/checks/` | L1–L5 聚合（含配置禁词 L3） |
| `append_only_guard.py` | `scripts/checks/` | 改写 `facts/*.jsonl` 既有行 |
| `rules_lock_guard.py` | `scripts/checks/` | `rules/` 权限与哈希被改 |

## 7. 本流程**不得**做的事

- ❌ 不得引入 `rules/banned_tokens.yaml` 里的任何禁词作为**标识符**
- ❌ 不得把"没有来源"的内容写成 `claims`（**不填入猜测的事实数值**）
- ❌ 不得因为"这条消息很有说服力"就跳过定位
- ❌ 不得新增模块 `gold` / `btc` / `crypto` / `cross_asset_allocation` /
  `portfolio_weight_optimizer` / `account_management` / `trade_execution`
  （`Ch3 §D.3` `DENIED_MODULES`）
