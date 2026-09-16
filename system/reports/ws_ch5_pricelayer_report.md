# 交付报告 · 工作流 `ws/ch5-pricelayer`（批次 13-B：Ch5 价格层）

> **分支**：`ws/ch5-pricelayer` ｜ **工作树**：`.worktrees/ws-ch5-pricelayer` ｜ **基点**：`main`（Step 0 已 `git merge main`）
> **权威设计**：`05_价格与市场预期研究/02_实现方案.md` §B / §D / §E / §F ｜ **任务卡**：`system/reports/batch13_taskbook.md` 卡 13-B
> **规范**：`system/CONVENTIONS.md`（R-06 / G-03 / G-06 / P-*）｜ **已确认参数**：`00_待拍板项清单.md` B2 / B4 / B11 / B13 / B18｜ **复用**：`system/scripts/compute/**`（Ch9 确定性层）

---

## ① 做了什么（文件 + 位置 + 要点）

| 文件 | 类型 | 要点 |
|---|---|---|
| `system/scripts/pricelayer/__init__.py` | 新增 | 包出口；**惰性导入**（PEP 562，`P-03`）；异常族 `PriceLayerError` / `ScenarioMismatch` / `ScenarioMethodPending` / `ProbabilityWithoutBasis` / `HistoricalExtrapolation` / `MoatPriceContamination` / `QuoteCaliberViolation` / `SingleSolutionError`；`order_violation()` 惰性返回 `scripts.compute.contract.OrderViolation`（`G-06`：**复用**既有异常，不新造第二条） |
| `system/scripts/pricelayer/solver.py` | 新增 | **反解求解器**（`Ch5 §B.1`）：`P=f(g,m,r,k,T)` **欠定** ⇒ 固定 4 类、求解第 5 类，产出**多组解** `ImpliedSolutionSet`；`assert_multi_solution`（单解 → `SingleSolutionError`）；`write_solution_set` 只写 `implied_requirements`；CLI 扫 `facts/implied_requirements.jsonl` |
| `system/scripts/pricelayer/order_guard.py` | 新增 | **倒填检测四规则**（`Ch5 §D`）：`PARAM_MODIFIED_AFTER_ISSUE` / `BOUNDARY_TUNED_PARAM` / `MANUAL_WITHOUT_HISTORY` / `VERSION_REVERSED`；`ALLOWED_IMPLIED_WRITE_TARGETS={implied_requirements, gap}`（**白名单**，`R-06 ④`）；`assert_baseline_source_ok` 拒 `source=implied_solution`；CLI 双扫 §B.1 多解 + §B.5 反解回灌 |
| `system/scripts/pricelayer/valuation.py` | 新增 | **估值路由 + 追溯链**（`Ch5 §D.1/§D.2`）：`load_method_routing` 走 `_cached_yaml`（`P-02`）；`route_method` 未注册类型 → `generic` **并标注**；`trace_derived_chain` **委托** `scripts.graph.closure.forward_closure` 做权威判环/截断；`compute_valuation` 复用 `scripts.compute.valuation.compute_value_per_share_range` |
| `system/scripts/pricelayer/scenario_guard.py` | 新增 | **情景守卫**（`Ch5 §E`/§D.6/§J9/B11）：`PROBABILITY_DEFAULT = None` —— **默认不给概率**；`load_scenario_policy` 缺规则文件时回落 `pending`（设计原值）并记 `value_source="design_default"`；`assert_probability_has_basis`（非空概率必须有可解析 `DerivedValue` 依据） |
| `system/scripts/pricelayer/history_guard.py` | 新增 | **历史外推 + 基准覆盖率**（`Ch5 §E.1/§E.5`/`§F`）：`is_historical_extrapolation` 用**词元等价** + `period != evidence_period` **结构判据**（不用子串，`R-06 ①`）；`MIN_MODELED_COVERAGE = Decimal("0.80")`（B4）；`check_benchmark_special_cases` **7 条逐项判据**；5 个未建模键走 `_coverage_value`（**行内优先 → `coverage_profile` 内层回落**，见 ④-4） |
| `system/scripts/pricelayer/daily_explain.py` | 新增 | **每日异动解释**（`Ch5 §F.1`）：`QuoteCaliber` **口径五要素** + `validate_quote`（逐项列出缺哪个）；`attribute` 归因 confirmed/inferred/unexplained（`forward_closure` 判定可达性）；`assert_no_price_contamination(MoatWriter)`（**共用** schema 对象，不另立白名单）；`ABNORMAL_DROP_1D=-7%` / `3D=-12%`（B2）触发复检单 |
| `system/scripts/pricelayer/step.py` | 新增 | **接线出口**（防孤儿模块）：`run_price_guards(root)` 只读跑 5 个模块的 `check` + 情景策略裁决；`make_price_guard_handler(root, step_no=6)` 产出 `orchestrate.pipeline.StepOutcome`（`produced=[]`、`degraded` 含"无被检对象"、`incomplete_reason` **显式点名模型侧缺口**）；另提供 `register_into(pipeline)` |
| `system/tests/pricelayer/` | 新增 | `conftest.py`（轻量夹具 + 可写 `rules/` 副本）+ 8 个测试文件，**127 例**全绿 |
| `system/scripts/ops/verify.py` | 修改 | **新增 `pricelayer` 批次**（`tests/pricelayer/`，超时 180s）+ 同步 `ORDER`（`V-06` 闭环；`verification_policy_guard` 的 C 断言要求两键集合一致） |
| `system/PROGRESS.md` | 修改 | 追加「十二、批次 13-B · Ch5 价格层」小节（模块表 / 实测值 / 接线说明 / 批次登记 / 待裁定） |
| `system/reports/ws_ch5_pricelayer_report.md` | 新增 | 本报告 |

