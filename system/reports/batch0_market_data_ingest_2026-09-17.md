# 批次 0 落库回执 —— 行情与基准入真源（2026-09-17）

> **任务**：用 MCP 连接器把「行情 → `facts/prices.jsonl`」与「基准 → `facts/benchmarks.jsonl`」落进真源，
> 逐项报告「落了什么 / 来源是哪个连接器 / 口径是什么」，再重跑每日运行，最后贴 `wc -l`。
>
> **时效核对件（`V-11` 规矩 5）**：取样于工作树 `/Users/gaza/Developer/InvestSigh`，2026-09-17 08:0x–08:1x UTC。
> **一切数字都是当时读数**；重跑前先按 §6 重取。
>
> ★ **本文件回答的是一句实话**：该任务此前**没有**执行过（`prices`/`benchmarks` 均 0 行，工作树改动面不含这两个文件）。
> 本次是**第一次**执行。

---

## 0. 落库前后一行对照

| 项 | 落库前 | 落库后 |
|---|---|---|
| `facts/prices.jsonl` | **0 行** | **64 行** |
| `facts/benchmarks.jsonl` | **0 行** | **1 行** |
| `derived/derived_values.jsonl` | 1 行（仅毛利率） | **3 行**（+ 两个总回报） |
| `derived/compute_gaps.jsonl` | 2 行 | 3 行（+ `dv-gap-benchmark-AGIX`） |
| 每日运行 `blocked` | True（gaps=12） | **True（gaps=10）** |
| 每日运行 `degraded` | True | True |
| `run_all_gates` 非零计数 | 1 | **1**（未变） |
| `stage_gate --stage all` | FAIL(2) | **FAIL(3)** |
| `pricelayer/history_guard.py` | PASS(0)（空样本 note） | **FAIL(1)** |

---

## 1. 行情 → `system/facts/prices.jsonl`（64 行）

### 落了什么

| 项 | 值 |
|---|---|
| 行数 | **64** = 32 个交易日 × 2 个标的 |
| 标的 | `sec-nvda`（NVDA，研究标的）· `sec-agix`（AGIX，主基准 ETF，代码 `usAGIX.OQ` / iFinD `AGIX.O` / tdx `AGIX`+`setcode=74`） |
| 区间 | 2026-08-03 ~ 2026-09-16 |
| `snapshot_id` | `snap-sec-nvda-hfq-YYYYMMDD` / `snap-sec-agix-hfq-YYYYMMDD` |
| `price` | **iFinD 后复权收盘价**（见下口径） |
| `currency` | `USD` |
| `trading_session` | `regular` |
| `adjustment_caliber_version` | `ifind-hfq-v1` |
| `source_id` | `iFinD`（对齐 `rules/data-sources.allowlist.yaml::sources[].id`） |
| `delayed` | `True`（见下"延迟标注"） |
| `is_nav` | `False`（净值点另行取到但**不写**本表，见 §2） |
| 五类时间 | `occurred_at` = `published_at` = 交易日 **20:00Z**（= 美东 16:00 收盘；8–9 月均为 EDT=UTC−4）；`first_seen_at` = `analyzed_at` = `backfilled_at` = **2026-09-17T08:10Z**（资料日期早于补入日 ⇒ 如实标补入，`Ch9 §N9.1-31/32`）；`recorded_seq` = 1..64 |

### 来源是哪个连接器

| 用途 | 连接器 | 实测 |
|---|---|---|
| **后复权收盘价（`price` 的来源）** | **iFinD** `get_security_indicators` | NVDA 走 **美股**市场；AGIX 走 **基金**市场 |
| **交易日历（过滤非交易日）** | **westock** `data_kline` | 32 个真实交易日（已剔除周末与 2026-09-07 美国劳动节） |
| **延迟证据** | **tdx** `tdx_quotes` | NVDA 与 AGIX 的 `BaseInfo.DelayHQMin` 均 = **15** |

### 口径是什么

**① 复权口径：iFinD 后复权，`indicators_params` 已逐次回读核对 ✓**

| 标的 | 请求 | 回读 `indicators_params` |
|---|---|---|
| NVDA | `market="美股"`，"后复权收盘价" | `收盘价: {货币币种: 原始币种, 交易日期: 最新, **复权方式: 后复权**}` ✓ |
| AGIX | `market="基金"`，"后复权收盘价" | `区间收盘价: {**复权方式: 后复权**, 起始交易日 20260914, 截止 20260916}` ✓ |

**区间首尾两端的内部自洽校验**（后复权序列 ÷ 原始收盘价，比值应恒定）：

