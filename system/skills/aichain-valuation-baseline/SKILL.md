---
name: aichain-valuation-baseline
description: 公司价值研究与估值基线——把 claims/impacts 变成研究基线与 DerivedValue。用于「这家公司的价值基线是什么」「这个数怎么算出来的」。算术必须程序化，模型不得口算。
---

# `aichain-valuation-baseline` —— 估值与基线

> **权威出处**
> - 名称与职责：`00_交付施工图 §3.3`（`skills/aichain-valuation-baseline`）
> - 模块 I/O 契约：`Ch9 §3.5`（④ 估值 行，逐字）
> - 详细设计：`04_公司价值研究与深度标准/02_实现方案.md`
> - 深度标准：`Ch4 §G`
> - 数值保真：`Ch9 §2.3`（`NumericClaim` / `Derivation`）

---

## 1. I/O 契约（`Ch9 §3.5` 逐字）

| 阶段 | 输入 | 输出 | 幂等键 | 失败处理 | 依赖 |
|---|---|---|---|---|---|
| **④ 估值** | baselines、impacts、prices | `derived/*`（DerivedValue）、`expectations` | (`company_id`, `version`, `method_version`) | 输入缺失 → 输出缺口对象，**不出数值** | ③ |

## 2. 落位

| 产物 | 落位 | 说明 |
|---|---|---|
| 研究基线 | `facts/baselines.jsonl` | 人读部分可落 Markdown + YAML frontmatter |
| 派生值 | `derived/` | 每个值**必带**公式与操作数引用 |
| 预期样本 | `facts/expectations.jsonl` | 每条带 `source_id`（禁无源聚合） |
| 价格快照 | `facts/prices.jsonl` | 带 `PriceSnapshot` 与资料日期 |
| 驱动器模型 | `facts/` 的 `DriverModel` | 承 `ValueStateRefs` |
| 基准 | `facts/benchmarks.jsonl` | 对象化；身份值只在 `rules/freeze.yaml::p01` |

## 3. 数值保真：`NumericClaim` / `DerivedValue`

**算术必须程序化**（`Ch9 §N9.2-03`：模型不口算）。每个数值必须能回答：

- `raw_text` —— 原文怎么写的？
- `locator` —— 原文在哪（可复查）？
- `unit_scale` / `currency` / `period_reported` / `period_normalized_start|end` —— 口径是什么？
- `is_derived` —— 是直接披露还是算出来的？
- `derivation{formula, operands[], method_version}` —— 怎么算的、用了谁、哪个版本的方法？

★ `method_version` 变了 → **必须**产生新的 `DerivedValue`，不得就地覆盖
（追加式不可变 + 版本事件 `financial_restatement`）。

★ 输入缺失时**输出"缺口对象"**，不得输出 `None` / `0` / 估算值冒充实值。

## 4. 三份判断**不许合并**（`Ch9 §N9.1-20`）

| 判断 | 含义 | 禁止 |
|---|---|---|
| 外部预期 | 别人怎么预期（带 `source_id`） | 不得聚合成"一致预期 / 共识价" |
| 价格隐含 | 现价隐含了什么 | 不得当成"市场错了" |
| 独立判断 | 我们自己的判断 | 不得被前两者替代 |

命名**不得**升级为"一致预期"；三者**不得**合并成一个数。

## 5. 守卫

| 守卫 | 拦什么 |
|---|---|
| `return_guard.py` | 基准收益来源必须是基金本身行情；禁二次扣费；`nav_return` 只能标 `diagnostic` |
| `rules_lock_guard.py` | 基准口径 / 参数的哈希与权限未被私改 |
| `conflict_scan.py` L1 | `Recommendation` 上不得出现置信度/共识类字段 |
| `no_placeholder_guard.py` | 缺口处**不得**用假数填充 |

## 6. 本流程**不得**做的事

- ❌ 不得把无 `source_id` 的外部预测聚合"共识价"（P-07）
- ❌ 不得让模型口算并直接把结果当 `DerivedValue`（算术必须在 `scripts/compute/`）
- ❌ 不得在输入缺失时输出数值（必须出缺口对象）
- ❌ 不得用 `past_return` 预测收益（`Ch5 §E history_guard`，P-08）
- ❌ 不得把"净值收益"用于相对收益判定（`Ch3 §D.2` ③）
