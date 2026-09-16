# 交付报告 · 工作流 `ws/ch5-pricelayer`（批次 13-B：Ch5 价格层）

> **分支**：`ws/ch5-pricelayer` ｜ **工作树**：`.worktrees/ws-ch5-pricelayer` ｜ **基点**：`main`
> **权威设计**：`05_价格与市场预期研究/02_实现方案.md` §B / §D / §E / §F ｜ **任务卡**：`system/reports/batch13_taskbook.md` 卡 13-B
> **规范**：`system/CONVENTIONS.md`（R-06 / G-03 / G-06 / P-* / V-02）｜ **已确认参数**：`00_待拍板项清单.md` B2 / B4 / B11 / B13 / B18｜ **复用**：`system/scripts/compute/**`（Ch9 确定性层）
>
> ★ **本报告为修订轮（第二轮）状态**。首轮已合并入主干（merge `4468da5`），随后主理人拿**真 `rules/` 文件**探出
> 两处「夹具与真文件不同源」缺陷（**与 `G-43`/`G-45` 同族**）。两处已修，并把**整类问题的防复发装置**一起补上
> （见 §①-2 与 §② V-1c）。首轮状态已不适用，故全文按修订后状态重写。
>
> **本轮提交**：修订内容提交 `9552e8c` → 合并 `main`（`3c7b34d`）得合并提交 **`60aab53`**；
> 提交前跑 `git merge main`（**零冲突**），合并后重跑 `bootstrap_worktree.sh`（复原 `rules/` 0444，
> 因 `git merge` 只跟踪可执行位、`rules/*.yaml` 一进树就是 `0644`）+ 重跑批次与 `pre-commit`（见 §② V-0′/V-3）。

---

## ① 做了什么（文件 + 位置 + 要点）

### 1-1 模块（首轮交付，修订轮在其上改读规则）

| 文件 | 类型 | 要点 |
|---|---|---|
| `system/scripts/pricelayer/__init__.py` | 新增 | 包出口；**惰性导入**（PEP 562，`P-03`）；异常族 `PriceLayerError` / `ScenarioMismatch` / `ScenarioMethodPending` / `ProbabilityWithoutBasis` / `HistoricalExtrapolation` / `MoatPriceContamination` / `QuoteCaliberViolation` / `SingleSolutionError`；`order_violation()` 惰性返回 `scripts.compute.contract.OrderViolation`（`G-06`：**复用**既有异常，不新造第二条）。**修订轮**：`ScenarioMethodPending` 的 docstring 补上「触发条件不写在本类里，由 `rules/scenario.yaml::scenario_method_blocking.when` 决定」—— 消除最靠近异常层的"声明与实现脱节" |
| `system/scripts/pricelayer/solver.py` | 新增 | **反解求解器**（`Ch5 §B.1`）：`P=f(g,m,r,k,t)` **欠定** ⇒ 固定 4 类、求解第 5 类，产出**多组解** `ImpliedSolutionSet`；`assert_multi_solution`（单解 → `SingleSolutionError`）；`write_solution_set` 只写 `implied_requirements`；CLI 扫 `facts/implied_requirements.jsonl`。**修订轮**：展示上限/多解下限改读 `rules/valuation-methods.yaml::solution_set_display`（见 §①-2） |
| `system/scripts/pricelayer/order_guard.py` | 新增 | **倒填检测四规则**（`Ch5 §D`）：`PARAM_MODIFIED_AFTER_ISSUE` / `BOUNDARY_TUNED_PARAM` / `MANUAL_WITHOUT_HISTORY` / `VERSION_REVERSED`；`ALLOWED_IMPLIED_WRITE_TARGETS={implied_requirements, gap}`（**白名单**，`R-06 ④`）；`assert_baseline_source_ok` 拒 `source=implied_solution`；CLI 双扫 §B.1 多解 + §B.5 反解回灌 |
| `system/scripts/pricelayer/valuation.py` | 新增 | **估值路由 + 追溯链**（`Ch5 §D.1/§D.2`）：`load_method_routing` 走 `_cached_yaml`（`P-02`）；`route_method` 未注册类型 → **规则文件声明的**回落类 **并标注**；`trace_derived_chain` **委托** `scripts.graph.closure.forward_closure` 做权威判环/截断；`compute_valuation` 复用 `scripts.compute.valuation.compute_value_per_share_range`。**修订轮**：新增 `load_unregistered_fallback` + `VALUATION-RULE-BINDING` 判据集 |
| `system/scripts/pricelayer/scenario_guard.py` | 新增 | **情景守卫**（`Ch5 §E`/§D.6/§J9/B11）：`PROBABILITY_DEFAULT = None` —— **默认不给概率**；`assert_probability_has_basis`（非空概率必须有可解析 `DerivedValue` 依据）。**修订轮：本模块改动最大**（修 1 + 修 2，见 §①-2） |
| `system/scripts/pricelayer/history_guard.py` | 新增 | **历史外推 + 基准覆盖率**（`Ch5 §E.1/§E.5`/`§F`）：`is_historical_extrapolation` 用**词元等价** + `period != evidence_period` **结构判据**（不用子串，`R-06 ①`）；`MIN_MODELED_COVERAGE = Decimal("0.80")`（B4）；`check_benchmark_special_cases` **7 条逐项判据**；5 个未建模键走 `_coverage_value`（**行内优先 → `coverage_profile` 内层回落**，见 §④-4） |
| `system/scripts/pricelayer/daily_explain.py` | 新增 | **每日异动解释**（`Ch5 §F.1`）：`QuoteCaliber` **口径五要素** + `validate_quote`（逐项列出缺哪个）；`attribute` 归因 confirmed/inferred/unexplained（`forward_closure` 判定可达性）；`assert_no_price_contamination(MoatWriter)`（**共用** schema 对象，不另立白名单）。**修订轮**：异常下跌复检阈值改读 `rules/review.yaml::forced_recheck`（见 §①-2） |
| `system/scripts/pricelayer/step.py` | 新增 | **接线出口**（防孤儿模块）：`run_price_guards(root)` 只读跑各模块的 `check` + 情景策略裁决；`make_price_guard_handler(root, step_no=6)` 产出 `orchestrate.pipeline.StepOutcome`（`produced=[]`、`degraded` 含"无被检对象"、`incomplete_reason` **显式点名模型侧缺口**）；另提供 `register_into(pipeline)`。**修订轮**：`checker` 循环补入 `scenario_guard.check`（与 `valuation.check` 对称），新增 `report.scenario_blocking` |
| `system/tests/pricelayer/` | 新增 | `conftest.py`（轻量夹具 + 可写 `rules/` 副本 + **`real_rules` 真文件夹具**）+ 8 个测试文件，**168 例**全绿 |
| `system/scripts/ops/verify.py` | 修改 | **新增 `pricelayer` 批次**（`tests/pricelayer/`，超时 **300s**）+ 同步 `ORDER`（`V-06` 闭环；`verification_policy_guard` 的 C 断言要求两键集合一致）。超时取值见 §② V-0 |
| `system/CONVENTIONS.md` | 修改 | 补 **`pricelayer` 批次表缺行**（原表漏登本批次）并把「**20 批**」订正为「**21 批**」—— 与 `verify.py::BATCHES`（21 项）对齐 |
| `system/PROGRESS.md` | 修改 | 追加「十二、批次 13-B · Ch5 价格层」+「**12.1 修订轮**」两小节 |
| `system/reports/ws_ch5_pricelayer_report.md` | 新增 | 本报告 |

**未触碰（禁改清单全绿）**：`rules/**`（0444 + SHA256 锁，**只读不写**）、`system/schema/**`、`system/scripts/compute/**`、`system/scripts/graph/**`、`system/facts/**`、`system/derived/**`、设计区 `00_*`/`01_`~`11_`、`system/tests/conftest.py`、`scripts/orchestrate/chain_steps.py`。

### 1-2 ★ 修订轮：两处「夹具与真文件不同源」（`G-43`/`G-45` 同族）

首轮**自带夹具**写出了一个**生产代码写不出来的形状**，于是"代码读了真文件里没有的键"这件事**永远绿**。两处都**不是就地打补丁**，而是连同**整类问题的防复发装置**一起补。

#### 修 1 —— `method_version` 在真 `rules/scenario.yaml` 里**不存在**

| 项 | 内容 |
|---|---|
| 主理人实测 | `load_scenario_policy('.')` → `status='pending' value_source='rules' method_version=''`；而首轮夹具虚构了 `{"scenario_method_status": "probability_wedge", "method_version": "scenario-v2"}` |
| 根因 | `§E.4` 的 `method_version` 是「`status` 转 `neutral`/`probability_weighted` **后记**」的**运行时写入字段**（写在产物/`derived/`），**不是规则文件里的键**。首轮用 `doc.get("method_version") or ""` 读它 ⇒ **静默返回空串**，测试恒绿 |
| 修法（主理人给的①+②都做） | ① **去核真实载体**：`§E.4` 的写入由 `scenario_consistency.param_ref → p05` 指向 `rules/freeze.yaml`，故改从**真实承载它的地方**读 —— 走**唯一参数读口** `config.freeze.get_param(param_ref, root)`（`G-06`：复用，不新造第二个参数读口）。② **响亮报错**：`status != pending` 而版本不可用（空串 / `algorithm == "tbd"` / 指针悬空 / 非映射值）⇒ 抛 `ScenarioGuardError`（"**method_version 不可用**… 不得静默取空串（先冻结参数再转正状态）"） |
| 现在的语义（关键） | `""` **只在 `status == "pending"` 时**返回，并标 `method_version_source="not_applicable_pending"`。这是**正确取值**（转正还没发生 ⇒ `§E.4` 的"记 `method_version`"尚不适用），**不是静默兜底**；`or ""` 已从代码中删除 |
| 真文件实测 | `method_version: ''` ｜ `method_version_source: 'not_applicable_pending'` ｜ `param_ref: 'p05'` ｜ `record_method_version: True` |

#### 修 2 —— `pending ⇒ 阻塞相对判断` 被**硬编码**，而真文件里**就有**这个口径键

| 项 | 内容 |
|---|---|
| 主理人实测 | 真 `rules/scenario.yaml` 顶层键含 **`scenario_method_blocking`** · **`scenario_method_status_domain`** · `scenario_method_status_note` · `scenario_method_status_promotion` |
| 根因 | `scenario_guard.py:195`（首轮）把「`pending` ⇒ 阻塞相对判断生成」写成常量、取值域也写成常量 ⇒ 违反 `P-09` / `Ch11 §D.2`「**参数只能住 `rules/`，代码不得内置**」，并造成**规则文件改了、代码不改**（本项目反复出现的"声明与实现脱节"） |
| 修法 | 阻塞条件改读 `scenario_method_blocking.{when, effect, downstream_output, required_field_at_downstream}`；取值域改读 `scenario_method_status_domain`。`assert_relative_judgment_allowed` 改为按 **`policy.blocking`** 分支（不再看 `is_pending`）；报错文案内联规则文件给的口径原文 |
| **不做假设** | `when` 用**刻意极小且严格校验**的语法解析：`<字段> == <单 token>`，字段必须**恰为** `scenario_method_status`；形态不认识 ⇒ `ScenarioGuardError("… 形态不认识 … 不发明表达式求值器")`。缺键 ⇒ 回落设计逐字条件 `scenario_method_status == pending`（`DESIGN_BLOCKING_WHEN`）并记 `NO_BLOCKING_RULE` note |
| 真文件实测 | `blocking: True` ｜ `domain: ('pending','neutral','probability_weighted')` ｜ `blocking_effect: 'assert_scenario_match 无法建立一致口径 → **阻塞相对判断生成**'` ｜ `blocking_downstream: '待判断（而非建议）'` ｜ `required_field_at_downstream: 'benchmark_forecast'` ｜ `assert_relative_judgment_allowed` → **BLOCKED**（文案取自规则文件） |

#### 同族扩展 —— 不等主理人再抓一遍，另三个守卫也改成读真规则键

| 模块 | 改读的规则键（真文件里确有） | 行为绑定证据（**改规则 ⇒ 行为变**） |
|---|---|---|
| `solver.py` | `rules/valuation-methods.yaml::solution_set_display`：`default_count: 3` / `max_count: 5` / `must_show_multiple: true` / `selection` / `overflow` | ① `default_count` 由 3 改 2 ⇒ 求解结果**只展示 2 组、折叠 1 组**（**不硬编码 3**）；② `must_show_multiple: false` ⇒ 多解下限由 2 **降为 1**（下限是**派生量**，不另存一份 —— `G-06` 单一真源，避免"同一事实两处存放"）；③ `default_count > max_count` ⇒ `PriceLayerError("…取值非法…")` **响亮失败，不静默夹紧** |
| `daily_explain.py` | `rules/review.yaml::forced_recheck`：`single_day_drop_pct: -7` / `three_day_cumulative_pct: -12` / `on_hit.keep_original_judgment_time: true` | 单点口径换算（**百分点 → 内部小数**，`/Decimal(100)`）集中在 `load_recheck_trigger`；改规则阈值 ⇒ 判定随之改变；阈值非负 ⇒ `DailyExplainError` 响亮失败；`is_abnormal_decline` / `enqueue_review` 的票面文案用**规则阈值**拼 |
| `valuation.py` | `rules/valuation-methods.yaml::unregistered_fallback{method_class: generic, mark: unregistered}` + `valuation_compute.entry: compute_valuation` | ① 改 `unregistered_fallback.method_class` 而代码未改 ⇒ `VALUATION-RULE-BINDING`；② 规则声明的 `valuation_compute.entry` 若在实现 `globals()` 里**不存在** ⇒ `VALUATION-RULE-BINDING`「**规则文件声明的入口与实现脱节**」；③ 路由回落类改从规则读（不再用常量） |