**未触碰（禁改清单全绿）**：`rules/**`（0444 + SHA256 锁，**只读不写**）、`system/schema/**`、`system/scripts/compute/**`、`system/scripts/graph/**`、`system/facts/**`、`system/derived/**`、设计区 `00_*`/`01_`~`11_`、`system/tests/conftest.py`、`system/CONVENTIONS.md`。

### 三条不可动摇设计点的落地位置

1. **多解（`§B.1`）**：`solver.py` 不存在"单解返回"的代码路径 —— `CandidateCombination` 构造即校验固定类恰为其余 4 类且 `alternative_explanations` 非空；`solve_implied_requirements` 默认 `DEFAULT_MIN_SOLUTIONS=2`、展示上限 3（B18），超出折叠并记 `SOLUTION_SET_FOLDED`；`assert_multi_solution` 把"单解"升级为 `SingleSolutionError`。**模型不做算术、程序不做假设（`§B.3`）**：候选假设（`SolvedVariable` 取值）由调用方传入，程序只做区间计算与可行性剪枝。
2. **倒填禁令（`§D` 四规则 + `§B.5`）**：`order_guard.assert_baseline_source_ok` 对 `source ∈ {implied_solution, implied_requirements}` 抛 `OrderViolation`；CLI 第二判据是**运行时效果**断言 —— 取真源里真实存在的 `implied_id` 集合，再看 `baselines` 的估值输入面（`formula_ref` / `forecast_assumptions` / `valuation_params` / `driver_model[].assumptions`）里**是否真的出现这些 id**；写入侧 `assert_write_target_allowed` 只放行 `implied_requirements` / `gap`。
3. **概率默认 `null`（`§E`/§D.6/B11）**：`scenario_guard.PROBABILITY_DEFAULT is None`，`ScenarioEstimate.probability` 缺省即 `None`；`rules/scenario.yaml` 缺失时状态回落 **`pending`（设计默认值）**，而非任何数值概率；`assert_probability_has_basis(None)` 直接放行、非 `None` 必须有可解析依据。

---

## ② 怎么验证的（原样命令 + 原样输出 + 退出码）

### V-0 本模块测试批次（`verify.py` 正式批次）

