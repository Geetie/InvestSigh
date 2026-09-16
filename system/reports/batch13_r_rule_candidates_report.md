# 批次 13-R · 4 份规则文件候选转写报告

- **worktree**：`.worktrees/ws-ch13r-rules`　**分支**：`ws/ch13r-rule-candidates`　**基点**：`main = ef16a81`
- **交付提交**：`b2e269c`（`feat(rule-candidates): 批次13-R 转写 4 份规则文件候选`）
- **任务卡**：`system/reports/batch13_taskbook.md` 卡 **13-R**
- **边界**：**只写 `system/registry/rule-candidates/**` + 本报告**；**`system/rules/**` 零改动**（见 §2.5 实测）

---

## §1 改了什么

| 文件 | 行数 | 设计出处（逐字读） |
|---|---|---|
| `registry/rule-candidates/metric-sets.yaml` | 96 | `Ch4 §C.1`（指标集定义）/ `§C.2`（防串味约束）/ `§C.3`（扩展机制）/ `§C.4`（三层映射） |
| `registry/rule-candidates/baseline.yaml` | 144 | `Ch4 §B.2`（分段证据）/ `§D.1`（驱动字段）/ `§D.2`（上限+超限+时长）/ `§G.1~§G.4`；`Ch4 §J.2 J2` / `§J.3 J3` / `§J.4 J4` |
| `registry/rule-candidates/valuation-methods.yaml` | 120 | `Ch5 §D.1`（方法路由）/ `§D.5`（三类输入+冲突）/ `§I.2`（搜索空间控制）/ `§J1~§J3`；`00_待拍板项清单 B13`（已确认粒度） |
| `registry/rule-candidates/scenario.yaml` | 102 | `Ch5 §E.3`（一致性）/ `§E.4`（方法状态+转正）/ `§E.5`（覆盖率）/ `§D.6`（概率默认空）/ `§J4` / `§J5`；`00_待拍板项清单 B11` |

合计 **462 行新增**，**181 个叶子键**（机械清点，见 §4 附录）。

### §1.1 ★ 我做的三个**关键裁定**（都关乎"唯一真源"，必须留痕）

**(1) `probability` 的默认值 —— 我拒绝在 `scenario.yaml` 里复写它。**

设计在**两处**都说"情景概率默认 `null`"：`Ch5 §D.6`（"**情景概率默认 `null`**（不默认 50/50）"）与 `Ch5 §E.4` / `00_待拍板项清单 B11`（"否则默认 `null`（**不是 50/50**）"）。
**实测**：该默认值**已由 schema 强制** —— `schema/models.py::Valuation.probability` 的 `default` 就是 `None`：

```
$ python -c "… ; print(m.Valuation.model_fields['probability'].default)"
Valuation.probability: required=False default=None ann=decimal.Decimal | None
构造 Valuation(...) 后 probability = None
```

⇒ 若我在 `scenario.yaml` 再写一个 `probability_default: null`，**同一事实就有两个真源**（`G-06`）。
**处置**：`scenario.yaml::probability_rule` **只声明规则**（`must_not_default_to: 0.5` / `requires_derived_value` / `requires_source_annotation`），并用 `field_ref: baselines.valuation.probability` **指向 schema**，**不复写该值**。这沿用了既有房型约定（`rules/scope.yaml`："本文件只声明**结构与解耦不变量**，不复制该值（防双写漂移）"）。

**(2) 与 `rules/freeze.yaml` 的关系 —— 实测排除双真源，故**不**写 `param_ref` 指针。**

`Ch11 §D.2` 讲死"**参数值唯一真源 = `rules/freeze.yaml::freeze_param`**"，且 `rules/scope.yaml`（p03）/`rules/notification.yaml`（p11）都用 `param_ref` 指针指向它。我**实测**了 `freeze.yaml` 的 11 个参数名，确认**与本文件无一个重叠**：

```
$ grep -nE "^  - param_id|^    param:" system/rules/freeze.yaml
  p01 benchmark_id / p03 recommended_security_scope / p06 negative_return_relative_lead_policy
  p08 publish_and_review_policy / p10 review_caliber / p11 notification_and_sharing
  p02 first_batch_company_product_relations / p04 recommendation_horizon
  p05 return_forecast_method / p07 run_schedule_and_latency_target / p09 public_data_and_budget

$ grep -nE "min_nonnull_rate|max_primary_drivers|nonnull|driver" system/rules/freeze.yaml
（无输出）
```

⇒ 二者是**不同概念**（freeze = 待需求方拍板的口径/范围；本文件 = 已定的上限/阈值），
故 `baseline.yaml` **不写** `param_ref`（写了反而是假指针）。此判断已写进文件头注释。

**(3) 载荷**只放设计原文，我的注解一律进注释。**

任务卡约束 1 是"**设计未写的不得新增**"。我第一版草稿自创了 `linked_accounts_open` / `is_fallback` / `delivery_stage` 等键，**自查后全部删除**，改为注释承载注解 —— 因为它们一旦被安装进 `rules/` 就会变成"无设计依据的声明"。
（唯一例外：任务卡**明确要求**的 `basis` 字段，用于给 `tbd` 项写"建议来源"，故 `*_basis` 键是**卡片要求**而非自创。）

---

## §2 测了什么（真实命令 + 真实输出 + 退出码）

### §2.1 YAML 可解析（DoD 第 1 条）

**首轮实测直接抓出 3 处真错**（我有意先跑再交付）：

```
$ python -c "import yaml,pathlib; … yaml.safe_load(每份) …"
FAIL baseline.yaml              ParserError: … line 110, column 47:
   min_fields_per_section_basis: "Ch4 §G.2 人工表"六项 section 非空且达最小字段数"；具体数设计未给"
                                        ^
FAIL scenario.yaml              ParserError: … line 83, column 40  （同上成因）
FAIL valuation-methods.yaml     ParserError: … line 92, column 35  （同上成因）
OK   metric-sets.yaml           顶层键=['version', 'spec_anchor', 'routing', 'metric_sets']
```

**根因**：我在**双引号标量内部又用了 ASCII 双引号** ⇒ 字符串提前终止，YAML 报 `expected <block end>, but found '<scalar>'`。
共 **7 处**（`baseline` 1 / `valuation-methods` 4 / `scenario` 2），逐处把内层引号改为 `「」` 后复验：