| 标的 | 2026-08-03 | 2026-09-16 | 判定 |
|---|---|---|---|
| NVDA | 108311.5875 / 206.413 = **524.73** | 112242.4151 / 213.90 = **524.74** | ✓ 恒定 ⇒ 区间内无拆股、序列自洽 |
| AGIX | 44.3029 / 43.62 = **1.01565** | 45.6232 / 44.92 = **1.01566** | ✓ 恒定 ⇒ 同上 |

★ **两个标的的复权基准差 500 倍，但收益率可比**（后复权基准在比值里约掉）；
**价格水平不可跨标的比较** —— 本表只用于算收益，不用于比价。

**② 交易日口径：改用 westock 日历，不直接用 iFinD 的日期列**

iFinD 的日频序列**含非交易日并按前值填充**（实测：`20260911/12/13` 三天同为 `114546.0346`，
而 09-12/13 是周六周日；`20260905/06/07` 同为 `120744.5668`，其中 09-07 是美国劳动节）。
⇒ 若直接落库会把非交易日写进追加式真源、污染收益序列。故**取 iFinD 与 westock 日 K 日期的交集**。

**③ 延迟口径：标 `delayed=True`（保守），并如实说明为什么这不完美**

`price` 是 **EOD 后复权收盘价**，既不是实时快照、也不是"延迟 15 分钟的实时行情"。
iFinD 自身的延迟分钟数**未披露**（`mcp_setup_brief.md` §四实测表该列为 ❌），
而 `PriceSnapshot.delayed` 是 **bool 二态**，无法表达"未披露 / EOD"这两种第三态。
⇒ 取**保守值 `True`**（设计红线是"延迟行情须显示延迟、**不得标实时**"，保守标注不违红线），
并把"二态表达力不足"登记为缺口（`gap-delayed-bool-two-state`）。tdx 实测的 `DelayHQMin: 15` 已记录在案。

---

## 2. 基准 → `system/facts/benchmarks.jsonl`（1 行）

### 落了什么

| 字段 | 值 | 来源 |
|---|---|---|
| `benchmark_id` | **`AGIX`** | 依 `rules/freeze.yaml::p01` 的 `suggested_value`（**未冻结**，`freeze_status: tbd`）；`rules/benchmark.yaml::freeze_status: unfrozen`（AGIX = 工作假设） |
| `benchmark_role` | `primary` | 同上 |
| `coverage_profile.tracking_index` | **`Solactive Etna人工智能通用智能指数`** | **iFinD 基金市场**（westock 取不到） |
| `coverage_profile.unit_nav` / `unit_nav_date` / `unit_nav_currency` | **`45.03`** / `2026-09-16` / `USD` | **iFinD 基金市场**（westock 取不到） |
| `coverage_profile.listing_date` | `20240718` | iFinD 基金市场 |
| `coverage_profile.p01_status` | 「依建议值、未冻结（… `freeze_status=tbd`；AGIX=工作假设）」 | 如实标注，按任务书要求 |
| `return_basis` | `same_start_end=true, currency=USD, dividends_reinvested=true, price_kind=market_price_total_return, fee_deducted_again=false, version=v1` | 设计既有口径；`dividends_reinvested=true` 现由**实测分红事件**支撑 ↓ |
| `return_source` / `proxy_index_used` | `fund_market_price` / `false` | `Ch3 §D.2` 红线（不得用公开指数充当基金） |
| `includes_non_listed_assets` | **`true`** | `rules/benchmark.yaml` 逐字声明（见下"一处真红"） |
| `non_listed_assets` | `{gap_note: "披露状态 undisclosed（rules/benchmark.yaml 逐字）；iFinD 成分接口返回空表 ⇒ 点值/权重不可得，不硬编"}` | 缺口显式记录 |
| `sensitivity` | `{disclosure_state: undisclosed, basis: "权重未披露 ⇒ 敏感性不可算；按 §J8 缺口+敏感性、不硬编点值"}` | 显式声明不可算 |
| `unverifiable_forecasts` | `[]` | **显式"没有此类预测"**（≠ `None`） |
| `modeled_coverage` | `None` | 未给 ⇒ ⑥⑦ 不可判定（如实；不默认 1.0） |
| `claims_complete_forecast` | `false` | 不声称"完成整个基金预测" |
| `freeze_status` | `unfrozen` | 同上 |
| `change_records` | 1 条：`{effective_date: 2026-09-17, reason: "首次落库", version: "1", approved_by: "pending_human_approval"}` | 基准变更须人工审批（`Ch3 §N4.4-08/09`），本行**如实标未审批** |

### 公司行动（分红 / 拆股）：tdx 深度资料