```sh
$ cd .worktrees/ws-ch5-pricelayer
$ /Users/gaza/.workbuddy/binaries/python/envs/default/bin/python system/scripts/ops/verify.py --batch pricelayer
✓ [pricelayer] tests/pricelayer/（Ch5 价格层：反解多解/估值路由/倒填/情景/历史外推/每日解释）  exit=0  39.18s/180s  exit=0
------------------------------------------------------------------------------
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 38.82s
------------------------------------------------------------------------------
证据留档: reports/verify_pricelayer_latest.log
```
→ **127 passed，退出码 0**，实测 39.18s / 预算 180s（≈4.6×，落 `V-02` 允许的 4~8× 且不越 300s）。

各文件用例数（`pytest --collect-only`）：

| 测试文件 | 例数 |
|---|---|
| `test_daily_explain.py` | 21 |
| `test_order_guard.py` | 21 |
| `test_valuation.py` | 20 |
| `test_scenario_guard.py` | 19 |
| `test_history_guard.py` | 19 |
| `test_solver.py` | 15 |
| `test_step_wiring.py` | 7 |
| `test_package_laziness.py` | 5 |
| **合计** | **127** |

### V-1 六门禁 **反例（exit≠0）/ 反向对照（exit=0）** 真机演示

演示在临时根上构造真源 JSONL（脚本在 `/tmp/ch5_demo.py`，**不落仓库**；`code_root` 语义 = 含 `facts/`、`derived/` 的那层，即 `<root>/system`）：

```sh
$ /Users/gaza/.workbuddy/binaries/python/envs/default/bin/python /tmp/ch5_demo.py
[OK ] solver · 单解解集（Ch5 §B.1）
      反例 exit=1 |   report: …/solver-bad/system/reports/pricelayer_solver_2026-09-16.json
      对照 exit=0 | RESULT: PASS（0 violations）
[OK ] order_guard · 反解 id 回灌 baseline（Ch5 §B.5）
      反例 exit=1 |   report: …/order_guard-bad/system/reports/pricelayer_order_guard_2026-09-16.json
      对照 exit=0 | RESULT: PASS（0 violations）
[OK ] scenario_guard · 填了 probability 却无依据（Ch5 §J9 / B11）
      反例 exit=1 |   report: …/scenario_guard-bad/system/reports/pricelayer_scenario_guard_2026-09-16.json
      对照 exit=0 | RESULT: PASS（0 violations）
[OK ] history_guard · 含非上市资产却无缺口字段（Ch5 §E.1）
      反例 exit=1 |   report: …/history_guard-bad/system/reports/pricelayer_history_guard_2026-09-16.json
      对照 exit=0 | RESULT: PASS（0 violations）
[OK ] daily_explain · 行情缺口径要素（Ch5 §F.1）
      反例 exit=1 |   report: …/daily_explain-bad/system/reports/pricelayer_daily_explain_2026-09-16.json
      对照 exit=0 | RESULT: PASS（0 violations）
[OK ] valuation · 有区间却无追溯链（Ch5 §D.2）
      反例 exit=1 |   report: …/valuation-bad/system/reports/pricelayer_valuation_2026-09-16.json
      对照 exit=0 | RESULT: PASS（0 violations）
DEMO_EXIT=0
```
→ **6/6 门禁均为「反例 exit=1 + 对照 exit=0」**，演示脚本自身退出码 **0**。

### V-1b 未建模覆盖率键的落点（行内 vs `coverage_profile`）——正 / 反 / 优先序 三向

```sh
$ sh system/scripts/ops/run_pytest.sh tests/pricelayer/test_history_guard.py -q
...................                                                      [100%]
19 passed in 29.24s
```
其中 3 条专锁落点（`Ch5 §E.1` 表头"`benchmarks` **新增**" vs `schema.models.Benchmark.coverage_profile` 开放 dict 约定）：
- `test_reverse_control_reads_unmodeled_keys_from_coverage_profile`：键放在 `coverage_profile` 内层 → **exit 0**（否则合规写法被误判"整片缺字段"）；
- `test_coverage_profile_with_insufficient_coverage_still_rejected`：内层也没给 `unmodeled_parts` 且 `modeled_coverage=0.60 < 1` → **exit 1**（证明上一条是"内层被读到"，不是"内层一律放过"）；
- `test_flat_keys_still_take_precedence_over_coverage_profile`：行内有 `modeled_coverage=1.0`、内层是旧值 `0.10` → **exit 0**（行内**优先**，与设计字面一致）。