#### 防复发装置（`G-43`/`G-45` 的**正面解法**：机器绑定）

1. **四组 `*-RULE-BINDING` 判据集**，各自跑在对应守卫 `check()` 的**首位**：
   `SOLVER-RULE-BINDING` · `VALUATION-RULE-BINDING` · `SCENARIO-RULE-BINDING` · `DAILY-RULE-BINDING`。
   检查内容：① 本模块**实际读取的键在真文件里真的存在**（`REQUIRED_RULE_KEYS` / `RULE_BOUND_ENTRIES`）；
   ② 规则键的值**与代码常量一致**（不一致即"声明与实现脱节"，如 `probability.default` 被改成 `0.5`）；
   ③ 规则声明的入口确实存在于实现；④ `scenario_tags` 与代码 `ScenarioTag` 枚举**逐字相等**。
   **★ 该检查在 `facts/` 为空时照跑** —— 否则会被空样本真空跳过（正是首轮恒绿的原因之一）。
   反向对照：文件不存在 ⇒ 记 `NO_*_FOR_BINDING` note 并标**不可判定**（**不**静默通过）。
2. **`real_rules` 真文件夹具**（`tests/pricelayer/conftest.py`）：`copy_real_rules(root, *names)` 把**真 `rules/*.yaml`**
   拷进用例 scratch 根（只读位一并放开），docstring **逐字点名 `G-43`/`G-45`**。新增用例一律走真文件，
   **不再自备虚构形状**。
3. **`test_tests_never_write_real_rules_files`**：对真 `rules/*.yaml` **改动前后各取一次 SHA256** 断言不变 ——
   `rules/` **只读不写**；0444 纪律由 `rules_lock_guard.py` 承载（测试不重复实现第二份权限判据）。
4. **`bootstrap_worktree.sh`**：`git merge` 会把 `rules/*.yaml` 的 **0444 重置为 0644**（git 只跟踪可执行位），
   故**每次合并后必须**跑它复原（只 `chmod`，**内容零变更**，不动 `locked_at`/SHA 台账 ⇒ `git status --short system/rules system/registry` 空）。
   本轮 `pre-commit` 曾因此报 4 条 `rules_lock_guard` FATAL，已按此处置（详见 §② V-3）。

**明确不做（本轮纪律）**：不给 `method_version` 造一个规则文件里没有的键；不发明 `when` 表达式求值器；
不用 `or ""` / `try-except-pass` 之类静默兜底 —— **程序写错必须响**。

### 1-3 三条不可动摇设计点的落地位置

1. **多解（`§B.1`）**：`solver.py` 不存在"单解返回"的代码路径 —— `CandidateCombination` 构造即校验固定类**恰为其余 4 类**且 `alternative_explanations` 非空；`solve_implied_requirements` 的展示上限取自**规则文件**（B18：默认 3 / 最多 5），超出**折叠**并记 `SOLUTION_SET_FOLDED`；多解下限由 `must_show_multiple` **派生**（≥2）；`assert_multi_solution` 把"单解"升级为 `SingleSolutionError`。**模型不做算术、程序不做假设（`§B.3`）**：候选假设由调用方传入，程序只做区间计算与可行性剪枝。
2. **倒填禁令（`§D` 四规则 + `§B.5`）**：`order_guard.assert_baseline_source_ok` 对 `source ∈ {implied_solution, implied_requirements}` 抛 `OrderViolation`；CLI 第二判据是**运行时效果**断言 —— 取真源里**真实存在**的 `implied_id` 集合，再看 `baselines` 的估值输入面（`formula_ref` / `forecast_assumptions` / `valuation_params` / `driver_model[].assumptions`）里**是否真的出现这些 id**；写入侧 `assert_write_target_allowed` 只放行 `implied_requirements` / `gap`。
3. **概率默认 `null`（`§E`/§D.6/B11）**：`scenario_guard.PROBABILITY_DEFAULT is None`，`ScenarioEstimate.probability` 缺省即 `None`；`assert_probability_has_basis(None)` 直接放行、非 `None` 必须有可解析依据。★ 本轮把"**默认 `null`**"这一条也纳入机器绑定：`SCENARIO-RULE-BINDING` 断言真文件 `probability.default is None` 且 `must_be_null_50_50` 为假 —— **规则文件若偷偷改成 0.5，门禁当场红**。

### 1-4 ★ 主理人裁定 ③ 的落地：口径保持现状 + **三条约束**（第三轮）

主理人裁定：**不**把本流统一到 `valuelayer::_rules.py` 的"读口即抛错"，**保持**"读口宽松 + 门禁响亮"
（理由：`/tmp/ch5_demo_rules.py` 这类**无完整工程树**的路径正是它在服务的；且两者最终等价 —— 都有人**响亮地**管）。
但**加三条约束**，本轮已全部落地并可执行验证：

| 约束（逐字） | 落地 | 证据 |
|---|---|---|
| ① 回落值必须是**设计逐字值**，docstring **标明设计节号** | 新增/补齐命名常量：`DESIGN_MUST_SHOW_MULTIPLE`（`Ch5 §B.1`）、`DESIGN_RECORD_METHOD_VERSION`（`Ch5 §E.4`）、`DESIGN_KEEP_ORIGINAL_JUDGMENT_TIME`（`Ch5 §F.5`/`T08`）；`DEFAULT_DISPLAY_CAP`/`MAX_DISPLAY_CAP`（B18）、`DEFAULT_METHOD_CLASS`/`DEFAULT_UNREGISTERED_MARK`（`Ch5 §D.1`）、`ABNORMAL_DROP_1D/3D`（B2）、`DESIGN_SCENARIO_METHOD_STATUSES`/`DESIGN_BLOCKING_WHEN`（`Ch5 §E.4`）**逐个带出处**；不再有裸字面量回落 | docstring 与常量一一对应（`grep -E '^DESIGN_|^DEFAULT_' scripts/pricelayer/*.py`） |
| ② 必须输出 `value_source ∈ {rules, design_default}`，且 `design_default` 时**必打一条 note** | 四个读口全部具备该字段；**缺文件 / 缺键 / 子键缺**三种成因各出**不同 note**（点明缺的是哪个文件/哪个键）。★ 补了两处**真实缺陷**：<br>· `valuation.check` 把读口放在 `if not baselines: return` **之后** ⇒ 空样本时 note 被**静默吞掉**（已前移到早退之前，并加回归锁用例）<br>· `scenario_guard` 的 `root is None` 与 `promotion.record_method_version` 缺省是**无 note 的静默默认**（已补 `NO_SCENARIO_ROOT` / `NO_PROMOTION_KEY`）<br>且 `solver.check` / `daily_explain.check` / `valuation.check` 均把 `notes` **上报进 report**（不只活在对象上），并加 `display_value_source` / `recheck_value_source` / `unregistered_fallback_value_source` 读数 | 见 §② V-1d |
| ③ `*-RULE-BINDING` 必须断言**"回落值 == 真文件里的值"** | 新增 6 条绑定：`scenario` 判据⑥（取值域）/⑦（`when` + `record_method_version`）、`solver` 判据③（`must_show_multiple` —— **此前漏绑**）、`daily` 判据③（`keep_original_judgment_time`，由"单向断言真"改为**双向漂移**断言）、`valuation`（把"读不到值"与"值不一致"**分开**，不再让缺键被回落值掩盖） | 见 §② V-1e（真值 0 违例 + 6 个反例各 1 违例） |
| ★ **刻意不绑的一项**（诚实登记） | `DEFAULT_SCENARIO_METHOD_STATUS` **不得**绑到文件的 `scenario_method_status` —— 前者是"尚未转正时的默认值"，后者是**当前状态**（转正后合法变 `neutral`），**不是同一事实**；绑了会在正常转正后**假红**。出处由 docstring 承担，另有 `test_design_status_default_is_deliberately_not_bound` 把该选择固化成可执行说明 | 同测试 |

★ 另修一处**夹具层的隐患**：`real_rules` 夹具现在统一把**副本** `chmod 0644`（真文件仍 0444）——
  此前"宿主是否保留只读位"这一环境差异会让注入用例**有时写得进、有时 PermissionError**（本会话实测到过）。
  真文件仍由 `test_tests_never_write_real_rules_files` 的 SHA256 前后对比把关。

---

### 1-5 ★ 第四轮（自查）：**"缺子键 ⇒ 门禁静默跳过"** + 我自己交付物里的**重复死代码**

第三轮落地后自查"③ 是否真的把**所有**漂移都变红"，发现**同一族病在第三轮没治干净**：
`*-RULE-BINDING` 里凡写成"**先取到值再比较**"的地方，**键被删掉**时会**静默跳过**
（`doc.get(k) is not None and ...` / `if ref and ...` / `if isinstance(node, Mapping)`），
于是"规则文件删掉这个键"**照样全绿**。判据③要求的是"回落值 == **真文件里的值**"——
**没有可比对象就直接跳过**，等于把"文件里根本没写"读成"一致"。

#### 修 3 —— 缺键 / 形态非法 ⇒ **违例**（不再静默跳过）

逐处先判"键在不在"，再判"值对不对"（**8 处**，覆盖 4 个读口）：

| # | 文件 | 键 | 改前的样子（删键后**不红**） |
|---|---|---|---|
| 1 | `scenario_guard` | `probability.default` | `is not None` 判 ⇒ 键没了 `.get` 回 `None` ⇒ **读成"合规 null"**（最危险：合法值就是 `null`） |
| 2 | `scenario_guard` | `probability.must_be_null_50_50` | `bool(...)` 判 ⇒ 键没了回 `False` ⇒ **读成"已确认不默认 50/50"** |
| 3 | `scenario_guard` | `scenario_method_blocking.when` | `if declared_when and ...` ⇒ 空/缺**静默通过**（且 `when: ""` 也过） |
| 4 | `scenario_guard` | `scenario_method_promotion.record_method_version` | `and key in node` ⇒ 缺键跳过 |
| 5 | `scenario_guard` | `scenario_method_status_domain` | `isinstance(list) and ...` ⇒ 形态非法跳过 |
| 6 | `valuation` | `valuation_compute.entry` | `if declared and ...` ⇒ 缺键跳过 |
| 7 | `solver` | `solution_set_display.{default_count,max_count}` | `is not None and ...` ⇒ 缺键跳过 |
| 8 | `solver` | `assumption_grid.solver_ref` | `if ref and ...` ⇒ 缺键跳过 |

并把 4 处 `isinstance(x, Mapping)` 换成"**在文档里但不是映射 ⇒ 形态非法**"（此前会**掉进 else 静默通过**）。

#### 修 4 —— `daily_explain`：`on_hit.keep_original_judgment_time` 缺键（**值比较判不出来**）

加载器在缺该键时回落 **设计逐字值 `True`**，而"应该有的值"**也是 `True`** ⇒ 两者**撞成同一个数**，
`trigger.keep_original_judgment_time != DESIGN_...` **恒为假** ⇒ 缺键**永远不红**。
处置：绑定里**按文档原文单独判存在性**（不靠值比较）。

#### 修 5 —— `daily_explain`：删掉一段**永不可达且描述错误**的 note

`load_recheck_trigger` 末段原本对"阈值键缺失"记 `NO_FORCED_RECHECK_KEY` note，声称
"该阈值取设计逐字回落值（B2）"。**实测证伪**：

```text
[删 single_day_drop_pct] 响亮失败 DailyExplainError: rules/review.yaml:: forced_recheck 阈值非数值（None / -12）—— 不静默兜底
```

上面的 `Decimal(...)` 解析**先抛错**，那段 note **一行都执行不到**；而它的文字还宣称"回落"，
**与真实行为相反**（真实行为是响亮失败，且这更好，符合"不许静默兜底"）。
⇒ 删死代码 + 订正 docstring 为"阈值键缺失/非数值 ⇒ `DailyExplainError`（响亮失败）"。

#### 修 6 —— ★ **我自己交付物里的重复死代码**（自曝，已进 main）

审计"证据是否真在执行"时发现：第三轮提交 `148867a` 把**整块测试重复追加了两遍**：

| 文件 | 第三轮前 | 第三轮后 | 其中**逐字重复**（AST 哈希相同） |
|---|---|---|---|
| `tests/pricelayer/test_daily_explain.py` | 20 个 `def` | 38 个 | **7 个函数 ×2**（`test_real_rules_recheck_thresholds` 等 7 条） |
| `tests/pricelayer/test_step_wiring.py` | 10 个 `def` | 14 个 | **2 个函数 ×2** |