| 查询 | 连接器 | 结果 |
|---|---|---|
| AGIX 拆股并股（2023-09-17 ~ 2026-09-17） | **tdx** `tdx_security_deep_info` → `f9_us_split_reverse_split` | **0 行**（区间内无拆股/并股） |
| AGIX 分红派息明细（同区间） | **tdx** `tdx_security_deep_info` → `f9_us_dividend_payout_detail` | **2 行**：除息 2025-12-22 每股 **$0.437658**；除息 2024-12-17 每股 **$0.109841**（美元） |

⇒ 这两条**实测事件**支撑 `return_basis.dividends_reinvested: true` 是"有分红的基金、须含再投资"，
而不是照抄设计默认值。
★ 但**没有**把它们写进 `registry/corporate-actions.jsonl` —— 见 §4 的口径耦合风险。

---

## 3. 重跑每日运行的变化（如实）

```
python system/scripts/daily/run.py system --date 2026-09-17 --scope full     # exit=0
```

| 项 | 落库前 | 落库后 |
|---|---|---|
| `blocked` | **True** | **True**（未变） |
| `degraded` | True | True（未变） |
| `changed` / `signals_emitted` | False / 0 | False / 0（未变） |
| **`gaps`** | **12** | **10**（−2） |
| `coverage_ok` / `violations` | True / 0 | True / 0 |

**−2 那两条是什么**：step 5 由 `gap` 变 **`ok`**，其两条 gap（"基准 p01 / tbd 无法解析"）消失。
**step 5 第一次真的产出了东西**：

| `derived_id` | 值 | 公式 |
|---|---|---|
| `dv-total_return-sec-nvda-2026-08-03..2026-09-16-compute-v1` | `0.036291847351974228` | `total_return(2026-08-03..2026-09-16)` |
| `dv-total_return-sec-agix-2026-08-03..2026-09-16-compute-v1` | `0.029801660839358145` | 同上 |

★ 这是本系统**第一次算出收益**（此前 `derived/` 只有一条毛利率）。

**仍未变的部分**：`blocked` 仍 True —— step 2/3/4/6 的 gap 与 step 7/8 的 `deferred_by_design` 照旧。
step 6 的 gap 文字仍是"上游输入为空或缺失"。

**★ 新增一条真事实**：`derived/compute_gaps.jsonl` 多了一行 `dv-gap-benchmark-AGIX`：

```
AGIX: 无法解析基准对应证券（未声明 security_id，且行情非唯一证券）
```

**这一行是本次最重要的产出**：现在 `prices` 里**已经有 AGIX 的行情**、`benchmarks` 里**已经有 AGIX 的行**，
但基准**依然解析不出**。⇒ **相对收益算不出来，卡点在 schema（`Benchmark` 无 `security_id` 字段），不在数据。**
（`scripts/compute/driver.py::_resolve_security` 的 `benchmark.get("security_id")` 是**死分支**；
唯一回退"prices 里唯一证券"在 ≥2 个证券时恒失效，而恰好 1 个时会**静默把个股当基准**。）

---

## 4. 落库带来的一处真红，与三处口径隐患

### 4.1 `pricelayer/history_guard.py` = **FAIL(1)**（新红，且是真红）

```
[FATAL] BENCHMARK-COVERAGE — AGIX: 缺 holdings_disclosure_lag — 公开持仓披露延迟必须显式标注（Ch5 §E.1）
```

**为什么不是"没填全"**：`check_benchmark_special_cases` 的 ①–⑤ 只在
`includes_non_listed_assets` 为真时生效，而 `rules/benchmark.yaml` 逐字声明 AGIX **含非上市资产**。
其中：

| 判据 | 状态 |
|---|---|
| ① 有 `non_listed_assets` 条目 | ✅ 已给（含 `gap_note`，`NON_LISTED_ASSET_REQUIRED_KEYS = ("gap_note",)`） |
| ② 条目有 `gap_note` | ✅ |
| ③ 有 `sensitivity` | ✅（显式声明"权重未披露 ⇒ 敏感性不可算"） |
| ④ 有 `holdings_disclosure_lag` | ❌ **填不出** —— iFinD 基金市场「重仓股 / ETF 成分」对 `AGIX.O` 返回**空表**；tdx 会话过期未能复核 ⇒ **该事实不可得** |
| ⑤ 显式给出 `unverifiable_forecasts` | ✅ `[]` |

