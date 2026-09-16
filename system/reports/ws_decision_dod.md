# DoD · 并行工作流 `ws/decision` —— 决策层 `scripts/decision/`

> 依据：`00_开发Agent开工提示词.md §5.1`（**先写 DoD 再写代码**；每条 AC **逐条可测**；≥1 条错误路径 + ≥1 条边界）。
> 设计权威：`Ch6 §B.2/§B.3`（三维正交决策函数 序/信/深 + 反加权）· `Ch7 §D.1`（5 规则）· `§D.2`（前置门 + `DerivedValue` 强制）·
> `§D.3`（`boundary_unresolved`）· `§D.4`（判断未变 → `check_record`）· `§D.5`（`RecommendationInput` 结构）· `§D.6/§D.7`（机会类型 / 提前判断三要素）·
> `§E`（`recommendations` schema）· `Ch2 §B.2 P-02/P-06/P-09` · `Ch2 §C.1/§C.3` · `Ch2 §D.1/§D.2`。
> 施工纪律：`00_交付施工图.md §8`（12 条）；开发规范：`system/CONVENTIONS.md`（V/G/P/R 系列，尤其 `R-06` 判据鲁棒性铁律）。

## 任务一句话

**建成 `scripts/decision/` 决策层**：把「证据（`Ch6 claims`）+ 计算（`scripts/compute` DerivedValue）」转成
**可解释、可追溯、无加权、无新增门槛**的股票建议 —— 三轴（**序** `priority_order` / **信** `is_adoptable` / **深** `research_cap`）
互不影响，建议由**前置门 + 5 规则**确定性产出，落 `facts/recommendations.jsonl`。

## 交付物清单（本工作流模块清单 —— 只改这些）

- 新增/填充：`system/scripts/decision/**`（`triage.py` · `gate.py` · `rules.py` · `step.py` · `run_decide.py` · `__init__.py`）
- 新增测试：`system/tests/decision/**`
- 报告：`system/reports/ws_decision_dod.md`（本文件）· `system/reports/ws_decision_report.md`

## 冻结接口（**消费，不重造**）

- `scripts/compute`：`contract.make_derived` / `contract.DerivedValue`（`schema.models`）· `returns.PricePoint` · `returns.compute_total_return`。
- `scripts/graph`：`forward_closure`（T12 传播，供下游复查；本层只**读**不建）。
- `schema.store`：`append_records`（`facts/recommendations.jsonl` 唯一写入口）· `rebuild_index`（删 `index/` 可重建）。

## 逐条可测的验收标准（AC）

### AC-01 真跑通（真实 `DerivedValue` → 真实建议）
- [ ] **触发方式（显式注入）**：`python system/scripts/decision/run_decide.py <code_root> --stock-prices <jsonl> --benchmark-prices <jsonl> --start <d> --end <d>`
- [ ] **触发方式（真源默认，★ `P7-2` 修复后新增）**：`python system/scripts/decision/run_decide.py <code_root> [--run-date <d>] [--scope <security_id>]`
      —— 读 `<code_root>/facts/prices.jsonl`（+ `facts/benchmarks.jsonl`，回落 `rules/benchmark.yaml`）；
      **无真源行情 → 无产出**（`exit 2` + 可读输入缺失报错，**不伪造**）。
- [ ] **可观察结果**：命令 **exit 0**，输出 JSON 含 `decision.action` 与 `recommendation_id`；`<code_root>/facts/recommendations.jsonl` 出现一行**真实** `Recommendation`（含 `action/status/rule_version/change_reason/horizon/start_date`）
- [ ] **不是单测调通**：证据 = 真命令行的原样 stdout + 退出码（非 pytest 断言）
- [ ] **真实 `DerivedValue`**：个股与基准的两个收益值均由 `scripts.compute.returns.compute_total_return` 从**行情点序列**真算得出（带 `formula` + `operands` + `method_version`），**非**包装裸数字

