# ws/ch2-rules · 批次 13-R 报告 —— 4 份规则文件的**内容转写**（候选）

- **分支**：`ws/ch2-rules`（基点 `main` @ `d74a829`）
- **工作树**：`/Users/gaza/Developer/InvestSigh/.worktrees/ws-ch2-rules`
- **任务书**：`system/reports/batch13_taskbook.md` **卡 13-R**
- **产出**：`system/registry/rule-candidates/` 下 4 个候选 YAML + 本报告
- **安装**：由主理人执行（`chmod -R u+w system/rules` → 复制 → `python system/scripts/ops/lock_rules.py` 重锁）

## 0. 一句话

设计**已写死**的 4 份规则内容已逐字转写为候选 YAML；**逐键对照表共 116 行**（每行都给出「取值 → 节号 + 原文片段」，
其中数行为多键合并书写）；
其中 **15 个键位**设计给了键但没给值 ⇒ 落 `tbd` + `basis`；**7 组**设计有语义但没给键名/没指派文件 ⇒ **未自创，单列在 §4.2**；
**1 处**改为指针（`scenario.yaml::scenario_consistency.param_ref = p05`）。

---

## 1. 改了什么（工作树内文件级 diff）

```
新增：system/registry/rule-candidates/metric-sets.yaml        （指标集注册表）
新增：system/registry/rule-candidates/baseline.yaml           （上限/阈值参数化）
新增：system/registry/rule-candidates/valuation-methods.yaml  （估值方法路由）
新增：system/registry/rule-candidates/scenario.yaml           （情景定义 + scenario_method_status）
新增：system/reports/ws_ch2_rules_report.md                   （本报告）
```

`system/rules/**` **零改动**（见 §3 证据 ④）。设计区（各章 `02_实现方案.md`、`00_交付施工图.md`、`00_待拍板项清单.md`）**只读未动**。

---

## 2. 逐键对照表

> 表列 = `键 → 取值 → 设计出处（节号 + 原文片段）`。**每一行都有节号与原文片段**，无"根据惯例"。
> 缩写：`04/02` = `04_公司价值研究与深度标准/02_实现方案.md`；`05/02` = `05_价格与市场预期研究/02_实现方案.md`；
> `施工图` = `00_交付施工图.md`；`清单` = `00_待拍板项清单.md`（v2 · 2026-09-15，D-03 已确认）。

### 2.1 `metric-sets.yaml`（安装目标 `rules/metric-sets.yaml`）