### V-2 六门禁在**真仓库真源**上运行（`code_root = system`）

```sh
$ PY=…/python; for m in solver valuation order_guard scenario_guard history_guard daily_explain; do
    $PY system/scripts/pricelayer/$m.py system; echo "EXIT=$?"; done

# solver
  scanned implied_rows: 0
  note: NO_IMPLIED_ROWS: 无反解行可检（非'已验证'）
RESULT: PASS（0 violations）            EXIT=0
# valuation
  scanned baselines: 1
  scanned derived_values: 0
  scanned routing_model_classes: 0
  scanned valuations_checked: 0
  note: NO_VALUATION_METHODS_RULE: rules/valuation-methods.yaml 不存在 —— 方法注册判据③不可判定
RESULT: PASS（0 violations）            EXIT=0
# order_guard
  scanned backfill_checks: 0
  scanned solution_sets: 0
  note: NO_IMPLIED_ROWS: 反解 id 真空成立
RESULT: PASS（0 violations）            EXIT=0
# scenario_guard
  scanned baselines: 1
  scanned probabilities_checked: 0
  note: NO_PROBABILITY_FILLED: 无任何已填概率（默认 null 是设计常态，非'已验证'）
RESULT: PASS（0 violations）            EXIT=0
# history_guard
  scanned benchmarks: 0 ; scanned coverage_keys: 8
  note: NO_BENCHMARKS: facts/benchmarks.jsonl 无行（非'已验证'）
RESULT: PASS（0 violations）            EXIT=0
# daily_explain
  scanned caliber_fields: 3 ; scanned prices: 0
  note: NO_PRICES: facts/prices.jsonl 无行（非'已验证'）
RESULT: PASS（0 violations）            EXIT=0
```
→ 六门禁在真仓库**全 exit=0**，且**每一处空样本都产出显式 `NO_*` note**（`G-03`：不把"无被检对象"当"已验证"）。
真源实测行数：`baselines=1`（该行 `valuation` 无区间 ⇒ 不检）、`benchmarks=0`、`prices=0`、`implied_requirements=0`、`derived/derived_values=0`。

### V-3 全门禁 pre-commit

```sh
$ sh system/scripts/ops/pre-commit.sh
…
pre-commit ✓ 全部门禁放行
EXIT=0
```
其中 `verification_policy_guard` 报 `test_files 67 / uncovered 0` —— 证明 `tests/pricelayer/`（新目录）已被批次覆盖，**`V-06` 闭环**。

### V-4 批次与阶段门（诚实登记非本流的红点）

```sh
$ /…/python system/scripts/ops/run_all_gates.py . --timeout 30
非零计数 1（traceback.py）
$ /…/python system/scripts/ops/stage_gate.py --stage all
7 FATAL
```
→ `traceback.py` 的 `G1-03` 投诉 `facts/recommendations.jsonl`（`rec-nvda-001` 缺 `assumptions`/`computation`）；`stage_gate` 的 7 条 FATAL 全部指向**其他卡片的判据**（13-A 的 `chapter4_g_depth`/`evidence_locatable`、core_chain/expansion 前置）与既存数据缺口。**均与本次改动无关**（见 ③ 的 `git status --short`：本次只动了 `verify.py`、`pricelayer/`、`tests/pricelayer/`、`PROGRESS.md`）。

### V-5 孤儿模块排查（"不写 `chain_steps` 也能到"）

`system/scripts/orchestrate/chain_steps.py` 是共享文件（**非本流可改**），故本流不改它，而是提供**两种一行接线**并各自留测试：