### AC-02 持久化（write-read-reload）
- [ ] 写 `facts/recommendations.jsonl` → **删 `index/`** → `schema.store.rebuild_index()` 重建 → 重读 `facts/recommendations.jsonl` 数据**仍在**（`facts/` 是真源，`index/` 是可重建索引）
- [ ] 单测 `tests/decision/test_persistence.py` 断言：写出 1 行（`persist_recommendation` 复用 `append_records`）、`read_models` 回读为 `Recommendation`、`rebuild_index` 生成的 `index/facts.sqlite` 非空；**同"输入窗口 + 规则版本"重跑 → 不新增行（幂等）**（`test_persist_same_window_rerun_does_not_append`），并配**反向对照**：**不同窗口 → 应新增**（`test_persist_different_window_appends_new_row`）。
      ★ **`P7-4` 修回**：修复前该 AC 写成"再次追加 → 2 行（append-only）"，把**重跑重复落库**这一缺陷写成了**期望**；现改为"重跑**不**新增行"。`version` / `recorded_seq` 亦按设计填，使 `schema.store.as_of` 对 `recommendations` 的版本链可用（`test_version_chain_is_usable_via_as_of`）。

### AC-03 真接线（谁调用它）
- [ ] 决策层暴露编排器接缝 `scripts/decision/step.py::make_decision_handler(root)`（签名与 `scripts/orchestrate/pipeline.py::StepHandler` 一致：`(run_date, scope) -> StepOutcome`）；**当前真实消费方**：`scripts/decision/run_decide.py`（真跑 CLI）与 `tests/decision/**`
- [ ] `RecommendationInput` **从哪来**：由调用方按 `Ch7 §D.5` 构造（**该标的自身** `baseline` + `stock_forecast` + `benchmark_forecast` + `own_evidence`）；行情→`DerivedValue` 由 `scripts/compute` 产出
- [ ] **★ 诚实标注**：`pipeline.py` 的 step 6 处理器属阶段③，**本批次不改共享文件 `pipeline.py`**，故 AC-03 判定为 **PARTIAL**（提供注册线 + 真实 CLI 消费方；注册动作待主理人集成）
- [ ] **★ `P7-1`/`P7-3` 修回（阻断级）**：`make_decision_handler` 不再忽略 `run_date` / `scope`
      —— `run_date` = **as-of 上界**（`Ch9 §3.4.1`）、`scope` = **目标证券选取**，二者经 `run_default` 真实生效；
      输入窗口来自**真源行情** `<root>/facts/prices.jsonl`，**不再**读 `system/tests/**` 夹具。
      **空仓库（18 JSONL 全 0 行 + rules/）上 step 6：`produced == []`、`degraded == True`、
      `facts/recommendations.jsonl` / `facts/benchmarks.jsonl` 零新增行**。

### AC-04 守卫真拦得住（injected → exit 1，不是 warn）
- [ ] **吃原始数字**：`forecast.worksheet = 1234`（裸数字）→ `require_derived_worksheet` **响亮拒绝**（`RawNumberRejected`）且 `decide()` 返回 `None`（**不生成建议**）
- [ ] **含禁止门输入**：构造含 `moat_required` 的门输入类 → 既有 `scripts/checks/assert_gate_input.py` **exit 1**；含 `min_confidence` → 同上（P-02）
- [ ] **P-09 禁词**：决策作用域出现 `weight` → 既有 `scripts/checks/conflict_scan.py --timing ci` **exit 1**（P-09），且**反向对照**（同词非决策域）放行
- [ ] **决策作用域不得读参数**：既有 `scripts/checks/freeze_guard.py` 在 `scripts/decision/**` 上 `exit 0`（AST 断言：无 `get_param`/`freeze_param`/`load_freeze`/`ParamResolution`）

### AC-05 错误路径（传导边界未解 / 无法判断，不静默）
- [ ] **`boundary_unresolved`**：预期绝对收益**为负**但**仍可能跑赢基准**、且该标的**已有积极建议** → `decide()` 返回 `status=boundary_unresolved`（**不自动转卖出、不新增买入、也不等于维持**）
- [ ] **无法判断 ≠ 卖出**：预期相对收益**不确定**（区间跨越基准）→ `action=pending` / `status=uncertain`（**严格不等于 `sell`**）；且 `boundary_unresolved` **不并入** `confident_underperform` / `uncertain` 任一端
- [ ] **R8 负绝对收益禁新增买入**：绝对收益为负且相对跑赢但无在途积极建议 → **不得**产出 `buy`（降为 `pending` + 记 gap）
- [ ] **R4 判断未变 → `check_record`**：`judgment_change` 全 False → `action=maintain` 且 `is_new_signal=False`（**不产新信号**）
- [ ] **门拒绝**：研究未完成 / 无可解释预测 → `decide()` 返回 `None`（**记 gap，不出建议**）
- [ ] **提前判断三要素**：`early_judgment=True` 且三要素任一为空 → `assert_early_judgment_complete` 抛 `EarlyJudgmentIncomplete`（**不出建议**）