| 键 | 取值 | 设计出处（节号 + 原文片段） |
|---|---|---|
| `spec_anchor` | `"Ch4 §C.1"` | `04/02` L123 标题「### C.1 可配置的指标集定义（`rules/metric-sets.yaml`）」；`04/02` L21「新配置 \| `rules/metric-sets.yaml`（指标集注册表）…\| 挂 `rules/`」 |
| `routing.key` | `model_class` | `04/02` L142「`business.model_class` 为路由键」 |
| `routing.binding_field` | `business.metric_set_id` | `04/02` L142「`businesses.metric_set_id` 绑定」 |
| `routing.metric_owner_field` | `business_id` | `04/02` L143「**`business_id → indicator_set` 绑定**：指标**挂在 `business_id`（非 `company_id`）**」 |
| `routing.fallback_metric_set_id` | `MS-GENERIC` | `04/02` L164「未注册类型 \| 归入 `MS-GENERIC` 并显式标注 `unregistered_model_class=true` \| 否」 |
| `routing.fallback_marks_unregistered_model_class` | `true` | 同上（「**并显式标注** `unregistered_model_class=true`」） |
| `metric_sets[0].metric_set_id` | `MS-HW-6STAGE` | `04/02` L126「`- metric_set_id: MS-HW-6STAGE`」；L485「`rules/metric-sets.yaml:MS-HW-6STAGE` \| 硬件六段呈现且不跳级」 |
| `metric_sets[0].model_class` | `hardware` | `04/02` L127「`  model_class: hardware`」 |
| `metric_sets[0].currency` | `n/a` | `04/02` L128「`  currency: n/a`」 |
| `metric_sets[0].stages` | `[order, production_schedule, shipment, acceptance, revenue, collection]` | `04/02` L129「`  stages: [order, production_schedule, shipment, acceptance, revenue, collection]`」（6 段，与 `MS-HW-6STAGE` 的 `6` 一致） |
| `metric_sets[0].metrics` | **`tbd`** | `04/02` L130「`  metrics: [{name, unit, source_class, linked_account}]`」——只给 **item 字段模板**，未给具体指标清单（见下 `metric_item_fields`） |
| `metric_sets[0].linked_accounts` | `[revenue, cogs, capex, inventory, receivables]` | `04/02` L131「`  linked_accounts: [revenue, cogs, capex, inventory, receivables, ...]`」——尾部 `...` = 集合开放，**只落原文点名的 5 项** |
| `metric_sets[1].metric_set_id` | `MS-CLOUD-5STAGE` | `04/02` L132；L486「云五段呈现」 |
| `metric_sets[1].model_class` | `cloud` | `04/02` L133「`  model_class: cloud`」 |
| `metric_sets[1].stages` | `[contract, energized, online, utilization, billing]` | `04/02` L134「`  stages: [contract, energized, online, utilization, billing]`」（5 段） |
| `metric_sets[1].currency` / `.metrics` / `.linked_accounts` | **各 `tbd`** | `04/02` L135「`  ...`」——该条以 `...` 省略，**设计未给值**（结构同 `MS-HW-6STAGE`） |
| `metric_sets[2].metric_set_id` | `MS-SW-5STAGE` | `04/02` L136；L487「软件五段呈现」 |
| `metric_sets[2].model_class` | `software` | `04/02` L137「`  model_class: software`」 |
| `metric_sets[2].stages` | `[usage, paid, renewal, retention, upsell]` | `04/02` L138「`  stages: [usage, paid, renewal, retention, upsell]`」（5 段） |
| `metric_sets[2].currency` / `.metrics` / `.linked_accounts` | **各 `tbd`** | `04/02` L139「`  ...`」——同上，设计未给值 |
| `metric_sets[3].metric_set_id` | `MS-GENERIC` | `04/02` L164（§C.3 表右列）逐字 |
| `metric_sets[3].model_class` | `generic` | `04/02` L164「归入 `MS-GENERIC`」（`generic` 为同名概念的 token；本条目由该行逐字转写） |
| `metric_sets[3].currency/.stages/.metrics/.linked_accounts` | **各 `tbd`** | `04/02` L164 只给"归入 + 标注"，**未给字段值** |
| `metric_item_fields` | `[name, unit, source_class, linked_account]` | `04/02` L130 原文 item 模板逐字 |
| `binding_guard.guard` | `scripts/valuelayer/route_guard.py` | `04/02` L148「`# scripts/valuelayer/route_guard.py`」 |
| `binding_guard.entry` | `validate_binding` | `04/02` L149「`def validate_binding(business, metric_set):`」 |
| `binding_guard.rule_model_class_mismatch` | `raise MetricSetMismatch` | `04/02` L150-151「`if business.model_class != metric_set.model_class:  # ← 外键一致性` / `raise MetricSetMismatch(business.business_id, metric_set.metric_set_id)`」 |
| `binding_guard.rule_metric_owner_must_be_own_business` | `true` | `04/02` L153「`for m in metric_set.metrics: assert m.owner_business_id == business.business_id`」 |
| `binding_guard.cross_business_reference` | `forbidden` | `04/02` L152「# 分部财务独立：指标只能写本业务分部科目，禁止跨业务引用」 |
| `binding_guard.rollup` | `scripts/valuelayer/rollup.py` | `04/02` L157「…（`scripts/valuelayer/rollup.py` 只做分部→公司层加总，不做跨业务语义混用）」 |
| `extension_policy.new_model_class_requires_code_change` | `false` | `04/02` L163「新增第 4 类（广告/代工/游戏内购…）\| **只改 `rules/metric-sets.yaml`**（注册新 `metric_set` + 路由）\| **否**（注册表驱动）」 |
| `extension_policy.unregistered_type_action` | `"归入 `MS-GENERIC` 并显式标注 `unregistered_model_class=true`"` | `04/02` L164 逐字（见上） |
| `conversion_chain_generic_stages` | `[获取, 交付, 使用, 变现]` | `04/02` L108「**转化链路分段模型**（通用四段，按商业模式实例化）：**获取 → 交付 → 使用 → 变现**。」（**四段名逐字照抄，未翻译**；英文 token 只在 §C.1 的三类 `stages` 里） |
| `conversion_chain_per_model_class.hardware` | `"订单→排产/出货→验收→收入/回款"` | `04/02` L109「- 硬件：订单→排产/出货→验收→收入/回款」 |
| `conversion_chain_per_model_class.cloud` | `"签约→通电/上线→利用率→收费"` | `04/02` L110 逐字 |
| `conversion_chain_per_model_class.software` | `"使用→付费→续约/留存→增购"` | `04/02` L111 逐字 |
| `segment_evidence.field` | `segment.pending_evidence` | `04/02` L113「每段必有 `evidence`（`claim_id[]`，接第六章），否则该段标"待补证"（`segment.pending_evidence=true`）。」（**字段名为设计逐字**） |
| `segment_evidence.evidence_field` | `segment.evidence` | 同上「每段必有 `evidence`（`claim_id[]`）」 |
| `segment_evidence.blocks_business_modeling` | `false` | `04/02` L117「`evidence` 空 → 标 `pending_evidence`，展示为"待补证"，**不阻止**业务建模但**阻止**该段进入财务连接（C）。」**← 键名为转写（设计此处为行文）** |
| `segment_evidence.blocks_financial_link` | `true` | 同上「但**阻止**该段进入财务连接（C）」**← 键名为转写** |
| `financial_link.field` | `driver.financial_link` | `04/02` L168「落 `facts/drivers.jsonl` 的 `financial_link`：」 |
| `financial_link.accounts` | `[revenue_segment, gross_margin, opex, capex, working_capital]` | `04/02` L172「`  accounts: [revenue_segment, gross_margin, opex, capex, working_capital, ...],`」（尾部 `...` = 开放，只落 5 项） |
| `financial_link.per_share_metric` | `[eps, fcf_per_share, value_per_share]` | `04/02` L173「`  per_share_metric: eps \| fcf_per_share \| value_per_share,`」 |
| `financial_link.formula_ref` | `"<DerivedValue ref>"` | `04/02` L174「`  formula_ref: <DerivedValue ref>        # 走 scripts/compute/`」 |
| `financial_link.cross_section_consistency_checker` | `scripts/valuelayer/completeness.py` | `04/02` L177「**跨节引用一致性**由 G 的形式校验器检查（驱动必须出现在财务连接里）」；G 的校验器路径见 L361「`# scripts/valuelayer/completeness.py`」 |

### 2.2 `baseline.yaml`（安装目标 `rules/baseline.yaml`）