Python 里**后一份静默遮蔽前一份** ⇒ 这 9 个副本**从不执行**（对覆盖率无损，因为是逐字副本），
但它让"新增了多少只有效用例"**虚高**，属"看起来测了、其实没跑"的同一族病。
处置：以 AST 哈希定位第二个副本整块删除（`+0 / -101` 与 `+0 / -30`，**纯删除**），
并逐文件名核对关键用例仍在；**pytest 收集数不变**（遮蔽态与实际态都是 1 个/名）。

#### 修 7 —— `order_guard` 的 §B.1 多解判据：**三处同族病**（口径冲突 / 内置参数 / 静默跳过）

审计"我自己的模块里还有没有'静默'"时发现 `order_guard._multi_solution_violations`：

| # | 病 | 后果 | 依据 |
|---|---|---|---|
| ① | 数**全部**行（不筛 `feasible`） | 同解集里 1 行可行 + 1 行不可行 ⇒ 被算成"2 组" ⇒ **漏报**单解集；且与 `solver.check` 的**同名判据**（只数 `feasible`）**口径冲突** | `Ch5 §B.1`（"展示**解集**"= 使当前价格成立的那些解） |
| ② | 硬编码 `count < 2` | 规则改了**代码不动** ⇒ 违反「**参数只能住 `rules/`**，代码不得内置」；且批 13 任务书**方案②已明确要求"代码删掉常量 `2`，改为从该键派生"** | `Ch11 §D.2` / `P-09` / 任务书 `batch13_taskbook.md:412` |
| ③ | 缺 `solution_set_id` 的行 `continue` 掉 | 那些行**落在不变式之外**却无声；且"所有行都缺键"时 note 说"无可用解集"，把**数据在、只是键缺**误报成**没有数据** | `schema.models.ImpliedRequirement.solution_set_id` 是**必填**字段；`G-03` |

处置：①只数 `feasible`；②下限改读 `load_solution_set_display(root).min_count`（**与 `solver` 同一个读口**，并把它 `design_default` 时的 note **转发进 report** —— 裁定 ③-2）；③缺键 ⇒ **违例**，并把被排除的行数（缺键 / 不可行）写进 note（**计数可见**）。

#### 修 8 —— 同一轮检查顺带抓到的第二处：`implied_ids` 的黑名单也会**静默少 id**

`_baseline_backfill_violations` 原稿用 `if row.get("implied_id")` 推导"反解 id 黑名单"⇒
**缺 `implied_id` 的行被静默排除**，于是"baseline 引用了反解 id"这条判据对它们**没有管**
（`solver.check` 对同类行是**响亮**报 `IMPLIED-ROW-INCOMPLETE` 的 ⇒ 又是一处**口径分裂**）。
`implied_id` 同样是 `schema.models.ImpliedRequirement` 的**必填**字段 ⇒ 缺即违例。
★ 处置时撞到一个**熟悉的坑**：该违例若放在 `if not (baselines and implied_ids): return` **之后**，
`baselines` 为空时就会被**早退静默吞掉** —— 与 `valuation.check` 的 D-1（§1-4 约束②）**同一形状**。
故**放在早退之前**，并加回归锁用例 `test_row_missing_implied_id_is_flagged_even_without_baselines`
（**刻意不写 `baselines`**，正是为了锁住这个位置）。

> **已办**：上表 8 处缺键 + 修 4 的**永久回归用例已写并逐条执行**（9 条新用例 + 2 条反向对照）——
> 方式见 §② V-1j：`pytest` **命令**仍未跑（`G-60` 排他窗口），但把**测试函数本体**用**手搓等价夹具**
> 直接调用执行了断言。窗口关闭后仍需按正式路径 `verify.py --batch pricelayer` 复跑一次。

### 1-6 ★ 第五轮：主理人**裁定（甲）**落地 —— `value_source` 的**声明粒度**收紧

`§④-8a` 那条待裁定项（第三轮起提了三轮）主理人已裁：**采纳 (甲)，不采纳 (乙)**。

> **理由（他的原话，逐字）**：*"标志的单位必须与它声称覆盖的单位一致。`value_source` 是对
> **整个结构**的'已核'声明。若结构内**有**字段落到 `design_default` 而标志仍写 `rules`，
> 那么只读 `value_source` 的下游会得到「**整块已核**」—— 而事实是**部分未核**。
> 这正是本轮入册的 `V-11` 类别轴（样本性质被上推到类别）与 `G-62`（不可区分）。"*

**改动面 = 3 个 `load_*` 各一行**（`solver` / `valuation` / `daily_explain`）：

```python
value_source="rules" if not notes else "design_default",
```

即 **"全部字段都来自文件"才叫 `rules`**，否则 `design_default` —— 而 `notes` 里逐条点名
**缺的是哪个字段**（**不丢信息**：改标志只是**不再过度声称**，不是删信息）。

#### ★★ 反向对照（`G-05`，主理人明确要求）：字段齐备时**必须仍报 `rules`**

否则标志会退化成"**永远 `design_default`**"——那与"永远 `rules`"**一样没有信息量**。
实测（真 `rules/` 只读副本，字段齐备）三处**全部仍报 `rules` 且零 note**（见 §② V-1l）。

#### ★ 落 (甲) 时**必须同步动的三处**（漏一处就变成"改出新的静默"）

| # | 连带改动 | 为什么非改不可 |
|---|---|---|
| ① | `solver`：`int(node.get(k) or DEFAULT)` → **先判键在不在**，键在但值非整数 ⇒ `PriceLayerError` | 旧写法在**键在但值为 `0`/`None`** 时用 `or` 悄悄换成回落值**且不留 note** ⇒ 标志会**误报 `rules`**（正是甲要堵的那个洞） |
| ② | `solver`：`must_show_multiple` 由 `bool(node.get(k, DEFAULT))` → **键在且非布尔 ⇒ `PriceLayerError`** | `bool(None)` = `False` ⇒ `must_show_multiple: null` 会把"必须多组解"这条**设计不变量**悄悄关掉（多解下限退化为 1） |
| ③ | ★★ `daily_explain._rule_binding_violations`：把 `on_hit.…` 的**存在性判据挪到早退之前** | 甲生效后"缺该子键"会让 `value_source` 变 `design_default`，而该函数有一条"`value_source != rules` ⇒ 报'读不到值'并**早退**"。存在性判据若排在早退**之后**就会被**吞掉**，只剩一条笼统消息、**信息更少** —— 与 `valuation.check` 的 D-1「**早退吞违例**」**同一形状**（`G-62` 家族） |

★ ③ 是**主理人赞扬过的那条跨模块形状**（"早退吞违例"）在本轮的**第二次复现**：他给我记功时
说的是修 8 里那次；本轮是**同一个人在同一个补丁里**又踩到一次、又自己发现并挪走。
★ 顺带：挪走后原位置留下**同一段判据的第二份副本**（我在第一轮编辑时留下的重复块）——
按**修 5/修 6 的同一条纪律**（死代码 / 重复代码必须删，不能留"看起来还在守"的假象）**已删**。

#### ★ 口径变更史（写明"为什么这不是反复"）

- **第三轮裁定 ③-2** 定的是**实现口径**："节存在即 `rules`"——即"**怎么判**"。
- **第五轮裁定（甲）** 定的是**声明的粒度**："标志只能覆盖它声称覆盖的单位"——即"**声称什么**"。
- ⇒ 两者是**同一方向上的收紧**，**不是翻转**。（主理人原话：*"这条不属于'反向改自己刚立的判据'"*。）

#### 顺带：`selection` / `overflow` 也纳入标志范围 —— ★ 裁定：**保留纳入**，但**加一条可区分性条件**

`solution_set_display` 的 5 个字段里，`selection`/`overflow` 是**自由文本标签**、**没有设计逐字
回落值**（设计里查不到这两个标签的"逐字值"）⇒ 严格看它们不构成"回落"。但 (甲) 的字面是
"**全部字段都来自文件**才叫 `rules`"，且 `""` 确实**不是从文件读到的** ⇒ 本流**选择纳入**：
缺它们 ⇒ note + `design_default`。

**★ 主理人裁定：保留纳入（维持本流的选择）** —— (甲) 的字面就是"全部字段都来自文件"，
`""` 确实不是从文件读到的 ⇒ 老实报 `design_default` 是对的；且**只多报不少报**（`G-03` 宁严勿松）。

**★★ 附加条件（`G-62`）：两种缺件在读数上必须可区分。** 否则下游会误以为
"有一个**被设计认可过的**默认值被应用了"。故**不靠散文措辞、靠 token 分设**：

| 情形 | token | note 必须能读出 |
|---|---|---|
| **有**设计逐字依据的字段（`default_count` / `max_count` / `must_show_multiple`） | `NOTE_NO_DISPLAY_KEY` | **用了哪个**设计逐字回落值（值本身写在 note 里 + "有设计逐字依据"） |
| 设计里**本无**逐字值的标签（`selection` / `overflow`） | `NOTE_NO_DISPLAY_LABEL` | **本无**回落值、只是空串（**不是**「用了某个被设计认可的默认值」） |

⇒ 由 `test_display_fallback_note_distinguishes_the_two_kinds` **机器绑定**
（token 改名 / 两种情形混用 ⇒ **当场红**），并含**反向对照**：字段齐备时**两种 token 一个都不出现**。

---

## ② 怎么验证的（原样命令 + 原样输出 + 退出码）

### V-0 本模块测试批次（`verify.py` 正式批次）

```sh
$ /Users/gaza/.workbuddy/binaries/python/envs/default/bin/python system/scripts/ops/verify.py --batch pricelayer
✓ [pricelayer] tests/pricelayer/（Ch5 价格层：反解多解/估值路由/倒填/情景/历史外推/每日解释）  exit=0  91.26s/300s  exit=0
------------------------------------------------------------------------------
........................................................................ [ 42%]
........................................................................ [ 85%]
........................                                                 [100%]
168 passed in 90.09s (0:01:30)
------------------------------------------------------------------------------
证据留档: reports/verify_pricelayer_latest.log
```
→ **168 passed，退出码 0**，实测 **91.26s / 预算 300s**（首轮 127 例；修订轮 +41 例，全部是规则绑定与真文件用例）。

**超时取值依据（`V-02`，本轮实测两次）**：工作树内 **53.89s / 83.80s / 91.26s**（同一套用例，宿主抖动明显）。
`V-02` 注已明确"慢批次 8× 会撞上限且不必"（`53.89 × 8 = 431s > 300s`），判据是「`<= 300s` + 余量足以区分"慢"与"卡死"」，
故取**不超过上限的最大值 300s（≈3.3~5.6×）**，与 `daily`（43s → 180s）/`injection-*`（统一 300s）同族。
`verification_policy_guard` 强制项 `0 < timeout <= 300s` 实测 PASS。

各文件用例数（`pytest --collect-only -q` → `168 tests collected`）：

| 测试文件 | 首轮 | 修订轮 |
|---|---|---|
| `test_scenario_guard.py` | 19 | **36** |
| `test_daily_explain.py` | 21 | **31** |
| `test_valuation.py` | 20 | **27** |
| `test_solver.py` | 15 | **23** |
| `test_order_guard.py` | 21 | 21 |
| `test_history_guard.py` | 19 | 19 |
| `test_step_wiring.py` | 7 | **11** |
| `test_package_laziness.py` | 5 | 5 |
| **合计** | **127** | **168** |

### V-0′ 合并 `main` 之后**重跑**（同一命令，同一工作树）

```sh
$ git merge main                      # Update bef9628..3c7b34d，33 files changed，**零冲突**
$ sh system/scripts/ops/bootstrap_worktree.sh
bootstrap_worktree ✓ rules_lock_guard 通过（纪律 9 不变量已复原）
$ git status --short                  # 空（只改权限位，内容零变更）

$ …/python system/scripts/ops/verify.py --batch pricelayer
✓ [pricelayer] tests/pricelayer/（Ch5 价格层：反解多解/估值路由/倒填/情景/历史外推/每日解释）  exit=0  54.48s/300s  exit=0
168 passed in 53.62s
```
→ 合并后 **168 passed / exit=0**，实测 **54.48s/300s**。**`main` 已推进到 `3c7b34d`（含 13-A 价值层、`ws-ch13e` 等），本批仍全绿**。

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

3 条专锁落点（`Ch5 §E.1` 表头"`benchmarks` **新增**" vs `schema.models.Benchmark.coverage_profile` 开放 dict 约定）：
- `test_reverse_control_reads_unmodeled_keys_from_coverage_profile`：键放在 `coverage_profile` 内层 → **exit 0**（否则合规写法被误判"整片缺字段"）；
- `test_coverage_profile_with_insufficient_coverage_still_rejected`：内层也没给 `unmodeled_parts` 且 `modeled_coverage=0.60 < 1` → **exit 1**（证明上一条是"内层被读到"，不是"内层一律放过"）；
- `test_flat_keys_still_take_precedence_over_coverage_profile`：行内有 `modeled_coverage=1.0`、内层是旧值 `0.10` → **exit 0**（行内**优先**，与设计字面一致）。

### V-1c ★ 规则↔代码绑定演示（**真 `rules/` 只读副本**，代码不动 ⇒ 必须被拦）
脚本在 `/tmp/ch5_demo_rules.py`（**不落仓库**）：把真 `rules/*.yaml` 拷进临时根，**只改副本**再跑守卫 CLI。