### AC-06 边界（空 / 超大 / 非法枚举 / 时区）
- [ ] **空**：`ResearchBaseline` 深度为空字符串 / `ReturnValue` 区间非法（`low > high`）→ 明确拒绝（`ValueError` / `ReturnRangeError`），不崩溃
- [ ] **超大**：`Decimal("1e18")` 量级收益 → 正常比较，不溢出（`Decimal` 精确算术）
- [ ] **非法枚举**：`tier` 非法 → `priority_order` 抛 `UnknownTierError`；`importance_class` 非法 → `research_cap` 抛 `UnknownImportanceError`；`horizon` 越界（如 `"2y"`）→ `assert_horizon` 抛 `HorizonOutOfRange`
- [ ] **时区**：`datetime` 为 naive 的 `first_seen_at` → `priority_order` 归一为 UTC 后排序；同一 `(tier, importance)` 下按时间升序、`claim_id` 兜底（**全序、确定性**）

### AC-07 无占位符
- [ ] `scripts/checks/no_placeholder_guard.py <code_root> --fail-on warn` → **exit 0**（本模块注释/docstring/字符串不含 `TODO`/`FIXME`/`HACK`/`待实现`/`占位`/`mock`/`fake`/`dummy`/`NotImplementedError` 等）
- [ ] 无 `pass` 空体、无 `...` 空体、无 `except: pass`、无 log 后原样重抛

### AC-08 设计对齐（节号）
- [ ] `triage.priority_order` / `research_cap` / `is_adoptable` ↔ `Ch6 §B.2`（字典序 + 字典表，**非加权和**）；三轴职责边界 ↔ `§B.2` 表
- [ ] `DecisionView` **物理上不含**被禁字段 ↔ `Ch6 §B.3`（类型约束）；`view_from_record` **allowlist** 取值 ↔ `§B.3` + `R-06`（白名单可穷尽）
- [ ] `rules.decide` 5 规则 ↔ `Ch7 §D.1`；`boundary_unresolved` ↔ `§D.3`；`check_record` / `judgment_change` ↔ `§D.4`
- [ ] `gate` 前置门 + `DerivedValue` 强制 ↔ `Ch7 §D.2`（`N7.3-06` / `N7.3-07`）；`assert_early_judgment_complete` ↔ `§D.7` / `Ch2 §D.1`（A-06）
- [ ] `RecommendationInput` **不含 `relations`、不含关联公司结论** ↔ `Ch7 §D.5`（`N7.4-11`）+ 不变性单测
- [ ] `classify_opportunity` **不进买入门**（标注非准入）↔ `§D.6` / `Ch2 §C.1`（规则 9）
- [ ] `assert_horizon` ↔ `Ch2 §D.2` / 规则 1（`[1Q,1Y]` 边界含，越界拒绝）
- [ ] `action` 枚举 ↔ `schema.models.RecommendationAction`（无 `short`/`short_sell`；无 `quantity`/`position`，P-04/P-05）

## 关键设计决策（预先声明）