```
$ python -c "…复验…"
OK   baseline.yaml              顶层键=['version', 'spec_anchor', 'limits', 'driver_tiering',
                                       'duration', 'segment_evidence', 'form_completeness',
                                       'required_field_increments']
OK   metric-sets.yaml           顶层键=['version', 'spec_anchor', 'routing', 'metric_sets']
OK   scenario.yaml              顶层键=['version', 'spec_anchor', 'scenario_tag', 'match_rule',
                                       'scenario_method_status', 'promotion', 'probability_rule',
                                       'unmodeled_coverage']
OK   valuation-methods.yaml     顶层键=['version', 'spec_anchor', 'routing', 'input_handling',
                                       'discretization', 'grid_search', 'solution_set', 'traceability']

解析通过 4/4
```

**并复述关键值，证明"能解析"不是唯一证据**（解析成功但读出来是错的，才是更坏的情况）：

```
metric_sets: {'MS-HW-6STAGE': ['order','production_schedule','shipment','acceptance','revenue','collection'],
              'MS-CLOUD-5STAGE': ['contract','energized','online','utilization','billing'],
              'MS-SW-5STAGE': ['usage','paid','renewal','retention','upsell'],
              'MS-GENERIC': 'tbd'}
baseline limits: {'max_primary_drivers_per_business': 5}
baseline sections depth: [1, 2, 3, 4, 5, 6]
baseline form_completeness tbd项: {'min_nonnull_rate': 'tbd', 'min_fields_per_section': 'tbd'}
baseline required incl: ['business_model_note','path_to_profitability','cash_runway','funding_need','unit_economics']
vm registry: {'hardware': ['normalized_earnings','reinvestment_cash_flow','segment_valuation','peer_comparison'],
              'cloud': ['reinvestment_cash_flow','segment_valuation'],
              'software': ['normalized_earnings','cash_flow','retention_metrics'],
              'etf': ['simplified_worksheet']}
vm discretization: {'growth_rate': {'step':1,'unit':'percentage_point'},
                    'margin': {'step':0.5,'unit':'tbd',…}, 'discount_rate': {'step':0.5,'unit':'tbd',…}}
scenario_tag: {'values': ['bear','neutral','bull','custom'], 'first_version_requires_consistent_label': True}
scenario_method_status: ['pending','neutral','probability_weighted'] default= pending
```

### §2.2 ★ 我实测了候选文件**是否真被门禁扫到**（避免"我以为被检查了"）

`conflict_scan.py::check_L3` 明确"扫描 `rules/**` 与 `registry/**` 的 `*.yaml|*.yml|*.json` **键名 / 标量值**"
（`Ch2 §B.4` 把后续章新引入的配置一并纳入被检目标）⇒ 我的 4 份**在安装前就受检**。这不是推断，而是算出来的：

```
rules/ yaml:         10
registry/ yaml+json: 11
  ├ 其中 rule-candidates: 4
  └ 改动前 registry 应为: 7
合计:                21
→ 与守卫报的 l3_config_files=21 比对          ← 完全相等
```