```sh
$ /Users/gaza/.workbuddy/binaries/python/envs/default/bin/python /tmp/ch5_demo_rules.py
[OK ] valuation · ①规则改了 unregistered_fallback，代码未改
      反例 exit=1 | [FATAL] VALUATION-RULE-BINDING @ <no-file> — rules/valuation-methods.yaml:: unregistered_fallback.method_class='misc' 与代码默认值 'generic' 不一致 —— 未注册回落口径改…
      对照 exit=0 | RESULT: PASS（0 violations）
[OK ] scenario_guard · ②规则缺本模块读取的 6 个键
      反例 exit=1 | [FATAL] SCENARIO-RULE-BINDING @ <no-file> — rules/scenario.yaml 缺本模块实际读取的键 ['scenario_method_status_domain', 'scenario_tags', 'scenario_method_blockin…
      对照 exit=0 | RESULT: PASS（0 violations）
[OK ] scenario_guard · ③probability.default 被改成 0.5（违反 §D.6）
      反例 exit=1 | [FATAL] SCENARIO-RULE-BINDING @ <no-file> — rules/scenario.yaml:: probability.default=0.5 非 null —— Ch5 §D.6：情景概率默认 null（**不默认 50/50**）
      对照 exit=0 | RESULT: PASS（0 violations）
[OK ] scenario_guard · ④status 转正但 p05 未冻结 ⇒ method_version 不可用
      反例 exit=1 | [FATAL] SCENARIO-RULE-BINDING @ <no-file> — scenario_method_status='neutral' 已转正，但 p05（return_forecast_method）的 algorithm='tbd' ⇒ **method_version 不可用…
      对照 exit=0 | RESULT: PASS（0 violations）
RULES_DEMO_EXIT=0
```
→ **4/4 均为「反例 exit=1 + 对照 exit=0」**，`RULES_DEMO_EXIT=0`。**此即修 1 / 修 2 的可执行反例**：
真规则与代码不一致时**当场红**，而不是静默绿。

### V-1d ★ 裁定 ② 的证据：`value_source` + note（**不建夹具、不删文件**的直连探针，`G-60` 窗口内亦安全）

```sh
$ python - <<'PY'    # sys.path=system；tmp 根只 mkdir，不作 teardown 删除
── 缺文件（应 design_default + note）──
solver / 空根        value_source=design_default  notes=1
      · NO_SOLUTION_SET_DISPLAY: rules/valuation-methods.yaml 不存在 —— 回落设计逐字值 default_count=3（B18）/ max_count=5（B18）/ must_show_multiple=True（Ch5 §B.1）（非'已核'）
daily  / 空根        value_source=design_default  notes=1
      · NO_FORCED_RECHECK: rules/review.yaml 不存在 —— 回落设计逐字值 单日 -0.07 / 三日累计 -0.12（B2）、保留原判断时间 True（Ch5 §F.5 / T08）（非'已核'）
valuation / 空根     value_source=design_default  notes=1
      · NO_UNREGISTERED_FALLBACK: rules/valuation-methods.yaml 不存在 —— 回落设计逐字值 method_class='generic' / mark='unregistered'（Ch5 §D.1 末句）（非'已核'）

── 真 rules/（应 rules + 0 note）──
solver / 真文件      value_source=rules           notes=0
daily  / 真文件      value_source=rules           notes=0
valuation / 真文件   value_source=rules           notes=0
scenario policy      value_source=rules           notes=0
```

**出口面（note 必须进 report，不只活在对象上）**：

```sh
$ python scripts/pricelayer/solver.py /tmp/ch5-norules --no-report   ; echo exit=$?
  scanned display_value_source: 0
  note: NO_SOLUTION_SET_DISPLAY: …（非'已核'）
RESULT: PASS（0 violations）            exit=0

$ python scripts/pricelayer/daily_explain.py /tmp/ch5-norules --no-report ; echo exit=$?
  scanned recheck_value_source: 0
  note: NO_FORCED_RECHECK: …（非'已核'）
RESULT: PASS（0 violations）            exit=0

$ python scripts/pricelayer/valuation.py /tmp/ch5-norules --no-report   ; echo exit=$?
  scanned unregistered_fallback_value_source: 0
  note: NO_VALUATION_METHODS_RULE: rules/valuation-methods.yaml 不存在 —— 方法注册判据③不可判定…
  note: NO_UNREGISTERED_FALLBACK: …（非'已核'）
RESULT: PASS（0 violations）            exit=0
```
→ 真仓库根上三者均为 `*_value_source: 1`（值确实来自规则）。
★ 这里暴露并修掉一个**真实缺陷**：`valuation.check` 原先把读口放在 `if not baselines: return report` **之后**
⇒ **空样本时 note 被静默吞掉**（"值来自回落"在出口面完全不可见）。已前移到早退之前，并加回归锁用例
`test_cli_reports_fallback_source_even_without_baselines`。

### V-1e ★ 裁定 ③ 的证据：**"回落值 == 真文件里的值"**（对照 0 违例 + 6 个反例各 1 违例）

```sh
$ python - <<'PY'    # 逐项改**真 rules/ 的副本**，再直接调该模块的 _rule_binding_violations
═══ 对照：真文件（应 0 违例）═══
  [scenario 真值]   0 violation(s)
  [solver 真值]     0 violation(s)
  [daily 真值]      0 violation(s)
  [valuation 真值]  0 violation(s)

═══ ⑥ scenario: 取值域被改 ═══
  [domain 少一项]   1 violation(s)
      · rules/scenario.yaml:: scenario_method_status_domain=['pending','neutral'] 与代码回落值 ['pending','neutral','probability_weighted'] 不一致…
═══ ⑦ scenario: when / record_method_version 被改 ═══
  [when 改了]       1 violation(s)
      · rules/scenario.yaml:: scenario_method_blocking.when='scenario_method_status == neutral' 与代码回落值… 不一致
  [record=false]    1 violation(s)
      · rules/scenario.yaml:: scenario_method_promotion.record_method_version=False 与代码回落值 True 不一致（Ch5 §E.4：转正后须记 method_version）
═══ ③ solver: must_show_multiple 被改（**此前漏绑**）═══
  [must_show_multiple=false]  1 violation(s)
      · rules/valuation-methods.yaml:: solution_set_display.must_show_multiple=False 与代码回落值 True 不一致（Ch5 §B.1：欠定方程必须展示多组解）
═══ ③ daily: keep_original_judgment_time 被改 ═══
  [keep=false]      1 violation(s)
      · rules/review.yaml:: forced_recheck.on_hit.keep_original_judgment_time=False 与代码回落值 True 不一致 —— `T08`…
```
→ **4 个对照 0 违例 + 6 个反例各 1 违例**。每一条都有对应的 pytest 用例（`exit 1` + `*-RULE-BINDING` 码面断言）。

### V-1f ★ 本轮**未跑 pytest** —— 第三轮证据的性质声明（`G-60` 排他窗口）

主理人指定本窗口**只给 `ws-degrade-contract`** 跑 pytest（配额判别实验）。故第三轮（裁定 ③ 落地）：

- **没有跑任何 pytest**；上文 V-1d / V-1e 的证据**全部是"不建夹具、不删文件"的直连探针**：
  `py_compile` + 直接调四个读口 / 四个 `_rule_binding_violations` + 守卫 CLI（真仓库根）。
- **本轮新增的 pytest 用例尚未执行** —— 它们随 `verify.py --batch pricelayer` 在**窗口关闭后**复跑。
  ★ **本报告刻意不写"新增了多少条"这个数**：手抄的条数会随新增静默过期，唯一真源是批次跑出来的读数
  （与主理人对 `CONVENTIONS.md` 批次表的处置同一理由）。
- 既有的 **168 passed / exit=0** 读数采集于**配额触顶之前**，仍然有效（见 §② V-0 / V-0′）。
- **未**使用 `--no-report` / 环境变量 / 改 `_clear_work_dir` 等方式绕过 —— **绕过得来的绿不算证据**。

### V-1g ★ 命令工具的可靠性（本轮环境告警后的**三重复核**）

`ws-verify-shard` 广播：Bash 里 `grep` 解析到的是 **broker 包装器**（`which -a grep` 首位命中
`…/shim/brokered-bin/grep`），症状是**静默返回空且退出码为 0** ⇒ "grep 无匹配"会被读成"确实没有"。
本轮凡曾用 Bash `grep` 得出的结论，已**用 Python 逐条重算**（三选一里的第 3 条；亦可用 Grep 工具 / `/usr/bin/grep`）：

| 结论 | Python 复算结果 | 判定 |
|---|---|---|
| `pre-commit.sh` 不含 pytest（口径 16） | `pytest`/`run_pytest`/`verify.py` 三者 `str.count` 与 `re.findall` **均 0**；正对照 `run_gate` = **14** | ✅ **成立** |
| `value_source` 取值域 ∈ {`rules`,`design_default`} | 全仓 `pricelayer/*.py` 实测取值 = `['design_default','rules']` | ✅ **成立** |
| `chmod` 只出现在夹具的副本处理 | 仅 `tests/pricelayer/conftest.py` ×1（真文件 0444 未被碰） | ✅ **成立** |
| `pre-commit` 输出 0 FATAL | 保存件 `[FATAL]` = **0**、`全部门禁放行` = **1** | ✅ **成立** |
| `verify.py` 批次数 | `': Batch('` = **23** | ✅ **成立** |
| `load_unregistered_fallback` 调用点已全部改为 dataclass | 5 处代码调用点无残留元组解包（`valuation.py:201/577` 用 `.method_class`） | ✅ **成立** |

★ 同时认领**同族第二处**（自查）：`python … | tail -8; echo $?` 报的是 **`tail` 的退出码**而非 python 的
（与 `grep \|` 空真同一病灶：**测的不是被测对象**）。已改为 `cmd > file 2>&1; echo "exit=$?"`（不经管道）。

### V-1h ★ 第四轮证据：**"改前绿、改后红"** 的对照表（8 处缺键 + 2 处形态）

**取证方法（不建 pytest、不删文件、不动真源）**：把**HEAD 版旧模块**用 `exec` 装成独立模块
`scripts.pricelayer._old_*`（`git show HEAD:…` 取源），与工作树新版**在同一变异根上**各算一次
`_rule_binding_violations(...)`，再跑一次守卫 **CLI 取退出码**。变异根 = `/tmp` 里**真 `rules/` 的副本**
（`chmod 0644` 只放开副本），真文件始终 0444、内容零改动。

```text
用例                                         模块                 旧    新   CLI
对造 真 rules                                 scenario_guard     0    0     0
对造 真 rules                                 valuation          0    0     0
对造 真 rules                                 solver             0    0     0
对造 真 rules                                 daily_explain      0    0     0
删 probability.default                      scenario_guard     0    1     1
删 must_be_null_50_50                       scenario_guard     0    1     1
删 blocking.when                            scenario_guard     1    2     1
blocking.when 置空串                          scenario_guard     1    2     1
删 promotion.record_method_version          scenario_guard     0    1     1
删 valuation_compute.entry                  valuation          0    1     1
删 solution_set_display.default_count       solver             0    1     1
删 assumption_grid.solver_ref               solver             0    1     1
删 on_hit.keep_original_judgment_time       daily_explain      0    1     1
```

★ **"旧"列必须为 0 才说明这条反例在守东西** —— 8 处里 **6 处旧 = 0**（真·欠报），
2 处 `blocking.when` 旧 = 1 也已在改前就红（加载器的"形态不认识"响亮失败），第四轮新增的是**绑定面**那一条（1 → 2）。

`order_guard` 的同类对照（修 7 / 修 8；同一份数据，旧 = `git show HEAD:` 版模块）：

```text
用例                                          旧违例    新违例   新CLI
④ 1 可行 + 1 不可行（同集）                       0      1      1
⑤ 有行缺 solution_set_id                       0      1      1
⑥ 单解集 + 规则 must=false                      1      0      0
对造 单解集 + 真规则 must=true                     1      1      1
⑦ 有行缺 implied_id（且无 baselines）              0      1      1
```

★ 这张表同时说明**三种方向都测到了**：④⑤⑦ 是"旧代码**漏报**（0→1）"，⑥ 是"旧代码**内置参数**
（规则改它不动，1→0）"，"对造"行是"真值下**行为不变**（1→1，不误伤）"。

`daily_explain` 单列（`_rule_binding_violations` 是两参，旧版也须传 `trigger`；用错签名会得到假读数）：

```text
用例                                           旧加载器     旧违例 |      新加载器     新违例
对造 真 rules                                  rules       0 |        rules       0
删 on_hit.keep_original_judgment_time        rules       0 |        rules       1
删 on_hit 整节                                 rules       0 |        rules       1
keep_original_judgment_time 置假              rules       1 |        rules       1
删 single_day_drop_pct   RAISE:DailyExplainError    None | RAISE:DailyExplainError    None
```

末行即**修 5** 的证伪依据：阈值缺键时**加载器先响亮失败**（旧新一致）⇒ 那段
`NO_FORCED_RECHECK_KEY` note **不可达**且描述与行为相反。

★ **负结论带完整命令与工具名**（口径 16 的配套纪律）：上表数字全部由**本机 Python
`str.count` / AST 哈希 / `subprocess` 退出码**得出；本行所述"旧代码"= `git show HEAD:<path>` 的字节，
工具名 = `/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`（3.13.12），
取值时刻见 §③ 抬头的【对象 + SHA + 取样时刻】。

