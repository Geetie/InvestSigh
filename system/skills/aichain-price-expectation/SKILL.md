---
name: aichain-price-expectation
description: 价格与市场预期研究——把行情与预期样本落到 prices/expectations，并做反向估值。用于「现在价格隐含了什么预期」「预期是谁给的、出自哪」。
---

# `aichain-price-expectation` —— 价格与市场预期

> **权威出处**
> - 名称与职责：`00_交付施工图 §3.3`（`skills/aichain-price-expectation`）
> - 模块 I/O 契约：`Ch9 §3.5`（④ 估值 行的 prices / expectations 部分）
> - 详细设计：`05_价格与市场预期研究/02_实现方案.md`
> - 命名纪律：`Ch9 §N9.1-20`（**不得**升级为"一致预期"）
> - 收益口径：`Ch3 §D.2` / `Ch9 §N9.1-22/23`

---

## 1. I/O 契约（`Ch9 §3.5` 逐字，④ 估值行）

| 输入 | 输出 | 幂等键 | 失败处理 |
|---|---|---|---|
| baselines、impacts、**prices** | `derived/*`、**`expectations`** | (`company_id`, `version`, `method_version`) | 输入缺失 → 输出缺口对象，不出数值 |

## 2. 落位

| 产物 | 落位 | 说明 |
|---|---|---|
| 价格快照 | `facts/prices.jsonl` | `PriceSnapshot`；带 `occurred_at` 与 `first_seen_at` |
| 预期样本 | `facts/expectations.jsonl` | 每条**必须**带 `source_id` |
| 基准 | `facts/benchmarks.jsonl` | `primary` / `secondary` 两个对象 |
| 基准口径 | `rules/benchmark.yaml` | 只声明**对象**；身份值 = `rules/freeze.yaml::p01` |

## 3. 基准收益三条硬口径（`Ch3 §D.2`）

| # | 断言 | 反例（= 失败） |
|---|---|---|
| ① | `return_source == "fund_market_price"` | 用公开股票指数替代整只基金 |
| ② | `fee_deducted_again is False` | 相对收益里二次扣费 |
| ③ | `nav_return` 只能标 `role = "diagnostic"` | 用净值收益做相对收益判定 |

★ 三条都由 `scripts/benchmark/return_guard.py` 真跑拦截（**不是**靠提示词自律）。

★ 基准变更**不覆盖**：新增版本 + `effective_date` + `reason` + `version` + 人工审批
（`Ch3 §D.2` / `Ch9 §3.4.12`）。旧口径结果保留、as-of 可查。

## 4. 三份判断**不许合并**（`Ch9 §N9.1-20`）

- **外部预期** 与 **价格隐含** 与 **独立判断** 是**三份**，分别可查、分别带来源。
- 命名**不得**升级为"一致预期 / 共识价"；**不得**把三者平均成一个数。
- 缺付费预期库时：**仍可**做反向估值与独立研究，但**必须披露覆盖缺口**
  （`registry/launch_criteria.yaml` 的 `consequence_if_absent`）。

## 5. 行情过期与降级（`AC-05`）

| 情形 | 必须的动作 | 禁止 |
|---|---|---|
| 行情过期 | 标 `stale_since` + 明确降级态 | 标"最新" |
| 无行情 | 出**缺口对象** + 待核验任务 | 置 `null` 后继续算 |
| 公司行动（拆股/分红） | 走 `registry/corporate-actions.jsonl`（含 `direction` 消歧） | 静默改价 |

## 6. 守卫

| 守卫 | 拦什么 |
|---|---|
| `return_guard.py` | 三条收益口径断言（N3.4-05/07） |
| `conflict_scan.py` L1 | `Recommendation` 上不得出现 `consensus` / `market_view` / `average_forecast` |
| `freeze_guard.py` | 基准身份参数被补成新门槛 / 锚点写成绝对行号 |
| `no_placeholder_guard.py` | 缺口处填假数 |

## 7. 本流程**不得**做的事

- ❌ 不得用公开指数充当基金（`proxy_index_used` 必须为 `false`）
- ❌ 不得把外部预测样本聚合成"一致预期"
- ❌ 不得用净值收益做相对收益判定
- ❌ 不得为凑覆盖面而纳入未过门槛的对象（`scripts/scope/anti_padding.py` 会拦）