| # | 决策 | 依据 |
|---|---|---|
| D1 | **排序一律走 `priority_order` 字典序**，不设任何加权/打分；`DecisionView` 物理不含热度字段，取值走 **allowlist**（未列出的键默认丢弃） | `Ch6 §B.2/§B.3`；`Ch2 §B.2 P-09`；`R-06`（白名单可穷尽） |
| D2 | 参数**不进决策函数**：`price_drop_triggered` / `horizon` 等只作**已判定的布尔/枚举**传入；阈值判定在参数层（本模块**不读** `config.freeze`） | `施工图 §8` 纪律 1；`Ch11 §E.1` |
| D3 | 门只做**结构完备性**校验（研究完成 / 可解释预测 / `DerivedValue` 底稿），**无数值置信度阈值** | `Ch2 §B.2 P-02`；`00_待拍板项清单` A5 |
| D4 | `RecommendationInput` 严格按 `Ch7 §D.5` 五字段，**不含** `relations` / 关联公司结论（配不变性单测） | `Ch7 §D.5`（`N7.4-11`） |
| D5 | `DerivedValue` **直接复用** `schema.models` 定义，经 `compute.contract.make_derived` 构造；**不新增**字段/类 | 纪律 11（复用优先）；`Ch9 §3.4.4` |
| D6 | 建议落 `facts/recommendations.jsonl`：**复用** `schema.store.append_records`（追加式、文件锁、pydantic 校验），**不新增**第二条写路径 | `Ch9 §3.4.2`；`G-06` 唯一真源 |
| D7 | ≤ 3 个建议状态语义**并列不并入**：`confident_underperform` / `uncertain` / `boundary_unresolved` | `Ch2 §C.3`；`Ch7 §D.3` |
| D8 | `horizon` 取值对齐 `rules/freeze.yaml::p04`（范围 `[1Q,1Y]`）；本层只做**区间断言**，不读参数值 | `Ch2 §D.2`；`Ch11 §D.2` |

## 已知缺口（如实登记，不掩饰）

- `pipeline.py` step 6 处理器属阶段③ → 决策层未接进主流程（AC-03 **PARTIAL**）。
- `V-06` 会因新增 `tests/decision/` 而报红（**预期**）：需主理人在集成时于 `verify.py::BATCHES` 增批次 `tests/decision/`（本批次**不改**共享文件）。
- `rules_lock_guard` 权限非 0444 属环境项（git 不记录只读位）→ 已 `chmod 444 rules/*.yaml` bootstrap，非本模块缺陷。
- `Ch7 §D.2` 设计文本用 `research_baseline_done`，而 `Ch9 §N9.1-05` 的 `ResearchDepth` 枚举 token 为 `baseline_done`（+`tracking`）—— 本层**对齐 schema 权威枚举**（`baseline_done` 及以上 = 已完成基线研究），并在报告登记该口径对齐。
- ★ **`P7-5`（生产不可满足，需设计侧裁定 —— 由"条件化"升级）**：设计 `Ch7 §D.7`（约 `:418`）逐字要求
  `assert rec.trio_written_seq <= rec.version_seq   # 与第一章 G1-01 一致：同版本写入`，
  而其引用的 `trio_written_seq` 与 `version_seq` **两字段在冻结的 `Recommendation`
  （`Ch9 §3.3.4` R-07）中皆不存在**（该模型只有 `version`（int）与 `TimeMixin.recorded_seq`）。
  依 `CONVENTIONS.md::R-04`（设计未写的一律不新增）本实现**不得**补造字段 →
  - **有判别力的部分**：对象**确暴露**该两字段时，`trio_written_seq > version_seq` → 抛
    `EarlyJudgmentIncomplete`（`test_early_judgment_same_version_assertion_is_conditional`，证明**非恒真**）；
  - **生产恒 no-op 的部分**：对 `Recommendation` / `SimpleNamespace` 两字段皆缺 → 断言不执行。
  → 判定：**生产不可满足，需设计侧裁定**（补字段 **或** 改写为结构性断言）；`G1-01` 的**结构性**保证
  （三要素与结论同一行、同一次写入生成）在本实现成立，但**不等于**设计写的那条运行时断言。
  设计原文引用与推理见 `system/reports/ws_decision_fix_report.md`。
- ★ **`P7-1`/`P7-2`/`P7-3`/`P7-4`/`P7-6` 已修**（§九 独立审计批次 7 根因修复）：
  `run_default` 读**真源**（不再读 `tests/**` 夹具、不再忽略 `root`）；handler 真实使用 `run_date`/`scope`；
  补幂等键 + 让 `as_of` 版本链对 `recommendations` 可用；空 `root` 上 CLI 给**可读**输入缺失报错（`exit 2`）。
  证据与原样命令见 `system/reports/ws_decision_fix_report.md`。
- 本层**不实现** `R5` 的价格下跌**阈值**判定（阈值属实施参数，未冻结）→ 只接受**已判定的布尔** `price_drop_triggered` 并置 `recheck_required`，不自动止损/抄底。