### V-1i ★ 本轮**未跑 pytest**（第二次声明，`G-60` 排他窗口）

`team-lead` 指令："本轮窗口内其他流请不要跑 pytest …… 你的 `pricelayer` 批等它回结论，
**在此之前不要跑 pytest**（`pre-commit` 可跑）。"
⇒ 本轮**未运行** `verify.py --batch pricelayer`，也**未运行** `pytest` 命令；
故**不给出**任何"通过数/耗时"。上方 V-1h 的证据**全部**是**不经 pytest** 的直连探针 + 守卫 CLI 退出码
（`G-60` 的删除配额只影响 pytest 的 `_clear_work_dir()`，与本方式无关）。
**待窗口关闭**：按正式路径重跑批次并回报**真**读数（含耗时）。

### V-1j 本轮新增用例的**执行**证据（不跑 `pytest` 命令，但**执行测试函数本体**）

本轮把 8 处缺键 + 修 4 写成永久回归用例后，**没有**留在"写了没跑"的状态：
用 `importlib` 载入测试模块，**手搓等价夹具**（`scratch` = `mkdtemp`；
`real_rules` = `conftest.copy_real_rules`；`run_script` = 照 `conftest` 逐字复刻的 `subprocess.run`；
`write_jsonl` = `conftest.write_jsonl.__wrapped__()`），再按签名注入参数**直接调用测试函数**。

```text
✓ test_scenario_guard.py::test_missing_probability_default_is_flagged_not_read_as_compliant
✓ test_scenario_guard.py::test_missing_must_be_null_50_50_is_flagged
✓ test_scenario_guard.py::test_missing_blocking_when_and_record_method_version_are_flagged
✓ test_scenario_guard.py::test_empty_blocking_when_is_flagged
✓ test_scenario_guard.py::test_reverse_control_cli_passes_on_real_rules_file
✓ test_valuation.py::test_missing_valuation_compute_entry_is_flagged
✓ test_valuation.py::test_reverse_control_cli_passes_on_real_rules_file
✓ test_solver.py::test_missing_default_count_is_flagged
✓ test_solver.py::test_missing_solver_ref_is_flagged
✓ test_solver.py::test_cli_clean_on_real_rules_file
✓ test_daily_explain.py::test_missing_on_hit_key_is_flagged_by_binding
✓ test_daily_explain.py::test_missing_threshold_key_fails_loudly_without_claiming_fallback
✓ test_daily_explain.py::test_cli_clean_on_real_rules_file
✓ test_daily_explain.py::test_trigger_missing_on_hit_key_records_note
失败数 = 0
```

★ **这条证据的性质必须说清（不夸大）**：它证明的是**断言与夹具用法**在真实对象上成立；
它**不等于** pytest 运行 —— 没有收集、没有 fixture 终结器、没有 `pytest_sessionstart`
（而那正是 `G-60` 配额作用的环节）。故**不能**据此声称"批次通过"，只能声称"这些用例的断言已执行且成立"。
★ 途中两个坑如实登记：①`pytest` 新版本**禁止直接调用 fixture 函数**（`Failed: Fixture "write_jsonl" called directly`）⇒
改用 `.__wrapped__()`；②`daily_explain._rule_binding_violations` 是 **`(root, trigger)` 两参**，
首轮探测用错签名得到**假读数**（"旧=1"）⇒ 已用 `inspect.signature` 核正后重测。

### V-1k ★ 第四轮**全量复核**：把 V-1j 的手法跑满整个 `tests/pricelayer/**`（零删除口径）

V-1j 只覆盖了"本轮新增的那几条"。为免"新的绿、老的黄"无人知，用**同一手法**（`importlib` 载入 +
手搓等价夹具 + 按签名注入 + 直接调用）把**目录下全部 8 个测试模块**跑了一遍，
并把 `parametrize` 的**参数组逐个展开**（否则会漏在 `pytest.skip` 形态里）。

命中 `G-60`（删除配额）：`SAFE_DELETE_BULK_CONFIRM_REQUIRED {"count":100003,"threshold":99999}`
⇒ 夹具根**全部改到 `/tmp`（`mkdtemp`）且**一次都不删**（`conftest` 的 `_clear_work_dir()` 不再被触碰）。
**这是绕开、不是绕过**：删除配额的作用面是 pytest 的 session 终结算，本方式压根不经那条路径，
故**没有**改 `conftest`、**没有**加环境变量、**没有**动 `--no-report`。

```text
test_daily_explain.py        通过  34 / 失败  0
test_history_guard.py        通过  19 / 失败  0
test_order_guard.py          通过  25 / 失败  0
test_package_laziness.py     通过   5 / 失败  0
test_scenario_guard.py       通过  44 / 失败  0
test_solver.py               通过  29 / 失败  0
test_step_wiring.py          通过   9 / 失败  0
test_valuation.py            通过  31 / 失败  0

合计：通过 196 / 失败 0
```

〔对象 = 工作树 `.worktrees/ws-ch5-pricelayer`，分支 `ws/ch5-pricelayer`，SHA `89e2d15`（含未提交的修 7/修 8 工作区改动）；取样时刻 = `2026-09-16T15:38:23Z`；
执行体 = `/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`；`exit=0`〕

★ 这一列**同样不是**"批次通过"（性质同 V-1j 末段的声明：无收集、无 fixture 终结器）——
它证明的是**整目录的断言与夹具用法在真实对象上成立、且我本轮的改动没有打黄任何老用例**。
正式批次读数仍以 §② V-0 的 `verify.py --batch pricelayer` 为准。

### V-1l ★ 第五轮裁定（甲）的证据：**8 例反例（旧→新）+ 3 例反向对照**

取证方式与 §② V-1h 同：`/tmp` 里**真 `rules/` 的副本**做变异根（**只 `chmod 0644` 副本**，
原文件是 0444 且**从未被写过**）；**旧 = `git show HEAD:system/scripts/pricelayer/<mod>.py`
的字节** `exec` 成 `scripts.pricelayer._old_*`，与新版在**同一根**上各读一次。

```text
删掉的子键                                    旧 value_source   新 value_source   新 note 点名该键
solution_set_display.default_count                    rules      design_default        ✓
solution_set_display.max_count                        rules      design_default        ✓
solution_set_display.must_show_multiple               rules      design_default        ✓
solution_set_display.selection                        rules      design_default        ✓
solution_set_display.overflow                         rules      design_default        ✓
unregistered_fallback.method_class                    rules      design_default        ✓
unregistered_fallback.mark                            rules      design_default        ✓
forced_recheck.on_hit                                 rules      design_default        ✓
```

```text
反向对照（G-05，真文件·字段齐备）       旧 value_source   新 value_source   新 note 数
solution_set_display (5 字段齐)               rules             rules           0
unregistered_fallback (2 字段齐)              rules             rules           0
forced_recheck (含 on_hit)                    rules             rules           0
```

★ **读法（与 V-1h 的"旧列必须为 0"相反，这里刻意**不**那样要求）**：本表的旧列**本来就该是
`rules`** —— 那**正是被裁定的旧口径**（"节存在即 `rules`"），**不是"旧代码漏报"**。
本表要证的是**声明粒度**变了、且**反向对照下两版一致**（未误伤真数据）。

★ **真文件上四门禁 CLI（未改任何文件）**：

```text
scripts/pricelayer/solver.py          exit=0   scanned display_value_source: 1
scripts/pricelayer/valuation.py       exit=0   scanned unregistered_fallback_value_source: 1
scripts/pricelayer/daily_explain.py   exit=0   scanned recheck_value_source: 1
scripts/pricelayer/order_guard.py     exit=0
```

★ **§1-6③ 的次序判据（"早退吞违例"）实测**：删 `on_hit.keep_original_judgment_time` ⇒

```text
exit=1
  scanned recheck_value_source: 0
  note: NO_ON_HIT_KEY: rules/review.yaml:: forced_recheck.on_hit.keep_original_judgment_time 缺失 —— 取设计逐字回落值 True …
  [FATAL] DAILY-RULE-BINDING — …keep_original_judgment_time 缺失 —— 缺键本身即违例（Ch11 §D.2）…
  [FATAL] DAILY-RULE-BINDING — …forced_recheck 读不到值（NO_ON_HIT_KEY: …）—— **不**按回落值判'一致'…
```

⇒ **具名违例与笼统违例都在** —— 若把存在性判据留在早退之后，**第一行 FATAL 会消失**（只剩第二行）。

★ **工具与命令（负结论带工具名，口径 16）**：上列数字由**本机 Python**
（`/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`，3.13.12）经
`importlib` / `types.ModuleType` / `subprocess.run(...).returncode` / `os.chmod` 得出；
"旧代码"取自 `git show HEAD:…` 的**字节**（工具 = `git`），非我复述。
〔对象 = 工作树 `.worktrees/ws-ch5-pricelayer`，分支 `ws/ch5-pricelayer`，`HEAD = 2611c85` + 本工作区改动；
取样时刻 = `2026-09-16T16:0x Z`〕

#### 第五轮**全量复核**（同 V-1k 手法，零删除口径）

改完 3 个 `load_*` 后重跑整目录（同一手法、同一零删除口径，**不经 pytest 命令**）：

```text
test_daily_explain.py        通过  34 / 失败  0
test_history_guard.py        通过  19 / 失败  0
test_order_guard.py          通过  25 / 失败  0
test_package_laziness.py     通过   5 / 失败  0
test_scenario_guard.py       通过  44 / 失败  0
test_solver.py               通过  34 / 失败  0        ← 第四轮 29，本轮 +5（新增的 5 组 parametrize）
test_step_wiring.py          通过   9 / 失败  0
test_valuation.py            通过  31 / 失败  0

合计：通过 201 / 失败 0      exit=0
```

〔取样时刻 = `2026-09-16T15:51:15Z`；执行体同 V-1k；**零删除**（`/tmp` 夹具，未触碰 `conftest` / 环境变量 / `--no-report`）〕
★ 性质声明同 V-1j/V-1k：**不等于** pytest 运行，**不能**据此声称"批次通过"。

**★ 合并最新 `main` 后重跑一次（同一手法、同一零删除口径）**：**通过 201 / 失败 0**，逐模块数字与上表**逐个相同**
〔对象 = `ws/ch5-pricelayer` @ `9d59302`（`git merge main` 之后，零冲突）；取样时刻 = `2026-09-16T15:55:20Z`〕
⇒ 说明"并入 `main` 的新改动（`degrade.py` / `pipeline.py` / `verify.py`）**没有打黄本模块任何用例**"。

#### 附加条件（`G-62`）：两种缺件**在读数上可区分** —— 原始输出

裁定 (甲) 之后主理人加了一条附加条件：`selection`/`overflow` **没有设计逐字回落值** ⇒ note 里
**必须把两种情况分开写**，否则下游会误以为"有一个**被设计认可过的**默认值被应用了"。
落地方式 = **token 分设**（不是只改措辞），实测原样输出：

```text
token①   = NO_DISPLAY_KEY          （缺键 ⇒ 用了设计逐字回落值）
token②   = NO_DISPLAY_LABEL        （缺键 ⇒ 空串，本无设计逐字回落值）
两 token 相异 = True

=== ① 有设计逐字依据的字段 ===
  删 default_count          value_source=design_default
     NO_DISPLAY_KEY: rules/valuation-methods.yaml:: solution_set_display.default_count 缺失 —— 该字段取**设计逐字回落值** 3（有设计逐字依据）（非'已核'）
  删 max_count              value_source=design_default
     NO_DISPLAY_KEY: rules/valuation-methods.yaml:: solution_set_display.max_count 缺失 —— 该字段取**设计逐字回落值** 5（有设计逐字依据）（非'已核'）
  删 must_show_multiple     value_source=design_default
     NO_DISPLAY_KEY: rules/valuation-methods.yaml:: solution_set_display.must_show_multiple 缺失 —— 该字段取**设计逐字回落值** True（有设计逐字依据）（非'已核'）

=== ② 设计里本无逐字值的标签 ===
  删 selection              value_source=design_default
     NO_DISPLAY_LABEL: rules/valuation-methods.yaml:: solution_set_display.selection 缺失 —— 该标签在设计里**本无逐字回落值** ⇒ 字段为空串（**不是「用了某个被设计认可的默认值」**）（非'已核'）
  删 overflow               value_source=design_default
     NO_DISPLAY_LABEL: rules/valuation-methods.yaml:: solution_set_display.overflow 缺失 —— 该标签在设计里**本无逐字回落值** ⇒ 字段为空串（**不是「用了某个被设计认可的默认值」**）（非'已核'）

=== ③ 反向对照：字段齐备 ===
  value_source=rules  notes=()
```

★ **两种情形在 token 层面就分开了** ⇒ 下游只需判前缀即可区分，**不必解析散文**。
★ 机器绑定：`test_display_fallback_note_distinguishes_the_two_kinds`（token 改名 / 混用 ⇒ 红；
并断言"① 的 note 里必须出现具体回落值"、"② 的 note 里必须出现「本无」且不得出现①的 token"）。

**★ 全量复核（附加条件落地后，同口径）**：**通过 202 / 失败 0**
（`test_solver.py` 34 → **35**，即新增的这条机器绑定；其余 7 个模块逐模块不变）
〔取样时刻 = `2026-09-16T16:00:08Z`；`exit=0`〕