| 键 | 取值 | 设计出处（节号 + 原文片段） |
|---|---|---|
| `spec_anchor` | `"Ch4 §D.2 / §B.2 / §G.2 / §G.4"` | `施工图` L124「配置 \| `rules/baseline.yaml` \| 上限/阈值参数化（`max_primary_drivers_per_business` / `min_nonnull_rate`）\| Ch4 §B/§G」；★ **该值的设计原文实际在 §D.2**（见下行），故按原文锚定并把 §B/§G 一并列入 |
| `thresholds.max_primary_drivers_per_business` | `5` | `04/02` L203「上限 \| `rules/baseline.yaml: max_primary_drivers_per_business`（**默认 5，可配**）」；`04/02` L562（§J 表 J2）「关键驱动上限默认值 \| 3 / 5 \| **5**（可配），超限分级」；`清单` B6「关键驱动上限默认值 \| **5**（可配，超限分级）〔原建议〕」 |
| `thresholds.min_nonnull_rate` | `0.9` | `04/02` L355 表格「必填字段非空率 ≥ 阈值」＋ L364（§G.2 代码）「`nonnull_rate(baseline) >= cfg.min_nonnull_rate,`」；`清单` B5「形式完备性最低阈值 \| **必填字段非空率 ≥ 90%**；**每条关键主张 ≥ 1 处原文定位**〔新给〕」（D-03 已确认） |
| `thresholds.min_locator_count` | `1` | `04/02` L365「`has_locator(baseline) >= 1,          # 含原始材料定位（N9.1-11）`」＋ L356 表格「≥1 原始材料定位（locator）」；`清单` B5「每条关键主张 ≥ 1 处原文定位」 |
| `thresholds.min_derivation_count` | `1` | `04/02` L366「`has_derivation(baseline) >= 1,       # 含推导（N9.2-02）`」＋ L357「≥1 推导（公式 + 操作数）」 |
| `thresholds.min_fields_per_section` | **`tbd`** | `04/02` L354 表格「六项 section 非空且**达最小字段数**」＋ L363「`sections_nonempty(baseline, cfg)`」——**具体数设计未给**；`04/02` L563（J3）「形式完备性最低阈值 \| 非空率/定位数/推导数 \| 占位 + 参数化 `rules/baseline.yaml`」 |
| `driver_overflow_policy.reject_direct_insert` | `true` | `04/02` L204「超限处理 \| 校验器**拒绝直接入库**；须先分级：…」 |
| `driver_overflow_policy.required_tiering` | `[primary_drivers, secondary_watchlist]` | `04/02` L204「须先分级：`primary_drivers(≤5)` + `secondary_watchlist`（或按 `importance_class` 取 top-N，其余归档）」 |
| `driver_overflow_policy.alternative` | `"或按 `importance_class` 取 top-N，其余归档"` | `04/02` L204 括号内逐字 |
| `driver_overflow_policy.validator_ref` | `validate_driver_count` | `04/02` L208「`def validate_driver_count(business, drivers, cfg):`」；L483（N4.1-05）「`rules/baseline.yaml:max_primary_drivers_per_business` + `validate_driver_count`」 |
| `driver_duration.mode_domain` | `[point, range]` | `04/02` L205「可持续时长 \| `duration.mode ∈ {point, range}`；…」；L189「`duration: {mode: point\|range, value: "1-3Y"}`」 |
| `driver_duration.undisclosed_policy` | `"用 `mode=range` + 定性标注（**不给伪精确点值**）"` | `04/02` L205「未披露用 `mode=range` + 定性标注（**不给伪精确点值**）」 |
| `driver_duration.validator_ref` | `validate_driver_count` | `04/02` L208-211（同一校验器代码块） |
| `form_completeness.entry` | `form_complete` | `04/02` L362「`def form_complete(baseline, cfg) -> CheckResult:`」 |
| `form_completeness.guard` | `scripts/valuelayer/completeness.py` | `04/02` L361「`# scripts/valuelayer/completeness.py`」 |
| `form_completeness.sections` | `["①业务与产业位置","②增长驱动","③增长确定性","④护城河","⑤财务与估值","⑥价格与行动"]` | `04/02` L341-348（§G.1 表第一列逐字：① 业务与产业位置 / ② 增长驱动 / ③ 增长确定性 / ④ 护城河 / ⑤ 财务与估值 / ⑥ 价格与行动）；L354「六项 section 非空且达最小字段数」 |
| `form_completeness.require_locator_at_least` | `1` | `04/02` L365「`has_locator(baseline) >= 1`」 |
| `form_completeness.require_derivation_at_least` | `1` | `04/02` L366「`has_derivation(baseline) >= 1`」 |
| `form_completeness.require_cross_section_consistent` | `true` | `04/02` L367「`cross_section_consistent(baseline)`」＋ L358「跨节引用一致（驱动出现在财务连接里）」 |
| `form_completeness.failed_items_reported` | `true` | `04/02` L368「`return CheckResult(passed=all(checks), failed=[...])   # 形式上拦截空标题`」 |
| `required_extra_fields_by_profitability.unprofitable` | `[business_model_note, path_to_profitability, cash_runway, funding_need, unit_economics]` | `04/02` L380「未盈利 \| `business_model_note`、`path_to_profitability`（里程碑）、`cash_runway`、`funding_need`、`unit_economics`」 |
| `required_extra_fields_by_profitability.profitable` | `[margin_persistence, fcf_persistence, reinvestment_return, share_dilution_impact]` | `04/02` L381「盈利 \| `margin_persistence`、`fcf_persistence`、`reinvestment_return`、`share_dilution_impact`」 |
| （分支键）`is_profitable` | — | `04/02` L376 表头「公司类型」＋ L383「校验器按 `is_profitable` 分支要求对应必填项非空（N4.2-04/05）」 |
| `segment_evidence.field` | `segment.pending_evidence` | `04/02` L113 逐字（同 §2.1） |
| `segment_evidence.blocks_business_modeling` | `false` | `04/02` L117「**不阻止**业务建模」**← 键名为转写** |
| `segment_evidence.blocks_financial_link` | `true` | `04/02` L117「但**阻止**该段进入财务连接（C）」**← 键名为转写** |