```sh
# 方案 A（单步挂载，不改 chain_steps）：
from scripts.pricelayer.step import make_price_guard_handler
pipeline.register("price_layer", 6, make_price_guard_handler(root, step_no=6))
# 方案 B（整步登记）：
from scripts.pricelayer.step import register_into
register_into(pipeline, step_no=6)
```
`test_step_wiring.py`（7 例）断言 `run_price_guards` **真的调用了 5 个模块的入口**（`(module, "check")` 属性对 AST 绑定断言，非词面搜索），并断言 handler 的 `produced` 恒空、`degraded` 在无被检对象时为真、`incomplete_reason` 点名模型侧缺口。**确定性部分（估值路由 / 倒填检测 / 口径校验）经此出口可在 step 4/5/6 被触达；模型侧（假设生成、基准选取与价格抓取）属阶段②③，本批次不交付 —— 该接缝在报告 ④ 中如实登记。**

---

## ③ 结果

- **本模块测试**：`tests/pricelayer` **127 passed**，退出码 **0**（`verify.py --batch pricelayer` 实测 39.18s/180s）。
- **门禁**：`pre-commit.sh` **全部门禁放行**（exit 0），**无 `--no-verify`**；`V-06` 因新批次登记而闭环（`uncovered 0`）。
- **反例有效性**：6/6 门禁均有**可执行反例（exit=1）+ 反向对照（exit=0）**，演示脚本 `DEMO_EXIT=0`。
- **复用与合规（`G-06` 零重造）**：`OrderViolation`/`MissingInput`/`UndefinedComputation` ← `scripts.compute.contract`；`compute_value_per_share_range` / `require_baseline_before_compute` ← `scripts.compute.valuation`；`read_rows` ← `scripts.compute.store`（`DerivedValue` 真源在 `derived/` 而非 `facts/`）；`forward_closure` ← `scripts.graph.closure`；`MoatWriter` ← `schema.models`。
- **禁词自查**：`weight`/`score`/`vote` 在 `scripts/pricelayer/**` 源码字符串中 0 命中（仅 `test_history_guard.py` 的 JSON 字面夹具里出现 `weight`，且该词只在 `decision_scope` 受限）；`PLACEHOLDER-CN`（`待实现|待补|占位|未实现`）在运行期消息中 0 命中。
- **`rules/**` 只读**：全程未写入；测试所需候选值一律写在夹具副本 `rules/` 内。

### 提交哈希

- 见随附提交（提交信息内不含动态哈希；哈希由 `git rev-parse HEAD` 另附于回报消息）。

### `git status --short`（提交前）

```
M  system/PROGRESS.md
M  system/scripts/ops/verify.py
A  system/scripts/pricelayer/__init__.py
A  system/scripts/pricelayer/daily_explain.py
A  system/scripts/pricelayer/history_guard.py
A  system/scripts/pricelayer/order_guard.py
A  system/scripts/pricelayer/scenario_guard.py
A  system/scripts/pricelayer/solver.py
A  system/scripts/pricelayer/step.py
A  system/scripts/pricelayer/valuation.py
A  system/tests/pricelayer/conftest.py
A  system/tests/pricelayer/test_daily_explain.py
A  system/tests/pricelayer/test_history_guard.py
A  system/tests/pricelayer/test_order_guard.py
A  system/tests/pricelayer/test_package_laziness.py
A  system/tests/pricelayer/test_scenario_guard.py
A  system/tests/pricelayer/test_solver.py
A  system/tests/pricelayer/test_step_wiring.py
A  system/tests/pricelayer/test_valuation.py
```
（未使用 `git add -A`；本次改动集合 = 上表 19 个路径 + 本报告。）

---

## ④ 诚实登记的残留 / 不确定项（**待裁定：不臆造，只上报**）

> 下列各项均为「设计未写死 / 设计自相矛盾 / 字段缺落点」。**处理方式**：代码里做**显式且响亮**的失败或回落到设计原文默认值并打 note，同时在本文登记，请主理人裁定。**未凭猜测发明任何键名语义。**

### ④-1 `rules/` 两个规则文件**当前不存在**（文件**有名**，键名**无名**）

仓库现有 `system/rules/` 只有 `banned_tokens / benchmark / data-sources.allowlist / freeze / notification / pipeline / publish / review / schedule / scope`。设计**点名要求**的两个文件**均不存在**，且 `freeze.yaml` / `benchmark.yaml` / `pipeline.yaml` 中 `scenario|probab|method|valuation|coverage|abnormal` **全部 0 命中**（**无键名先例可循**）。本流**不创建/不修改 `rules/**`**，故登记如下：