---

### V-1m ★ 跨口径对照：**pytest 的 `passed` 与本流替代口径，在同一内容上一致**

**来历**：`ws-verify-shard` 在 `#102`（"相关批次必须复跑"）里顺手取了本批次的**真机批次读数**并按本流的
4 项规格给了出来。★ 那是它 `#102` 的副产物、**不是**替 `#83` 取数，故本流**只登记、不据此销卡**。

**先做对象对齐（`口径 10`）—— 这一步是必须先做的**：

```text
读数对象（其自报）：工作树 .worktrees/ws-fixture-cost · 分支 ws/fixture-cost · HEAD=2c30cee · 取样 2026-09-17 00:04:58 +0800
批名/命令：verify.py --batch pricelayer        退出码：0
真机原文：201 passed in 14.61s ；门禁自印 14.84s/300s ；进度点 72+72+57 = 201
```

```text
$ git merge-base --is-ancestor 862e91c 2c30cee        → 非 0   （★ 我的最后一个提交**不在**其中）
$ git merge-base --is-ancestor 76f1de5 2c30cee        → 0      （裁定甲**在**）
$ git diff --stat 862e91c 2c30cee -- system/tests/pricelayer
  system/tests/pricelayer/test_solver.py | 61 ------------------------  （恰好 = 862e91c 自己加的那 61 行）
$ git diff --stat 862e91c 2c30cee -- system/scripts/pricelayer
  system/scripts/pricelayer/solver.py | 8 +++ / 27 ---                     （恰好 = 862e91c 的 token 改动）
```

⇒ **该树的 `tests/pricelayer/**` ＝ 本流在 `862e91c` **之前**那一版**（只少最后一个提交）。

**★★ 由此得到的正面结论**：

| 内容版本 | 本流替代口径（执行测试函数本体、逐组展开） | pytest 真机 `passed` |
|---|---|---|
| `76f1de5`（裁定甲、**无**可区分性绑定） | **201**（本流 `2026-09-16T15:51:15Z` 实测） | **201**（`2c30cee` 上实测） |

⇒ **同一内容上两个口径相等** ⇒ **`202` 与 `201` 的差不是口径差，是对象差（差一个提交 +1 例）**。
⇒ ⇒ **更强的结论**：**此前担心的"pytest 会少收集某个 `parametrize` 组"不存在** ——
本流那个"逐组展开"的替代口径与 pytest 的收集口径**在本例 1:1 对齐**。

★ **配平（本流 `#101` 判定清单里的那一步）**：`collected 201 = passed 201 + failed 0 + skipped 0 + xfailed 0 + errors 0`
⇒ **配平干净** ⇒ 按本流自己预声明的规则，**不是"有组没被收集"**。

#### ★★ 留给后续的一条**可falsify命题**（主理人批准转达）—— 但**须连前提一起引**

> **命题（严格形态）**：在**同一对象**上重取 `verify.py --batch pricelayer`，
> 其 `passed` **应当等于**该对象上本流替代口径（逐组展开）的计数。
>
> **`202` 只是"当且仅当下面前提成立"时的那个数**：
> 前提 = `2c30cee` 之后再无**其他**提交改动 `tests/pricelayer/**`。
> ⇒ 若期间别的流又动了那目录（**本轮实测一晚动过三次**：`183 → 192 → 201`），
> 预测值就**不再是 `202`**，此时应改按"严格形态"核，而不是判"预测失败"。

★ **为什么必须连前提一起写**：**用会漂的常数表达的预测，本身就不是可falsify的**
——它只是**看起来可falsify**。这与本卡 §③"不写死条数"是**同一条病**（`#84`/`#91` 同族）。
★ **若重取得到 `201`（在前提成立时）** ⇒ 才说明**真有组没被收集**，那时才该按配平表往下查。

★ **代价登记（诚实）**：本条对照**不是本流自己跑的批次**（本流遵主理人指令**不自起会话**），
对象也不是本工作树；且 `ws-verify-shard` 已按其口径**明确拒绝**做 `202` vs `201` 的比较
（`口径 21`：不同口径不得比大小）。本流在此**补上的是"差在哪"的机理**（对象差一个提交），
而**不是**用它的读数替本流的卡结案 —— **最终读数仍待 `#83` 轮 1**。
★ **主理人裁定（第五轮）**：该读数**接受为"对象是另一棵树的合法读数"（`V-11`：举证半径 = 结论半径），
可引用（**须标注对象** `ws-fixture-cost @ 2c30cee`）；但**不能替 `#101` 结案**，因本卡对象**不含**最后那个提交。

★ **`G-60` 前提修正（本流自查代码证实，非转述）**：`verify.py::_child_env()`（`verify.py:620-625`）
**显式**返回 `CODEBUDDY_SAFE_DELETE_ENABLED="0"`（`run_pytest.sh:35` 同；`3653c7c` 起，已在 main），
该函数 docstring 写明这是 `E` 裁定的「**合法配置**、非绕过」，且"`E` 下即**生产/门禁口径**"。
⇒ **走包装器跑批次，删除守卫是关的**；撞配额的是**绕过包装器直接跑 `pytest`** 那条路径。
⇒ 故本卡原先"等窗口 / 会撞 `G-60`"的前置**对门禁口径不成立**，已订正。
⇒ ★ **派生边界（本流登记，供主理人处置）**：`SAFE_DELETE_BULK_CONFIRM_REQUIRED` 这一整类
在**门禁口径里结构性不可达**。**"不可达"≠"不存在"** —— 绕过包装器那条路径上它**是活的**
（`Bash` env 实测 `=1`）。若门禁侧不**明文**写下"删除配额不属于门禁口径"，
后来的读者会把"门禁里从没见它红过"读成"该约束不成立" —— 即 **`G-62` 加在安全机制自身**上：
**"没报"与"没被检"在读数上长得一样**。
★ **但"要不要现在跑"本流不擅自决定**（主理人已下"不要自起会话"，且窗口序由他定）。

---

### V-2 六门禁在**真仓库真源**上运行（`code_root = system`）

```sh
$ for m in solver valuation order_guard scenario_guard history_guard daily_explain; do
    python scripts/pricelayer/$m.py . --no-report; echo "EXIT=$?"; done

# solver          exit=0
  scanned min_solution_count: 2
  scanned rule_binding_checks: 2
  note: NO_IMPLIED_ROWS: 无反解行可检（非'已验证'）
RESULT: PASS（0 violations）
# valuation       exit=0
  scanned routing_model_classes: 4
  scanned rule_binding_checks: 3
  scanned valuations_checked: 0
RESULT: PASS（0 violations）
# order_guard     exit=0
  scanned solution_sets: 0
  note: NO_IMPLIED_ROWS: facts/implied_requirements.jsonl 无可用解集（非'已验证'）
  note: NO_IMPLIED_ROWS: 无反解 id 可比对，本判据真空成立
RESULT: PASS（0 violations）
# scenario_guard  exit=0
  scanned probabilities_checked: 0
  scanned rule_keys_required: 7
  note: NO_PROBABILITY_FILLED: 无任何已填概率（默认 null 是设计常态，非'已验证'）
RESULT: PASS（0 violations）
# history_guard   exit=0
  scanned benchmarks: 0 ; scanned coverage_keys: 8
  note: NO_BENCHMARKS: facts/benchmarks.jsonl 无行（非'已验证'）
RESULT: PASS（0 violations）
# daily_explain   exit=0
  scanned recheck_value_source: 1
  scanned rule_binding_checks: 1
  note: NO_PRICES: facts/prices.jsonl 无行（非'已验证'）
RESULT: PASS（0 violations）
```
→ 六门禁在真仓库**全 exit=0**，且**每一处空样本都产出显式 `NO_*` note**（`G-03`：不把"无被检对象"当"已验证"）。
`scanned routing_model_classes: 4` / `rule_keys_required: 7` / `rule_binding_checks: 2·3·1` 都证明**规则绑定检查真的跑了**，不是空转。

### V-2b ★ 真 `rules/` 文件的**取值逐个核**（主理人点名要求）

```sh
$ python - <<'PY'   # code_root = system
```

**`load_method_routing(rules/valuation-methods.yaml)` 真值 —— 与主理人实测逐字一致（4/2/3/1）**

| `model_class` | 个数 | 方法（逐字） |
|---|---|---|
| `hardware` | 4 | `正常化利润` · `含再投资现金流` · `分部估值` · `同行比较` |
| `cloud` | 2 | `含再投资现金流（订阅/用量）` · `分部` |
| `software` | 3 | `正常化利润` · `现金流` · `留存指标` |
| `etf` | 1 | `简化底稿` |

**本实现在真值下行为正确（不只是自备夹具下）**：
`test_real_rules_routing_matches_team_lead_measured_values` 把上表**逐字**断言进用例（4 个 `model_class`，分别 4/2/3/1 项）；
`test_real_rules_route_method_on_real_values` 用真值逐个 `route_method` 验证命中；`test_real_rules_unregistered_fallback_matches_code_defaults`
验证回落口径 `generic`/`unregistered` 与代码默认一致；`test_reverse_control_cli_passes_on_real_rules_file` 证明**真文件上 CLI 干净退出（exit 0）**。
→ 首轮"`method_routing` 键名属**假定**"的登记**已作废**：真文件实证使用该键名。

**其余真值（逐个核，均与实现一致）**

| 读取函数 | 真来源 | 真值 |
|---|---|---|
| `load_scenario_policy` | `rules/scenario.yaml` | `status='pending'` · `value_source='rules'` · `domain=('pending','neutral','probability_weighted')` · `blocking=True` · `blocking_effect='assert_scenario_match 无法建立一致口径 → **阻塞相对判断生成**'` · `blocking_downstream='待判断（而非建议）'` · `required_field_at_downstream='benchmark_forecast'` · `param_ref='p05'` · `record_method_version=True` · `method_version=''`（`method_version_source='not_applicable_pending'`，**正确的空值**，见修 1） |
| `assert_rule_tags_match` | 同上 `scenario_tags` | `('bear','neutral','bull','custom')` —— 与 `ScenarioTag` 枚举**逐字相等** |
| `assert_relative_judgment_allowed` | 同上 `scenario_method_blocking` | **BLOCKED**（`scenario_method_status=pending` ⇒ 阻塞），文案内联规则原文 + 下游所需字段 |
| `load_solution_set_display` | `rules/valuation-methods.yaml` | `default_count=3` · `max_count=5` · `must_show_multiple=True` ⇒ `min_count=2` · `value_source='rules'` |
| `load_recheck_trigger` | `rules/review.yaml` | 单日 `-0.07` · 三日累计 `-0.12`（**规则里写的是百分点 `-7`/`-12`**）· `keep_original_judgment_time=True` · `value_source='rules'` |

### V-3 全门禁 pre-commit

```sh
$ sh system/scripts/ops/pre-commit.sh
…
== criterion_effectiveness_guard.py ==
…
pre-commit ✓ 全部门禁放行
PRECOMMIT_EXIT=0
```
`verification_policy_guard` 报 **`scanned batches: 21` / `test_files: 67` / `test_files_uncovered: 0`** ⇒
`tests/pricelayer/`（新目录）已被批次覆盖，**`V-06` 闭环**。
`rules_lock_guard` **RESULT: PASS（0 violations）**（`scanned files_on_disk: 14` / `registered_files: 14`）。

★ **本轮 `pre-commit` 曾红一次，如实登记**：4 条 FATAL 为 `rules/{baseline,metric-sets,scenario,valuation-methods}.yaml`
权限 `0o644`（应为 `0o444`）。**根因不是本流写坏了文件** —— `git merge` 只跟踪可执行位，`rules/*.yaml` 一进工作树就是 `0644`。
按**被认可的处置**修复：

```sh
$ sh system/scripts/ops/bootstrap_worktree.sh
RESULT: PASS（0 violations）
bootstrap_worktree ✓ rules_lock_guard 通过（纪律 9 不变量已复原）
$ git status --short system/rules system/registry     # 空
$ git diff --stat   -- system/rules system/registry   # 空
```
→ **只改权限位、内容零变更**（未走 `lock_rules.py`，避免 `locked_at`/SHA 台账无谓翻动）。
另：`rules/` 是 **0444**，所以**演示/测试里凡要"改真规则"的都必须先拷贝再改副本**（`/tmp/ch5_demo_rules.py` 与 `real_rules` 夹具均如此，见 §①-2 装置 2/4）。

**合并后 `pre-commit` 重跑**：

```sh
$ sh system/scripts/ops/pre-commit.sh
pre-commit ✓ 全部门禁放行        PRECOMMIT_EXIT=0
$ git status --short             # 空
```

### V-4 批次与阶段门（诚实登记非本流的红点）

```sh
$ python scripts/ops/run_all_gates.py . --timeout 30
  traceback.py                       exit=1        0.14s
  非零计数                               1

$ python scripts/delivery/stage_gate.py --stage all
RESULT: FAIL（7 violations）
```
→ `traceback.py` 的 `G1-03` 投诉 `facts/recommendations.jsonl`（`rec-nvda-001` 缺 `assumptions`/`computation`）；
`stage_gate` 的 7 条 FATAL 全部指向**其他卡片的判据**（13-A 的 `chapter4_g_depth`/`evidence_locatable`、core_chain/expansion 前置产物）。
**均与本次改动无关**（本次只动 `verify.py` 批次表 + `CONVENTIONS.md` 批次表 + `pricelayer/` + `tests/pricelayer/` + `PROGRESS.md`，见 §③ `git status --short`）。

