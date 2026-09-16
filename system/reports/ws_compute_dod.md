# DoD · 并行工作流 `ws/compute` —— 确定性计算层 `scripts/compute/`

> 依据：`00_开发Agent开工提示词.md §5.1`（先写 DoD 再写代码；≥1 条错误路径 + ≥1 条边界）。
> 设计权威：`Ch9 §3.4.4`（确定性计算层）/ `§3.4.5`（NumericClaim 9 字段）/ `§3.5` 阶段④（模块 I/O 契约）
> ／ `§2.4.3`（计算由程序完成，排除清单）／ `Ch3 §D.2`（基准收益三条硬口径）／ `Ch4 §D.3`（增长质量分档）
> ／ `Ch5 §B.3`（模型不做算术、程序不做假设）/ `§D.2`（可追溯链）/ `§D.6`（区间宽度 + 概率默认 null）。
> 施工纪律：`00_交付施工图.md §8`（12 条）；开发规范：`system/CONVENTIONS.md`（G/P/R 系列）。

## 任务一句话

**建 `scripts/compute/` 确定性计算层**：所有算术由程序产出、可追到 operand；基准收益只经
`scripts/benchmark/return_guard.py`（唯一真源）；输入缺失 → 输出**缺口对象**（不出数值）；
`method_version` 变更 → **新 `DerivedValue`**（追加式不可变，不就地覆盖）。

## 交付物清单（本工作流模块清单 —— 只改这些）

- 新增/填充：`system/scripts/compute/**`
- 新增测试：`system/tests/compute/**`
- 报告：`system/reports/ws_compute_dod.md`（本文件）· `system/reports/ws_compute_report.md`

## 逐条可测的验收标准（AC）

### AC-01 真跑通
- [ ] **触发方式**：`python system/scripts/compute/run_derived.py <code_root>`（真实读取 `facts/`＋`rules/`＋`registry/`＋真实行情输入文件）
- [ ] **可观察结果**：落盘 `derived/derived_values.jsonl` 出现**真实** `DerivedValue`（含 `formula`＋`operands`＋`method_version`＋`computed_at`），且同一命令的退出码为 **0**
- [ ] **不是单测调通**：证据 = 真命令行原样 stdout＋退出码（非 pytest 断言）
- [ ] **真实输入来源**：`usAGIX`（KraneShares 人工智能 ETF）真实日线（westock MCP 连接器抓取，抓取日 2026-09-16，区间 2026-03-11~2026-09-15），落 `tests/compute/fixtures/agix_prices.jsonl` 供复现

### AC-02 持久化（write-read-reload）
- [ ] 写入 `derived/derived_values.jsonl` → **删 `index/`** → `schema.store.rebuild_index()` 重建 → 重读 `derived/` 数据**仍在**（`derived/` 是**真源**，非索引；索引可全量重建）
- [ ] 说明**为何不是 `facts/`**：`DerivedValue` 按 `Ch9 §3.3.3` 归 `derived/`（"确定性计算结果"）；`facts/` 恰为 18 个 JSONL，**不得增删改名**（`tests/unit/test_contracts.py` 断言 `facts/*.jsonl` 恰为 18）。写进 `facts/` 会违反设计契约 → 故按设计落 `derived/`

### AC-03 真接线（谁调用它）
- [ ] 计算层暴露 step ⑤/⑥ 可插拔处理器工厂 `scripts/compute/step.py::make_derived_handler(root)`（签名与 `scripts/orchestrate/pipeline.py::StepHandler` 一致）
- [ ] **当前真实消费方**：`scripts/trace/traceback.py::_find_derived()` 真读 `derived/*.jsonl`（该脚本已注册进 `run_all_gates.py`）
- [ ] **★ 诚实标注**：主流程 `pipeline.py` 的 step 4/5/6 处理器属阶段②③，**本批次未实现**（张力 `T-08`，已由主理人登记）；本批次**不改共享文件** `pipeline.py`，故 AC-03 判定为 **PARTIAL**（提供注册线 + 真实消费方，注册动作待主理人集成）

### AC-04 守卫真拦得住（injected → exit 1，不是 warn）
- [ ] 注入违例：构造 `return_source != "fund_market_price"` / `fee_deducted_again is True` 的基准对象 → **调用既有 `scripts/benchmark/return_guard.py` CLI → exit 1**（禁 warn-only，纪律 2）
- [ ] 计算层**不写第二套口径校验**（`G-06` 唯一真源）：`scripts/compute/returns.py` 只**调用** `return_guard.benchmark_return()`
- [ ] `run_derived.py --strict`：`derived/` 中出现缺 `formula`/`operands`/`method_version` 的违例行 → **exit 1**