| 项 | 设计是否有名 | 本流处置 |
|---|---|---|
| 文件 `rules/valuation-methods.yaml` | **有名**（`§实现方案` 第 20 / 151 行、`N5.3-01`、`J2`） | 读它。缺文件 → `valuation.check` 发 `NO_VALUATION_METHODS_RULE` note 并把判据③标为**不可判定**（**不**静默通过） |
| ↳ 其中「`method_class → business.model_class` 绑定」的 **YAML 键名** | **无名**（`§151` 只写绑定关系） | 本流**假定** `method_routing`（`METHOD_ROUTING_KEY`）。键名不符 → **响亮失败**（不回落、不猜） |
| ↳ 其中「每类假设离散粒度」的 **YAML 键名** | **无名**（`§B.1` / `J2` / `B13` 只给了**值** ±1% / ±0.5 / ±0.5） | 本批次**未读取**（属模型侧假设空间，见 ④-5）；仅登记 |
| ↳ 其中「网格搜索上界」的 **YAML 键名** | **无名**（`§438` 只写"限制…网格搜索上界"） | 程序侧用 `GRID_CAP_EXCEEDED` note + 调用方可传上界；**不读规则文件** |
| 文件 `rules/scenario.yaml` | **有名**（`§20` / `§260` / `J5`） | 读它 ✓（文件名与设计逐字一致） |
| ↳ 键 `scenario_method_status` | **有名且逐字**（`§E.4` yaml 块 + `§J5` + 默认 `pending`） | 逐字实现 ✓ |
| ↳ 键 `method_version` | **有名**（`§260`「+ 记 `method_version`」） | 逐字实现 ✓ |
| ↳ 「情景标签」是否也要落盘为规则键（`§20` 写"情景标签/方法状态"） | **无名**（`§J4` 只给标签枚举） | 本流把 `ScenarioTag` 枚举**硬编为设计枚举**（`bear/neutral/bull/custom`），**不**从规则文件读；若裁定要外部化，需补键名 |

**建议**：由主理人在第十一章统一冻结时补建这两个文件并回填键名；届时只需按上表对齐常量即可，无需改本流逻辑（除键名常量）。

### ④-2 `Ch5 §E.2` 首句与 `R-06 ①`（禁子串判据）**直接冲突**

`§E.2` 首句写作 `"past_return" in forecast.basis` —— 这是**子串判据**，命中 `R-06 ①`（rubric 禁词面判据）。**本流处置**：改用**词元等价**（`basis` 与 `HISTORICAL_BASIS_TOKENS` 逐词元相等）+ **更穷尽的结构判据**（`period != evidence_period` ⇒ 用历史期收益当预测期收益）。该取舍已写进 `history_guard` 模块 docstring。**请裁定**：是否需要同步申请修订 `§E.2` 表述。

### ④-3 字段命名 / 落点缺口的 5 处

| 冲突 | 现状 | 本流处置 |
|---|---|---|
| `§D.4` `assumption_source` vs `§D.5` `input_source` | 同一语义两个名字 | 统一用 `schema.models.InputSource`（`§D.5` 的 `input_source`），并在 docstring 标注 `§D.4` 系同一物 |
| `Ch5 §B.1` 未给 `f` 的具体形式 | 只给 `P=f(g,m,r,k,T)` 与"欠定" | 编程上只实现**网格 + 剪枝 + 多解**，具体 `f` 由调用方注入；**程序不做假设** |
| `Ch5 §F.1` 的 `quote_time` / `adjusted_flag` / `corporate_actions_ref` vs `schema.models.PriceSnapshot` | schema 里是 `published_at`/`occurred_at` + `adjustment_caliber_version` | `quote_caliber_from_snapshot` 作为**唯一映射点**（`published_at ?? occurred_at`；`adjustment_caliber_version` 同时驱动 `adjusted_flag` 与 `corporate_actions_ref`），映射集中在一处便于裁定后改 |
| `Valuation.formula_ref` vs `§D.2` 的 `share_count` / `compute_date` | schema 无这两个字段 | 不新增 schema 字段（schema 非本流可改）；`share_count` 视为 `compute_value_per_share_range` 的操作数（走 `DerivedValue.operands`），`compute_date` 用 `compute_time` 参数承载 |
| `schema.models.RecommendationStatus` **无 `rechecking`** | `Ch5 §F.2`/B2 要求异动复检 | `daily_explain.enqueue_review` 返回 `status="rechecking"` 的 **`ReviewTicket` 对象**（不进 `RecommendationStatus` 枚举）；待裁定是否扩枚举 |