### V-5 孤儿模块排查（"不写 `chain_steps.py` 也能到"）

`system/scripts/orchestrate/chain_steps.py` 是共享文件（**非本流可改**），故本流不改它，而是提供**两种一行接线**并各自留测试：

```python
# 方案 A（单步挂载，不改 chain_steps）：
from scripts.pricelayer.step import make_price_guard_handler
pipeline.register("price_layer", 6, make_price_guard_handler(root, step_no=6))
# 方案 B（整步登记）：
from scripts.pricelayer.step import register_into
register_into(pipeline, step_no=6)
```
`test_step_wiring.py`（**11 例**）断言 `run_price_guards` **真的调用了 6 个入口**（`(module, "check")` 属性对 **AST 绑定**断言，非词面搜索 —— 修订轮补入 `("scenario_guard","check")`），并断言 `report.scenario_blocking is True`、handler 的 `produced` 恒空、`degraded` 在无被检对象时为真、`incomplete_reason` 点名模型侧缺口；另有 `test_run_price_guards_surfaces_rule_binding_violations`（注入规则漂移 ⇒ 违规上报）与 `test_run_price_guards_clean_on_real_rules_files`（真文件 ⇒ 干净）。

**真机接线输出**：

```sh
$ python scripts/pricelayer/step.py .
== pricelayer_step ==
  guards_run: valuation, order_guard, history_guard, daily_explain, scenario_guard, scenario_guard:policy
  checked_ids: 1
  scenario_method_status: pending（rules）
  scenario_blocking: True（读 rules/scenario.yaml）
  …
  note: SCENARIO_METHOD_PENDING: scenario_method_status=pending（来源 rules）—— 方法未定 ⇒ 阻塞相对判断生成（Ch5 §E.4 / N5.4-07…规则文件口径：…阻塞相对判断生成；待判断（而非建议）；下游所需字段：benchmark_forecast
RESULT: PASS（0 violations）        EXIT=0
```
**确定性部分（估值路由 / 倒填检测 / 口径校验 / 情景裁决）经此出口可在 step 4/5/6 被触达**；模型侧（假设生成、基准选取与价格抓取）属阶段②③，本批次不交付 —— 该接缝在 §④-5 如实登记。

---

## ③ 结果

- **本模块测试** —— ★ **本条不写死任何条数，只指真源**（见下方"为什么"）：
  - **判据真源** = 批次**自印**的那一行（`verify.py --batch pricelayer` 输出里
    `✓ [pricelayer] … exit=… <elapsed>s/300s exit=…`）；
  - **日志真源** = `system/reports/verify_pricelayer_latest.log`（批次每次覆盖写入）；
  - ⇒ 引用时**连对象一起引**（`口径 10`）：**哪个 SHA + 哪个工作树 + 取样时刻**。
  - ★ **本卡交付时的最终读数仍待 `#83` 轮 1 统一取**（主理人指定，本流不自起会话）。

  **★ 为什么不留散文里的条数**：本条原写 `168 passed / 91.26s`，现已**同时过期**且**会继续漂** ——
  实测一晚上动过三次（`183` → `192` → `201` → `202`，其中 `202` 是本流的替代口径）。
  写死的数**活不过一轮**，且读者无从判断它对应哪个对象 ⇒ 与 `#84`（清 `verify.py` 手写数量漂移）、
  `#91`（"6 片"表述漂移）同一类病，按 `V-10`/`V-11` 的口径**改成指真源**。

  **历史读数（仅作留档，逐条带对象，不得当现值）**：

  | 读数 | 条数 | 耗时 | 对象（`口径 10`） |
  |---|---|---|---|
  | 首轮交付 | `127 passed` | `51.19s/300s` | `main` 上试合并批次（主理人实测，见 §② V-0） |
  | 修订轮 | `168 passed` | `91.26s/300s` | 修订轮工作树（**早于** §1-5 修 3–8） |
  | `#102` 副产物（`ws-verify-shard` 实测，经其报告） | `201 passed`（`in 14.61s`） | `14.84s/300s` | `.worktrees/ws-fixture-cost` / `ws/fixture-cost` / **`2c30cee`** / 取样 `2026-09-17 00:04:58 +0800` |
  | 替代口径（**非 pytest**，本流实测） | `196` → `201` → `202` | — | 本工作树逐阶段（见 §② V-1k / V-1l） |

  ★ **`201` 与 `202` 的差不是口径差，是对象差**（已查实）：`2c30cee` **不含** `862e91c`
  （`git merge-base --is-ancestor 862e91c 2c30cee` → 非 0；`76f1de5` **在**），
  且 `git diff 862e91c 2c30cee -- system/tests/pricelayer` **只差 `test_solver.py` 的 61 行**，
  正是 `862e91c` 自己加的那条可区分性机器绑定。
  ★★ **由此得到一个正面结论（比差值本身值钱）**：**在同一内容上，pytest 的 `passed` = `201`
  与本流"执行测试函数本体"口径的 `201` 完全一致** ⇒ **两口径在本例一致**，
  此前担心的"pytest 少收集一组 `parametrize`"**不存在**。详见 §② V-1m。
- **门禁**：`pre-commit.sh` **全部门禁放行**（exit 0），**无 `--no-verify`**；`V-06` 因新批次登记而闭环（`uncovered 0`）。
- **反例有效性**：**6/6 守卫**有可执行反例（exit=1）+ 反向对照（exit=0）（`DEMO_EXIT=0`）；
  **4/4 规则↔代码绑定**有可执行反例 + 对照（`RULES_DEMO_EXIT=0`）。每个反例都是**真机跑出来的退出码**，不是断言文字。
- **★ 修订轮的两处缺陷已修且有防复发装置**：修 1（`method_version` 真实载体 = `param_ref → p05`，删掉 `or ""` 静默兜底、转正后不可用即响亮报错）；
  修 2（`blocking` / 取值域改读规则键，`when` 语法严格校验、不认识即响亮失败）。四组 `*-RULE-BINDING` 判据集 + `real_rules` 夹具 + SHA256 只读断言，把 `G-43`/`G-45` 这一族**机器绑定**住了。
- **`Ch11 §D.2`「参数只能住 `rules/`」本次核过一遍**：`solver` 展示上限/下限、`daily_explain` 复检阈值、`valuation` 回落口径与计算入口、`scenario_guard` 状态域/阻塞条件/标签集/概率默认 —— **全部读规则**；
  仅 `MIN_MODELED_COVERAGE`（B4）保持常量，因为 `rules/**` 里**确实没有任何** `modeled_coverage` 键（已核，非假定）。
- **复用与合规（`G-06` 零重造）**：`OrderViolation`/`MissingInput`/`UndefinedComputation` ← `scripts.compute.contract`；
  `compute_value_per_share_range` / `require_baseline_before_compute` ← `scripts.compute.valuation`；
  `read_rows` ← `scripts.compute.store`（`DerivedValue` 真源在 `derived/` 而非 `facts/`）；
  `forward_closure` ← `scripts.graph.closure`；`MoatWriter` ← `schema.models`；**参数读口** ← `config.freeze.get_param`（修 1 用它，未另造）。
- **禁词自查**：`weight`/`score`/`vote` 在 `scripts/pricelayer/**` 源码字符串中 0 命中（仅 `test_history_guard.py` 的 JSON 字面夹具里出现 `weight`，且该词只在 `decision_scope` 受限）；
  `PLACEHOLDER-CN`（`待实现|待补|占位|未实现`）在运行期消息中 0 命中。
- **`rules/**` 只读**：全程未写入；`git status --short system/rules system/registry` 与 `git diff --stat -- system/rules system/registry` **均为空**；
  测试所需的"改规则"一律改**副本**，并有 SHA256 前后对比用例把关。

### 提交哈希

- **修订内容提交**：`9552e8c`
- **合并 `main`（`3c7b34d`）后的合并提交**：`60aab53`（试合并**零冲突**；合并后 `bootstrap_worktree.sh` + 批次重跑 + `pre-commit` 全绿，见 §② V-0′/V-3）
- 首轮提交：`9834f4f`（已在主干，merge `4468da5`）
- （提交信息内不含动态哈希；哈希由 `git rev-parse HEAD` 另附于回报消息。）

**第四轮（自查轮）提交**（均**未** `--no-verify`）：

| 提交 | 内容 | 是否已在 main（核法：`git merge-base --is-ancestor <sha> main`） |
|---|---|---|
| `f648a3d` | 报告：删掉散文里的条数 + 补 V-1f/V-1g | ✅ 已在 |
| `bff9791` | 修 3/修 4/修 5/修 6（8 处缺键静默跳过 + 死 note + 重复死用例） | ✅ 已在 |
| `bf99f91` | 修 3/修 4 的 9 条永久回归用例 + 诚实证据声明 | ✅ 已在 |
| `89e2d15` | `git merge main`（快进） | ✅ 已在 |
| **`89cc2d8`** | **修 7 / 修 8（`order_guard`）+ §② V-1k 全量复核 + §④-9 登记** | ⏳ **待合** |
| **`d489300`** | 本表自身的**取样时刻**订正 + §③「本模块测试」读数标明对象（纯文档） | ⏳ **待合** |
| **`eacd8e7`** | 提交表补 `d489300`，并把"待合"判法改成可复算的 `git log` 区间（纯文档） | ⏳ **待合** |
| **`76f1de5`** | ★ **第五轮：落地主理人裁定（甲）** + §1-6 / §② V-1l / §④-8a 闭合 + `PROGRESS.md §12.4` | ⏳ **待合** |

★ **本表"待合"的判法**（可复算，不依赖本行文字）：`git log --oneline d766a32..ws/ch5-pricelayer`
列出的事实上就是**尚未进 main 的全部提交**（本条撰写时 = `89cc2d8`、`d489300`、`eacd8e7`、`76f1de5` 四条）；
若本表与之一致即为准。**避免"表格里写着唯一、实际有两条"这类会随手过期的措辞**。


★ **更正**：本表初稿把 `bf99f91`/`89e2d15` 写成"待合"——实测 `git merge-base --is-ancestor` 两条**均返回 0**
（`main` 已快进到含它们的位置），故订正为"已在"。**这是我自己写错的，登记在此**。

〔核对对象 = 工作树 `.worktrees/ws-ch5-pricelayer`，分支 `ws/ch5-pricelayer`，`HEAD = 89cc2d8`，
`main = d766a32`；取样时刻 = `2026-09-16T15:47Z` 前后；命令 = `git merge-base --is-ancestor`，工具 = `git`，逐条 `exit=0/1`〕


### `git status --short`（第四轮，提交前）

```
 M system/reports/ws_ch5_pricelayer_report.md
 M system/scripts/pricelayer/order_guard.py
 M system/tests/pricelayer/test_order_guard.py
```

〔对象 = 工作树 `.worktrees/ws-ch5-pricelayer`，分支 `ws/ch5-pricelayer`，SHA `89e2d15`；取样时刻 = `2026-09-16T15:38:29Z`；
命令 = `git status --short`，工具 = `git` 2.x，`exit=0`〕
（**未使用 `git add -A`**；只 add 上表 3 个文件。`rules/**`、`facts/**`、`derived/**`、`schema/**` 无任何改动。）


### `git status --short`（提交前，修订轮）

```
 M system/CONVENTIONS.md
 M system/PROGRESS.md
 M system/scripts/ops/verify.py
 M system/scripts/pricelayer/__init__.py
 M system/scripts/pricelayer/daily_explain.py
 M system/scripts/pricelayer/scenario_guard.py
 M system/scripts/pricelayer/solver.py
 M system/scripts/pricelayer/step.py
 M system/scripts/pricelayer/valuation.py
 M system/tests/pricelayer/conftest.py
 M system/tests/pricelayer/test_daily_explain.py
 M system/tests/pricelayer/test_scenario_guard.py
 M system/tests/pricelayer/test_solver.py
 M system/tests/pricelayer/test_step_wiring.py
 M system/tests/pricelayer/test_valuation.py
```
（**未使用 `git add -A`**；只 add 上表 15 个文件 + 本报告。`rules/**`、`facts/**`、`derived/**`、`schema/**` 无任何改动。）

**提交后**：`git merge main`（零冲突，33 files changed）→ `bootstrap_worktree.sh` → 批次重跑 168 passed → `pre-commit` 全绿 →
`git status --short` **空**（工作树干净、无未跟踪残留）。

---

## ④ 诚实登记的残留 / 不确定项

> 下列各项均为「设计未写死 / 设计自相矛盾 / 字段缺落点」。**处理方式**：代码里做**显式且响亮**的失败，或回落到**设计原文/规则文件**的值并打 note，同时在本文登记。
> **未凭猜测发明任何键名语义。**
> ★ 修订轮起，凡是**能从真 `rules/` 文件读到的**，一律已改成读文件，并由 `*-RULE-BINDING` 判据集**机器绑定**（§①-2）—— 下面**只登记读不到的东西**。