### 2.3 `valuation-methods.yaml`（安装目标 `rules/valuation-methods.yaml`）

| 键 | 取值 | 设计出处（节号 + 原文片段） |
|---|---|---|
| `spec_anchor` | `"Ch5 §D.1"` | `05/02` L149 标题「### D.1 估值方法按商业模式路由」 |
| `method_routing.hardware` | `["正常化利润","含再投资现金流","分部估值","同行比较"]` | `05/02` L155「hardware \| 正常化利润 / 含再投资现金流 / 分部估值 / 同行比较」 |
| `method_routing.cloud` | `["含再投资现金流（订阅/用量）","分部"]` | `05/02` L156「cloud \| 含再投资现金流（订阅/用量） + 分部」 |
| `method_routing.software` | `["正常化利润","现金流","留存指标"]` | `05/02` L157「software \| 正常化利润 / 现金流 + 留存指标」 |
| `method_routing.etf` | `["简化底稿"]` | `05/02` L158「**ETF（基准）** \| 简化底稿（E）」 |
| `registry_driven` | `true` | `05/02` L160「方法注册表驱动；未注册类型归入 generic 并标注。」 |
| `unregistered_fallback.method_class` | `generic` | `05/02` L160「未注册类型归入 generic」 |
| `unregistered_fallback.mark` | `unregistered` | `05/02` L160「并标注」 |
| `assumption_grid.growth_assumption` | `"±1 个百分点"` | `05/02` L459（J2）「每类假设离散粒度 \| 待定 \| 参数化 `rules/valuation-methods.yaml`」＋ `清单` B13「**增长率 ±1 个百分点 / 利润率 ±0.5 / 折现率 ±0.5**；参数化 `rules/valuation-methods.yaml`〔新给〕」（D-03 已确认） |
| `assumption_grid.margin_assumption` | `"±0.5"` | 同上 `清单` B13「利润率 ±0.5」（**原文未标单位 ⇒ 照抄不换算**） |
| `assumption_grid.risk_assumption` | `"±0.5"` | 同上 `清单` B13「折现率 ±0.5」；字段名取自 `05/02` L101「风险 k \| `risk_assumption` \| WACC / 折现率」 |
| `assumption_grid.reinvestment_assumption` | **`tbd`** | `清单` B13 只列 增长率/利润率/折现率 三项，**未给再投资粒度**；`05/02` L100「再投资 r \| `reinvestment_assumption`」只给字段名 |
| `assumption_grid.duration_assumption` | **`tbd`** | 同上：`清单` B13 未给持续时间粒度；`05/02` L102「持续时间 T \| `duration_assumption`」只给字段名 |
| `assumption_grid.grid_search_upper_bound` | **`tbd`** | `05/02` L438「限制每类假设的离散粒度 + **网格搜索上界（`rules/valuation-methods.yaml`）**」——**只给控制手段，未给数值** |
| `assumption_grid.solver_ref` | `scripts/pricelayer/solver.py` | `05/02` L91「求解 \| **程序** \| 固定 4 类解第 5 类；…迭代找可行解集（`scripts/pricelayer/solver.py`）」 |
| `valuation_compute.guard` | `scripts/pricelayer/valuation.py` | `05/02` L177「`# scripts/pricelayer/valuation.py（可测）`」 |
| `valuation_compute.entry` | `compute_valuation` | `05/02` L178「`def compute_valuation(baseline_version, params, *, compute_time):`」 |
| `valuation_compute.order_constraint` | `"baseline_version.system_time.analyzed_at < compute_time"` | `05/02` L179-180「`assert baseline_version.system_time.analyzed_at < compute_time, \` / `"估值计算时间必须晚于 baseline 版本时间（禁止倒填）"`」 |
| `valuation_compute.method_version_field` | `method_version` | `05/02` L172「每个 price range → formula + operands + **method_version** + share_count + compute_date（N5.3-02 / N9.2-02）」 |

### 2.4 `scenario.yaml`（安装目标 `rules/scenario.yaml`）

| 键 | 取值 | 设计出处（节号 + 原文片段） |
|---|---|---|
| `spec_anchor` | `"Ch5 §E.3 / §E.4"` | `05/02` L242 标题「### E.3 情景口径一致性检查（可直接写单测）」；L253「### E.4 `scenario_method_status = pending` 的落地」 |
| `scenario_tags` | `[bear, neutral, bull, custom]` | `05/02` L461（J4）「情景标签体系 \| 枚举 \| 定义 `{bear, neutral, bull, custom}`，首版仅用一致标签」 |
| `first_version_tag_policy` | `"仅用一致标签"` | `05/02` L461 逐字 |
| `scenario_consistency.param_ref` | **`p05`**（★ 指针，不抄值） | `rules/freeze.yaml::freeze_params[p05]`：`same_period_same_scenario_as_benchmark: true` / `method_versioning: required`；`Ch11 §D.2`「参数值**唯一真源 = `rules/freeze.yaml`**」 |
| `scenario_consistency.guard` | `scripts/pricelayer/scenario_guard.py` | `05/02` L245「`# scripts/pricelayer/scenario_guard.py（可测）`」；`施工图` L135「配置/脚本 \| `rules/scenario.yaml` + `scripts/pricelayer/scenario_guard.py`」 |
| `scenario_consistency.entry` | `assert_scenario_match` | `05/02` L246「`def assert_scenario_match(stock, benchmark):`」 |
| `scenario_consistency.checked_fields` | `[stock.scenario_tag, benchmark.scenario_tag]` | `05/02` L247「`if stock.scenario_tag != benchmark.scenario_tag:`」 |
| `scenario_consistency.on_mismatch` | `raise ScenarioMismatch` | `05/02` L248「`raise ScenarioMismatch(stock.scenario_tag, benchmark.scenario_tag)  # 拒绝生成相对判断`」 |
| `scenario_consistency.downstream_effect` | `"拒绝生成相对判断"` | `05/02` L248 行内注释逐字 |
| `scenario_consistency.forbidden_comparison` | `"个股乐观情景 vs 基准悲观情景"` | `05/02` L251「**不能比较个股乐观情景与基准悲观情景**（N5.4-08）」 |
| `scenario_method_status` | `pending` | `05/02` L256「`scenario_method_status: pending \| neutral \| probability_weighted    # 默认 pending`」；L258「首版方法（中性情景 vs 概率加权）未定 → **显式 `pending`，不静默默认**（N5.4-07 / C45-2）」 |
| `scenario_method_status_domain` | `[pending, neutral, probability_weighted]` | `05/02` L256 取值域逐字 |
| `scenario_method_blocking.when` | `"scenario_method_status == pending"` | `05/02` L259「**对下游（第七章收益比较）的阻塞行为**：`scenario_method_status=pending` 时，…」 |
| `scenario_method_blocking.effect` | `"assert_scenario_match 无法建立一致口径 → **阻塞相对判断生成**"` | `05/02` L259 逐字 |
| `scenario_method_blocking.downstream_output` | `"待判断（而非建议）"` | `05/02` L259「输出"待判断"而非建议」 |
| `scenario_method_blocking.required_field_at_downstream` | `benchmark_forecast` | `05/02` L259「第七章前置门收不到可用的 `benchmark_forecast`」 |
| `scenario_method_promotion.trigger` | `"样例确定后"` | `05/02` L260「**待定转正流程**：样例确定后 → 写 `rules/scenario.yaml`（版本化）」 |
| `scenario_method_promotion.requires_versioned_file` | `true` | `05/02` L260「（版本化）」；L462（J5）「样例通过 + `rules/scenario.yaml` 版本化」 |
| `scenario_method_promotion.target_status` | `[neutral, probability_weighted]` | `05/02` L260「`status` 转 `neutral`/`probability_weighted`」 |
| `scenario_method_promotion.record_method_version` | `true` | `05/02` L260「+ 记 `method_version`」（**该值面见 `p05` 指针**） |
| `probability.default` | `null` | `05/02` L205「**情景概率默认 `null`**（不默认 50/50）：`probability: null`；仅当有依据才填（N5.3-07 / C45-2）」 |
| `probability.required` | `false` | `05/02` L210「`assert "probability" not in required_fields                # 非必填`」 |
| `probability.must_be_null_50_50` | `false` | `05/02` L205「不默认 50/50」 |
| `probability.fill_condition` | `"须为 `DerivedValue` 且标注来源"` | `清单` B11「`probability` 何时才能填 \| 须为 `DerivedValue` 且标注来源；否则默认 `null`（**不是 50/50**）〔原建议〕」（来源 `05/02` J9，见 L466） |
| `range_expression.field` / `.keys` | `range` / `[low, high]` | `05/02` L204「区间用 `range{low, high}` 表达宽度（N5.3-06）」 |
| `range_expression.wrap_wide_range_as_precise_forecast` | `false` | `05/02` L204「**不把宽泛区间包装成精确预测**（N5.3-06）」 |