### ④-4 `schema.models.Benchmark` **缺 5 个字段落点**（已按"两边都认"实现，落点口径待裁定）

`Ch5 §E.1`（表头逐字："字段（`benchmarks` **新增**）"）与 `§E.5`（`benchmarks.modeled_coverage` + `unmodeled_parts[]`）把下面 5 项写成 **`benchmarks` 的行内平铺键**；而 `schema.models.Benchmark` **只有** `includes_non_listed_assets` / `non_listed_assets` / `sensitivity` 三个（**schema 非本流可改**）：

| `§E.1`/`§E.5` 要求 | `Benchmark` 有无字段 | 本流读取位置 |
|---|---|---|
| `includes_non_listed_assets` / `non_listed_assets` / `sensitivity` | **有** ✓ | 只读行内 |
| `holdings_disclosure_lag` | **无** | 行内**优先** → 回落 `coverage_profile` 内层 |
| `unverifiable_forecasts` | **无** | 同上 |
| `modeled_coverage` | **无** | 同上 |
| `unmodeled_parts` | **无** | 同上 |
| `claims_complete_forecast` | **无** | 同上 |

**为何"两边都认"**：设计读起来是平铺键，而 `schema/models.py::Benchmark.coverage_profile: dict[str, Any]`（`models.py:1706`）是本项目对"设计给了键名、模型未封闭建模"的**既有开放 dict 约定**（同一约定见 `models.py:1077-1081` 对 `BusinessMechanism.cost_structure` 的说明）。只认行内会把**合规的** `coverage_profile` 写法误判成"整片缺字段"，只认内层会偏离设计字面。故 `_coverage_value` **行内优先 + 内层回落**，并有 3 条用例正反锁住（见 V-1 补充）。

缺键 → 缺省值 + 显式 note（`NO_MODELED_COVERAGE` / `NO_NON_LISTED_ASSETS`），**不臆造默认通过**。**请裁定**：把 5 个键正式并入 `Benchmark`，还是明文指定用 `coverage_profile` 承载（裁定后本流删掉另一路即可）。

### ④-5 模型侧未交付（本批次边界，非缺陷）

`Ch5 §5.3/§5.4` 的**假设生成**（候选假设组合 / 假设空间边界 / 替代解释产出）与**基准选取与价格抓取**属**模型侧、阶段②③**，本批次（确定性价格层）**不交付**。`step.py::make_price_guard_handler` 的 `incomplete_reason` 已**逐字点名**该缺口，并保证 `degraded=True`、**绝不报 ok 却什么都没做**。

### ④-6 真源为空导致的"真空成立"

真仓库 `implied_requirements` / `benchmarks` / `prices` / `derived/derived_values` **均为 0 行**，故 §B.1 多解、§B.5 回灌、§D.6 概率依据、§E.1 覆盖率、§F.1 口径五类判据在真源上**真空成立**。全部反例/对照均在**副本根**上以真实对象形态注入验证（V-1），**写入型探测只在副本上做**，真仓库 `facts/`、`derived/` 保持原状。

### ④-7 其余

- **不做**：建议生成（`scripts/decision/**`）、展示视图（`views/**`）、Skill 编排 —— 不属本流模块清单。
- **不做**：不改 `chain_steps.py`（共享文件），仅提供两种接线并留测试（见 V-5）。
- **不做**：不写 `rules/**`（0444 + SHA256 锁）—— 候选值全部写在测试夹具副本内。