### ④-1 修订轮已澄清的两项（原"待裁定"，现记结论）

| 项 | 结论 |
|---|---|
| `method_version` 的载体 | **不是**规则文件里的键。`§E.4` 说「转正后**记** `method_version`」⇒ 它是**运行时写入的字段**；真实载体是 `scenario_consistency.param_ref → rules/freeze.yaml::p05`，故由 `config.freeze.get_param` 解析（修 1）。`status == pending` 时**不适用**故返回 `""` 并标 `not_applicable_pending`；一旦转正而版本不可用 ⇒ 抛 `ScenarioGuardError` |
| `method_routing` 键名 | 首轮登记为「**假定**」——**已作废**。真 `rules/valuation-methods.yaml` 实证使用该键名，且 4 个 `model_class` 的真值已逐个核过并写进用例（§② V-2b） |

### ④-2 `Ch5 §E.2` 首句与 `R-06 ①`（禁子串判据）**直接冲突**

`§E.2` 首句写作 `"past_return" in forecast.basis` —— 这是**子串判据**，命中 `R-06 ①`（rubric 禁词面判据）。**本流处置**：改用**词元等价**（`basis` 与 `HISTORICAL_BASIS_TOKENS` 逐词元相等）+ **更穷尽的结构判据**（`period != evidence_period` ⇒ 用历史期收益当预测期收益）。该取舍已写进 `history_guard` 模块 docstring。**请裁定**：是否需要同步申请修订 `§E.2` 表述。

### ④-3 字段命名 / 落点缺口的 4 处

| 冲突 | 现状 | 本流处置 |
|---|---|---|
| `§D.4` `assumption_source` vs `§D.5` `input_source` | 同一语义两个名字 | **已统一**用 `schema.models.InputSource`（`§D.5` 的 `input_source`），并在 docstring 标注 `§D.4` 系同一物 |
| `Ch5 §B.1` 未给 `f` 的具体形式 | 只给 `P=f(g,m,r,k,t)` 与"欠定" | 编程上只实现**网格 + 剪枝 + 多解**，具体 `f` 由调用方注入；**程序不做假设** |
| `Ch5 §F.1` 的 `quote_time` / `adjusted_flag` / `corporate_actions_ref` vs `schema.models.PriceSnapshot` | schema 里是 `published_at`/`occurred_at` + `adjustment_caliber_version` | `quote_caliber_from_snapshot` 作为**唯一映射点**（`published_at ?? occurred_at`；`adjustment_caliber_version` 同时驱动 `adjusted_flag` 与 `corporate_actions_ref`），映射集中在一处便于裁定后改 |
| `schema.models.RecommendationStatus` **无 `rechecking`** | `Ch5 §F.2`/B2 要求异动复检 | `daily_explain.enqueue_review` 返回 `status="rechecking"` 的 **`ReviewTicket` 对象**（不进 `RecommendationStatus` 枚举）；待裁定是否扩枚举 |

### ④-4 `schema.models.Benchmark` 缺 5 个字段落点 —— **不归本卡，已单列成卡**

`Ch5 §E.1`（表头逐字："字段（`benchmarks` **新增**）"）与 `§E.5` 把 5 项写成 **`benchmarks` 的行内平铺键**，而 `schema.models.Benchmark` 只有 `includes_non_listed_assets` / `non_listed_assets` / `sensitivity` 三个：

| `§E.1`/`§E.5` 要求 | `Benchmark` 有无字段 | 本流读取位置 |
|---|---|---|
| `includes_non_listed_assets` / `non_listed_assets` / `sensitivity` | **有** ✓ | 只读行内 |
| `holdings_disclosure_lag` | **无** | 行内**优先** → 回落 `coverage_profile` 内层 |
| `unverifiable_forecasts` | **无** | 同上 |
| `modeled_coverage` | **无** | 同上 |
| `unmodeled_parts` | **无** | 同上 |
| `claims_complete_forecast` | **无** | 同上 |

`coverage_profile: dict[str, Any]`（`models.py:1706`）是本项目对"设计给了键名、模型未封闭建模"的**既有开放 dict 约定**（同一约定见 `models.py:1077-1081` 对 `BusinessMechanism.cost_structure` 的说明）。只认行内会把**合规的** `coverage_profile` 写法误判成"整片缺字段"，只认内层会偏离设计字面 ⇒ `_coverage_value` **行内优先 + 内层回落**，3 条用例正反锁住（§② V-1b）。
**★ 主理人已明确：这 5 个 `Benchmark` 字段不属本卡** —— `schema` 的唯一写入者是 `ws-schema-expand`，**已由其单列成卡**。本流**不新增 schema 字段**（`schema/**` 禁改），**不臆造默认通过**（缺键 → 缺省值 + `NO_MODELED_COVERAGE` / `NO_NON_LISTED_ASSETS` note）；待 `ws-schema-expand` 落字段后，本流删掉另一路即可（映射集中在一处，改动面 = 1 个函数）。

### ④-5 模型侧未交付（本批次边界，非缺陷）

`Ch5 §5.3/§5.4` 的**假设生成**（候选假设组合 / 假设空间边界 / 替代解释产出）与**基准选取与价格抓取**属**模型侧、阶段②③**，本批次（确定性价格层）**不交付**。`step.py::make_price_guard_handler` 的 `incomplete_reason` 已**逐字点名**该缺口，并保证 `degraded=True`、**绝不报 ok 却什么都没做**。

### ④-6 真源为空导致的"真空成立"

真仓库 `implied_requirements` / `benchmarks` / `prices` / `derived/derived_values` **均为 0 行**，故 §B.1 多解、§B.5 回灌、§D.6 概率依据、§E.1 覆盖率、§F.1 口径五类判据在真源上**真空成立**。
**★ 但"规则绑定"判据在空样本下照常执行**（`rule_binding_checks: 2 / 3 / 1`、`rule_keys_required: 7`），并与真文件的实际取值比对 —— 这正是修订轮补上的：**别让"没有被检对象"把"代码与规则是否同源"也一并跳过**。
全部反例/对照均在**副本根**上以真实对象形态注入验证（V-1 / V-1c），**写入型探测只在副本上做**，真仓库 `facts/`、`derived/`、`rules/` 保持原状。

### ④-7 其余

- **不做**：建议生成（`scripts/decision/**`）、展示视图（`views/**`）、Skill 编排 —— 不属本流模块清单。
- **不做**：不改 `chain_steps.py`（共享文件），仅提供两种接线并留测试（§② V-5）。
- **不做**：不写 `rules/**`（0444 + SHA256 锁）—— 候选值全部写在测试夹具副本内。
- **宿主抖动如实登记**：同一套 168 例在本工作树内实测 **53.89s ~ 91.26s**（≈1.7×波动，宿主配额/删除监察所致，见 `CONVENTIONS.md` 对 `rmtree` 的实测）。超时取上限 300s 正是为了**让这种抖动不误报**。
- **`CONVENTIONS.md` 批次表已由主理人统一处置（本流不再动它）**：主理人裁定 ② ——"`CONVENTIONS.md` 批次表 **已由我统一处置，你不要动**"：他**删掉了"批次数"这一项**（"★ 刻意不写'批次数' —— 唯一真源是 `verify.py::BATCHES`"）并补上缺失的 `valuelayer` 行。
- **与同轮并入的 `scripts/valuelayer/_rules.py` 交叉核对（同一纪律的第二个实现，结论一致）**：该模块（13-A 价值层）把 `rules/{baseline,metric-sets}.yaml` 集中成**唯一读口**，走 `_cached_yaml`（P-02）、缺文件/缺键/值非法**响亮失败**、**不内置兜底默认值**——与本流 `solver`/`valuation`/`scenario_guard`/`daily_explain` 的读法**同构**（同一 `P-02` 读口 + 同类 note 口径）。
  该模块对 `tbd` 与「缺键」**刻意分开**（`tbd` = 管了但待拍板 ⇒ 不可核 + note；缺键 = 根本没管 ⇒ 响亮失败），本流在**结论层面**已等价：`load_*` 在缺键时回落**设计逐字值**并记 note，而 `check()` 的 `*-RULE-BINDING` 判据集**同时**把该键列为必需 ⇒ **门禁当场 exit 1**（§② V-1c 用例②实测）。**该差异已裁定**（主理人裁定 ③）：**保持现状，不统一到** `_rules.py` 的"读口即抛错"，改以 §1-4 的三条约束（设计逐字值 + `value_source`&note + 绑定断言）承担同一纪律；第四轮（§1-5 修 3）进一步把"缺子键"也纳入**门禁必红**，使两口径在**门禁层面**完全等价（差异只剩"单独调 `load_*` 时抛不抛"）。

### ④-8 第四轮登记（两条）

**（a）`value_source` 在"部分字段回落"时的语义 —— ★★ 主理人第五轮已裁定：采纳 (甲)。**
（**本条已闭合**，落地与证据见 §1-6 / §② V-1l。以下保留裁定前的登记原文，便于追溯。）

`value_source` 是**单个**取值域为 `{rules, design_default}` 的标志，却服务**多字段**结构
（`UnregisteredFallback{method_class, mark}`、`SolutionSetDisplay{default_count, max_count, must_show_multiple, selection, overflow}`、
`RecheckTrigger{阈值×2, keep_original_judgment_time}`）。**裁定前**口径（第三轮选的、并曾写进用例
`test_unregistered_fallback_partial_key_records_note` 的 docstring）是：**只要节存在 ⇒ `rules`**，
缺失的**子键**由 **note** 点名。第四轮实测确认它一致地等于"**子键缺 ⇒ 仍报 `rules`**"：

```text
[删 on_hit.keep_original_judgment_time] 加载成功 value_source=rules notes=("NO_ON_HIT_KEY: … 缺失 —— 取设计逐字回落值 True …",)
```

⇒ **风险**：只看 `value_source` 的下游（看板/其它门禁）会读成"这个结构整体已核"，而实际有字段来自设计回落。
**两个候选口径**：(甲) `value_source` 改为"**全部字段都来自文件**才叫 `rules`"，否则 `design_default`（信息由 note 保留）；
(乙) 保持现状（`rules` + 逐键 note）。

**★ 裁定结果**：主理人第五轮**采纳 (甲)**，理由 = *"标志的单位必须与它声称覆盖的单位一致"*
（该风险正是 `V-11` 类别轴 / `G-62` 不可区分）。落地见 **§1-6**（3 个 `load_*` 各一行 + **3 处必须同步动的连带面**），
证据见 **§② V-1l**（8 例反例 + **3 例反向对照**）。★ 裁定前的用例断言已按 (甲) **翻转**
（`test_unregistered_fallback_partial_key_records_note` / `test_trigger_missing_on_hit_key_records_note`），
并在 docstring 里写明**口径变更史**与"为何不是反复"（③-2 是实现口径、(甲) 是声明粒度）。

**（b）本轮 pytest 用例：已写、已逐条**执行**，但**未跑 `pytest` 命令**（与 §② V-1i/V-1j 同一条）。
正式路径 `verify.py --batch pricelayer` 待窗口关闭后复跑；届时在 §③ 补报**真**读数（不在此处写条数 —— 见 §② V-1i）。

### ④-9 修 7 / 修 8 带出的两条"行为收窄"（已处置，登记风险面）

**（a）`order_guard` 的 §B.1 判据从"数全部行"收窄为"只数 `feasible` 行" —— 收窄即会**多报**。**
依据是 `Ch5 §B.1`（"展示**解集**" = 使当前价格成立的那些解）+ 与 `solver.check` 的**同名判据口径必须一致**
（此前两处口径分裂：`solver` 只数 `feasible`，`order_guard` 数全部）。⇒ 收窄后，
"同解集里既有可行行又有不可行行"的**正确**数据现在会（正确地）被判为**单解集**而报警；
若某上游把"同一 `solution_set_id` 下混放不可行行"当作合法写法，那属于**上游与 `§B.1` 不一致**，不是本判据过严。
**风险面已用 note 显式暴露**（被排除的行数写进 note：缺键 / 不可行分别计数），避免"数少了但看不出为什么"。

**（b）"行缺 `solution_set_id` / `implied_id` ⇒ 违例"会让**存量脏数据**从"静默通过"变成"红"。**
依据：`schema.models.ImpliedRequirement` 这两个字段**均为必填**，且 `solver.check` 对同类行**本来就响亮报**
`IMPLIED-ROW-INCOMPLETE` ⇒ 这是**补齐口径分裂**，不是新增更严的标准。**未对存量真源做任何写入**；
若窗口关闭后正式批次出现本判据的红，应读作**真源缺字段**（上游 bug），而非本模块缺陷 ——
判据消息里已直接点名字段与"这些行无法进入黑名单/无法进入解集计数"的后果。

### ④-9补 本轮**未**触碰的边界（再声明，防误读）

- **`rules/**` 一字未改**（0444 + SHA256；`git diff --stat -- system/rules system/registry` 为空）。
- **未改 `CONVENTIONS.md`**（主理人裁定 ②：由他统一处置）。
- **未跑 `pytest` 命令**（`G-60` 排他窗口，主理人指令）；正式批次读数仍**待补**。
- **未做任何 branch 操作**（主理人指令："不要做任何 branch 操作"）；`git merge main` 是唯一例外且经其明示许可。