---

## 3. 测了什么（真实输出 + 退出码）

### ① 4 个候选 YAML 可解析（任务书指定命令）

```
$ python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]; print('YAML OK:', len(sys.argv)-1, 'files')" \
    system/registry/rule-candidates/metric-sets.yaml \
    system/registry/rule-candidates/baseline.yaml \
    system/registry/rule-candidates/valuation-methods.yaml \
    system/registry/rule-candidates/scenario.yaml
YAML OK: 4 files
exit=0
```

**过程如实记录**：首次运行**失败**（`yaml.parser.ParserError`，`valuation-methods.yaml` L56 双引号字符串内嵌 ASCII `"`）⇒ 改为
`『…』` 全角引号后复跑通过。这不是"一次就绿"，是修过的。

### ② 逐文件解析 + 顶层键清单（证明不是"解析器读到空文件也算过"）

```
$ for f in metric-sets baseline valuation-methods scenario; do
    python -c "import yaml,sys;d=yaml.safe_load(open(sys.argv[1]));print(sys.argv[1].split('/')[-1], type(d).__name__, sorted(d.keys()))" \
      system/registry/rule-candidates/$f.yaml
  done
metric-sets.yaml dict ['binding_guard', 'conversion_chain_generic_stages', 'conversion_chain_per_model_class',
                       'extension_policy', 'financial_link', 'install_note', 'install_target', 'metric_item_fields',
                       'metric_sets', 'routing', 'segment_evidence', 'spec_anchor', 'version']
baseline.yaml dict ['driver_duration', 'driver_overflow_policy', 'form_completeness', 'install_note', 'install_target',
                    'required_extra_fields_by_profitability', 'segment_evidence', 'spec_anchor', 'thresholds', 'version']
valuation-methods.yaml dict ['assumption_grid', 'install_note', 'install_target', 'method_routing', 'registry_driven',
                    'spec_anchor', 'unregistered_fallback', 'valuation_compute', 'version']
scenario.yaml dict ['first_version_tag_policy', 'install_note', 'install_target', 'probability', 'range_expression',
                    'scenario_consistency', 'scenario_method_blocking', 'scenario_method_promotion',
                    'scenario_method_status', 'scenario_method_status_domain', 'scenario_method_status_note',
                    'scenario_tags', 'spec_anchor', 'version']
exit=0
```