### AC-05 错误路径（输入缺失 → 缺口对象，不置 null）
- [ ] 缺价格序列 / 缺基准对象 / 缺汇率 / 股本为 0 / 除零 → 计算层输出 **`ComputeGap`**（缺口对象，含 `missing[]` + `reason`），**不得**返回 `None` / `0` / 估算值冒充实值
- [ ] `ComputeGap` 落 `derived/compute_gaps.jsonl`（缺口也留痕，不静默丢弃）

### AC-06 边界（空 / 超大 / 非法 / 口径冲突）
- [ ] 空价格序列 / 单点序列 / 窗口内无数据 → 缺口对象，不崩溃
- [ ] 除零（base=0 / shares=0）→ 缺口对象（明确降级）
- [ ] 非法输入（`Decimal` 转换失败 / 负股本）→ 缺口或响亮失败，不静默
- [ ] 口径冲突（基准 `return_source` 非基金行情）→ `CaliberViolation`（响亮失败，非缺口）
- [ ] 超大（1e18 量级）→ 正常计算，不溢出不崩

### AC-07 无占位符
- [ ] `scripts/checks/no_placeholder_guard.py <code_root> --fail-on warn` → exit 0（本模块注释/docstring/字符串**不含** `TODO`/`FIXME`/`HACK`/`待实现`/`占位`/`mock`/`fake`/`dummy`/`NotImplementedError` 等）

### AC-08 设计对齐（节号）
- [ ] `compute_yoy/...` ↔ `Ch9 §3.4.4`（目录 + 接口示例）
- [ ] `returns.compute_total_return` ↔ `Ch9 §3.4.9`（先复权 → 再总回报）+ `Ch3 §D.2`
- [ ] `growth.assess_growth_quality` ↔ `Ch4 §D.3`（四项分档，**不压成单一分数**）
- [ ] `valuation.compute_value_per_share_range` ↔ `Ch5 §D.2`（formula+operands+method_version+share_count+compute_date）+ `§D.6`（区间宽度；`probability` 默认 `null`）+ `§D.3`（顺序约束，禁倒填）
- [ ] `DerivedValue` ↔ `schema/models.py::DerivedValue`（**复用**，不自造）；数值保真走 `Decimal`（`DerivedValue.value` + `formula` + `operands`）
  - 更正（`ws/compute` 静默缺陷批次）：原此处写"`numerics` ↔ `NumericClaim`（9 字段复用）"属**清单与代码脱节**——计算层只产 `DerivedValue`，代码中不存在 `numerics` / `NumericClaim` 引用。`NumericClaim`（`Ch9 §3.4.5` 9 字段）是**证据/声明层**（`facts/` 里 `is_derived` 的引用型数字）的模型，非计算层返回值；二者职责不同，计算层**不应**产出 `NumericClaim`。故删去该子项。

## 关键设计决策（预先声明）

| # | 决策 | 依据 |
|---|---|---|
| D1 | `DerivedValue` **直接复用** `schema/models.py` 定义；**不新增**字段/类 | `Ch9 §3.4.4` + 纪律 11（复用优先） |
| D2 | 缺口对象 = 计算层自有 `ComputeGap`（`derived/` 自有 JSONL）；**不进 `facts/`** | `Ch9 §3.3.3`（18 JSONL 不得增删改名） |
| D3 | 基准收益：**调用** `return_guard.benchmark_return()`，不复制口径断言 | `G-06` 唯一真源；纪律 11 |
| D4 | 文件锁**复用** `schema.store._file_lock`（同 `index/.locks/`）；**不新增**第二条锁路径 | 纪律 11 / `Ch9 §3.10 J6` |
| D5 | 幂等：`(derived_id, version, method_version)` 已存在则**跳过追加**（重跑同日不重复）；`version` 变（上游重述）→ **新增行** | `Ch9 §3.5` 阶段④幂等键（`company_id`, `version`, `method_version`）；`N9.2-11` |
| D6 | 配置读取走 `_common._cached_yaml()`；包 `__init__` **惰性导入**（PEP 562） | `CONVENTIONS.md P-02/P-03` |
| D7 | 行情输入由**调用方注入**（`PricePoint` 序列）；计算层不联网、不猜数 | `Ch9 §2.4.3`（模型抽取输入、程序算数） |

## 已知缺口（如实登记，不掩饰）

- step ⑤/⑥ 主流程处理器属阶段②③（张力 `T-08`）→ 计算层未接进 `pipeline.py`（AC-03 PARTIAL）。
- `V-06` 会因新增 `tests/compute/` 而报红（**预期**）：需主理人集成时在 `verify.py::BATCHES` 加批次 `compute`（本批次**不改**共享文件）。
- 真实行情输入的**分红金额**：连接器返回的 2024-12-17 / 2025-12-22 两个分红计划金额为 `null`（未披露）→ 本批次的真实总回报窗口（2026-04-01~2026-09-15）**不含**分红事件；分红再投资的算术由单测夹具覆盖。