⇒ **我没有把 `includes_non_listed_assets` 改成 `false` 来换绿**（那会与锁定的设计真源冲突、且是把"未知"写成"已知"）。
**这一条红 = "声明了非上市资产，却没有持仓披露延迟的事实"** —— 是系统在如实报缺。
**两条出路（需需求方/实现方裁）**：① 补 AGIX 公开持仓披露延迟的事实；
② 裁定 AGIX 不含非上市资产（`rules/benchmark.yaml` 的 `true` 是未核验的工作假设，其 `freeze_status: unfrozen` 本就允许替换）。
**在裁定前，这条红会一直挂着。**

### 4.2 `stage_gate` FAIL(2 → 3)

新增的第 3 条与落库无关，是**又跑了一次每日运行**的结果：
每多一条失败运行记录，就多一条 `last_valid_result_ref` 假红 FATAL（见
`nvda_e2e_run_2026-09-17.md §4.1` 的两谓词打架根因）。本次新增的是 `task_check_2026-09-17_full_r1`。

### 4.3 口径耦合风险：后复权价 + 公司行动表 = 可能重复计分红

`scripts/compute/returns.py::_total_return_value` 的机制是「**先复权再总回报**」——
它自己对 `split` 折算 `shares`、对 `div` 做再投资。而本次 `prices` 里存的**已经是后复权价**。
⇒ 若再把 §2 那两条分红事件写进 `registry/corporate-actions.jsonl`，**分红会被计两次**。
当前该文件 **0 行**，故未发生；但"后复权价 + 公司行动表"这一组合**没有任何机器绑定**（`gap-hfq-vs-corporate-actions-double-count`）。

### 4.4 两处载体被强行借用（已登记）

- **`coverage_profile`**：`Benchmark` 模型**没有**「单位净值」「跟踪指数名」字段 ⇒ 只能塞进这个自由 dict。
  而它的既有定位是"13-E 裁定后 5 个新字段的第二份载体、须由消费方删除"（`G-06`）⇒ 语义被混用。
- **`delayed: bool`**：见 §1 ③。
- 另：`facts/prices.jsonl` 引用了 `security_id="sec-agix"`，而 `facts/securities.jsonl` 只有 `sec-nvda`
  ⇒ **悬挂引用**（根因：`Security.company_id` 必填，ETF 无公司主体）。

---

## 5. 落库动作本身不可复现（必须说）

**没有任何代码调用 MCP 并落库** —— 这正是 `test_run_sheet_batched.md §0.2` 早先判定的"只差写脚本"。
本次执行方式是：会话内分次调用连接器 → 把返回值搬进临时脚本 → `schema/store.append_records` 落库。
⇒ 代价：**交易日历与口径过滤逻辑不在版本库里**，重跑必须重新取数、重新做一遍交集过滤。
建议补 `scripts/ingest/market_data.py`（`gap-mcp-fetch-not-reproducible`）。

**落库后新登记的 9 条缺口任务**（`facts/tasks.jsonl`，`idempotency_key = research::<gap_id>`）：
`gap-benchmark-security-id-dead-branch` · `gap-history-guard-holdings-disclosure-lag` ·
`gap-ifind-agix-us-market-empty` · `gap-ifind-nontrading-forwardfill` ·
`gap-hfq-vs-corporate-actions-double-count` · `gap-sec-agix-no-security-row` ·
`gap-delayed-bool-two-state` · `gap-benchmark-no-carrier-nav-tracking-index` ·
`gap-mcp-fetch-not-reproducible`

---

## 6. `wc -l` 与复现命令

```bash
wc -l system/facts/prices.jsonl system/facts/benchmarks.jsonl
#       64 system/facts/prices.jsonl
#        1 system/facts/benchmarks.jsonl
#       65 total
```

```bash
V=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python

# 落库后终态
"$V" system/scripts/daily/run.py system --date 2026-09-17 --scope full      # exit=0, blocked=True, gaps=10
"$V" system/scripts/ops/run_all_gates.py --timeout 30                       # 非零计数 1（no_signal_day::G1-02③）
"$V" system/scripts/delivery/stage_gate.py system --stage all               # FAIL(3)
"$V" system/scripts/pricelayer/history_guard.py system                      # FAIL(1) —— 见 §4.1
"$V" system/scripts/benchmark/return_guard.py system                        # PASS(0)

# 派生值与基准解析
"$V" -c "import sys;sys.path.insert(0,'system');\
from pathlib import Path;from scripts.compute.driver import load_benchmark_objects,load_price_points,_resolve_security;\
bm=load_benchmark_objects(Path('system'));ps=load_price_points(None,Path('system'));\
print([b.get('benchmark_id') for b in bm], sorted(ps), [_resolve_security(b,ps) for b in bm])"
# 期望：['AGIX'] ['sec-agix','sec-nvda'] [None]
```