### ③ 关键值的存在性断言（防"写了但被 YAML 吞掉"）

```
$ python - <<'PY'
import yaml
r='system/registry/rule-candidates/'
ms=yaml.safe_load(open(r+'metric-sets.yaml'))
bl=yaml.safe_load(open(r+'baseline.yaml'))
vm=yaml.safe_load(open(r+'valuation-methods.yaml'))
sc=yaml.safe_load(open(r+'scenario.yaml'))
assert [m['metric_set_id'] for m in ms['metric_sets']]==['MS-HW-6STAGE','MS-CLOUD-5STAGE','MS-SW-5STAGE','MS-GENERIC']
assert len(ms['metric_sets'][0]['stages'])==6 and len(ms['metric_sets'][1]['stages'])==5 and len(ms['metric_sets'][2]['stages'])==5
assert bl['thresholds']['max_primary_drivers_per_business']==5
assert bl['thresholds']['min_nonnull_rate']==0.9
assert bl['thresholds']['min_locator_count']==1 and bl['thresholds']['min_derivation_count']==1
assert vm['method_routing']['etf']==['简化底稿']
assert vm['assumption_grid']['growth_assumption']=='±1 个百分点'
assert sc['scenario_method_status']=='pending'
assert sc['probability']['default'] is None
assert sc['scenario_consistency']['param_ref']=='p05'
print('关键值断言全过（4 文件 / 10 断言）')
PY
关键值断言全过（4 文件 / 10 断言）
exit=0
```

### ④ `rules/` 零改动（纪律 9/10）

```
$ git status --short system/rules
(无输出)
exit=0

$ ls -l system/rules | head -3          # bootstrap 后的 0444 位未被破坏
total 120
-r--r--r--@ 1 gaza  staff   8245 Sep 16 20:50 banned_tokens.yaml
-r--r--r--@ 1 gaza  staff   3985 Sep 16 20:50 benchmark.yaml
```

### ⑤ `rules_lock_guard`（bootstrap 已跑，纪律 9 不变量）

```
$ sh system/scripts/ops/bootstrap_worktree.sh
bootstrap_worktree: 已把 10 个 rules 文件置为 0444（内容零改动）
bootstrap_worktree: 自检 rules_lock_guard …
== rules_lock_guard.py ==
  scanned files_on_disk: 10
  scanned registered_files: 10
  note: 锁清单 locked_at = 2026-09-15T16:34:55+00:00
RESULT: PASS（0 violations）
bootstrap_worktree ✓ rules_lock_guard 通过（纪律 9 不变量已复原）
exit=0
```

### ⑥ `git status --short`（全部改动都在候选目录 + 报告）

```
$ git status --short          # 提交前
?? system/registry/rule-candidates/
?? system/reports/ws_ch2_rules_report.md

$ git status --short          # 提交后（工作区干净，口径见 ⑦）
(无输出)
```

### ⑦ `pre-commit` 全绿（**禁 `--no-verify`，实测**）

提交 `3e5bc27` 由 pre-commit 钩子放行（显式路径 `git add`，**未用 `git add -A`**）。钩子逐门输出：

```
pre-commit → append_only_guard           RESULT: PASS（0 violations）
pre-commit → rules_lock_guard            scanned files_on_disk: 10 / registered_files: 10
                                         RESULT: PASS（0 violations）   ← ★ rules/ 锁不变量未破
pre-commit → registry_schema_guard       RESULT: PASS（0 violations）
pre-commit → schema_sync_guard           scanned committed_defs: 84 / fresh_defs: 84
                                         RESULT: PASS（0 violations）
pre-commit → conflict_scan(L1-L5)        RESULT: PASS（0 violations）   ← 候选 YAML 未触禁词/双写
pre-commit → no_placeholder_guard        scanned files: 127   RESULT: PASS（0 violations）
pre-commit → injection_guard             scanned rules_files: 10 / on_disk: 10
                                         RESULT: PASS（0 violations）
pre-commit → verification_policy_guard   RESULT: PASS（0 violations）
pre-commit → shell_var_guard             RESULT: PASS（0 violations）
pre-commit → graph_integrity_guard       RESULT: PASS（0 violations）
pre-commit → criterion_effectiveness_guard  RESULT: PASS（0 violations）
pre-commit ✓ 全部门禁放行
commit-exit=0
[ws/ch2-rules 3e5bc27] feat(rules-candidates): 批次13-R 4 份规则文件逐字转写为可安装候选
 5 files changed, 718 insertions(+)
```

> `criterion_effectiveness_guard` 打印的 6 条 `criteria_not_implemented` / 2 条 `ineffective_entries`
> 是**既有登记**（本单未动判据），`RESULT: PASS（0 violations）`——如实贴上，**不当作"已验证"**（`G-03`）。

> **未跑**：`verify.py --batch <整目录>`（配额，任务书禁）。**未跑** `run_all_gates`（本单不新增测试目录、不动代码，
> 门禁项不变；如主理人要求，可在合并后随批次统一跑）。

---

## 4. `tbd` 项 与 "设计未给" 项（**分开列**）

### 4.1 `tbd` 项（**设计给了键位/字段名，但没给值**）—— 共 **15 个键位**