```
$ python scripts/checks/conflict_scan.py . --timing pre_commit
== conflict_scan.py（timing=pre_commit）==
  scanned l1_recommendation_field_count: 31
  scanned l2_py_files: 157
  scanned l2_token_count: 12
  scanned l3_config_files: 21          ← 含我的 4 份（10 rules + 7 原有 registry + 4 新增）
  scanned l3_self_exempt: 1
  scanned l3_token_count: 7
  scanned l4_gate_files: 5
  scanned l4_gate_objects_declared: 1
  scanned l5_view_configs: 0
  note: timing=pre_commit；layers=['L1', 'L2', 'L3', 'L4', 'L5']
  note: L3 自命中豁免（禁词唯一真源）: rules/banned_tokens.yaml
  note: L5_SKIPPED_NO_VIEW_CONFIG（`views/**` 三入口于阶段④ 交付）
RESULT: PASS（0 violations）
CONFLICT_EXIT=0
```

**L3 的 7 个禁词是** `min_excess_return` / `minimum_alpha` / `safety_margin` / `excess_threshold` / `confidence_threshold` / `min_confidence` / `confidence_gate`（`layers: [L2, L3]`）—— 我的文件**一个都没沾**。
⚠️ 另需说明：`weight` / `score` / `vote` 的 `scope` 是 **`decision_scope_only`**（仅 `scripts/decision/**`、`scripts/graph/**` 与 `classify_*`/`assert_*` 调用链），**不扫 `registry/**`** ⇒ 设计原词 `probability_weighted` 合法（但我在文件里仍避免使用裸 `weight`）。

### §2.3 反占位符门禁（`--fail-on warn`，即 warn 也算失败）

```
── no_placeholder_guard.py ──
  → exit=0  用时=1.33s
```

⚠️ 顺带实测出一条**写作约束**（对后续写 YAML 的人有用）：`no_placeholder_guard` 的
`DATA_PLACEHOLDER` 对**非 `.py`** 文件匹配 `待填写|待补充|占位符|PLACEHOLDER`。
YAML **值**里不能出现这些词（注释会被先剥掉，但我仍在值里规避）。
**`tbd` 不在禁词内**（`freeze.yaml`/`notification.yaml`/`scope.yaml` 已大量使用 `tbd` 并长期绿）
—— 这正是设计要求的"未定值写 `tbd`"能够落地的前提。

### §2.4 全门禁（24 项）

```
$ python scripts/ops/run_all_gates.py --timeout 30
  conflict_scan.py                  exit=0   1.10s
  append_only_guard.py              exit=0   0.48s
  rules_lock_guard.py               exit=0   0.25s
  registry_schema_guard.py          exit=0   0.60s
  schema_sync_guard.py              exit=0   0.53s
  assert_gate_input.py              exit=0   0.21s
  freeze_guard.py                   exit=0   0.30s
  launch_guard.py                   exit=0   0.17s
  module_denylist.py                exit=0   0.38s
  no_signal_day.py                  exit=0   0.19s
  no_placeholder_guard.py           exit=0   1.33s
  neutrality_check.py               exit=0   0.24s
  return_guard.py                   exit=0   0.25s
  anti_padding.py                   exit=0   0.34s
  gap_to_task.py                    exit=0   0.20s
  traceback.py                      exit=1   0.18s   ← 唯一红项
  pipeline.py                       exit=0   0.21s
  stage_gate.py --stage prep        exit=0   0.39s
  injection_guard.py                exit=0   0.32s
  verification_policy_guard.py      exit=0   0.19s
  shell_var_guard.py                exit=0   0.19s
  graph_integrity_guard.py          exit=0   0.50s
  locator_check.py                  exit=0   0.61s
  criterion_effectiveness_guard.py  exit=0   0.58s
  非零计数                          1
```

**23/24 绿**。唯一红项 `traceback.py` 是**基点既有**的真实数据问题
（`rec-nvda-001` 缺 `assumptions`/`computation`，`G1-03`），**不是本次引入** ——
该事实已在 `ws_schema_expand_report.md::G-2` 用"基点 `bc26933` 同一条命令逐字复现"证过，
我**没有**顺手改数据把它捂绿。

**另**：`registry_schema_guard` 的扫描域是 `registry/*.jsonl`（**非递归、只 `.jsonl`**，源码 `:108`）
⇒ 我的 `registry/rule-candidates/*.yaml` **不在其域内**，不会与"新增真源必须先登记模型"冲突。

### §2.5 ★ `rules/` 零改动（DoD 第 4 条）

```
$ git status --short system/rules
（空输出）

$ git status --short
?? system/registry/rule-candidates/

$ ls -l system/rules/ | head -4
-r--r--r--  1 gaza  staff   8245 banned_tokens.yaml
-r--r--r--  1 gaza  staff   3985 benchmark.yaml
-r--r--r--  1 gaza  staff   2863 data-sources.allowlist.yaml
```

**`rules/` 零改动，且 0444 只读位完好**（新 worktree 建好后我按 `system/scripts/ops/bootstrap_worktree.sh`
复原过一次 —— 因为 **git 只跟踪可执行位、不跟踪只读位**，`git worktree add` 检出的 `rules/*.yaml` 一律是 `0644`）。

### §2.6 无回归：唯一会数 `registry/` 文件的测试不受影响

```
$ grep -n "registry.*glob" tests/**
tests/test_ch11_invariants.py:99:  (SYSTEM_ROOT / "registry").glob("*.yaml")
```

该 glob **非递归** ⇒ 我的**子目录** `registry/rule-candidates/` 不被匹配，
`test_params_are_single_source_of_truth`（`I11-01` 指针唯一真源）不受影响。

---

## §3 每条 DoD → 证据对照

| 卡 13-R 的 DoD | 结论 | 证据 |
|---|---|---|
| 4 个候选文件齐备，YAML 可解析 | ✅ | §2.1：`4/4` `yaml.safe_load` 通过（**首轮 3 处真错被抓出并修掉**），并复述关键值 |
| 逐键对照表齐备 | ✅ | §4（181 个叶子键全覆盖） |
| `tbd` 项与"设计未给"项**分开列** | ✅ | §5 两张表分列，且每条 `tbd` 都带 `basis`（卡片要求） |
| 与现有 `rules/*.yaml` **风格一致** | ✅ | §3.1 逐项对照 |
| 报告四段式 | ✅ | §1 改了什么 / §2 测了什么 / §3 每条 DoD 证据 / §7 剩余不确定性与缺口 |
| `rules/` 零改动（贴 `git status --short system/rules`） | ✅ | §2.5：输出为空 + 权限 0444 完好 |
| **绝不写 `system/rules/`** | ✅ | §2.5 |
| 逐字转写、不得自创；设计没给 ⇒ `tbd` + `basis` | ✅ | §1.1(3)（自创键已自查删除）+ §5（`tbd` 与"设计未给"分列，**无一处编数**） |
| 文件头注明 `spec_anchor` / `install_target` / `install_note` | ✅ | 4 份文件头部"候选元信息"块逐条列出（**并注明安装时应删除该块**） |
| 若设计根本没写 ⇒ 如实标注"设计未给，需需求方拍板" | ✅ | §5 表 B（9 项）+ §6（译名 7 项） |

### §3.1 与既有 `rules/*.yaml` 的风格一致性（逐项对照）

| 房型要素 | 既有示例（`rules/scope.yaml` / `notification.yaml`） | 我的候选 |
|---|---|---|
| 头部首行 | `# rules/<name>.yaml —— <职责>（<锚点>）` | 同（`# rule-candidates/<name>.yaml —— <职责>（<锚点>）`） |
| `# 权威出处：` | `# 权威出处：\`Ch3 §B-17\`（…）/ \`Ch3 §E\`（…）` | 同（多条出处逐行列出） |
| `# ★ 单一真源纪律：` | "值的真源在 `rules/freeze.yaml::pXX`；本文件只声明…，不复制该值（防双写漂移）" | 同（`scenario.yaml` 用 `field_ref` 指向 schema；`valuation-methods.yaml` 指针指向 `scenario.yaml`） |
| `# 只读：0444 + SHA256。` | 有 | 同（并补注"安装后"） |
| `version: 1` | 有 | 同 |
| `spec_anchor: "ChX §Y"` | 有 | 同 |
| 分节注释横幅 | `# ── …（N3.2-03/05）────────` | 同 |
| 未定值 | `tbd` | 同 |
| `guard_ref: "scripts/…"` | `scope.yaml` / `notification.yaml` | 同（`scenario.yaml::match_rule.guard_ref`） |
| **差异（1 处，刻意）** | — | 我多一个"**候选元信息**"块（`spec_anchor`/`install_target`/`install_note`），因卡片要求"文件头注明"。**块内已写明"安装进 rules/ 时应删除本块"** ⇒ 安装后与既有房型**零差异** |

---

## §4 逐键对照表（键 → 取值 → 设计出处）

> 出处一律用**节号 + 原文片段**（禁绝对行号，卡片约束 1）。
> "原文片段"用 `「」` 包裹，`…` 表示省略。**181 个叶子键全覆盖**（机械清点后逐条归因）。

### §4.1 `metric-sets.yaml`（47 键）

| 键 | 取值 | 设计出处（节号 + 原文片段） |
|---|---|---|
| `version` / `spec_anchor` | `1` / `"Ch4 §C.1"` | 房型必备（`§C.1` 标题即"可配置的指标集定义（`rules/metric-sets.yaml`）"） |
| `routing.key` | `model_class` | `§C.1`「`businesses.metric_set_id` 绑定；**`business.model_class` 为路由键**」 |
| `routing.binding_field` | `metric_set_id` | `§C.1`「`businesses.metric_set_id` 绑定」 |
| `routing.fallback_metric_set_id` | `MS-GENERIC` | `§C.3`「未注册类型 ｜ 归入 `MS-GENERIC` 并显式标注…」 |
| `routing.fallback_flag_field` | `unregistered_model_class` | `§C.3`「…并显式标注 `unregistered_model_class=true`」 |
| `metric_sets[0].*` | `MS-HW-6STAGE` / `hardware` / `n/a` / 六段 | `§C.1` 逐字给出整条（`stages: [order, production_schedule, shipment, acceptance, revenue, collection]`、`currency: n/a`） |
| `metric_sets[0].metrics` | `tbd` | `§C.1` 只给形状 `metrics: [{name, unit, source_class, linked_account}]`，**未给任何条目** |
| `metric_sets[0].linked_accounts` | `[revenue, cogs, capex, inventory, receivables]` | `§C.1`「`linked_accounts: [revenue, cogs, capex, inventory, receivables, ...]`」——`...` 表**未穷举**，故只转写逐字给出的 5 项（**并已在注释标明不是全集**） |
| `metric_sets[1].*` | `MS-CLOUD-5STAGE` / `cloud` / 五段 | `§C.1`「`stages: [contract, energized, online, utilization, billing]`」 |
| `metric_sets[1].currency` / `.metrics` / `.linked_accounts` | `tbd` ×3 | `§C.1` 该段原文以 `...` 结尾 |
| `metric_sets[2].*` | `MS-SW-5STAGE` / `software` / 五段 | `§C.1`「`stages: [usage, paid, renewal, retention, upsell]`」 |
| `metric_sets[2].currency` / `.metrics` / `.linked_accounts` | `tbd` ×3 | 同上（原文 `...`） |
| `metric_sets[3].metric_set_id` | `MS-GENERIC` | `§C.3` 逐字 |
| `metric_sets[3]` 其余 5 键 | `tbd` ×5 | `§C.3` 只给 id 与标注字段，**未给**兜底集的 `model_class`/`currency`/`stages`/`metrics`/`linked_accounts` |

### §4.2 `baseline.yaml`（55 键）

| 键 | 取值 | 设计出处（节号 + 原文片段） |
|---|---|---|
| `limits.max_primary_drivers_per_business` | `5` | `§D.2`「上限 ｜ `rules/baseline.yaml: max_primary_drivers_per_business`（**默认 5**，可配）」＋`§J.2 J2`「3 / 5 ｜ **5**（可配），超限分级」 |
| `driver_tiering.tier_field` | `tier` | `§D.2` 伪码「`primary = [d for d in drivers if d.tier == "primary"]`」 |
| `driver_tiering.primary_value` | `primary` | 同上（`== "primary"`；`§D.2` 表「`primary_drivers(≤5)`」） |
| `driver_tiering.overflow_container` | `secondary_watchlist` | `§D.2`「须先分级：`primary_drivers(≤5)` + `secondary_watchlist`」 |
| `driver_tiering.overflow_action` | `reject_direct_insert` | `§D.2`「校验器**拒绝直接入库**」 |
| `driver_tiering.alternative_selection` | `importance_class_top_n` | `§D.2`「（或按 `importance_class` 取 top-N，其余归档）」 |
| `driver_tiering.importance_class_values` | `[high, medium, low]` | `§D.1`「`importance_class: high\|medium\|low`」 |
| `duration.mode_values` | `[point, range]` | `§D.2`「`duration.mode ∈ {point, range}`」 |
| `duration.undisclosed_mode` | `range` | `§D.2`「未披露用 `mode=range` + 定性标注（**不给伪精确点值**）」 |
| `duration.undisclosed_requires_qualitative_note` | `true` | 同上（"+ 定性标注"）；`§J.4 J4`「**区间 + 定性标注**，禁伪精确」 |
| `segment_evidence.evidence_field` | `evidence` | `§B.2`「每段 `evidence` 为该段**该业务**的主张引用」 |
| `segment_evidence.pending_flag_field` | `pending_evidence` | `§B.2`「`evidence` 空 → 标 `pending_evidence`」 |
| `segment_evidence.empty_blocks_modeling` | `false` | `§B.2`「**不阻止**业务建模」 |
| `segment_evidence.empty_blocks_financial_link` | `true` | `§B.2`「但**阻止**该段进入财务连接（C）」 |
| `form_completeness.sections[0]` | `depth: 1`, `fields: [business_refs]` | `§G.1①`「业务与产业位置 ｜ `business_refs[]` + `relations`（N9.1-06）」 |
| `form_completeness.sections[1]` | `depth: 2`, `fields: [driver_refs]` | `§G.1②`「增长驱动 ｜ `driver_refs[]`（含 financial_link、duration、cost_of_growth）」 |
| `form_completeness.sections[2]` | `depth: 3`, `fields: [realization_stage, timeline, confidence, dependencies]` | `§G.1③`「增长确定性 ｜ `drivers[].realization_stage/timeline/confidence` + `dependencies[]`」 |
| `form_completeness.sections[3]` | `depth: 4`, `fields: [moat]` | `§G.1④`「护城河 ｜ `moat[]`」 |
| `form_completeness.sections[4]` | `depth: 5`, `fields: [valuation_inputs, historical_numeric_claims]` | `§G.1⑤`「财务与估值 ｜ `valuation_inputs` + `historicals` + `DerivedValue` 引用」（`historicals` 为行文简称，schema 实名为 `historical_numeric_claims`；"`DerivedValue` 引用"**设计未给字段名**） |
| `form_completeness.sections[5]` | `depth: 6`, `fields: [expectation, implied, independent]` | `§G.1⑥`「价格与行动 ｜ 引用第五章三份判断 + 第七章建议」；字段名取自 `Ch5 §C.1` 表首列 |
| `form_completeness.min_nonnull_rate` / `_basis` | `tbd` / 出处说明 | `§G.2` 伪码「`nonnull_rate(baseline) >= cfg.min_nonnull_rate`」；`§J.3 J3`「**占位 + 参数化** `rules/baseline.yaml`」⇒ 值设计未给 |
| `form_completeness.min_fields_per_section` / `_basis` | `tbd` / 出处说明 | `§G.2` 人工表「六项 section 非空且达**最小字段数**」⇒ 数设计未给 |
| `form_completeness.min_locator_count` | `1` | `§G.2` 伪码「`has_locator(baseline) >= 1`」（**值设计已给**） |
| `form_completeness.min_derivation_count` | `1` | `§G.2` 伪码「`has_derivation(baseline) >= 1`」（**值设计已给**） |
| `form_completeness.cross_section_consistent` | `true` | `§G.2` 伪码「`cross_section_consistent(baseline)`」 |
| `form_completeness.cross_section_rule` | `driver 必须出现在 financial_link 里` | `§C.4` 末句「**跨节引用一致性**由 G 的形式校验器检查（**驱动必须出现在财务连接里**）」 |
| `required_field_increments.branch_field` | `is_profitable` | `§G.4` 末句「校验器按 `is_profitable` 分支要求对应必填项非空（N4.2-04/05）」 |
| `required_field_increments.is_profitable_false[0..4]` | `business_model_note` / `path_to_profitability` / `cash_runway` / `funding_need` / `unit_economics` | `§G.4`「未盈利 ｜ `business_model_note`、`path_to_profitability`（里程碑）、`cash_runway`、`funding_need`、`unit_economics`」 |
| `required_field_increments.is_profitable_true[0..3]` | `margin_persistence` / `fcf_persistence` / `reinvestment_return` / `share_dilution_impact` | `§G.4`「盈利 ｜ `margin_persistence`、`fcf_persistence`、`reinvestment_return`、`share_dilution_impact`」 |

**交叉验证（额外证据，非卡片要求但我做了）**：上表 22 个字段名**逐个**在 `schema/models.py` 里**确实存在**，包括容易踩的 `historical_numeric_claims`（而非 `historicals`）与 `is_profitable` 分支的两组必填项：

```
Baseline 字段（实测）：… business_refs / driver_refs / moat / valuation / valuation_inputs /
historical_numeric_claims / is_profitable / business_model_note / path_to_profitability /
cash_runway / funding_need / unit_economics / margin_persistence / fcf_persistence /
reinvestment_return / share_dilution_impact …
Driver 字段（实测）：… realization_stage / timeline / confidence / dependencies / importance_class …
```

### §4.3 `valuation-methods.yaml`（47 键）

| 键 | 取值 | 设计出处（节号 + 原文片段） |
|---|---|---|
| `routing.key` | `model_class` | `§D.1` 表头列「`model_class`」；正文「`method_class → business.model_class` 绑定」 |
| `routing.binding_field` | `method_class` | `§D.1` 表头列「`method_class`」 |
| `routing.fallback_method_class` | `generic` | `§D.1`「方法注册表驱动；**未注册类型归入 generic 并标注**」 |
| `routing.method_registry[0]` | `hardware` → 4 个方法 | `§D.1` 表「hardware ｜ 正常化利润 / 含再投资现金流 / 分部估值 / 同行比较」 |
| `routing.method_registry[1]` | `cloud` → 2 个方法 | `§D.1` 表「cloud ｜ 含再投资现金流（订阅/用量） + 分部」 |
| `routing.method_registry[2]` | `software` → 3 个方法 | `§D.1` 表「software ｜ 正常化利润 / 现金流 + 留存指标」 |
| `routing.method_registry[3]` | `etf` → 1 个方法 | `§D.1` 表「ETF（基准） ｜ 简化底稿（E）」 |
| `input_handling.input_source_values` | `[fact, model_estimate, manual]` | `§D.5`「`input_source ∈ {fact, model_estimate, manual}`」 |
| `input_handling.manual_requires_trace` | `[author, modified_at]` | `§D.5`「须留痕（`author` + `modified_at`）（N5.3-04）」 |
| `input_handling.conflict_handling.weighting` | `forbidden` | `§D.5`「**不用加权**（承第六章禁加权、C45-4）」 |
| `input_handling.conflict_handling.mode` | `keep_and_display_side_by_side` | `§D.5`「分别保留并**并列展示**」 |
| `input_handling.conflict_handling.status_token` | `unresolved` | `§D.5`「冲突时标 `conflict_status="unresolved"`」 |
| `discretization.growth_rate.step` / `.unit` | `1` / `percentage_point` | `00_待拍板项清单 B13`「**增长率 ±1 个百分点**」（单位原文即"个百分点"） |
| `discretization.margin.step` / `.unit` | `0.5` / `tbd` | B13「**利润率 ±0.5**」⇒ 数值给定，**单位设计未给**（tbd + basis） |
| `discretization.discount_rate.step` / `.unit` | `0.5` / `tbd` | B13「**折现率 ±0.5**」⇒ 同上 |
| `grid_search.method` | `grid_with_monotonic_pruning` | `§J1`「反解数值方法 ｜ … ｜ **网格 + 单调剪枝**（可单测、可控）」 |
| `grid_search.max_grid_upper_bound` / `_basis` | `tbd` / 出处说明 | `§I.2`「限制每类假设的离散粒度 + **网格搜索上界**（`rules/valuation-methods.yaml`）」⇒ 数值设计未给 |
| `solution_set.max_displayed` / `_basis` | `tbd` / 出处说明 | `§J3`「解集展示上限 N ｜ **待定**」；`§I.2`「`solution_set` 上限 N，超出折叠」 |
| `solution_set.overflow_action` | `fold_into_envelope` | `§I.2`「只保留**代表解 + 区间包络**…超出折叠」；`§J3`「上限 + 区间包络折叠」 |
| `traceability.required_fields` | `[formula, operands, method_version, share_count, compute_date]` | `§D.2`「每个 price range → formula + operands + method_version + share_count + compute_date」 |
| `traceability.method_version_example` | `val-v1` | `§D.2` 伪码「`method_version="val-v1"`」 |

### §4.4 `scenario.yaml`（32 键）

| 键 | 取值 | 设计出处（节号 + 原文片段） |
|---|---|---|
| `scenario_tag.values` | `[bear, neutral, bull, custom]` | `§J4`「情景标签体系 ｜ 枚举 ｜ 定义 `{bear, neutral, bull, custom}`」 |
| `scenario_tag.first_version_requires_consistent_label` | `true` | `§J4`「**首版仅用一致标签**」 |
| `match_rule.compare_field` | `scenario_tag` | `§E.3` 伪码「`if stock.scenario_tag != benchmark.scenario_tag:`」 |
| `match_rule.on_mismatch` | `reject_relative_judgment` | `§E.3`「`raise ScenarioMismatch(...)`  # **拒绝生成相对判断**」 |
| `match_rule.guard_ref` | `scripts/pricelayer/scenario_guard.py` | `§E.3` 代码块注释「`# scripts/pricelayer/scenario_guard.py（可测）`」 |
| `scenario_method_status.values` | `[pending, neutral, probability_weighted]` | `§E.4` 逐字「`scenario_method_status: pending \| neutral \| probability_weighted`」 |
| `scenario_method_status.default` | `pending` | `§E.4`「# 默认 pending」 |
| `scenario_method_status.must_be_explicit` | `true` | `§E.4`「**显式 `pending`，不静默默认**」 |
| `scenario_method_status.blocks_relative_judgment_when_pending` | `true` | `§E.4`「`assert_scenario_match` 无法建立一致口径 → **阻塞相对判断生成**」 |
| `promotion.versioned` | `true` | `§E.4`「写 `rules/scenario.yaml`（**版本化**）」；`§J5`「样例通过 + `rules/scenario.yaml` 版本化」 |
| `promotion.requires` | `[sample_approved]` | `§J5`「转正条件 ｜ 待样例 ｜ **样例通过**」；`§E.4`「样例确定后」 |
| `promotion.targets` | `[neutral, probability_weighted]` | `§E.4`「`status` 转 `neutral`/`probability_weighted`」 |
| `promotion.records_method_version` | `true` | `§E.4`「+ 记 `method_version`」 |
| `probability_rule.field_ref` | `baselines.valuation.probability` | `§D.6`「`probability: null`」＋ `Valuation.probability`（schema 真源，见 §1.1(1)） |
| `probability_rule.must_not_default_to` | `0.5` | `§D.6`「（**不默认 50/50**）」；`B11`「（**不是 50/50**）」 |
| `probability_rule.requires_derived_value` | `true` | `B11`「须为 `DerivedValue` 且标注来源」；`§J9`「须为 DerivedValue 且标注来源」 |
| `probability_rule.requires_source_annotation` | `true` | 同上 |
| `probability_rule.evidence_standard` / `_basis` | `tbd` / 出处说明 | `§J9`「`probability` 有依据才填的"依据"标准 ｜ **待定**」 |
| `unmodeled_coverage.field_ref` | `benchmarks.modeled_coverage` | `§E.5`「`benchmarks.modeled_coverage` + `unmodeled_parts[]`」 |
| `unmodeled_coverage.unmodeled_list_field` | `unmodeled_parts` | 同上 |
| `unmodeled_coverage.threshold` / `_basis` | `tbd` / 出处说明 | `§J10`「未建模覆盖率阈值 ｜ **待定** ｜ 参数化，低于阈值禁止称"完整预测"」 |
| `unmodeled_coverage.claim_complete_forecast_below_threshold` | `forbidden` | `§E.5`「`modeled_coverage < 1` 时**不得**声称"完成整个基金预测"（N5.4-05）」；`§J10` 同 |

---

## §5 `tbd` 项 与 "设计未给"项（**分列**，卡片要求）

### §5.1 表 A：`tbd`（设计**明示未定 / 只给形状未给值**）

| 文件 | 键 | `basis`（建议来源，卡片要求） |
|---|---|---|
| `metric-sets.yaml` | `metric_sets[0..3].metrics`（4 处） | `§C.1` 只给形状 `{name, unit, source_class, linked_account}`，未给条目 |
| `metric-sets.yaml` | `metric_sets[1..3].linked_accounts`（3 处） | `§C.1` 原文以 `...` 结尾（未穷举） |
| `metric-sets.yaml` | `metric_sets[1..2].currency` | `§C.1` 原文以 `...` 结尾 |
| `metric-sets.yaml` | `metric_sets[3].*`（5 键） | `§C.3` 只给 `MS-GENERIC` 与标注字段名 |
| `baseline.yaml` | `form_completeness.min_nonnull_rate` | `§G.2` 伪码 `cfg.min_nonnull_rate`；`§J.3 J3` 明示"占位 + 参数化" |
| `baseline.yaml` | `form_completeness.min_fields_per_section` | `§G.2` 人工表"达最小字段数"，数未给 |
| `valuation-methods.yaml` | `discretization.margin.unit` | `B13` 原文"利润率 ±0.5"**未标单位** |
| `valuation-methods.yaml` | `discretization.discount_rate.unit` | `B13` 原文"折现率 ±0.5"**未标单位** |
| `valuation-methods.yaml` | `grid_search.max_grid_upper_bound` | `§I.2` 提到"网格搜索上界"但未给数值 |
| `valuation-methods.yaml` | `solution_set.max_displayed` | `§J3` 明示"待定" |
| `scenario.yaml` | `probability_rule.evidence_standard` | `§J9` 明示"待定" |
| `scenario.yaml` | `unmodeled_coverage.threshold` | `§J10` 明示"待定" |

**共 15 处 `tbd`，每处都带 `*_basis` 说明"为什么是 tbd"**（不是我偷懒，是设计如此）。

### §5.2 表 B：**"设计根本没写"**（与表 A 不同 —— 这些是**结构性缺失**，我按约束 1 未填任何值）

| # | 缺什么 | 设计出处（说了什么 / 没说什么） | 影响 |
|---|---|---|---|
| B-1 | `MS-GENERIC` 兜底集的 `model_class` | `§C.3` 只说"归入 `MS-GENERIC` 并显式标注 `unregistered_model_class=true`"，**未给**兜底集自身的 `model_class` 取值 | 13-A `route_guard` 的兜底分支无法判"未注册"（无对照值） |
| B-2 | `metric.metrics[]` 的**条目形状以外的内容** | `§C.1` 给了形状，未给任何指标条目 | 指标集注册表**当前是空壳**（阶段② 只能跑路由，跑不了指标） |
| B-3 | `§C.1` 的 `metrics[].source_class` **取值域** | `§D.1` 给了 **drivers** 的 `source_class`（7 类 + `mixed`），但 **§C.1 未说 metrics 复用同一域** | 我在文件里**只做引用并在注释标"待确认"**，未复制枚举（防双真源）；**需需求方确认是否同域** |
| B-4 | `§G.1⑤` 的"`DerivedValue` 引用"**字段名** | `§G.1` 写"`valuation_inputs` + `historicals` + `DerivedValue` 引用"，前两者有字段名，第三项**没有** | 十三-A `completeness` 的第⑤节无法判定"是否有 DerivedValue 引用" |
| B-5 | `duration.mode=range` 时**定性标注的字段名** | `§D.2`「未披露用 `mode=range` + 定性标注」——**"定性标注"没有字段名** | 13-A 无法校验"给了定性标注" |
| B-6 | `overload` 归档（"其余归档"）的**落点对象** | `§D.2`「（或按 `importance_class` 取 top-N，**其余归档**）」——"归档"到哪里没说 | 13-A 超限分级后的落点待定 |
| B-7 | `conflict_status="unresolved"` 的**字段承载对象** | `§D.5` 给了取值，未说该字段挂在哪（`ValuationInputs`？`Baseline`？） | 13-B 需要落位 |
| B-8 | `scenario.yaml` 的 **`version` 语义**（"版本化"的粒度） | `§E.4`/`§J5` 只说"写 `rules/scenario.yaml`（版本化）"，**未说**版本号与 `method_version` 的关系 | 13-B 转正流程需口径 |
| B-9 | `promotion` 的"样例通过"**判据** | `§J5`「转正条件 ｜ 待样例 ｜ 样例通过」——**由谁判、按什么判**未写 | 转正流程无法自动化（只能人工） |

> **我为什么把这些单列**：任务卡说"设计根本没写 ⇒ 如实标注'设计未给，需需求方拍板'，**不要**从别处抄一个数来填空"。
> 上表 9 项**确实不是我能在 13-R 范围内解决的**（需要需求方拍板或后续批次实现），故只登记、不填值。

---

## §6 译名登记（**需需求方确认**）—— token 是英文，设计原词是中文

卡片约束 5 要求"枚举 token **英文小写 + 下划线**"，而 `Ch5 §D.1` 的**方法名是中文** ⇒ 必须译名。
**译名不是设计原文**，逐条登记（文件内每个 token 旁也已注明中文原词）：

| 设计原文（`Ch5 §D.1`） | 我的 token | 备注 |
|---|---|---|
| 正常化利润 | `normalized_earnings` | |
| 含再投资现金流 | `reinvestment_cash_flow` | `cloud` 行原文"含再投资现金流（订阅/用量）" |
| 分部估值 | `segment_valuation` | `cloud` 行原文简写为"分部" |
| 同行比较 | `peer_comparison` | |
| 现金流 | `cash_flow` | ⚠️ `software` 行的"现金流"与 `hardware` 行的"含再投资现金流"**是否同一方法？** 设计分作两个词且 `software` 行不带"含再投资"限定 ⇒ 我按**两个 token** 转写，**不自作合并** |
| 留存指标 | `retention_metrics` | |
| 简化底稿 | `simplified_worksheet` | `ETF（基准）` 行"简化底稿（E）" |
| `ETF（基准）`（`model_class` 列） | `etf` | 括号里的"（基准）"是中文限定词，token 化时去掉了 —— **若需求方要求保留语义，请给新 token** |
| 个百分点（`B13` "±1 个百分点"） | `percentage_point` | 单位 token |
| 拒绝直接入库（`§D.2`） | `reject_direct_insert` | 行为 token |
| 区间包络折叠（`§I.2`/`§J3`） | `fold_into_envelope` | 行为 token |
| 网格 + 单调剪枝（`§J1`） | `grid_with_monotonic_pruning` | 方法 token |

> **处置**：这些如果需求方给出别的英文名，**只改 `rule-candidates/*.yaml` 即可**（配置驱动，不改代码）——
> 这正是这些文件存在的意义。**我不认为译名可以自己拍板**，故在此登记。

---

## §7 剩余不确定性与缺口（**如实登记，未掩盖**）

### G-13R-1 ★★ 设计声明的 3 个 `baselines.valuation` 字段**在 schema 中不存在** ⇒ 会卡住 13-B

`Ch5 §0 表`逐字：`baselines.valuation` 上新增「`independent_judgment`、`implied_ref`、`input_source`、`probability`、`scenario_tag`」；
`§C.1` 与 `N5.1-03` 也引用 `baselines.valuation.independent_judgment`。

**实测**（`schema/models.py::Valuation` 的**全部**字段）：

```
Valuation: ['method_class', 'range', 'probability', 'formula_ref',
            'forecast_assumptions', 'valuation_params']
```

⇒ **只有 `probability` 在**；以下 3 个**全仓零命中**（`grep -rn` 代码区与设计区）：

| 缺失字段 | 谁需要它 | 后果 |
|---|---|---|
| `scenario_tag` | `§E.3` `scenario_guard.assert_scenario_match(stock, benchmark)` 比较 `stock.scenario_tag != benchmark.scenario_tag` | **13-B 的情景一致性检查无法实现**（被比较的字段不存在） |
| `independent_judgment` | `§C.1` 三份判断之一的**存储落位**；`N5.1-03` 验收面 | 三份判断无法"分别查询" |
| `implied_ref` | `§0 表`声明的字段 | 独立判断 → 价格隐含的引用链缺环 |

**另**：`input_source` **存在但落位不同** —— 设计写 `baselines.valuation.input_source`，
实现在 `schema/models.py::AssumptionInput.input_source`（`Ch5 §D.5` / `N5.3-04`）。
**概念没丢，落位不一致**。

**我为什么没修**：扩表是**需求方裁定项**（`Ch4 §B.1` 的裁定先例：扩表须走需求方），
且 13-R 的边界是"只写 `registry/rule-candidates/**`" ⇒ **越界**。
**建议**：由 team-lead 决定是否开一张"Ch5 schema 补字段"卡（影响面：13-B 全卡 + `N5.1-03` 验收）。
**已在消息里直接告知 team-lead。**

### G-13R-2 ★ `Business.model_class`（设计）↔ `business_type`（schema）**命名错位**

- `Ch4 §B.1` 的 business schema 写 `business_type: hardware # model_class：见 C`；
- `Ch4 §C.1/§C.2` 的**程序约束**用 `business.model_class`（伪码 `if business.model_class != metric_set.model_class`）；
- **实测** schema：`Business` 有 `business_type`，**没有** `model_class`。

⇒ `metric-sets.yaml::routing.key: model_class` 与 `Business.business_type` **不是同一个字符串**。
13-A 的 `route_guard.validate_binding()` 若**照伪码逐字写**，会在 `Business` 上找不到 `model_class` 而**报属性错误**。
**我保留了设计原词 `model_class`**（约束 1：不得改设计），并在文件注释里标明。
**需要一次显式消歧裁定**（`Ch2 §C.2 R-15 ③`：同名不同域必须可区分）。**已在消息里告知 13-A 的 owner。**

### G-13R-3 ★ `§G.1` 六项深度**并非全落在 `Baseline` 单对象上** ⇒ `sections_nonempty(baseline, cfg)` 签名不足

实测字段持有者：

| 深度 | 字段 | **实际持有者** |
|---|---|---|
| ① 业务与产业位置 | `business_refs` / `relations` | `Baseline.business_refs` ✅ ／ `relations` 是**独立事实表** `facts/relations.jsonl` |
| ③ 增长确定性 | `realization_stage` / `timeline` / `confidence` / `dependencies` | **`Driver`**（经 `driver_refs[]` 可达），**不在 `Baseline` 上** |
| ⑥ 价格与行动 | `expectation` / `implied` / `independent` | `facts/expectations.jsonl` ／ `facts/implied_requirements.jsonl` ／ `Baseline.valuation.independent_judgment`（**缺，见 G-13R-1**） |

⇒ `§G.2` 伪码的 `sections_nonempty(baseline, cfg)` **单对象签名**不足以判定"六节非空"，
需要**跨对象解析**。**我已在 `baseline.yaml` 的 `sections` 上方用注释标明**（未改设计伪码）。
**已在消息里告知 13-A 的 owner**（其 `completeness.py` 直接受影响）。

### G-13R-4 `scenario_tag` 与 `scenario_method_status` **同名值 `neutral`** 需消歧

`§J4` 的 `scenario_tag.values` 含 `neutral`；`§E.4` 的 `scenario_method_status.values` 也含 `neutral`。
**两个不同域共用同一 token** ⇒ `R-15 ③` 要求可区分。**已登记（注释 + 本节），未自行改名。**

### G-13R-5 ★ 候选 → `rules/` 的安装是**纯人工步骤，无机器绑定**

我把候选写到 `registry/rule-candidates/`，安装靠"主理人 `cp` + `lock_rules.py` 重锁"。
**风险**：安装时**手抄/改字**会让候选与生效配置漂移，而**当前没有任何检查器**比对
`registry/rule-candidates/*.yaml` 与 `rules/*.yaml`（我实测：无此守卫）。
**我没有自行新增守卫**（会动 `run_all_gates.py` 的共享门禁清单 + 需要需求方认可这套新目录约定）。
**建议**：加一个轻量守卫，断言"每份候选与其 `install_target` 的**内容除头部候选元信息块外逐字一致**"
（可行性：候选里已声明 `install_target`，可机器核对）。**请 team-lead 裁定。**

### G-13R-6 环境/流程备注（沿用前两轮结论，不重复展开）

- 本 worktree 建好后**必须**先跑 `sh system/scripts/ops/bootstrap_worktree.sh`
  （**git 不跟踪只读位** ⇒ 新检出的 `rules/*.yaml` 是 `0644`，`rules_lock_guard` 必红）。**本次已跑**。
- 我用 `/tmp/wsse-venv` 隔离 venv（`pydantic 2.13.5 / pytest 9.1.1 / PyYAML 6.0.3 / jsonschema 4.26.0`，
  与 `system/requirements.txt` 逐字一致）；**未改动用户环境**。

---

## §8 给主理人的安装清单（照做即可）

```bash
# ① 逐字核对（可选但建议）：候选 ↔ 报告 §4 逐键对照表
ls -l system/registry/rule-candidates/

# ② 安装（★ 只做这一步是"人工步骤"，见 G-13R-5）
chmod u+w system/rules
cp system/registry/rule-candidates/metric-sets.yaml       system/rules/metric-sets.yaml
cp system/registry/rule-candidates/baseline.yaml          system/rules/baseline.yaml
cp system/registry/rule-candidates/valuation-methods.yaml system/rules/valuation-methods.yaml
cp system/registry/rule-candidates/scenario.yaml          system/rules/scenario.yaml
# ★ 安装前请**删除每份文件头部的"候选元信息"块**（§3.1 已注明），使与既有房型零差异

# ③ 重锁 + 校验
python system/scripts/ops/lock_rules.py
python system/scripts/checks/rules_lock_guard.py system     # 期望 exit=0
python system/scripts/checks/conflict_scan.py system --timing pre_commit   # 期望 exit=0（L3 会扫新文件）
python system/scripts/ops/run_all_gates.py --timeout 30     # 期望非零计数 1（仅 traceback.py，基点既有）

# ④ 安装后 rules/ 应变回 0444（lock_rules.py 负责）：
ls -l system/rules/ | grep -E "metric-sets|baseline|valuation-methods|scenario"
```

> ⚠️ **安装时机**：13-A / 13-B 的**测试**按任务卡"在夹具副本里自备候选文件"，代码路径按
> `rules/<name>.yaml` 读 ⇒ **13-A/13-B 的合并早于本次安装也不会红**；但**生产路径**需要安装后才能跑通。
> 建议**安装与 13-A/13-B 合并同一轮完成**，避免出现"代码就绪但配置不在位"的中间态。

---

## 附：本报告的证据可复现性

```bash
cd /Users/gaza/Developer/InvestSigh/.worktrees/ws-ch13r-rules/system
export CODEBUDDY_SAFE_DELETE_SANDBOX=0 CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0

# YAML 可解析（§2.1）
python -c "import yaml,pathlib; [print(p.name, bool(yaml.safe_load(p.read_text()))) \
  for p in sorted(pathlib.Path('registry/rule-candidates').glob('*.yaml'))]"

# 候选真被 L3 扫到（§2.2）：两处计数应相等
python scripts/checks/conflict_scan.py . --timing pre_commit | grep l3_config_files
find rules registry -type f \( -name '*.yaml' -o -name '*.yml' -o -name '*.json' \) | wc -l

# rules/ 零改动（§2.5）
git status --short system/rules        # 期望：空

# 全门禁（§2.4）
python scripts/ops/run_all_gates.py --timeout 30   # 期望：非零计数 1
```