| 文件 | 键 | 为什么是 `tbd`（设计原文） |
|---|---|---|
| metric-sets | `metric_sets[0].metrics` | `04/02` §C.1 只给 item 字段模板 `{name, unit, source_class, linked_account}`，未给具体指标清单 |
| metric-sets | `MS-CLOUD-5STAGE.currency` / `.metrics` / `.linked_accounts` | `04/02` §C.1 该条以 `...` 省略（L135） |
| metric-sets | `MS-SW-5STAGE.currency` / `.metrics` / `.linked_accounts` | 同上（L139） |
| metric-sets | `MS-GENERIC.currency` / `.stages` / `.metrics` / `.linked_accounts` | `04/02` §C.3 只写"归入 + 标注"，未给字段值 |
| baseline | `thresholds.min_fields_per_section` | `04/02` §G.2「达最小字段数」无数值；§J3 说"占位 + 参数化"但占位值缺失 |
| valuation-methods | `assumption_grid.reinvestment_assumption` | `清单` B13 只给 增长率/利润率/折现率 三项粒度 |
| valuation-methods | `assumption_grid.duration_assumption` | 同上 |
| valuation-methods | `assumption_grid.grid_search_upper_bound` | `05/02` §I.2 只声明"网格搜索上界（`rules/valuation-methods.yaml`）"，未给数值 |
| scenario | （无） | 本文件全部键位均有设计值（含"默认 `pending`"与"默认 `null`"） |

> 每个 `tbd` 在 YAML 内都带同级 `basis`（说明"设计未给，待需求方拍板"），**没有一个数是我填的**。

### 4.2 "设计未给"项（**设计有语义/有值，但没给键名、也没指派文件**）—— **未自创，故未进 YAML**

> 这 7 组的共同点：设计**给了明确语义甚至明确数值**，但**没有**说它落在哪个 `rules/*.yaml`、也**没有**给出键名。
> 按任务书硬约束 2（"设计根本没这个键 ⇒ 不要加"），我**没有转写**，在此单列请主理人裁决是否补做。
> **注意区分**：它们不是"设计没写"，而是"设计写了但没给落位"——**若主理人要收，请指定文件与键名**，我按原文补。

| # | 内容（含设计已给的值） | 出处 | 设计未给什么 |
|---|---|---|---|
| N-1 | 增长质量分档 `growth_quality ∈ {high, medium, low}` + 四判定项（`ROIIC vs WACC`、现金转化率、营运资金变动、融资依赖）；`ROIIC < WACC → low` + `value_destructive_growth=true` | `04/02` L224 / L232-236 | 未指派到 `baseline.yaml` 或其他文件；未给参数键名 |
| N-2 | 收入增速 denylist 守卫（"收入增速不得作投资回报代理"） | `04/02` L236 / L567（J7「类型约束 + AST 检查（双保险）」） | 未指派文件；未给键名 |
| N-3 | 倒填检测四条规则（参数后改 / 临界凑值 / 无历史假设 / 版本倒序） | `05/02` L189-192（§D.4） | 未指派到 `valuation-methods.yaml`；四条规则无键名（实现面在 `scripts/pricelayer/order_guard.py`，L133 施工图） |
| N-4 | 三类输入分离 `input_source ∈ {fact, model_estimate, manual}` + `manual` 须留痕 + 冲突`unresolved` 不加权 | `05/02` L196-198（§D.5） | 未指派文件（代码侧已落 `schema/models.py::InputSource`） |
| N-5 | 解集展示上限 `N` = **默认展示 3 组，最多 5 组** | `05/02` L460（J3）；`清单` B18（**已给值**） | 未指派文件（`05/02` §I.2 只把"离散粒度 + 网格搜索上界"指派给 `valuation-methods.yaml`，**不含**本项） |
| N-6 | 反解数值方法 = **网格 + 单调剪枝**；未建模覆盖率阈值 = **已建模业务覆盖 ≥ 80%** | `05/02` L458（J1）/ L467（J10）；`清单` B4（**已给值**） | 未指派文件；未给键名 |
| N-7 | `value_state` 三字段枚举 + `moat_level` 枚举（`tbd` 归一） | `04/02` L392-396（§H.1） | 属 **schema 层**（代码侧已落），设计未说进哪个 `rules/*.yaml` |

### 4.3 11 项待冻结参数的**指针**（唯一真源 = `rules/freeze.yaml::freeze_params`，`Ch11 §D.2`）

**逐项核过 `p01`–`p11` 的 `param` 名**（`benchmark_id` / `first_batch_company_product_relations` /
`recommended_security_scope` / `recommendation_horizon` / `return_forecast_method` /
`negative_return_relative_lead_policy` / `run_schedule_and_latency_target` / `publish_and_review_policy` /
`public_data_and_budget` / `review_caliber` / `notification_and_sharing`）：

| 候选文件 | 与 11 项冻结参数的关系 |
|---|---|
| `metric-sets.yaml` | **无**（全为注册表 token 与校验器入口，不属任何 `freeze_param`） |
| `baseline.yaml` | **无**（`max_primary_drivers_per_business` / `min_nonnull_rate` / 定位数 / 推导数 / 必填增量 均非 11 项之一） |
| `valuation-methods.yaml` | **无**。★ 特意核过 **`p05 return_forecast_method`** —— 它是"**收益预测**方法"（`blocking_targets` 含 `Ch5 §C.1`，**不含 §D.1**），与本文件"**估值**方法路由"是两件事，故**不是** p05 的取值面，无指针 |
| `scenario.yaml` | **1 处指针** → `scenario_consistency.param_ref: p05`。理由：`05/02` §E.3/§E.4 要求的"个股与基准**同期间同情景**"与"记 `method_version`"正是 `freeze.yaml::p05` 的 `same_period_same_scenario_as_benchmark: true` / `method_versioning: required` ⇒ **只留指针，不复制值** |

---

## 5. 每条要求对应的证据

| 任务书要求 | 证据 |
|---|---|
| 4 个候选文件齐备 | `system/registry/rule-candidates/{metric-sets,baseline,valuation-methods,scenario}.yaml`（§1 diff） |
| YAML 可解析（贴 `yaml.safe_load` 实测） | §3 ①②③（含首次失败 + 修复过程，退出码 0） |
| 逐键对照表齐备，每行有节号 + 原文片段 | §2（**116 行**数据行，无"根据惯例"行；无出处的键**不写**） |
| `tbd` 项与"设计未给"项**分开列** | §4.1（**15 个 `tbd` 键位**）vs §4.2（**7 组"未给键名/未指派"**，未转写） |
| 与现有 `rules/*.yaml` **风格一致** | 头部注释照抄 `freeze.yaml` / `schedule.yaml` / `benchmark.yaml` / `scope.yaml` 的 `spec_anchor` + 单一真源纪律 + 只读说明三段式；字段命名沿用 `param_ref` / `guard` / `entry` / `spec_anchor` / `version` / 行尾中文注释 |
| 文件头注明 `spec_anchor` / `install_target` / `install_note` | 4 个文件均有这 3 个顶层键（§3 ② 的键清单可见） |
| 与 `freeze.yaml` 只指针不双写 | §4.3（`scenario.yaml` → `p05`；其余 3 文件经逐项核对**无** 11 项之一） |
| 绝不写 `system/rules/` | §3 ④⑤（`git status --short system/rules` 空 + `rules_lock_guard` PASS + 0444 位完好） |
| 报告四段式 | 本文 §1 改了什么 / §3 测了什么 / §5 每条要求证据 / §6 剩余不确定性 |
| 禁 `git add -A`；`pre-commit` 全绿（禁 `--no-verify`） | §3 ⑦（11 道门全 PASS + commit-exit=0；显式路径 `git add`，未用 `-A`） |
| 未跑 `verify.py --batch <目录>` | §3 末尾声明 |

---

## 6. 剩余不确定性与缺口

**A. 需要主理人/需求方裁决**

1. **`scenario_method_status` 是否其实是 `p05` 的取值面（§2.4 已标张力）**：`05/02` §E.4 与 §J5 说它"待样例转正"，
   而 `freeze.yaml::p05` 也说 `algorithm: tbd` / `resolved_at: delivery_stage_2` —— 两者**同属"样例校准后转正"家族**，
   但设计**没有**把 `scenario_method_status` 写成 p05 的键。我**照设计逐字**落 `pending`，**没有**擅自改成指针。
   若主理人判定它就是 p05，应改成 `param_ref: p05` + 删值（**这需要一次显式裁决**）。
2. **§4.2 的 7 组"设计有值但未指派落位"**（尤其 N-5 解集上限 3/5 组、N-6 反解方法与覆盖率 80% 阈值）：
   是否要收进这 4 个文件之一？**请指定文件与键名**，我按原文补；我未自创。
3. **`baseline.yaml` 的 `spec_anchor` 与任务书不一致**：任务书写"§B/§G"，但 `max_primary_drivers_per_business`
   的设计原文在 **`04/02 §D.2`**（§B 全节无任何阈值）。我按**设计原文**锚定并在 `spec_anchor` 里把
   `§D.2 / §B.2 / §G.2 / §G.4` 一并列出，请主理人核时以此为准。

**B. 已知张力（**不是我的卡能改的**，如实上报）**

4. **`business_type` vs `model_class` 命名**：`04/02 §C.1/§C.2` 行文用 `business.model_class`，而 §B.1 的 schema 块与
   `04_.../01_需求拆解.md §4` 用 `business_type`；代码侧 `schema/models.py::Business` 已取 `business_type`。
   我在 `metric-sets.yaml` **照 §C.1 逐字**用 `model_class`（指标集侧字段名），**没有新增第三个名字**，文件头已登记该张力。
5. **`tbd` 的两种语义**：本项目 `tbd` 同时用于"未冻结参数"与"设计未给值"。本次 12 个 `tbd` **全部是后者**
   （设计未给值），与 `freeze.yaml` 的 `freeze_status: tbd` **不是一回事** —— 已在每个 `tbd` 旁写 `basis` 区分。
6. **旁证不一致（不属本卡，供主理人留意）**：`清单` **A2** 写"交易成本 = **双边合计 20 个基点（0.2%）**"，
   而 `rules/freeze.yaml::p10` 的 `caliber_terms.transaction_cost` 仍是 `tbd`。两处对 `p10` 的值**口径不一致**
   （一个是"已确认"、一个是 `tbd`）—— 本卡 4 个文件都不含该参数，故未处理，仅登记。

**C. 覆盖边界（明确未做的事）**

7. 本卡**只转写内容**，**不做**：安装进 `rules/`、重锁、写校验器、写测试、接线。
   安装后需要有人核：`rules_lock_guard` 绿 + 消费方（`route_guard` / `completeness` / `valuation` / `scenario_guard`）
   真的从这 4 个文件读值（**当前代码里这 4 个消费方尚未建**，属 13-A / 13-B 卡的范围）。
8. 4 个候选文件**没有做 schema 校验器**（如"`stages` 数量必须与 `metric_set_id` 尾数一致"）——
   设计未要求，且属 13-A/13-B 的测试面。
